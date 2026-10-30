import { http, HttpResponse } from 'msw'

import type { Job } from '../stores/jobs'
import type { User } from '../stores/session'

const user: User = { username: 'demo', role: 'administrador' }
const jobs: Job[] = [
  { id: 1, kind: 'import', status: 'running', progress: 40 },
  { id: 2, kind: 'download', status: 'succeeded', progress: 100 },
]

/** Respuestas simuladas de la API para desarrollo sin backend y para los tests. */
export const handlers = [
  http.get('/api/v1/accounts/me/', () => HttpResponse.json(user)),
  http.post('/api/v1/accounts/login/', () => HttpResponse.json(user)),
  http.post('/api/v1/accounts/logout/', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/v1/jobs/', () => HttpResponse.json(jobs)),
]
