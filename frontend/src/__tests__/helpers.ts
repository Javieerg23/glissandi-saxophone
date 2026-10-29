import { mount } from '@vue/test-utils'
import type { Component, Plugin } from 'vue'
import { createI18n } from 'vue-i18n'

import { messages } from '../locales'

/** Monta un componente con vue-i18n en el idioma indicado. */
export function render(component: Component, options: Record<string, unknown> = {}, locale = 'es') {
  const i18n = createI18n({ legacy: false, locale, messages })
  const extra = (options.global as { plugins?: Plugin[] } | undefined)?.plugins ?? []
  return mount(component, { ...options, global: { plugins: [i18n, ...extra] } })
}
