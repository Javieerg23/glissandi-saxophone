<script setup lang="ts">
/**
 * Casilla cuya etiqueta completa es la zona táctil.
 *
 * Checkbox whose whole label is the touch target.
 */
defineProps<{ label: string }>()
const model = defineModel<boolean>({ default: false })
</script>

<template>
  <label class="check">
    <input v-model="model" type="checkbox" />
    <span>{{ label }}</span>
  </label>
</template>

<style scoped>
.check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: var(--touch-target);
  cursor: pointer;
}
input {
  width: 1.25rem;
  height: 1.25rem;
  accent-color: var(--color-primary);
}
</style>
