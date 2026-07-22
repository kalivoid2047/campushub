.PHONY: install run migrate seed test-backend test-client lint

install:
	cd backend && python -m venv .venv && .venv/Scripts/pip install -e .[dev]

run:
	cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000

migrate:
	cd backend && .venv/Scripts/alembic upgrade head

seed:
	cd backend && .venv/Scripts/python ../scripts/dev/seed_db.py

test-backend:
	cd backend && .venv/Scripts/pytest

test-client:
	cd client && flutter test

lint:
	cd backend && .venv/Scripts/ruff check . && .venv/Scripts/black --check .
	cd client && dart format --output=none --set-exit-if-changed . && flutter analyze
