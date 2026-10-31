<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '../api/client'
import { errorText } from '../api/errors'
import type { components } from '../api/schema'
import BaseAlert from '../components/BaseAlert.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseCheckbox from '../components/BaseCheckbox.vue'
import FilterPanel from '../components/FilterPanel.vue'
import JobRunPanel from '../components/JobRunPanel.vue'
import ResponsiveList from '../components/ResponsiveList.vue'
import { useJobRun } from '../composables/useJobRun'
import { usePagedList, type Page } from '../composables/usePagedList'

type Track = components['schemas']['Track']
type Artist = components['schemas']['Artist']
type Album = components['schemas']['Album']
type JobRun = components['schemas']['JobRun']

/**
 * Descargar: canciones pendientes con filtros por artista y álbum, para descargar las elegidas
 * o todas. Solo puede haber una descarga a la vez, así que si ya hay una se sigue esa.
 *
 * Download: pending tracks filtered by artist and album, to download the selected ones or all.
 * Only one download can run at a time, so a running one is followed instead.
 */
const { t } = useI18n()
const list = usePagedList<Track>('/api/v1/catalog/tracks/', ['downloaded', 'artist', 'album'])
const job = useJobRun()

// La selección vive fuera de la página: se conserva al pasar de página o cambiar filtros.
const selected = reactive(new Set<number>())
const artists = ref<Artist[]>([])
const albums = ref<Album[]>([])
const error = ref('')
const columns = computed(() => [
  { key: 'title', label: t('download.columns.title') },
  { key: 'artists', label: t('download.columns.artists') },
])

// shortcut: los filtros ofrecen los 200 primeros (el máximo por página de la API); con más,
// pasar a un buscador.
async function options<T>(path: string, query: string): Promise<T[]> {
  try {
    return (await api<Page<T>>(`${path}?page_size=200&${query}`)).results
  } catch (e) {
    error.value = errorText(e, t)
    return []
  }
}

/** Sigue la última descarga si sigue activa; como mucho hay una, es siempre la más reciente. */
async function followActive(): Promise<void> {
  try {
    const [latest] = (await api<Page<JobRun>>('/api/v1/jobs/runs/?kind=download')).results
    if (latest && ['pending', 'running', 'stopping'].includes(latest.status)) {
      await job.follow(latest.id)
    }
  } catch (e) {
    error.value = errorText(e, t)
  }
}

async function launch(params: Record<string, unknown>): Promise<void> {
  // Si falla porque otra acaba de empezar (409), se sigue esa en vez de mostrar el error.
  if (!(await job.start('download', params))) await followActive()
}

function toggle(id: number, on: boolean): void {
  if (on) selected.add(id)
  else selected.delete(id)
}

function setArtist(event: Event): void {
  // Un álbum de otro artista dejaría la lista vacía sin motivo aparente.
  list.update({ artist: (event.target as HTMLSelectElement).value, album: '' })
}

watch(
  () => list.query.artist,
  async (artist) => {
    const filter = artist ? `&artist=${encodeURIComponent(artist)}` : ''
    albums.value = await options<Album>('/api/v1/catalog/albums/', `ordering=title${filter}`)
  },
  { immediate: true },
)

// Al terminar una descarga cambian las pendientes: se recarga y se vacía la selección.
watch(
  () => job.active,
  (now, before) => {
    if (before && !now) {
      selected.clear()
      void list.reload()
    }
  },
)

onMounted(async () => {
  void followActive()
  artists.value = await options<Artist>('/api/v1/catalog/artists/', 'ordering=name')
})
</script>

<template>
  <section class="download">
    <h1>{{ t('download.title') }}</h1>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>

    <FilterPanel>
      <div class="filters">
        <label>
          {{ t('download.filters.artist') }}
          <select :value="list.query.artist ?? ''" @change="setArtist">
            <option value="">{{ t('download.filters.all') }}</option>
            <option v-for="a in artists" :key="a.id" :value="String(a.id)">{{ a.name }}</option>
          </select>
        </label>
        <label>
          {{ t('download.filters.album') }}
          <select
            :value="list.query.album ?? ''"
            @change="list.update({ album: ($event.target as HTMLSelectElement).value })"
          >
            <option value="">{{ t('download.filters.all') }}</option>
            <option v-for="a in albums" :key="a.id" :value="String(a.id)">{{ a.title }}</option>
          </select>
        </label>
      </div>
    </FilterPanel>

    <BaseAlert v-if="job.active" variant="info">{{ t('download.running') }}</BaseAlert>
    <div class="actions">
      <BaseButton
        :disabled="job.active || selected.size === 0"
        @click="launch({ track_ids: [...selected].sort((a, b) => a - b) })"
      >
        {{ t('download.chosen', { count: selected.size }) }}
      </BaseButton>
      <BaseButton
        variant="secondary"
        :disabled="job.active || list.count === 0"
        @click="launch({ all_pending: true })"
      >
        {{ t('download.all') }}
      </BaseButton>
    </div>
    <JobRunPanel :job="job" />

    <BaseAlert v-if="list.error" variant="error">{{ list.error }}</BaseAlert>
    <p>{{ t('download.pending', { count: list.count }) }}</p>
    <ResponsiveList :columns="columns" :rows="list.items" row-key="id">
      <template #cell-title="{ row }">
        <BaseCheckbox
          :label="row.title"
          :model-value="selected.has(row.id)"
          @update:model-value="toggle(row.id, $event)"
        />
      </template>
      <template #cell-artists="{ row }">
        {{ row.artists.map((a) => a.name).join(', ') }}
      </template>
    </ResponsiveList>

    <nav v-if="list.hasPrevious || list.hasNext" class="pages">
      <BaseButton
        variant="secondary"
        :disabled="!list.hasPrevious"
        @click="list.goTo(list.page - 1)"
      >
        {{ t('download.previous') }}
      </BaseButton>
      <span>{{ t('download.page', { page: list.page }) }}</span>
      <BaseButton variant="secondary" :disabled="!list.hasNext" @click="list.goTo(list.page + 1)">
        {{ t('download.next') }}
      </BaseButton>
    </nav>
  </section>
</template>

<style scoped>
.download {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.filters,
.actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.filters label {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
select {
  min-height: var(--touch-target);
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
}
.pages {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

@media (min-width: 600px) {
  .filters,
  .actions {
    flex-direction: row;
  }
}
</style>
