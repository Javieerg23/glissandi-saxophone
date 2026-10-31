import type { RouteRecordRaw } from 'vue-router'

import ProxiesView from '../../views/ProxiesView.vue'

/** Ruta de los proxies de salida, solo para administradores. */
export default [
  {
    path: '/proxies',
    name: 'proxies',
    component: ProxiesView,
    meta: { navLabel: 'proxies.nav', navGroup: 'more', navOrder: 60, adminOnly: true },
  },
] satisfies RouteRecordRaw[]
