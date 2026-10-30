<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useSessionStore } from '../stores/session'
import { navEntries } from './nav-meta'

/**
 * Navegación principal. En móvil, barra inferior con las entradas `main` y «Más», que lleva
 * a la lista del resto; desde 1024 px, barra lateral con todo, agrupado. Las dos formas son
 * el mismo HTML y cambian solo por CSS. Cada vista se añade a sí misma con `meta.navLabel`.
 *
 * Main navigation. On mobile, a bottom bar with the `main` entries plus "More"; from
 * 1024 px, a side bar with everything, grouped. Same markup, switched by CSS only.
 */
const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()
const entries = computed(() =>
  navEntries(router.getRoutes(), session.user?.role === 'administrador'),
)
</script>

<template>
  <nav class="nav" :aria-label="t('nav.main')">
    <ul class="nav__main">
      <li v-for="r in entries.main" :key="r.name?.toString() ?? r.path">
        <RouterLink :to="r.path">{{ t(r.meta.navLabel as string) }}</RouterLink>
      </li>
      <li class="nav__more-item">
        <RouterLink class="nav__more-link" :to="{ name: 'more' }">{{ t('nav.more') }}</RouterLink>
      </li>
    </ul>
    <template v-if="entries.more.length">
      <h2 id="nav-more-title" class="nav__group-title">{{ t('nav.more') }}</h2>
      <ul class="nav__secondary" aria-labelledby="nav-more-title">
        <li v-for="r in entries.more" :key="r.name?.toString() ?? r.path">
          <RouterLink :to="r.path">{{ t(r.meta.navLabel as string) }}</RouterLink>
        </li>
      </ul>
    </template>
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
/* En móvil el resto se ve desde «Más»; el grupo solo existe en la barra lateral. */
.nav__group-title,
.nav__secondary {
  display: none;
}

@media (min-width: 1024px) {
  .nav {
    inset: 0 auto 0 0;
    width: var(--nav-side-width);
    height: auto;
    overflow-y: auto;
    border-top: 0;
    border-right: 1px solid var(--color-border);
  }
  ul {
    flex-direction: column;
    height: auto;
    padding: var(--space-3) 0;
  }
  li {
    flex: none;
  }
  a {
    justify-content: flex-start;
    padding: 0 var(--space-3);
  }
  .nav__more-item {
    display: none;
  }
  .nav__group-title {
    display: block;
    margin: 0;
    padding: 0 var(--space-3);
    color: var(--color-muted);
    font-size: 0.875rem;
    text-transform: uppercase;
  }
  .nav__secondary {
    display: flex;
    padding-top: var(--space-2);
  }
}
</style>
