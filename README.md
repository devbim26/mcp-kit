# mcp_kit

Переиспользуемый каркас MCP-серверов: авторизация, `/health`, формат
ошибок, аудит, ограничение файлов, надзор за процессами. Проект
регистрирует свои инструменты и получает готовое Streamable HTTP
приложение; HTTP-обвязку не пишет.

Рабочий пример обвязки сервера плагином DeepSeek Harness —
`../drawing5/plugin/dsh-plugin-drawing5/`.

## Что внутри

| Модуль | Назначение |
|---|---|
| `mcp_kit.app.McpApp` | FastMCP + FastAPI, Bearer на `/mcp`, `/health`, аудит вызовов |
| `mcp_kit.errors.ToolError`, `call_http` | ошибка инструмента → `isError=True` с кодом `HTTP 404: …` |
| `mcp_kit.paths.RootPolicy` | белый список каталогов, из которых сервер читает файлы (`realpath` + `commonpath`) |
| `mcp_kit.audit.AuditLog` | журнал `out/logs/mcp-audit.jsonl` |
| `mcp_kit.ops` | задачи Планировщика Windows из `ops/tasks.json` |
| `mcp-kit new` | генератор заготовки проекта из `mcp_kit/templates/` |

## Быстрый старт: создать MCP-сервер

```bash
# из каталога, где лежит mcp_kit (соседняя папка будущего проекта)
python -m mcp_kit.cli new myproject --out ../myproject --port 8808
```

Создаются:

```text
myproject/
├── mcp_server.py           # точка входа: McpApp + пример инструмента
├── start-myproject-mcp.bat # лаунчер: читает .env, ставит PYTHONPATH
├── .env.example            # шаблон ключа и порта
├── README.md
├── ops/tasks.json          # описание для Планировщика
└── tests/test_mcp_server.py
```

Дальше — заменить пример `list_example` на свои инструменты.

Если каркас установлен в окружение (`pip install -e ../mcp_kit`),
`MCP_KIT_HOME` в `.env` можно не задавать. Лаунчер работает и без
установки: подставляет `PYTHONPATH` из `MCP_KIT_HOME` (по умолчанию
`..\mcp_kit`).

## Инструменты

Инструмент — обычная функция (sync или async) с аннотациями типов.
Pydantic-модели описывают вход и выход; docstring и `Field(description=…)`
попадают в схему для модели.

```python
from pydantic import BaseModel, Field
from mcp_kit import McpApp, ToolError, run

class Item(BaseModel):
    id: str = Field(description="Идентификатор")
    title: str = ""

class ItemList(BaseModel):
    total: int
    items: list[Item]

async def list_items(limit: int = 20) -> ItemList:
    """Список записей.

    Args:
        limit: сколько вернуть (1..100).
    """
    if limit < 1 or limit > 100:
        raise ToolError("limit вне 1..100", code="bad_limit")
    ...

app = McpApp(
    name="myproject",
    version="1.0",
    instructions="Доступ к данным проекта.",
    key_env="MYPROJECT_KEY",
    require_key=True,
    audit_log="out/logs/mcp-audit.jsonl",
)
app.add_tool(list_items, read_only=True, idempotent=True)
# или декоратором:
# app.tool(read_only=True)(list_items)

if __name__ == "__main__":
    run(app, host_env="MYPROJECT_HOST",
        port_env="MYPROJECT_PORT", default_port=8808)
```

Аннотации `add_tool` — подсказки клиенту, не права доступа:
`read_only`, `destructive`, `idempotent`, `open_world`.

`from __future__ import annotations` превращает аннотации в строки;
FastMCP их не увидит. Каркас резолвит типы сам (`get_type_hints` в
глобалах проекта) — писать `Optional[X]` можно.

Ошибки: поднимайте `ToolError` (попадёт как `isError=True`). Если
инструмент зовёт функцию из `server.py`, которая бросает
`HTTPException`, оборачивайте вызов в `call_http` — код HTTP останется
виден в тексте ошибки.

Файлы: инструмент, принимающий путь, обязан проверять его через
`RootPolicy` — иначе превращается в «прочитай любой файл на диске».

`require_key=True` — fail-closed: без ключа в окружении сервер не
поднимается. Пустой ключ в `.env` не «открывает доступ», а валит старт.

## Конфигурация и запуск

`.env` рядом с `mcp_server.py` (шаблон — `.env.example`):

```ini
# python -c "import secrets; print(secrets.token_urlsafe(32))"
MYPROJECT_KEY=
MYPROJECT_PORT=8808
# где лежит каркас (если не pip install)
MCP_KIT_HOME=..\mcp_kit
```

```bash
python -X utf8 mcp_server.py          # http://127.0.0.1:8808/mcp
start-myproject-mcp.bat
```

Эндпоинт: `POST/GET/DELETE /mcp` (Streamable HTTP, JSON-RPC 2.0).
Liveness: `GET /health` — `{"status":"ok","name":…,"tools":[…]}`.
Авторизация: `Authorization: Bearer <MYPROJECT_KEY>` — только на `/mcp`,
`/health` открыт.

Конфиг MCP-клиента:

```json
{
  "mcpServers": {
    "myproject": {
      "url": "http://127.0.0.1:8808/mcp",
      "headers": {"Authorization": "Bearer <ключ>"}
    }
  }
}
```

## Надзор за процессом

```bash
python -m mcp_kit.ops install --spec ops/tasks.json
python -m mcp_kit.ops status  --spec ops/tasks.json
python -m mcp_kit.ops uninstall --spec ops/tasks.json
```

`ops/tasks.json` — задачи Планировщика Windows: python-процесс или
cloudflared-туннель. Логи — `out/logs/`. Порт из `ports` резервируется
в брандмауэре скриптом `register_tasks.ps1`.

Тесты: `python -m pytest tests/ -q`. Заготовка проверяет `/health`,
401 без Bearer и наличие инструментов.

---

# Подключение как плагин DeepSeek Harness

Плагин DSH — npm-пакет с манифестом `dsh.bundle`. Хост ставит его через
pnpm в каталог профиля и применяет слой конфигурации из
`cordis.patch.yml`. После установки в модели появляются инструменты
`mcp__<serverName>__<tool>`.

Плагин поднимает **только клиент**. Сам MCP-сервер живёт на машине
владельца (запущенный `mcp_server.py` и, для доступа снаружи, туннель).

## Минимальный состав

```text
dsh-plugin-myproject/
├── package.json          # имя, версия, dsh.bundle.patch
├── cordis.patch.yml      # слой: строка MCP-клиента
├── index.js              # не обязателен, если только MCP-строка
├── skills/myproject-mcp/SKILL.md  # справочник для модели
├── README.md
└── plugin-index.json     # только если светить в Discover
```

## package.json

```json
{
  "name": "dsh-plugin-myproject",
  "version": "0.1.0",
  "description": "MCP-сервер myproject для DeepSeek Harness",
  "type": "module",
  "main": "index.js",
  "files": [
    "index.js",
    "cordis.patch.yml",
    "skills/myproject-mcp/SKILL.md",
    "README.md"
  ],
  "keywords": ["deepseek", "dsh-plugin", "mcp"],
  "license": "UNLICENSED",
  "engines": { "dsh": ">=0.2.0" },
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" }
  }
}
```

* Без `dsh.bundle.patch` DSH поставит пакет как обычную зависимость и
  **не активирует ничего** — в лог уйдёт «activates no layer».
* `files` — белый список для `npm pack`. Скилл, который нужен модели,
  должен быть в списке, иначе не поедет в tarball.
* Не класть в `files`: `dist/`, `plugin-index.json`, секреты.

## cordis.patch.yml

```yaml
# АДРЕС И ТОКЕН — из переменных окружения процесса dsh:
#   MYPROJECT_SERVER_URL — адрес БЕЗ /mcp (плагин допишет сам)
#   MYPROJECT_API_KEY    — Bearer-токен
# Windows: setx MYPROJECT_API_KEY <токен>  и перезапуск DSH.
#
# Проверка слоя: dsh --profile <профиль> --dump-config
- insert:
    - id: myproject-mcp
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: myproject
        transport: streamable-http
        url: !!js (process.env.MYPROJECT_SERVER_URL ?? "https://myproject.example.com") + "/mcp"
        headers:
          Authorization: !!js '`Bearer ${process.env.MYPROJECT_API_KEY ?? ""}`'
        toolCallTimeoutMs: 120000
- insert:
    - id: myproject-skill
      name: './index.js'
      config:
        serverUrl: !!js process.env.MYPROJECT_SERVER_URL ?? "https://myproject.example.com"
        tokenEnv: MYPROJECT_API_KEY
```

Правила:

* `serverName` — то, что увидит модель: `mcp__myproject__tool`.
  Латиница, цифры, `_`, `-`, до 32 символов. **Один `serverName` на всю
  конфигурацию** — дубль, и второй клиент не поднимется
  («server is disconnected»).
* `url` — адрес **с** `/mcp` (FastMCP/официальный python MCP).
  Переменную окружения храните без `/mcp` — патч дописывает.
* `transport: streamable-http` — для уже запущенного сервера;
  `stdio` — для дочернего процесса (`command`, `args`, `env`, `cwd`).
* `toolCallTimeoutMs` — дефолт DSH 60 с; для долгих инструментов
  (загрузка PDF, поиск по большому комплекту) — 120000.
* `!!js` исполняется в DSH, а не в браузере: `process.env` — да,
  `require('fs')` — не рассчитывайте.
* Секреты — только через `process.env`. Уже заданные переменные
  окружения сильнее значений из `.env` хоста.

Пользователь переопределяет адрес/токен, не правя пакет: обычная строка
без `insert:` в `~/.dsh/profiles/<профиль>/cordis.patch.yml` с тем же
`id` **целиком заменяет** строку плагина. Это рабочий способ задать
локальный URL поверх облачного дефолта плагина.

**Не добавляйте вторую строку с тем же `serverName` через `- insert:`**
ни в профиле, ни в машинном слое (`~/.dsh/cordis.patch.yml`). Плагин уже
вставляет свою строку; `insert:` добавляет ещё одну, два клиента с одним
`serverName` не поднимаются, набор инструментов агента откатывается.
Машинный слой держите пустым (`[]`), если строка живёт в профиле или в
плагине — иначе профиль `web` и `desktop` поссорятся о дубль.

## README плагина — то, что видит клиент

DSH показывает весь `README.md` пакета при клике на плагин. Пишите его
для клиента, а не для себя:

- что это и какие инструменты появляются в модели;
- как поставить (Add plugin / ссылка / токен);
- типовой сценарий работы агента;
- три-четыре строчки «если не работает».

Внутренности — схема патча, публикация в npm, ограничения, «как
переопределить строку в профиле» — оставляйте в документации сервера
(`docs/DSH.md`, `docs/CLIENT.md`), а не в пакете. Хотите длинную
инструкцию — держите её рядом, в репозитории, и не кладите в `files`.

После правки README:

1. Закоммитьте и запушьте в репозиторий плагина (`dsh-plugin-<имя>`).
2. Обновите `commit` в `plugin-index.json` — иначе Discover продолжает
   ставить старый коммит.
3. Пересоберите tgz (`npm pack`), если раздаёте прямые ссылки.
4. Перезапустите DSH **целиком** — процессы, оставшиеся с прошлой
   сессии, держат старый README в памяти. Копия в `node_modules` сама
   по себе карточку не меняет.

Персональные сборки с вшитым токеном пересобирают отдельно
(`issue_license --plugin`) — они не подхватят новый README сами.

## index.js: скилл и подсказка про токен

Модуль — Cordis-строка: DSH вызывает `apply(ctx, config)` при старте.
Типовые задачи — зарегистрировать скилл, проверить токен, написать в лог
адрес сервера.

```js
import { readFile } from 'node:fs/promises'

export const name = 'myproject'
export const inject = ['skills']

const DEFAULT_SERVER_URL = 'https://myproject.example.com'

export async function apply(ctx, config = {}) {
  const serverUrl = config.serverUrl ?? DEFAULT_SERVER_URL
  const tokenEnv = config.tokenEnv ?? 'MYPROJECT_API_KEY'
  ctx.logger.info(`myproject: MCP-сервер ${serverUrl}/mcp`)

  if (!process.env[tokenEnv] && config.tokenConfigured !== true) {
    ctx.logger.warn(
      `myproject: не задана ${tokenEnv} — сервер вернёт 401. ` +
        `Windows: setx ${tokenEnv} <токен>, затем перезапуск DSH.`,
    )
  }
  await registerSkill(ctx)
}

const SKILL_URL = new URL('./skills/myproject-mcp/SKILL.md', import.meta.url)

function parseSkill(text) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text)
  if (match === null) return null
  const fields = {}
  for (const line of match[1].split(/\r?\n/)) {
    const sep = line.indexOf(':')
    if (sep <= 0) continue
    const key = line.slice(0, sep).trim()
    if (key === '' || line.startsWith(' ')) continue
    fields[key] = line.slice(sep + 1).trim()
  }
  if (!fields.name || !fields.description) return null
  return { name: fields.name, description: fields.description,
           content: match[2].trim() }
}

async function registerSkill(ctx) {
  let skill
  try {
    skill = parseSkill(await readFile(SKILL_URL, 'utf8'))
  } catch (error) {
    ctx.logger.warn(`myproject: скилл не прочитан: ${String(error)}`)
    return
  }
  if (!skill) return
  const existing = await ctx.skills.list()
  if (existing.some(entry => entry.name === skill.name)) return
  ctx.skills.register({
    name: skill.name,
    description: skill.description,
    content: skill.content,
    source: 'runtime',
  })
}
```

Ошибка в `apply` не должна валить старт хоста — оборачивайте чтение
файлов в try/catch. `config.tokenConfigured === true` — флаг
персональной сборки: токен вшит в патч, варн не нужен.

## skills/myproject-mcp/SKILL.md

```markdown
---
name: myproject-mcp
description: Что умеет и когда triggered. Пишите шире — модели недотриггивают.
---

# Как работать с myproject

1. Сначала list_..., потом get_...
2. Ошибки приходят как isError: true
```

`description` — главный триггер: модель выбирает скилл по нему.

## Установка в DSH

Собрать и отдать клиенту:

```bash
cd dsh-plugin-myproject
npm pack                # dsh-plugin-myproject-0.1.0.tgz
```

Способы поставить (диалог **Plugins → Add plugin** или CLI):

```sh
dsh plugin --profile desktop add ./dsh-plugin-myproject          # локальная папка
dsh plugin --profile desktop add ./dsh-plugin-myproject-0.1.0.tgz
dsh plugin --profile desktop add github:owner/dsh-plugin-myproject
dsh plugin --profile desktop add dsh-plugin-myproject            # после npm publish
dsh plugin --profile desktop add https://host/plugins/dsh-plugin-myproject-0.1.0.tgz
```

После установки — **перезапуск DSH**: набор бандлов читается при старте
профиля. Полностью закройте приложение (включая трей и фоновые процессы
`DeepSeek Harness.exe`) — остатки прошлой сессии держат старый конфиг и
старый README. Прямая `https://…tgz` принимается (под капотом pnpm),
хотя в официальных примерах её нет; если клиентская сборка откажется —
скачать tgz и указать путь к файлу.

Проверка:

```sh
dsh --profile desktop --dump-config | grep -A8 "dsh-plugin-myproject"
```

Ищите комментарий `# == dsh-plugin-myproject` и строку
`serverName: myproject`. В сессии агента инструменты видны как
`mcp__myproject__list_items` и т. д.

## Токен

```bat
setx MYPROJECT_API_KEY <токен>
setx MYPROJECT_SERVER_URL https://myproject.example.com
```

После `setx` приложение перезапустить. `MYPROJECT_SERVER_URL` — **без**
`/mcp`. Если токен не задан — 401, в лог DSH падает подсказка модуля.

## Вкладка Discover

**Настройки → Плагины → Источники индекса** — публичный URL файла
`plugin-index.json` (формат 1). Источник версии — **только `npm` или
`git`** (коммит в hex); прямую ссылку на tarball Discover не принимает.

```json
{
  "format": 1,
  "title": "myproject",
  "plugins": [
    {
      "name": "dsh-plugin-myproject",
      "title": { "en": "myproject", "ru": "myproject" },
      "description": {
        "en": "Adds the myproject MCP server",
        "ru": "Добавляет MCP-сервер myproject"
      },
      "author": "devBIM",
      "homepage": "https://myproject.example.com",
      "versions": [
        {
          "version": "0.1.0",
          "publishTimestamp": 1794220289,
          "source": {
            "type": "git",
            "url": "https://github.com/owner/dsh-plugin-myproject.git",
            "commit": "cf687f80c7773470032b66dc205432ed9217e1bb"
          },
          "engines": { "dsh": ">=0.2.0" }
        }
      ]
    }
  ]
}
```

`publishTimestamp` — Unix-секунды; `commit` — 40 hex; в локализованном
объекте обязателен `en`. Индекс валидируется
`@deepseek-ai/dsh-plugin-market-index` (`parseMarketIndex`) — нарушение
формата отбрасывает весь индекс.

**Коммит в индексе — контракта версии.** После любого пуша в репозиторий
плагина обновите `commit` в `plugin-index.json` и задеплойте индекс.
Discover ставит ровно тот коммит, что указан, а не `HEAD`. Локальная
правка `node_modules` новых установок не меняет.

## Персональная сборка с вшитым токеном

Платному клиенту — отдельный tgz, в котором Bearer-токен уже вшит
(`tokenConfigured: true` в конфиге строки `index.js`, токен в
`Authorization` патча). Клиент вставляет ссылку — и работает, `setx`
не нужен. Имя файла — `dsh-plugin-<версия>-<8 hex>.tgz`: названия
компании в URL нет, ссылка равна токену.

Такие сборки **не публикуют** в npm. Публичный пакет остаётся триальным
— без токена сервер отвечает 401.

Как выдать лицензию и собрать tarball на примере drawing5:
`../drawing5/cloud/issue_license.py`, `../drawing5/docs/DSH.md`.

## Тест контракта плагина

Минимум, который стоит проверить, не запуская DSH:

```python
import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "dsh-plugin-myproject"

def test_manifest_declares_bundle():
    m = json.loads((PLUGIN / "package.json").read_text(encoding="utf-8"))
    assert m["dsh"]["bundle"]["patch"] == "./cordis.patch.yml"
    assert "skills/myproject-mcp/SKILL.md" in m["files"]

def test_patch_has_single_server_name():
    text = (PLUGIN / "cordis.patch.yml").read_text(encoding="utf-8")
    assert text.count("serverName:") == 1
    assert "myproject" in text
```

## Типовые сбои

| Симптом | Причина | Что делать |
|---|---|---|
| `server is disconnected` | сервер не запущен; 401 на initialize; дубль `serverName`; неверный URL | Проверить `/health`, токен, `--dump-config`, лог DSH |
| Окно/процесс мигнул и умер | порт занят | `netstat -ano \| findstr :<порт>`, убить старый PID |
| «Такой плагин не найден» в Add plugin | искали в npm, а пакет не опубликован | Вставить прямую ссылку на tgz или локальный путь |
| Discover не видит | индекс не добавлен или источник не npm/git | Настройки → Плагины → Источники индекса |
| Инструменты не появились | DSH не перезапущен; патч не применился | Рестарт; `--dump-config` |
| Карточка плагина показывает старый README | DSH не перезапущен; Discover стоит на старом коммите; персональная сборка не пересобрана | Закрыть все процессы DSH; обновить `commit` в индексе; пересобрать персональный tgz |
| Два набора инструментов / конфликт | ручной `- insert:` с тем же `serverName` поверх плагина | Удалить вставку; если нужен свой URL — строка **без** `insert:` с тем же `id` |
| «activates no layer» в логе | в `package.json` нет `dsh.bundle.patch` | Добавить манифест бандла |
| pnpm заблокировал build-скрипт | git-установка с `prepare` | Разрешить в `pnpm-workspace.yaml` профиля (`allowBuilds`) или ставить готовый tarball |

## Чек-лист перед отдачей клиенту

- [ ] `mcp_server.py` поднимается, `/health` отвечает, инструменты в `tools/list`.
- [ ] Ключ генерируется `secrets.token_urlsafe(32)`, лежит только в `.env` владельца.
- [ ] `package.json` объявляет `dsh.bundle.patch`, скилл в `files`.
- [ ] README плагина — для клиента: что это, установка, сценарий, «если не работает». Без патчей и npm publish.
- [ ] В патче ровно один `serverName`, URL с `/mcp`, таймаут 120000.
- [ ] В профиле и машинном слое нет `- insert:` с этим `serverName`.
- [ ] Токен читается из `process.env`, варн модуля работает.
- [ ] Тест контракта зелёный; `npm pack` содержит скилл.
- [ ] `plugin-index.json` указывает на свежий коммит.
- [ ] DSH перезапущен целиком (все процессы), `--dump-config` показывает слой плагина.
