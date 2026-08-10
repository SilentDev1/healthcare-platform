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
COPY data/fixtures/cdm_crosswalk.json data/fixtures/cdm_crosswalk.json
COPY data/fixtures/verified_hospital_price_sources.json data/fixtures/verified_hospital_price_sources.json
COPY data/fixtures/verified_price_locations.json data/fixtures/verified_price_locations.json
RUN useradd --create-home --uid 10001 carevero && mkdir -p /data/downloads && chown -R carevero:carevero /app /data
USER carevero
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HOSPITAL_PRICE_RAW_DIR=/data/downloads/hospital-prices/US/NH
ENTRYPOINT ["python", "-m", "scripts.run_price_refresh"]
