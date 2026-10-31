<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import LibraryList from './LibraryList.vue'
import { KINDS, type Kind } from './kinds'

/**
 * Biblioteca: pestañas de artistas, álbumes y canciones. La pestaña va en la URL (`tab`)
 * junto a los filtros, así que un enlace lleva a la misma lista filtrada.
 *
 * Library: artists, albums and tracks tabs. The tab lives in the URL next to the filters.
 */
const { t } = useI18n()
const route = useRoute()
const kind = computed<Kind>(() => {
  const tab = route.query.tab
  return KINDS.find((k) => k === tab) ?? 'artists'
})
</script>

<template>
  <section class="library">
    <h1>{{ t('library.title') }}</h1>
    <nav class="library__tabs" :aria-label="t('library.tabs')">
      <RouterLink
        v-for="k in KINDS"
        :key="k"
        :to="{ name: 'library', query: { tab: k } }"
        :aria-current="k === kind ? 'page' : undefined"
        class="library__tab"
      >
        {{ t(`library.kind.${k}`) }}
      </RouterLink>
    </nav>
    <!-- Una lista por pestaña: al cambiar se monta de cero con su propia ruta de la API. -->
    <LibraryList :key="kind" :kind="kind" />
  </section>
</template>

<style scoped>
.library {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.library__tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border);
}
.library__tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: var(--touch-target);
  color: var(--color-muted);
  text-decoration: none;
}
.library__tab[aria-current='page'] {
  color: var(--color-text);
  font-weight: 600;
  border-bottom: 3px solid var(--color-primary);
}
@media (min-width: 1024px) {
  .library__tab {
    flex: 0 0 auto;
    padding: 0 var(--space-4);
  }
}
</style>
