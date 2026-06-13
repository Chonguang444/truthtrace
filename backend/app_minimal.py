"""Minimal Render test — no app imports, just prove the platform works."""
from fastapi import FastAPI
import os, sys

app = FastAPI()

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "python": sys.version,
        "db_url_set": bool(os.environ.get("DATABASE_URL")),
    }

@app.get("/")
async def root():
    return {"message": "Hello from Render! Platform works."}
