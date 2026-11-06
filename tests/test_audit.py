"""Журнал вызовов: одна JSON-строка на вызов."""
from __future__ import annotations

import json

from mcp_kit.audit import AuditLog


def test_write_appends_json_line(tmp_path):
    path = tmp_path / "logs" / "audit.jsonl"
    log = AuditLog(str(path))

    log.write("search", True, 12.345)
    log.write("extract_stamps", False, 7.0, error="путь вне корней")

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["tool"] == "search"
    assert first["ok"] is True
    assert first["duration_ms"] == 12.35
    assert "error" not in first

    second = json.loads(lines[1])
    assert second["ok"] is False
    assert second["error"] == "путь вне корней"
    assert second["ts"]


def test_disabled_log_writes_nothing(tmp_path):
    log = AuditLog(None)
    log.write("search", True, 1.0)  # не должно бросить


def test_write_error_does_not_raise(tmp_path):
    # каталог-файл вместо каталога → запись невозможна, но вызов не падает
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    log = AuditLog(str(blocker / "audit.jsonl"))

    log.write("search", True, 1.0)
