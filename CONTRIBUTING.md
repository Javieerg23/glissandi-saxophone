# Contribuir · Contributing

[Español](#español) · [English](#english)

## Español

- Ramas cortas desde `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Commits con [Conventional Commits](https://www.conventionalcommits.org/es/) (`feat: …`, `fix: …`).
- PRs pequeños (unas 400 líneas como máximo), revisados por el code owner y fusionados con squash.
- Antes de abrir el PR: `make lint test` en verde, con documentación y migraciones al día. Si cambias la API, ejecuta `make api` para regenerar `backend/openapi.yaml` y los tipos del frontend; la CI falla si no coinciden.
- Código, nombres e identificadores en inglés; docstrings y comentarios en español con su versión en inglés.

### Entorno

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
npm --prefix frontend install
pre-commit install
```

## English

- Short branches off `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
- Small PRs (about 400 lines at most), reviewed by the code owner and squash-merged.
- Before opening a PR: `make lint test` must pass, with docs and migrations up to date. If you change the API, run `make api` to regenerate `backend/openapi.yaml` and the frontend types; CI fails if they drift.
- Code and identifiers in English; docstrings and comments in Spanish followed by their English version.
