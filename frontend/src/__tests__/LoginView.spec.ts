import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { server } from '../mocks/server'
import { useSessionStore } from '../stores/session'
import LoginView from '../views/LoginView.vue'
import { fill, mountView } from './viewHelpers'

async function signIn(wrapper: Awaited<ReturnType<typeof mountView>>['wrapper']) {
  await fill(wrapper, 'Usuario', 'demo')
  await fill(wrapper, 'Contraseña', 'secreta')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('LoginView', () => {
  it('abre la sesión y va al panel', async () => {
    const { wrapper, router, pinia } = await mountView(LoginView, '/login')
    await signIn(wrapper)
    expect(useSessionStore(pinia).user?.username).toBe('demo')
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('vuelve a la ruta pedida si es interna', async () => {
    const { wrapper, router } = await mountView(LoginView, '/login?redirect=/cuenta')
    await signIn(wrapper)
    expect(router.currentRoute.value.path).toBe('/cuenta')
  })

  it('ignora una redirección externa', async () => {
    const { wrapper, router } = await mountView(LoginView, '/login?redirect=//evil.example')
    await signIn(wrapper)
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('muestra el error del servidor y no cambia de ruta', async () => {
    server.use(
      http.post('/api/v1/accounts/login/', () =>
        HttpResponse.json({ detail: 'Usuario o contraseña incorrectos.' }, { status: 400 }),
      ),
    )
    const { wrapper, router } = await mountView(LoginView, '/login')
    await signIn(wrapper)
    expect(wrapper.get('[role="alert"]').text()).toBe('Usuario o contraseña incorrectos.')
    expect(router.currentRoute.value.name).toBe('login')
    expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
  })

  it('lleva a la configuración inicial si aún no hay administrador', async () => {
    server.use(http.get('/api/v1/accounts/setup/', () => HttpResponse.json({ needed: true })))
    const { router } = await mountView(LoginView, '/login')
    expect(router.currentRoute.value.name).toBe('setup')
  })

  it('avisa si no puede consultar la configuración', async () => {
    server.use(http.get('/api/v1/accounts/setup/', () => HttpResponse.error()))
    const { wrapper } = await mountView(LoginView, '/login')
    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo conectar con el servidor.')
  })

  it('traduce los textos al inglés', async () => {
    const { wrapper } = await mountView(LoginView, '/login')
    expect(wrapper.get('h1').text()).toBe('Iniciar sesión')
  })
})
