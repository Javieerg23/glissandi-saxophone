import type { RouteRecordRaw } from 'vue-router'

import ImportView from '../../views/ImportView.vue'

/** Importar artistas desde Deezer. */
export default [
  {
    path: '/importar',
    name: 'import',
    component: ImportView,
    meta: { navLabel: 'import.nav', navGroup: 'main', navOrder: 30 },
  },
] satisfies RouteRecordRaw[]
