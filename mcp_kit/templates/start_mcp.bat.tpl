@echo off
rem {name}: MCP-сервер (Streamable HTTP) на :{port}, эндпоинт /mcp
rem Ключ и порт читаются из .env; MCP_KIT_HOME — где лежит каркас mcp_kit.
setlocal
cd /d "%~dp0"
set "KEY="
set "PORT={port}"
set "KIT=%MCP_KIT_HOME%"
if "%KIT%"=="" set "KIT=%~dp0..\mcp_kit"
for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.env") do (
    if /i "%%A"=="{env_prefix}_KEY" set "KEY=%%B"
    if /i "%%A"=="{env_prefix}_PORT" set "PORT=%%B"
    if /i "%%A"=="MCP_KIT_HOME" set "KIT=%%B"
)
if "%KEY%"=="" (
    echo [start-{name}-mcp] {env_prefix}_KEY не найден в .env — запуск отменён.
    exit /b 1
)
set "{env_prefix}_KEY=%KEY%"
set "{env_prefix}_PORT=%PORT%"
set "PYTHONPATH=%KIT%;%PYTHONPATH%"
python -X utf8 mcp_server.py
