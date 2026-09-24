from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: str | None


_AUTH_CACHE: dict[str, tuple[float, AuthUser]] = {}
_AUTH_CACHE_LOCK = threading.Lock()
_AUTH_CACHE_SECONDS = 30.0


def _auth_config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on the API.",
        )
    return url, key


def _parse_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def _user_from_payload(payload: dict[str, Any]) -> AuthUser:
    raw_id = payload.get("id")
    if not raw_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.")
    try:
        user_id = uuid.UUID(str(raw_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.") from exc
    email = payload.get("email")
    return AuthUser(id=user_id, email=str(email) if email else None)


def _verify_token(token: str) -> AuthUser:
    now = time.monotonic()
    with _AUTH_CACHE_LOCK:
        cached = _AUTH_CACHE.get(token)
        if cached and cached[0] > now:
            return cached[1]
        if cached is not None:
            _AUTH_CACHE.pop(token, None)
        # Keep the short-lived cache bounded in long-running API workers.
        if len(_AUTH_CACHE) > 2048:
            expired = [key for key, (expires_at, _) in _AUTH_CACHE.items() if expires_at <= now]
            for key in expired:
                _AUTH_CACHE.pop(key, None)
            while len(_AUTH_CACHE) > 2048:
                _AUTH_CACHE.pop(next(iter(_AUTH_CACHE)))

    url, anon_key = _auth_config()
    try:
        response = httpx.get(
            f"{url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": anon_key},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        ) from exc

    if response.status_code in {401, 403}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        )

    user = _user_from_payload(response.json())
    with _AUTH_CACHE_LOCK:
        _AUTH_CACHE[token] = (now + _AUTH_CACHE_SECONDS, user)
    return user


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser:
    return _verify_token(_parse_bearer(authorization))


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
DatabaseSession = Annotated[Session, Depends(get_db)]


def require_owned_dog(db: Session, dog_id: uuid.UUID, user: AuthUser) -> Dog:
    dog = db.scalar(
        select(Dog).where(
            Dog.id == dog_id,
            Dog.owner_user_id == user.id,
        )
    )
    if dog is None:
        # Deliberately use 404 so callers cannot enumerate another account's dog IDs.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found.")
    return dog


def require_resource_dog(db: Session, dog_id: uuid.UUID, user: AuthUser) -> None:
    require_owned_dog(db, dog_id, user)
