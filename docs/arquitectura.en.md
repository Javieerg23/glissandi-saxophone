# Architecture

Glissandi is a responsive web app to build and manage a music library. The backend exposes a REST API and the frontend consumes it from the browser. Everything is done from the web: end users never need a command line.

## Components

| Component | Path | Responsibility |
|---|---|---|
| Configuration | `backend/config/` | Base, development and test settings; root URLs; `DATABASE_URL`. |
| Core | `backend/core/` | Health check, the `AppendOnlyModel` base model, shared utilities. |
| Accounts | `backend/accounts/` | Users, sessions, groups and permissions. |
| Catalog | `backend/catalog/` | Artists, albums, tracks, blocks and downloads. |
| Jobs | `backend/jobs/` | Background runs, their status and their log lines. |
| Watches | `backend/watches/` | Scheduled searches for new releases by artist. |
| Proxies | `backend/proxies/` | Proxies used for downloads and their counters. |
| Activity | `backend/activity/` | Action history and technical logs. |
| Preferences | `backend/preferences/` | User preferences with defaults defined in code. |
| Integrations | `backend/integrations/` | Deezer, MusicBrainz, YouTube (yt-dlp) and audio. No Django dependency. |
| Frontend | `frontend/` | Vue 3 with Vite and TypeScript. |
| Documentation | `docs/` | MkDocs site in Spanish and English. |

Each Django app exposes its API under `/api/v1/<app>/`. Integrations are plain Python: they take and return their own `dataclasses`, so they can be tested without a database and without network access.

## Import flow

1. The web starts an import job for the chosen artist.
2. `jobs` creates a `JobRun` and hands it to the server's thread executor.
3. The import service asks `integrations.deezer` for the artist, their albums and their tracks, and skips anything listed in `BlockedItem`.
4. Each item is saved in `catalog` through the ORM. Every step writes a `JobRunLine` and an `ActivityLog` entry.
5. The web reads the status and the log lines from a given position, so progress is followed without reloading.

## Download flow

1. Pending tracks are selected.
2. `integrations.youtube` finds the best match for each track with yt-dlp, using a proxy from the rotation.
3. The audio is downloaded with a progress callback.
4. `integrations.audio` converts it with ffmpeg and tags it with mutagen.
5. A `Download` record is written. It is append-only. "Downloaded" is not a checkbox: it is computed from those records.

## Data

- **Immutable:** data received from Deezer or MusicBrainz (`deezer_id`, `musicbrainz_id`, `isrc`) and records describing something that already happened (activity, runs, downloads). External identifiers are unique and checked in `save()`.
- **Mutable:** what the user edits, with change history, and operational state.
- Every table has its own `id`. Schema and data changes go through reversible migrations, one per change.

The reasoning behind each decision is in the [ADRs](adr/0001-django-drf.en.md).

## Security

- Sessions use a `Secure`, `HttpOnly` and `SameSite=Lax` cookie, with an inactivity timeout.
- CSRF through the `X-CSRFToken` header.
- Content Security Policy without `unsafe-inline` or `unsafe-eval` for scripts.
- Temporary lockout after repeated failed logins (django-axes).
- No record stores passwords, tokens or cookies, and a test checks it.

## Testing

- Integrations: simulated HTTP with `responses` and real recorded responses in `backend/tests/fixtures/`.
- Backend: pytest covering models, services and the API, run on SQLite and PostgreSQL.
- Frontend: Vitest with Vue Test Utils and the API mocked with MSW.
- End to end: Playwright at 390, 768 and 1440 px.
