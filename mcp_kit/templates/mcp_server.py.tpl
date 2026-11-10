"""MCP-сервер {name}: инструменты проекта.

Запуск:
  python -X utf8 mcp_server.py       # http://127.0.0.1:{port}/mcp
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_kit import McpApp, run

INSTRUCTIONS = (
    "Доступ к данным проекта {name}. Пример: list_example."
)


class ExampleItem(BaseModel):
    """Одна запись."""

    id: str = Field(description="Идентификатор записи")
    title: str = ""


class ExampleList(BaseModel):
    """Список записей."""

    total: int
    items: list[ExampleItem]


async def list_example(limit: int = 20) -> ExampleList:
    """Список записей проекта.

    Args:
        limit: сколько записей вернуть (1..100, по умолчанию 20).
    """
    items = [ExampleItem(id=str(i), title=f"Запись {{i}}")
             for i in range(1, max(1, min(limit, 100)) + 1)]
    return ExampleList(total=len(items), items=items)


def build_app() -> McpApp:
    """Собрать приложение: у каждого экземпляра свой session_manager."""
    app = McpApp(
        name="{name}",
        version="1.0",
        instructions=INSTRUCTIONS,
        key_env="{env_prefix}_KEY",
        require_key=True,
        health_extra={{"project": "{name}"}},
        audit_log=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "out", "logs", "mcp-audit.jsonl"),
    )
    app.add_tool(list_example, read_only=True, idempotent=True)
    return app


_MCP_APP = build_app()
app = _MCP_APP.app


if __name__ == "__main__":
    run(_MCP_APP, host_env="{env_prefix}_HOST",
        port_env="{env_prefix}_PORT", default_port={port})
