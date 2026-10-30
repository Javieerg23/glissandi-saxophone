import { http, HttpResponse } from 'msw'

import type { Job } from '../stores/jobs'
import type { User } from '../stores/session'

const user: User = { username: 'demo', role: 'administrador' }
const jobs: Job[] = [
  { id: 2, kind: 'download', status: 'succeeded', done: 10, total: 10, current: '' },
  { id: 1, kind: 'import', status: 'running', done: 4, total: 10, current: 'Daft Punk' },
]

/** Respuestas simuladas de la API para desarrollo sin backend y para los tests. */
export const handlers = [
  http.get('/api/v1/accounts/me/', () => HttpResponse.json(user)),
  http.post('/api/v1/accounts/login/', () => HttpResponse.json(user)),
  http.post('/api/v1/accounts/logout/', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/v1/accounts/setup/', () => HttpResponse.json({ needed: false })),
  http.post('/api/v1/accounts/setup/', () => HttpResponse.json(user, { status: 201 })),
  http.post('/api/v1/accounts/password/', () => new HttpResponse(null, { status: 204 })),
  http.post('/api/v1/accounts/username/', async ({ request }) => {
    const { username } = (await request.json()) as { username: string }
    return HttpResponse.json({ ...user, username })
  }),
  // Aún sin backend: el catálogo (E6.1) no expone este resumen.
  http.get('/api/v1/catalog/summary/', () =>
    HttpResponse.json({ artists: 12, albums: 48, tracks: 530, downloaded: 211 }),
  ),
  http.get('/api/v1/jobs/runs/', () =>
    HttpResponse.json({ count: jobs.length, next: null, previous: null, results: jobs }),
  ),
]
