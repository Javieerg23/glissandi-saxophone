import { http, HttpResponse } from 'msw'

import type { components } from '../../api/schema'

type Preference = components['schemas']['Preference']
type ManagedUser = components['schemas']['ManagedUser']

const preferences: Preference[] = [
  { key: 'download.format', value: 'mp3', default: 'mp3' },
  { key: 'download.folder', value: 'music', default: 'music' },
  {
    key: 'download.name_template',
    value: '{artist}/{album}/{disc}{track} {title}',
    default: '{artist}/{album}/{disc}{track} {title}',
  },
]

const users: ManagedUser[] = [
  {
    id: 1,
    username: 'demo',
    role: 'administrador',
    is_active: true,
    last_login: '2026-10-30T10:00:00Z',
    date_joined: '2026-01-01T10:00:00Z',
  },
  {
    id: 2,
    username: 'invitado',
    role: 'usuario',
    is_active: true,
    last_login: null,
    date_joined: '2026-02-01T10:00:00Z',
  },
]

/** Ajustes globales y gestión de usuarios. Sin estado: cada test parte de los mismos datos. */
export default [
  http.get('/api/v1/preferences/', () => HttpResponse.json(preferences)),
  http.put('/api/v1/preferences/:key/', async ({ params, request }) => {
    const { value } = (await request.json()) as { value: unknown }
    const pref = preferences.find((p) => p.key === params.key)
    return HttpResponse.json({ ...pref, value })
  }),
  http.get('/api/v1/accounts/users/', () => HttpResponse.json(users)),
  http.post('/api/v1/accounts/users/', async ({ request }) => {
    const { username, role } = (await request.json()) as { username: string; role: string }
    return HttpResponse.json(
      { ...users[1], id: 3, username, role, date_joined: '2026-10-30T10:00:00Z' },
      { status: 201 },
    )
  }),
  http.patch('/api/v1/accounts/users/:id/', async ({ params, request }) => {
    const user = users.find((u) => u.id === Number(params.id))
    return HttpResponse.json({ ...user, ...((await request.json()) as object) })
  }),
]
