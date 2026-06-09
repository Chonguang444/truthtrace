"""
JWT 令牌生成和验证
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.base import get_db
from app.models.user import User

settings = get_settings()

# --- 密码哈希 ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- JWT 配置 ---
SECRET_KEY = getattr(settings, "jwt_secret_key", None)
if SECRET_KEY is None:
    # 开发环境使用固定密钥，生产环境务必设置环境变量
    import os
    SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "truthtrace-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# --- 密码工具 ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# --- JWT 工具 ---

def create_access_token(user_id: uuid.UUID, username: str, role: str = "user") -> str:
    """生成访问令牌 (短期)"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """生成刷新令牌 (长期)"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码并验证 JWT 令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# --- FastAPI 依赖: 获取当前用户 ---

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    从 JWT 令牌获取当前用户。

    如果请求中没有令牌，返回 None（可选认证）。
    如果令牌无效或用户不存在，返回 None。
    """
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
