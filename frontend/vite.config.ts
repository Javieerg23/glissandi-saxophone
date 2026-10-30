import vue from '@vitejs/plugin-vue'
import { configDefaults, defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  server: {
    // En desarrollo la API de Django se sirve bajo el mismo origen.
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    // Los specs de `e2e/` son de Playwright y no corren bajo Vitest.
    exclude: [...configDefaults.exclude, 'e2e/**'],
    environment: 'jsdom',
    setupFiles: ['src/__tests__/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      exclude: ['src/main.ts', 'src/mocks/browser.ts'],
      // Suelo global del 80 %. / 80 % global floor.
      thresholds: { lines: 80, branches: 80, functions: 80, statements: 80 },
    },
  },
})
