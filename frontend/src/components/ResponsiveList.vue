<script setup lang="ts" generic="T extends object">
import { useI18n } from 'vue-i18n'

/** Columna de la lista: clave del campo y su cabecera ya traducida. */
export interface Column {
  key: string
  label: string
}

/**
 * Tabla en escritorio y lista de tarjetas en móvil (menos de 600 px).
 * Es la misma estructura HTML: en móvil cada celda muestra su cabecera con CSS
 * (`data-label`), sin duplicar el contenido ni medir la pantalla con JS.
 * Cada celda se puede personalizar con el slot `cell-<key>`.
 *
 * Table on desktop, card list on mobile (under 600 px). Same markup both ways:
 * on mobile each cell shows its header through CSS (`data-label`).
 */
const props = defineProps<{ columns: Column[]; rows: T[]; rowKey: keyof T & string }>()
const { t } = useI18n()

function cell(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key]
}
</script>

<template>
  <p v-if="props.rows.length === 0" class="list-empty">{{ t('ui.list.empty') }}</p>
  <table v-else class="list">
    <thead>
      <tr>
        <th v-for="c in props.columns" :key="c.key" scope="col">{{ c.label }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="row in props.rows" :key="String(row[props.rowKey])">
        <td v-for="c in props.columns" :key="c.key" :data-label="c.label">
          <slot :name="`cell-${c.key}`" :row="row">{{ cell(row, c.key) }}</slot>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.list {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: var(--space-2) var(--space-3);
  text-align: left;
}
tbody tr {
  border-top: 1px solid var(--color-border);
}

@media (max-width: 599.98px) {
  /* El encabezado queda solo para lectores de pantalla; cada celda lleva el suyo. */
  thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  tbody tr {
    display: block;
    margin-bottom: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
    background: var(--color-surface);
  }
  td {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
  }
  td::before {
    content: attr(data-label);
    font-weight: 600;
    color: var(--color-muted);
  }
}
</style>
