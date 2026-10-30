import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { messages } from '../locales'

import { server } from '../mocks/server'
import TrackUploadView from '../views/TrackUploadView.vue'
import { mountView } from './viewHelpers'

const URL = '/api/v1/catalog/tracks/7/upload/'

async function choose(wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'], name = 'a.wav') {
  const input = wrapper.get('input[type="file"]')
  const file = new File(['audio'], name, { type: 'audio/wav' })
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  return file
}

describe('TrackUploadView', () => {
  it('muestra la canción y no deja enviar sin fichero', async () => {
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    expect(wrapper.get('h1').text()).toBe('Subir audio')
    expect(wrapper.text()).toContain('One More Time')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('sube el fichero elegido con el token CSRF y avisa al terminar', async () => {
    const sent: Request[] = []
    const listen = ({ request }: { request: Request }) => void sent.push(request.clone())
    server.events.on('request:start', listen)
    document.cookie = 'csrftoken=abc'
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    await choose(wrapper, 'grabación.wav')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').exists()).toBe(true))
    server.events.removeListener('request:start', listen)
    expect(wrapper.get('[role="status"]').text()).toBe(
      'Audio guardado. La canción ya está descargada.',
    )
    const upload = sent.find((r) => r.method === 'POST')
    expect(upload?.headers.get('X-CSRFToken')).toBe('abc')
    expect(((await upload?.formData())?.get('file') as File).name).toBe('grabación.wav')
  })

  it('no envía nada si se quita el fichero elegido', async () => {
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    await choose(wrapper)
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [] })
    await input.trigger('change')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(false)
  })

  it('pinta el porcentaje subido cuando el navegador lo conoce', async () => {
    const xhrs: FakeXhr[] = []
    class FakeXhr {
      upload: { onprogress?: (e: Partial<ProgressEvent>) => void } = {}
      constructor() {
        xhrs.push(this)
      }
      open() {}
      setRequestHeader() {}
      send() {}
    }
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    await choose(wrapper)
    await wrapper.get('form').trigger('submit')
    const bar = () => wrapper.get('[role="progressbar"]').attributes('aria-valuenow')
    xhrs[0]?.upload.onprogress?.({ lengthComputable: false, loaded: 1, total: 0 })
    await flushPromises()
    expect(bar()).toBe('0')
    xhrs[0]?.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 200 })
    await flushPromises()
    expect(bar()).toBe('25')
    vi.unstubAllGlobals()
  })

  it('muestra el progreso mientras sube', async () => {
    let finish: () => void = () => {}
    server.use(
      http.post(URL, async () => {
        await new Promise<void>((resolve) => (finish = resolve))
        return HttpResponse.json({ id: 7, downloaded: true }, { status: 201 })
      }),
    )
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    await choose(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(true)
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    finish()
    await vi.waitFor(() => expect(wrapper.find('[role="progressbar"]').exists()).toBe(false))
  })

  it('muestra el error de validación del servidor', async () => {
    server.use(
      http.post(URL, () =>
        HttpResponse.json({ file: ['El fichero no es un audio válido.'] }, { status: 400 }),
      ),
    )
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    await choose(wrapper, 'notas.txt')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.get('[role="alert"]').text()).toBe('El fichero no es un audio válido.')
  })

  it('muestra un error genérico si el servidor no explica el fallo', async () => {
    server.use(http.post(URL, () => new HttpResponse('boom', { status: 500 })))
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    await choose(wrapper)
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
  })

  it('avisa si no hay conexión', async () => {
    server.use(http.post(URL, () => HttpResponse.error()))
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    await choose(wrapper)
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo conectar con el servidor.')
  })

  it('avisa si la canción no existe', async () => {
    server.use(
      http.get('/api/v1/catalog/tracks/:id/', () =>
        HttpResponse.json({ detail: 'No encontrado.' }, { status: 404 }),
      ),
    )
    const { wrapper } = await mountView(TrackUploadView, '/canciones/7/subir')
    expect(wrapper.get('[role="alert"]').text()).toBe('No encontrado.')
  })

  it('es solo para administradores y no sale en la navegación', async () => {
    const { router } = await mountView(TrackUploadView, '/canciones/7/subir')
    const route = router.resolve({ name: 'track-upload', params: { id: 7 } })
    expect(route.path).toBe('/canciones/7/subir')
    expect(route.meta.adminOnly).toBe(true)
    expect(route.meta.navLabel).toBeUndefined()
  })
  it('tiene los mismos textos en español y en inglés', () => {
    const keys = (tree: object): string[] =>
      Object.entries(tree).flatMap(([k, v]) =>
        typeof v === 'string' ? [k] : keys(v as object).map((c) => `${k}.${c}`),
      )
    expect(keys(messages.en.trackUpload as object)).toEqual(keys(messages.es.trackUpload as object))
  })
})
