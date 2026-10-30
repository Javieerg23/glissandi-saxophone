import { readFileSync } from 'node:fs'

import { beforeEach, describe, expect, it, vi } from 'vitest'

type Listener = (event: unknown) => void

/** Carga public/sw.js con un `self`, `caches` y `fetch` simulados y devuelve sus manejadores. */
function loadWorker() {
  const listeners: Record<string, Listener> = {}
  const cache = { add: vi.fn(), put: vi.fn() }
  const caches = {
    open: vi.fn(async () => cache),
    keys: vi.fn(async () => ['glissandi-shell-v1', 'viejo']),
    delete: vi.fn(async () => true),
    match: vi.fn<(r: unknown) => Promise<string | undefined>>(async () => 'cached'),
  }
  const self = {
    location: { origin: 'https://app.test' },
    addEventListener: (type: string, fn: Listener) => (listeners[type] = fn),
    skipWaiting: vi.fn(),
  }
  const fetchMock = vi.fn()
  new Function('self', 'caches', 'fetch', 'URL', readFileSync('public/sw.js', 'utf8'))(
    self,
    caches,
    fetchMock,
    URL,
  )
  return { listeners, caches, cache, fetchMock, self }
}

function fetchEvent(url: string, method = 'GET') {
  return { request: { url, method }, respondWith: vi.fn() }
}

describe('service worker', () => {
  let w: ReturnType<typeof loadWorker>
  beforeEach(() => (w = loadWorker()))

  it.each([
    ['la API', 'https://app.test/api/v1/jobs/runs/', 'GET'],
    ['un POST', 'https://app.test/x', 'POST'],
    ['otro origen', 'https://otro.test/x', 'GET'],
  ])('no intercepta %s', (_n, url, method) => {
    const e = fetchEvent(url, method)
    w.listeners.fetch(e)
    expect(e.respondWith).not.toHaveBeenCalled()
  })

  it('guarda en caché lo estático y lo sirve de la red', async () => {
    const res = { clone: () => 'copia' }
    w.fetchMock.mockResolvedValue(res)
    const e = fetchEvent('https://app.test/assets/a.js')
    w.listeners.fetch(e)
    expect(await e.respondWith.mock.calls[0][0]).toBe(res)
    await Promise.resolve()
    expect(w.cache.put).toHaveBeenCalled()
  })

  it('sin red sirve la caché y, si no hay, el cascarón', async () => {
    w.fetchMock.mockRejectedValue(new Error('offline'))
    const e = fetchEvent('https://app.test/a')
    w.listeners.fetch(e)
    expect(await e.respondWith.mock.calls[0][0]).toBe('cached')
    w.caches.match.mockImplementation(async (r: unknown) => (r === '/' ? 'shell' : undefined))
    const e2 = fetchEvent('https://app.test/b')
    w.listeners.fetch(e2)
    expect(await e2.respondWith.mock.calls[0][0]).toBe('shell')
  })

  it('precachea el cascarón al instalar y limpia cachés viejas al activar', async () => {
    const wait: Promise<unknown>[] = []
    w.listeners.install({ waitUntil: (p: Promise<unknown>) => wait.push(p) })
    w.listeners.activate({ waitUntil: (p: Promise<unknown>) => wait.push(p) })
    await Promise.all(wait)
    expect(w.cache.add).toHaveBeenCalledWith('/')
    expect(w.self.skipWaiting).toHaveBeenCalled()
    expect(w.caches.delete).toHaveBeenCalledOnce()
    expect(w.caches.delete).toHaveBeenCalledWith('viejo')
  })
})
