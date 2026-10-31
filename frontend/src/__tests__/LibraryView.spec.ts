import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { messages } from '../locales'
import libraryHandlers from '../mocks/handlers/library'
import { server } from '../mocks/server'
import { routes } from '../router'
import LibraryView from '../views/library/LibraryView.vue'
import { duration } from '../views/library/kinds'
import { trackRequests } from './settle'
import { fill, mountView } from './viewHelpers'

type Tree = { [key: string]: string | Tree }

function paths(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === 'string' ? [`${prefix}${k}`] : paths(v, `${prefix}${k}.`),
  )
}

/** Guarda la query de cada petición a la lista indicada. */
function spy(kind: string): Record<string, string>[] {
  const seen: Record<string, string>[] = []
  server.events.on('request:start', ({ request }) => {
    const url = new URL(request.url)
    if (url.pathname === `/api/v1/catalog/${kind}/`) seen.push(Object.fromEntries(url.searchParams))
  })
  return seen
}

const button = (wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)!

describe('LibraryView', () => {
  // Otras zonas (Descargar) también simulan las listas del catálogo: aquí mandan las de la Biblioteca.
  let settle: () => Promise<void>
  beforeEach(() => {
    server.use(...libraryHandlers)
    settle = trackRequests()
  })

  async function mount(path: string) {
    const ctx = await mountView(LibraryView, path)
    await settle()
    return ctx
  }

  afterEach(() => server.events.removeAllListeners())

  it('va en la navegación principal', () => {
    const route = routes.find((r) => r.name === 'library')!
    expect(route.meta).toMatchObject({ navLabel: 'library.nav', navGroup: 'main' })
  })

  it('tiene los mismos textos en español y en inglés', () => {
    const es = paths(messages.es.library as Tree)
    expect(paths(messages.en.library as Tree)).toEqual(es)
  })

  it('abre la pestaña de artistas por defecto, con enlace a cada ficha', async () => {
    const { wrapper } = await mount('/biblioteca?tab=otra')
    expect(wrapper.get('[aria-current="page"]').text()).toBe('Artistas')
    const link = wrapper.findAll('a').find((a) => a.text() === 'Daft Punk')!
    expect(link.attributes('href')).toBe('/biblioteca/artists/1')
    expect(wrapper.text()).toContain('Página 1 · 2 en total')
  })

  it('cambia de pestaña y muestra artistas, duración y si está descargada', async () => {
    const { wrapper, router } = await mount('/biblioteca')
    await wrapper
      .findAll('a')
      .find((a) => a.text() === 'Canciones')!
      .trigger('click')
    await settle()
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ tab: 'tracks' }))
    await vi.waitFor(() => expect(wrapper.findAll('tbody tr')).toHaveLength(2))
    const rows = wrapper.findAll('tbody tr').map((r) => r.findAll('td').map((c) => c.text()))
    expect(rows[0]).toEqual(['Get Lucky', 'Daft Punk, Pharrell Williams', '6:09', 'Sí'])
    expect(rows[1]?.[3]).toBe('No')
  })

  it('aplica búsqueda, orden y fechas de los álbumes', async () => {
    const seen = spy('albums')
    const { wrapper, router } = await mount('/biblioteca?tab=albums')
    await fill(wrapper, 'Buscar', 'random')
    await fill(wrapper, 'Publicado desde', '2010-01-01')
    await fill(wrapper, 'Publicado hasta', '2020-12-31')
    await wrapper.get('select').setValue('-release_date')
    expect(wrapper.text()).toContain('Fecha (más recientes primero)')
    await wrapper.get('form').trigger('submit')
    await settle()
    await vi.waitFor(() =>
      expect(router.currentRoute.value.query).toEqual({
        tab: 'albums',
        search: 'random',
        ordering: '-release_date',
        released_after: '2010-01-01',
        released_before: '2020-12-31',
      }),
    )
    await vi.waitFor(() =>
      expect(seen.at(-1)).toEqual({
        search: 'random',
        ordering: '-release_date',
        released_after: '2010-01-01',
        released_before: '2020-12-31',
      }),
    )
  })

  it('filtra las canciones por descarga y recupera los filtros de la URL', async () => {
    const seen = spy('tracks')
    const { wrapper, router } = await mount('/biblioteca?tab=tracks&search=get')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('get')
    await wrapper.findAll('select')[1]!.setValue('false')
    await wrapper.get('form').trigger('submit')
    await settle()
    await vi.waitFor(() =>
      expect(router.currentRoute.value.query).toMatchObject({ downloaded: 'false', search: 'get' }),
    )
    await vi.waitFor(() => expect(seen.at(-1)).toEqual({ search: 'get', downloaded: 'false' }))
  })

  it('muestra el filtro por álbum y lo quita', async () => {
    const { wrapper, router } = await mount('/biblioteca?tab=tracks&album=10')
    expect(wrapper.text()).toContain('Solo las del álbum elegido.')
    await button(wrapper, 'Quitar filtro').trigger('click')
    await settle()
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ tab: 'tracks' }))
    expect(wrapper.text()).not.toContain('Solo las del álbum elegido.')
  })

  it('pasa de página adelante y atrás', async () => {
    server.use(
      http.get('/api/v1/catalog/artists/', ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get('page') ?? 1)
        return HttpResponse.json({
          count: 60,
          next: page === 1 ? 'x?page=2' : null,
          previous: page === 2 ? 'x?page=1' : null,
          results: [{ id: page, name: `Artista ${page}`, image_url: '', deezer_id: null }],
        })
      }),
    )
    const { wrapper, router } = await mount('/biblioteca')
    expect(button(wrapper, 'Anterior').attributes('disabled')).toBeDefined()
    await button(wrapper, 'Siguiente').trigger('click')
    await settle()
    await vi.waitFor(() => expect(router.currentRoute.value.query.page).toBe('2'))
    await vi.waitFor(() => expect(wrapper.text()).toContain('Artista 2'))
    expect(button(wrapper, 'Siguiente').attributes('disabled')).toBeDefined()
    await button(wrapper, 'Anterior').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Artista 1'))
    await vi.waitFor(() => expect(router.currentRoute.value.query.page).toBe('1'))
  })

  it('avisa mientras carga y muestra el error de la API', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    server.use(
      http.get('/api/v1/catalog/artists/', async () => {
        await gate
        return new HttpResponse(null, { status: 500 })
      }),
    )
    const { wrapper } = await mountView(LibraryView, '/biblioteca')
    expect(wrapper.get('[role="status"]').text()).toBe('Cargando…')
    release()
    await settle()
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it.each([
    ['/biblioteca?tab=tracks&id=100&panel=history', '/biblioteca/tracks/100#historial'],
    ['/biblioteca?tab=albums&id=10', '/biblioteca/albums/10'],
    ['/biblioteca?tab=otra&id=10', '/biblioteca?tab=otra&id=10'],
    ['/biblioteca?tab=albums&id=x', '/biblioteca?tab=albums&id=x'],
  ])('lleva el enlace %s a la ficha cuando nombra un elemento', async (from, to) => {
    const { router } = await mount('/panel')
    await router.push(from)
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe(to))
  })

  // Así enlaza el Registro: con el id numérico tal cual viene de la API.
  it('acepta el id como número al navegar por nombre', async () => {
    const { router } = await mount('/panel')
    await router.push({ name: 'library', query: { tab: 'albums', id: 10, panel: 'history' } })
    await vi.waitFor(() =>
      expect(router.currentRoute.value.fullPath).toBe('/biblioteca/albums/10#historial'),
    )
  })

  it('formatea la duración y deja vacía la desconocida', () => {
    expect([duration(65), duration(null)]).toEqual(['1:05', ''])
  })
})
