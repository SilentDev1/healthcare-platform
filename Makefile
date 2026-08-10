.PHONY: setup dev db-up db-down migrate test lint typecheck build beta-gate migrate-deployment beta-data-smoke secret-scan import-cms-hospitals import-cms-quality import-nppes-organizations seed-facility-identity seed-procedure-catalog rebuild-search-index evaluate-data-health discover-hospital-price-sources download-hospital-price-files import-hospital-prices normalize-hospital-prices map-price-procedures evaluate-pricing-health rebuild-price-summaries pricing-pipeline api admin web verify-phase-2 verify-phase-3 verify-phase-4 benchmark-pricing-import generate-large-pricing-fixture resume-price-import restart-price-import verify-phase-4-1 pipeline-discover-nh pipeline-download-nh pipeline-import-nh pipeline-postprocess-nh pipeline-full-nh audit-nh-hospitals statewide-scorecard procedure-coverage geocode-nh verify-phase-4-2 enhanced-scorecard benchmark-coverage final-classification discover-pricing import-pricing verify-coverage

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

secret-scan:
	uv run python -m scripts.secret_scan

beta-data-smoke:
	uv run python -m scripts.beta_data_smoke

migrate-deployment:
	uv run python -m scripts.migrate_deployment

beta-gate: test lint typecheck build secret-scan
	npm audit --audit-level=high

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

benchmark-pricing-import:
	uv run python -m scripts.benchmark_pricing_import

generate-large-pricing-fixture:
	uv run python -m scripts.generate_large_pricing_fixture

resume-price-import:
	uv run python -m scripts.resume_price_import --import-run-id $(IMPORT_RUN_ID)

restart-price-import:
	uv run python -m scripts.restart_price_import --source-file-id $(SOURCE_FILE_ID)

pipeline-discover-nh:
	uv run python -m scripts.pipeline_discover --state NH

pipeline-download-nh:
	uv run python -m scripts.pipeline_download --state NH

pipeline-import-nh:
	uv run python -m scripts.pipeline_import --state NH

pipeline-postprocess-nh:
	uv run python -m scripts.pipeline_postprocess --state NH

pipeline-full-nh:
	uv run python -m scripts.pipeline_full --state NH

audit-nh-hospitals:
	uv run python -m scripts.audit_nh_hospitals

statewide-scorecard:
	uv run python -m scripts.statewide_scorecard

procedure-coverage:
	uv run python -m scripts.report_procedure_coverage

geocode-nh:
	uv run python -m scripts.geocode_facilities

verify-phase-4-2: migrate
	uv run python -m collectors.hospital_prices --fixtures-dir data/fixtures/hospital_prices
	uv run python -m collectors.hospital_prices --fixtures-dir data/fixtures/hospital_prices
	uv run python -m scripts.rebuild_search_index
	uv run python -m scripts.benchmark_pricing_import
	uv run python -m scripts.phase_4_2_final_report
	uv run pytest --cov=services --cov=collectors --cov=packages --cov=scripts --cov-report=term-missing
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) build
	npm audit --audit-level=high

# --- Phase 4.2.1 targets (generic, accept STATE=XX) ---

enhanced-scorecard:
	uv run python -m scripts.statewide_scorecard --state $${STATE:-NH}

benchmark-coverage:
	uv run python -m scripts.benchmark_coverage --state $${STATE:-NH}

final-classification:
	uv run python -m scripts.final_classification --state $${STATE:-NH}

# Generic discovery/import targets (accept STATE=XX for multi-state)
discover-pricing:
	uv run python -m scripts.pipeline_discover --state $${STATE:-NH}

import-pricing:
	uv run python -m scripts.pipeline_import --state $${STATE:-NH}

verify-coverage:
	uv run python -m scripts.statewide_scorecard --state $${STATE:-NH}

verify-phase-4-1: migrate
	uv run python -m collectors.hospital_prices --fixtures-dir data/fixtures/hospital_prices
	uv run python -m collectors.hospital_prices --fixtures-dir data/fixtures/hospital_prices
	uv run python -m scripts.rebuild_search_index
	uv run python -m scripts.benchmark_pricing_import
	uv run pytest --cov=services --cov=collectors --cov=packages --cov=scripts --cov-report=term-missing
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) build
	npm audit --audit-level=high
