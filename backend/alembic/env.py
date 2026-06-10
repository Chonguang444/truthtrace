"""
Alembic 迁移环境配置

支持 SQLite 和 PostgreSQL 双后端。
从 DATABASE_URL_SYNC 环境变量或 alembic.ini 读取数据库 URL。
"""

from logging.config import fileConfig
import os
import re

from sqlalchemy import engine_from_config, pool
from alembic import context

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- 从环境变量覆盖数据库 URL ---
db_url = os.environ.get("DATABASE_URL_SYNC", "")
if db_url:
    # 如果是 asyncpg URL → 转为同步 psycopg2
    db_url = db_url.replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", db_url)

# --- 导入所有模型以触发 Base.metadata 注册 ---
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models.base import Base
from app.models import event, user  # noqa: F401 — 注册所有模型

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式 — 生成 SQL 脚本而不连接数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式 — 连接数据库并执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
