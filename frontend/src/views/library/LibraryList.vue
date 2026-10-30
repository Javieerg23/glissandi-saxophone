<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseAlert from '../../components/BaseAlert.vue'
import BaseButton from '../../components/BaseButton.vue'
import BaseField from '../../components/BaseField.vue'
import FilterPanel from '../../components/FilterPanel.vue'
import ResponsiveList from '../../components/ResponsiveList.vue'
import { usePagedList } from '../../composables/usePagedList'
import { type Credit, type Item, type Kind, SPECS, apiPath, duration, label } from './kinds'

/**
 * Lista de una pestaña de la Biblioteca con búsqueda, filtros y orden de la API. Los filtros
 * por artista o por álbum llegan desde la ficha de cada uno y aquí solo se pueden quitar.
 *
 * One Library tab: paged list with the API's search, filters and ordering. Artist and album
 * filters come from their detail pages and can only be cleared here.
 */
const props = defineProps<{ kind: Kind }>()
const { t } = useI18n()
const spec = SPECS[props.kind]
const list = usePagedList<Item>(apiPath(props.kind), spec.filters)

// Copia editable de los filtros: se aplican al enviar, no con cada tecla.
const form = reactive({
  search: list.query.search ?? '',
  ordering: list.query.ordering ?? '',
  downloaded: list.query.downloaded ?? '',
  released_after: list.query.released_after ?? '',
  released_before: list.query.released_before ?? '',
})

function apply(): void {
  const changes: Record<string, string> = { search: form.search, ordering: form.ordering }
  for (const key of ['downloaded', 'released_after', 'released_before'] as const) {
    if (spec.filters.includes(key)) changes[key] = form[key]
  }
  list.update(changes)
}

/** Filtros por elemento activos (artista o álbum), que no tienen campo en el formulario. */
const scoped = computed(() => (['artist', 'album'] as const).filter((key) => list.query[key]))

const columns = computed(() => {
  const keys = {
    artists: ['name'],
    albums: ['title', 'artists', 'release_date'],
    tracks: ['title', 'artists', 'duration', 'downloaded'],
  }[props.kind]
  return keys.map((key) => ({ key, label: t(`library.fields.${key}`) }))
})

const names = (credits: Credit[]) => credits.map((c) => c.name).join(', ')
const cell = (row: Item, key: string) => (row as Record<string, unknown>)[key]
</script>

<template>
  <div class="library-list">
    <FilterPanel>
      <form class="library-list__filters" @submit.prevent="apply">
        <BaseField v-model="form.search" type="search" :label="t('library.filters.search')" />
        <label class="library-list__select">
          {{ t('library.filters.ordering') }}
          <select v-model="form.ordering">
            <option value="">{{ t('library.ordering.default') }}</option>
            <option v-for="o in spec.orderings" :key="o" :value="o">
              {{ t(`library.ordering.${o.replace(/^-(.*)/, '$1_desc')}`) }}
            </option>
          </select>
        </label>
        <label v-if="spec.filters.includes('downloaded')" class="library-list__select">
          {{ t('library.fields.downloaded') }}
          <select v-model="form.downloaded">
            <option value="">{{ t('library.filters.any') }}</option>
            <option value="true">{{ t('library.yes') }}</option>
            <option value="false">{{ t('library.no') }}</option>
          </select>
        </label>
        <template v-if="spec.filters.includes('released_after')">
          <BaseField
            v-model="form.released_after"
            type="date"
            :label="t('library.filters.released_after')"
          />
          <BaseField
            v-model="form.released_before"
            type="date"
            :label="t('library.filters.released_before')"
          />
        </template>
        <BaseButton type="submit">{{ t('library.filters.apply') }}</BaseButton>
      </form>
    </FilterPanel>

    <p v-for="key in scoped" :key="key" class="library-list__scope">
      {{ t(`library.filters.only_${key}`) }}
      <BaseButton variant="secondary" @click="list.update({ [key]: '' })">
        {{ t('library.filters.clear') }}
      </BaseButton>
    </p>

    <BaseAlert v-if="list.error" variant="error">{{ list.error }}</BaseAlert>
    <p v-if="list.loading" role="status">{{ t('library.loading') }}</p>
    <ResponsiveList :columns="columns" :rows="list.items" row-key="id">
      <template #cell-name="{ row }">
        <RouterLink :to="{ name: 'library-item', params: { kind, id: row.id } }">
          {{ label(row) }}
        </RouterLink>
      </template>
      <template #cell-title="{ row }">
        <RouterLink :to="{ name: 'library-item', params: { kind, id: row.id } }">
          {{ label(row) }}
        </RouterLink>
      </template>
      <template #cell-artists="{ row }">{{ names(cell(row, 'artists') as Credit[]) }}</template>
      <template #cell-duration="{ row }">
        {{ duration(cell(row, 'duration') as number | null) }}
      </template>
      <template #cell-downloaded="{ row }">
        {{ cell(row, 'downloaded') ? t('library.yes') : t('library.no') }}
      </template>
    </ResponsiveList>

    <nav class="library-list__pages" :aria-label="t('library.pages')">
      <BaseButton
        variant="secondary"
        :disabled="!list.hasPrevious"
        @click="list.goTo(list.page - 1)"
      >
        {{ t('library.previous') }}
      </BaseButton>
      <span>{{ t('library.page', { page: list.page, count: list.count }) }}</span>
      <BaseButton variant="secondary" :disabled="!list.hasNext" @click="list.goTo(list.page + 1)">
        {{ t('library.next') }}
      </BaseButton>
    </nav>
  </div>
</template>

<style scoped>
.library-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.library-list__filters {
  display: grid;
  gap: var(--space-3);
}
.library-list__select {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.library-list__select select {
  min-height: var(--touch-target);
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
}
.library-list__scope {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin: 0;
}
.library-list__pages {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

@media (min-width: 600px) {
  .library-list__filters {
    grid-template-columns: repeat(2, 1fr);
    align-items: end;
  }
}

@media (min-width: 1024px) {
  .library-list__filters {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
