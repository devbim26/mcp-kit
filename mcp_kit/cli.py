"""CLI каркаса: генератор заготовок и управление надзором."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ops as ops_mod

_TEMPLATES = Path(__file__).resolve().parent / "templates"


def _render(name: str, template: str, **values) -> str:
    text = (_TEMPLATES / template).read_text(encoding="utf-8")
    text = text.replace("{{", "\x00").replace("}}", "\x01")
    text = text.format(name=name, **values)
    return text.replace("\x00", "{").replace("\x01", "}")


def new_project(name: str, out: str, port: int = 8808) -> list[str]:
    """Создать заготовку MCP-сервера; вернуть список созданных файлов."""
    root = Path(out).resolve()
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "ops").mkdir(parents=True, exist_ok=True)

    env_prefix = name.upper().replace("-", "_")
    created: list[str] = []

    targets = [
        (root / "mcp_server.py", "mcp_server.py.tpl", {}),
        (root / f"start-{name}-mcp.bat", "start_mcp.bat.tpl", {}),
        (root / ".env.example", "env.example.tpl", {}),
        (root / "README.md", "README.md.tpl", {}),
        (root / "ops" / "tasks.json", "tasks.json.tpl", {}),
        (root / "tests" / "test_mcp_server.py", "test_mcp_server.py.tpl", {}),
    ]

    for path, template, extra in targets:
        content = _render(name, template, port=port, env_prefix=env_prefix,
                           **extra)
        path.write_text(content, encoding="utf-8")
        created.append(str(path))

    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-kit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="создать заготовку MCP-сервера")
    p_new.add_argument("name")
    p_new.add_argument("--out", required=True)
    p_new.add_argument("--port", type=int, default=8808)

    for action in ("install", "uninstall", "status"):
        p_ops = sub.add_parser(action, help=f"надзор: {action}")
        p_ops.add_argument("--spec", required=True)
        p_ops.add_argument("--python", default="")
        p_ops.add_argument("--cloudflared", default="")

    args = parser.parse_args(argv)

    if args.command == "new":
        for path in new_project(args.name, args.out, port=args.port):
            print(f"создан {path}")
        return 0

    return ops_mod.main([args.command, "--spec", args.spec,
                         "--python", args.python,
                         "--cloudflared", args.cloudflared])


if __name__ == "__main__":
    sys.exit(main())
