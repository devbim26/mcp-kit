"""Журнал вызовов инструментов (JSONL).

Единственный способ узнать, кто и что читал через туннель. Запись
асинхронна по отношению к вызову и не должна его ломать: ошибка записи
глотается.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any


class AuditLog:
    """Построчный JSON-журнал вызовов."""

    def __init__(self, path: str | None) -> None:
        self.path = path
        self._lock = threading.Lock()

    def write(self, tool: str, ok: bool, duration_ms: float,
              error: str | None = None, **extra: Any) -> None:
        if not self.path:
            return
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "ok": bool(ok),
            "duration_ms": round(float(duration_ms), 2),
        }
        if error:
            record["error"] = error
        record.update(extra)
        line = json.dumps(record, ensure_ascii=False)
        try:
            with self._lock:
                folder = os.path.dirname(self.path)
                if folder:
                    os.makedirs(folder, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except OSError:
            pass
