<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <main class="home">
    <h1>{{ t('app.title') }}</h1>
    <p>{{ t('app.tagline') }}</p>
  </main>
</template>

<style scoped>
/* Mobile-first: el diseño base es el de móvil y se amplía con media queries. */
.home {
  padding: 1rem;
}
</style>
