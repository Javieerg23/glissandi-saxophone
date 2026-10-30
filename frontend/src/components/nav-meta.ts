import 'vue-router'
import type { RouteRecordNormalized } from 'vue-router'

declare module 'vue-router' {
  /** Metadatos de ruta propios. / Project-specific route metadata. */
  interface RouteMeta {
    /** Clave de vue-i18n con la que la ruta aparece en la navegación principal. */
    navLabel?: string
    /** Grupo de la navegación; sin él, la ruta va a «Más». */
    navGroup?: 'main' | 'more'
    /** Posición dentro del grupo, de menor a mayor (0 por defecto). */
    navOrder?: number
  }
}

/** Entradas que caben en la barra inferior del móvil; el resto va a «Más». */
export const MAIN_SLOTS = 4

/**
 * Reparte las rutas con `navLabel` entre la barra principal y «Más», ordenadas y sin las de
 * administrador si el usuario no lo es. Las principales que no caben pasan al principio de «Más».
 *
 * Splits routes with `navLabel` into the main bar and "More", sorted, hiding admin-only ones
 * for non-admins. Main entries beyond the bar's slots go first in "More".
 */
export function navEntries(
  routes: RouteRecordNormalized[],
  isAdmin: boolean,
): { main: RouteRecordNormalized[]; more: RouteRecordNormalized[] } {
  const visible = routes
    .filter((r) => r.meta.navLabel && (isAdmin || !r.meta.adminOnly))
    .sort((a, b) => (a.meta.navOrder ?? 0) - (b.meta.navOrder ?? 0))
  const main = visible.filter((r) => r.meta.navGroup === 'main')
  const more = visible.filter((r) => r.meta.navGroup !== 'main')
  return { main: main.slice(0, MAIN_SLOTS), more: [...main.slice(MAIN_SLOTS), ...more] }
}
