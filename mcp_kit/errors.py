"""Ошибки инструментов: один формат для всех MCP-клиентов.

Проектные функции (`server.py`) поднимают `HTTPException` или возвращают
`JSONResponse` с кодом ошибки. Клиенту MCP это должно прийти как
`isError=True` с текстом, в котором код виден: «HTTP 404: ...».
"""
from __future__ import annotations

import json
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class ToolError(Exception):
    """Ошибка инструмента: попадёт в MCP-ответ как `isError=True`."""

    def __init__(self, message: str, code: str = "error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def call_http(fn: Callable[..., Any], **kwargs: Any) -> Any:
    """Вызвать функцию проекта, превратив HTTP-ошибку в `ToolError`."""
    try:
        out = fn(**kwargs)
    except HTTPException as exc:
        raise ToolError(f"HTTP {exc.status_code}: {exc.detail}",
                        code=str(exc.status_code)) from exc
    if isinstance(out, JSONResponse):
        body = out.body.decode("utf-8", "replace")
        try:
            body = json.dumps(json.loads(body), ensure_ascii=False)
        except ValueError:
            pass
        raise ToolError(f"HTTP {out.status_code}: {body}",
                        code=str(out.status_code))
    return out
