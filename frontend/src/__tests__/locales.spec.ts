import { describe, expect, it } from 'vitest'

import { messages } from '../locales'

describe('locales', () => {
  it('reúne los mensajes de cada zona en ambos idiomas', () => {
    expect(messages.es).toHaveProperty('app.title')
    expect(messages.en).toHaveProperty('app.title')
  })

  it('tiene las mismas claves de primer nivel en español e inglés', () => {
    expect(Object.keys(messages.es).sort()).toEqual(Object.keys(messages.en).sort())
  })
})
