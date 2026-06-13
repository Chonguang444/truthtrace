#!/usr/bin/env python3
"""
TruthTrace — Render 诊断启动脚本
每一步都打印到 stdout（Render 日志捕获），用于精确定位启动崩溃点。
用法：
  python startup_diag.py
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""

import sys, os, traceback, time

def log(msg: str):
    print(f"[DIAG {time.strftime('%H:%M:%S')}] {msg}", flush=True)

log(f"Python {sys.version}")
log(f"cwd={os.getcwd()}")
log(f"DATABASE_URL={'[SET]' if os.environ.get('DATABASE_URL') else '[NOT SET]'}")
log(f"PORT={'[SET]' if os.environ.get('PORT') else '[NOT SET]'}")

# Step 1: config
log("Step 1/8: Loading config...")
try:
    sys.path.insert(0, '.')
    from app.config import get_settings, _normalize_database_url
    settings = get_settings()
    log(f"  OK: app_name={settings.app_name}, db_url={'[SET]' if settings.database_url else '[EMPTY]'}")
    if settings.database_url:
        log(f"  Normalized URL: {_normalize_database_url(settings.database_url)[:80]}...")
except Exception as e:
    log(f"  FATAL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 2: models
log("Step 2/8: Loading models (creates engine)...")
try:
    from app.models.base import engine, Base
    log("  OK")
except Exception as e:
    log(f"  FATAL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 3: security
log("Step 3/8: Loading security middleware...")
try:
    from app.security import SecurityHeadersMiddleware
    log("  OK")
except Exception as e:
    log(f"  FATAL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 4: rate limit
log("Step 4/8: Loading rate limiter...")
try:
    from app.middleware.rate_limit import setup_rate_limit
    log("  OK")
except Exception as e:
    log(f"  FATAL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 5: API modules
log("Step 5/8: Loading API modules...")
for mod in ["search", "events", "trace", "rumors", "stats", "auth", "ws", "export",
             "monitor", "admin", "feedback", "reporting", "video", "system",
             "literacy", "situational", "community", "debunk_studio", "vertical_medical",
             "developer", "quick_check", "analytics", "detectzoo", "new_engines"]:
    try:
        __import__(f"app.api.{mod}")
    except Exception as e:
        log(f"  WARN api.{mod}: {type(e).__name__}: {e}")

log("  API modules loaded")

# Step 6: lifespan (test database connection)
log("Step 6/8: Testing database connection...")
try:
    from sqlalchemy import text
    import asyncio
    async def test_db():
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        log("  DB connection OK")
    asyncio.new_event_loop().run_until_complete(test_db())
except Exception as e:
    log(f"  WARN DB connection failed: {e} (non-fatal, lifespan handles this)")

# Step 7: Create FastAPI app
log("Step 7/8: Creating FastAPI app...")
try:
    from app.main import app
    log(f"  OK: {len([r for r in app.routes if hasattr(r, 'path')])} routes")
except Exception as e:
    log(f"  FATAL: {e}")
    traceback.print_exc()
    sys.exit(1)

log("Step 8/8: All checks passed — ready for uvicorn!")
log("DIAGNOSTICS COMPLETE — starting uvicorn now")
