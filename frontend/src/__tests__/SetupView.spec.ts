import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { server } from '../mocks/server'
import { useSessionStore } from '../stores/session'
import SetupView from '../views/SetupView.vue'
import { fill, mountView } from './viewHelpers'

const needed = () =>
  server.use(http.get('/api/v1/accounts/setup/', () => HttpResponse.json({ needed: true })))

async function submit(
  wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'],
  confirm = 'Clave-larga-1',
) {
  await fill(wrapper, 'Usuario', 'admin')
  await fill(wrapper, 'Contraseña', 'Clave-larga-1')
  await fill(wrapper, 'Repite la contraseña', confirm)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('SetupView', () => {
  it('crea el administrador, abre la sesión y va al panel', async () => {
    needed()
    const { wrapper, router, pinia } = await mountView(SetupView, '/setup')
    await submit(wrapper)
    expect(useSessionStore(pinia).isAuthenticated).toBe(true)
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('no envía nada si las contraseñas no coinciden', async () => {
    needed()
    let posted = false
    server.use(
      http.post('/api/v1/accounts/setup/', () => {
        posted = true
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    const { wrapper } = await mountView(SetupView, '/setup')
    await submit(wrapper, 'otra')
    expect(wrapper.get('[role="alert"]').text()).toBe('Las contraseñas no coinciden.')
    expect(posted).toBe(false)
  })

  it('muestra los errores de validación del servidor', async () => {
    needed()
    server.use(
      http.post('/api/v1/accounts/setup/', () =>
        HttpResponse.json({ password: ['Demasiado corta.'] }, { status: 400 }),
      ),
    )
    const { wrapper, router } = await mountView(SetupView, '/setup')
    await submit(wrapper)
    expect(wrapper.get('[role="alert"]').text()).toBe('Demasiado corta.')
    expect(router.currentRoute.value.name).toBe('setup')
  })

  it('vuelve al login si ya hay administrador', async () => {
    const { router } = await mountView(SetupView, '/setup')
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('avisa si no puede consultar la configuración', async () => {
    server.use(http.get('/api/v1/accounts/setup/', () => HttpResponse.error()))
    const { wrapper } = await mountView(SetupView, '/setup')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  })
})
