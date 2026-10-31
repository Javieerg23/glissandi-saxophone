<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { type ApiError, api } from '../api/client'
import { errorText } from '../api/errors'
import type { components } from '../api/schema'
import BaseAlert from '../components/BaseAlert.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseField from '../components/BaseField.vue'

type Preference = components['schemas']['Preference']

/** Claves que edita esta vista; el resto de ajustes tendrán su propia vista. */
const KEYS = ['download.format', 'download.folder', 'download.name_template'] as const
type Key = (typeof KEYS)[number]

// Los mismos que `integrations.audio.FORMATS`: la API solo valida el tipo, no el valor.
const FORMATS = ['mp3', 'm4a', 'flac', 'opus']
// Marcadores de `integrations.audio.render_path`; van como parámetro porque vue-i18n
// tomaría las llaves del texto por interpolaciones.
const PLACEHOLDERS = '{artist} {album} {disc} {track} {title} {year}'

/**
 * Ajustes globales de descarga: formato, carpeta y plantilla de nombres. Cada ajuste se
 * guarda con su propio `PUT`, así que el error de validación va a su campo.
 *
 * Global download settings: format, folder and naming template. Each one is saved with
 * its own `PUT`, so a validation error lands on its field.
 */
const { t } = useI18n()

const values = reactive<Record<Key, string>>({
  'download.format': '',
  'download.folder': '',
  'download.name_template': '',
})
const saved = reactive<Partial<Record<Key, string>>>({})
const fieldErrors = reactive<Partial<Record<Key, string>>>({})
const message = ref('')
const error = ref('')

function setAll(entries: Preference[]): void {
  for (const p of entries) {
    if (!(KEYS as readonly string[]).includes(p.key)) continue
    values[p.key as Key] = saved[p.key as Key] = String(p.value)
  }
}

onMounted(async () => {
  try {
    setAll(await api<Preference[]>('/api/v1/preferences/'))
  } catch (e) {
    error.value = errorText(e, t)
  }
})

/** Guarda solo lo que ha cambiado; un fallo en un campo no impide guardar los demás. */
async function save(): Promise<void> {
  message.value = error.value = ''
  for (const key of KEYS) delete fieldErrors[key]
  const changed = KEYS.filter((key) => values[key] !== saved[key])
  const results = await Promise.allSettled(
    changed.map((key) =>
      api<Preference>(`/api/v1/preferences/${key}/`, {
        method: 'PUT',
        body: { value: values[key] },
      }),
    ),
  )
  results.forEach((r, i) => {
    const key = changed[i] as Key
    if (r.status === 'fulfilled') return setAll([r.value])
    // Si no es un `ApiError`, `errorText` lo relanza: es un fallo de programación.
    const body = (r.reason as ApiError).body as { value?: string[] } | null
    if (body?.value) fieldErrors[key] = body.value.join(' ')
    else error.value = errorText(r.reason, t)
  })
  if (results.every((r) => r.status === 'fulfilled')) message.value = t('settings.saved')
}
</script>

<template>
  <section class="settings">
    <h1>{{ t('settings.title') }}</h1>
    <p>
      <RouterLink :to="{ name: 'account' }">{{ t('settings.accountLink') }}</RouterLink>
    </p>
    <BaseAlert v-if="message" variant="success">{{ message }}</BaseAlert>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>

    <form name="settings" @submit.prevent="save">
      <div class="select">
        <label for="settings-format">{{ t('settings.format') }}</label>
        <select
          id="settings-format"
          v-model="values['download.format']"
          :aria-invalid="fieldErrors['download.format'] ? 'true' : undefined"
          :aria-describedby="fieldErrors['download.format'] ? 'settings-format-error' : undefined"
        >
          <option v-for="f in FORMATS" :key="f" :value="f">{{ f }}</option>
        </select>
        <p v-if="fieldErrors['download.format']" id="settings-format-error" class="select__error">
          {{ fieldErrors['download.format'] }}
        </p>
      </div>
      <BaseField
        v-model="values['download.folder']"
        :label="t('settings.folder')"
        :error="fieldErrors['download.folder']"
      />
      <BaseField
        v-model="values['download.name_template']"
        :label="t('settings.template')"
        :error="fieldErrors['download.name_template']"
      />
      <p class="hint">{{ t('settings.templateHint', { placeholders: PLACEHOLDERS }) }}</p>
      <BaseButton type="submit">{{ t('settings.save') }}</BaseButton>
    </form>
  </section>
</template>

<style scoped>
.settings,
form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 32rem;
}
.select select {
  display: block;
  width: 100%;
  min-height: var(--touch-target);
  margin-top: var(--space-1);
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
}
.select select[aria-invalid='true'] {
  border-color: var(--color-danger);
}
.select__error {
  margin: var(--space-1) 0 0;
  color: var(--color-danger);
}
.hint {
  margin: 0;
  color: var(--color-muted);
}
</style>
