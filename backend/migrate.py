#!/usr/bin/env python3
"""
TruthTrace 数据库迁移管理工具

用法:
  python migrate.py check        # 检查迁移状态
  python migrate.py upgrade      # 运行所有待处理的迁移
  python migrate.py downgrade    # 回滚最近的迁移
  python migrate.py history      # 查看迁移历史
  python migrate.py generate     # 生成新的自动迁移
"""
import sys
import os

# Setup path
sys.path.insert(0, os.path.dirname(__file__))

from alembic.config import Config
from alembic import command
from app.config import get_settings

settings = get_settings()
sync_url = settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")

alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

if cmd == "check":
    print(f"Database: {sync_url}")
    command.current(alembic_cfg)

elif cmd == "upgrade":
    print(f"Upgrading to head... ({sync_url})")
    command.upgrade(alembic_cfg, "head")
    print("Done.")

elif cmd == "downgrade":
    revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
    print(f"Downgrading to {revision}...")
    command.downgrade(alembic_cfg, revision)
    print("Done.")

elif cmd == "history":
    command.history(alembic_cfg)

elif cmd == "generate":
    msg = sys.argv[2] if len(sys.argv) > 2 else "auto_migration"
    print(f"Generating migration: {msg}")
    command.revision(alembic_cfg, autogenerate=True, message=msg)
    print("Done. Check alembic/versions/ for the new file.")

elif cmd == "stamp":
    revision = sys.argv[2] if len(sys.argv) > 2 else "head"
    command.stamp(alembic_cfg, revision)
    print(f"Stamped at {revision}")

else:
    print(__doc__)
    print("Valid commands: check, upgrade, downgrade, history, generate, stamp")
