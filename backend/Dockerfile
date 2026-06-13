FROM python:3.12-slim

WORKDIR /app

# 系统依赖 (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖 — requirements-api.txt (纯 Python, 无 Rust 编译)
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY . .

# SQLite data directory (mounted as persistent volume on Fly.io)
RUN mkdir -p /app/data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Start: normalize DATABASE_URL if PostgreSQL, otherwise use SQLite
CMD if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "postgres"; then \
      export DATABASE_URL=$(echo "$DATABASE_URL" | sed -e 's/^postgres:/postgresql+asyncpg:/' -e 's/^postgresql:/postgresql+asyncpg:/'); \
    fi; \
    python -m alembic upgrade head 2>/dev/null || echo "Migration skipped"; \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
