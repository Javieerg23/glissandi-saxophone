import { http, HttpResponse } from 'msw'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import type { RouteLocationNormalized } from 'vue-router'

import { server } from '../mocks/server'
import { authGuard, safeRedirect } from '../router/guards'

const private_ = { fullPath: '/panel?x=1', meta: {} } as RouteLocationNormalized
const public_ = { fullPath: '/login', meta: { public: true } } as unknown as RouteLocationNormalized
const anonymous = () =>
  server.use(http.get('/api/v1/accounts/me/', () => new HttpResponse(null, { status: 401 })))

describe('authGuard', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('deja pasar a una ruta privada con sesión', async () => {
    expect(await authGuard(private_)).toBe(true)
  })

  it('lleva al login recordando el destino si no hay sesión', async () => {
    anonymous()
    expect(await authGuard(private_)).toEqual({
      name: 'login',
      query: { redirect: '/panel?x=1' },
    })
  })

  it('saca de las rutas públicas a quien ya tiene sesión', async () => {
    expect(await authGuard(public_)).toEqual({ name: 'dashboard' })
  })

  it('deja ver las rutas públicas sin sesión', async () => {
    anonymous()
    expect(await authGuard(public_)).toBe(true)
  })

  it('trata como anónimo si el servidor falla', async () => {
    server.use(http.get('/api/v1/accounts/me/', () => new HttpResponse(null, { status: 500 })))
    expect(await authGuard(public_)).toBe(true)
  })

  it('pregunta al servidor solo una vez', async () => {
    let calls = 0
    server.use(
      http.get('/api/v1/accounts/me/', () => {
        calls += 1
        return HttpResponse.json({ username: 'demo', role: 'usuario' })
      }),
    )
    await authGuard(private_)
    await authGuard(private_)
    expect(calls).toBe(1)
  })
})

describe('safeRedirect', () => {
  it('admite rutas internas', () => {
    expect(safeRedirect('/panel?a=1')).toBe('/panel?a=1')
  })

  it.each(['//evil.example', '/\\evil.example', 'https://evil.example', '', undefined, ['/a']])(
    'rechaza %j',
    (value) => {
      expect(safeRedirect(value)).toBeNull()
    },
  )
})
