"""Каркас MCP-серверов: общая инфраструктура без знания о данных проекта.

Проект импортирует отсюда `McpApp` и регистрирует свои инструменты;
всё остальное (авторизация, /health, формат ошибок, аудит, ограничение
файлов, надзор за процессами) — здесь.
"""
from __future__ import annotations

from .errors import ToolError, call_http

__version__ = "0.1.0"

__all__ = ["__version__", "ToolError", "call_http"]
