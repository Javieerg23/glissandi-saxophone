<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '../../api/client'
import { errorText } from '../../api/errors'
import BaseAlert from '../../components/BaseAlert.vue'
import BaseButton from '../../components/BaseButton.vue'
import BaseField from '../../components/BaseField.vue'
import type { Page } from '../../composables/usePagedList'
import { type Artist, type Item, apiPath } from './kinds'

/**
 * Cambia los artistas de un álbum o una canción: quitar, reordenar (el primero es el
 * principal) y añadir buscando en el catálogo. Se guarda todo de una vez con `set_artists`.
 *
 * Edits an album's or track's artists: remove, reorder (first is the main one) and add from
 * the catalogue. Saved in one go through `set_artists`.
 */
const props = defineProps<{ artists: { id: number; name: string }[]; path: string }>()
const emit = defineEmits<{ saved: [item: Item] }>()
const { t } = useI18n()

const chosen = ref(props.artists.map(({ id, name }) => ({ id, name })))
const query = ref('')
const found = ref<Artist[]>([])
const error = ref('')

function move(index: number, by: -1 | 1): void {
  const list = chosen.value
  ;[list[index], list[index + by]] = [list[index + by]!, list[index]!]
}

async function search(): Promise<void> {
  error.value = ''
  try {
    const url = `${apiPath('artists')}?search=${encodeURIComponent(query.value)}`
    found.value = (await api<Page<Artist>>(url)).results
  } catch (e) {
    error.value = errorText(e, t)
  }
}

async function save(): Promise<void> {
  error.value = ''
  try {
    const item = await api<Item>(`${props.path}artists/`, {
      method: 'PUT',
      body: { artists: chosen.value.map((a) => a.id) },
    })
    emit('saved', item)
  } catch (e) {
    error.value = errorText(e, t)
  }
}
</script>

<template>
  <section class="artists-editor">
    <h2>{{ t('library.artists.title') }}</h2>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>
    <ol class="artists-editor__chosen">
      <li v-for="(artist, i) in chosen" :key="artist.id">
        <span>{{ artist.name }}</span>
        <BaseButton
          variant="secondary"
          :disabled="i === 0"
          :aria-label="t('library.artists.up', { name: artist.name })"
          @click="move(i, -1)"
          >↑</BaseButton
        >
        <BaseButton
          variant="secondary"
          :disabled="i === chosen.length - 1"
          :aria-label="t('library.artists.down', { name: artist.name })"
          @click="move(i, 1)"
          >↓</BaseButton
        >
        <BaseButton
          variant="secondary"
          :aria-label="t('library.artists.remove', { name: artist.name })"
          @click="chosen.splice(i, 1)"
          >✕</BaseButton
        >
      </li>
    </ol>
    <form class="artists-editor__search" @submit.prevent="search">
      <BaseField v-model="query" type="search" :label="t('library.artists.search')" />
      <BaseButton type="submit" variant="secondary">{{ t('library.artists.find') }}</BaseButton>
    </form>
    <ul v-if="found.length" class="artists-editor__found">
      <li v-for="artist in found" :key="artist.id">
        <span>{{ artist.name }}</span>
        <BaseButton
          variant="secondary"
          :disabled="chosen.some((a) => a.id === artist.id)"
          @click="chosen.push({ id: artist.id, name: artist.name })"
        >
          {{ t('library.artists.add') }}
        </BaseButton>
      </li>
    </ul>
    <BaseButton :disabled="chosen.length === 0" @click="save">
      {{ t('library.artists.save') }}
    </BaseButton>
  </section>
</template>

<style scoped>
.artists-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.artists-editor__chosen,
.artists-editor__found {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
.artists-editor__chosen li,
.artists-editor__found li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.artists-editor__chosen span,
.artists-editor__found span {
  flex: 1;
}
.artists-editor__search {
  display: flex;
  align-items: end;
  gap: var(--space-2);
}
.artists-editor__search > :first-child {
  flex: 1;
}
</style>
