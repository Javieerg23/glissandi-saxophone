import { flushPromises } from '@vue/test-utils'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { messages } from '../locales'
import { server } from '../mocks/server'
import { routes } from '../router'
import LibraryBackupView from '../views/LibraryBackupView.vue'
import { mountView } from './viewHelpers'

type Tree = { [key: string]: string | Tree }

function paths(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === 'string' ? [`${prefix}${k}`] : paths(v, `${prefix}${k}.`),
  )
}

async function mount() {
  return mountView(LibraryBackupView, '/biblioteca/copia')
}

/** Elige un fichero en el selector, como haría el usuario. */
async function choose(wrapper: Awaited<ReturnType<typeof mount>>['wrapper'], content = '[]') {
  const input = wrapper.get('input[type="file"]')
  const files = content ? [new File([content], 'copia.json')] : []
  Object.defineProperty(input.element, 'files', { value: files, configurable: true })
  await input.trigger('change')
  await flushPromises()
}

describe('LibraryBackupView', () => {
  it('es solo para administradores y no sale en la navegación', () => {
    const route = routes.find((r) => r.name === 'library-backup')
    expect(route?.meta).toEqual({ adminOnly: true })
  })

  it('tiene los mismos textos en español y en inglés', () => {
    const es = paths(messages.es.libraryBackup as Tree)
    expect(paths(messages.en.libraryBackup as Tree)).toEqual(es)
  })

  it('enlaza la descarga de la copia', async () => {
    const { wrapper } = await mount()
    const link = wrapper.get('a[download]')
    expect(link.attributes('href')).toBe('/api/v1/catalog/backup/')
    expect(link.text()).toBe('Descargar la copia')
  })

  it('muestra la vista previa del fichero elegido', async () => {
    const { wrapper } = await mount()
    expect(wrapper.find('table').exists()).toBe(false)
    await choose(wrapper)
    const rows = wrapper.findAll('tbody tr').map((r) => r.findAll('th, td').map((c) => c.text()))
    expect(rows).toEqual([
      ['Artistas', '3', '1', '2'],
      ['Álbumes', '5', '2', '3'],
      ['Canciones', '40', '12', '28'],
      ['Descargas', '30', '12', '18'],
    ])
  })

  it('no hace nada si se quita el fichero', async () => {
    const { wrapper } = await mount()
    await choose(wrapper)
    await choose(wrapper, '')
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('rechaza un fichero no válido con el mensaje del servidor', async () => {
    server.use(
      http.post('/api/v1/catalog/backup/preview/', () =>
        HttpResponse.json({ detail: 'El fichero no es JSON válido.' }, { status: 400 }),
      ),
    )
    const { wrapper } = await mount()
    await choose(wrapper, '{roto')
    expect(wrapper.get('[role="alert"]').text()).toBe('El fichero no es JSON válido.')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('al confirmar sube el fichero y sigue la tarea', async () => {
    let sent = ''
    server.use(
      http.post('/api/v1/catalog/backup/restore/', async ({ request }) => {
        sent = await ((await request.formData()).get('file') as File).text()
        return HttpResponse.json({ id: 7, status: 'pending' }, { status: 201 })
      }),
      http.get('/api/v1/jobs/runs/7/', () =>
        HttpResponse.json({ id: 7, status: 'succeeded', done: 1, total: 1, current: '' }),
      ),
    )
    const { wrapper } = await mount()
    await choose(wrapper, '[{"model": "catalog.artist"}]')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(sent).toBe('[{"model": "catalog.artist"}]')
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).toContain('Terminada')
  })

  it('muestra el error si ya hay una importación en curso', async () => {
    server.use(
      http.post('/api/v1/catalog/backup/restore/', () =>
        HttpResponse.json({ detail: 'Ya hay una tarea de este tipo en curso.' }, { status: 409 }),
      ),
    )
    const { wrapper } = await mount()
    await choose(wrapper)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Ya hay una tarea de este tipo en curso.')
    expect(wrapper.find('table').exists()).toBe(true)
  })
})
