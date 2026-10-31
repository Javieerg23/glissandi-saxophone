<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { api, type ApiError } from '../api/client'
import { errorText } from '../api/errors'
import type { components } from '../api/schema'
import BaseAlert from '../components/BaseAlert.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseCheckbox from '../components/BaseCheckbox.vue'
import BaseDialog from '../components/BaseDialog.vue'
import BaseField from '../components/BaseField.vue'
import ResponsiveList from '../components/ResponsiveList.vue'

type Proxy = components['schemas']['Proxy']
type ProxyCheck = components['schemas']['ProxyCheck']

const BASE = '/api/v1/proxies/'

/**
 * Proxies de salida (solo administradores): lista con estado y contadores, alta, edición,
 * activar o desactivar, borrado con confirmación y prueba de conexión.
 *
 * Outbound proxies (administrators only): list with status and counters, create, edit,
 * enable or disable, delete with confirmation and connection test.
 */
const { t, locale } = useI18n()

const proxies = ref<Proxy[]>([])
const message = ref('')
const error = ref('')

const columns = computed(() => [
  { key: 'url', label: t('proxies.columns.url') },
  { key: 'enabled', label: t('proxies.columns.status') },
  { key: 'success_count', label: t('proxies.columns.success') },
  { key: 'failure_count', label: t('proxies.columns.failure') },
  { key: 'last_used_at', label: t('proxies.columns.lastUsed') },
  { key: 'actions', label: t('proxies.columns.actions') },
])

// Formulario de alta y edición: `editing` es null al crear.
const formOpen = ref(false)
const editing = ref<Proxy | null>(null)
const url = ref('')
const enabled = ref(true)
const urlError = ref('')
const formError = ref('')

const toDelete = ref<Proxy | null>(null)
const deleteOpen = ref(false)

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString(locale.value) : t('proxies.never')
}

/** Ejecuta una acción mostrando su éxito o su error, nunca los dos. */
async function run(action: () => Promise<string>): Promise<void> {
  message.value = ''
  error.value = ''
  try {
    message.value = await action()
  } catch (e) {
    error.value = errorText(e, t)
  }
}

const load = () =>
  run(async () => {
    proxies.value = await api<Proxy[]>(BASE)
    return ''
  })

function openForm(proxy: Proxy | null): void {
  editing.value = proxy
  url.value = proxy?.url ?? ''
  enabled.value = proxy?.enabled ?? true
  urlError.value = formError.value = ''
  formOpen.value = true
}

async function save(): Promise<void> {
  urlError.value = formError.value = ''
  const proxy = editing.value
  const body = { url: url.value, enabled: enabled.value }
  try {
    await (proxy
      ? api(`${BASE}${proxy.id}/`, { method: 'PATCH', body })
      : api(BASE, { method: 'POST', body }))
  } catch (e) {
    // `errorText` relanza lo que no es de la API. El error de la dirección va junto a su
    // campo; cualquier otro, arriba del formulario.
    const text = errorText(e, t)
    const field = ((e as ApiError).body as { url?: string[] } | null)?.url
    if (field) urlError.value = field.join(' ')
    else formError.value = text
    return
  }
  formOpen.value = false
  await load()
  message.value = t(proxy ? 'proxies.done.updated' : 'proxies.done.created')
}

const toggle = (proxy: Proxy) =>
  run(async () => {
    const saved = await api<Proxy>(`${BASE}${proxy.id}/`, {
      method: 'PATCH',
      body: { enabled: !proxy.enabled },
    })
    proxies.value = proxies.value.map((p) => (p.id === saved.id ? saved : p))
    return t('proxies.done.updated')
  })

function askDelete(proxy: Proxy): void {
  toDelete.value = proxy
  deleteOpen.value = true
}

const confirmDelete = () =>
  run(async () => {
    const proxy = toDelete.value as Proxy
    deleteOpen.value = false
    await api(`${BASE}${proxy.id}/`, { method: 'DELETE' })
    proxies.value = proxies.value.filter((p) => p.id !== proxy.id)
    return t('proxies.done.deleted')
  })

const check = (proxy: Proxy) =>
  run(async () => {
    const result = await api<ProxyCheck>(`${BASE}${proxy.id}/check/`, { method: 'POST' })
    const params = { url: proxy.url, status: result.status_code }
    if (result.ok) return t('proxies.check.ok', params)
    // La API responde bien aunque el proxy falle: el fallo se avisa como error, sin éxito.
    error.value = t(
      result.status_code === null ? 'proxies.check.failed' : 'proxies.check.failedStatus',
      params,
    )
    return ''
  })

onMounted(load)
</script>

<template>
  <section class="proxies">
    <h1>{{ t('proxies.title') }}</h1>
    <p>{{ t('proxies.intro') }}</p>
    <BaseAlert v-if="message" variant="success">{{ message }}</BaseAlert>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>

    <div>
      <BaseButton @click="openForm(null)">{{ t('proxies.add') }}</BaseButton>
    </div>

    <ResponsiveList :columns="columns" :rows="proxies" row-key="id">
      <template #cell-url="{ row }">
        <span class="proxies__url">{{ row.url }}</span>
      </template>
      <template #cell-enabled="{ row }">
        {{ t(row.enabled ? 'proxies.status.enabled' : 'proxies.status.disabled') }}
      </template>
      <template #cell-last_used_at="{ row }">{{ when(row.last_used_at) }}</template>
      <template #cell-actions="{ row }">
        <div class="proxies__actions">
          <BaseButton variant="secondary" @click="openForm(row)">
            {{ t('proxies.actions.edit') }}
          </BaseButton>
          <BaseButton variant="secondary" @click="toggle(row)">
            {{ t(row.enabled ? 'proxies.actions.disable' : 'proxies.actions.enable') }}
          </BaseButton>
          <BaseButton variant="secondary" @click="check(row)">
            {{ t('proxies.actions.check') }}
          </BaseButton>
          <BaseButton variant="danger" @click="askDelete(row)">
            {{ t('proxies.actions.delete') }}
          </BaseButton>
        </div>
      </template>
    </ResponsiveList>

    <BaseDialog
      v-model="formOpen"
      :title="t(editing ? 'proxies.form.editTitle' : 'proxies.form.createTitle')"
    >
      <form name="proxy" class="proxies__form" @submit.prevent="save">
        <BaseAlert v-if="formError" variant="error">{{ formError }}</BaseAlert>
        <BaseField v-model="url" :label="t('proxies.form.url')" type="url" :error="urlError" />
        <BaseCheckbox v-model="enabled" :label="t('proxies.form.enabled')" />
        <BaseButton type="submit">{{ t('proxies.form.save') }}</BaseButton>
      </form>
    </BaseDialog>

    <BaseDialog v-model="deleteOpen" :title="t('proxies.delete.title')">
      <p>{{ t('proxies.delete.confirm', { url: toDelete?.url }) }}</p>
      <BaseButton variant="danger" @click="confirmDelete">
        {{ t('proxies.delete.submit') }}
      </BaseButton>
    </BaseDialog>
  </section>
</template>

<style scoped>
.proxies {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.proxies__url {
  overflow-wrap: anywhere;
}
.proxies__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.proxies__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
