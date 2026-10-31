<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { useSessionStore } from '../../stores/session'
import ActivityTab from './ActivityTab.vue'
import JobsTab from './JobsTab.vue'
import TechnicalTab from './TechnicalTab.vue'

/**
 * Registro con tres pestañas: actividad, tareas y logs técnicos (estos solo para
 * administradores). La pestaña y sus filtros viven en la URL.
 *
 * Log section with three tabs: activity, jobs and technical logs (administrators only).
 * The tab and its filters live in the URL.
 */
const { t } = useI18n()
const route = useRoute()
const session = useSessionStore()

const panels = { activity: ActivityTab, jobs: JobsTab, technical: TechnicalTab }
type Tab = keyof typeof panels

const tabs = computed<Tab[]>(() =>
  session.user?.role === 'administrador' ? ['activity', 'jobs', 'technical'] : ['activity', 'jobs'],
)
// Una pestaña desconocida o vedada en la URL cae en Actividad en lugar de dar error.
const tab = computed<Tab>(() => {
  const asked = route.query.tab as Tab
  return tabs.value.includes(asked) ? asked : 'activity'
})
</script>

<template>
  <section class="log">
    <h1>{{ t('log.title') }}</h1>
    <nav class="tabs" :aria-label="t('log.tabs.label')">
      <!-- Solo cambia la query: RouterLink marcaría todas como activas, así que se marca a mano. -->
      <RouterLink
        v-for="name in tabs"
        :key="name"
        :to="{ query: { tab: name } }"
        :aria-current="name === tab ? 'page' : undefined"
        replace
      >
        {{ t(`log.tabs.${name}`) }}
      </RouterLink>
    </nav>
    <component :is="panels[tab]" :key="tab" />
  </section>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
  overflow-x: auto;
  border-bottom: 1px solid var(--color-border);
}
.tabs a {
  display: flex;
  align-items: center;
  min-height: var(--touch-target);
  padding: 0 var(--space-3);
  color: var(--color-muted);
  text-decoration: none;
  white-space: nowrap;
}
.tabs a[aria-current='page'] {
  border-bottom: 2px solid var(--color-primary);
  color: var(--color-text);
  font-weight: 600;
}
</style>
