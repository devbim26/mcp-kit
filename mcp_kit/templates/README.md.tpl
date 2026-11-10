# {name}

MCP-сервер на каркасе `mcp_kit`.

## Запуск

```
python -X utf8 mcp_server.py
```

или `start-{name}-mcp.bat` (читает `.env`, ставит `PYTHONPATH` из `MCP_KIT_HOME`).

Эндпоинт: `http://127.0.0.1:{port}/mcp`, liveness — `/health`.

## Конфиг MCP-клиента

```json
{{
  "mcpServers": {{
    "{name}": {{
      "url": "http://127.0.0.1:{port}/mcp",
      "headers": {{"Authorization": "Bearer <ключ>"}}
    }}
  }}
}}
```

## Надзор за процессом

```
python -m mcp_kit.ops install --spec ops/tasks.json
python -m mcp_kit.ops status  --spec ops/tasks.json
```

Логи: `out/logs/`. Журнал вызовов: `out/logs/mcp-audit.jsonl`.
