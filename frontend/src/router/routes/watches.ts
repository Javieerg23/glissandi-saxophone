import type { RouteRecordRaw } from 'vue-router'

import WatchFormView from '../../views/watches/WatchFormView.vue'
import WatchesView from '../../views/watches/WatchesView.vue'
import WatchView from '../../views/watches/WatchView.vue'

/** Búsquedas de novedades: lista, alta, detalle con historial y edición. */
export default [
  {
    path: '/novedades',
    name: 'watches',
    component: WatchesView,
    meta: { navLabel: 'watches.nav', navGroup: 'more', navOrder: 20 },
  },
  { path: '/novedades/nueva', name: 'watches-new', component: WatchFormView },
  { path: '/novedades/:id(\\d+)', name: 'watch', component: WatchView },
  { path: '/novedades/:id(\\d+)/editar', name: 'watches-edit', component: WatchFormView },
] satisfies RouteRecordRaw[]
