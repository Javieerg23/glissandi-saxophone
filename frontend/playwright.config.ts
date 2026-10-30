import { defineConfig } from '@playwright/test'

const port = 4173

/**
 * Pruebas extremo a extremo contra la compilación de producción (la que se despliega,
 * con su service worker), no contra el servidor de desarrollo. Los tres anchos
 * cubren móvil, tableta y escritorio; el de 1440 px es el único con navegación lateral.
 *
 * End-to-end tests against the production build (the one that ships, service worker
 * included), not the dev server. The three widths cover mobile, tablet and desktop;
 * only 1440 px gets the side navigation.
 */
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  // En CI un `test.only` olvidado dejaría pasar el resto sin ejecutarse.
  // In CI a forgotten `test.only` would silently skip everything else.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${port}`,
    locale: 'es-ES',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'mobile-390', use: { viewport: { width: 390, height: 844 }, hasTouch: true } },
    { name: 'tablet-768', use: { viewport: { width: 768, height: 1024 }, hasTouch: true } },
    { name: 'desktop-1440', use: { viewport: { width: 1440, height: 900 } } },
  ],
  webServer: {
    command: `npm run build && npx vite preview --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
