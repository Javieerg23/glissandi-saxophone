import type { RouteRecordRaw } from 'vue-router'

import DownloadView from '../../views/DownloadView.vue'

/** Ruta de la descarga de canciones pendientes. */
export default [
  {
    path: '/descargar',
    name: 'download',
    component: DownloadView,
    meta: { navLabel: 'download.nav', navGroup: 'main', navOrder: 40 },
    // La lista solo muestra pendientes: el filtro va fijo en la URL porque `usePagedList`
    // manda a la API únicamente lo que hay en ella.
    beforeEnter: (to) =>
      to.query.downloaded === 'false' || { ...to, query: { ...to.query, downloaded: 'false' } },
  },
] satisfies RouteRecordRaw[]
