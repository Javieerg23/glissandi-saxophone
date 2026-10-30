import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router'

import { useSessionStore } from '../stores/session'

declare module 'vue-router' {
  /** Metadatos de ruta propios. / Project-specific route metadata. */
  interface RouteMeta {
    /** Ruta accesible sin sesión (login, configuración inicial). */
    public?: boolean
    /** Ruta solo para administradores; al resto se le lleva al panel. */
    adminOnly?: boolean
  }
}

/**
 * Protege las rutas privadas: sin sesión lleva al login (recordando el destino) y con
 * sesión saca de las públicas; las de `adminOnly` llevan al panel a quien no es
 * administrador. Pregunta al servidor una sola vez por carga de página.
 *
 * Guards private routes: anonymous users go to login (remembering the target), signed-in
 * users are bounced off public routes and non-admins off `adminOnly` ones. Asks the
 * server once per page load.
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
  if (!session.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } }
  // Solo oculta la vista: quien protege los datos es el permiso de cada endpoint.
  if (to.meta.adminOnly && session.user?.role !== 'administrador') return { name: 'dashboard' }
  return true
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
