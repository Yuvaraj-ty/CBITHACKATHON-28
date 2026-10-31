"""Email/password auth with an httpOnly JWT session cookie."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request, Response

from lib.sqldb import query_one

COOKIE = "codeatlas_session"
SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
MAX_AGE = 7 * 24 * 3600


def hash_password(pw: str) -> str:
    pw_bytes = pw.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        pw_bytes = pw.encode("utf-8")[:72]
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


def set_session(request: Request, response: Response, user_id: str) -> None:
    token = jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(seconds=MAX_AGE)}, SECRET, algorithm="HS256"
    )
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=MAX_AGE, path="/")


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Session expired")
    user = query_one("SELECT id, email, name, created_at FROM users WHERE id = ?", (payload.get("sub"),))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
