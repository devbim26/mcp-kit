"""Описание задач Планировщика превращается в готовые команды."""
from __future__ import annotations

import json

from mcp_kit.ops import build_task_specs, load_spec


def test_build_python_task(tmp_path):
    spec = {
        "project": "drawing5",
        "ports": [8808],
        "tasks": [
            {"name": "drawing5-mcp", "kind": "python", "entry": "mcp_server.py",
             "delay_seconds": 0, "log": "mcp.log"},
        ],
    }

    tasks = build_task_specs(spec, root=str(tmp_path),
                             python=r"C:\Python311\python.exe")

    assert len(tasks) == 1
    task = tasks[0]
    assert task.name == "drawing5-mcp"
    assert task.execute == "cmd.exe"
    assert "mcp_server.py" in task.arguments
    assert task.working_dir == str(tmp_path)
    assert task.log == str(tmp_path / "out" / "logs" / "mcp.log")
    assert task.delay_seconds == 0
    assert task.dedupe is None


def test_build_cloudflared_task(tmp_path):
    spec = {
        "project": "drawing5",
        "tasks": [
            {"name": "drawing5-tunnel", "kind": "cloudflared",
             "config": r"C:\Users\Lenovo\.cloudflared\config-drawing5.yml",
             "tunnel": "drawing5", "delay_seconds": 30, "log": "tunnel.log"},
        ],
    }

    tasks = build_task_specs(spec, root=str(tmp_path),
                             cloudflared=r"C:\Users\Lenovo\.cloudflared\cloudflared.exe")

    task = tasks[0]
    assert "tunnel" in task.arguments and "drawing5" in task.arguments
    assert task.delay_seconds == 30
    assert task.dedupe == {"kind": "cloudflared",
                           "config": r"C:\Users\Lenovo\.cloudflared\config-drawing5.yml",
                           "tunnel": "drawing5"}


def test_load_spec_reads_json(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"project": "x", "tasks": []}),
                    encoding="utf-8")

    data = load_spec(str(path))

    assert data["project"] == "x"
    assert data["tasks"] == []
