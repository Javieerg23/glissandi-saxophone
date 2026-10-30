import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeAll, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type RouteLocationNormalized } from 'vue-router'

import { navEntries } from '../components/nav-meta'
import { messages } from '../locales'
import { server } from '../mocks/server'
import { routes } from '../router'
import { authGuard } from '../router/guards'
import ProxiesView from '../views/ProxiesView.vue'
import { fill, mountView } from './viewHelpers'

type Wrapper = Awaited<ReturnType<typeof mountView>>['wrapper']

// jsdom no implementa showModal/close de <dialog>.
beforeAll(() => {
  Object.assign(HTMLDialogElement.prototype, {
    showModal(this: HTMLDialogElement) {
      this.setAttribute('open', '')
    },
    close(this: HTMLDialogElement) {
      this.removeAttribute('open')
    },
  })
})

const mount = () => mountView(ProxiesView, '/proxies')

/** Pulsa el botón con ese texto; `row` elige la fila de la lista (0 = primera). */
async function click(wrapper: Wrapper, text: string, row?: number): Promise<void> {
  const scope = row === undefined ? wrapper : wrapper.findAll('tbody tr')[row]!
  await scope
    .findAll('button')
    .find((b) => b.text() === text)!
    .trigger('click')
  await flushPromises()
}

const rows = (w: Wrapper) => w.findAll('tbody tr').map((r) => r.findAll('td').map((c) => c.text()))

describe('ProxiesView', () => {
  it('lista los proxies con su estado, contadores y último uso', async () => {
    const { wrapper } = await mount()
    const [first, second] = rows(wrapper)
    expect(first?.slice(0, 4)).toEqual(['http://proxy.example:3128', 'Activo', '42', '3'])
    expect(first?.[4]).not.toBe('Nunca')
    expect(second?.slice(1, 5)).toEqual(['Inactivo', '0', '0', 'Nunca'])
  })

  it('muestra el error si no puede cargar la lista', async () => {
    server.use(http.get('/api/v1/proxies/', () => new HttpResponse(null, { status: 500 })))
    const { wrapper } = await mount()
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
  })

  it('añade un proxy y recarga la lista', async () => {
    let sent: unknown
    server.use(
      http.post('/api/v1/proxies/', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    const { wrapper } = await mount()
    await click(wrapper, 'Añadir proxy')
    expect(wrapper.find('dialog[open] h2').text()).toBe('Nuevo proxy')
    await fill(wrapper, 'Dirección (http, https, socks5 o socks5h)', 'https://nuevo.example:8080')
    await wrapper.get('form[name="proxy"]').trigger('submit')
    await flushPromises()
    expect(sent).toEqual({ url: 'https://nuevo.example:8080', enabled: true })
    expect(wrapper.find('dialog[open]').exists()).toBe(false)
    expect(wrapper.get('[role="status"]').text()).toBe('Proxy añadido.')
  })

  it('cierra los diálogos sin guardar ni borrar', async () => {
    const { wrapper } = await mount()
    await click(wrapper, 'Añadir proxy')
    await click(wrapper.findAll('dialog')[0] as unknown as Wrapper, 'Cerrar')
    await click(wrapper, 'Borrar', 0)
    await click(wrapper.findAll('dialog')[1] as unknown as Wrapper, 'Cerrar')
    expect(wrapper.find('dialog[open]').exists()).toBe(false)
    expect(rows(wrapper)).toHaveLength(2)
  })

  it('añade un proxy inactivo', async () => {
    const { wrapper } = await mount()
    await click(wrapper, 'Añadir proxy')
    await fill(wrapper, 'Dirección (http, https, socks5 o socks5h)', 'socks5h://otro.example:1080')
    await wrapper.get('form[name="proxy"] input[type="checkbox"]').setValue(false)
    await wrapper.get('form[name="proxy"]').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toBe('Proxy añadido.')
  })

  it('edita un proxy con sus datos ya cargados', async () => {
    let sent: unknown
    server.use(
      http.patch('/api/v1/proxies/2/', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({})
      }),
    )
    const { wrapper } = await mount()
    await click(wrapper, 'Editar', 1)
    expect(wrapper.find('dialog[open] h2').text()).toBe('Editar proxy')
    const input = wrapper.get('form[name="proxy"] input[type="url"]')
    expect((input.element as HTMLInputElement).value).toBe('socks5://socks.example:1080')
    await wrapper.get('form[name="proxy"] input[type="checkbox"]').setValue(true)
    await wrapper.get('form[name="proxy"]').trigger('submit')
    await flushPromises()
    expect(sent).toEqual({ url: 'socks5://socks.example:1080', enabled: true })
    expect(wrapper.get('[role="status"]').text()).toBe('Proxy guardado.')
  })

  it('muestra el error de validación junto a la dirección y deja el formulario abierto', async () => {
    server.use(
      http.post('/api/v1/proxies/', () =>
        HttpResponse.json({ url: ['Usa un proxy con esquema válido.'] }, { status: 400 }),
      ),
    )
    const { wrapper } = await mount()
    await click(wrapper, 'Añadir proxy')
    await wrapper.get('form[name="proxy"]').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.field__error').text()).toBe('Usa un proxy con esquema válido.')
    expect(wrapper.get('input[type="url"]').attributes('aria-invalid')).toBe('true')
    expect(wrapper.find('dialog[open]').exists()).toBe(true)
  })

  it('muestra en el formulario un error que no es de la dirección', async () => {
    server.use(http.post('/api/v1/proxies/', () => new HttpResponse(null, { status: 403 })))
    const { wrapper } = await mount()
    await click(wrapper, 'Añadir proxy')
    await wrapper.get('form[name="proxy"]').trigger('submit')
    await flushPromises()
    expect(wrapper.get('form [role="alert"]').text()).toBe('No tienes permiso para hacer esto.')
    expect(wrapper.find('.field__error').exists()).toBe(false)
  })

  it('activa y desactiva un proxy', async () => {
    const { wrapper } = await mount()
    await click(wrapper, 'Desactivar', 0)
    expect(rows(wrapper)[0]?.[1]).toBe('Inactivo')
    await click(wrapper, 'Activar', 1)
    expect(rows(wrapper)[1]?.[1]).toBe('Activo')
    expect(wrapper.get('[role="status"]').text()).toBe('Proxy guardado.')
  })

  it('borra un proxy tras confirmarlo', async () => {
    const { wrapper } = await mount()
    await click(wrapper, 'Borrar', 0)
    const dialog = wrapper.get('dialog[open]')
    expect(dialog.text()).toContain('¿Borrar http://proxy.example:3128?')
    await click(wrapper.findAll('dialog')[1] as unknown as Wrapper, 'Borrar')
    expect(rows(wrapper).map((r) => r[0])).toEqual(['socks5://socks.example:1080'])
    expect(wrapper.find('dialog[open]').exists()).toBe(false)
    expect(wrapper.get('[role="status"]').text()).toBe('Proxy borrado.')
  })

  it('muestra el error si no puede borrar', async () => {
    server.use(http.delete('/api/v1/proxies/:id/', () => new HttpResponse(null, { status: 404 })))
    const { wrapper } = await mount()
    await click(wrapper, 'Borrar', 0)
    await click(wrapper.findAll('dialog')[1] as unknown as Wrapper, 'Borrar')
    expect(rows(wrapper)).toHaveLength(2)
    expect(wrapper.get('[role="alert"]').text()).toBe('No se ha encontrado lo que buscabas.')
  })

  it('informa de una prueba de conexión correcta', async () => {
    const { wrapper } = await mount()
    await click(wrapper, 'Probar', 0)
    expect(wrapper.get('[role="status"]').text()).toBe(
      'http://proxy.example:3128 funciona (HTTP 200).',
    )
  })

  it('avisa como error de una prueba fallida, con o sin respuesta', async () => {
    server.use(
      http.post('/api/v1/proxies/:id/check/', () =>
        HttpResponse.json({ ok: false, status_code: 407 }),
      ),
    )
    const { wrapper } = await mount()
    await click(wrapper, 'Probar', 0)
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'http://proxy.example:3128 responde con un error (HTTP 407).',
    )
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    server.use(
      http.post('/api/v1/proxies/:id/check/', () =>
        HttpResponse.json({ ok: false, status_code: null }),
      ),
    )
    await click(wrapper, 'Probar', 1)
    expect(wrapper.get('[role="alert"]').text()).toBe('socks5://socks.example:1080 no responde.')
  })

  it('tiene los mismos textos en español y en inglés', () => {
    const keys = (tree: object, prefix = ''): string[] =>
      Object.entries(tree).flatMap(([k, v]) =>
        typeof v === 'string' ? [`${prefix}${k}`] : keys(v as object, `${prefix}${k}.`),
      )
    expect(keys(messages.en.proxies as object)).toEqual(keys(messages.es.proxies as object))
  })
})

describe('ruta de proxies', () => {
  it('es solo para administradores: oculta en la navegación y redirigida por la guarda', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({ history: createMemoryHistory(), routes })
    const proxies = router.resolve({ name: 'proxies' })
    expect(proxies.meta).toMatchObject({ adminOnly: true, navGroup: 'more' })
    expect(navEntries(router.getRoutes(), false).more.map((e) => e.name)).not.toContain('proxies')
    expect(navEntries(router.getRoutes(), true).more.map((e) => e.name)).toContain('proxies')
    server.use(
      http.get('/api/v1/accounts/me/', () => HttpResponse.json({ username: 'u', role: 'usuario' })),
    )
    expect(await authGuard(proxies as RouteLocationNormalized)).toEqual({ name: 'dashboard' })
  })
})
