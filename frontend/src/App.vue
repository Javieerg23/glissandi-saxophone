<script setup lang="ts">
import { onMounted } from 'vue'

import AppNav from './components/AppNav.vue'
import './styles/base.css'

// El service worker de la PWA solo se registra en producción: en desarrollo
// chocaría con el de MSW, que usa el mismo ámbito.
onMounted(() => {
  if (import.meta.env.PROD && 'serviceWorker' in navigator)
    void navigator.serviceWorker.register('/sw.js')
})
</script>

<template>
  <AppNav />
  <main class="app-main">
    <RouterView />
  </main>
</template>
