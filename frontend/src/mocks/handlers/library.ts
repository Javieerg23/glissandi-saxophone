import { http, HttpResponse } from 'msw'

import type { Album, Artist, Item, Track } from '../../views/library/kinds'

const artists: Artist[] = [
  { id: 1, name: 'Daft Punk', image_url: '', deezer_id: 27, musicbrainz_id: null },
  { id: 2, name: 'Pharrell Williams', image_url: '', deezer_id: 103, musicbrainz_id: null },
]
const credit = (a: Artist, position: number) => ({ id: a.id, name: a.name, position })
const albums: Album[] = [
  {
    id: 10,
    title: 'Random Access Memories',
    release_date: '2013-05-17',
    cover_url: 'https://example.com/ram.jpg',
    artists: [credit(artists[0]!, 0)],
    deezer_id: 6575789,
    musicbrainz_id: null,
  },
]
const tracks: Track[] = [
  {
    id: 100,
    album: 10,
    title: 'Get Lucky',
    track_number: 8,
    disc_number: 1,
    duration: 369,
    isrc: 'USQX91300108',
    artists: [credit(artists[0]!, 0), credit(artists[1]!, 1)],
    downloaded: true,
    deezer_id: 67238735,
    musicbrainz_id: null,
  },
  {
    id: 101,
    album: 10,
    title: 'Giorgio by Moroder',
    track_number: 3,
    disc_number: 1,
    duration: 544,
    isrc: null,
    artists: [credit(artists[0]!, 0)],
    downloaded: false,
    deezer_id: 67238730,
    musicbrainz_id: null,
  },
]
const data: Record<string, Item[]> = { artists, albums, tracks }

function find(kind: string, params: Record<string, unknown>): Item | undefined {
  return data[kind]!.find((i) => i.id === Number(params.id))
}

const history = [
  {
    history_id: 2,
    history_date: '2026-10-02T10:00:00Z',
    history_type: '~',
    history_user: 'demo',
    changes: { title: 'Get Lucky (Radio Edit)' },
  },
  {
    history_id: 1,
    history_date: '2026-10-01T10:00:00Z',
    history_type: '+',
    history_user: null,
    changes: { title: 'Get Lucky' },
  },
]

const notFound = () => HttpResponse.json({ detail: 'No encontrado.' }, { status: 404 })

/** Respuestas de una de las tres listas y de sus fichas. */
function itemHandlers(kind: string) {
  const base = `/api/v1/catalog/${kind}`
  return [
    http.get(`${base}/`, () => {
      const results = data[kind]!
      return HttpResponse.json({ count: results.length, next: null, previous: null, results })
    }),
    http.get(`${base}/:id/`, ({ params }) => {
      const item = find(kind, params)
      return item ? HttpResponse.json(item) : notFound()
    }),
    http.patch(`${base}/:id/`, async ({ params, request }) =>
      HttpResponse.json({ ...find(kind, params), ...((await request.json()) as object) }),
    ),
    http.put(`${base}/:id/artists/`, async ({ params, request }) => {
      const { artists: ids } = (await request.json()) as { artists: number[] }
      const chosen = ids.map((id, i) =>
        credit(
          artists.find((a) => a.id === id)!,
          i,
        ),
      )
      return HttpResponse.json({ ...find(kind, params), artists: chosen })
    }),
    http.get(`${base}/:id/history/`, () => HttpResponse.json(history)),
    http.post(`${base}/:id/revert/`, ({ params }) => HttpResponse.json(find(kind, params))),
  ]
}

/** Biblioteca: listas, fichas, edición, artistas, historial y bloqueo. Sin estado entre peticiones. */
export default [
  ...Object.keys(data).flatMap(itemHandlers),
  http.post('/api/v1/catalog/blocked/', async ({ request }) =>
    HttpResponse.json(
      { id: 1, created_at: '2026-10-30T10:00:00Z', ...((await request.json()) as object) },
      { status: 201 },
    ),
  ),
]
