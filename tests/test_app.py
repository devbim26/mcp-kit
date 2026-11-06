"""McpApp: HTTP-хост, /health, fail-closed, подключение MCP."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_kit.app import McpApp


def _app(**kwargs):
    kwargs.setdefault("name", "probe")
    kwargs.setdefault("version", "1.0")
    return McpApp(**kwargs)


def test_health_is_open_and_lists_tools(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    app = _app(key_env="TEST_KEY")

    with TestClient(app.app) as client:
        r = client.get("/health")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["name"] == "probe"
    assert body["transport"] == "mcp"
    assert body["path"] == "/mcp"
    assert body["tools"] == []
    assert body["uptime_seconds"] >= 0


def test_health_extra_is_merged(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    app = _app(key_env="TEST_KEY", health_extra={"doc": "АР"})

    with TestClient(app.app) as client:
        body = client.get("/health").json()

    assert body["doc"] == "АР"


def test_startup_fails_without_key(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    app = _app(key_env="TEST_KEY")

    with pytest.raises(RuntimeError) as exc:
        with TestClient(app.app):
            pass

    assert "TEST_KEY" in str(exc.value)


def test_startup_succeeds_when_key_not_required(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    app = _app(key_env="TEST_KEY", require_key=False)

    with TestClient(app.app) as client:
        assert client.get("/health").status_code == 200


def test_mcp_requires_bearer(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    app = _app(key_env="TEST_KEY")
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    with TestClient(app.app) as client:
        no_key = client.post("/mcp", json=body)
        with_key = client.post("/mcp", json=body,
                               headers={"Authorization": "Bearer secret"})

    assert no_key.status_code == 401
    assert with_key.status_code != 401


def test_cors_is_disabled_by_default(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    app = _app(key_env="TEST_KEY")

    with TestClient(app.app) as client:
        r = client.get("/health",
                       headers={"Origin": "https://example.com"})

    assert "access-control-allow-origin" not in r.headers


def test_cors_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    app = _app(key_env="TEST_KEY", cors_origins=["https://example.com"])

    with TestClient(app.app) as client:
        r = client.get("/health",
                       headers={"Origin": "https://example.com"})

    assert r.headers.get("access-control-allow-origin") == \
        "https://example.com"
