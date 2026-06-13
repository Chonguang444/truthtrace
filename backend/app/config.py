"""
TruthTrace 全局配置
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用
    app_name: str = "TruthTrace - 平浪散暴"
    app_version: str = "0.1.0"
    debug: bool = False

    # 安全
    jwt_secret_key: str = ""  # 必须通过环境变量 JWT_SECRET_KEY 设置 (python -c "import secrets; print(secrets.token_urlsafe(64))")
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30  # 30 minutes (best practice)
    jwt_refresh_expire_days: int = 7

    # CORS (逗号分隔的允许域名，或 JSON 数组。留空使用 localhost 默认值)
    cors_origins: str = ""  # e.g. "https://app.vercel.app,https://www.example.com"

    # AI/LLM
    anthropic_api_key: str = ""  # Claude API 密钥，用于辟谣工坊/LLM增强分析

    # 数据库
    database_url: str = ""  # 必须通过 DATABASE_URL 环境变量设置
    database_url_sync: str = ""  # 必须通过 DATABASE_URL_SYNC 环境变量设置

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # 爬虫配置
    crawler_concurrency: int = 10
    crawler_timeout: int = 30
    crawler_user_agents: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    ]

    # Google Fact Check Tools API (第三方事实核查交叉验证)
    google_fact_check_api_key: str = ""
    google_fact_check_base_url: str = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    # NLP
    spacy_model: str = "zh_core_web_sm"
    sentence_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def _normalize_database_url(url: str) -> str:
    """Normalize DATABASE_URL for SQLAlchemy async engine compatibility.

    Render and many platforms provide DATABASE_URL as:
      postgres://user:pass@host:port/dbname
      postgresql://user:pass@host:port/dbname

    SQLAlchemy's create_async_engine() requires the async driver prefix:
      postgresql+asyncpg://user:pass@host:port/dbname

    This function transforms the URL automatically so the app works
    out-of-the-box on Render, Railway, Fly.io, and local PostgreSQL.
    """
    if not url:
        return url
    # Already has an async driver — nothing to do
    if "+asyncpg" in url or "+aiosqlite" in url:
        return url
    # postgres:// → postgresql+asyncpg:// (Render default)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    # postgresql:// → postgresql+asyncpg:// (standard PostgreSQL URL)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.database_url = _normalize_database_url(s.database_url)
    return s
