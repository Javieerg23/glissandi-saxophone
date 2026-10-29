import { describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import BaseAlert from '../components/BaseAlert.vue'
import BaseButton from '../components/BaseButton.vue'
import BaseCheckbox from '../components/BaseCheckbox.vue'
import BaseDialog from '../components/BaseDialog.vue'
import BaseField from '../components/BaseField.vue'
import ProgressBar from '../components/ProgressBar.vue'
import ResponsiveList from '../components/ResponsiveList.vue'
import { render } from './helpers'

describe('BaseButton', () => {
  it('pinta el slot, la variante y el tipo', () => {
    const w = render(BaseButton, {
      slots: { default: 'Guardar' },
      props: { variant: 'danger', type: 'submit' },
    })
    expect(w.text()).toBe('Guardar')
    expect(w.classes()).toContain('btn--danger')
    expect(w.attributes('type')).toBe('submit')
  })

  it('es primario y de tipo button por defecto', () => {
    const w = render(BaseButton)
    expect(w.classes()).toContain('btn--primary')
    expect(w.attributes('type')).toBe('button')
  })
})

describe('BaseField', () => {
  it('enlaza etiqueta y campo y actualiza el modelo', async () => {
    const w = render(BaseField, { props: { label: 'Usuario', modelValue: '' } })
    const input = w.get('input')
    expect(w.get('label').attributes('for')).toBe(input.attributes('id'))
    expect(input.attributes('type')).toBe('text')
    expect(input.attributes('aria-invalid')).toBeUndefined()
    await input.setValue('ana')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['ana'])
  })

  it('anuncia el error enlazado al campo', () => {
    const w = render(BaseField, {
      props: { label: 'Clave', type: 'password', error: 'Obligatoria' },
    })
    const input = w.get('input')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(w.get(`#${input.attributes('aria-describedby')}`).text()).toBe('Obligatoria')
  })
})

describe('BaseCheckbox', () => {
  it('actualiza el modelo al pulsar la etiqueta', async () => {
    const w = render(BaseCheckbox, { props: { label: 'Recordarme', modelValue: false } })
    await w.get('input').setValue(true)
    expect(w.text()).toBe('Recordarme')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([true])
  })
})

describe('BaseAlert', () => {
  it.each([
    ['error', 'alert'],
    ['warning', 'alert'],
    ['info', 'status'],
    ['success', 'status'],
  ] as const)('%s usa el rol %s', (variant, role) => {
    expect(render(BaseAlert, { props: { variant } }).attributes('role')).toBe(role)
  })

  it('es informativo por defecto', () => {
    expect(render(BaseAlert).classes()).toContain('alert--info')
  })
})

describe('ProgressBar', () => {
  it('expone el valor y el nombre accesible', () => {
    const w = render(ProgressBar, { props: { value: 42.4, label: 'Descarga' } })
    expect(w.attributes('aria-valuenow')).toBe('42')
    expect(w.attributes('aria-label')).toBe('Descarga')
  })

  it.each([
    [-5, '0'],
    [250, '100'],
  ])('acota %s a %s', (value, expected) => {
    expect(render(ProgressBar, { props: { value, label: 'x' } }).attributes('aria-valuenow')).toBe(
      expected,
    )
  })
})

describe('ResponsiveList', () => {
  const columns = [
    { key: 'name', label: 'Nombre' },
    { key: 'year', label: 'Año' },
  ]
  const rows = [{ id: 1, name: 'Kind of Blue', year: 1959 }]

  it('pinta una fila por elemento con la cabecera de cada celda', () => {
    const w = render(ResponsiveList, { props: { columns, rows, rowKey: 'id' } })
    expect(w.findAll('tbody tr')).toHaveLength(1)
    expect(w.findAll('td').map((td) => td.attributes('data-label'))).toEqual(['Nombre', 'Año'])
    expect(w.text()).toContain('Kind of Blue')
  })

  it('permite personalizar una celda', () => {
    const w = render(ResponsiveList, {
      props: { columns, rows, rowKey: 'id' },
      slots: { 'cell-year': '<template #cell-year="{ row }">Año {{ row.year }}</template>' },
    })
    expect(w.text()).toContain('Año 1959')
  })

  it('muestra el texto de lista vacía en cada idioma', () => {
    expect(render(ResponsiveList, { props: { columns, rows: [], rowKey: 'id' } }).text()).toBe(
      'No hay nada que mostrar.',
    )
    expect(
      render(ResponsiveList, { props: { columns, rows: [], rowKey: 'id' } }, 'en').text(),
    ).toBe('Nothing to show.')
  })
})

describe('BaseDialog', () => {
  // jsdom no implementa showModal/close de <dialog>.
  const showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  })
  const close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open')
  })
  Object.assign(HTMLDialogElement.prototype, { showModal, close })

  it('abre y cierra el diálogo según el modelo', async () => {
    const w = render(BaseDialog, {
      props: { title: 'Aviso', modelValue: false },
      slots: { default: 'Contenido' },
      attachTo: document.body,
    })
    expect(showModal).not.toHaveBeenCalled()
    await w.setProps({ modelValue: true })
    await nextTick()
    expect(showModal).toHaveBeenCalledOnce()
    // Reabrir estando ya abierto no vuelve a llamar a showModal.
    await w.setProps({ modelValue: true })
    await w.setProps({ modelValue: false })
    expect(close).toHaveBeenCalledOnce()
    await w.setProps({ modelValue: false })
    expect(close).toHaveBeenCalledOnce()
    w.unmount()
  })

  it('abre de inicio si el modelo ya es true', async () => {
    showModal.mockClear()
    const w = render(BaseDialog, {
      props: { title: 'Aviso', modelValue: true },
      attachTo: document.body,
    })
    await nextTick()
    expect(showModal).toHaveBeenCalledOnce()
    w.unmount()
  })

  it('emite el cierre con el botón y con el evento close del navegador', async () => {
    const w = render(BaseDialog, { props: { title: 'Aviso', modelValue: true } })
    expect(w.get('h2').text()).toBe('Aviso')
    await w.get('button').trigger('click')
    expect(w.emitted('update:modelValue')).toEqual([[false]])
    // Esc: el navegador cierra el <dialog> y avisa con `close`.
    const esc = render(BaseDialog, { props: { title: 'Aviso', modelValue: true } })
    await esc.get('dialog').trigger('close')
    expect(esc.emitted('update:modelValue')).toEqual([[false]])
  })
})
