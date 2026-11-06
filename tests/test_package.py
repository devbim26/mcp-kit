"""Ядро доступно для импорта без установки."""
from __future__ import annotations

import mcp_kit


def test_version_is_exposed():
    assert isinstance(mcp_kit.__version__, str)
    assert mcp_kit.__version__


def test_public_api_is_declared():
    # экспорт наполняется по мере появления модулей; здесь — базовый минимум
    assert hasattr(mcp_kit, "__all__")
