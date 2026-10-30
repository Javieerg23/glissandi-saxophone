import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { authGuard } from './guards'

// Cada módulo de `routes/` exporta por defecto sus rutas; así una vista nueva
// añade un fichero en lugar de editar uno común (y evita conflictos entre PRs).
const modules = import.meta.glob<{ default: RouteRecordRaw[] }>('./routes/*.ts', { eager: true })

/** Todas las rutas de la aplicación, reunidas de `routes/*.ts`. */
export const routes: RouteRecordRaw[] = Object.values(modules).flatMap((m) => m.default)

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(authGuard)
