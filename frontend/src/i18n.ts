import { createI18n } from 'vue-i18n'

import { messages } from './locales'

/** Clave de `localStorage` con el idioma elegido en los ajustes de la cuenta. */
export const LOCALE_KEY = 'locale'

function storedLocale(): 'es' | 'en' {
  try {
    return localStorage.getItem(LOCALE_KEY) === 'en' ? 'en' : 'es'
  } catch {
    // Almacenamiento bloqueado (modo privado): se usa el idioma por defecto.
    return 'es'
  }
}

/** Guarda el idioma elegido; si el almacenamiento no está disponible, solo dura la sesión. */
export function rememberLocale(locale: string): void {
  try {
    localStorage.setItem(LOCALE_KEY, locale)
  } catch {
    // Sin almacenamiento el cambio sigue valiendo hasta recargar.
  }
}

/** Español por defecto (o el idioma guardado); el inglés es la alternativa y el de reserva. */
export const i18n = createI18n({
  legacy: false,
  locale: storedLocale(),
  fallbackLocale: 'en',
  messages,
})
