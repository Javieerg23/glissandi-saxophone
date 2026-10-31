<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { type ApiError, api } from '../../api/client'
import { errorText } from '../../api/errors'
import BaseAlert from '../../components/BaseAlert.vue'
import BaseButton from '../../components/BaseButton.vue'
import BaseDialog from '../../components/BaseDialog.vue'
import BaseField from '../../components/BaseField.vue'
import { useSessionStore } from '../../stores/session'
import ArtistsEditor from './ArtistsEditor.vue'
import HistoryList from './HistoryList.vue'
import { type Item, type Kind, SPECS, apiPath, duration, label } from './kinds'

/**
 * Ficha de un artista, álbum o canción: datos, enlaces a lo relacionado, historial y, para
 * administradores, edición, cambio de artistas, reversión y bloqueo. Ocultar los botones es
 * solo comodidad: quien protege los datos es el permiso de cada endpoint.
 *
 * Artist, album or track page: data, related links, history and, for admins, editing,
 * artist changes, revert and blocking. Hiding the buttons is a courtesy; the API enforces it.
 */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const session = useSessionStore()

// De una ficha a otra (de una canción a su álbum) el router reutiliza este componente.
const kind = ref(route.params.kind as Kind)
const id = ref(route.params.id as string)
const spec = computed(() => SPECS[kind.value])
const path = computed(() => apiPath(kind.value, id.value))
const canWrite = computed(() => session.user?.role === 'administrador')

const item = ref<Item | null>(null)
// Cambia con cada guardado para volver a montar el historial y el editor de artistas.
const version = ref(0)
const draft = ref<Record<string, string>>({})
const fieldErrors = ref<Record<string, string>>({})
const error = ref('')
const message = ref('')
const confirmBlock = ref(false)

const record = computed(() => item.value as Record<string, unknown> | null)

function show(next: Item, notice = ''): void {
  item.value = next
  const values = next as Record<string, unknown>
  draft.value = Object.fromEntries(
    Object.keys(spec.value.editable).map((name) => [name, String(values[name] ?? '')]),
  )
  fieldErrors.value = {}
  error.value = ''
  message.value = notice
  version.value++
}

async function load(): Promise<void> {
  item.value = null
  message.value = error.value = ''
  try {
    show(await api<Item>(path.value))
  } catch (e) {
    error.value = errorText(e, t)
  }
}

async function save(): Promise<void> {
  // Los números y las fechas vacías no son texto para la API.
  const body = Object.fromEntries(
    Object.entries(spec.value.editable).map(([name, type]) => {
      const value = draft.value[name]!
      if (type === 'number') return [name, Number(value)]
      if (type === 'date') return [name, value || null]
      return [name, value]
    }),
  )
  try {
    show(await api<Item>(path.value, { method: 'PATCH', body }), t('library.edit.done'))
  } catch (e) {
    // `errorText` relanza lo que no es un error de la API. / Rethrows non-API errors.
    const text = errorText(e, t)
    const fields = ((e as ApiError).body ?? {}) as Record<string, string[]>
    const own = Object.keys(fields).filter((name) => name in spec.value.editable)
    message.value = ''
    fieldErrors.value = Object.fromEntries(own.map((name) => [name, fields[name]!.join(' ')]))
    // Si el fallo es de los campos, ya se ve junto a cada uno.
    error.value = own.length ? '' : text
  }
}

async function block(): Promise<void> {
  confirmBlock.value = false
  message.value = ''
  error.value = ''
  try {
    await api('/api/v1/catalog/blocked/', {
      method: 'POST',
      body: {
        kind: spec.value.blockKind,
        deezer_id: item.value!.deezer_id,
        name: label(item.value!),
      },
    })
    message.value = t('library.block.done')
  } catch (e) {
    error.value = errorText(e, t)
  }
}

// Al salir hacia otra ruta los parámetros se vacían y la ficha aún está montada: se ignora.
watch(
  () => route.params,
  (params) => {
    if (route.name !== 'library-item') return
    kind.value = params.kind as Kind
    id.value = params.id as string
    void load()
  },
)
void load()
</script>

<template>
  <section class="item">
    <RouterLink :to="{ name: 'library', query: { tab: kind } }">
      {{ t('library.back') }}
    </RouterLink>
    <BaseAlert v-if="message" variant="success">{{ message }}</BaseAlert>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>

    <template v-if="item && record">
      <h1>{{ label(item) }}</h1>
      <img
        v-if="record.image_url || record.cover_url"
        class="item__image"
        :src="String(record.image_url || record.cover_url)"
        alt=""
      />
      <dl class="item__data">
        <div v-if="'artists' in item && item.artists.length">
          <dt>{{ t('library.fields.artists') }}</dt>
          <dd>
            <template v-for="(artist, i) in item.artists" :key="artist.id">
              <span v-if="i > 0">, </span>
              <RouterLink
                :to="{ name: 'library-item', params: { kind: 'artists', id: artist.id } }"
              >
                {{ artist.name }}
              </RouterLink>
            </template>
          </dd>
        </div>
        <div v-if="'album' in item">
          <dt>{{ t('library.fields.album') }}</dt>
          <dd>
            <RouterLink :to="{ name: 'library-item', params: { kind: 'albums', id: item.album } }">
              {{ t('library.links.album') }}
            </RouterLink>
          </dd>
        </div>
        <div v-if="'release_date' in item && item.release_date">
          <dt>{{ t('library.fields.release_date') }}</dt>
          <dd>{{ item.release_date }}</dd>
        </div>
        <template v-if="'downloaded' in item">
          <div>
            <dt>{{ t('library.fields.track_number') }}</dt>
            <dd>{{ item.disc_number }}-{{ item.track_number }}</dd>
          </div>
          <div v-if="item.duration !== null">
            <dt>{{ t('library.fields.duration') }}</dt>
            <dd>{{ duration(item.duration) }}</dd>
          </div>
          <div v-if="item.isrc">
            <dt>{{ t('library.fields.isrc') }}</dt>
            <dd>{{ item.isrc }}</dd>
          </div>
          <div>
            <dt>{{ t('library.fields.downloaded') }}</dt>
            <dd class="item__downloaded" :class="{ 'is-yes': item.downloaded }">
              {{ item.downloaded ? t('library.yes') : t('library.no') }}
            </dd>
          </div>
        </template>
        <div v-if="item.deezer_id !== null">
          <dt>{{ t('library.fields.deezer_id') }}</dt>
          <dd>{{ item.deezer_id }}</dd>
        </div>
        <div v-if="item.musicbrainz_id">
          <dt>{{ t('library.fields.musicbrainz_id') }}</dt>
          <dd>{{ item.musicbrainz_id }}</dd>
        </div>
      </dl>

      <nav class="item__links" :aria-label="t('library.links.title')">
        <RouterLink
          v-if="kind === 'artists'"
          :to="{ name: 'library', query: { tab: 'albums', artist: item.id } }"
        >
          {{ t('library.links.albums') }}
        </RouterLink>
        <RouterLink
          v-if="kind !== 'tracks'"
          :to="{ name: 'library', query: { tab: 'tracks', [kind.slice(0, -1)]: item.id } }"
        >
          {{ t('library.links.tracks') }}
        </RouterLink>
        <!-- La subida de audio es otra vista: el enlace aparece cuando esa ruta existe. -->
        <RouterLink
          v-if="kind === 'tracks' && router.hasRoute('track-upload')"
          :to="{ name: 'track-upload', params: { id: item.id } }"
        >
          {{ t('library.links.upload') }}
        </RouterLink>
      </nav>

      <template v-if="canWrite">
        <form class="item__edit" @submit.prevent="save">
          <h2>{{ t('library.edit.title') }}</h2>
          <BaseField
            v-for="(type, name) in spec.editable"
            :key="name"
            v-model="draft[name]"
            :type="type"
            :label="t(`library.fields.${name}`)"
            :error="fieldErrors[name]"
          />
          <BaseButton type="submit">{{ t('library.edit.save') }}</BaseButton>
        </form>

        <ArtistsEditor
          v-if="'artists' in item"
          :key="`artists-${version}`"
          :artists="item.artists"
          :path="path"
          @saved="show($event, t('library.artists.done'))"
        />

        <div v-if="spec.blockKind && item.deezer_id !== null">
          <BaseButton variant="danger" @click="confirmBlock = true">
            {{ t('library.block.action') }}
          </BaseButton>
          <BaseDialog v-model="confirmBlock" :title="t('library.block.title')">
            <p>{{ t(`library.block.confirm.${kind}`, { name: label(item) }) }}</p>
            <BaseButton variant="danger" @click="block">{{ t('library.block.action') }}</BaseButton>
          </BaseDialog>
        </div>
      </template>

      <HistoryList
        :key="`history-${version}`"
        :path="path"
        :can-revert="canWrite"
        @reverted="show($event, t('library.history.done'))"
      />
    </template>
  </section>
</template>

<style scoped>
.item,
.item__edit {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 48rem;
}
.item__image {
  width: min(16rem, 100%);
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: var(--radius);
}
.item__data {
  display: grid;
  gap: var(--space-2);
  margin: 0;
}
.item__data div {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.item__data dt {
  font-weight: 600;
}
.item__data dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.item__downloaded {
  color: var(--color-muted);
}
.item__downloaded.is-yes {
  color: var(--color-success);
}
.item__links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.item__links a {
  display: inline-flex;
  align-items: center;
  min-height: var(--touch-target);
}
</style>
