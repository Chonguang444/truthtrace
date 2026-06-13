#!/bin/bash
set -e

echo "=============================="
echo "TruthTrace Render Start Script"
echo "=============================="
echo "[$(date +%H:%M:%S)] Python: $(python --version 2>&1)"
echo "[$(date +%H:%M:%S)] CWD: $(pwd)"

# -------- Step 1: Fix DATABASE_URL for asyncpg ----------
echo "[$(date +%H:%M:%S)] Normalizing DATABASE_URL..."
export DATABASE_URL=$(echo "$DATABASE_URL" | sed -e 's/^postgres:/postgresql+asyncpg:/' -e 's/^postgresql:/postgresql+asyncpg:/')
echo "[$(date +%H:%M:%S)] DATABASE_URL=${DATABASE_URL:0:30}..."

# -------- Step 2: Check Python path ----------
if [ ! -f "app/main.py" ]; then
    echo "ERROR: app/main.py not found in $(pwd)"
    echo "Directory listing:"
    ls -la
    exit 1
fi

# -------- Step 3: Try alembic (non-fatal) ----------
echo "[$(date +%H:%M:%S)] Running alembic migration..."
timeout 30 python -m alembic upgrade head 2>&1 || echo "[$(date +%H:%M:%S)] Alembic skipped (non-fatal)"

# -------- Step 4: Quick import test ----------
echo "[$(date +%H:%M:%S)] Testing Python imports..."
timeout 30 python -c "
import sys, os
sys.path.insert(0, '.')
print('  config...', flush=True)
from app.config import get_settings
print('  config OK', flush=True)
print('  models...', flush=True)
from app.models.base import engine
print('  models OK', flush=True)
print('  security...', flush=True)
from app.security import SecurityHeadersMiddleware
print('  security OK', flush=True)
print('  rate_limit...', flush=True)
from app.middleware.rate_limit import setup_rate_limit
print('  rate_limit OK', flush=True)
print('[$(date +%H:%M:%S)] ALL IMPORTS PASSED — starting uvicorn')
" 2>&1 || echo "[$(date +%H:%M:%S)] WARNING: Import test had errors (non-fatal)"

# -------- Step 5: Start ----------
echo "[$(date +%H:%M:%S)] Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
