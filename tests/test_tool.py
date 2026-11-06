"""Инструменты: аннотации, структурированный вывод, аудит."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from mcp_kit.app import McpApp


class SheetRow(BaseModel):
    """Строка листа."""

    sheet_no: str = Field(description="Номер листа из штампа")
    title: str = ""


class SheetList(BaseModel):
    """Список листов."""

    doc: str
    sheets_total: int
    sheets: list[SheetRow]


@pytest.fixture
def built(tmp_path):
    """McpApp с двумя инструментами: модельный и строковый."""
    app = McpApp(name="probe", version="1.0", key_env="TEST_KEY",
                 audit_log=str(tmp_path / "audit.jsonl"))
    import os
    os.environ["TEST_KEY"] = "secret"

    @app.tool(read_only=True, idempotent=True)
    async def list_sheets() -> SheetList:
        """Список листов."""
        return SheetList(doc="АР", sheets_total=1,
                         sheets=[SheetRow(sheet_no="3", title="План")])

    @app.tool()
    async def raw_text() -> str:
        """Строка без структуры."""
        return "готово"

    return app


def _rpc(client, method, params=None, tool_id=1):
    body = {"jsonrpc": "2.0", "id": tool_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", json=body,
                       headers={"Authorization": "Bearer secret",
                                "Accept": "application/json, text/event-stream"})


def test_tools_list_exposes_schema_and_annotations(built):
    app = built
    with TestClient(app.app) as client:
        r = _rpc(client, "tools/list")

    assert r.status_code == 200
    tools = r.json()["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == {"list_sheets", "raw_text"}

    by_name = {t["name"]: t for t in tools}
    assert by_name["list_sheets"]["outputSchema"]["title"] == "SheetList"
    ann = by_name["list_sheets"]["annotations"]
    assert ann["readOnlyHint"] is True
    assert ann["idempotentHint"] is True
    assert ann["destructiveHint"] is False


def test_tool_call_returns_text_and_structured(built):
    app = built
    with TestClient(app.app) as client:
        r = _rpc(client, "tools/call",
                 {"name": "list_sheets", "arguments": {}})

    result = r.json()["result"]
    payload = json.loads(result["content"][0]["text"])
    assert payload["sheets"][0]["sheet_no"] == "3"
    assert result["structuredContent"]["sheets_total"] == 1
    assert result["structuredContent"]["sheets"][0]["sheet_no"] == "3"


def test_string_tool_has_no_structured_content(built):
    app = built
    with TestClient(app.app) as client:
        r = _rpc(client, "tools/call", {"name": "raw_text", "arguments": {}})

    result = r.json()["result"]
    assert "готово" in result["content"][0]["text"]


def test_tool_error_becomes_is_error(built):
    app = built

    @app.tool()
    async def failing() -> str:
        """Всегда падает."""
        raise RuntimeError("не вышло")

    with TestClient(app.app) as client:
        r = _rpc(client, "tools/call", {"name": "failing", "arguments": {}})

    result = r.json()["result"]
    assert result["isError"] is True
    assert "не вышло" in result["content"][0]["text"]


def test_audit_log_records_call(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    app = McpApp(name="probe", version="1.0", key_env="TEST_KEY",
                 audit_log=str(log_path))
    import os
    os.environ["TEST_KEY"] = "secret"

    @app.tool(read_only=True)
    async def ping() -> str:
        """Пинг."""
        return "pong"

    with TestClient(app.app) as client:
        _rpc(client, "tools/call", {"name": "ping", "arguments": {}})

    lines = Path(log_path).read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["tool"] == "ping"
    assert rec["ok"] is True


def test_audit_log_records_failure(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    app = McpApp(name="probe", version="1.0", key_env="TEST_KEY",
                 audit_log=str(log_path))
    import os
    os.environ["TEST_KEY"] = "secret"

    @app.tool()
    async def failing() -> str:
        """Падает."""
        raise RuntimeError("бум")

    with TestClient(app.app) as client:
        _rpc(client, "tools/call", {"name": "failing", "arguments": {}})

    rec = json.loads(Path(log_path).read_text(encoding="utf-8").strip())
    assert rec["ok"] is False
    assert "бум" in rec["error"]
