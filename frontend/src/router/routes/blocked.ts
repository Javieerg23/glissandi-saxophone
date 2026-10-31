import type { RouteRecordRaw } from 'vue-router'

import BlockedView from '../../views/BlockedView.vue'

/** Ruta de los elementos bloqueados. */
export default [
  {
    path: '/bloqueados',
    name: 'blocked',
    component: BlockedView,
    meta: { navLabel: 'blocked.nav', navGroup: 'more', navOrder: 30 },
  },
] satisfies RouteRecordRaw[]
