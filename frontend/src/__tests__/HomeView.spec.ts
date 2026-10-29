import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createI18n } from 'vue-i18n'

import en from '../locales/en.json'
import es from '../locales/es.json'
import HomeView from '../views/HomeView.vue'

function render(locale: 'es' | 'en') {
  const i18n = createI18n({ legacy: false, locale, messages: { es, en } })
  return mount(HomeView, { global: { plugins: [i18n] } })
}

describe('HomeView', () => {
  it('muestra el lema en español', () => {
    expect(render('es').text()).toContain('Tu biblioteca musical')
  })

  it('muestra el lema en inglés', () => {
    expect(render('en').text()).toContain('Your music library')
  })
})
