import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { routes } from '../router'
import { render } from './helpers'

/**
 * Monta una vista en `path` con el router real (rutas de `routes/`), Pinia y vue-i18n.
 * Sin guarda de navegación, para probar cada vista por separado.
 */
export async function mountView(view: Component, path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  const wrapper = render(view, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router, pinia }
}

/** Rellena un campo por su etiqueta visible. */
export async function fill(
  wrapper: ReturnType<typeof render>,
  label: string,
  value: string,
): Promise<void> {
  const field = wrapper.findAll('label').find((l) => l.text() === label)
  await wrapper.get(`#${field?.attributes('for')}`).setValue(value)
}
