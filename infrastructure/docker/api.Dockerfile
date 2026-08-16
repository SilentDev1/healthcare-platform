FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev
COPY packages packages
COPY services services
COPY collectors collectors
COPY scripts scripts
COPY data/fixtures/nh_hospital_inventory.json data/fixtures/nh_hospital_inventory.json
COPY data/consumer_procedure_categories.json data/consumer_procedure_categories.json
COPY data/consumer_location_capabilities.json data/consumer_location_capabilities.json
COPY data/fixtures/zip_city_centroids.json data/fixtures/zip_city_centroids.json
RUN useradd --create-home --uid 10001 carevero && chown -R carevero:carevero /app
USER carevero
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
