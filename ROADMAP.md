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
- **Батч 5** — sandboxed local git: `git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`. Тот же флаг `ENABLE_LOCAL_TOOLS`, тот же `LOCAL_TOOLS_ROOT`.
- **Батч 6** — sandboxed shell / python: `run_command`, `run_python`. Отдельный флаг `ENABLE_LOCAL_SHELL=1`. Самая опасная категория — включать только поверх уровня изоляции 2–4 (см. `SANDBOX.md`).
- **Батч 7a** — каркас Synapse без эмбеддингов: `publish_profile`, `search_people` (keyword-MVP), `propose_contact`, `save_note`, `search_notes`, `index_github`. Флаг `ENABLE_SYNAPSE=1`, данные в `SYNAPSE_DATA_DIR`.
- **Repo admin** — `update_repo_info` (description / homepage / topics).

---

## Единый sandbox-пул инструментов (идея)

Батчи 4–6 готовы: localfs + git + shell естественно объединяются
в **один изолированный workspace** под одним пользователем:

- один `LOCAL_TOOLS_ROOT` (= `/workspace`) — общий whitelist для всех трёх категорий;
- раздельные флаги `ENABLE_LOCAL_TOOLS` (fs + git) и `ENABLE_LOCAL_SHELL` (shell) —
  для более тонкого контроля;
- всё выполняется под одним `mcp-sandbox` (Linux) / внутри WSL2 без automount;
- shell-команды запускаются с `cwd` внутри `LOCAL_TOOLS_ROOT`;
- git-операции — только над репозиториями внутри `LOCAL_TOOLS_ROOT`.

Смысл: агент работает как полноценный разработчик в «своей песочнице»,
но не выходит за её границы. Дальнейшее усиление — bwrap/Docker вокруг
этого пула (см. уровни изоляции в `SANDBOX.md`).

---

## Батч 7b — Эмбеддинг-матчинг в Synapse (следующий)

Заменяет keyword-MVP в `search_people`/`search_notes` на настоящие эмбеддинги
и добавляет `model_me` и `find_my_match`.

### Выбор модели эмбеддингов — три опции

| Опция | Как работает | Плюсы | Минусы | Когда выбирать |
|-------|--------------|-------|--------|----------------|
| **A. OpenAI `text-embedding-3-small`** | облачные эмбеддинги через HTTP API (`OPENAI_API_KEY`) | лучшее качество из коробки, ноль локальных ресурсов, 1536 dim | платно (~$0.02 / 1M токенов), данные уходят в OpenAI, нужен интернет | нужен максимум качества и готов платить |
| **B. Локальная `sentence-transformers`** | модель скачивается один раз, работает локально (`all-MiniLM-L6-v2` — 384 dim, ~90 MB; `bge-small-en` — 384 dim) | бесплатно, приватно, работает офлайн | ~100–400 MB, нужен CPU (медленно) или GPU, качество ниже OpenAI | приоритет приватности и нулевой стоимости |
| **C. Ollama `nomic-embed-text`** | локальный сервер Ollama, HTTP на `http://localhost:11434` | бесплатно, приватно, легко менять модели (`ollama pull`), единый интерфейс | нужно поднять Ollama и держать его запущенным, ~300 MB | уже используешь Ollama или хочешь легко переключать модели |

### Конфигурация (env)

```bash
SYNAPSE_EMBEDDING_PROVIDER=openai | local | ollama   # по умолчанию — выключено (keyword-MVP)

# вариант A
OPENAI_API_KEY=...
SYNAPSE_EMBEDDING_MODEL=text-embedding-3-small

# вариант B
SYNAPSE_EMBEDDING_MODEL=all-MiniLM-L6-v2

# вариант C
SYNAPSE_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

### Что войдёт в батч 7b

- Векторное хранилище: SQLite + numpy (без внешних сервисов).
- `model_me(text)` — строит эмбеддинг-слепок из описания/диалога.
- `find_my_match(query, limit)` — косинусный поиск похожих профилей.
- `search_people`/`search_notes` переключаются на эмбеддинги, если провайдер задан; иначе остаются keyword-MVP (graceful fallback).

---

## Батч 8 — Авторизация и безопасность для публичного IP

⚠️ **Критично до любого публичного развёртывания.** Сейчас сервер слушает
`0.0.0.0:3001`, не проверяет собственный токен, CORS открыт. На публичном IP
любой, кто дотянется до порта, сможет вызывать инструменты.

### Что нужно

1. **`MCP_AUTH_TOKEN`** — сервер требует `Authorization: Bearer <MCP_AUTH_TOKEN>`
   на каждый запрос к `/mcp`. Без него — 401. Закрывает доступ.
2. **Разделить заголовки:**
   - `X-MCP-Auth: <MCP_AUTH_TOKEN>` — доступ к серверу;
   - `Authorization: Bearer <github_token>` — GitHub API.
   Сейчас один заголовок используется для двух целей — на публичном IP это ломается.
3. **CORS white-list** — вместо `CORS(app)` указать конкретный origin расширения.
4. **Rate limit** — счётчик на IP + окно (например 60 запросов/мин).
5. **TLS** — reverse-proxy (nginx / caddy) или Cloudflare Tunnel. Публичный IP без HTTPS = токен в открытом виде.
6. **Правило:** публичный IP ⇒ локальные инструменты (`localfs`, `localgit`, `shell`) **выключены**.

### Опции выключения (по умолчанию безопасно)

| Переменная | Что делает |
|-----------|------------|
| `MCP_REQUIRE_AUTH=1` | включает проверку `MCP_AUTH_TOKEN` (по умолчанию выключено для localhost) |
| `MCP_AUTH_TOKEN=...` | сам токен |
| `MCP_CORS_ORIGINS=https://...` | список разрешённых origin через запятую |
| `MCP_RATE_LIMIT=60` | запросов в минуту на IP (0 = без лимита) |
| `ENABLE_LOCAL_TOOLS` | должен быть НЕ задан на публичном IP |
| `ENABLE_LOCAL_SHELL` | должен быть НЕ задан на публичном IP |

---

## Батч 9 — Прочее / идеи

- GitHub Pages сайт репозитория (сгенерированная страница из README).
- Дополнительные Synapse-инструменты (Telegram-индексация, экспорт профиля в gist).

---

## Технические заметки

- Версия проекта — единый источник: `mcp_server/__init__.py` (`__version__`).
  `server.py` и `pyproject.toml` читают её, дублей нет.
- Инструменты возвращают `str`; обёртка в MCP-контент — на стороне `server.py`.
- Новый файл с инструментами нужно импортировать в `__init__.py` соответствующего подпакета.
- `ToolRegistry.discover()` сканирует подпакеты в `mcp_server/tools/`; внутри подпакета нужен `__init__.py` с импортами.
- Единственный канонический декоратор — `mcp_server.core.registry.mcp_tool`.
- Опасные категории (shell, local fs, local git) держать отдельными подпакетами, чтобы отключать одной строкой.
- `localfs/__init__.py` и `localgit/__init__.py` сами решают, регистрировать инструменты или нет (по `ENABLE_LOCAL_TOOLS`).
- `shell/__init__.py` работает по той же схеме, но с флагом `ENABLE_LOCAL_SHELL`.
