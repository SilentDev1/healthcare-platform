.PHONY: setup dev db-up db-down migrate test lint typecheck import-cms-hospitals import-cms-quality api admin web build verify-phase-2

setup:
	command -v uv >/dev/null || (echo "Install uv: https://docs.astral.sh/uv/" && exit 1)
	uv sync --all-groups
	npm install

dev: db-up
	@echo "Run 'make api' and 'npm run dev' in separate terminals."

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	uv run alembic upgrade head

test:
	uv run pytest
	npm test

lint:
	uv run ruff format --check .
	uv run ruff check .
	npm run lint
	npm run format:check

typecheck:
	uv run mypy services collectors packages scripts
	npm run typecheck

build:
	npm run build

import-cms-hospitals:
	uv run python -m collectors.cms_hospitals

import-cms-quality:
	uv run python -m collectors.cms_quality

api:
	uv run uvicorn services.api.app.main:app --reload --port $${API_PORT:-8000}

admin:
	npm run dev --workspace @carecompare/admin

web:
	npm run dev --workspace @carecompare/web

verify-phase-2: migrate
	uv run python -m collectors.cms_quality --fixtures-dir data/fixtures/cms_quality
	uv run pytest
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) build
