import type { RouteRecordRaw } from 'vue-router'

import LoginView from '../../views/LoginView.vue'
import SetupView from '../../views/SetupView.vue'

/** Rutas de acceso, abiertas sin sesión. */
export default [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/setup', name: 'setup', component: SetupView, meta: { public: true } },
] satisfies RouteRecordRaw[]
