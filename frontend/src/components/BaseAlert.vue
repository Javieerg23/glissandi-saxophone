<script setup lang="ts">
/**
 * Aviso en línea. Los errores y advertencias se anuncian como `alert`; el resto como `status`.
 *
 * Inline notice. Errors and warnings are announced as `alert`, the rest as `status`.
 */
withDefaults(defineProps<{ variant?: 'info' | 'success' | 'warning' | 'error' }>(), {
  variant: 'info',
})
</script>

<template>
  <div
    class="alert"
    :class="`alert--${variant}`"
    :role="variant === 'error' || variant === 'warning' ? 'alert' : 'status'"
  >
    <slot />
  </div>
</template>

<style scoped>
.alert {
  padding: var(--space-2) var(--space-3);
  border: 1px solid currentcolor;
  border-radius: var(--radius);
  background: var(--color-surface);
}
.alert--info {
  color: var(--color-info);
}
.alert--success {
  color: var(--color-success);
}
.alert--warning {
  color: var(--color-warning);
}
.alert--error {
  color: var(--color-danger);
}
</style>
