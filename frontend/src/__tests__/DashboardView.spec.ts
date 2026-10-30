import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { server } from '../mocks/server'
import DashboardView from '../views/DashboardView.vue'
import { mountView } from './viewHelpers'

const page = (results: unknown[]) => HttpResponse.json({ count: results.length, results })

afterEach(() => vi.useRealTimers())

describe('DashboardView', () => {
  it('muestra el resumen de la biblioteca', async () => {
    const { wrapper } = await mountView(DashboardView, '/panel')
    const stats = wrapper.findAll('dl div').map((d) => d.text())
    expect(stats).toEqual(['Artistas12', 'Álbumes48', 'Canciones530', 'Descargadas211'])
  })

  it('lista solo las tareas en curso, con su progreso', async () => {
    const { wrapper } = await mountView(DashboardView, '/panel')
    const items = wrapper.findAll('.jobs li')
    expect(items).toHaveLength(1)
    expect(items[0]?.text()).toContain('Importación')
    expect(items[0]?.text()).toContain('Daft Punk')
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('40')
  })

  it('usa el tipo tal cual si no tiene traducción', async () => {
    server.use(
      http.get('/api/v1/jobs/runs/', () =>
        page([{ id: 9, kind: 'raro', status: 'running', done: 0, total: 0, current: '' }]),
      ),
    )
    const { wrapper } = await mountView(DashboardView, '/panel')
    expect(wrapper.get('.jobs li').text()).toContain('raro')
  })

  it('indica que no hay tareas en curso', async () => {
    server.use(http.get('/api/v1/jobs/runs/', () => page([])))
    const { wrapper } = await mountView(DashboardView, '/panel')
    expect(wrapper.text()).toContain('No hay tareas en curso.')
  })

  it('muestra el error si falla el resumen y sigue con las tareas', async () => {
    server.use(http.get('/api/v1/catalog/summary/', () => new HttpResponse(null, { status: 500 })))
    const { wrapper } = await mountView(DashboardView, '/panel')
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
    expect(wrapper.find('dl').exists()).toBe(false)
    expect(wrapper.findAll('.jobs li')).toHaveLength(1)
  })

  it('refresca las tareas cada pocos segundos y deja de hacerlo al desmontar', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    let calls = 0
    server.use(
      http.get('/api/v1/jobs/runs/', () => {
        calls += 1
        return page([])
      }),
    )
    const { wrapper } = await mountView(DashboardView, '/panel')
    expect(calls).toBe(1)
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(calls).toBe(2)
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(calls).toBe(2)
  })

  it('un fallo al refrescar se muestra y se borra cuando vuelve a funcionar', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    server.use(http.get('/api/v1/jobs/runs/', () => HttpResponse.error()))
    const { wrapper } = await mountView(DashboardView, '/panel')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    server.use(http.get('/api/v1/jobs/runs/', () => page([])))
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })
})
