import { createRouter, createWebHistory } from 'vue-router'

import HomeView from './views/HomeView.vue'

/** Rutas de la aplicación; cada pantalla nueva se añade aquí. */
export const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', name: 'home', component: HomeView }],
})
