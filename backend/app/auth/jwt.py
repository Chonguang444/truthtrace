"""
JWT 令牌生成和验证
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt  # PyJWT — 纯 Python，无需 Rust 编译
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.base import get_db
from app.models.user import User

settings = get_settings()

# --- 密码哈希 (bcrypt — 抗GPU加速攻击) ---
# bcrypt 懒加载: Render 免费层无 Rust 编译器时回退到 hashlib.pbkdf2_hmac
# 直接使用 bcrypt 而非 passlib (passlib 已停止维护，与新版 bcrypt 不兼容)
_bcrypt = None
_BCRYPT_ROUNDS = 12  # 成本因子 (12 = ~0.3s/hash)
_PBKDF2_ITERATIONS = 600_000  # OWASP 2025 推荐 pbkdf2 迭代数

def _get_bcrypt():
    global _bcrypt
    if _bcrypt is None:
        try:
            import bcrypt as _mod
            _bcrypt = _mod
        except ImportError:
            pass
    return _bcrypt

# --- JWT 配置 ---
import os
import secrets as _secrets

SECRET_KEY = getattr(settings, "jwt_secret_key", None) or os.environ.get("JWT_SECRET_KEY")

# 可预测的弱密钥模式 — 防止开发者使用占位符密钥
_WEAK_KEY_PATTERNS = [
    r"^truthtrace-dev-",          # 预定开发模式
    r"^dev-",                     # 通用 dev 前缀
    r"^test-",                    # 测试密钥
    r"^changeme",                 # 占位符
    r"^secret",                   # 通用 secret 词
    r"^your-",                    # 模板占位符
    r"^please-change",            # 英文占位符
    r"^(12345|abcde|password)",   # 玩具密钥
]


def _is_weak_key(key: str) -> bool:
    """检测密钥是否为可预测的弱密钥"""
    if len(key) < 32:
        return True  # HS256 需要至少 256-bit 密钥 (32 bytes)
    for pattern in _WEAK_KEY_PATTERNS:
        if re.match(pattern, key, re.IGNORECASE):
            return True
    return False


if SECRET_KEY is None or SECRET_KEY == "":
    # 开发环境: 生成随机临时密钥 (每次重启令牌失效 — 仅影响开发体验)
    SECRET_KEY = _secrets.token_urlsafe(64)
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY 未设置! 已生成临时随机密钥。\n"
        "生产环境必须设置 JWT_SECRET_KEY 环境变量。\n"
        "设置方法: 在 .env 中添加 JWT_SECRET_KEY=<随机64位安全密钥>\n"
        "所有现有令牌将在下次重启后失效。",
        RuntimeWarning,
    )
elif _is_weak_key(SECRET_KEY):
    raise RuntimeError(
        "检测到弱 JWT 密钥，拒绝启动。\n"
        "请设置环境变量 JWT_SECRET_KEY 为一个随机生成的安全密钥。\n"
        "可以用: python -c \"import secrets; print(secrets.token_urlsafe(64))\"\n"
        "将此输出添加到 .env: JWT_SECRET_KEY=<生成的密钥>\n"
        f"当前密钥长度: {len(SECRET_KEY)} 字符 (需要至少 32 字符)"
    )
ALGORITHM = getattr(settings, "jwt_algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, "jwt_access_expire_minutes", 60 * 24)
REFRESH_TOKEN_EXPIRE_DAYS = getattr(settings, "jwt_refresh_expire_days", 30)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# --- 密码工具 ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码 — 优先 bcrypt，回退 hashlib.pbkdf2_hmac"""
    bc = _get_bcrypt()
    if bc is not None:
        try:
            password_bytes = plain_password.encode("utf-8")
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            return bc.checkpw(password_bytes, hashed_password.encode("utf-8"))
        except Exception:
            pass
    # Fallback: pbkdf2_hmac (OWASP 推荐的 bcrypt 替代)
    import hashlib
    try:
        parts = hashed_password.split("$")
        if len(parts) == 4 and parts[0] == "pbkdf2":
            salt = bytes.fromhex(parts[2])
            expected = bytes.fromhex(parts[3])
            dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
            return dk == expected
    except Exception:
        pass
    return False


def hash_password(password: str) -> str:
    """哈希密码 — 优先 bcrypt，回退 hashlib.pbkdf2_hmac"""
    bc = _get_bcrypt()
    if bc is not None:
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        salt = bc.gensalt(rounds=_BCRYPT_ROUNDS)
        return bc.hashpw(password_bytes, salt).decode("utf-8")
    # Fallback: pbkdf2_hmac (OWASP 推荐)
    import hashlib, os as _os
    salt = _os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


# --- JWT 工具 ---

def create_access_token(user_id: uuid.UUID, username: str, role: str = "user") -> str:
    """生成访问令牌 (短期)"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """生成刷新令牌 (长期)"""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码并验证 JWT 令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


# --- FastAPI 依赖: 获取当前用户 ---

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    从 JWT 令牌获取当前用户。

    优先从 Authorization Bearer 头获取令牌；
    其次从 httpOnly Cookie (access_token) 获取。

    如果请求中没有令牌，返回 None（可选认证）。
    如果令牌无效或用户不存在，返回 None。
    """
    # Cookie 回退 (用于页面刷新时的会话恢复)
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        return None

    payload = decode_token(token)
    if not payload:
        return None

    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        return user
    return None


async def get_current_active_user(
    current_user: User | None = Depends(get_current_user),
) -> User:
    """获取当前活跃用户，未认证则 401"""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """获取管理员用户，非管理员则 403"""
    if current_user.role.value not in ("admin", "analyst"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
