"""Bearer-авторизация: ключ обязателен (fail-closed) и проверяется на /mcp."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_kit.auth import bearer_middleware, check_key


def _app(key_env: str) -> FastAPI:
    app = FastAPI()
    app.middleware("http")(bearer_middleware(key_env))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/mcp")
    async def mcp():
        return {"ok": True}

    return app


def test_check_key_returns_value(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    assert check_key("TEST_KEY") == "secret"


def test_check_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        check_key("TEST_KEY")
    assert "TEST_KEY" in str(exc.value)


def test_check_key_allows_missing_when_not_required(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    assert check_key("TEST_KEY", require_key=False) == ""


def test_mcp_requires_bearer(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    app = _app("TEST_KEY")
    with TestClient(app) as client:
        no_key = client.post("/mcp")
        wrong = client.post("/mcp",
                            headers={"Authorization": "Bearer nope"})
        good = client.post("/mcp",
                           headers={"Authorization": "Bearer secret"})
    assert no_key.status_code == 401
    assert wrong.status_code == 401
    assert good.status_code == 200


def test_health_stays_open(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    app = _app("TEST_KEY")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
