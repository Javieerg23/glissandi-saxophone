import type { RouteRecordRaw } from 'vue-router'

import MoreView from '../../views/MoreView.vue'

/** «Más»: el resto de secciones en móvil; la enlaza la propia navegación. */
export default [{ path: '/mas', name: 'more', component: MoreView }] satisfies RouteRecordRaw[]
