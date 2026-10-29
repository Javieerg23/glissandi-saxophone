<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import './nav-meta'

/**
 * Navegación principal: barra inferior en móvil, lateral desde 1024 px. Muestra las
 * rutas que declaran `meta.navLabel` (clave de vue-i18n), así que cada vista nueva
 * se añade a sí misma sin editar este componente.
 *
 * Main navigation: bottom bar on mobile, side bar from 1024 px. Lists routes that
 * declare `meta.navLabel` (a vue-i18n key), so new views register themselves.
 */
const { t } = useI18n()
const router = useRouter()
const items = computed(() => router.getRoutes().filter((r) => r.meta.navLabel))
</script>

<template>
  <nav class="nav" :aria-label="t('nav.main')">
    <ul>
      <li v-for="r in items" :key="r.name?.toString() ?? r.path">
        <RouterLink :to="r.path">{{ t(r.meta.navLabel as string) }}</RouterLink>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.nav {
  position: fixed;
  z-index: 10;
  inset: auto 0 0;
  height: var(--nav-bar-height);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}
ul {
  display: flex;
  height: 100%;
  margin: 0;
  padding: 0;
  list-style: none;
}
li {
  flex: 1;
}
a {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: var(--touch-target);
  height: 100%;
  color: var(--color-text);
  text-decoration: none;
}
a.router-link-exact-active {
  color: var(--color-primary);
  font-weight: 600;
}

@media (min-width: 1024px) {
  .nav {
    inset: 0 auto 0 0;
    width: var(--nav-side-width);
    height: auto;
    border-top: 0;
    border-right: 1px solid var(--color-border);
  }
  ul {
    flex-direction: column;
    padding: var(--space-3) 0;
  }
  li {
    flex: none;
  }
  a {
    justify-content: flex-start;
    padding: 0 var(--space-3);
  }
}
</style>
