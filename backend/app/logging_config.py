"""
结构化日志配置 + Sentry 错误监控集成

用法:
    from app.logging_config import setup_logging
    setup_logging()
"""

import logging
import sys
import uuid
from contextvars import ContextVar

# 请求追踪 ID (跨异步任务传递)
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """为每条日志注入 request_id"""

    def filter(self, record):
        rid = request_id_var.get("")
        record.request_id = rid[:8] if rid else "-"
        return True


def setup_logging(level: int = logging.INFO, enable_sentry: bool = False):
    """
    配置结构化日志

    格式: 时间 | 级别 | 模块 | [请求ID] | 消息

    Sentry 集成 (可选):
        设置环境变量 SENTRY_DSN 后自动启用错误上报。
        也可在代码中调用 setup_logging(enable_sentry=True)。
    """
    import os

    # --- 根日志配置 ---
    root = logging.getLogger()
    root.setLevel(level)

    # 清除已有 handler (避免重复)
    for h in root.handlers[:]:
        root.removeHandler(h)

    # 控制台 handler (结构化)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.addFilter(RequestIdFilter())

    # 开发环境使用可读格式，生产环境使用 JSON
    if os.environ.get("ENV", "development") == "production":
        import json

        class JsonFormatter(logging.Formatter):
            def format(self, record):
                return json.dumps({
                    "ts": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "req_id": getattr(record, "request_id", "-"),
                    "msg": record.getMessage(),
                }, ensure_ascii=False)

        console.setFormatter(JsonFormatter())
    else:
        console.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | [%(request_id)s] | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    root.addHandler(console)

    # 降低第三方库日志噪音
    for lib in ("httpx", "httpcore", "urllib3", "asyncio", "aiosqlite", "sqlalchemy.engine"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    # --- Sentry 集成 ---
    sentry_dsn = os.environ.get("SENTRY_DSN", "")
    if (enable_sentry or sentry_dsn) and sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

            sentry_logging = LoggingIntegration(
                level=logging.WARNING,   # WARNING 及以上发送到 Sentry
                event_level=logging.ERROR,  # ERROR 及以上作为 Sentry event
            )

            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
                profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_RATE", "0.1")),
                environment=os.environ.get("ENV", "development"),
                release=os.environ.get("APP_VERSION", "0.1.0"),
                integrations=[
                    sentry_logging,
                    FastApiIntegration(transaction_style="endpoint"),
                    SqlalchemyIntegration(),
                ],
            )
            logging.getLogger("truthtrace").info("Sentry error monitoring enabled")
        except ImportError:
            logging.getLogger("truthtrace").warning(
                "SENTRY_DSN is set but sentry-sdk is not installed. "
                "Install with: pip install sentry-sdk"
            )
        except Exception as e:
            logging.getLogger("truthtrace").warning(f"Sentry init failed: {e}")


# ---------------------------------------------------------------------------
# 快速访问
# ---------------------------------------------------------------------------

def get_logger(name: str = "truthtrace") -> logging.Logger:
    """获取带有项目前缀的 logger"""
    return logging.getLogger(name)
