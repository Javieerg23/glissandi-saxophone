import { http, HttpResponse } from 'msw'

/** Catálogo. */
export default [
  http.get('/api/v1/catalog/summary/', () =>
    HttpResponse.json({ artists: 12, albums: 48, tracks: 530, downloaded: 211 }),
  ),
]
