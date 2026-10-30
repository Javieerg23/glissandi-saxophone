import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { server } from '../mocks/server'
import { useSessionStore } from '../stores/session'
import AccountView from '../views/AccountView.vue'
import { fill, mountView } from './viewHelpers'

afterEach(() => localStorage.clear())

async function mountSignedIn(path = '/cuenta') {
  const ctx = await mountView(AccountView, path)
  await useSessionStore(ctx.pinia).fetchMe()
  await flushPromises()
  return ctx
}

describe('AccountView', () => {
  it('indica quién ha iniciado sesión y con qué rol', async () => {
    const { wrapper } = await mountSignedIn()
    expect(wrapper.text()).toContain('Has iniciado sesión como demo (administrador).')
  })

  it('cambia el idioma y lo recuerda', async () => {
    const { wrapper } = await mountSignedIn()
    await wrapper.get('select').setValue('en')
    expect(wrapper.get('h1').text()).toBe('My account')
    expect(localStorage.getItem('locale')).toBe('en')
  })

  it('cambia el nombre de usuario y actualiza la sesión', async () => {
    const { wrapper, pinia } = await mountSignedIn()
    await fill(wrapper, 'Nuevo nombre de usuario', 'nuevo')
    await fill(wrapper.findAll('form')[0] ? wrapper : wrapper, 'Contraseña actual', 'secreta')
    await wrapper.get('form[name="username"]').trigger('submit')
    await flushPromises()
    expect(useSessionStore(pinia).user?.username).toBe('nuevo')
    expect(wrapper.get('[role="status"]').text()).toBe('Nombre de usuario cambiado.')
  })

  it('cambia la contraseña y vacía los campos', async () => {
    const { wrapper } = await mountSignedIn()
    const form = wrapper.get('form[name="password"]')
    const inputs = form.findAll('input')
    await inputs[0]?.setValue('vieja')
    await inputs[1]?.setValue('Nueva-clave-1')
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toBe('Contraseña cambiada.')
    expect(inputs.map((i) => (i.element as HTMLInputElement).value)).toEqual(['', ''])
  })

  it('muestra el error del servidor y quita el éxito anterior', async () => {
    const { wrapper } = await mountSignedIn()
    const form = wrapper.get('form[name="password"]')
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    server.use(
      http.post('/api/v1/accounts/password/', () =>
        HttpResponse.json({ current_password: ['No es correcta.'] }, { status: 400 }),
      ),
    )
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('No es correcta.')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('cierra la sesión y va al login', async () => {
    const { wrapper, router, pinia } = await mountSignedIn()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Cerrar sesión')
      ?.trigger('click')
    await flushPromises()
    expect(useSessionStore(pinia).isAuthenticated).toBe(false)
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('muestra el error si no puede cerrar la sesión', async () => {
    server.use(http.post('/api/v1/accounts/logout/', () => new HttpResponse(null, { status: 500 })))
    const { wrapper, router } = await mountSignedIn()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Cerrar sesión')
      ?.trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(router.currentRoute.value.name).toBe('account')
  })

  it('no pinta el rol si aún no hay usuario', async () => {
    const { wrapper } = await mountView(AccountView, '/cuenta')
    expect(wrapper.text()).not.toContain('Has iniciado sesión')
  })
})
