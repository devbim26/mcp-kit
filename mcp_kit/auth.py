"""Bearer-авторизация для /mcp.

Fail-closed: если переменная с ключом не задана, сервер не поднимается.
Обратный дефолт («ключ не задан — доступ открыт») опасен: опечатка в `.env`
публикует данные наружу.
"""
from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse


def check_key(key_env: str, require_key: bool = True) -> str:
    """Значение ключа; `RuntimeError`, если ключ обязателен, но не задан."""
    key = os.environ.get(key_env, "").strip()
    if require_key and not key:
        raise RuntimeError(
            f"{key_env} не задан — сервер не поднимается "
            f"(fail-closed: без ключа доступ был бы открыт)")
    return key


def bearer_middleware(key_env: str):
    """Middleware: Bearer-ключ обязателен для путей `/mcp`."""
    async def _auth(request: Request, call_next):
        expected = os.environ.get(key_env, "").strip()
        if expected and request.url.path.startswith("/mcp"):
            got = request.headers.get("authorization", "")
            token = got.removeprefix("Bearer ").strip()
            if token != expected:
                return JSONResponse(
                    {"error": "требуется Authorization: Bearer <ключ>"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)

    return _auth
