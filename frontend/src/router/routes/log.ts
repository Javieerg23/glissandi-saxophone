import type { RouteRecordRaw } from 'vue-router'

import LogView from '../../views/log/LogView.vue'

/** Registro: actividad, tareas y logs técnicos; la pestaña va en `?tab=`. */
export default [
  {
    path: '/registro',
    name: 'log',
    component: LogView,
    meta: { navLabel: 'log.nav', navGroup: 'more', navOrder: 80 },
  },
] satisfies RouteRecordRaw[]
