import uuid

import pytest
from fastapi import HTTPException

import app.security as security
from app.security import AuthUser, _parse_bearer, _user_from_payload, require_owned_dog


class StubSession:
    def __init__(self, scalar_value):
        self.scalar_value = scalar_value
        self.statement = None

    def scalar(self, statement):
        self.statement = statement
        return self.scalar_value


class StubResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_parse_bearer_accepts_valid_header():
    assert _parse_bearer("Bearer abc.def.ghi") == "abc.def.ghi"


def test_parse_bearer_rejects_missing_or_malformed_header():
    with pytest.raises(HTTPException) as missing:
        _parse_bearer(None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as malformed:
        _parse_bearer("Basic abc")
    assert malformed.value.status_code == 401


def test_user_from_payload_parses_supabase_user():
    user_id = uuid.uuid4()
    user = _user_from_payload({"id": str(user_id), "email": "owner@example.com"})
    assert user == AuthUser(id=user_id, email="owner@example.com")


def test_user_from_payload_rejects_invalid_user_id():
    with pytest.raises(HTTPException) as exc:
        _user_from_payload({"id": "not-a-uuid"})
    assert exc.value.status_code == 401


def test_verify_token_calls_supabase_and_caches(monkeypatch):
    security._AUTH_CACHE.clear()
    user_id = uuid.uuid4()
    calls = []

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        return StubResponse(200, {"id": str(user_id), "email": "owner@example.com"})

    monkeypatch.setattr(security.httpx, "get", fake_get)

    first = security._verify_token("token-1")
    second = security._verify_token("token-1")

    assert first == AuthUser(id=user_id, email="owner@example.com")
    assert second == first
    assert len(calls) == 1
    assert calls[0][0] == "https://example.supabase.co/auth/v1/user"
    assert calls[0][1]["Authorization"] == "Bearer token-1"
    assert calls[0][1]["apikey"] == "anon-key"


def test_verify_token_maps_invalid_session_to_401(monkeypatch):
    security._AUTH_CACHE.clear()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(
        security.httpx,
        "get",
        lambda *args, **kwargs: StubResponse(401, {"message": "invalid"}),
    )

    with pytest.raises(HTTPException) as exc:
        security._verify_token("bad-token")

    assert exc.value.status_code == 401


def test_require_owned_dog_returns_matching_dog():
    expected = object()
    db = StubSession(expected)
    user = AuthUser(id=uuid.uuid4(), email="owner@example.com")

    assert require_owned_dog(db, uuid.uuid4(), user) is expected
    assert db.statement is not None


def test_require_owned_dog_returns_404_when_query_finds_no_owned_dog():
    db = StubSession(None)
    user = AuthUser(id=uuid.uuid4(), email="owner@example.com")

    with pytest.raises(HTTPException) as exc:
        require_owned_dog(db, uuid.uuid4(), user)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Dog not found."
