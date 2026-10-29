import type { RouteRecordRaw } from 'vue-router'

import HomeView from '../../views/HomeView.vue'

/** Rutas de la pantalla de inicio. */
export default [{ path: '/', name: 'home', component: HomeView }] satisfies RouteRecordRaw[]
