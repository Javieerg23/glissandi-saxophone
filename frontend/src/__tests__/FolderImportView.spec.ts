import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { routes } from '../router'
import { server } from '../mocks/server'
import FolderImportView from '../views/FolderImportView.vue'
import { fill, mountView } from './viewHelpers'

async function launch(folder = ' Daft Punk ') {
  const { wrapper } = await mountView(FolderImportView, '/importar/carpeta')
  await fill(wrapper, 'Carpeta', folder)
  await wrapper.get('form').trigger('submit')
  return wrapper
}

describe('FolderImportView', () => {
  it('tiene ruta propia sin entrada en la navegación', () => {
    const route = routes.find((r) => r.name === 'import-folder')
    expect(route?.path).toBe('/importar/carpeta')
    expect(route?.meta?.navLabel).toBeUndefined()
  })

  it('lanza folder_import con la carpeta y lista los ficheros no enlazados', async () => {
    const sent: unknown[] = []
    server.events.on('request:start', async ({ request }) => {
      if (request.method === 'POST') sent.push(await request.clone().json())
    })
    const wrapper = await launch()

    await vi.waitFor(() => expect(wrapper.findAll('tbody tr')).toHaveLength(2))
    server.events.removeAllListeners()
    expect(sent).toEqual([{ kind: 'folder_import', params: { folder: 'Daft Punk' } }])
    expect(wrapper.text()).toContain('2 enlazados, 0 ya estaban enlazados y 2 sin enlazar.')
    expect(wrapper.get('tbody tr').text()).toContain('Daft Punk/demo.mp3')
    expect(wrapper.get('tbody tr').text()).toContain('Sin etiquetas o sin título')
    expect(wrapper.text()).toContain('Daft Punk/one.mp3 → «One More Time»')
  })

  it('muestra el código del motivo si no tiene traducción', async () => {
    const run = {
      id: 30,
      kind: 'folder_import',
      status: 'succeeded',
      done: 1,
      total: 1,
      current: '',
      summary: { linked: 1, unlinked: [{ file: 'a.mp3', reason: 'nuevo' }] },
    }
    // El alta también devuelve la ejecución: si no, la vista pinta antes el resumen por defecto.
    server.use(
      http.post('/api/v1/jobs/runs/', () => HttpResponse.json(run, { status: 201 })),
      http.get('/api/v1/jobs/runs/30/', () => HttpResponse.json(run)),
    )
    const wrapper = await launch('')
    // El alta simulada ya trae un resumen terminado: hay que esperar al del sondeo.
    await vi.waitFor(() => expect(wrapper.find('tbody tr').text()).toContain('nuevo'))
    expect(wrapper.text()).toContain('1 enlazados, 0 ya estaban enlazados y 1 sin enlazar.')
  })

  it('indica que no quedan ficheros sin enlazar', async () => {
    server.use(
      http.get('/api/v1/jobs/runs/30/', () =>
        HttpResponse.json({
          id: 30,
          status: 'succeeded',
          done: 3,
          total: 3,
          current: '',
          summary: { linked: 0, already_linked: 3 },
        }),
      ),
    )
    const wrapper = await launch()
    await vi.waitFor(() =>
      expect(wrapper.text()).toContain('0 enlazados, 3 ya estaban enlazados y 0 sin enlazar.'),
    )
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('no muestra resultado mientras la tarea sigue en marcha', async () => {
    server.use(
      http.post('/api/v1/jobs/runs/', () =>
        HttpResponse.json(
          { id: 31, kind: 'folder_import', status: 'running', done: 1, total: 3, summary: {} },
          { status: 201 },
        ),
      ),
      http.get('/api/v1/jobs/runs/31/', () =>
        HttpResponse.json({ id: 31, status: 'running', done: 1, total: 3, current: 'a.mp3' }),
      ),
    )
    const wrapper = await launch()
    await vi.waitFor(() => expect(wrapper.text()).toContain('a.mp3'))
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('table').exists()).toBe(false)
    wrapper.unmount()
  })

  it('muestra el error si la API rechaza la tarea', async () => {
    server.use(
      http.post('/api/v1/jobs/runs/', () =>
        HttpResponse.json({ detail: 'No permitido.' }, { status: 403 }),
      ),
    )
    const wrapper = await launch()
    await vi.waitFor(() => expect(wrapper.text()).toContain('No permitido.'))
  })

  it('tiene los mismos textos en es y en', async () => {
    const { messages } = await import('../locales')
    const keys = (tree: object): string[] =>
      Object.entries(tree).flatMap(([k, v]) =>
        typeof v === 'string' ? [k] : keys(v).map((c) => `${k}.${c}`),
      )
    expect(keys(messages.en.importFolder as object)).toEqual(
      keys(messages.es.importFolder as object),
    )
  })
})
