import type { components } from '../../api/schema'

export type Artist = components['schemas']['Artist']
export type Album = components['schemas']['Album']
export type Track = components['schemas']['Track']
export type Credit = components['schemas']['Credit']
export type HistoryEntry = components['schemas']['HistoryEntry']
export type Item = Artist | Album | Track

/** Pestañas de la Biblioteca; coinciden con el tramo de la API (`catalog/<kind>/`). */
export const KINDS = ['artists', 'albums', 'tracks'] as const
export type Kind = (typeof KINDS)[number]

/** Cómo se edita un campo: los números y las fechas viajan con su tipo, no como texto. */
export type FieldType = 'text' | 'url' | 'number' | 'date'

interface KindSpec {
  /** Filtros de la API que la lista deja en la URL, además de búsqueda y orden. */
  filters: readonly string[]
  /** Valores de `ordering` que ofrece la lista (los de `ordering_fields` del backend). */
  orderings: readonly string[]
  /** Campos editables, los mismos que revierte el historial. */
  editable: Readonly<Record<string, FieldType>>
  /** Tipo de bloqueo; los artistas no se bloquean desde aquí. */
  blockKind?: 'album' | 'track'
}

export const SPECS: Record<Kind, KindSpec> = {
  artists: {
    filters: [],
    orderings: ['name', '-name'],
    editable: { name: 'text', image_url: 'url' },
  },
  albums: {
    filters: ['artist', 'released_after', 'released_before'],
    orderings: ['title', '-title', 'release_date', '-release_date'],
    editable: { title: 'text', release_date: 'date', cover_url: 'url' },
    blockKind: 'album',
  },
  tracks: {
    filters: ['artist', 'album', 'downloaded'],
    orderings: ['title', '-title', 'track_number'],
    editable: { title: 'text', track_number: 'number', disc_number: 'number' },
    blockKind: 'track',
  },
}

export function apiPath(kind: Kind, id?: number | string): string {
  return id === undefined ? `/api/v1/catalog/${kind}/` : `/api/v1/catalog/${kind}/${id}/`
}

/** Nombre visible: los artistas tienen `name` y el resto `title`. */
export function label(item: Item): string {
  return 'name' in item ? item.name : item.title
}

/** Duración `m:ss` a partir de segundos. */
export function duration(seconds: number | null): string {
  if (seconds === null) return ''
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
