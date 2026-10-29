<script setup lang="ts">
import { useId } from 'vue'

/**
 * Campo de texto con etiqueta y mensaje de error enlazados para lectores de pantalla.
 *
 * Text field with its label and error message wired up for screen readers.
 */
defineProps<{ label: string; type?: string; error?: string }>()
const model = defineModel<string>({ default: '' })
const id = useId()
</script>

<template>
  <div class="field">
    <label :for="id">{{ label }}</label>
    <input
      :id="id"
      v-model="model"
      :type="type ?? 'text'"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-error` : undefined"
    />
    <p v-if="error" :id="`${id}-error`" class="field__error">{{ error }}</p>
  </div>
</template>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
input {
  min-height: var(--touch-target);
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
  /* 16 px evita el zoom automático de iOS al enfocar el campo. */
  font: inherit;
}
input[aria-invalid='true'] {
  border-color: var(--color-danger);
}
.field__error {
  margin: 0;
  color: var(--color-danger);
}
</style>
