import type { RequestHandler } from 'msw'

// Un fichero por zona en `handlers/`, como las rutas y los textos: cada vista añade el
// suyo sin tocar un array común (y sin conflictos entre PRs).
const modules = import.meta.glob<{ default: RequestHandler[] }>('./handlers/*.ts', { eager: true })

/** Respuestas simuladas de la API para desarrollo sin backend y para los tests. */
export const handlers: RequestHandler[] = Object.values(modules).flatMap((m) => m.default)
