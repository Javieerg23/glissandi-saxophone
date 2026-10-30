import { http, HttpResponse } from 'msw'

import type { components } from '../../api/schema'

type JobRun = components['schemas']['JobRun']

const ID = 30

const finished: JobRun = {
  id: ID,
  kind: 'folder_import',
  params: { folder: 'Daft Punk' },
  user: 'demo',
  status: 'succeeded',
  started_at: '2026-01-01T10:00:00Z',
  finished_at: '2026-01-01T10:01:00Z',
  done: 4,
  total: 4,
  current: '',
  summary: {
    albums: 1,
    tracks: 12,
    linked: 2,
    already_linked: 0,
    completed: true,
    unlinked: [
      { file: 'Daft Punk/demo.mp3', reason: 'no_tags' },
      { file: 'Daft Punk/live.flac', reason: 'not_found' },
    ],
  },
}

const lines = [
  { position: 1, level: 'info', message: 'Daft Punk/one.mp3 → «One More Time»' },
  { position: 2, level: 'warning', message: 'Daft Punk/demo.mp3: no_tags' },
].map((l) => ({ ...l, created_at: '2026-01-01T10:00:10Z' }))

/**
 * Importar una carpeta: la tarea `folder_import` termina al momento con un resumen de
 * ejemplo. Las demás tareas siguen en `jobs.ts` (este fichero se carga antes y les cede
 * la petición al no responder).
 */
export default [
  http.post('/api/v1/jobs/runs/', async ({ request }) => {
    const { kind } = (await request.clone().json()) as Pick<JobRun, 'kind'>
    if (kind === 'folder_import') return HttpResponse.json(finished, { status: 201 })
  }),
  http.get(`/api/v1/jobs/runs/${ID}/`, () => HttpResponse.json(finished)),
  // Respeta `after`: con la tarea cerrada, el panel pide líneas hasta recibir una lista vacía.
  http.get(`/api/v1/jobs/runs/${ID}/lines/`, ({ request }) => {
    const after = Number(new URL(request.url).searchParams.get('after'))
    return HttpResponse.json(lines.filter((l) => l.position > after))
  }),
]
