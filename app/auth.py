from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash

from app.config import Settings


password_hash = PasswordHash.recommended()


def verify_login(settings: Settings, username: str, password: str) -> bool:
    if not settings.admin_password_hash:
        return False
    username_ok = secrets.compare_digest(username, settings.admin_username)
    try:
        password_ok = password_hash.verify(password, settings.admin_password_hash)
    except Exception:
        password_ok = False
    return username_ok and password_ok


def require_login(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def require_csrf(request: Request, submitted: str) -> None:
    expected = request.session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected, submitted):
        raise HTTPException(status_code=403, detail="Invalid form token")
