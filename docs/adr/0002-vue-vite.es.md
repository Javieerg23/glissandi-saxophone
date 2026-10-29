# ADR 0002: Vue 3 con Vite y TypeScript para el frontend

- **Estado:** aceptada

## Contexto

La interfaz debe ser responsive, mobile-first e instalable como PWA. La política de contenido (CSP) no permite `unsafe-eval` ni `unsafe-inline`, así que no se pueden compilar plantillas en el navegador.

## Decisión

Usar Vue 3 con `<script setup>`, Vite, TypeScript, Vue Router, Pinia y vue-i18n. Las plantillas se compilan en el build. Los tipos de la API se generan desde el esquema OpenAPI con openapi-typescript.

## Consecuencias

- Hace falta un paso de build. A cambio, la CSP puede ser estricta sin excepciones.
- El contrato entre backend y frontend se comprueba en tiempo de compilación, y un cambio incompatible en la API rompe el build y no la ejecución.
- No se usa Vue sin build, aunque sea más rápido de empezar, porque obligaría a relajar la CSP.
