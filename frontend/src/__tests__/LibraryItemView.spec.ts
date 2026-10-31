import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import libraryHandlers from '../mocks/handlers/library'
import { server } from '../mocks/server'
import { useSessionStore } from '../stores/session'
import LibraryItemView from '../views/library/LibraryItemView.vue'
import { trackRequests } from './settle'
import { fill, mountView } from './viewHelpers'

// jsdom no implementa showModal/close de <dialog>.
Object.assign(HTMLDialogElement.prototype, {
  showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '')
  },
  close(this: HTMLDialogElement) {
    this.removeAttribute('open')
  },
})

type Wrapper = Awaited<ReturnType<typeof mountView>>['wrapper']

async function open(path: string, role: 'administrador' | 'usuario' = 'administrador') {
  server.use(http.get('/api/v1/accounts/me/', () => HttpResponse.json({ username: 'u', role })))
  const ctx = await mountView(LibraryItemView, path)
  await useSessionStore(ctx.pinia).fetchMe()
  await settle()
  return ctx
}

const button = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text || b.attributes('aria-label') === text)!
const link = (wrapper: Wrapper, text: string) => wrapper.findAll('a').find((a) => a.text() === text)

/** Cuerpo JSON de la próxima petición con ese método y ruta. */
function capture(method: string, path: string): Promise<unknown> {
  return new Promise((resolve) => {
    server.events.on('request:start', ({ request }) => {
      if (request.method === method && new URL(request.url).pathname === path)
        void request.clone().json().then(resolve)
    })
  })
}

// Otras zonas (Descargar) también simulan las listas del catálogo: aquí mandan las de la Biblioteca.
let settle: () => Promise<void>
beforeEach(() => {
  server.use(...libraryHandlers)
  settle = trackRequests()
})
afterEach(() => server.events.removeAllListeners())

describe('LibraryItemView', () => {
  it('muestra los datos de una canción con enlaces a sus artistas y su álbum', async () => {
    const { wrapper } = await open('/biblioteca/tracks/100')
    expect(wrapper.get('h1').text()).toBe('Get Lucky')
    const text = wrapper.get('.item__data').text()
    expect(text).toContain('1-8')
    expect(text).toContain('6:09')
    expect(text).toContain('USQX91300108')
    expect(wrapper.get('.item__downloaded').text()).toBe('Sí')
    expect(link(wrapper, 'Pharrell Williams')?.attributes('href')).toBe('/biblioteca/artists/2')
    expect(link(wrapper, 'Ver el álbum')?.attributes('href')).toBe('/biblioteca/albums/10')
  })

  it('no enlaza a la subida de audio sin esa ruta', async () => {
    // Se abre un álbum: quitar la ruta con un enlace de subida ya pintado lo rompería.
    const { wrapper, router } = await open('/biblioteca/albums/10')
    router.removeRoute('track-upload')
    await router.push('/biblioteca/tracks/101')
    await vi.waitFor(() => expect(wrapper.find('h1').text()).toBe('Giorgio by Moroder'))
    expect(link(wrapper, 'Subir audio')).toBeUndefined()
  })

  it('enlaza a la subida de audio cuando existe esa ruta', async () => {
    const { wrapper, router } = await open('/biblioteca/tracks/101')
    router.addRoute({ path: '/subir/:id', name: 'track-upload', component: { render: () => null } })
    await router.push('/biblioteca/tracks/100')
    await settle()
    await vi.waitFor(() =>
      expect(link(wrapper, 'Subir audio')?.attributes('href')).toBe('/subir/100'),
    )
    expect(wrapper.get('.item__downloaded').text()).toBe('Sí')
  })

  it('va de una canción a su álbum recargando la ficha', async () => {
    const { wrapper, router } = await open('/biblioteca/tracks/101')
    expect(wrapper.text()).not.toContain('ISRC')
    await link(wrapper, 'Ver el álbum')!.trigger('click')
    await settle()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/biblioteca/albums/10'))
    await vi.waitFor(() => expect(wrapper.find('h1').text()).toBe('Random Access Memories'))
    expect(wrapper.get('img').attributes('src')).toBe('https://example.com/ram.jpg')
    expect(link(wrapper, 'Ver sus canciones')?.attributes('href')).toBe(
      '/biblioteca?tab=tracks&album=10',
    )
  })

  it('no recarga al salir de la ficha', async () => {
    const { router } = await open('/biblioteca/artists/1')
    const fetched = vi.fn()
    server.events.on('request:start', fetched)
    await router.push('/biblioteca')
    await settle()
    expect(fetched).not.toHaveBeenCalled()
  })

  it('enlaza a los álbumes y canciones de un artista, sin artistas ni bloqueo', async () => {
    const { wrapper } = await open('/biblioteca/artists/1')
    expect(link(wrapper, 'Ver sus álbumes')?.attributes('href')).toBe(
      '/biblioteca?tab=albums&artist=1',
    )
    expect(link(wrapper, 'Ver sus canciones')?.attributes('href')).toBe(
      '/biblioteca?tab=tracks&artist=1',
    )
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.artists-editor').exists()).toBe(false)
    expect(button(wrapper, 'Bloquear')).toBeUndefined()
    expect(link(wrapper, 'Volver a la biblioteca')?.attributes('href')).toBe(
      '/biblioteca?tab=artists',
    )
  })

  it('muestra el error si el elemento no existe', async () => {
    const { wrapper } = await open('/biblioteca/tracks/999')
    expect(wrapper.get('[role="alert"]').text()).toBe('No encontrado.')
    expect(wrapper.find('h1').exists()).toBe(false)
  })

  it('oculta edición, artistas, bloqueo y reversión a quien no puede escribir', async () => {
    const { wrapper } = await open('/biblioteca/tracks/100', 'usuario')
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('.artists-editor').exists()).toBe(false)
    expect(button(wrapper, 'Bloquear')).toBeUndefined()
    expect(wrapper.text()).toContain('Historial')
    expect(button(wrapper, 'Volver a esta versión')).toBeUndefined()
  })

  describe('edición', () => {
    it('guarda los campos con su tipo y muestra el resultado', async () => {
      const { wrapper } = await open('/biblioteca/tracks/100')
      const body = capture('PATCH', '/api/v1/catalog/tracks/100/')
      await fill(wrapper, 'Título', 'Get Lucky (Edit)')
      await fill(wrapper, 'Número de pista', '9')
      await wrapper.get('form').trigger('submit')
      await settle()
      expect(await body).toEqual({ title: 'Get Lucky (Edit)', track_number: 9, disc_number: 1 })
      expect(wrapper.get('h1').text()).toBe('Get Lucky (Edit)')
      expect(wrapper.get('[role="status"]').text()).toBe('Cambios guardados.')
    })

    it('manda una fecha vacía como nula', async () => {
      const { wrapper } = await open('/biblioteca/albums/10')
      const body = capture('PATCH', '/api/v1/catalog/albums/10/')
      await fill(wrapper, 'Fecha de publicación', '')
      await wrapper.get('form').trigger('submit')
      expect(await body).toMatchObject({
        release_date: null,
        cover_url: 'https://example.com/ram.jpg',
      })
    })

    it('muestra cada error de validación en su campo', async () => {
      server.use(
        http.patch('/api/v1/catalog/artists/1/', () =>
          HttpResponse.json({ name: ['Obligatorio.'], other: ['x'] }, { status: 400 }),
        ),
      )
      const { wrapper } = await open('/biblioteca/artists/1')
      await wrapper.get('form').trigger('submit')
      await settle()
      expect(wrapper.get('.field__error').text()).toBe('Obligatorio.')
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    })

    it('muestra un error general cuando no es de un campo', async () => {
      server.use(
        http.patch('/api/v1/catalog/artists/1/', () => new HttpResponse(null, { status: 500 })),
      )
      const { wrapper } = await open('/biblioteca/artists/1')
      await wrapper.get('form').trigger('submit')
      await settle()
      expect(wrapper.get('[role="alert"]').text()).toBe(
        'El servidor ha fallado. Inténtalo más tarde.',
      )
      expect(wrapper.find('.field__error').exists()).toBe(false)
    })
  })

  describe('artistas', () => {
    it('quita, reordena, añade del catálogo y guarda en orden', async () => {
      const { wrapper } = await open('/biblioteca/tracks/100')
      const body = capture('PUT', '/api/v1/catalog/tracks/100/artists/')
      expect(button(wrapper, 'Subir a Daft Punk').attributes('disabled')).toBeDefined()
      expect(button(wrapper, 'Bajar a Pharrell Williams').attributes('disabled')).toBeDefined()
      await button(wrapper, 'Bajar a Daft Punk').trigger('click')
      await button(wrapper, 'Subir a Daft Punk').trigger('click')
      await button(wrapper, 'Quitar a Daft Punk').trigger('click')
      await fill(wrapper, 'Buscar un artista del catálogo', 'daft')
      await wrapper.get('.artists-editor form').trigger('submit')
      await settle()
      const add = wrapper.findAll('.artists-editor__found button')
      expect(add[1]?.attributes('disabled')).toBeDefined()
      await add[0]!.trigger('click')
      await button(wrapper, 'Guardar artistas').trigger('click')
      await settle()
      expect(await body).toEqual({ artists: [2, 1] })
      expect(wrapper.get('[role="status"]').text()).toBe('Artistas actualizados.')
      expect(link(wrapper, 'Pharrell Williams')).toBeDefined()
    })

    it('no deja guardar sin artistas', async () => {
      const { wrapper } = await open('/biblioteca/albums/10')
      await button(wrapper, 'Quitar a Daft Punk').trigger('click')
      expect(button(wrapper, 'Guardar artistas').attributes('disabled')).toBeDefined()
    })

    it('muestra los errores de búsqueda y de guardado', async () => {
      server.use(
        http.get('/api/v1/catalog/artists/', () => new HttpResponse(null, { status: 500 })),
        http.put('/api/v1/catalog/albums/10/artists/', () =>
          HttpResponse.json({ artists: ['No existe.'] }, { status: 400 }),
        ),
      )
      const { wrapper } = await open('/biblioteca/albums/10')
      await wrapper.get('.artists-editor form').trigger('submit')
      await settle()
      expect(wrapper.get('.artists-editor [role="alert"]').text()).toContain(
        'El servidor ha fallado',
      )
      await button(wrapper, 'Guardar artistas').trigger('click')
      await settle()
      expect(wrapper.get('.artists-editor [role="alert"]').text()).toBe('No existe.')
    })
  })

  describe('historial', () => {
    it('lista las versiones y vuelve a una', async () => {
      const { wrapper } = await open('/biblioteca/tracks/100')
      const entries = wrapper.findAll('.history__entry')
      expect(entries).toHaveLength(2)
      expect(entries[0]!.text()).toContain('Modificado')
      expect(entries[0]!.text()).toContain('demo')
      expect(entries[1]!.text()).toContain('Creado')
      expect(entries[1]!.text()).toContain('Sistema')
      const body = capture('POST', '/api/v1/catalog/tracks/100/revert/')
      await entries[1]!.get('button').trigger('click')
      await settle()
      expect(await body).toEqual({ history_id: 1 })
      expect(wrapper.get('[role="status"]').text()).toBe('Se ha vuelto a la versión elegida.')
    })

    it('baja al historial cuando el enlace lo pide', async () => {
      const scroll = vi.fn()
      Element.prototype.scrollIntoView = scroll
      const { wrapper } = await open('/biblioteca/tracks/100#historial')
      expect(scroll).toHaveBeenCalledOnce()
      expect(scroll.mock.contexts[0]).toBe(wrapper.get('#historial').element)
    })

    it('muestra tal cual un tipo desconocido y los valores vacíos con un guion', async () => {
      server.use(
        http.get('/api/v1/catalog/albums/10/history/', () =>
          HttpResponse.json([
            {
              history_id: 5,
              history_date: '2026-10-01T10:00:00Z',
              history_type: '-',
              history_user: 'demo',
              changes: { release_date: null, cover_url: '' },
            },
            {
              history_id: 4,
              history_date: '2026-10-01T09:00:00Z',
              history_type: '?',
              history_user: 'demo',
              changes: {},
            },
          ]),
        ),
      )
      const { wrapper } = await open('/biblioteca/albums/10')
      const entries = wrapper.findAll('.history__entry')
      expect(entries[0]!.text()).toContain('Borrado')
      expect(entries[0]!.findAll('dd').map((d) => d.text())).toEqual(['—', '—'])
      expect(entries[1]!.text()).toContain('?')
    })

    it('muestra los errores de carga y de reversión', async () => {
      server.use(
        http.get(
          '/api/v1/catalog/artists/1/history/',
          () => new HttpResponse(null, { status: 500 }),
        ),
      )
      const { wrapper } = await open('/biblioteca/artists/1')
      expect(wrapper.get('.history [role="alert"]').text()).toContain('El servidor ha fallado')

      server.use(
        http.post('/api/v1/catalog/tracks/100/revert/', () =>
          HttpResponse.json({ detail: 'Esa versión no existe.' }, { status: 404 }),
        ),
      )
      const track = await open('/biblioteca/tracks/100')
      await track.wrapper.get('.history__entry button').trigger('click')
      await settle()
      expect(track.wrapper.get('.history [role="alert"]').text()).toBe('Esa versión no existe.')
    })
  })

  describe('bloqueo', () => {
    it('pide confirmación y bloquea la canción', async () => {
      const { wrapper } = await open('/biblioteca/tracks/100')
      await button(wrapper, 'Bloquear').trigger('click')
      await settle()
      expect(wrapper.get('dialog').text()).toContain('¿Bloquear la canción «Get Lucky»?')
      const body = capture('POST', '/api/v1/catalog/blocked/')
      await wrapper.get('dialog .btn--danger').trigger('click')
      await settle()
      expect(await body).toEqual({ kind: 'track', deezer_id: 67238735, name: 'Get Lucky' })
      expect(wrapper.get('[role="status"]').text()).toBe(
        'Bloqueado: no se volverá a importar ni a descargar.',
      )
      expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
    })

    it('se puede cancelar sin bloquear', async () => {
      const { wrapper } = await open('/biblioteca/tracks/100')
      const posted = vi.fn()
      server.events.on('request:start', ({ request }) => {
        if (request.method === 'POST') posted()
      })
      await button(wrapper, 'Bloquear').trigger('click')
      await settle()
      await button(wrapper, 'Cerrar').trigger('click')
      await settle()
      expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
      expect(posted).not.toHaveBeenCalled()
    })

    it('muestra el error si ya estaba bloqueado', async () => {
      server.use(
        http.post('/api/v1/catalog/blocked/', () =>
          HttpResponse.json({ non_field_errors: ['Ya está bloqueado.'] }, { status: 400 }),
        ),
      )
      const { wrapper } = await open('/biblioteca/albums/10')
      await button(wrapper, 'Bloquear').trigger('click')
      await wrapper.get('dialog .btn--danger').trigger('click')
      await settle()
      expect(wrapper.get('[role="alert"]').text()).toBe('Ya está bloqueado.')
    })

    it('no ofrece bloquear lo que no viene de Deezer', async () => {
      server.use(
        http.get('/api/v1/catalog/tracks/101/', () =>
          HttpResponse.json({
            id: 101,
            album: 10,
            title: 'Local',
            track_number: 1,
            disc_number: 1,
            duration: null,
            isrc: null,
            artists: [],
            downloaded: false,
            deezer_id: null,
            musicbrainz_id: '8f0e0a5c-1d3c-4b5a-9a51-1a2b3c4d5e6f',
          }),
        ),
      )
      const { wrapper } = await open('/biblioteca/tracks/101')
      expect(button(wrapper, 'Bloquear')).toBeUndefined()
      expect(wrapper.text()).toContain('8f0e0a5c-1d3c-4b5a-9a51-1a2b3c4d5e6f')
      expect(wrapper.text()).not.toContain('Duración')
      expect(wrapper.text()).not.toContain('ID de Deezer')
    })
  })
})
