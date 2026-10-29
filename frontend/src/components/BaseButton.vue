<script setup lang="ts">
/**
 * Botón con zona táctil de 44 px.
 *
 * Touch-friendly button (44 px minimum hit area).
 */
withDefaults(
  defineProps<{ variant?: 'primary' | 'secondary' | 'danger'; type?: 'button' | 'submit' }>(),
  {
    variant: 'primary',
    type: 'button',
  },
)
</script>

<template>
  <button :type="type" class="btn" :class="`btn--${variant}`"><slot /></button>
</template>

<style scoped>
.btn {
  min-height: var(--touch-target);
  min-width: var(--touch-target);
  padding: 0 var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius);
  font: inherit;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn--primary {
  background: var(--color-primary);
  color: var(--color-primary-contrast);
}
.btn--secondary {
  background: var(--color-surface);
  color: var(--color-text);
  border-color: var(--color-border);
}
.btn--danger {
  background: var(--color-danger);
  color: var(--color-bg);
}
</style>
