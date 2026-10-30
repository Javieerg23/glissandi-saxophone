import { describe, expect, it } from 'vitest'

import { routes } from '../router'

describe('router', () => {
  it('reúne las rutas de los módulos de routes/', () => {
    expect(routes.map((r) => r.name)).toContain('home')
  })

  it('coloca el panel en la barra principal y la cuenta en «Más»', () => {
    const meta = (name: string) => routes.find((r) => r.name === name)?.meta
    expect(meta('dashboard')?.navGroup).toBe('main')
    expect(meta('account')?.navGroup).toBe('more')
    expect(routes.find((r) => r.name === 'more')?.path).toBe('/mas')
  })
})
