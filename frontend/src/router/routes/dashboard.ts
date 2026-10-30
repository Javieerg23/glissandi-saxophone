import type { RouteRecordRaw } from 'vue-router'

import DashboardView from '../../views/DashboardView.vue'

/** Ruta del panel. */
export default [
  {
    path: '/panel',
    name: 'dashboard',
    component: DashboardView,
    meta: { navLabel: 'dashboard.nav' },
  },
] satisfies RouteRecordRaw[]
