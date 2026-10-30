<script setup lang="ts">
import { ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * Panel de filtros: plegable en móvil, para no tapar la lista, y siempre abierto desde
 * 1024 px. El contenido (campos) lo pone cada vista en el slot.
 *
 * Filter panel: collapsible on mobile, always open from 1024 px. Each view slots its fields.
 */
const { t } = useI18n()
const open = ref(false)
const bodyId = useId()
</script>

<template>
  <section class="filters">
    <button
      type="button"
      class="filters__toggle"
      :aria-expanded="open"
      :aria-controls="bodyId"
      @click="open = !open"
    >
      {{ t('ui.filters.title') }}
    </button>
    <div :id="bodyId" class="filters__body" :class="{ 'is-open': open }">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.filters {
  margin-bottom: var(--space-3);
}
.filters__toggle {
  width: 100%;
  min-height: var(--touch-target);
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
  color: var(--color-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.filters__body {
  display: none;
  padding-top: var(--space-2);
}
.filters__body.is-open {
  display: block;
}

@media (min-width: 1024px) {
  .filters__toggle {
    display: none;
  }
  .filters__body {
    display: block;
    padding-top: 0;
  }
}
</style>
