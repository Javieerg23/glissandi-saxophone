/** Categoría de error común de la API, mapeada a una clave `errors.*` de vue-i18n. */
export type ApiErrorKind =
  'network' | 'unauthorized' | 'forbidden' | 'notFound' | 'server' | 'unknown'

/**
 * Error de una petición a la API.
 *
 * Error from an API request; `kind` maps to an `errors.*` i18n key.
 */
export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status: number,
    readonly body: unknown = null,
  ) {
    super(kind)
  }

  /** Clave de vue-i18n con el mensaje para el usuario. */
  get messageKey(): string {
    return `errors.${this.kind}`
  }
}

export function kindOf(status: number): ApiErrorKind {
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'notFound'
  return status >= 500 ? 'server' : 'unknown'
}

export function csrfToken(): string {
  return document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] ?? ''
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

/**
 * Petición JSON a la API de Django. Con sesión por cookie, Django exige el token
 * CSRF en la cabecera `X-CSRFToken` en todo método que no sea de lectura. Un cuerpo
 * `FormData` va como multipart (subida de ficheros) y el navegador pone su Content-Type.
 *
 * JSON request to the Django API. Session cookies require the CSRF token in the
 * `X-CSRFToken` header on every non-read method. A `FormData` body goes as multipart
 * (file uploads); the browser sets its Content-Type with the boundary.
 *
 * @throws {ApiError} si no hay red o la respuesta no es 2xx.
 */
export async function api<T = unknown>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers: Record<string, string> = { Accept: 'application/json' }
  const form = init.body instanceof FormData
  if (init.body !== undefined && !form) headers['Content-Type'] = 'application/json'
  if (!SAFE_METHODS.has(method)) headers['X-CSRFToken'] = csrfToken()

  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: 'same-origin',
      body: form
        ? (init.body as FormData)
        : init.body === undefined
          ? undefined
          : JSON.stringify(init.body),
    })
  } catch {
    throw new ApiError('network', 0)
  }

  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(kindOf(res.status), res.status, body)
  return body as T
}
