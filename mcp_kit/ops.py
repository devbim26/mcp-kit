"""Надзор за процессами сервера: задачи Планировщика Windows.

Проект описывает свои задачи в `ops/tasks.json`; этот модуль превращает
описание в готовые команды и вызывает общий `register_tasks.ps1`.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Optional

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "ops", "register_tasks.ps1")


@dataclass(frozen=True)
class TaskSpec:
    """Готовая к регистрации задача Планировщика."""

    name: str
    execute: str
    arguments: str
    working_dir: str
    delay_seconds: int = 0
    log: str = ""
    dedupe: Optional[dict] = None


def load_spec(path: str) -> dict[str, Any]:
    """Прочитать описание задач."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_task_specs(spec: dict[str, Any], root: str,
                      python: str = "",
                      cloudflared: str = "") -> list[TaskSpec]:
    """Развернуть описание задач в готовые команды.

    Сборку делает Python, а не PowerShell: описание проекта читается в
    одном месте, а PS1 получает уже готовые строки — иначе правила
    формирования команд разъезжаются между двумя языками.
    """
    root = os.path.abspath(root)
    log_dir = os.path.join(root, "out", "logs")
    tasks: list[TaskSpec] = []

    for item in spec.get("tasks", []):
        kind = item.get("kind", "python")
        name = item["name"]
        delay = int(item.get("delay_seconds", 0))
        log_path = os.path.join(log_dir, item.get("log", f"{name}.log"))
        dedupe: Optional[dict] = None

        if kind == "python":
            exe = python or "python"
            entry = os.path.join(root, item["entry"])
            inner = f'"{exe}" -X utf8 "{entry}"'
        elif kind == "cloudflared":
            exe = cloudflared or item.get("cloudflared") or "cloudflared"
            inner = (f'"{exe}" tunnel --config "{item["config"]}" '
                     f'run {item["tunnel"]}')
            dedupe = {"kind": "cloudflared",
                      "config": item["config"],
                      "tunnel": item["tunnel"]}
        else:
            raise ValueError(f"неизвестный kind задачи: {kind}")

        # cmd.exe /c "команда >> лог 2>&1": без перенаправления вывод
        # задачи Планировщика некуда смотреть.
        arguments = f'/c ""{inner} >> "{log_path}" 2>&1"'
        tasks.append(TaskSpec(name=name, execute="cmd.exe",
                              arguments=arguments, working_dir=root,
                              delay_seconds=delay, log=log_path,
                              dedupe=dedupe))

    return tasks


def resolved_payload(specs: list[TaskSpec], root: str,
                     ports: Optional[list] = None) -> dict[str, Any]:
    """Разрешённое описание — то, что читает PowerShell-скрипт."""
    return {
        "root": root,
        "ports": list(ports or []),
        "tasks": [
            {
                "name": t.name,
                "execute": t.execute,
                "arguments": t.arguments,
                "working_dir": t.working_dir,
                "delay_seconds": t.delay_seconds,
                "log": t.log,
                "dedupe": t.dedupe,
            }
            for t in specs
        ],
    }


def run_ps1(action: str, resolved_path: str,
            script_path: str | None = None) -> int:
    """Вызвать `register_tasks.ps1` с разрешённым описанием."""
    script = script_path or _SCRIPT
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", script, "-Spec", resolved_path, "-Action", action]
    proc = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=__import__("sys").stderr)
    return proc.returncode
