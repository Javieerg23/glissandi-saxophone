.PHONY: dev lint test e2e migrate docs api

# Arranca backend y frontend. / Starts backend and frontend.
dev:
	cd backend && python manage.py compilemessages -v0 && python manage.py runserver & \
	cd frontend && npm run dev

lint:
	cd backend && ruff check . && ruff format --check . && mypy . && interrogate .
	cd frontend && npm run lint && npm run typecheck

test:
	cd backend && python manage.py compilemessages -v0 && pytest
	cd frontend && npm test

# Pruebas extremo a extremo (requiere `npx playwright install chromium`). / End-to-end tests (needs `npx playwright install chromium`).
e2e:
	cd frontend && npm run e2e

migrate:
	cd backend && python manage.py migrate

docs:
	mkdocs serve

# Regenera el esquema OpenAPI y los tipos del frontend. / Regenerates the OpenAPI schema and frontend types.
api:
	cd backend && python manage.py spectacular --file openapi.yaml --validate --fail-on-warn
	cd frontend && npm run api:types
