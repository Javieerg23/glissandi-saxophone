import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import AppNav from '../components/AppNav.vue'
import { render } from './helpers'

const Empty = { template: '<div />' }

describe('AppNav', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Empty, meta: { navLabel: 'nav.home' } },
      { path: '/oculta', component: Empty },
    ],
  })

  it('lista solo las rutas con navLabel, traducidas', async () => {
    await router.push('/')
    const w = render(AppNav, { global: { plugins: [router] } })
    expect(w.get('nav').attributes('aria-label')).toBe('Navegación principal')
    expect(w.findAll('a').map((a) => a.text())).toEqual(['Inicio'])
    expect(w.get('a').classes()).toContain('router-link-exact-active')
  })

  it('traduce al inglés', () => {
    const w = render(AppNav, { global: { plugins: [router] } }, 'en')
    expect(w.get('a').text()).toBe('Home')
  })

  it('usa la ruta como clave si no tiene nombre', () => {
    const r = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/x', component: Empty, meta: { navLabel: 'nav.home' } }],
    })
    expect(render(AppNav, { global: { plugins: [r] } }).findAll('a')).toHaveLength(1)
  })
})
