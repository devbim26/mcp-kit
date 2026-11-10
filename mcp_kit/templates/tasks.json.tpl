{{
  "project": "{name}",
  "ports": [{port}],
  "tasks": [
    {{
      "name": "{name}-mcp",
      "kind": "python",
      "entry": "mcp_server.py",
      "delay_seconds": 0,
      "log": "mcp.log"
    }}
  ]
}}
