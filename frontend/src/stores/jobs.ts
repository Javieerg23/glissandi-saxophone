import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '../api/client'

/** Ejecución de una tarea en segundo plano, tal y como la devuelve `/api/v1/jobs/runs/`. */
export interface Job {
  id: number
  kind: string
  status: 'pending' | 'running' | 'stopping' | 'stopped' | 'succeeded' | 'failed' | 'interrupted'
  done: number
  total: number
  current: string
}

/** Porcentaje (0-100) de una ejecución; el total es 0 hasta que la tarea sabe cuánto va a hacer. */
export function progressOf(job: Job): number {
  return job.total > 0 ? Math.round((job.done / job.total) * 100) : 0
}

const ACTIVE: ReadonlySet<Job['status']> = new Set(['pending', 'running', 'stopping'])

/**
 * Tareas en segundo plano. El refresco periódico lo decide quien use la store
 * (llamando a `refresh`), para no mantener sondeos abiertos en pantallas que no los necesitan.
 *
 * Background jobs. Whoever uses the store decides when to call `refresh`.
 */
export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref<Job[]>([])
  const active = computed(() => jobs.value.filter((j) => ACTIVE.has(j.status)))

  async function refresh(): Promise<void> {
    // Las más recientes primero; las activas lo son casi siempre, así que basta la primera página.
    jobs.value = (await api<{ results: Job[] }>('/api/v1/jobs/runs/')).results
  }

  return { jobs, active, refresh }
})
