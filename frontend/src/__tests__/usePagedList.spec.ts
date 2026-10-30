import { flushPromises } from '@vue/test-utils'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { usePagedList } from '../composables/usePagedList'
import { server } from '../mocks/server'
import { render } from './helpers'

interface Item {
  id: number
}

/** Monta un componente mínimo que usa la lista (dentro de RouterView o suelto) y devuelve lo que expone. */
async function setup(path = '/lista', mount: 'router-view' | 'direct' = 'router-view') {
  const requests: URL[] = []
  server.use(
    http.get('/api/v1/things/', ({ request }) => {
      const url = new URL(request.url)
      requests.push(url)
      const page = Number(url.searchParams.get('page') ?? 1)
      return HttpResponse.json({
        count: 3,
        next: page < 2 ? 'http://x/?page=2' : null,
        previous: page > 1 ? 'http://x/?page=1' : null,
        results: [{ id: page }],
      })
    }),
  )
  let list!: ReturnType<typeof usePagedList<Item>>
  const View = defineComponent({
    setup() {
      list = usePagedList<Item>('/api/v1/things/', ['kind'])
      return () => null
    },
  })
  const Other = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/lista', name: 'list', component: View },
      { path: '/otra', name: 'other', component: Other },
    ],
  })
  await router.push(path)
  const wrapper = render(mount === 'direct' ? View : { template: '<RouterView />' }, {
    global: { plugins: [router] },
  })
  await vi.waitFor(() => expect(list.loading).toBe(false))
  return { list, router, requests, wrapper }
}

describe('usePagedList', () => {
  it('carga la primera página con su total', async () => {
    const { list } = await setup()
    expect(list.items).toEqual([{ id: 1 }])
    expect(list.count).toBe(3)
    expect(list.page).toBe(1)
    expect([list.hasPrevious, list.hasNext]).toEqual([false, true])
    expect(list.error).toBe('')
  })

  it('pasa a la API solo la página, la búsqueda, el orden y los filtros declarados', async () => {
    const { requests } = await setup('/lista?page=2&search=a&ordering=-id&kind=x&tab=log')
    expect(Object.fromEntries(requests[0]!.searchParams)).toEqual({
      page: '2',
      search: 'a',
      ordering: '-id',
      kind: 'x',
    })
  })

  it('cambia de página guardándola en la URL', async () => {
    const { list, router } = await setup()
    list.goTo(2)
    await vi.waitFor(() => expect(list.items).toEqual([{ id: 2 }]))
    expect(router.currentRoute.value.query).toEqual({ page: '2' })
    expect([list.hasPrevious, list.hasNext]).toEqual([true, false])
  })

  it('al filtrar vuelve a la primera página y quita los filtros vacíos', async () => {
    const { list, router } = await setup('/lista?page=2&kind=x')
    list.update({ search: 'daft', kind: '' })
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ search: 'daft' }))
    expect(list.query).toEqual({ search: 'daft' })
  })

  it('muestra el error de la API', async () => {
    const { list } = await setup()
    server.use(http.get('/api/v1/things/', () => new HttpResponse(null, { status: 500 })))
    await list.reload()
    expect(list.error).toBe('El servidor ha fallado. Inténtalo más tarde.')
    expect(list.loading).toBe(false)
  })

  it.each([
    ['correcta', () => HttpResponse.json({ count: 1, results: [{ id: 1 }] })],
    ['fallida', () => HttpResponse.error()],
  ])('descarta una respuesta %s que llega después de otra más nueva', async (_, late) => {
    const { list } = await setup()
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    server.use(
      http.get('/api/v1/things/', async ({ request }) => {
        const slow = new URL(request.url).searchParams.get('search') === 'lenta'
        if (!slow) return HttpResponse.json({ count: 1, results: [{ id: 2 }] })
        await gate
        return late()
      }),
    )
    list.update({ search: 'lenta' })
    await flushPromises()
    list.update({ search: 'rapida' })
    await vi.waitFor(() => expect(list.items).toEqual([{ id: 2 }]))
    release()
    await new Promise((r) => setTimeout(r, 20))
    expect(list.items).toEqual([{ id: 2 }])
    expect(list.error).toBe('')
    expect(list.loading).toBe(false)
  })

  // Con transiciones o KeepAlive la vista sigue montada un momento tras cambiar de ruta.
  it('no vuelve a cargar al salir hacia otra ruta', async () => {
    const { router, requests } = await setup('/lista', 'direct')
    await router.push({ name: 'other', query: { kind: 'y' } })
    await flushPromises()
    expect(requests).toHaveLength(1)
  })
})
