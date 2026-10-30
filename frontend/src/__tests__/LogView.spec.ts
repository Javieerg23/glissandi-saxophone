import { flushPromises } from '@vue/test-utils'
import { http, HttpResponse } from 'msw'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'

import type { components } from '../api/schema'
import { POLL_MS } from '../composables/useJobRun'
import { messages } from '../locales'
import { server } from '../mocks/server'
import { routes } from '../router'
import { useSessionStore } from '../stores/session'
import LogView from '../views/log/LogView.vue'
import { render } from './helpers'
import { fill as fillNow } from './viewHelpers'

type JobRun = components['schemas']['JobRun']
type Tree = { [key: string]: string | Tree }

const library: RouteRecordRaw = {
  path: '/biblioteca',
  name: 'library',
  component: { render: () => null },
}

/** Monta el registro con sesión; `extra` añade rutas de otras vistas (p. ej. la Biblioteca). */
async function mountLog(
  path = '/registro',
  { role = 'administrador', extra = [] as RouteRecordRaw[] } = {},
) {
  server.use(http.get('/api/v1/accounts/me/', () => HttpResponse.json({ username: 'demo', role })))
  const pinia = createPinia()
  setActivePinia(pinia)
  await useSessionStore(pinia).fetchMe()
  const router = createRouter({ history: createMemoryHistory(), routes: [...routes, ...extra] })
  await router.push(path)
  await router.isReady()
  const wrapper = render(LogView, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

/** Apunta la query de cada petición a `path` y responde con `results`. */
function record(path: string, results: unknown[] = []) {
  const seen: Record<string, string>[] = []
  server.use(
    http.get(path, ({ request }) => {
      seen.push(Object.fromEntries(new URL(request.url).searchParams))
      return HttpResponse.json({ count: 60, next: 'x', previous: null, results })
    }),
  )
  return seen
}

/** Rellena un campo y espera a que la URL cambie, como haría quien escribe campo a campo. */
async function fill(
  wrapper: Awaited<ReturnType<typeof mountLog>>['wrapper'],
  label: string,
  value: string,
) {
  await fillNow(wrapper, label, value)
  await flushPromises()
}

async function choose(
  wrapper: Awaited<ReturnType<typeof mountLog>>['wrapper'],
  label: string,
  value: string,
) {
  const field = wrapper.findAll('label').find((l) => l.text() === label)
  await wrapper.get(`#${field?.attributes('for')}`).setValue(value)
  await flushPromises()
}

const job = (fields: Partial<JobRun>): JobRun => ({
  id: 9,
  kind: 'download',
  params: {},
  user: 'demo',
  status: 'running',
  started_at: '2026-01-01T10:00:00Z',
  finished_at: null,
  done: 1,
  total: 4,
  current: '',
  summary: {},
  ...fields,
})

afterEach(() => vi.useRealTimers())

describe('ruta del registro', () => {
  it('está en «Más» con su etiqueta', () => {
    const route = routes.find((r) => r.name === 'log')
    expect(route?.path).toBe('/registro')
    expect(route?.meta).toMatchObject({ navLabel: 'log.nav', navGroup: 'more' })
  })

  it('tiene las mismas claves en es y en', () => {
    const paths = (tree: Tree, prefix = ''): string[] =>
      Object.entries(tree).flatMap(([k, v]) =>
        typeof v === 'string' ? [`${prefix}${k}`] : paths(v, `${prefix}${k}.`),
      )
    expect(paths(messages.en.log as Tree)).toEqual(paths(messages.es.log as Tree))
  })
})

describe('pestaña Actividad', () => {
  it('es la pestaña por defecto y lista las entradas', async () => {
    const { wrapper } = await mountLog()
    expect(wrapper.get('[aria-current="page"]').text()).toBe('Actividad')
    expect(wrapper.text()).toContain('catalog.artist.updated')
    expect(wrapper.text()).toContain('Artista n.º 7')
    expect(wrapper.text()).toContain('Sistema')
  })

  it('manda los filtros a la API y los deja en la URL', async () => {
    const seen = record('/api/v1/activity/entries/')
    const { wrapper, router } = await mountLog()
    await fill(wrapper, 'Desde', '2026-01-01')
    await fill(wrapper, 'Hasta', '2026-01-31')
    await fill(wrapper, 'Usuario', 'demo')
    await fill(wrapper, 'Acción', 'blocked')
    await choose(wrapper, 'Tipo de objeto', 'catalog.track')
    expect(seen.at(-1)).toEqual({
      date_from: '2026-01-01',
      date_to: '2026-01-31',
      username: 'demo',
      action: 'blocked',
      object_type: 'catalog.track',
    })
    expect(router.currentRoute.value.query).toMatchObject({
      username: 'demo',
      object_type: 'catalog.track',
    })
  })

  it('lee los filtros de la URL al entrar', async () => {
    const seen = record('/api/v1/activity/entries/')
    const { wrapper } = await mountLog('/registro?action=import')
    expect(seen[0]).toEqual({ action: 'import' })
    const field = wrapper.findAll('label').find((l) => l.text() === 'Acción')
    expect((wrapper.get(`#${field?.attributes('for')}`).element as HTMLInputElement).value).toBe(
      'import',
    )
  })

  it('enlaza al historial en la Biblioteca cuando la vista existe', async () => {
    const { wrapper, router } = await mountLog('/registro', { extra: [library] })
    const link = wrapper.get('a.history')
    expect(link.text()).toBe('Ver historial')
    expect(router.resolve(link.attributes('href') as string).query).toEqual({
      tab: 'artists',
      id: '7',
      panel: 'history',
    })
  })

  it('no enlaza sin la vista Biblioteca ni para objetos fuera del catálogo', async () => {
    server.use(
      http.get('/api/v1/activity/entries/', () =>
        HttpResponse.json({
          count: 1,
          results: [
            {
              id: 3,
              created_at: '2026-01-01T10:00:00Z',
              user: 1,
              username: 'demo',
              action: 'proxies.created',
              object_type: 'proxies.proxy',
              object_id: '2',
              detail: {},
            },
            {
              id: 4,
              created_at: '2026-01-01T10:00:00Z',
              user: 1,
              username: 'demo',
              action: 'otra.cosa',
              object_type: 'otra.cosa',
              object_id: '5',
              detail: {},
            },
          ],
        }),
      ),
    )
    const { wrapper } = await mountLog('/registro', { extra: [library] })
    expect(wrapper.text()).toContain('Proxy n.º 2')
    expect(wrapper.text()).toContain('otra.cosa n.º 5')
    expect(wrapper.find('a.history').exists()).toBe(false)
  })

  it('pasa de página', async () => {
    const seen = record('/api/v1/activity/entries/')
    const { wrapper } = await mountLog()
    expect(wrapper.text()).toContain('Página 1 · 60 en total')
    const [previous, next] = wrapper.findAll('.pager button')
    expect(previous.attributes('disabled')).toBeDefined()
    await next.trigger('click')
    await flushPromises()
    expect(seen.at(-1)).toEqual({ page: '2' })
  })

  it('vuelve a la página anterior', async () => {
    const seen: Record<string, string>[] = []
    server.use(
      http.get('/api/v1/activity/entries/', ({ request }) => {
        seen.push(Object.fromEntries(new URL(request.url).searchParams))
        return HttpResponse.json({ count: 60, next: null, previous: 'x', results: [] })
      }),
    )
    const { wrapper } = await mountLog('/registro?page=2')
    const [previous, next] = wrapper.findAll('.pager button')
    expect(next.attributes('disabled')).toBeDefined()
    await previous.trigger('click')
    await flushPromises()
    expect(seen.at(-1)).toEqual({ page: '1' })
  })

  it('muestra el error de la API', async () => {
    server.use(http.get('/api/v1/activity/entries/', () => HttpResponse.json({}, { status: 500 })))
    const { wrapper } = await mountLog()
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
  })
})

describe('errores de la API', () => {
  it.each([
    ['jobs', '/api/v1/jobs/runs/'],
    ['technical', '/api/v1/activity/logs/'],
  ])('la pestaña %s muestra el error de su lista', async (tab, path) => {
    server.use(http.get(path, () => HttpResponse.json({}, { status: 500 })))
    const { wrapper } = await mountLog(`/registro?tab=${tab}`)
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
  })
})

describe('pestaña Tareas', () => {
  it('lista las ejecuciones y manda sus filtros', async () => {
    const seen = record('/api/v1/jobs/runs/', [job({})])
    const { wrapper, router } = await mountLog('/registro?tab=jobs')
    expect(wrapper.get('[aria-current="page"]').text()).toBe('Tareas')
    expect(wrapper.text()).toContain('Descarga')
    expect(wrapper.text()).toContain('1 / 4')
    await choose(wrapper, 'Tipo de tarea', 'import')
    await choose(wrapper, 'Estado', 'failed')
    await fill(wrapper, 'Desde', '2026-01-01T00:00')
    await fill(wrapper, 'Hasta', '2026-01-02T00:00')
    await flushPromises()
    expect(seen.at(-1)).toEqual({
      kind: 'import',
      status: 'failed',
      started_after: '2026-01-01T00:00',
      started_before: '2026-01-02T00:00',
    })
    expect(router.currentRoute.value.query.tab).toBe('jobs')
  })

  it('muestra el tipo tal cual si no tiene traducción', async () => {
    record('/api/v1/jobs/runs/', [job({ kind: 'library_restore', status: 'pending', total: 0 })])
    const { wrapper } = await mountLog('/registro?tab=jobs')
    expect(wrapper.text()).toContain('library_restore')
    // Sin total todavía no hay progreso que mostrar.
    expect(wrapper.find('td[data-label="Progreso"]').text()).toBe('')
  })

  it('abre el detalle y lo actualiza mientras la tarea está en marcha', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    record('/api/v1/jobs/runs/', [job({})])
    // La primera respuesta es la de abrirla; la segunda, la del primer sondeo.
    const states = [
      job({ done: 1 }),
      job({ done: 1 }),
      job({ done: 3 }),
      job({ status: 'succeeded', done: 4 }),
    ]
    let calls = 0
    server.use(
      http.get('/api/v1/jobs/runs/9/', () => HttpResponse.json(states[Math.min(calls++, 3)])),
      http.get('/api/v1/jobs/runs/9/lines/', () => HttpResponse.json([])),
    )
    const { wrapper, router } = await mountLog('/registro?tab=jobs')
    await wrapper.get('a.detail').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.run).toBe('9')
    expect(wrapper.get('.run h2').text()).toBe('Tarea n.º 9')
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('1 / 4'))
    await vi.advanceTimersByTimeAsync(POLL_MS)
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('3 / 4'))
    await vi.advanceTimersByTimeAsync(POLL_MS)
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('Terminada'))
    await vi.advanceTimersByTimeAsync(POLL_MS * 3)
    expect(calls).toBe(4)

    await wrapper.get('.run button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.run).toBeUndefined()
    expect(wrapper.find('.run').exists()).toBe(false)
  })
})

describe('pestaña Logs técnicos', () => {
  it('lista los logs con nivel y traza desplegable, y manda sus filtros', async () => {
    const { wrapper } = await mountLog('/registro?tab=technical')
    expect(wrapper.get('[aria-current="page"]').text()).toBe('Logs técnicos')
    expect(wrapper.text()).toContain('Error')
    expect(wrapper.get('details summary').text()).toBe('Traza')
    expect(wrapper.findAll('details')).toHaveLength(1)

    const seen = record('/api/v1/activity/logs/')
    await choose(wrapper, 'Nivel mínimo', '40')
    await fill(wrapper, 'Módulo', 'catalog')
    await fill(wrapper, 'Número de tarea', '5')
    await fill(wrapper, 'Buscar en el mensaje', 'yt-dlp')
    await fill(wrapper, 'Desde', '2026-01-01')
    await fill(wrapper, 'Hasta', '2026-01-02')
    await flushPromises()
    expect(seen.at(-1)).toEqual({
      min_level: '40',
      module: 'catalog',
      task: '5',
      search: 'yt-dlp',
      date_from: '2026-01-01',
      date_to: '2026-01-02',
    })
  })

  it('cambiar de pestaña quita los filtros de la anterior', async () => {
    const { wrapper, router } = await mountLog('/registro?tab=technical&module=jobs')
    const link = wrapper.findAll('.tabs a').find((a) => a.text() === 'Actividad')
    await link?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tab: 'activity' })
  })

  it('muestra con su número un nivel sin nombre', async () => {
    record('/api/v1/activity/logs/', [
      {
        id: 1,
        created_at: '2026-01-01T10:00:00Z',
        level: 0,
        logger_name: 'x',
        msg: 'm',
        trace: null,
      },
    ])
    const { wrapper } = await mountLog('/registro?tab=technical')
    expect(wrapper.get('td[data-label="Nivel"]').text()).toBe('0')
  })

  it('no la ve quien no es administrador, ni siquiera desde la URL', async () => {
    let asked = false
    server.use(
      http.get('/api/v1/activity/logs/', () => {
        asked = true
        return HttpResponse.json({ count: 0, results: [] })
      }),
    )
    const { wrapper } = await mountLog('/registro?tab=technical', { role: 'usuario' })
    expect(wrapper.findAll('.tabs a').map((a) => a.text())).toEqual(['Actividad', 'Tareas'])
    expect(wrapper.get('[aria-current="page"]').text()).toBe('Actividad')
    expect(asked).toBe(false)
  })
})
