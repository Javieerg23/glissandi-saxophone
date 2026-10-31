import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { messages } from '../locales'
import { routes } from '../router'
import { server } from '../mocks/server'
import ImportView from '../views/ImportView.vue'
import { fill, mountView } from './viewHelpers'

type Wrapper = Awaited<ReturnType<typeof mountView>>['wrapper']

async function search(wrapper: Wrapper, q: string): Promise<void> {
  await fill(wrapper, 'Artista', q)
  await wrapper.get('form').trigger('submit')
}

const item = (wrapper: Wrapper, name: string) =>
  wrapper.findAll('.results li').find((li) => li.text().includes(name))!

const button = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text().startsWith(text))!

describe('ImportView', () => {
  it('con la búsqueda vacía no pregunta a Deezer y lo indica', async () => {
    let calls = 0
    server.use(
      http.get('/api/v1/catalog/deezer/artists/', () => {
        calls += 1
        return HttpResponse.json({ results: [], total: 0, next_index: null })
      }),
    )
    const { wrapper } = await mountView(ImportView, '/importar')
    expect(wrapper.text()).toContain('Escribe el nombre de un artista')
    await search(wrapper, '   ')
    expect(calls).toBe(0)
    expect(wrapper.text()).toContain('Escribe el nombre de un artista')
  })

  it('muestra los resultados con imagen, álbumes y su estado', async () => {
    const { wrapper } = await mountView(ImportView, '/importar')
    await search(wrapper, 'daft')
    await vi.waitFor(() => expect(wrapper.findAll('.results li')).toHaveLength(2))
    const daft = item(wrapper, 'Daft Punk')
    expect(daft.get('img').attributes('src')).toContain('250x250')
    expect(daft.text()).toContain('34 álbumes')
    expect(daft.text()).toContain('Ya en la biblioteca')
    const tribute = item(wrapper, 'Tribute')
    expect(tribute.find('img').exists()).toBe(false)
    expect(tribute.text()).toContain('Bloqueado')
    expect(tribute.get('input').attributes('disabled')).toBeDefined()
  })

  it('indica que no hay resultados', async () => {
    const { wrapper } = await mountView(ImportView, '/importar')
    await search(wrapper, 'nadie')
    await vi.waitFor(() =>
      expect(wrapper.text()).toContain('Deezer no ha encontrado ningún artista con «nadie».'),
    )
  })

  it('muestra el error de Deezer y lo borra en la siguiente búsqueda', async () => {
    server.use(
      http.get(
        '/api/v1/catalog/deezer/artists/',
        () => HttpResponse.json({ detail: 'Deezer no responde.' }, { status: 502 }),
        { once: true },
      ),
    )
    const { wrapper } = await mountView(ImportView, '/importar')
    await search(wrapper, 'daft')
    await vi.waitFor(() => expect(wrapper.get('[role="alert"]').text()).toBe('Deezer no responde.'))
    expect(wrapper.find('.results').exists()).toBe(false)
    await search(wrapper, 'daft')
    await vi.waitFor(() => expect(wrapper.findAll('.results li')).toHaveLength(2))
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('la selección se mantiene entre búsquedas y se puede quitar', async () => {
    const { wrapper } = await mountView(ImportView, '/importar')
    expect(button(wrapper, 'Importar').attributes('disabled')).toBeDefined()
    await search(wrapper, 'daft')
    await vi.waitFor(() => expect(wrapper.findAll('.results li')).toHaveLength(2))
    await item(wrapper, 'Daft Punk').get('input').setValue(true)
    await search(wrapper, 'justice')
    await vi.waitFor(() => expect(wrapper.findAll('.results li')).toHaveLength(1))
    await item(wrapper, 'Justice').get('input').setValue(true)
    expect(wrapper.get('.selected h2').text()).toBe('Seleccionados (2)')
    expect(button(wrapper, 'Importar').text()).toBe('Importar 2 artistas')
    await wrapper.get('[aria-label="Quitar Justice"]').trigger('click')
    expect(button(wrapper, 'Importar').text()).toBe('Importar 1 artista')
    expect((item(wrapper, 'Justice').get('input').element as HTMLInputElement).checked).toBe(false)
    await search(wrapper, 'daft')
    await vi.waitFor(() => expect(wrapper.findAll('.results li')).toHaveLength(2))
    const daft = item(wrapper, 'Daft Punk').get('input')
    expect((daft.element as HTMLInputElement).checked).toBe(true)
    await daft.setValue(false)
    expect(wrapper.find('.selected').exists()).toBe(false)
  })

  it('lanza la importación con los ids y la verificación, y la sigue', async () => {
    let body: unknown
    server.use(
      http.post('/api/v1/jobs/runs/', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(
          { id: 3, kind: 'import', status: 'running', done: 0, total: 2, current: 'Justice' },
          { status: 201 },
        )
      }),
      http.get('/api/v1/jobs/runs/3/', () =>
        HttpResponse.json({ id: 3, kind: 'import', status: 'running', done: 1, total: 2 }),
      ),
    )
    const { wrapper } = await mountView(ImportView, '/importar')
    await search(wrapper, 'u')
    await vi.waitFor(() => expect(wrapper.findAll('.results li')).toHaveLength(3))
    await item(wrapper, 'Daft Punk').get('input').setValue(true)
    await item(wrapper, 'Justice').get('input').setValue(true)
    await wrapper
      .findAll('label')
      .find((l) => l.text() === 'Verificar con MusicBrainz')!
      .get('input')
      .setValue(true)
    await button(wrapper, 'Importar').trigger('click')
    await vi.waitFor(() =>
      expect(body).toEqual({ kind: 'import', params: { artist_ids: [27, 1424], verify: true } }),
    )
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('1 / 2'))
    // La selección se vacía y no se puede lanzar otra mientras esta sigue en marcha.
    expect(wrapper.find('.selected').exists()).toBe(false)
    await item(wrapper, 'Justice').get('input').setValue(true)
    expect(button(wrapper, 'Importar').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('si la API rechaza la importación, la selección se mantiene', async () => {
    server.use(
      http.post('/api/v1/jobs/runs/', () =>
        HttpResponse.json({ detail: 'Ya hay una importación en curso.' }, { status: 409 }),
      ),
    )
    const { wrapper } = await mountView(ImportView, '/importar')
    await search(wrapper, 'justice')
    await vi.waitFor(() => expect(wrapper.findAll('.results li')).toHaveLength(1))
    await item(wrapper, 'Justice').get('input').setValue(true)
    await button(wrapper, 'Importar').trigger('click')
    await vi.waitFor(() =>
      expect(wrapper.get('.job [role="alert"]').text()).toBe('Ya hay una importación en curso.'),
    )
    expect(wrapper.get('.selected h2').text()).toBe('Seleccionados (1)')
  })

  it('enlaza a «Importar una carpeta» solo si esa vista existe', async () => {
    const { wrapper } = await mountView(ImportView, '/importar')
    expect(wrapper.text()).not.toContain('Importar una carpeta')
    routes.push({ path: '/importar/carpeta', name: 'import-folder', component: ImportView })
    try {
      const { wrapper: linked } = await mountView(ImportView, '/importar')
      expect(linked.get('a[href="/importar/carpeta"]').text()).toBe('Importar una carpeta')
    } finally {
      routes.pop()
    }
  })

  it('tiene los mismos textos en español y en inglés', () => {
    const keys = (tree: object, prefix = ''): string[] =>
      Object.entries(tree).flatMap(([k, v]) =>
        typeof v === 'string' ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`),
      )
    expect(keys(messages.en.import as object)).toEqual(keys(messages.es.import as object))
  })
})
