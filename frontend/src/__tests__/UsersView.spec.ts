import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { server } from '../mocks/server'
import { useSessionStore } from '../stores/session'
import UsersView from '../views/UsersView.vue'
import { fill, mountView } from './viewHelpers'

async function mountUsers() {
  const ctx = await mountView(UsersView, '/usuarios')
  await useSessionStore(ctx.pinia).fetchMe()
  await flushPromises()
  return ctx
}

const button = (wrapper: Awaited<ReturnType<typeof mountUsers>>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)

describe('UsersView', () => {
  it('lista los usuarios con su rol y último acceso', async () => {
    const { wrapper } = await mountUsers()
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.text()).toContain('demo')
    expect(rows[1]?.text()).toContain('Nunca')
    // Uno mismo no puede cambiarse el rol ni desactivarse.
    expect(rows[0]?.get('select').attributes('disabled')).toBeDefined()
    expect(rows[0]?.find('button').exists()).toBe(false)
  })

  it('da de alta un usuario y vacía el formulario', async () => {
    const { wrapper } = await mountUsers()
    await fill(wrapper, 'Nombre de usuario', 'ana')
    await fill(wrapper, 'Contraseña', 'Clave-segura-1')
    await wrapper.get('#users-new-role').setValue('administrador')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toBe('Usuario ana creado.')
    expect(wrapper.findAll('tbody tr').map((r) => r.find('td').text())).toEqual([
      'ana',
      'demo',
      'invitado',
    ])
    expect((wrapper.get('#users-new-role').element as HTMLSelectElement).value).toBe('usuario')
  })

  it('muestra los errores de validación del alta en su campo', async () => {
    server.use(
      http.post('/api/v1/accounts/users/', () =>
        HttpResponse.json(
          { username: ['Ese nombre de usuario ya existe.'], password: ['Muy corta.'] },
          { status: 400 },
        ),
      ),
    )
    const { wrapper } = await mountUsers()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Ese nombre de usuario ya existe.')
    expect(wrapper.text()).toContain('Muy corta.')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('muestra solo el error del campo que lo tiene', async () => {
    server.use(
      http.post('/api/v1/accounts/users/', () =>
        HttpResponse.json({ password: ['Muy corta.'] }, { status: 400 }),
      ),
    )
    const { wrapper } = await mountUsers()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.findAll('[aria-invalid="true"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('Muy corta.')
  })

  it('muestra un error general si el alta falla sin errores de campo', async () => {
    server.use(
      http.post('/api/v1/accounts/users/', () =>
        HttpResponse.json({ role: 'No válido.' }, { status: 400 }),
      ),
    )
    const { wrapper } = await mountUsers()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('No válido.')
  })

  it('muestra el error si el alta falla en el servidor', async () => {
    server.use(http.post('/api/v1/accounts/users/', () => new HttpResponse(null, { status: 500 })))
    const { wrapper } = await mountUsers()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
  })

  it('cambia el rol de un usuario', async () => {
    const { wrapper } = await mountUsers()
    await wrapper.findAll('tbody tr')[1]?.get('select').setValue('administrador')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toBe('Usuario invitado actualizado.')
    expect((wrapper.findAll('tbody tr')[1]?.get('select').element as HTMLSelectElement).value).toBe(
      'administrador',
    )
  })

  it('desactiva y reactiva a un usuario', async () => {
    const { wrapper } = await mountUsers()
    await button(wrapper, 'Desactivar')?.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('tbody tr')[1]?.text()).toContain('(desactivado)')
    await button(wrapper, 'Reactivar')?.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('tbody tr')[1]?.text()).not.toContain('(desactivado)')
  })

  it('si un cambio falla, muestra el error y vuelve a leer la lista', async () => {
    server.use(
      http.patch('/api/v1/accounts/users/:id/', () =>
        HttpResponse.json({ detail: 'No puedes hacerlo.' }, { status: 400 }),
      ),
    )
    const { wrapper } = await mountUsers()
    const select = () => wrapper.findAll('tbody tr')[1]?.get('select').element as HTMLSelectElement
    await wrapper.findAll('tbody tr')[1]?.get('select').setValue('administrador')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('No puedes hacerlo.')
    expect(select().value).toBe('usuario')
  })

  it('muestra el error si no puede cargar la lista', async () => {
    server.use(http.get('/api/v1/accounts/users/', () => new HttpResponse(null, { status: 403 })))
    const { wrapper } = await mountUsers()
    expect(wrapper.get('[role="alert"]').text()).toBe('No tienes permiso para hacer esto.')
  })
})
