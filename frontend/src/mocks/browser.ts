import { setupWorker } from 'msw/browser'

import { handlers } from './handlers'

/** Service worker MSW para el navegador; solo se carga en desarrollo con `VITE_MOCKS=1`. */
export const worker = setupWorker(...handlers)
