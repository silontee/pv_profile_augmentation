# ── Stage 1: 의존성 설치 ───────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 의존성 파일만 먼저 복사 (레이어 캐시)
COPY pyproject.toml uv.lock ./

# 시스템 빌드 의존성 (psycopg2-binary 빌드용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: 런타임 ───────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 가상환경 복사
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 앱 코드 복사
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
