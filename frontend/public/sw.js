// Service worker mínimo: guarda el «cascarón» estático para abrir la app sin red.
// Nunca toca /api/: las respuestas llevan datos de sesión y deben ser siempre frescas.
const CACHE = 'glissandi-shell-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add('/')))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith('/api/')
  )
    return

  // Red primero para que un despliegue nuevo se vea al instante; la caché es la reserva.
  event.respondWith(
    fetch(request)
      .then((res) => {
        const copy = res.clone()
        void caches.open(CACHE).then((cache) => cache.put(request, copy))
        return res
      })
      .catch(() => caches.match(request).then((hit) => hit ?? caches.match('/'))),
  )
})
