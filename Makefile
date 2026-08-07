.PHONY: setup dev db-up db-down migrate test lint typecheck import-cms-hospitals import-cms-quality import-nppes-organizations seed-facility-identity seed-procedure-catalog rebuild-search-index evaluate-data-health discover-hospital-price-sources download-hospital-price-files import-hospital-prices normalize-hospital-prices map-price-procedures evaluate-pricing-health rebuild-price-summaries pricing-pipeline api admin web build verify-phase-2 verify-phase-3 verify-phase-4

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

import-nppes-organizations:
	uv run python -m collectors.nppes_organizations

seed-facility-identity:
	uv run python -m scripts.seed_facility_identity

seed-procedure-catalog:
	uv run python -m scripts.seed_procedure_catalog

rebuild-search-index:
	uv run python -m scripts.rebuild_search_index

evaluate-data-health:
	uv run python -m scripts.evaluate_data_health

discover-hospital-price-sources:
	uv run python -m scripts.discover_hospital_price_sources

download-hospital-price-files:
	uv run python -m scripts.download_hospital_price_files

import-hospital-prices:
	uv run python -m scripts.import_hospital_prices

normalize-hospital-prices map-price-procedures: import-hospital-prices

evaluate-pricing-health:
	uv run python -m scripts.evaluate_pricing_health

rebuild-price-summaries:
	uv run python -m scripts.rebuild_price_summaries

pricing-pipeline:
	uv run python -m collectors.hospital_prices --fixtures-dir data/fixtures/hospital_prices

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

verify-phase-3: migrate
	uv run python -m scripts.seed_facility_identity
	uv run python -m collectors.nppes_organizations --source-file data/fixtures/nppes_organizations.json
	uv run python -m scripts.seed_procedure_catalog
	uv run python -m scripts.rebuild_search_index
	uv run python -m scripts.evaluate_data_health
	uv run python -m scripts.benchmark_search
	uv run pytest --cov=services --cov=collectors --cov=packages --cov=scripts --cov-report=term-missing
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) build
	npm audit --audit-level=high

verify-phase-4: migrate
	uv run python -m collectors.hospital_prices --fixtures-dir data/fixtures/hospital_prices
	uv run python -m collectors.hospital_prices --fixtures-dir data/fixtures/hospital_prices
	uv run python -m scripts.rebuild_search_index
	uv run pytest --cov=services --cov=collectors --cov=packages --cov=scripts --cov-report=term-missing
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) build
	npm audit --audit-level=high
