import { ApiError } from './client'

/** Cuerpo de error de DRF: `{ detail }` o `{ campo: [mensajes] }`. */
function flatten(body: unknown): string[] {
  if (typeof body === 'string') return [body]
  if (Array.isArray(body)) return body.flatMap(flatten)
  if (body !== null && typeof body === 'object') return Object.values(body).flatMap(flatten)
  return []
}

/**
 * Texto de un error de la API para mostrarlo al usuario: los mensajes que devuelve el
 * servidor (ya traducidos según `Accept-Language`) o, si no hay, el genérico de `errors.*`.
 * Cualquier otra excepción es un fallo de programación y se relanza.
 *
 * User-facing text for an API error: the server's own messages, else the generic `errors.*`.
 * Any other exception is a bug and is rethrown.
 */
export function errorText(e: unknown, t: (key: string) => string): string {
  if (!(e instanceof ApiError)) throw e
  return flatten(e.body).join(' ') || t(e.messageKey)
}
