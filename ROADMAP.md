# ROADMAP — расширение MCP-сервера

Дорожная карта развития `mcp-github-server`. Цель — превратить сервер из GitHub-обёртки в универсальный «швейцарский нож» для агента.

Легенда приоритетов:
- 🔴 высокий — блокирует базовые сценарии, делать первым
- 🟡 средний — ощутимо расширяет возможности
- 🟢 низкий — нишевое / требует осторожности

---

## Текущее состояние

Реализовано (смержено в `main`):
- **Батч 1** — PR / Issues / Releases / Tags / batch-push, meta (`list_my_tools`, `describe_tool`), web (`web_fetch`, `web_search`), утилиты (base64/hash/json/uuid/date/regex/diff) → ~54 инструмента.
- **Батч 2** — branches, gists, Actions control (`dispatch`/`rerun`/`cancel`/`list_workflows`/`list_artifacts`), security alerts (`dependabot`/`code-scanning`/`secret-scanning`), repo info → ~75.
- **Батч 3** — web (`rss_read`, `html_to_markdown`), данные (`csv_parse`/`csv_generate`/`yaml_to_json`/`json_to_yaml`/`markdown_to_html`), commits (`get_commit_diff`, `list_directory`, `get_file_blame`) → ~85.
- **Батч 4 (в этой ветке)** — sandboxed local filesystem: `read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`. По умолчанию **выключено** (`ENABLE_LOCAL_TOOLS=1`). См. `SANDBOX.md`.

---

## Батч 4 — Локальные файлы (реализовано в этой ветке)

### 🔒 Инструменты
Файлы: `mcp_server/tools/localfs/files.py`

- `read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`

### 🔒 Уровни изоляции

Базовая модель: **обычный непривилегированный Linux-пользователь** (`mcp-sandbox`).
Этого достаточно, чтобы не навредить системе и другим пользователям.

| Уровень | Что даёт | Статус |
|---|---|---|
| **1. Отдельный Linux-юзер** | Нет доступа к системе/чужим home/процессам | ✅ используется |
| **2. WSL2 + отключённый automount** | + нет доступа к Windows-диску `C:` | ✅ инструкция в `SANDBOX.md` |
| **3. `bubblewrap`** | + нет сети, только `/workspace`, изоляция PID/IPC | 🟢 опция на будущее |
| **4. Docker/Podman** | + лимиты CPU/RAM/PID, read-only rootfs | 🟢 опция на будущее |

### 🟢 Уровень 3 — bubblewrap (будущее)

`--unshare-all --ro-bind /usr --bind $ROOT` — полная изоляция ФС/сети без root.
Полезно, если localfs-инструменты будут вызываться из недоверенного контента
(prompt injection через `web_fetch`).

### 🟢 Уровень 4 — Docker/Podman (будущее)

`--read-only --network=none --cap-drop=ALL --memory=512m --pids-limit=100`.
Для продакшена и мультиарендных сценариев.

### Что НЕ закрывает уровень 1

Закрывается только bwrap/docker:
1. Чтение world-readable файлов (`/etc/passwd`, логи, конфиги с `o+r`).
2. Полный доступ в сеть.
3. DoS (fork-бомба, забивание диска/RAM).
4. Доступ к `ssh-agent`, docker-сокету, другим IPC.

---

## Батч 5 — Git-операции в workspace (осторожно)

⚠️ Внутри whitelist-корня, поверх уровня изоляции из батча 4.

- `git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`

---

## Батч 6 — Shell / код (опасно)

⚠️ Требует подтверждения на опасные команды, таймаут, лимит вывода.
Обязательно внутри sandbox (уровень 2–4).

- `run_command(cmd, cwd, timeout)`
- `run_python(code)` в песочнице

---

## Батч 7 — Память и Synapse

Стратегическая линия проекта.

- `model_me` — эмбеддинг-слепок пользователя из диалога
- `find_my_match` — поиск похожих людей по смыслу
- `publish_profile`, `search_people`, `propose_contact`
- `index_github` — индексировать публичные GitHub-профили
- `save_note`, `search_notes` — личная база знаний

---

## Технические заметки

- Инструменты возвращают `str`; обёртка в MCP-контент — на стороне `server.py`.
- Новый файл с инструментами нужно импортировать в `__init__.py` соответствующего подпакета.
- `ToolRegistry.discover()` сканирует подпакеты в `mcp_server/tools/`; внутри подпакета нужен `__init__.py` с импортами.
- Опасные категории (shell, local fs) держать отдельными подпакетами, чтобы отключать одной строкой.
- `localfs/__init__.py` сам решает, регистрировать инструменты или нет (по `ENABLE_LOCAL_TOOLS`).
