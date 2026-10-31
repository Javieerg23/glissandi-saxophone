<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { type ApiError, api } from '../api/client'
import { errorText } from '../api/errors'
import type { components } from '../api/schema'
import BaseAlert from '../components/BaseAlert.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseField from '../components/BaseField.vue'
import ResponsiveList from '../components/ResponsiveList.vue'
import { useSessionStore } from '../stores/session'

type ManagedUser = components['schemas']['ManagedUser']
type Role = components['schemas']['RoleEnum']

const ROLES: Role[] = ['usuario', 'administrador']

/**
 * Gestión de usuarios: listar, dar de alta con su rol, cambiar de rol y desactivar o
 * reactivar. No hay borrado: la API solo desactiva, para no perder su historial.
 *
 * User management: list, create with a role, change role and deactivate or reactivate.
 * There is no delete: the API only deactivates, so their history is kept.
 */
const { t, locale } = useI18n()
const session = useSessionStore()

const users = ref<ManagedUser[]>([])
const form = reactive({ username: '', password: '', role: 'usuario' as Role })
const formErrors = ref<{ username?: string; password?: string }>({})
const message = ref('')
const error = ref('')

const columns = computed(() => [
  { key: 'username', label: t('users.columns.username') },
  { key: 'role', label: t('users.columns.role') },
  { key: 'last_login', label: t('users.columns.lastLogin') },
  { key: 'actions', label: t('users.columns.actions') },
])

async function load(): Promise<void> {
  try {
    users.value = await api<ManagedUser[]>('/api/v1/accounts/users/')
  } catch (e) {
    error.value = errorText(e, t)
  }
}

onMounted(load)

async function create(): Promise<void> {
  message.value = error.value = ''
  formErrors.value = {}
  try {
    const user = await api<ManagedUser>('/api/v1/accounts/users/', { method: 'POST', body: form })
    users.value = [...users.value, user].sort((a, b) => a.username.localeCompare(b.username))
    message.value = t('users.created', { username: user.username })
    Object.assign(form, { username: '', password: '', role: 'usuario' })
  } catch (e) {
    // Errores de DRF por campo (`{ campo: [mensajes] }`); el resto va al aviso general.
    const body = (e as ApiError).body as { username?: string[]; password?: string[] } | null
    if (body?.username || body?.password)
      formErrors.value = { username: body.username?.join(' '), password: body.password?.join(' ') }
    else error.value = errorText(e, t)
  }
}

async function update(
  user: ManagedUser,
  changes: { role?: Role; is_active?: boolean },
): Promise<void> {
  message.value = error.value = ''
  try {
    const updated = await api<ManagedUser>(`/api/v1/accounts/users/${user.id}/`, {
      method: 'PATCH',
      body: changes,
    })
    users.value = users.value.map((u) => (u.id === updated.id ? updated : u))
    message.value = t('users.updated', { username: updated.username })
  } catch (e) {
    error.value = errorText(e, t)
    // El selector ya muestra el rol pedido: se vuelve a leer para que refleje el real.
    await load()
  }
}

function onRole(user: ManagedUser, event: Event): void {
  void update(user, { role: (event.target as HTMLSelectElement).value as Role })
}
</script>

<template>
  <section class="users">
    <h1>{{ t('users.title') }}</h1>
    <BaseAlert v-if="message" variant="success">{{ message }}</BaseAlert>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>

    <ResponsiveList :columns="columns" :rows="users" row-key="id">
      <template #cell-username="{ row }">
        {{ row.username }}
        <span v-if="row.is_active === false" class="inactive">{{ t('users.inactive') }}</span>
      </template>
      <template #cell-role="{ row }">
        <select
          :value="row.role"
          :aria-label="t('users.roleOf', { username: row.username })"
          :disabled="row.username === session.user?.username"
          @change="onRole(row, $event)"
        >
          <option v-for="r in ROLES" :key="r" :value="r">{{ t(`account.role.${r}`) }}</option>
        </select>
      </template>
      <template #cell-last_login="{ row }">
        {{ row.last_login ? new Date(row.last_login).toLocaleString(locale) : t('users.never') }}
      </template>
      <template #cell-actions="{ row }">
        <BaseButton
          v-if="row.username !== session.user?.username"
          :variant="row.is_active === false ? 'secondary' : 'danger'"
          @click="update(row, { is_active: row.is_active === false })"
        >
          {{ t(row.is_active === false ? 'users.activate' : 'users.deactivate') }}
        </BaseButton>
      </template>
    </ResponsiveList>

    <form name="create" @submit.prevent="create">
      <h2>{{ t('users.new.title') }}</h2>
      <BaseField
        v-model="form.username"
        :label="t('users.new.username')"
        :error="formErrors.username"
      />
      <BaseField
        v-model="form.password"
        :label="t('users.new.password')"
        type="password"
        :error="formErrors.password"
      />
      <div class="select">
        <label for="users-new-role">{{ t('users.new.role') }}</label>
        <select id="users-new-role" v-model="form.role">
          <option v-for="r in ROLES" :key="r" :value="r">{{ t(`account.role.${r}`) }}</option>
        </select>
      </div>
      <BaseButton type="submit">{{ t('users.new.submit') }}</BaseButton>
    </form>
  </section>
</template>

<style scoped>
.users {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 32rem;
}
select {
  display: block;
  min-height: var(--touch-target);
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
}
.select select {
  width: 100%;
  margin-top: var(--space-1);
}
.inactive {
  margin-left: var(--space-1);
  color: var(--color-muted);
}
</style>
