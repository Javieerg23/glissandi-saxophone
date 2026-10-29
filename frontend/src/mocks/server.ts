import { setupServer } from 'msw/node'

import { handlers } from './handlers'

/** Servidor MSW para Vitest (Node). */
export const server = setupServer(...handlers)
