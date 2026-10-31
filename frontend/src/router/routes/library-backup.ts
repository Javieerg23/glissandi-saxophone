import type { RouteRecordRaw } from 'vue-router'

import LibraryBackupView from '../../views/LibraryBackupView.vue'

/** Copia de la biblioteca: sin entrada en la navegación, la enlazan otras vistas. */
export default [
  {
    path: '/biblioteca/copia',
    name: 'library-backup',
    component: LibraryBackupView,
    meta: { adminOnly: true },
  },
] satisfies RouteRecordRaw[]
