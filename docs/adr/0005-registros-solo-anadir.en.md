# ADR 0005: Append-only records

- **Status:** accepted

## Context

Activity history, task runs and downloads must be reliable. A bug in the code or a badly formed request must not be able to rewrite what already happened.

## Decision

- An abstract base model, `AppendOnlyModel`, rejects changes to an already saved row, deletion, and the bulk `update()` and `delete()` operations on its manager.
- The API exposes these models read-only (`ReadOnlyModelViewSet`).
- No database triggers are used, so the behaviour does not depend on the engine (see [ADR 0003](0003-base-de-datos-intercambiable.en.md)).
- Every table of this kind has a test that checks it cannot be changed or deleted.

## Consequences

- Correcting a record means appending a new one.
- Cleaning up technical logs older than 30 days is the only exception. It is an explicit service function and does not touch `ActivityLog`.
