import { flushPromises } from '@vue/test-utils'
import { expect, vi } from 'vitest'

import { server } from '../mocks/server'

/**
 * Cuenta las peticiones en curso y devuelve una espera hasta que no quede ninguna y la vista
 * haya pintado sus respuestas. `flushPromises` solo no basta: una respuesta simulada puede
 * tardar más de una vuelta del bucle (en CI, o tras cambiar de ruta) y algunas encadenan otra.
 *
 * Counts in-flight requests and returns a wait until none is left and the view has rendered.
 */
export function trackRequests(): () => Promise<void> {
  let open = 0
  server.events.on('request:start', () => void open++)
  server.events.on('request:end', () => void open--)
  return async () => {
    do {
      await vi.waitFor(() => expect(open).toBe(0))
      await flushPromises()
    } while (open > 0)
  }
}
