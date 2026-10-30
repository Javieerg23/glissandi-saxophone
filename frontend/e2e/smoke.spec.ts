import { expect, test } from '@playwright/test'

test('la portada carga con título y eslogan en español', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Glissandi' })).toBeVisible()
  await expect(page.getByText('Tu biblioteca musical, en cualquier pantalla.')).toBeVisible()
})

test('la página no desborda en horizontal', async ({ page }) => {
  await page.goto('/')
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBe(0)
})

test('la navegación es barra inferior hasta 1023 px y lateral desde 1024 px', async ({ page }) => {
  await page.goto('/')
  const nav = page.getByRole('navigation')
  await expect(nav).toBeVisible()
  const box = await nav.boundingBox()
  const viewport = page.viewportSize()
  if (!box || !viewport) throw new Error('sin geometría')

  if (viewport.width >= 1024) {
    expect(box.x).toBe(0)
    expect(box.height).toBe(viewport.height)
  } else {
    expect(box.y + box.height).toBe(viewport.height)
    expect(box.width).toBe(viewport.width)
  }
})

test('los enlaces de navegación tienen zona táctil de al menos 44 px', async ({ page }) => {
  await page.goto('/')
  const box = await page.getByRole('navigation').getByRole('link').first().boundingBox()
  expect(box?.height).toBeGreaterThanOrEqual(44)
})
