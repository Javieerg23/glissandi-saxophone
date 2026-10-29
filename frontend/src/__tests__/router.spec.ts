import { describe, expect, it } from 'vitest'

import { routes } from '../router'

describe('router', () => {
  it('reúne las rutas de los módulos de routes/', () => {
    expect(routes.map((r) => r.name)).toContain('home')
  })
})
