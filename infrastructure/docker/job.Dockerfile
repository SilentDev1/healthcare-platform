FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock alembic.ini ./
RUN uv sync --frozen --no-dev
COPY packages packages
COPY collectors collectors
COPY scripts scripts
COPY services services
COPY data/fixtures/nh_hospital_inventory.json data/fixtures/nh_hospital_inventory.json
COPY data/fixtures/zip_city_centroids.json data/fixtures/zip_city_centroids.json
COPY data/consumer_procedure_categories.json data/consumer_procedure_categories.json
COPY data/consumer_location_capabilities.json data/consumer_location_capabilities.json
COPY data/nh_roster_expansion.json data/nh_roster_expansion.json
COPY data/nh_nonhospital_published_prices.json data/nh_nonhospital_published_prices.json
COPY data/nh_location_service_availability.json data/nh_location_service_availability.json
COPY data/fixtures/cdm_crosswalk.json data/fixtures/cdm_crosswalk.json
COPY data/fixtures/verified_hospital_price_sources.json data/fixtures/verified_hospital_price_sources.json
COPY data/fixtures/verified_price_locations.json data/fixtures/verified_price_locations.json
COPY data/ma_hospitals_seed.json data/ma_hospitals_seed.json
COPY data/ma_cms_hospital_snapshot.json data/ma_cms_hospital_snapshot.json
COPY data/ma_region_taxonomy.json data/ma_region_taxonomy.json
COPY data/ma_hospital_price_sources.json data/ma_hospital_price_sources.json
RUN useradd --create-home --uid 10001 carevero && mkdir -p /data/downloads && chown -R carevero:carevero /app /data
USER carevero
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HOSPITAL_PRICE_RAW_DIR=/data/downloads/hospital-prices/US/NH
ENTRYPOINT ["python", "-m", "scripts.run_price_refresh"]
