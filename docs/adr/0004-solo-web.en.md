# ADR 0004: Web-only application, no command line

- **Status:** accepted

## Context

End users must not depend on a terminal. Importing and downloading are long-running tasks that must keep working while the app is in use, and their progress must be visible from the web.

## Decision

- All operations are done from the web. `manage.py` is kept for development only.
- Tasks run with `ThreadPoolExecutor` inside the server process, with one task of each type at a time.
- Status and log lines are stored in the database, so the web can read them at any moment.
- Stopping is cooperative: it is checked between tracks.

## Consequences

- There is no external queue (Celery, Redis). A single server process is enough, which is the intended use case.
- On startup, tasks left half-done are marked as interrupted and are not resumed automatically.
- If more than one process is ever needed, this ADR will be reviewed before adding a queue.
