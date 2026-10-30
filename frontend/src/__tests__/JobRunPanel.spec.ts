import { flushPromises } from '@vue/test-utils'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import type { components } from '../api/schema'
import JobRunPanel from '../components/JobRunPanel.vue'
import { POLL_MS, useJobRun, type JobRunHandle } from '../composables/useJobRun'
import { server } from '../mocks/server'
import { render } from './helpers'

type JobRun = components['schemas']['JobRun']
type Line = components['schemas']['JobRunLine']

const run = (fields: Partial<JobRun> = {}): JobRun => ({
  id: 5,
  kind: 'download',
  params: {},
  user: 'demo',
  status: 'running',
  started_at: '2026-01-01T10:00:00Z',
  finished_at: null,
  done: 1,
  total: 4,
  current: 'One More Time',
  summary: {},
  ...fields,
})
const line = (position: number, level: Line['level'] = 'info'): Line => ({
  position,
  level,
  message: `línea ${position}`,
  created_at: '2026-01-01T10:00:00Z',
})

/**
 * Simula el servidor de una tarea: `states` son los estados que devuelve el detalle en cada
 * sondeo (el último se repite) y `batches` las líneas por petición. Apunta cada `after`.
 */
function serve(states: JobRun[], batches: Line[][] = []) {
  const afters: string[] = []
  let detail = 0
  server.use(
    http.post('/api/v1/jobs/runs/', () =>
      HttpResponse.json(run({ status: 'pending' }), { status: 201 }),
    ),
    http.get('/api/v1/jobs/runs/5/', () =>
      HttpResponse.json(states[Math.min(detail++, states.length - 1)]),
    ),
    http.get('/api/v1/jobs/runs/5/lines/', ({ request }) => {
      afters.push(new URL(request.url).searchParams.get('after') as string)
      return HttpResponse.json(batches.shift() ?? [])
    }),
  )
  return { afters, detailCalls: () => detail }
}

function mount(locale = 'es') {
  let job!: JobRunHandle
  const Host = defineComponent({
    setup() {
      job = useJobRun()
      return () => h(JobRunPanel, { job })
    },
  })
  const wrapper = render(Host, {}, locale)
  return { wrapper, job: () => job }
}

beforeEach(() => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }))
afterEach(() => vi.useRealTimers())

describe('useJobRun y JobRunPanel', () => {
  it('no muestra nada antes de lanzar', () => {
    expect(mount().wrapper.find('section').exists()).toBe(false)
  })

  it('lanza la tarea con su tipo y parámetros y muestra el progreso', async () => {
    let body: unknown
    serve([run()])
    server.use(
      http.post('/api/v1/jobs/runs/', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(run({ status: 'pending' }), { status: 201 })
      }),
    )
    const { wrapper, job } = mount()
    expect(await job().start('download', { all_pending: true })).toBe(true)
    expect(body).toEqual({ kind: 'download', params: { all_pending: true } })
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('En curso'))
    expect(wrapper.get('.job__status').text()).toContain('1 / 4')
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('25')
    expect(wrapper.get('.job__current').text()).toBe('One More Time')
  })

  it('lanza sin parámetros', async () => {
    let body: unknown
    serve([run({ status: 'succeeded' })])
    server.use(
      http.post('/api/v1/jobs/runs/', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(run(), { status: 201 })
      }),
    )
    await mount().job().start('watch_check')
    expect(body).toEqual({ kind: 'watch_check', params: {} })
  })

  it('muestra el rechazo de la API al lanzar', async () => {
    server.use(
      http.post('/api/v1/jobs/runs/', () =>
        HttpResponse.json({ detail: 'Ya hay una tarea de este tipo en curso.' }, { status: 409 }),
      ),
    )
    const { wrapper, job } = mount()
    expect(await job().start('download')).toBe(false)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Ya hay una tarea de este tipo en curso.')
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(false)
  })

  it('pide solo las líneas nuevas en cada sondeo', async () => {
    const { afters } = serve([run()], [[line(1), line(2, 'warning')], [line(3, 'error')]])
    const { wrapper, job } = mount()
    await job().start('download')
    await vi.waitFor(() => expect(wrapper.findAll('.job__line')).toHaveLength(2))
    await vi.advanceTimersByTimeAsync(POLL_MS)
    await vi.waitFor(() => expect(wrapper.findAll('.job__line')).toHaveLength(3))
    expect(afters.slice(0, 2)).toEqual(['0', '2'])
    expect(wrapper.get('[role="log"]').attributes('aria-label')).toBe('Registro de la tarea')
    expect(wrapper.get('.job__line--warning').text()).toBe('línea 2')
    expect(wrapper.get('.job__line--error').text()).toBe('línea 3')
  })

  it('deja de sondear al cerrarse la tarea, tras leer todas sus líneas', async () => {
    const closed = run({ status: 'succeeded', done: 4, current: '' })
    const { afters, detailCalls } = serve([closed], [[line(1)], [line(2)]])
    const { wrapper, job } = mount()
    await job().start('download')
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('Terminada'))
    expect(afters).toEqual(['0', '1', '2'])
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('.job__current').exists()).toBe(false)
    await vi.advanceTimersByTimeAsync(POLL_MS * 3)
    expect(detailCalls()).toBe(1)
  })

  it('detiene la tarea y sigue hasta que se cierra', async () => {
    serve([run(), run({ status: 'stopped' })])
    let stopped = false
    server.use(
      http.post('/api/v1/jobs/runs/5/stop/', () => {
        stopped = true
        return HttpResponse.json(run({ status: 'stopping' }))
      }),
    )
    const { wrapper, job } = mount()
    await job().start('download')
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('En curso'))
    expect(wrapper.get('button').text()).toBe('Detener')
    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(stopped).toBe(true))
    await vi.waitFor(() => expect(wrapper.get('button').attributes('disabled')).toBeDefined())
    await vi.advanceTimersByTimeAsync(POLL_MS)
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('Detenida'))
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('muestra el error al detener', async () => {
    serve([run()])
    server.use(
      http.post('/api/v1/jobs/runs/5/stop/', () =>
        HttpResponse.json({ detail: 'La tarea ya ha terminado.' }, { status: 409 }),
      ),
    )
    const { wrapper, job } = mount()
    await job().start('download')
    await job().stop()
    await vi.waitFor(() =>
      expect(wrapper.get('[role="alert"]').text()).toBe('La tarea ya ha terminado.'),
    )
  })

  it('detener sin tarea no hace nada', async () => {
    const { job } = mount()
    await job().stop()
    expect(job().error).toBe('')
  })

  it('un fallo al sondear se muestra, se reintenta y se borra al volver', async () => {
    serve([run({ status: 'succeeded' })])
    server.use(http.get('/api/v1/jobs/runs/5/', () => HttpResponse.error(), { once: true }))
    const { wrapper, job } = mount()
    await job().start('download')
    await vi.waitFor(() =>
      expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo conectar con el servidor.'),
    )
    await vi.advanceTimersByTimeAsync(POLL_MS)
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(false))
    expect(wrapper.get('.job__status').text()).toContain('Terminada')
  })

  it('sigue una ejecución existente por id', async () => {
    serve([run({ status: 'failed', total: 0 })], [[line(1)]])
    const { wrapper, job } = mount()
    await job().follow(5)
    await vi.waitFor(() => expect(wrapper.findAll('.job__line')).toHaveLength(1))
    expect(wrapper.get('.job__status').text()).toBe('Fallida')
  })

  it('muestra el error si la ejecución no existe', async () => {
    server.use(http.get('/api/v1/jobs/runs/9/', () => new HttpResponse(null, { status: 404 })))
    const { wrapper, job } = mount()
    await job().follow(9)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('No se ha encontrado lo que buscabas.')
  })

  it('al seguir otra ejecución descarta el sondeo en vuelo de la anterior', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    serve([run()])
    server.use(
      http.get('/api/v1/jobs/runs/5/lines/', async () => {
        await gate
        return HttpResponse.json([line(1)])
      }),
      http.get('/api/v1/jobs/runs/6/', () =>
        HttpResponse.json(run({ id: 6, status: 'succeeded' })),
      ),
      http.get('/api/v1/jobs/runs/6/lines/', () => HttpResponse.json([])),
    )
    const { job } = mount()
    await job().start('download')
    await job().follow(6)
    release()
    await vi.waitFor(() => expect(job().run?.id).toBe(6))
    await flushPromises()
    expect(job().lines).toEqual([])
  })

  it('deja de sondear al desmontar la vista', async () => {
    const { detailCalls } = serve([run()])
    const { wrapper, job } = mount()
    await job().start('download')
    await vi.waitFor(() => expect(detailCalls()).toBe(1))
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(POLL_MS * 3)
    expect(detailCalls()).toBe(1)
  })

  it('una respuesta que llega tras desmontar no programa otro sondeo', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    const { detailCalls } = serve([run()])
    server.use(
      http.get('/api/v1/jobs/runs/5/', async () => {
        await gate
        return HttpResponse.error()
      }),
    )
    const { wrapper, job } = mount()
    await job().start('download')
    wrapper.unmount()
    release()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(POLL_MS * 3)
    expect(detailCalls()).toBe(0)
  })

  it('traduce al inglés', async () => {
    serve([run()])
    const { wrapper, job } = mount('en')
    await job().start('download')
    await vi.waitFor(() => expect(wrapper.get('.job__status').text()).toContain('Running'))
    expect(wrapper.get('button').text()).toBe('Stop')
  })
})
