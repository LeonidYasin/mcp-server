# ROADMAP — расширение MCP-сервера

Дорожная карта развития **mcp-server**. Цель — превратить сервер из GitHub-обёртки в универсальный «швейцарский нож» для агента.

> **Source of truth:** версия — `pyproject.toml`; список инструментов — рантайм `list_my_tools` + [`TOOLS.md`](TOOLS.md).
> **Ревизия документации: 3 · 2026-09-26** (см. README → Source of truth).

Легенда приоритетов:
- 🔴 высокий — блокирует базовые сценарии, делать первым
- 🟡 средний — ощутимо расширяет возможности
- 🟢 низкий — нишевое / требует осторожности

---

## Экосистема проектов (карта)

У автора несколько связанных репозиториев вокруг одной идеи: **находимость и обмен через ИИ-агента**.

| Репозиторий | Домен | Стек | Роль |
|-------------|-------|------|------|
| **NoKing** | Обмен ценностями, DAO | HTML+JS → Solidity/IPFS | Протокол-фундамент |
| **Civis** | Люди по ценностям + маркетплейс | Python, SQLite, Telegram | Первый рабочий матчинг |
| **synapse** (старый) | Соцсеть на ИИ-чатах | концепция | Идейный предок |
| **synapse2** | ИИ-платформа поиска связей | FastAPI, DeepSeek | Веб-версия |
| **agora-mcp** | offers/wants, сетевой | TypeScript, Postgres+pgvector | Сетевой протокол |
| **mcp-server** | **110 инструментов** + Synapse | Python, Flask | MCP-интерфейс |

**Стратегия (вариант A):** не сливать репозитории, а унифицировать протокол. Общая спека `synapse-protocol` — JSON-схема для item (offer/want), profile, contact, exchange. На неё ссылаются и Synapse, и Agora, и NoKing.

---

## Текущее состояние

Фактически зарегистрировано **110 инструментов** (проверяется `list_my_tools`). Реализовано (смержено в `main`):

- **Батч 1** — PR / Issues / Releases / Tags / batch-push, meta (`list_my_tools`, `describe_tool`), web (`web_fetch`, `web_search`), утилиты (base64/hash/json/uuid/date/regex/diff).
- **Батч 2** — branches, gists, Actions control, security alerts, repo info.
- **Батч 3** — web (`rss_read`, `html_to_markdown`), данные (`csv_*`, `yaml/json` конвертеры, `markdown_to_html`), commits (`get_commit_diff`, `list_directory`, `get_file_blame`).
- **Батч 4** — sandboxed local filesystem (`localfs/`, 4 инструмента). По умолчанию **выключено** (`ENABLE_LOCAL_TOOLS=1`). См. `SANDBOX.md`.
- **Батч 5** — sandboxed local git (`localgit/`, 6 инструментов). Тот же флаг.
- **Батч 6** — sandboxed shell / python (`shell/`, `run_command`, `run_python`). Флаг `ENABLE_LOCAL_SHELL=1`.
- **Батч 7a** — каркас Synapse без эмбеддингов: `publish_profile`, `search_people` (keyword-MVP), `propose_contact`, `save_note`, `search_notes`, `index_github`. Флаг `ENABLE_SYNAPSE=1`, данные в `SYNAPSE_DATA_DIR`.
- **Repo admin** — `update_repo_info`; плюс `move_file`, `read_multiple_files`, `get_repo_tree`, `read_run_logs_offset`, review-threads (resolve/unresolve), search-* и др. — см. [`TOOLS.md`](TOOLS.md).

---

## Единый sandbox-пул инструментов

Батчи 4–6 готовы: localfs + git + shell объединяются в **один изолированный workspace**:

- один `LOCAL_TOOLS_ROOT` (= `/workspace`) — общий whitelist;
- раздельные флаги `ENABLE_LOCAL_TOOLS` (fs + git) и `ENABLE_LOCAL_SHELL` (shell);
- всё выполняется под одним `mcp-sandbox` (Linux) / внутри WSL2 без automount;
- shell-команды и git-операции — только внутри `LOCAL_TOOLS_ROOT`.

Дальнейшее усиление — bwrap/Docker (уровни 3–4 в `SANDBOX.md`).

---

## Батч 7b — Эмбеддинг-матчинг в Synapse (в работе)

> Статус: **в работе** — в репозитории уже есть `synapse/embeddings.py`, `vector_store.py`, `matching.py`, `items.py`. Рантайм-регистрация инструментов батча 7b проверяется через `list_my_tools`.

### Ключевой архитектурный урок (из agora-mcp)

**Item-модель, а не user-модель.** Одна эмбеддинг на **item** (offer | want), а не на пользователя. Матчинг **асимметричный**: offer ↔ чужие want.

**Instruction-aware эмбеддинги.** Разные префиксы для offer- и want-роли. Multilingual (RU+EN): BGE-M3 / multilingual-e5-large.

**Hybrid search.** Vector + structured filters (category, tags, geography).

**Freshness.** Items имеют `updated_at` и `active`; stale offers decay out.

**Outcome feedback.** Capturing (состоялся ли обмен) — задел для behavioral ranking.

### Выбор модели эмбеддингов — три опции

| Опция | Как работает | Плюсы | Минусы | Когда выбирать |
|-------|--------------|-------|--------|----------------|
| **A. OpenAI `text-embedding-3-small`** | облачные эмбеддинги (`OPENAI_API_KEY`) | лучшее качество, 1536 dim | платно, данные уходят в OpenAI | нужен максимум качества |
| **B. Локальная `sentence-transformers`** | модель локально (`all-MiniLM-L6-v2`, 384 dim) | бесплатно, приватно, офлайн | CPU/GPU, качество ниже | приоритет приватности |
| **C. Ollama `nomic-embed-text`** | локальный Ollama (`localhost:11434`) | бесплатно, легко менять модели | держать Ollama запущенным | уже используешь Ollama |

### Конфигурация (env)

```bash
SYNAPSE_EMBEDDING_PROVIDER=openai | local | ollama   # по умолчанию выключено (keyword-MVP)

# A
OPENAI_API_KEY=...
SYNAPSE_EMBEDDING_MODEL=text-embedding-3-small
# B
SYNAPSE_EMBEDDING_MODEL=all-MiniLM-L6-v2
# C
SYNAPSE_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

### Что войдёт в батч 7b

- Векторное хранилище: SQLite + numpy.
- Item-модель: `submit_offer`, `submit_want`, `list_my_items`, `deactivate_item`.
- `model_me(text)`, `find_my_match(query, limit)`.
- `draft_profile_from_dialog`.
- `search_people`/`search_notes` → эмбеддинги при заданном провайдере, иначе keyword-MVP (graceful fallback).
- Freshness: `updated_at` + `active` + decay.
- Outcome feedback: `report_match_outcome`.

---

## Батч 20 — Token economy (экономия токенов, план)

**Зачем:** ИИ-агенту легче работать, когда «дешёвые» по токенам вызовы отдают короткий ответ. Сейчас часть инструментов возвращает «простыни» (полные файлы, полные логи, длинные списки) — это дорого по контексту.

> **Принцип: не дублировать инструменты.** 110 + 110 `*_slim` = 220 раздует `tools/list` и запутает выбор. Вместо дублей — **параметр формата** в существующих методах (обратная совместимость: дефолт `full`).

### Что сделать

1. **`format: "full" | "compact"`** для «дорогих» list-методов:
   - `list_commits`, `list_branches`, `list_pull_requests`, `list_issues`, `list_releases`, `list_tags`, `list_workflow_runs`, `list_repo_contributors`.
   - `compact` → одна строка на элемент (`id | date | title`), без вложенных объектов.
2. **Подсказки в `description`** «дорогих» методов (`read_full_file`, `get_file_contents`, `get_full_workflow_logs`, `get_workflow_run_logs`): явно писать «для больших файлов/логов предпочитай `grep_file` / `read_file_chunk` / `grep_workflow_logs`».
3. **`fields=` (опционально)** — вернуть только запрошенные поля у list-методов.

### Как делать осторожно (не сломать)

- Дефолт остаётся `full` → существующие вызовы не меняются.
- `compact` — **новый** код-путь; покрыть быстрым тестом (smoke: `format=compact` возвращает строки, `format=full` — как раньше).
- Менять **по одному методу за PR**, после каждого — проверка, что `full` не сломан.
- Проверка после правки: `describe_tool(name)` показывает новый параметр; вызов с `format=compact` и без него даёт ожидаемое.

### Метрика

- До/после: размер ответа (байты) на типовом вызове `list_commits(format=compact)` vs `full`.
- Цель: −70…90% на листингах при сохранении `full` по запросу.

---

## Батч 8 — Авторизация и безопасность для публичного IP

⚠️ **Критично до любого публичного развёртывания.** Сейчас сервер слушает `0.0.0.0:3001`, не проверяет собственный токен, CORS открыт.

1. **`MCP_AUTH_TOKEN`** — требовать `Authorization: Bearer <MCP_AUTH_TOKEN>` на каждый запрос к `/mcp`.
2. **Разделить заголовки:** `X-MCP-Auth` (доступ к серверу) vs `Authorization: Bearer <github_token>` (GitHub API).
3. **CORS white-list** — вместо `CORS(app)`.
4. **Rate limit** — счётчик на IP + окно.
5. **TLS** — reverse-proxy (nginx / caddy) или Cloudflare Tunnel.
