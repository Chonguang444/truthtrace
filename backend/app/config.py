"""
TruthTrace 全局配置
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用
    app_name: str = "TruthTrace - 平浪散暴"
    app_version: str = "0.1.0"
    debug: bool = True

    # 安全
    jwt_secret_key: str = ""  # 空值触发自动生成 — 生产环境必须显式设置
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60 * 24  # 24 hours
    jwt_refresh_expire_days: int = 30

    # CORS (逗号分隔的允许域名，或 JSON 数组。留空使用 localhost 默认值)
    cors_origins: str = ""  # e.g. "https://app.vercel.app,https://www.example.com"

    # AI/LLM
    anthropic_api_key: str = ""  # Claude API 密钥，用于辟谣工坊/LLM增强分析

    # 数据库
    database_url: str = "postgresql+asyncpg://truthtrace:truthtrace_dev@localhost:5432/truthtrace"
    database_url_sync: str = "postgresql://truthtrace:truthtrace_dev@localhost:5432/truthtrace"

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

    # NLP
    spacy_model: str = "zh_core_web_sm"
    sentence_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
