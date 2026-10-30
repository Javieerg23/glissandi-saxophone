# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [SemVer](https://semver.org/lang/es/).
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/).

## [Sin publicar · Unreleased]

### Añadido · Added

- Esqueleto de backend (Django + DRF) y frontend (Vue 3 + Vite + TypeScript).
- Backend (Django + DRF) and frontend (Vue 3 + Vite + TypeScript) skeletons.
- CI endurecida (interrogate, diff-cover, pip-audit, npm audit, `check --deploy`, django-migration-linter) y mutación nocturna (mutmut y StrykerJS).
- Hardened CI (interrogate, diff-cover, pip-audit, npm audit, `check --deploy`, django-migration-linter) and nightly mutation testing (mutmut and StrykerJS).
- Esquema OpenAPI versionado y tipos del frontend generados con openapi-typescript; la CI comprueba que están al día.
- Versioned OpenAPI schema and frontend types generated with openapi-typescript; CI checks they are up to date.
