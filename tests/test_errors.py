"""ToolError и маппинг HTTP-ошибок в единый формат."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from mcp_kit.errors import ToolError, call_http


def test_tool_error_keeps_message_and_code():
    err = ToolError("путь вне корней", code="path_not_allowed")
    assert err.code == "path_not_allowed"
    assert str(err) == "путь вне корней"
    assert err.message == "путь вне корней"


def test_call_http_passes_through_result():
    assert call_http(lambda x: x * 2, x=21) == 42


def test_call_http_maps_http_exception():
    def boom():
        raise HTTPException(404, "лист не найден")

    with pytest.raises(ToolError) as exc:
        call_http(boom)

    assert exc.value.code == "404"
    assert "404" in str(exc.value)
    assert "лист не найден" in str(exc.value)


def test_call_http_maps_json_response():
    def conflict():
        return JSONResponse(status_code=409,
                            content={"error": "неоднозначно"})

    with pytest.raises(ToolError) as exc:
        call_http(conflict)

    assert exc.value.code == "409"
    assert "409" in str(exc.value)
    assert "неоднозначно" in str(exc.value)


def test_call_http_keeps_non_json_body():
    def raw():
        return JSONResponse(status_code=422, content="не разобрано")

    with pytest.raises(ToolError) as exc:
        call_http(raw)

    assert exc.value.code == "422"
    assert "не разобрано" in str(exc.value)
