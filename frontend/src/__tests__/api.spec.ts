import { http, HttpResponse } from 'msw'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError, api } from '../api/client'
import { server } from '../mocks/server'
import { progressOf, useJobsStore } from '../stores/jobs'
import { useSessionStore } from '../stores/session'

describe('api()', () => {
  it('devuelve el JSON de una respuesta correcta', async () => {
    server.use(http.get('/api/t/', () => HttpResponse.json({ ok: true })))
    expect(await api('/api/t/')).toEqual({ ok: true })
  })

  it('envía el token CSRF solo en métodos de escritura', async () => {
    document.cookie = 'csrftoken=abc123'
    const seen: Record<string, string | null> = {}
    server.use(
      http.get('/api/t/', ({ request }) => {
        seen.get = request.headers.get('X-CSRFToken')
        return HttpResponse.json({})
      }),
      http.post('/api/t/', async ({ request }) => {
        seen.post = request.headers.get('X-CSRFToken')
        return HttpResponse.json(await request.json())
      }),
    )
    await api('/api/t/')
    expect(await api('/api/t/', { method: 'post', body: { a: 1 } })).toEqual({ a: 1 })
    expect(seen).toEqual({ get: null, post: 'abc123' })
  })

  it('envía un FormData como multipart, sin JSON', async () => {
    let type: string | null = null
    let name = ''
    server.use(
      http.post('/api/t/', async ({ request }) => {
        type = request.headers.get('Content-Type')
        name = await ((await request.formData()).get('file') as File).text()
        return HttpResponse.json({})
      }),
    )
    const body = new FormData()
    body.append('file', new File(['[]'], 'copia.json'))
    await api('/api/t/', { method: 'POST', body })
    expect(type).toMatch(/^multipart\/form-data; boundary=/)
    expect(name).toBe('[]')
  })

  it('envía cadena vacía si no hay cookie CSRF', async () => {
    document.cookie = 'csrftoken=; max-age=0'
    let token: string | null = null
    server.use(
      http.post('/api/t/', ({ request }) => {
        token = request.headers.get('X-CSRFToken')
        return new HttpResponse(null, { status: 204 })
      }),
    )
    expect(await api('/api/t/', { method: 'POST' })).toBeNull()
    expect(token).toBe('')
  })

  it('lee su cookie CSRF entre otras, no una que solo acabe igual', async () => {
    document.cookie = 'xcsrftoken=falso'
    document.cookie = 'csrftoken=bueno'
    let token: string | null = null
    server.use(
      http.post('/api/t/', ({ request }) => {
        token = request.headers.get('X-CSRFToken')
        return new HttpResponse(null, { status: 204 })
      }),
    )
    await api('/api/t/', { method: 'POST' })
    expect(token).toBe('bueno')
    document.cookie = 'xcsrftoken=; max-age=0'
  })

  it('declara JSON solo cuando envía un cuerpo JSON', async () => {
    const seen: (string | null)[][] = []
    server.use(
      http.all('/api/t/', ({ request }) => {
        seen.push([request.headers.get('Accept'), request.headers.get('Content-Type')])
        return new HttpResponse(null, { status: 204 })
      }),
    )
    await api('/api/t/', { method: 'POST', body: { a: 1 } })
    await api('/api/t/', { method: 'POST' })
    expect(seen).toEqual([
      ['application/json', 'application/json'],
      ['application/json', null],
    ])
  })

  it.each([
    [401, 'unauthorized'],
    [403, 'forbidden'],
    [404, 'notFound'],
    [500, 'server'],
    [400, 'unknown'],
  ])('traduce el estado %s en el error %s', async (status, kind) => {
    server.use(http.get('/api/t/', () => HttpResponse.json({ detail: 'x' }, { status })))
    const err = await api('/api/t/').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ kind, status, body: { detail: 'x' }, messageKey: `errors.${kind}` })
  })

  it('traduce un fallo de red en el error network', async () => {
    server.use(http.get('/api/t/', () => HttpResponse.error()))
    await expect(api('/api/t/')).rejects.toMatchObject({ kind: 'network', status: 0 })
  })
})

describe('stores', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('session: fetchMe, login y logout', async () => {
    const s = useSessionStore()
    expect(s.loaded).toBe(false)
    await s.fetchMe()
    expect(s.isAuthenticated).toBe(true)
    expect(s.user?.username).toBe('demo')
    await s.logout()
    expect(s.isAuthenticated).toBe(false)
    await s.login('demo', 'x')
    expect(s.user?.username).toBe('demo')
  })

  it('session: el login envía usuario y contraseña', async () => {
    let sent: unknown = null
    server.use(
      http.post('/api/v1/accounts/login/', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ username: 'ana', role: 'usuario' })
      }),
    )
    await useSessionStore().login('ana', 'secreta')
    expect(sent).toEqual({ username: 'ana', password: 'secreta' })
  })

  it('session: 403 también significa sin sesión', async () => {
    server.use(http.get('/api/v1/accounts/me/', () => new HttpResponse(null, { status: 403 })))
    const s = useSessionStore()
    await s.fetchMe()
    expect(s.user).toBeNull()
  })

  it('session: 401 significa sin sesión, no error', async () => {
    server.use(http.get('/api/v1/accounts/me/', () => new HttpResponse(null, { status: 401 })))
    const s = useSessionStore()
    await s.fetchMe()
    expect(s.user).toBeNull()
    expect(s.loaded).toBe(true)
  })

  it('session: un fallo de servidor sí se propaga', async () => {
    server.use(http.get('/api/v1/accounts/me/', () => new HttpResponse(null, { status: 500 })))
    await expect(useSessionStore().fetchMe()).rejects.toMatchObject({ kind: 'server' })
  })

  it('session: un error que no es de la API se propaga', async () => {
    server.use(http.get('/api/v1/accounts/me/', () => HttpResponse.error()))
    // Un fallo de red también es ApiError pero no es «sin sesión».
    await expect(useSessionStore().fetchMe()).rejects.toMatchObject({ kind: 'network' })
  })

  it('jobs: refresh y tareas activas', async () => {
    const j = useJobsStore()
    await j.refresh()
    expect(j.jobs).toHaveLength(2)
    expect(j.active.map((x) => x.id)).toEqual([1])
  })

  it('jobs: porcentaje de progreso, 0 mientras no hay total', () => {
    const base = { id: 1, kind: 'import', status: 'running', current: '' } as const
    expect(progressOf({ ...base, done: 1, total: 3 })).toBe(33)
    expect(progressOf({ ...base, done: 0, total: 0 })).toBe(0)
  })
})
