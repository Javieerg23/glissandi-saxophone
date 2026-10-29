import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  server: {
    // En desarrollo la API de Django se sirve bajo el mismo origen.
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    coverage: { provider: 'v8', include: ['src/**'], exclude: ['src/main.ts'] },
  },
})
