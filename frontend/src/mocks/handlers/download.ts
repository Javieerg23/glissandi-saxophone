import { http, HttpResponse } from 'msw'

import type { components } from '../../api/schema'

type Track = components['schemas']['Track']

const track = (id: number, title: string, album: number): Track => ({
  id,
  album,
  title,
  track_number: id,
  disc_number: 1,
  duration: 240,
  isrc: null,
  artists: [{ id: 1, name: 'Daft Punk', position: 0 }],
  downloaded: false,
  deezer_id: 3135550 + id,
  musicbrainz_id: null,
})

const pending = [track(1, 'One More Time', 1), track(2, 'Aerodynamic', 1), track(3, 'Da Funk', 2)]
const albums = [
  { id: 1, title: 'Discovery' },
  { id: 2, title: 'Homework' },
]

const page = <T>(results: T[]) =>
  HttpResponse.json({ count: results.length, next: null, previous: null, results })

/** Canciones pendientes y los artistas y álbumes de sus filtros. */
export default [
  // Solo responde a las pendientes; cualquier otra lista de canciones sigue al siguiente handler.
  http.get('/api/v1/catalog/tracks/', ({ request }) => {
    const query = new URL(request.url).searchParams
    if (query.get('downloaded') !== 'false') return
    const album = query.get('album')
    return page(album ? pending.filter((t) => t.album === Number(album)) : pending)
  }),
  http.get('/api/v1/catalog/artists/', () => page([{ id: 1, name: 'Daft Punk' }])),
  http.get('/api/v1/catalog/albums/', () => page(albums)),
]
