import { createPinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '../App.vue'
import { routes } from '../router'
import { render } from './helpers'

describe('App', () => {
  it('monta la navegación y la vista activa', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes })
    await router.push('/')
    const w = render(App, { global: { plugins: [createPinia(), router] } })
    expect(w.find('nav').exists()).toBe(true)
    expect(w.get('main.app-main').text()).toContain('Glissandi')
  })

  it('registra el service worker solo en producción', async () => {
    const register = vi.fn()
    vi.stubGlobal('navigator', { serviceWorker: { register } })
    const router = createRouter({ history: createMemoryHistory(), routes })
    const mountApp = () => render(App, { global: { plugins: [createPinia(), router] } })
    mountApp()
    expect(register).not.toHaveBeenCalled()
    vi.stubEnv('PROD', true)
    mountApp()
    expect(register).toHaveBeenCalledWith('/sw.js')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })
})
