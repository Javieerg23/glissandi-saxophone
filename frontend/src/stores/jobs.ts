import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '../api/client'

/** Tarea en segundo plano con su estado y progreso (0-100). */
export interface Job {
  id: number
  kind: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  progress: number
}

/**
 * Tareas en segundo plano. El refresco periódico lo decide quien use la store
 * (llamando a `refresh`), para no mantener sondeos abiertos en pantallas que no los necesitan.
 *
 * Background jobs. Whoever uses the store decides when to call `refresh`.
 */
export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref<Job[]>([])
  const active = computed(() =>
    jobs.value.filter((j) => j.status === 'queued' || j.status === 'running'),
  )

  async function refresh(): Promise<void> {
    jobs.value = await api<Job[]>('/api/v1/jobs/')
  }

  return { jobs, active, refresh }
})
