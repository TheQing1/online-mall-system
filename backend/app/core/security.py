from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt import InvalidTokenError
import bcrypt

from app.core.config import settings

# 从 python-jose 迁到 PyJWT 的原因与验证记录：
#
# python-jose 3.3.0 有 4 条已知 CVE（含算法混淆与解压型 DoS），而它承担
# **全部认证**——项目里最高风险的一个依赖。PyJWT 是同类库中维护更活跃的选择。
#
# 迁移面极小：全仓只有本文件用到它，且只用到 encode / decode 两个函数。
# 两处行为差异都已核实：
#   1. 异常类型：jose 的 `JWTError` 对应 PyJWT 的 `InvalidTokenError`
#      （`ExpiredSignatureError` / `InvalidSignatureError` 都是它的子类）；
#   2. 令牌格式：两者都是标准 JWS，**互相可解**。已实测「jose 签发 → PyJWT 解码」
#      与反向都能通过，所以升级不会让已登录用户掉线，回滚也无需重新登录。
#
# 注意 PyJWT 的 decode 必须显式传 `algorithms=[...]`（不接受默认值），
# 这正是抵御算法混淆攻击的关键——不要为了省事把它写成从 token 头里读。


def hash_password(password: str) -> str:
    # bcrypt 限制密码最大 72 字节
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt 限制密码最大 72 字节
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """解码并校验 token；无效/过期/签名错误一律返回 None。

    调用方（依赖注入、限流里的身份识别）只关心「有没有身份」，不区分失败原因，
    所以这里统一收敛成 None——也避免把「签名不对」和「过期」的差异暴露出去。
    """
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except InvalidTokenError:
        return None
