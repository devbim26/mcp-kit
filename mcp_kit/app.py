"""Сборка MCP-сервера: FastMCP + FastAPI + авторизация + /health.

Проект не пишет HTTP-обвязку: он создаёт `McpApp`, регистрирует свои
инструменты и получает готовое приложение в `.app`.
"""
from __future__ import annotations

import functools
import inspect
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional, get_type_hints

import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.middleware.cors import CORSMiddleware

from .audit import AuditLog
from .auth import bearer_middleware, check_key


class McpApp:
    """MCP-сервер: инструменты проекта + инфраструктура каркаса."""

    def __init__(self,
                 name: str,
                 version: str,
                 instructions: str = "",
                 key_env: str = "MCP_KEY",
                 require_key: bool = True,
                 health_extra: Optional[dict] = None,
                 cors_origins: Optional[list] = None,
                 audit_log: Optional[str] = None) -> None:
        self.name = name
        self.version = version
        self.key_env = key_env
        self.require_key = require_key
        self.health_extra = dict(health_extra or {})
        self.cors_origins = list(cors_origins or [])
        self.audit = AuditLog(audit_log)
        self._started = time.time()
        self.mcp = FastMCP(name, instructions=instructions or "",
                           stateless_http=True, json_response=True)
        self._app = self._build()

    # --- сборка ---------------------------------------------------------

    def _build(self) -> FastAPI:
        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            self.check_ready()
            async with self.mcp.session_manager.run():
                yield

        app = FastAPI(title=f"{self.name} MCP", version=self.version,
                      lifespan=lifespan)

        # Bearer регистрируется первым (внутренний слой), CORS — после
        # (внешний слой). В Starlette последний зарегистрированный middleware
        # выполняется на запросе первым, поэтому CORS обрабатывает
        # OPTIONS-preflight к /mcp раньше, чем bearer успевает вернуть 401.
        app.middleware("http")(bearer_middleware(self.key_env))

        if self.cors_origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self.cors_origins,
                allow_methods=["*"],
                allow_headers=["*"],
                expose_headers=["mcp-session-id", "mcp-protocol-version"])

        @app.get("/health")
        async def health() -> dict:
            tools = [t.name for t in await self.mcp.list_tools()]
            out: dict[str, Any] = {
                "status": "ok",
                "name": self.name,
                "version": self.version,
                "transport": "mcp",
                "path": "/mcp",
                "tools": tools,
                "uptime_seconds": round(time.time() - self._started, 1),
            }
            out.update(self.health_extra)
            return out

        # mount("/") перехватывает все пути — /health должен быть выше
        app.mount("/", self.mcp.streamable_http_app())
        return app

    @property
    def app(self) -> FastAPI:
        return self._app

    def check_ready(self) -> None:
        """Проверить конфигурацию до старта; бросает `RuntimeError`."""
        check_key(self.key_env, self.require_key)

    # --- инструменты ---------------------------------------------------

    def add_tool(self, fn: Callable[..., Any], *,
                 name: Optional[str] = None,
                 title: Optional[str] = None,
                 description: Optional[str] = None,
                 read_only: bool = False,
                 destructive: bool = False,
                 idempotent: bool = False,
                 open_world: bool = False) -> Callable[..., Any]:
        """Зарегистрировать инструмент проекта.

        Обёртка добавляет аудит; аннотации MCP описывают, безопасен ли
        вызов (read-only, идемпотентен, не разрушает данные).
        """
        wrapped = self._wrap(fn)
        annotations = ToolAnnotations(
            title=title,
            readOnlyHint=read_only,
            destructiveHint=destructive,
            idempotentHint=idempotent,
            openWorldHint=open_world)
        self.mcp.tool(name=name, title=title, description=description,
                      annotations=annotations)(wrapped)
        return wrapped

    def tool(self, **kwargs):
        """Декоратор инструмента: `app.tool(read_only=True)(fn)`."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            return self.add_tool(fn, **kwargs)
        return decorator

    def _wrap(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Обёртка с аудитом и корректными аннотациями типов.

        `from __future__ import annotations` превращает аннотации в строки.
        FastMCP вычисляет их через `get_type_hints` в глобалах СВОЕГО
        модуля — проектные pydantic-модели там не видны. Поэтому резолвим
        аннотации здесь, в глобалах проекта, и кладём готовые объекты.
        """
        tool_name = getattr(fn, "__name__", "tool")
        audit = self.audit

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                try:
                    out = await fn(*args, **kwargs)
                except Exception as exc:
                    audit.write(tool_name, False,
                                (time.perf_counter() - started) * 1000,
                                error=str(exc))
                    raise
                audit.write(tool_name, True,
                            (time.perf_counter() - started) * 1000)
                return out
        else:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                try:
                    out = fn(*args, **kwargs)
                except Exception as exc:
                    audit.write(tool_name, False,
                                (time.perf_counter() - started) * 1000,
                                error=str(exc))
                    raise
                audit.write(tool_name, True,
                            (time.perf_counter() - started) * 1000)
                return out

        try:
            wrapper.__annotations__ = get_type_hints(fn, include_extras=True)
        except Exception:
            wrapper.__annotations__ = dict(
                getattr(fn, "__annotations__", {}))
        return wrapper


def run(app: McpApp,
        host_env: str = "MCP_HOST",
        port_env: str = "MCP_PORT",
        default_host: str = "127.0.0.1",
        default_port: int = 8808) -> None:
    """Поднять сервер в переднем плане."""
    app.check_ready()
    host = os.environ.get(host_env, "").strip() or default_host
    port = int(os.environ.get(port_env, "").strip() or default_port)
    uvicorn.run(app.app, host=host, port=port)
