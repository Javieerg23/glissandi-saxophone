import { http, HttpResponse } from 'msw'

import type { components } from '../../api/schema'

type Track = components['schemas']['Track']

const track = (id: number, downloaded: boolean): Track => ({
  id,
  album: 1,
  title: 'One More Time',
  track_number: 1,
  disc_number: 1,
  duration: 320,
  isrc: null,
  artists: [],
  downloaded,
  deezer_id: 3135556,
  musicbrainz_id: null,
})

/** Subida manual de audio. */
export default [
  http.get('/api/v1/catalog/tracks/:id/', ({ params }) =>
    HttpResponse.json(track(Number(params.id), false)),
  ),
  http.post('/api/v1/catalog/tracks/:id/upload/', ({ params }) =>
    HttpResponse.json(track(Number(params.id), true), { status: 201 }),
  ),
]
