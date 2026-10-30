import { flushPromises } from '@vue/test-utils'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { components } from '../api/schema'
import { POLL_MS } from '../composables/useJobRun'
import { messages } from '../locales'
import { routes } from '../router'
import { server } from '../mocks/server'
import UtilitiesView from '../views/UtilitiesView.vue'
import { render } from './helpers'
import { mountView } from './viewHelpers'

type JobRun = components['schemas']['JobRun']

const run = (fields: Partial<JobRun> = {}): JobRun => ({
  id: 8,
  kind: 'maintenance',
  params: {},
  user: 'demo',
  status: 'running',
  started_at: '2026-01-01T10:00:00Z',
  finished_at: null,
  done: 1,
  total: 3,
  current: 'a.mp3',
  summary: {},
  ...fields,
})

/** Sirve la tarea: el detalle devuelve `states` por orden (el último se repite). */
function serve(states: JobRun[]) {
  const bodies: unknown[] = []
  let detail = 0
  server.use(
    http.post('/api/v1/jobs/runs/', async ({ request }) => {
      bodies.push(await request.json())
      return HttpResponse.json(run({ status: 'pending' }), { status: 201 })
    }),
    http.get('/api/v1/jobs/runs/8/', () =>
      HttpResponse.json(states[Math.min(detail++, states.length - 1)]),
    ),
    http.get('/api/v1/jobs/runs/8/lines/', () => HttpResponse.json([])),
  )
  return bodies
}

const mount = async () => (await mountView(UtilitiesView, '/utilidades')).wrapper
const boxes = (wrapper: Awaited<ReturnType<typeof mount>>) =>
  wrapper.findAll('input[type="checkbox"]')
const startButton = (wrapper: Awaited<ReturnType<typeof mount>>) =>
  wrapper.findAll('button').find((b) => b.text() === 'Ejecutar')!

beforeEach(() => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }))
afterEach(() => vi.useRealTimers())

describe('UtilitiesView', () => {
  it('ofrece las tres operaciones, todas marcadas', async () => {
    const wrapper = await mount()
    expect(wrapper.findAll('.check').map((c) => c.text())).toEqual([
      'Volver a etiquetar los ficheros descargados',
      'Comprobar que los ficheros siguen en disco',
      'Revisar los artistas de cada canción con Deezer',
    ])
    expect(boxes(wrapper).every((b) => (b.element as HTMLInputElement).checked)).toBe(true)
  })

  it('lanza solo las operaciones elegidas', async () => {
    const bodies = serve([run({ status: 'succeeded' })])
    const wrapper = await mount()
    await boxes(wrapper)[0].setValue(false)
    await startButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toEqual({
      kind: 'maintenance',
      params: { operations: ['check_files', 'review_artists'] },
    })
  })

  it('no deja lanzar sin operaciones', async () => {
    const wrapper = await mount()
    for (const box of boxes(wrapper)) await box.setValue(false)
    expect(startButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('sigue la tarea y no deja lanzar otra mientras está activa', async () => {
    serve([run()])
    const wrapper = await mount()
    await startButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('En curso'))
    expect(startButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.find('.summary').exists()).toBe(false)
  })

  it('muestra el resumen final con los ficheros que faltan y los cambios', async () => {
    serve([
      run(),
      run({
        status: 'succeeded',
        done: 3,
        summary: {
          retag: { retagged: 5, failed: 1 },
          check_files: { checked: 6, missing: [3, 7] },
          review_artists: { reviewed: 4, differences: 2, errors: 0 },
        },
      }),
    ])
    const wrapper = await mount()
    await startButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('En curso'))
    await vi.advanceTimersByTimeAsync(POLL_MS)
    await vi.waitFor(() => expect(wrapper.find('.summary').exists()).toBe(true))
    expect(wrapper.findAll('.summary li').map((l) => l.text())).toEqual([
      'Ficheros etiquetados: 5. Fallidos: 1.',
      'Ficheros comprobados: 6. Faltan: 2.',
      'Descargas sin fichero: #3, #7.',
      'Canciones revisadas: 4. Con diferencias: 2. Sin respuesta de Deezer: 0.',
    ])
  })

  it('resume solo las operaciones hechas y omite la lista si no falta nada', async () => {
    serve([run({ status: 'stopped', summary: { check_files: { checked: 2, missing: [] } } })])
    const wrapper = await mount()
    await startButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('.summary').exists()).toBe(true))
    expect(wrapper.findAll('.summary li').map((l) => l.text())).toEqual([
      'Ficheros comprobados: 2. Faltan: 0.',
    ])
  })

  it('sin resumen (tarea fallida) no muestra el apartado', async () => {
    serve([run({ status: 'failed' })])
    const wrapper = await mount()
    await startButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('Fallida'))
    expect(wrapper.find('.summary').exists()).toBe(false)
  })

  it('muestra el rechazo de la API al lanzar', async () => {
    server.use(
      http.post('/api/v1/jobs/runs/', () =>
        HttpResponse.json({ detail: 'Ya hay una tarea de este tipo en curso.' }, { status: 409 }),
      ),
    )
    const wrapper = await mount()
    await startButton(wrapper).trigger('click')
    await vi.waitFor(() =>
      expect(wrapper.get('[role="alert"]').text()).toBe('Ya hay una tarea de este tipo en curso.'),
    )
  })

  it('enlaza a la copia de la biblioteca cuando esa ruta existe', async () => {
    expect((await mount()).find('a[href="/copia"]').exists()).toBe(false)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [...routes, { path: '/copia', name: 'library-backup', component: UtilitiesView }],
    })
    await router.push('/utilidades')
    const wrapper = render(UtilitiesView, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.get('a[href="/copia"]').text()).toBe('Copia de la biblioteca')
  })

  it('traduce al inglés', async () => {
    const wrapper = render(
      UtilitiesView,
      {
        global: { plugins: [createRouter({ history: createMemoryHistory(), routes })] },
      },
      'en',
    )
    expect(wrapper.get('h1').text()).toBe('Utilities')
    expect(wrapper.findAll('button').at(-1)!.text()).toBe('Run')
  })

  it('tiene las mismas claves en es y en', () => {
    expect(Object.keys(messages.en.utilities as object)).toEqual(
      Object.keys(messages.es.utilities as object),
    )
  })
})
