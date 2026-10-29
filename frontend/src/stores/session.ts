import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, api } from '../api/client'

/** Usuario de la sesión tal y como lo devuelve «quién soy». */
export interface User {
  id: number
  username: string
  role: 'administrator' | 'user'
}

/**
 * Sesión del usuario. `loaded` distingue «aún no sé si hay sesión» de «no hay sesión»,
 * para que el router no redirija al login antes de preguntar al servidor.
 *
 * User session. `loaded` tells "not asked yet" apart from "no session".
 */
export const useSessionStore = defineStore('session', () => {
  const user = ref<User | null>(null)
  const loaded = ref(false)
  const isAuthenticated = computed(() => user.value !== null)

  async function fetchMe(): Promise<void> {
    try {
      user.value = await api<User>('/api/v1/accounts/me/')
    } catch (e) {
      // 401/403 solo significan «sin sesión»; cualquier otro fallo sí debe verse.
      if (!(e instanceof ApiError) || (e.kind !== 'unauthorized' && e.kind !== 'forbidden')) throw e
      user.value = null
    } finally {
      loaded.value = true
    }
  }

  async function login(username: string, password: string): Promise<void> {
    user.value = await api<User>('/api/v1/accounts/login/', {
      method: 'POST',
      body: { username, password },
    })
    loaded.value = true
  }

  async function logout(): Promise<void> {
    await api('/api/v1/accounts/logout/', { method: 'POST' })
    user.value = null
  }

  return { user, loaded, isAuthenticated, fetchMe, login, logout }
})
