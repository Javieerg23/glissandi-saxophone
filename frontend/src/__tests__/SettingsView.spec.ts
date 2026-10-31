import { http, HttpResponse } from 'msw'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type RouteLocationNormalized } from 'vue-router'

import { navEntries } from '../components/nav-meta'
import { messages } from '../locales'
import { server } from '../mocks/server'
import { routes } from '../router'
import { authGuard } from '../router/guards'
import SettingsView from '../views/SettingsView.vue'
import { fill, mountView } from './viewHelpers'

const field = (wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'], label: string) => {
  const id = wrapper
    .findAll('label')
    .find((l) => l.text() === label)
    ?.attributes('for')
  return wrapper.get(`#${id}`)
}

describe('SettingsView', () => {
  it('carga los ajustes y enlaza a la cuenta', async () => {
    const { wrapper } = await mountView(SettingsView, '/ajustes')
    expect((field(wrapper, 'Formato de descarga').element as HTMLSelectElement).value).toBe('mp3')
    expect((field(wrapper, 'Carpeta de descargas').element as HTMLInputElement).value).toBe('music')
    expect(wrapper.text()).toContain('{artist} {album} {disc} {track} {title} {year}')
    expect(wrapper.get('a').attributes('href')).toBe('/cuenta')
  })

  it('guarda solo los ajustes cambiados', async () => {
    const puts: string[] = []
    server.use(
      http.put('/api/v1/preferences/:key/', async ({ params, request }) => {
        puts.push(params.key as string)
        const { value } = (await request.json()) as { value: unknown }
        return HttpResponse.json({ key: params.key, value, default: 'mp3' })
      }),
    )
    const { wrapper } = await mountView(SettingsView, '/ajustes')
    await field(wrapper, 'Formato de descarga').setValue('flac')
    await fill(wrapper, 'Carpeta de descargas', 'musica')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(puts.sort()).toEqual(['download.folder', 'download.format'])
    expect(wrapper.get('[role="status"]').text()).toBe('Ajustes guardados.')

    // Ya guardados: un segundo envío no repite las peticiones.
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(puts).toHaveLength(2)
  })

  it('muestra el error de validación en su campo y guarda los demás', async () => {
    server.use(
      http.put('/api/v1/preferences/download.name_template/', () =>
        HttpResponse.json({ value: ['Plantilla no válida.'] }, { status: 400 }),
      ),
      http.put('/api/v1/preferences/download.format/', () =>
        HttpResponse.json({ value: ['Formato no válido.'] }, { status: 400 }),
      ),
    )
    const { wrapper } = await mountView(SettingsView, '/ajustes')
    await fill(wrapper, 'Plantilla de nombres', '{nada}')
    await field(wrapper, 'Formato de descarga').setValue('opus')
    await fill(wrapper, 'Carpeta de descargas', 'musica')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const template = field(wrapper, 'Plantilla de nombres')
    expect(template.attributes('aria-invalid')).toBe('true')
    expect(wrapper.text()).toContain('Plantilla no válida.')
    expect(field(wrapper, 'Formato de descarga').attributes('aria-describedby')).toBeTruthy()
    expect(wrapper.text()).toContain('Formato no válido.')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('muestra un error general si falla sin errores de campo', async () => {
    server.use(http.put('/api/v1/preferences/:key/', () => new HttpResponse(null, { status: 500 })))
    const { wrapper } = await mountView(SettingsView, '/ajustes')
    await fill(wrapper, 'Carpeta de descargas', 'musica')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe(
      'El servidor ha fallado. Inténtalo más tarde.',
    )
  })

  it('muestra el error si no puede cargar los ajustes e ignora claves ajenas', async () => {
    server.use(
      http.get('/api/v1/preferences/', () => HttpResponse.json([{ key: 'otro', value: 1 }])),
    )
    const { wrapper } = await mountView(SettingsView, '/ajustes')
    expect((field(wrapper, 'Carpeta de descargas').element as HTMLInputElement).value).toBe('')
    server.use(http.get('/api/v1/preferences/', () => new HttpResponse(null, { status: 403 })))
    const failed = await mountView(SettingsView, '/ajustes')
    expect(failed.wrapper.get('[role="alert"]').text()).toBe('No tienes permiso para hacer esto.')
  })
})

describe('rutas de ajustes y usuarios', () => {
  it('solo las ven y abren los administradores', async () => {
    setActivePinia(createPinia())
    const router = createRouter({ history: createMemoryHistory(), routes })
    const names = (admin: boolean) => navEntries(router.getRoutes(), admin).more.map((r) => r.name)
    expect(names(true)).toEqual(expect.arrayContaining(['settings', 'users']))
    expect(names(false)).not.toContain('settings')
    expect(names(false)).not.toContain('users')

    server.use(
      http.get('/api/v1/accounts/me/', () =>
        HttpResponse.json({ username: 'invitado', role: 'usuario' }),
      ),
    )
    for (const path of ['/ajustes', '/usuarios']) {
      const to = router.resolve(path) as unknown as RouteLocationNormalized
      expect(await authGuard(to)).toEqual({ name: 'dashboard' })
    }
  })
})

describe('textos de ajustes y usuarios', () => {
  type Tree = { [key: string]: string | Tree }
  const paths = (tree: Tree, prefix = ''): string[] =>
    Object.entries(tree).flatMap(([k, v]) =>
      typeof v === 'string' ? [`${prefix}${k}`] : paths(v, `${prefix}${k}.`),
    )

  it.each(['settings', 'users'])('«%s» tiene las mismas claves en es y en', (ns) => {
    expect(paths(messages.en[ns] as Tree)).toEqual(paths(messages.es[ns] as Tree))
  })
})
