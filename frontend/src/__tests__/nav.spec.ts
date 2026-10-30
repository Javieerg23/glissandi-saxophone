import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'

import AppNav from '../components/AppNav.vue'
import { navEntries } from '../components/nav-meta'
import { useSessionStore } from '../stores/session'
import MoreView from '../views/MoreView.vue'
import { render } from './helpers'

const Empty = { template: '<div />' }
const route = (name: string, meta: RouteRecordRaw['meta']): RouteRecordRaw => ({
  path: `/${name}`,
  name,
  component: Empty,
  meta: { navLabel: 'nav.home', ...meta },
})

// Seis entradas principales (una de más), dos secundarias y una solo para administradores.
const routes: RouteRecordRaw[] = [
  route('m3', { navGroup: 'main', navOrder: 3 }),
  route('m1', { navGroup: 'main', navOrder: 1 }),
  route('m2', { navGroup: 'main', navOrder: 2 }),
  route('m4', { navGroup: 'main', navOrder: 4 }),
  route('m5', { navGroup: 'main', navOrder: 5 }),
  route('s2', { navGroup: 'more', navOrder: 2 }),
  route('s1', {}),
  route('admin', { navGroup: 'more', navOrder: 3, adminOnly: true }),
  { path: '/anonima', component: Empty, meta: { navLabel: 'nav.home' } },
  { path: '/oculta', component: Empty },
  { path: '/mas', name: 'more', component: MoreView },
]

function mount(role: 'administrador' | 'usuario' = 'usuario', locale = 'es') {
  const pinia = createPinia()
  setActivePinia(pinia)
  useSessionStore().user = { username: 'demo', role }
  const router = createRouter({ history: createMemoryHistory(), routes })
  return {
    router,
    render: (c: object) => render(c, { global: { plugins: [pinia, router] } }, locale),
  }
}

const names = (w: ReturnType<typeof render>, selector: string) =>
  w.findAll(`${selector} a`).map((a) => a.attributes('href'))

describe('navEntries', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('ordena por navOrder, deja «more» por defecto y quita las de administrador', () => {
    const r = createRouter({ history: createMemoryHistory(), routes })
    const { main, more } = navEntries(r.getRoutes(), false)
    expect(main.map((e) => e.name)).toEqual(['m1', 'm2', 'm3', 'm4'])
    expect(more.map((e) => e.path)).toEqual(['/m5', '/s1', '/anonima', '/s2'])
  })

  it('incluye las de administrador para un administrador', () => {
    const r = createRouter({ history: createMemoryHistory(), routes })
    expect(navEntries(r.getRoutes(), true).more.map((e) => e.name)).toContain('admin')
  })
})

describe('AppNav', () => {
  it('en móvil: cuatro principales y «Más»', async () => {
    const ctx = mount()
    await ctx.router.push('/m1')
    const w = ctx.render(AppNav)
    expect(w.get('nav').attributes('aria-label')).toBe('Navegación principal')
    expect(names(w, '.nav__main li:not(.nav__more-item)')).toEqual(['/m1', '/m2', '/m3', '/m4'])
    expect(w.get('.nav__more-link').attributes('href')).toBe('/mas')
    expect(w.get('.nav__more-link').text()).toBe('Más')
    expect(w.get('.nav__main a').classes()).toContain('router-link-exact-active')
  })

  it('en escritorio: el resto agrupado bajo su título', () => {
    const w = mount().render(AppNav)
    expect(w.get('.nav__group-title').text()).toBe('Más')
    expect(names(w, '.nav__secondary')).toEqual(['/m5', '/s1', '/anonima', '/s2'])
  })

  it('enseña las entradas de administrador solo a administradores', () => {
    expect(names(mount('administrador').render(AppNav), '.nav__secondary')).toContain('/admin')
    expect(names(mount('usuario').render(AppNav), '.nav__secondary')).not.toContain('/admin')
  })

  it('traduce al inglés', () => {
    const w = mount('usuario', 'en').render(AppNav)
    expect(w.get('.nav__main a').text()).toBe('Home')
    expect(w.get('.nav__more-link').text()).toBe('More')
  })

  it('usa la ruta como clave si no tiene nombre', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const r = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/x', component: Empty, meta: { navLabel: 'nav.home', navGroup: 'main' } },
        { path: '/mas', name: 'more', component: Empty },
      ],
    })
    expect(
      render(AppNav, { global: { plugins: [pinia, r] } }).findAll('.nav__main a'),
    ).toHaveLength(2)
  })

  it('sin sesión trata al usuario como no administrador', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const r = createRouter({ history: createMemoryHistory(), routes })
    const w = render(AppNav, { global: { plugins: [pinia, r] } })
    expect(names(w, '.nav__secondary')).not.toContain('/admin')
  })
})

describe('MoreView', () => {
  it('lista las entradas que no caben en la barra inferior', () => {
    const w = mount('administrador').render(MoreView)
    expect(w.get('h1').text()).toBe('Más')
    expect(w.findAll('a').map((a) => a.attributes('href'))).toEqual([
      '/m5',
      '/s1',
      '/anonima',
      '/s2',
      '/admin',
    ])
  })
})
