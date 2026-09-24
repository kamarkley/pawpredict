from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware, RequestContextMiddleware


def test_request_context_adds_request_id_and_server_timing():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get('/ok')
    def ok():
        return {'ok': True}

    client = TestClient(app)
    response = client.get('/ok', headers={'X-Request-ID': 'test-request-id'})

    assert response.status_code == 200
    assert response.headers['X-Request-ID'] == 'test-request-id'
    assert response.headers['Server-Timing'].startswith('app;dur=')


def test_rate_limit_returns_429_after_limit():
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=10)

    @app.get('/limited')
    def limited():
        return {'ok': True}

    client = TestClient(app)
    for _ in range(10):
        assert client.get('/limited').status_code == 200

    limited = client.get('/limited')
    assert limited.status_code == 429
    assert int(limited.headers['Retry-After']) >= 1
