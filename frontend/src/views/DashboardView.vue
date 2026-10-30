<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '../api/client'
import { errorText } from '../api/errors'
import BaseAlert from '../components/BaseAlert.vue'
import ProgressBar from '../components/ProgressBar.vue'
import { useJobsStore } from '../stores/jobs'

/** Totales de la biblioteca que muestra el panel. */
interface LibrarySummary {
  artists: number
  albums: number
  tracks: number
  downloaded: number
}

/** Cada cuántos milisegundos se refrescan las tareas mientras el panel está abierto. */
const POLL_MS = 5000

/**
 * Panel: resumen de la biblioteca y tareas en curso. Las tareas se sondean solo
 * mientras la vista está montada.
 *
 * Dashboard: library summary and running jobs. Jobs are polled only while mounted.
 */
const { t, te } = useI18n()
const jobs = useJobsStore()

const summary = ref<LibrarySummary | null>(null)
const summaryError = ref('')
const jobsError = ref('')
let timer: ReturnType<typeof setInterval> | undefined

async function refreshJobs(): Promise<void> {
  try {
    await jobs.refresh()
    jobsError.value = ''
  } catch (e) {
    jobsError.value = errorText(e, t)
  }
}

function kindLabel(kind: string): string {
  return te(`dashboard.jobs.kind.${kind}`) ? t(`dashboard.jobs.kind.${kind}`) : kind
}

onMounted(async () => {
  timer = setInterval(() => void refreshJobs(), POLL_MS)
  try {
    summary.value = await api<LibrarySummary>('/api/v1/catalog/summary/')
  } catch (e) {
    summaryError.value = errorText(e, t)
  }
  await refreshJobs()
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <section class="dashboard">
    <h1>{{ t('dashboard.title') }}</h1>

    <h2>{{ t('dashboard.library') }}</h2>
    <BaseAlert v-if="summaryError" variant="error">{{ summaryError }}</BaseAlert>
    <dl v-if="summary" class="stats">
      <div v-for="key in ['artists', 'albums', 'tracks', 'downloaded'] as const" :key="key">
        <dt>{{ t(`dashboard.summary.${key}`) }}</dt>
        <dd>{{ summary[key] }}</dd>
      </div>
    </dl>

    <h2>{{ t('dashboard.jobs.title') }}</h2>
    <BaseAlert v-if="jobsError" variant="error">{{ jobsError }}</BaseAlert>
    <p v-if="jobs.active.length === 0">{{ t('dashboard.jobs.empty') }}</p>
    <ul v-else class="jobs">
      <li v-for="job in jobs.active" :key="job.id">
        <span>{{ kindLabel(job.kind) }}</span>
        <ProgressBar
          :value="job.progress"
          :label="t('dashboard.jobs.progress', { kind: kindLabel(job.kind) })"
        />
      </li>
    </ul>
  </section>
</template>

<style scoped>
/* Mobile-first: dos columnas de totales en móvil y cuatro desde 600 px. */
.stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
  margin: 0;
}
.stats div {
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
}
dt {
  color: var(--color-muted);
}
dd {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}
.jobs {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (min-width: 600px) {
  .stats {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
