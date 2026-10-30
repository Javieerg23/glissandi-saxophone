import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { errorText } from '../api/errors'

const t = (key: string) => `t:${key}`

describe('errorText', () => {
  it('usa el detalle que devuelve el servidor', () => {
    expect(errorText(new ApiError('unknown', 400, { detail: 'Mal.' }), t)).toBe('Mal.')
  })

  it('junta los mensajes de varios campos', () => {
    const body = { username: ['Corto.', 'Raro.'], password: ['Débil.'] }
    expect(errorText(new ApiError('unknown', 400, body), t)).toBe('Corto. Raro. Débil.')
  })

  it('acepta un cuerpo que es solo texto', () => {
    expect(errorText(new ApiError('unknown', 400, 'Texto'), t)).toBe('Texto')
  })

  it('cae al mensaje genérico si el cuerpo no trae texto', () => {
    expect(errorText(new ApiError('server', 500, null), t)).toBe('t:errors.server')
    expect(errorText(new ApiError('server', 500, 42), t)).toBe('t:errors.server')
  })

  it('relanza lo que no es un error de la API', () => {
    expect(() => errorText(new TypeError('bug'), t)).toThrow('bug')
  })
})
