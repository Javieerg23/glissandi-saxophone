import { computed, onScopeDispose, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '../api/client'
import { errorText } from '../api/errors'
import type { components } from '../api/schema'

type JobRun = components['schemas']['JobRun']
type JobRunLine = components['schemas']['JobRunLine']

const BASE = '/api/v1/jobs/runs/'
const ACTIVE: ReadonlySet<JobRun['status']> = new Set(['pending', 'running', 'stopping'])

/** Cada cuántos milisegundos se pregunta por una tarea activa. */
export const POLL_MS = 2000

/**
 * Lanza o sigue una tarea en segundo plano: estado, progreso y líneas nuevas (`lines/?after=`)
 * mientras esté activa. El sondeo se para al cerrarse la tarea o al desmontar la vista.
 *
 * Starts or follows a background job: status, progress and new log lines while it is active.
 * Polling stops when the job closes or the owning view unmounts.
 */
export function useJobRun() {
  const { t } = useI18n()
  const run = ref<JobRun | null>(null)
  const lines = ref<JobRunLine[]>([])
  const error = ref('')
  const active = computed(() => run.value !== null && ACTIVE.has(run.value.status))

  let timer: ReturnType<typeof setTimeout> | undefined
  // Cada tarea seguida tiene su generación: un sondeo en vuelo de la anterior se descarta.
  let generation = 0

  function track(fresh: JobRun): void {
    clearTimeout(timer)
    generation += 1
    run.value = fresh
    lines.value = []
    void poll(generation)
  }

  async function poll(gen: number): Promise<void> {
    const id = (run.value as JobRun).id
    try {
      // Primero el estado y luego las líneas: si ya estaba cerrada, las líneas están completas.
      const fresh = await api<JobRun>(`${BASE}${id}/`)
      let batch: JobRunLine[]
      do {
        // `lines/` responde con una lista sin paginar (con un máximo por petición).
        batch = await api<JobRunLine[]>(
          `${BASE}${id}/lines/?after=${lines.value.at(-1)?.position ?? 0}`,
        )
        if (gen !== generation) return
        lines.value.push(...batch)
      } while (!ACTIVE.has(fresh.status) && batch.length > 0)
      run.value = fresh
      error.value = ''
    } catch (e) {
      if (gen !== generation) return
      error.value = errorText(e, t)
    }
    // Tras un fallo se sigue preguntando: suele ser un corte de red pasajero.
    if (error.value || active.value) timer = setTimeout(() => void poll(gen), POLL_MS)
  }

  /** Lanza una tarea; devuelve `false` (con `error` puesto) si la API la rechaza. */
  async function start(kind: string, params: Record<string, unknown> = {}): Promise<boolean> {
    error.value = ''
    try {
      track(await api<JobRun>(BASE, { method: 'POST', body: { kind, params } }))
      return true
    } catch (e) {
      error.value = errorText(e, t)
      return false
    }
  }

  /** Sigue una ejecución que ya existe. */
  async function follow(id: number): Promise<void> {
    error.value = ''
    try {
      track(await api<JobRun>(`${BASE}${id}/`))
    } catch (e) {
      error.value = errorText(e, t)
    }
  }

  /** Pide detenerla; el sondeo sigue hasta que la tarea se cierra de verdad. */
  async function stop(): Promise<void> {
    if (!run.value) return
    try {
      run.value = await api<JobRun>(`${BASE}${run.value.id}/stop/`, { method: 'POST' })
    } catch (e) {
      error.value = errorText(e, t)
    }
  }

  onScopeDispose(() => {
    generation += 1
    clearTimeout(timer)
  })

  return reactive({ run, lines, error, active, start, follow, stop })
}

/** Lo que devuelve `useJobRun`, para pasarlo a `JobRunPanel`. */
export type JobRunHandle = ReturnType<typeof useJobRun>
