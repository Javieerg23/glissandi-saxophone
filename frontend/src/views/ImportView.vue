<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { api } from '../api/client'
import { errorText } from '../api/errors'
import type { components } from '../api/schema'
import BaseAlert from '../components/BaseAlert.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseCheckbox from '../components/BaseCheckbox.vue'
import BaseField from '../components/BaseField.vue'
import JobRunPanel from '../components/JobRunPanel.vue'
import { useJobRun } from '../composables/useJobRun'

type DeezerArtist = components['schemas']['DeezerArtist']
type DeezerSearch = components['schemas']['DeezerSearch']

/**
 * Importar: busca artistas en Deezer, deja elegir varios (también de búsquedas distintas)
 * y lanza la tarea `import`, que se sigue en la misma vista.
 *
 * Import: searches Deezer artists, lets the user pick several (across searches too) and
 * starts the `import` job, followed in the same view.
 */
const { t } = useI18n()
const job = useJobRun()
// La vista de carpetas llega en su propio cambio: hasta entonces no hay enlace roto.
const hasFolderImport = useRouter().hasRoute('import-folder')

const query = ref('')
const searched = ref('')
const results = ref<DeezerArtist[]>([])
const searchError = ref('')
const loading = ref(false)
const selected = ref(new Map<number, DeezerArtist>())
const verify = ref(false)

const picked = computed(() => [...selected.value.values()])

// shortcut: solo la primera página de Deezer (`next_index`); basta para dar con un artista
// por su nombre, añadir «cargar más» si alguien lo echa en falta.
async function search(): Promise<void> {
  const q = query.value.trim()
  searched.value = ''
  results.value = []
  searchError.value = ''
  if (!q) return
  loading.value = true
  try {
    const page = await api<DeezerSearch>(
      `/api/v1/catalog/deezer/artists/?q=${encodeURIComponent(q)}`,
    )
    results.value = page.results
    searched.value = q
  } catch (e) {
    searchError.value = errorText(e, t)
  } finally {
    loading.value = false
  }
}

function toggle(artist: DeezerArtist, on: boolean): void {
  if (on) selected.value.set(artist.deezer_id, artist)
  else selected.value.delete(artist.deezer_id)
}

async function start(): Promise<void> {
  const ok = await job.start('import', {
    artist_ids: picked.value.map((a) => a.deezer_id),
    verify: verify.value,
  })
  if (ok) selected.value.clear()
}
</script>

<template>
  <section class="import">
    <h1>{{ t('import.title') }}</h1>
    <RouterLink v-if="hasFolderImport" :to="{ name: 'import-folder' }">
      {{ t('import.folder') }}
    </RouterLink>

    <form class="search" role="search" @submit.prevent="search">
      <BaseField v-model="query" :label="t('import.search.label')" type="search" />
      <BaseButton type="submit" :disabled="loading">{{ t('import.search.submit') }}</BaseButton>
    </form>

    <BaseAlert v-if="searchError" variant="error">{{ searchError }}</BaseAlert>
    <p v-else-if="!searched && !loading">{{ t('import.search.empty') }}</p>
    <p v-else-if="searched && results.length === 0">
      {{ t('import.search.none', { q: searched }) }}
    </p>
    <ul v-if="results.length" class="results" :aria-label="t('import.search.results')">
      <li v-for="a in results" :key="a.deezer_id">
        <label class="artist" :class="{ 'artist--blocked': a.blocked }">
          <input
            type="checkbox"
            :checked="selected.has(a.deezer_id)"
            :disabled="a.blocked"
            @change="toggle(a, ($event.target as HTMLInputElement).checked)"
          />
          <img v-if="a.image_url" :src="a.image_url" alt="" loading="lazy" />
          <span v-else class="artist__placeholder" aria-hidden="true"></span>
          <span class="artist__text">
            <strong>{{ a.name }}</strong>
            <small v-if="a.album_count !== null">
              {{ t('import.artist.albums', { n: a.album_count }, a.album_count) }}
            </small>
            <small v-if="a.blocked" class="artist__tag">{{ t('import.artist.blocked') }}</small>
            <small v-else-if="a.in_catalog" class="artist__tag">
              {{ t('import.artist.inCatalog') }}
            </small>
          </span>
        </label>
      </li>
    </ul>

    <section v-if="picked.length" class="selected">
      <h2>{{ t('import.selected.title', { n: picked.length }) }}</h2>
      <ul>
        <li v-for="a in picked" :key="a.deezer_id">
          <span>{{ a.name }}</span>
          <BaseButton
            variant="secondary"
            :aria-label="t('import.selected.remove', { name: a.name })"
            @click="toggle(a, false)"
          >
            ×
          </BaseButton>
        </li>
      </ul>
    </section>

    <div class="launch">
      <BaseCheckbox v-model="verify" :label="t('import.verify')" />
      <BaseButton :disabled="picked.length === 0 || job.active" @click="start">
        {{ t('import.start', { n: picked.length }, picked.length) }}
      </BaseButton>
    </div>

    <JobRunPanel :job="job" />
  </section>
</template>

<style scoped>
.import {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.search {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
}
.search > :first-child {
  flex: 1;
}
/* Mobile-first: una columna de artistas, dos desde 600 px y tres desde 1024 px. */
.results {
  display: grid;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
.artist {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: var(--touch-target);
  padding: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
  cursor: pointer;
}
.artist:has(input:checked) {
  border-color: var(--color-primary);
}
.artist--blocked {
  cursor: not-allowed;
  opacity: 0.6;
}
.artist input {
  width: 1.25rem;
  height: 1.25rem;
  accent-color: var(--color-primary);
}
.artist img,
.artist__placeholder {
  flex: none;
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  background: var(--color-border);
  object-fit: cover;
}
.artist__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.artist__text small {
  color: var(--color-muted);
}
.artist__tag {
  font-weight: 600;
}
.selected ul {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
.selected li {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding-left: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}
.selected h2 {
  margin-top: 0;
}
.launch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

@media (min-width: 600px) {
  .results {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (min-width: 1024px) {
  .results {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
