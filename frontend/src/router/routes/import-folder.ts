import type { RouteRecordRaw } from 'vue-router'

import FolderImportView from '../../views/FolderImportView.vue'

/** Importar una carpeta de música; sin entrada propia en la navegación (se llega desde Importar). */
export default [
  { path: '/importar/carpeta', name: 'import-folder', component: FolderImportView },
] satisfies RouteRecordRaw[]
