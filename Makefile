.PHONY: dev lint test migrate docs

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

migrate:
	cd backend && python manage.py migrate

docs:
	mkdocs serve
