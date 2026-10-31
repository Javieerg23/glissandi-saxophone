<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import BaseButton from '../components/BaseButton.vue'
import BaseCheckbox from '../components/BaseCheckbox.vue'
import JobRunPanel from '../components/JobRunPanel.vue'
import { useJobRun } from '../composables/useJobRun'

/** Resumen de la tarea `maintenance`: una entrada por operación hecha. */
interface Summary {
  retag?: { retagged: number; failed: number }
  check_files?: { checked: number; missing: number[] }
  review_artists?: { reviewed: number; differences: number; errors: number }
}

// Mismo orden en que las ejecuta el backend.
const OPERATIONS = ['retag', 'check_files', 'review_artists'] as const

/**
 * Utilidades de mantenimiento: elegir operaciones, lanzar la tarea `maintenance`, seguirla y
 * ver su resumen final.
 *
 * Maintenance utilities: pick operations, start the `maintenance` job, follow it and show
 * its final summary.
 */
const { t } = useI18n()
const job = useJobRun()
const chosen = reactive(Object.fromEntries(OPERATIONS.map((op) => [op, true])))
const operations = computed(() => OPERATIONS.filter((op) => chosen[op]))
// La copia de la biblioteca es otra vista; el enlace aparece cuando su ruta esté registrada.
const hasBackup = useRouter().hasRoute('library-backup')

const summary = computed(() => {
  const value = job.run && !job.active ? (job.run.summary as Summary) : {}
  return Object.keys(value).length ? value : null
})

const start = () => job.start('maintenance', { operations: operations.value })
</script>

<template>
  <section class="utilities">
    <h1>{{ t('utilities.title') }}</h1>
    <p>{{ t('utilities.intro') }}</p>

    <fieldset>
      <legend>{{ t('utilities.operations') }}</legend>
      <BaseCheckbox
        v-for="op in OPERATIONS"
        :key="op"
        v-model="chosen[op]"
        :label="t(`utilities.operation.${op}`)"
      />
    </fieldset>
    <BaseButton :disabled="!operations.length || job.active" @click="start">
      {{ t('utilities.start') }}
    </BaseButton>

    <JobRunPanel :job="job" />

    <section v-if="summary" class="summary">
      <h2>{{ t('utilities.summary.title') }}</h2>
      <ul>
        <li v-if="summary.retag">{{ t('utilities.summary.retag', summary.retag) }}</li>
        <template v-if="summary.check_files">
          <li>
            {{
              t('utilities.summary.check_files', {
                checked: summary.check_files.checked,
                missing: summary.check_files.missing.length,
              })
            }}
          </li>
          <li v-if="summary.check_files.missing.length">
            {{
              t('utilities.summary.missing', {
                ids: summary.check_files.missing.map((id) => `#${id}`).join(', '),
              })
            }}
          </li>
        </template>
        <li v-if="summary.review_artists">
          {{ t('utilities.summary.review_artists', summary.review_artists) }}
        </li>
      </ul>
    </section>

    <RouterLink v-if="hasBackup" :to="{ name: 'library-backup' }">
      {{ t('utilities.backup') }}
    </RouterLink>
  </section>
</template>

<style scoped>
.utilities {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 40rem;
}
fieldset {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}
.utilities > .btn {
  align-self: flex-start;
}
.summary ul {
  margin: 0;
  padding-left: var(--space-3);
}
.utilities > a {
  display: inline-flex;
  align-items: center;
  min-height: var(--touch-target);
}
</style>
