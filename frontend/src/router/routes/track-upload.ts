import type { RouteRecordRaw } from 'vue-router'

import TrackUploadView from '../../views/TrackUploadView.vue'

/** Subida a mano del audio de una canción; se llega desde la canción, no desde el menú. */
export default [
  {
    path: '/canciones/:id(\\d+)/subir',
    name: 'track-upload',
    component: TrackUploadView,
    meta: { adminOnly: true },
  },
] satisfies RouteRecordRaw[]
