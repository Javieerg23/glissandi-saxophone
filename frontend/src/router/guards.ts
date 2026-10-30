import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router'

import { useSessionStore } from '../stores/session'

declare module 'vue-router' {
  /** Metadatos de ruta propios. / Project-specific route metadata. */
  interface RouteMeta {
    /** Ruta accesible sin sesión (login, configuración inicial). */
    public?: boolean
  }
}

/**
 * Protege las rutas privadas: sin sesión lleva al login (recordando el destino) y con
 * sesión saca de las públicas. Pregunta al servidor una sola vez por carga de página.
 *
 * Guards private routes: anonymous users go to login (remembering the target) and
 * signed-in users are bounced off public routes. Asks the server once per page load.
 */
export async function authGuard(to: RouteLocationNormalized): Promise<true | RouteLocationRaw> {
  const session = useSessionStore()
  if (!session.loaded) {
    try {
      await session.fetchMe()
    } catch {
      // Servidor caído: se trata como anónimo y el login mostrará el error al enviar.
    }
  }
  if (to.meta.public) return session.isAuthenticated ? { name: 'dashboard' } : true
  return session.isAuthenticated ? true : { name: 'login', query: { redirect: to.fullPath } }
}

/**
 * Destino tras el login. Solo se admiten rutas internas: `//host` o `https://…` serían
 * una redirección abierta.
 *
 * Post-login target. Internal paths only; anything else would be an open redirect.
 */
export function safeRedirect(value: unknown): string | null {
  return typeof value === 'string' && /^\/(?![/\\])/.test(value) ? value : null
}
