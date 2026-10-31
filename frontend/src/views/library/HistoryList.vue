<script setup lang="ts">
import { nextTick, onMounted, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { api } from '../../api/client'
import { errorText } from '../../api/errors'
import BaseAlert from '../../components/BaseAlert.vue'
import BaseButton from '../../components/BaseButton.vue'
import type { HistoryEntry, Item } from './kinds'

/**
 * Versiones de un elemento, la más reciente primero, con los valores de sus campos
 * editables y, para quien puede escribir, el botón de volver a cada una.
 *
 * An item's versions, newest first, with its editable values and, for writers, a revert button.
 */
const props = defineProps<{ path: string; canRevert: boolean }>()
const emit = defineEmits<{ reverted: [item: Item] }>()
const { t, locale } = useI18n()

const route = useRoute()
const section = useTemplateRef('section')
const entries = ref<HistoryEntry[]>([])
const error = ref('')

async function load(): Promise<void> {
  try {
    entries.value = await api<HistoryEntry[]>(`${props.path}history/`)
    // Sin `scrollBehavior` en el router: se baja al historial cuando el enlace lo pide.
    if (route.hash === '#historial') {
      await nextTick()
      section.value!.scrollIntoView()
    }
  } catch (e) {
    error.value = errorText(e, t)
  }
}

async function revert(entry: HistoryEntry): Promise<void> {
  error.value = ''
  try {
    const item = await api<Item>(`${props.path}revert/`, {
      method: 'POST',
      body: { history_id: entry.history_id },
    })
    emit('reverted', item)
  } catch (e) {
    error.value = errorText(e, t)
  }
}

// Códigos de django-simple-history; uno desconocido se muestra tal cual.
const TYPES: Record<string, string> = { '+': 'created', '~': 'changed', '-': 'deleted' }
const typeLabel = (type: string) =>
  type in TYPES ? t(`library.history.type.${TYPES[type]}`) : type
const show = (value: unknown) => (value === null || value === '' ? '—' : String(value))

onMounted(load)
</script>

<template>
  <section id="historial" ref="section" class="history">
    <h2>{{ t('library.history.title') }}</h2>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>
    <ol class="history__entries">
      <li v-for="entry in entries" :key="entry.history_id" class="history__entry">
        <p class="history__meta">
          {{ new Date(entry.history_date).toLocaleString(locale) }} ·
          {{ typeLabel(entry.history_type) }} ·
          {{ entry.history_user ?? t('library.history.system') }}
        </p>
        <dl>
          <div v-for="(value, field) in entry.changes" :key="field">
            <dt>{{ t(`library.fields.${field}`) }}</dt>
            <dd>{{ show(value) }}</dd>
          </div>
        </dl>
        <BaseButton v-if="canRevert" variant="secondary" @click="revert(entry)">
          {{ t('library.history.revert') }}
        </BaseButton>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.history__entries {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}
.history__entry {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
}
.history__meta {
  margin: 0;
  color: var(--color-muted);
}
.history dl div {
  display: flex;
  gap: var(--space-2);
}
.history dt {
  font-weight: 600;
}
.history dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
