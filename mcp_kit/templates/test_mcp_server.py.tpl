"""Тесты MCP-сервера {name}."""
from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_server as mcp_srv

KEY = "test-key"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("{env_prefix}_KEY", KEY)
    return mcp_srv.build_app().app


def test_health(app):
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_mcp_requires_bearer(app):
    body = {{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}}
    with TestClient(app) as client:
        assert client.post("/mcp", json=body).status_code == 401
        ok = client.post("/mcp", json=body,
                         headers={{"Authorization": "Bearer " + KEY}})
    assert ok.status_code != 401


def test_tools_list(app):
    body = {{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}}
    with TestClient(app) as client:
        r = client.post("/mcp", json=body,
                        headers={{"Authorization": "Bearer " + KEY}})
    tools = r.json()["result"]["tools"]
    assert "list_example" in {{t["name"] for t in tools}}
