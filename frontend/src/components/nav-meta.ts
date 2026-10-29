import 'vue-router'

declare module 'vue-router' {
  /** Metadatos de ruta propios. / Project-specific route metadata. */
  interface RouteMeta {
    /** Clave de vue-i18n con la que la ruta aparece en la navegación principal. */
    navLabel?: string
  }
}
