import { afterEach, describe, expect, it, vi } from 'vitest'

async function load() {
  vi.resetModules()
  return import('../i18n')
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('i18n', () => {
  it('arranca en español', async () => {
    expect((await load()).i18n.global.locale.value).toBe('es')
  })

  it('recupera el inglés guardado', async () => {
    localStorage.setItem('locale', 'en')
    expect((await load()).i18n.global.locale.value).toBe('en')
  })

  it('ignora un valor guardado desconocido', async () => {
    localStorage.setItem('locale', 'fr')
    expect((await load()).i18n.global.locale.value).toBe('es')
  })

  it('guarda el idioma elegido', async () => {
    ;(await load()).rememberLocale('en')
    expect(localStorage.getItem('locale')).toBe('en')
  })

  it('funciona sin almacenamiento', async () => {
    const broken = {
      getItem: () => {
        throw new Error('bloqueado')
      },
      setItem: () => {
        throw new Error('bloqueado')
      },
    }
    vi.stubGlobal('localStorage', broken)
    const mod = await load()
    expect(mod.i18n.global.locale.value).toBe('es')
    expect(() => mod.rememberLocale('en')).not.toThrow()
  })
})
