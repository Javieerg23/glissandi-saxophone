/** Árbol de textos tal y como lo describe un JSON de mensajes. */
interface Dictionary {
  [key: string]: string | Dictionary
}

function collect(files: Record<string, { default: Dictionary }>): Dictionary {
  return Object.assign({}, ...Object.values(files).map((f) => f.default))
}

// Un fichero por zona (`app.json`, `catalog.json`...) con su propio espacio de
// nombres de primer nivel; así cada vista añade el suyo sin tocar los demás.
/** Mensajes en español y en inglés, reunidos de `es/*.json` y `en/*.json`. */
export const messages = {
  es: collect(import.meta.glob<{ default: Dictionary }>('./es/*.json', { eager: true })),
  en: collect(import.meta.glob<{ default: Dictionary }>('./en/*.json', { eager: true })),
}
