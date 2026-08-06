FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev
COPY packages packages
COPY services services
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]

