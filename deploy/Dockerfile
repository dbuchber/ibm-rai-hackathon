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
CMD ["uv", "run", "--no-sync", "uvicorn", "api.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "17080"]
