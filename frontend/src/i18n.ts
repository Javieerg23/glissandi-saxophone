import { createI18n } from 'vue-i18n'

import { messages } from './locales'

/** Español por defecto; el inglés es la alternativa y también el idioma de reserva. */
export const i18n = createI18n({
  legacy: false,
  locale: 'es',
  fallbackLocale: 'en',
  messages,
})
