"""Admin passwords (bcrypt) and access tokens (JWT, HS256)."""

import time
from typing import Any

import bcrypt
import jwt

ALGORITHM = "HS256"
# bcrypt reads at most 72 bytes of a password.
MAX_PASSWORD_BYTES = 72


class InvalidToken(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:MAX_PASSWORD_BYTES], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:MAX_PASSWORD_BYTES], password_hash.encode())
    except ValueError:  # not a bcrypt hash
        return False


def create_token(subject: str, secret: str, ttl_s: int, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    payload = {"sub": subject, "iat": issued, "exp": issued + ttl_s, "scope": "admin"}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    if payload.get("scope") != "admin":
        raise InvalidToken("wrong scope")
    return payload
