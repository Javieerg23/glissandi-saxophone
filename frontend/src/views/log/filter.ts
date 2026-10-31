/** Lo que necesita `bindFilter` de una lista de `usePagedList`. */
interface FilteredList {
  query: Record<string, string>
  update(changes: Record<string, string>): void
}

/**
 * Enlaza un campo de filtro con la URL a través de `usePagedList`: muestra el valor de la
 * query y, al cambiarlo, vuelve a la primera página. Se usa con `v-bind`.
 *
 * Binds a filter field to the URL through `usePagedList`. Use it with `v-bind`.
 */
export function bindFilter(list: FilteredList, key: string) {
  return {
    modelValue: list.query[key] ?? '',
    'onUpdate:modelValue': (value: string) => list.update({ [key]: value }),
  }
}
