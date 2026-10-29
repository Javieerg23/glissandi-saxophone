# ADR 0002: Vue 3 with Vite and TypeScript for the frontend

- **Status:** accepted

## Context

The interface must be responsive, mobile-first and installable as a PWA. The content security policy (CSP) forbids `unsafe-eval` and `unsafe-inline`, so templates cannot be compiled in the browser.

## Decision

Use Vue 3 with `<script setup>`, Vite, TypeScript, Vue Router, Pinia and vue-i18n. Templates are compiled at build time. API types are generated from the OpenAPI schema with openapi-typescript.

## Consequences

- A build step is required. In return, the CSP can be strict with no exceptions.
- The backend–frontend contract is checked at compile time: an incompatible API change breaks the build, not the running app.
- Vue without a build step is quicker to start with, but it would force a relaxed CSP, so it is not used.
