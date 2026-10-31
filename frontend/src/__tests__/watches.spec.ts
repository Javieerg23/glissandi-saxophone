import { flushPromises } from '@vue/test-utils'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'

import type { components } from '../api/schema'
import { POLL_MS } from '../composables/useJobRun'
import { messages } from '../locales'
import { server } from '../mocks/server'
import watchHandlers, { watches } from '../mocks/handlers/watches'
import WatchFormView from '../views/watches/WatchFormView.vue'
import WatchesView from '../views/watches/WatchesView.vue'
import WatchView from '../views/watches/WatchView.vue'
import { fill, mountView } from './viewHelpers'

type JobRun = components['schemas']['JobRun']

// jsdom no implementa showModal/close de <dialog>.
Object.assign(HTMLDialogElement.prototype, {
  showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '')
  },
  close(this: HTMLDialogElement) {
    this.removeAttribute('open')
  },
})

// Otras vistas simulan también `catalog/artists/` con sus propios datos: aquí mandan los de Novedades.
beforeEach(() => server.use(...watchHandlers))

// Peticiones a MSW sin responder: una sola vuelta de `flushPromises` no basta en una máquina
// lenta (navegación, petición y respuesta encadenadas), así que se espera a que no quede ninguna.
let inflight = 0
server.events.on('request:start', () => void inflight++)
server.events.on('response:mocked', () => void inflight--)

/**
 * Espera a que terminen las peticiones en curso y se pinte el resultado. Una petición puede
 * arrancar unos ciclos después del clic (navegación, vigilante), así que se exigen dos vueltas
 * seguidas sin ninguna en vuelo.
 */
async function settle(): Promise<void> {
  for (let idle = 0; idle < 2;) {
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 10))
    idle = inflight > 0 ? 0 : idle + 1
  }
}

async function mount(...args: Parameters<typeof mountView>) {
  const ctx = await mountView(...args)
  await settle()
  return ctx
}

type Wrapper = Awaited<ReturnType<typeof mountView>>['wrapper']

function button(wrapper: Wrapper, text: string) {
  const found = wrapper
    .findAll('button')
    .find((b) => b.text() === text || b.attributes('aria-label') === text)
  if (!found) throw new Error(`Sin botón «${text}»`)
  return found
}

/** Apunta el cuerpo de cada petición `method` a la API; responde el mock por defecto. */
function capture(method: string) {
  const bodies: unknown[] = []
  const listener = ({ request }: { request: Request }) => {
    if (request.method === method)
      void request
        .clone()
        .json()
        .catch(() => null)
        .then((b) => bodies.push(b))
  }
  server.events.on('request:start', listener)
  onTestFinished(() => server.events.removeListener('request:start', listener))
  return bodies
}

/** Responde a la petición de guardado con `reply`. */
function captureSave(method: 'post' | 'patch', reply: () => Response) {
  const bodies: unknown[] = []
  const path = method === 'post' ? '/api/v1/watches/' : '/api/v1/watches/:id/'
  server.use(
    http[method](path, async ({ request }) => {
      bodies.push(await request.json())
      return reply()
    }),
  )
  return bodies
}

describe('WatchesView', () => {
  it('lista las búsquedas con artistas, intervalo y estado', async () => {
    const { wrapper } = await mount(WatchesView, '/novedades')
    const rows = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(rows[0]).toContain('Urbano')
    expect(rows[0]).toContain('Bad Bunny, Rauw Alejandro')
    expect(rows[0]).toContain('24 horas')
    expect(rows[0]).toContain('Activa')
    expect(rows[1]).toContain('Pausada · Descarga automática')
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('pasa de página con la query de la URL', async () => {
    server.use(
      http.get('/api/v1/watches/', ({ request }) => {
        const page = new URL(request.url).searchParams.get('page') ?? '1'
        return HttpResponse.json({
          count: 51,
          next: page === '1' ? 'x?page=2' : null,
          previous: page === '1' ? null : 'x',
          results: page === '1' ? watches : [{ ...watches[0], id: 9, interval_hours: 1 }],
        })
      }),
    )
    const { wrapper, router } = await mount(WatchesView, '/novedades')
    expect(button(wrapper, 'Anterior').attributes('disabled')).toBeDefined()
    await button(wrapper, 'Siguiente').trigger('click')
    await settle()
    expect(router.currentRoute.value.query.page).toBe('2')
    expect(wrapper.text()).toContain('1 hora')
    await button(wrapper, 'Anterior').trigger('click')
    await settle()
    expect(router.currentRoute.value.query.page).toBe('1')
  })

  it('muestra el error de la API', async () => {
    server.use(http.get('/api/v1/watches/', () => new HttpResponse(null, { status: 500 })))
    const { wrapper } = await mount(WatchesView, '/novedades')
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
  })
})

describe('WatchFormView', () => {
  it('da de alta con artistas buscados en el catálogo y en orden', async () => {
    const bodies = capture('POST')
    const { wrapper, router } = await mount(WatchFormView, '/novedades/nueva')
    expect(wrapper.get('h1').text()).toBe('Nueva búsqueda de novedades')
    expect(wrapper.text()).toContain('Todavía no hay artistas.')

    await fill(wrapper, 'Nombre', 'Mis novedades')
    await fill(wrapper, 'Intervalo en horas', '6')
    await wrapper.findAll('input[type="checkbox"]')[0]?.setValue(true)
    await fill(wrapper, 'Buscar en el catálogo', 'r')
    await wrapper.get('form[name="artist-search"]').trigger('submit')
    await settle()
    await button(wrapper, 'Añadir Rosalía').trigger('click')
    await button(wrapper, 'Añadir Rauw Alejandro').trigger('click')
    expect(wrapper.text()).toContain('Ningún artista del catálogo coincide.')
    await button(wrapper, 'Subir Rauw Alejandro').trigger('click')

    await wrapper.get('form[name="watch"]').trigger('submit')
    await settle()
    expect(bodies).toEqual([
      {
        name: 'Mis novedades',
        interval_hours: 6,
        auto_download: true,
        enabled: true,
        artist_ids: [3, 1],
      },
    ])
    expect(router.currentRoute.value.fullPath).toBe('/novedades/3')
  })

  it('no ofrece artistas ya elegidos y permite bajar y quitar', async () => {
    const bodies = capture('PATCH')
    const { wrapper } = await mount(WatchFormView, '/novedades/1/editar')
    expect(wrapper.get('h1').text()).toBe('Editar «Urbano»')
    expect(wrapper.findAll('.artists__chosen li').map((li) => li.text().split(/\s/)[0])).toEqual([
      'Bad',
      'Rauw',
    ])
    expect(button(wrapper, 'Subir Bad Bunny').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'Bajar Rauw Alejandro').attributes('disabled')).toBeDefined()

    await wrapper.get('form[name="artist-search"]').trigger('submit')
    await settle()
    expect(wrapper.findAll('.artists__results li').map((li) => li.text())).toEqual([
      'Añadir Rosalía',
    ])

    await button(wrapper, 'Bajar Bad Bunny').trigger('click')
    await button(wrapper, 'Quitar Bad Bunny').trigger('click')
    await wrapper.findAll('input[type="checkbox"]')[1]?.setValue(false)
    await wrapper.get('form[name="watch"]').trigger('submit')
    await settle()
    expect(bodies).toEqual([
      { name: 'Urbano', interval_hours: 24, auto_download: false, enabled: false, artist_ids: [3] },
    ])
  })

  it('muestra cada error de validación en su campo y el resto arriba', async () => {
    captureSave('post', () =>
      HttpResponse.json(
        {
          name: ['Ya existe una vigilancia con este nombre.'],
          interval_hours: ['Asegúrese de que este valor es mayor o igual a 1.'],
          artist_ids: ['Algún artista no existe.'],
          non_field_errors: ['Algo más.'],
        },
        { status: 400 },
      ),
    )
    const { wrapper, router } = await mount(WatchFormView, '/novedades/nueva')
    await wrapper.get('form[name="watch"]').trigger('submit')
    await settle()
    const errors = wrapper.findAll('.field__error').map((p) => p.text())
    expect(errors).toEqual([
      'Ya existe una vigilancia con este nombre.',
      'Asegúrese de que este valor es mayor o igual a 1.',
    ])
    expect(wrapper.get('.artists__error').text()).toBe('Algún artista no existe.')
    expect(wrapper.get('.alert').text()).toBe('Algo más.')
    expect(router.currentRoute.value.name).toBe('watches-new')
  })

  it('un 400 solo de campos no pone aviso general', async () => {
    captureSave('post', () => HttpResponse.json({ name: ['Obligatorio.'] }, { status: 400 }))
    const { wrapper } = await mount(WatchFormView, '/novedades/nueva')
    await wrapper.get('form[name="watch"]').trigger('submit')
    await settle()
    expect(wrapper.get('.field__error').text()).toBe('Obligatorio.')
    expect(wrapper.find('.alert').exists()).toBe(false)
  })

  it('otros fallos van al aviso general', async () => {
    captureSave('post', () => new HttpResponse(null, { status: 500 }))
    const { wrapper } = await mount(WatchFormView, '/novedades/nueva')
    await wrapper.get('form[name="watch"]').trigger('submit')
    await settle()
    expect(wrapper.get('.alert').text()).toBe('El servidor ha fallado. Inténtalo más tarde.')
    expect(wrapper.find('.field__error').exists()).toBe(false)
  })

  it('avisa si no puede cargar la búsqueda ni buscar artistas', async () => {
    server.use(
      http.get('/api/v1/watches/:id/', () => new HttpResponse(null, { status: 404 })),
      http.get('/api/v1/catalog/artists/', () => new HttpResponse(null, { status: 500 })),
    )
    const { wrapper } = await mount(WatchFormView, '/novedades/5/editar')
    expect(wrapper.get('.alert').text()).toBe('No se ha encontrado lo que buscabas.')
    await wrapper.get('form[name="artist-search"]').trigger('submit')
    await settle()
    expect(wrapper.get('.alert').text()).toBe('El servidor ha fallado. Inténtalo más tarde.')
  })
})

describe('WatchView', () => {
  it('muestra los datos y el historial de comprobaciones', async () => {
    const { wrapper } = await mount(WatchView, '/novedades/1')
    expect(wrapper.get('h1').text()).toBe('Urbano')
    expect(wrapper.text()).toContain('Activa · 24 horas')
    expect(wrapper.text()).toContain('Bad Bunny, Rauw Alejandro')
    const rows = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(rows[0]).toContain('Fallida')
    expect(rows[0]).toContain('Deezer no responde')
    expect(rows[1]).toContain('Correcta')
    expect(rows[0]).toContain(new Date('2026-01-03T10:01:00Z').toLocaleString('es'))
  })

  it('pagina el historial', async () => {
    server.use(
      http.get('/api/v1/watches/2/runs/', ({ request }) => {
        const first = !new URL(request.url).searchParams.has('page')
        return HttpResponse.json({
          count: 60,
          next: first ? 'x?page=2' : null,
          previous: first ? null : 'x',
          results: [],
        })
      }),
    )
    const { wrapper, router } = await mount(WatchView, '/novedades/2')
    expect(wrapper.text()).toContain('Pausada · 6 horas · Descarga automática')
    await button(wrapper, 'Siguiente').trigger('click')
    await settle()
    expect(router.currentRoute.value.query.page).toBe('2')
    await button(wrapper, 'Anterior').trigger('click')
    await settle()
    expect(router.currentRoute.value.query.page).toBe('1')
  })

  it('comprueba ahora y recarga el historial al terminar', async () => {
    const launched: unknown[] = []
    let runsCalls = 0
    const job = (status: JobRun['status']): JobRun => ({
      id: 8,
      kind: 'watch_check',
      params: { watch_id: 1 },
      user: 'demo',
      status,
      started_at: '2026-01-01T10:00:00Z',
      finished_at: null,
      done: 0,
      total: 1,
      current: 'Urbano',
      summary: {},
    })
    let detail = 0
    server.use(
      http.post('/api/v1/jobs/runs/', async ({ request }) => {
        launched.push(await request.json())
        return HttpResponse.json(job('pending'), { status: 201 })
      }),
      http.get('/api/v1/jobs/runs/8/', () =>
        HttpResponse.json(job(detail++ ? 'succeeded' : 'running')),
      ),
      http.get('/api/v1/watches/1/runs/', () => {
        runsCalls += 1
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] })
      }),
    )
    const { wrapper } = await mount(WatchView, '/novedades/1')
    await button(wrapper, 'Comprobar ahora').trigger('click')
    // Tiempo real: el sondeo pasa a «Terminada» en el siguiente ciclo (POLL_MS).
    await vi.waitFor(() => expect(wrapper.text()).toContain('En curso'))
    expect(launched).toEqual([{ kind: 'watch_check', params: { watch_id: 1 } }])
    expect(button(wrapper, 'Comprobar ahora').attributes('disabled')).toBeDefined()
    expect(runsCalls).toBe(1)
    await vi.waitFor(() => expect(runsCalls).toBe(2), { timeout: POLL_MS * 3 })
    expect(wrapper.text()).toContain('Terminada')
  })

  it('borra tras confirmar y vuelve a la lista', async () => {
    const deletes = capture('DELETE')
    const { wrapper, router } = await mount(WatchView, '/novedades/1')
    await button(wrapper, 'Borrar').trigger('click')
    expect(wrapper.get('dialog').attributes('open')).toBeDefined()
    expect(wrapper.get('dialog').text()).toContain('¿Borrar «Urbano»?')
    await button(wrapper, 'Cerrar').trigger('click')
    expect(wrapper.get('dialog').attributes('open')).toBeUndefined()
    await button(wrapper, 'Borrar').trigger('click')
    await button(wrapper, 'Sí, borrar').trigger('click')
    await settle()
    expect(deletes).toHaveLength(1)
    expect(router.currentRoute.value.name).toBe('watches')
  })

  it('muestra por qué no se puede borrar', async () => {
    server.use(
      http.delete('/api/v1/watches/1/', () =>
        HttpResponse.json(
          { detail: 'La vigilancia tiene comprobaciones registradas y no se puede borrar.' },
          { status: 409 },
        ),
      ),
    )
    const { wrapper, router } = await mount(WatchView, '/novedades/1')
    await button(wrapper, 'Borrar').trigger('click')
    await button(wrapper, 'Sí, borrar').trigger('click')
    await settle()
    expect(wrapper.get('.alert').text()).toContain('no se puede borrar')
    expect(router.currentRoute.value.name).toBe('watch')
  })

  it('avisa si no puede cargar el historial', async () => {
    server.use(http.get('/api/v1/watches/1/runs/', () => new HttpResponse(null, { status: 500 })))
    const { wrapper } = await mount(WatchView, '/novedades/1')
    expect(wrapper.get('.alert').text()).toBe('El servidor ha fallado. Inténtalo más tarde.')
  })

  it('avisa si la búsqueda no existe', async () => {
    const { wrapper } = await mount(WatchView, '/novedades/99')
    expect(wrapper.get('.alert').text()).toBe('No encontrado.')
    expect(wrapper.find('h1').exists()).toBe(false)
  })
})

describe('textos de Novedades', () => {
  type Tree = { [key: string]: string | Tree }
  const paths = (tree: Tree, prefix = ''): string[] =>
    Object.entries(tree).flatMap(([k, v]) =>
      typeof v === 'string' ? [`${prefix}${k}`] : paths(v, `${prefix}${k}.`),
    )

  it('tienen las mismas claves en es y en', () => {
    expect(paths(messages.en.watches as Tree)).toEqual(paths(messages.es.watches as Tree))
  })
})
