import type { RouteRecordRaw } from 'vue-router'

import UtilitiesView from '../../views/UtilitiesView.vue'

/** Ruta de las utilidades de mantenimiento del catálogo. */
export default [
  {
    path: '/utilidades',
    name: 'utilities',
    component: UtilitiesView,
    meta: { navLabel: 'utilities.nav', navGroup: 'more', navOrder: 50 },
  },
] satisfies RouteRecordRaw[]
