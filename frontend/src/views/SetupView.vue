<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { api } from '../api/client'
import { errorText } from '../api/errors'
import BaseAlert from '../components/BaseAlert.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseField from '../components/BaseField.vue'
import { useSessionStore } from '../stores/session'

/**
 * Alta del primer administrador. El servidor la cierra en cuanto existe cualquier
 * usuario, así que si ya no hace falta se vuelve al login.
 *
 * First administrator creation. The server closes it once any user exists, so the
 * view goes back to login when it is no longer needed.
 */
const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()

const username = ref('')
const password = ref('')
const confirm = ref('')
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    const { needed } = await api<{ needed: boolean }>('/api/v1/accounts/setup/')
    if (!needed) await router.replace({ name: 'login' })
  } catch (e) {
    error.value = errorText(e, t)
  }
})

async function submit(): Promise<void> {
  error.value = ''
  if (password.value !== confirm.value) {
    error.value = t('auth.setup.mismatch')
    return
  }
  busy.value = true
  try {
    // El alta abre la sesión en el servidor; «quién soy» la refleja en la store.
    await api('/api/v1/accounts/setup/', {
      method: 'POST',
      body: { username: username.value, password: password.value },
    })
    await session.fetchMe()
    await router.push({ name: 'dashboard' })
  } catch (e) {
    error.value = errorText(e, t)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="auth">
    <h1>{{ t('auth.setup.title') }}</h1>
    <p>{{ t('auth.setup.intro') }}</p>
    <BaseAlert v-if="error" variant="error">{{ error }}</BaseAlert>
    <form @submit.prevent="submit">
      <BaseField v-model="username" :label="t('auth.username')" />
      <BaseField v-model="password" :label="t('auth.password')" type="password" />
      <BaseField v-model="confirm" :label="t('auth.setup.confirm')" type="password" />
      <BaseButton type="submit" :disabled="busy">{{ t('auth.setup.submit') }}</BaseButton>
    </form>
  </main>
</template>

<style scoped>
.auth {
  max-width: 24rem;
  margin: 0 auto;
  padding: var(--space-3);
}
form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
