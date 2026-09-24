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
- **Батч 4** — sandboxed local filesystem: `read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`. По умолчанию **выключено** (`ENABLE_LOCAL_TOOLS=1`). См. `SANDBOX.md`.

---

## Единый sandbox-пул инструментов (идея)

Когда батчи 4–6 будут готовы, localfs + git + shell естественно объединяются
в **один изолированный workspace** под одним пользователем:

- один `LOCAL_TOOLS_ROOT` (= `/workspace`) — общий whitelist для всех трёх категорий;
- один флаг `ENABLE_LOCAL_TOOLS` включает весь пул (или раздельные флаги
  `ENABLE_LOCAL_FS` / `ENABLE_LOCAL_GIT` / `ENABLE_LOCAL_SHELL`, если нужен
  более тонкий контроль);
- всё выполняется под одним `mcp-sandbox` (Linux) / внутри WSL2 без automount;
- shell-команды запускаются с `cwd` внутри `LOCAL_TOOLS_ROOT`;
- git-операции — только над репозиториями внутри `LOCAL_TOOLS_ROOT`.

Смысл: агент работает как полноценный разработчик в «своей песочнице»,
но не выходит за её границы. Дальнейшее усиление — bwrap/Docker вокруг
этого пула (см. уровни изоляции выше).

---

## Батч 5 — Git-операции в workspace (следующий)

⚠️ Внутри whitelist-корня, поверх уровня изоляции из батча 4.

- `git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`
- Флаги: `ENABLE_LOCAL_TOOLS` (общий) + `LOCAL_TOOLS_ROOT` (общий)
- `git_push` требует наличие remote/токена; по умолчанию не форсит (`--force` не используется)

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
- `localgit/__init__.py` работает по той же схеме (флаг `ENABLE_LOCAL_TOOLS`).
