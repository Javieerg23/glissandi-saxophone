<script setup lang="ts">
import { computed } from 'vue'

/**
 * Barra de progreso de 0 a 100; `label` es su nombre accesible.
 *
 * Progress bar from 0 to 100; `label` is its accessible name.
 */
const props = defineProps<{ value: number; label: string }>()
const percent = computed(() => Math.min(100, Math.max(0, Math.round(props.value))))
</script>

<template>
  <div
    class="progress"
    role="progressbar"
    :aria-label="label"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="percent"
  >
    <div class="progress__fill" :style="{ width: `${percent}%` }" />
  </div>
</template>

<style scoped>
.progress {
  height: 0.75rem;
  overflow: hidden;
  border-radius: var(--radius);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}
.progress__fill {
  height: 100%;
  background: var(--color-primary);
}
</style>
