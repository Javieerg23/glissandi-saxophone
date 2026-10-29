# ADR 0003: Interchangeable database (SQLite and PostgreSQL)

- **Status:** accepted

## Context

A personal installation works well with SQLite, but a shared installation needs PostgreSQL. The code must not depend on one specific engine.

## Decision

- The engine is selected with `DATABASE_URL` (dj-database-url).
- Only the ORM is used: no hand-written SQL and no `RunSQL`.
- CI runs the full test suite on SQLite and on PostgreSQL.
- Moving between engines is done with `dumpdata` and `loaddata`.

## Consequences

- Engine-specific features are not used. If one becomes necessary, it is documented and isolated in its own ADR.
- Every migration is tested on both engines before it is merged.
