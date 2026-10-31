import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { components } from '../api/schema'
import { api } from '../api/client'
import { messages } from '../locales'
import { handlers } from '../mocks/handlers'
import downloadHandlers from '../mocks/handlers/download'
import { server } from '../mocks/server'
import downloadRoutes from '../router/routes/download'
import { render } from './helpers'

type JobRun = components['schemas']['JobRun']
type Track = components['schemas']['Track']

const track = (id: number, title: string): Track => ({
  id,
  album: 1,
  title,
  track_number: id,
  disc_number: 1,
  duration: 200,
  isrc: null,
  artists: [{ id: 1, name: 'Daft Punk', position: 0 }],
  downloaded: false,
  deezer_id: id,
  musicbrainz_id: null,
})
const run = (fields: Partial<JobRun> = {}): JobRun => ({
  id: 9,
  kind: 'download',
  params: {},
  user: 'demo',
  status: 'running',
  started_at: '2026-01-01T10:00:00Z',
  finished_at: null,
  done: 1,
  total: 2,
  current: 'One More Time',
  summary: {},
  ...fields,
})
const page = <T>(results: T[], next: string | null = null, previous: string | null = null) =>
  HttpResponse.json({ count: results.length, next, previous, results })

/**
 * Prepara la API: canciones pendientes, artistas, álbumes, la última descarga (`latest`) y lo
 * que responde el lanzamiento (`launch`). Apunta las peticiones de canciones y los lanzamientos.
 */
function serve({
  latest = [] as JobRun[],
  launch = () => HttpResponse.json(run({ status: 'pending' }), { status: 201 }) as Response,
  detail = run({ status: 'succeeded', done: 2 }),
} = {}) {
  const trackQueries: Record<string, string>[] = []
  const launched: unknown[] = []
  const runQueries: Record<string, string>[] = []
  server.use(
    http.get('/api/v1/catalog/tracks/', ({ request }) => {
      const query = Object.fromEntries(new URL(request.url).searchParams)
      trackQueries.push(query)
      return query.page === '2'
        ? page([track(3, 'Digital Love')], null, 'http://x/?page=1')
        : page([track(1, 'One More Time'), track(2, 'Aerodynamic')], 'http://x/?page=2')
    }),
    http.get('/api/v1/catalog/artists/', () => page([{ id: 1, name: 'Daft Punk' }])),
    http.get('/api/v1/catalog/albums/', ({ request }) =>
      page(
        new URL(request.url).searchParams.get('artist') === '1'
          ? [{ id: 1, title: 'Discovery' }]
          : [
              { id: 1, title: 'Discovery' },
              { id: 2, title: 'Homework' },
            ],
      ),
    ),
    http.get('/api/v1/jobs/runs/', ({ request }) => {
      runQueries.push(Object.fromEntries(new URL(request.url).searchParams))
      return page(latest)
    }),
    http.post('/api/v1/jobs/runs/', async ({ request }) => {
      launched.push(await request.json())
      return launch()
    }),
    http.get('/api/v1/jobs/runs/:id/', () => HttpResponse.json(detail)),
    http.get('/api/v1/jobs/runs/:id/lines/', () => HttpResponse.json([])),
  )
  return { trackQueries, launched, runQueries }
}

async function mount(path = '/descargar', locale = 'es', ready = 'One More Time') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [...downloadRoutes, { path: '/otra', name: 'other', component: { template: '<p/>' } }],
  })
  await router.push(path)
  const wrapper = render({ template: '<RouterView />' }, { global: { plugins: [router] } }, locale)
  await vi.waitFor(() => expect(wrapper.text()).toContain(ready))
  return { wrapper, router }
}

const button = (wrapper: Awaited<ReturnType<typeof mount>>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text().includes(text))!

describe('DownloadView', () => {
  it('lista solo las pendientes y lo deja fijo en la URL', async () => {
    const api = serve()
    const { router } = await mount('/descargar?downloaded=true')
    expect(router.currentRoute.value.query.downloaded).toBe('false')
    expect(api.trackQueries[0]).toEqual({ downloaded: 'false' })
    expect(api.runQueries[0]).toEqual({ kind: 'download' })
  })

  it('filtra por artista y álbum, y cambiar de artista quita el álbum', async () => {
    const api = serve()
    const { wrapper, router } = await mount('/descargar?album=2')
    const [artist, album] = wrapper.findAll('select')
    await vi.waitFor(() => expect(album!.findAll('option')).toHaveLength(3))
    await artist!.setValue('1')
    await vi.waitFor(() => expect(router.currentRoute.value.query).toMatchObject({ artist: '1' }))
    expect(router.currentRoute.value.query.album).toBeUndefined()
    await vi.waitFor(() => expect(album!.findAll('option')).toHaveLength(2))
    await album!.setValue('1')
    await vi.waitFor(() =>
      expect(api.trackQueries.at(-1)).toEqual({ downloaded: 'false', artist: '1', album: '1' }),
    )
  })

  it('mantiene la selección al cambiar de página y descarga las elegidas', async () => {
    const api = serve()
    const { wrapper } = await mount()
    const chosen = button(wrapper, 'Descargar las elegidas')
    expect(chosen.attributes('disabled')).toBeDefined()
    await wrapper.findAll('input[type=checkbox]')[0]!.setValue(true)
    await button(wrapper, 'Siguiente').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Digital Love'))
    await wrapper.findAll('input[type=checkbox]')[0]!.setValue(true)
    expect(chosen.text()).toContain('(2)')
    await chosen.trigger('click')
    await vi.waitFor(() => expect(api.launched).toHaveLength(1))
    expect(api.launched[0]).toEqual({ kind: 'download', params: { track_ids: [1, 3] } })
    await button(wrapper, 'Anterior').trigger('click')
    await vi.waitFor(() =>
      expect(api.trackQueries.at(-1)).toEqual({ downloaded: 'false', page: '1' }),
    )
  })

  it('quitar una casilla la saca de la selección', async () => {
    serve()
    const { wrapper } = await mount()
    const box = wrapper.findAll('input[type=checkbox]')[1]!
    await box.setValue(true)
    await box.setValue(false)
    expect(button(wrapper, 'Descargar las elegidas').attributes('disabled')).toBeDefined()
  })

  it('descarga todas las pendientes y, al terminar, recarga la lista', async () => {
    const api = serve()
    const { wrapper } = await mount()
    await button(wrapper, 'Descargar todas las pendientes').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Terminada'))
    expect(api.launched[0]).toEqual({ kind: 'download', params: { all_pending: true } })
    await vi.waitFor(() => expect(api.trackQueries).toHaveLength(2))
  })

  it('si ya hay una descarga en marcha, la muestra y no deja lanzar otra', async () => {
    serve({ latest: [run()], detail: run() })
    const { wrapper } = await mount()
    await vi.waitFor(() => expect(wrapper.text()).toContain('En curso'))
    expect(wrapper.text()).toContain('Ya hay una descarga en marcha')
    expect(button(wrapper, 'Descargar todas las pendientes').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('no sigue la última descarga si ya terminó', async () => {
    serve({ latest: [run({ status: 'failed' })] })
    const { wrapper } = await mount()
    await vi.waitFor(() =>
      expect(button(wrapper, 'Descargar todas').attributes('disabled')).toBeUndefined(),
    )
    expect(wrapper.text()).not.toContain('Fallida')
  })

  it('si al lanzar otra ya ha empezado (409), sigue esa', async () => {
    let latest: JobRun[] = []
    serve({
      launch: () => {
        latest = [run()]
        return HttpResponse.json({ detail: 'Ya hay una tarea' }, { status: 409 })
      },
      detail: run(),
    })
    server.use(http.get('/api/v1/jobs/runs/', () => page(latest)))
    const { wrapper } = await mount()
    await button(wrapper, 'Descargar todas').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('En curso'))
    expect(wrapper.text()).not.toContain('Ya hay una tarea')
    wrapper.unmount()
  })

  it('muestra el error si no se puede lanzar', async () => {
    serve({ launch: () => HttpResponse.json({ detail: 'Sin permiso' }, { status: 403 }) })
    const { wrapper } = await mount()
    await button(wrapper, 'Descargar todas').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Sin permiso'))
  })

  it('muestra el error si no se cargan los filtros ni la última descarga', async () => {
    serve()
    server.use(
      http.get('/api/v1/catalog/artists/', () => new HttpResponse(null, { status: 500 })),
      http.get('/api/v1/jobs/runs/', () => new HttpResponse(null, { status: 500 })),
    )
    const { wrapper } = await mount()
    await vi.waitFor(() => expect(wrapper.text()).toContain('El servidor ha fallado'))
  })

  it('muestra el error si no se cargan las pendientes', async () => {
    serve()
    server.use(http.get('/api/v1/catalog/tracks/', () => new HttpResponse(null, { status: 500 })))
    await mount('/descargar', 'es', 'El servidor ha fallado')
  })

  it('tiene los mismos textos en español y en inglés', () => {
    const keys = (tree: object): string[] =>
      Object.entries(tree).flatMap(([k, v]) =>
        typeof v === 'string' ? [k] : keys(v).map((sub) => `${k}.${sub}`),
      )
    expect(keys(messages.en.download as object)).toEqual(keys(messages.es.download as object))
  })

  it('está traducida al inglés', async () => {
    serve()
    const { wrapper } = await mount('/descargar', 'en')
    expect(wrapper.text()).toContain('Download all pending')
  })
})

describe('respuestas simuladas de Descargar', () => {
  const titles = async (query: string) =>
    (await api<{ results: Track[] }>(`/api/v1/catalog/tracks/?${query}`)).results.map(
      (t) => t.title,
    )

  it('dan las pendientes, filtradas por álbum', async () => {
    expect(await titles('downloaded=false')).toHaveLength(3)
    expect(await titles('downloaded=false&album=2')).toEqual(['Da Funk'])
    expect(await api('/api/v1/catalog/artists/')).toMatchObject({ count: 1 })
    expect(await api('/api/v1/catalog/albums/')).toMatchObject({ count: 2 })
  })

  it('dejan pasar las demás listas de canciones', async () => {
    // Al final: solo responde si el handler de la zona deja pasar la petición. Solo los de
    // esta zona, porque otras (la Biblioteca) también responden a las listas de canciones.
    server.resetHandlers(
      ...downloadHandlers,
      http.get('/api/v1/catalog/tracks/', () => page([track(7, 'Otra')])),
    )
    expect(await titles('')).toEqual(['Otra'])
    // `resetHandlers` con argumentos sustituye los iniciales: se devuelven a su sitio.
    server.resetHandlers(...handlers)
  })
})
