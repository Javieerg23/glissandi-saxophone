# Glissandi

[Español](#español) · [English](#english)

## Español

App web responsive para crear y gestionar tu biblioteca musical: importa artistas, álbumes y canciones desde Deezer, verifícalos con MusicBrainz y descárgalos con yt-dlp.

> **Aviso:** pensado para uso personal con contenido sobre el que tengas derechos.

> **Estado:** en construcción; de momento solo existe el esqueleto del proyecto.

### Tecnologías

- Backend: Django 6 + Django REST Framework, SQLite o PostgreSQL mediante `DATABASE_URL`.
- Frontend: Vue 3 + Vite + TypeScript, bilingüe (español por defecto).
- Documentación: MkDocs Material.

### Requisitos

Python 3.12+, Node.js 22+ y, opcionalmente, PostgreSQL.

### Desarrollo

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
npm --prefix frontend install
make migrate
make dev       # API en :8000 y frontend en :5173
make lint test
make docs
```

Las variables de entorno disponibles están en `.env.example`. Para usar PostgreSQL define `DATABASE_URL=postgres://usuario:clave@localhost:5432/glissandi`.

### Estructura

- `backend/`: proyecto Django (`config/`, apps).
- `frontend/`: aplicación Vue.
- `docs/`: documentación.

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para colaborar. Licencia: [AGPL-3.0](LICENSE).

## English

Responsive web app to build and manage your music library: import artists, albums and songs from Deezer, verify them with MusicBrainz and download them with yt-dlp.

> **Notice:** intended for personal use with content you have the rights to.

> **Status:** under construction; only the project skeleton exists so far.

### Stack

- Backend: Django 6 + Django REST Framework, SQLite or PostgreSQL through `DATABASE_URL`.
- Frontend: Vue 3 + Vite + TypeScript, bilingual (Spanish by default).
- Documentation: MkDocs Material.

### Requirements

Python 3.12+, Node.js 22+ and, optionally, PostgreSQL.

### Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
npm --prefix frontend install
make migrate
make dev       # API on :8000 and frontend on :5173
make lint test
make docs
```

Available environment variables are listed in `.env.example`. To use PostgreSQL set `DATABASE_URL=postgres://user:password@localhost:5432/glissandi`.

### Layout

- `backend/`: Django project (`config/`, apps).
- `frontend/`: Vue application.
- `docs/`: documentation.

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute. License: [AGPL-3.0](LICENSE).
