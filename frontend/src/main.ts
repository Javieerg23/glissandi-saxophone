import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'

// Con `VITE_MOCKS=1` el navegador responde la API con MSW (desarrollo sin backend).
if (import.meta.env.DEV && import.meta.env.VITE_MOCKS) {
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledFrame: 'bypass' })
}

createApp(App).use(createPinia()).use(router).use(i18n).mount('#app')
