import type { RouteRecordRaw } from 'vue-router'

import LibraryItemView from '../../views/library/LibraryItemView.vue'
import LibraryView from '../../views/library/LibraryView.vue'
import { KINDS } from '../../views/library/kinds'

/** Biblioteca: listas por pestaña y ficha de cada artista, álbum o canción. */
export default [
  {
    path: '/biblioteca',
    name: 'library',
    component: LibraryView,
    meta: { navLabel: 'library.nav', navGroup: 'main', navOrder: 20 },
    // Otras vistas (el Registro) enlazan un elemento con `?tab=…&id=…&panel=history`.
    beforeEnter: (to) => {
      const { tab, id, panel } = to.query
      if (!KINDS.some((k) => k === tab) || typeof id !== 'string' || !/^\d+$/.test(id)) return true
      return {
        name: 'library-item',
        params: { kind: tab as string, id },
        hash: panel === 'history' ? '#historial' : '',
      }
    },
  },
  {
    path: '/biblioteca/:kind(artists|albums|tracks)/:id(\\d+)',
    name: 'library-item',
    component: LibraryItemView,
  },
] satisfies RouteRecordRaw[]
