"""Генератор заготовок: создаёт проект, который сразу работает."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from mcp_kit.cli import new_project

KIT_HOME = str(Path(__file__).resolve().parents[1])


def test_new_project_creates_expected_files(tmp_path):
    out = tmp_path / "drawing6"
    created = new_project("drawing6", str(out), port=9100)

    names = {os.path.basename(p) for p in created}
    assert "mcp_server.py" in names
    assert "start-drawing6-mcp.bat" in names
    assert ".env.example" in names
    assert "tasks.json" in names

    assert (out / "mcp_server.py").exists()
    assert (out / "tests" / "test_mcp_server.py").exists()
    assert (out / "ops" / "tasks.json").exists()


def test_generated_tasks_json_is_valid(tmp_path):
    out = tmp_path / "drawing6"
    new_project("drawing6", str(out), port=9100)

    data = json.loads((out / "ops" / "tasks.json").read_text(encoding="utf-8"))

    assert data["project"] == "drawing6"
    assert data["ports"] == [9100]
    assert data["tasks"][0]["name"] == "drawing6-mcp"
    assert data["tasks"][0]["entry"] == "mcp_server.py"


def test_generated_server_imports_and_lists_tools(tmp_path):
    out = tmp_path / "drawing6"
    new_project("drawing6", str(out), port=9100)

    env = dict(os.environ)
    env["PYTHONPATH"] = KIT_HOME + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import mcp_server as m; "
         "import asyncio; "
         "print(sorted(t.name for t in "
         "asyncio.run(m.build_app().mcp.list_tools())))"],
        cwd=str(out), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace")

    assert proc.returncode == 0, proc.stderr
    assert "example" in proc.stdout


def test_generated_bat_references_kit_home(tmp_path):
    out = tmp_path / "drawing6"
    new_project("drawing6", str(out), port=9100)

    text = (out / "start-drawing6-mcp.bat").read_text(encoding="utf-8")

    assert "MCP_KIT_HOME" in text
    assert "PYTHONPATH" in text
