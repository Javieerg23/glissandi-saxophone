<script setup lang="ts">
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * Desplegable de filtro del registro, con «Todos» (vacío) como primera opción.
 *
 * Log filter dropdown with "All" (empty) as its first option.
 */
defineProps<{ label: string; options: { value: string; label: string }[] }>()
const model = defineModel<string>({ default: '' })
const { t } = useI18n()
const id = useId()
</script>

<template>
  <div class="select">
    <label :for="id">{{ label }}</label>
    <select :id="id" v-model="model">
      <option value="">{{ t('log.filters.any') }}</option>
      <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
  </div>
</template>

<style scoped>
.select {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
select {
  min-height: var(--touch-target);
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
}
</style>
