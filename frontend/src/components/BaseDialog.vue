<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseButton from './BaseButton.vue'

/**
 * Diálogo modal sobre `<dialog>` nativo: el navegador gestiona foco, `Esc` y capa inerte.
 *
 * Modal dialog on the native `<dialog>`: the browser handles focus, `Esc` and the inert backdrop.
 */
defineProps<{ title: string }>()
const open = defineModel<boolean>({ default: false })
const { t } = useI18n()
const dialog = ref<HTMLDialogElement>()

// `<dialog>` solo se abre por API, no por atributo: se sincroniza al montar y en cada cambio.
function sync(): void {
  const el = dialog.value as HTMLDialogElement
  if (open.value && !el.open) el.showModal()
  else if (!open.value && el.open) el.close()
}

onMounted(sync)
watch(open, sync, { flush: 'post' })
</script>

<template>
  <dialog ref="dialog" class="dialog" @close="open = false">
    <h2>{{ title }}</h2>
    <slot />
    <div class="dialog__actions">
      <BaseButton variant="secondary" @click="open = false">{{ t('ui.close') }}</BaseButton>
    </div>
  </dialog>
</template>

<style scoped>
.dialog {
  width: min(32rem, calc(100vw - 2 * var(--space-3)));
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  color: var(--color-text);
}
.dialog::backdrop {
  background: rgb(0 0 0 / 50%);
}
.dialog__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-3);
}
</style>
