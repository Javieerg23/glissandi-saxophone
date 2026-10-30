<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { navEntries } from '../components/nav-meta'
import { useSessionStore } from '../stores/session'

/**
 * «Más»: en móvil, las secciones que no caben en la barra inferior.
 *
 * "More": on mobile, the sections that do not fit in the bottom bar.
 */
const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()
const entries = computed(
  () => navEntries(router.getRoutes(), session.user?.role === 'administrador').more,
)
</script>

<template>
  <section>
    <h1>{{ t('nav.more') }}</h1>
    <ul class="more">
      <li v-for="r in entries" :key="r.name?.toString() ?? r.path">
        <RouterLink :to="r.path">{{ t(r.meta.navLabel as string) }}</RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.more {
  margin: 0;
  padding: 0;
  list-style: none;
}
li + li {
  border-top: 1px solid var(--color-border);
}
a {
  display: flex;
  align-items: center;
  min-height: var(--touch-target);
  color: var(--color-text);
  text-decoration: none;
}
</style>
