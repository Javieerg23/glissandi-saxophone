# ADR 0001: Django and Django REST Framework for the backend

- **Status:** accepted

## Context

The backend needs users, sessions, CSRF protection, per-route permissions, an ORM with migrations and a documented API. FastAPI and Flask were considered.

## Decision

Use Django 6.x with Django REST Framework, and drf-spectacular for the OpenAPI schema.

## Consequences

- Security (sessions, CSRF, headers, CSP, password hashing) comes built in and is maintained by the framework itself.
- The ORM and the migration system avoid hand-written SQL and make it easier to change database engine.
- It is heavier than FastAPI. External integrations are blocking I/O run in threads, so the async model brings no advantage here.
