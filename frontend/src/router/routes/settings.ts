import type { RouteRecordRaw } from 'vue-router'

import SettingsView from '../../views/SettingsView.vue'
import UsersView from '../../views/UsersView.vue'

/** Ajustes globales y gestión de usuarios: afectan a todo el servidor, solo administradores. */
export default [
  {
    path: '/ajustes',
    name: 'settings',
    component: SettingsView,
    meta: { navLabel: 'settings.nav', navGroup: 'more', navOrder: 80, adminOnly: true },
  },
  {
    path: '/usuarios',
    name: 'users',
    component: UsersView,
    meta: { navLabel: 'users.nav', navGroup: 'more', navOrder: 85, adminOnly: true },
  },
] satisfies RouteRecordRaw[]
