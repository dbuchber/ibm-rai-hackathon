# Build context = repo root (see compose.yml). Stage 1 builds web/ (skipped until it exists).
FROM node:22-slim AS web
WORKDIR /src
COPY . .
RUN mkdir -p /out && if [ -f web/package.json ]; then cd web && npm ci && VITE_DATA=api npm run build && cp -r dist/. /out/; fi

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra api --extra engine
COPY . .
COPY --from=web /out ./web/dist
# Run as an unprivileged user; HOME and caches go to /tmp (a tmpfs under compose, read-only root fs).
RUN useradd --system --uid 10001 --no-create-home --home-dir /tmp app \
 && mkdir -p /app/data/state /app/runs && chown app:app /app/data/state /app/runs
USER 10001
ENV HOME=/tmp PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
