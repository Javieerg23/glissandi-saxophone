import { http, HttpResponse } from 'msw'

import type { components } from '../../api/schema'

type DeezerArtist = components['schemas']['DeezerArtist']

const artists: DeezerArtist[] = [
  {
    deezer_id: 27,
    name: 'Daft Punk',
    image_url: 'https://e-cdns-images.dzcdn.net/images/artist/daft-punk/250x250.jpg',
    album_count: 34,
    fan_count: 4200000,
    in_catalog: true,
    blocked: false,
  },
  {
    deezer_id: 1424,
    name: 'Justice',
    image_url: null,
    album_count: 21,
    fan_count: 900000,
    in_catalog: false,
    blocked: false,
  },
  {
    deezer_id: 4050,
    name: 'Daft Punk Tribute',
    image_url: null,
    album_count: 2,
    fan_count: 120,
    in_catalog: false,
    blocked: true,
  },
]

/** Búsqueda de artistas en Deezer para importar. */
export default [
  http.get('/api/v1/catalog/deezer/artists/', ({ request }) => {
    const q = (new URL(request.url).searchParams.get('q') as string).toLowerCase()
    const results = artists.filter((a) => a.name.toLowerCase().includes(q))
    return HttpResponse.json({ results, total: results.length, next_index: null })
  }),
]
