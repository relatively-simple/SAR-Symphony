# KurinjiKumaraN — SAR Symphony: Dancing with Earth's Signals
# Single unified multi-stage Docker build targeting Hugging Face Spaces (port 7860)

FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    SPX_PRESET_DIR=/app/cache/presets \
    SPX_CACHE_DIR=/app/runtime_cache \
    SPX_FRONTEND_DIST=/app/frontend/dist \
    SPX_MAX_WORKERS=6

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY backend/pyproject.toml /app/backend/pyproject.toml
WORKDIR /app/backend
RUN uv pip install --system --no-cache \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "httpx>=0.28.0" \
    "certifi>=2024.12.14" \
    "astropy>=7.0.0" \
    "reproject>=0.14.0" \
    "numpy>=2.0.0" \
    "scipy>=1.14.0" \
    "pydantic>=2.9.0" \
    "pydantic-settings>=2.6.0" \
    "pillow>=11.0.0"

COPY backend/app /app/backend/app
COPY cache/presets /app/cache/presets
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

RUN useradd -m -u 1000 user \
    && mkdir -p /app/runtime_cache \
    && chown -R user:user /app/runtime_cache /app/cache/presets
USER user

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-7860}"]
