import type { RouteRecordRaw } from 'vue-router'

import AccountView from '../../views/AccountView.vue'

/** Ruta de los ajustes de la cuenta. */
export default [
  {
    path: '/cuenta',
    name: 'account',
    component: AccountView,
    meta: { navLabel: 'account.nav', navGroup: 'more', navOrder: 90 },
  },
] satisfies RouteRecordRaw[]
