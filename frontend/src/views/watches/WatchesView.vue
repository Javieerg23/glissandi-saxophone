<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { components } from '../../api/schema'
import BaseAlert from '../../components/BaseAlert.vue'
import BaseButton from '../../components/BaseButton.vue'
import ResponsiveList from '../../components/ResponsiveList.vue'
import { usePagedList } from '../../composables/usePagedList'

type Watch = components['schemas']['Watch']

/**
 * Lista de búsquedas de novedades con su estado; cada una lleva a su detalle.
 *
 * List of new-release watches with their status; each one opens its detail.
 */
const { t } = useI18n()
const list = usePagedList<Watch>('/api/v1/watches/')

/** Estado de una búsqueda: activa o pausada y, si la tiene, la descarga automática. */
const status = (w: Watch) => [
  t(w.enabled ? 'watches.enabled' : 'watches.disabled'),
  ...(w.auto_download ? [t('watches.autoDownload')] : []),
]

const columns = [
  { key: 'name', label: t('watches.columns.name') },
  { key: 'artists', label: t('watches.columns.artists') },
  { key: 'interval_hours', label: t('watches.columns.interval') },
  { key: 'enabled', label: t('watches.columns.state') },
]
</script>

<template>
  <section class="watches">
    <header class="watches__head">
      <h1>{{ t('watches.title') }}</h1>
      <RouterLink class="watches__new" :to="{ name: 'watches-new' }">
        {{ t('watches.new') }}
      </RouterLink>
    </header>
    <p>{{ t('watches.intro') }}</p>
    <BaseAlert v-if="list.error" variant="error">{{ list.error }}</BaseAlert>
    <ResponsiveList v-if="!list.loading" :columns="columns" :rows="list.items" row-key="id">
      <template #cell-name="{ row }">
        <RouterLink :to="{ name: 'watch', params: { id: row.id } }">{{ row.name }}</RouterLink>
      </template>
      <template #cell-artists="{ row }">
        {{ row.artists.map((a) => a.name).join(', ') }}
      </template>
      <template #cell-interval_hours="{ row }">
        {{ t('watches.hours', { n: row.interval_hours }, Number(row.interval_hours)) }}
      </template>
      <template #cell-enabled="{ row }">
        {{ status(row).join(' · ') }}
      </template>
    </ResponsiveList>
    <nav v-if="list.hasPrevious || list.hasNext" class="watches__pages">
      <BaseButton
        variant="secondary"
        :disabled="!list.hasPrevious"
        @click="list.goTo(list.page - 1)"
      >
        {{ t('watches.previous') }}
      </BaseButton>
      <BaseButton variant="secondary" :disabled="!list.hasNext" @click="list.goTo(list.page + 1)">
        {{ t('watches.next') }}
      </BaseButton>
    </nav>
  </section>
</template>

<style scoped>
.watches {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.watches__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.watches__new {
  display: inline-flex;
  align-items: center;
  min-height: var(--touch-target);
  padding: 0 var(--space-3);
  border-radius: var(--radius);
  background: var(--color-primary);
  color: var(--color-primary-contrast);
  text-decoration: none;
}
.watches__pages {
  display: flex;
  justify-content: space-between;
}
</style>
