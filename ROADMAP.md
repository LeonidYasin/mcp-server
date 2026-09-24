# ROADMAP — расширение MCP-сервера

Дорожная карта развития `mcp-github-server`. Цель — превратить сервер из GitHub-обёртки в универсальный «швейцарский нож» для агента.

Легенда приоритетов:
- 🔴 высокий — блокирует базовые сценарии, делать первым
- 🟡 средний — ощутимо расширяет возможности
- 🟢 низкий — нишевое / требует осторожности

---

## Экосистема проектов (карта)

У автора шесть связанных репозиториев вокруг одной идеи: **находимость и обмен через ИИ-агента**.

```
┌──────────────────────────────────────────────────────────┐
│  NoKing — открытый протокол честного обмена              │
│  ─ любые ценности: товары, услуги, время, права, голоса  │
│  ─ DAO, комиссия 0.5–1%, репутация принадлежит участнику │
│  ─ MVP: HTML+JS+localStorage; план: Solidity/IPFS/The Graph │
└──────────────────────────────────────────────────────────┘
              │ идея-фундамент
    ┌─────────┼──────────────┬──────────────┐
    ▼         ▼              ▼              ▼
┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Civis   │ │ Synapse  │ │ Agora    │ │ mcp-     │
│ люди +  │ │ люди +   │ │ offers/  │ │ server   │
│ маркет. │ │ идеи     │ │ wants    │ │ (этот)   │
│ Telegram│ │ MCP+web  │ │ MCP+VPS  │ │ 90+ tools│
│ SQLite  │ │ файлы    │ │ pgvector │ │ Synapse  │
└─────────┘ └──────────┘ └──────────┘ └──────────┘
```

| Репозиторий | Домен | Стек | Роль |
|-------------|-------|------|------|
| **NoKing** | Обмен ценностями, DAO | HTML+JS → Solidity/IPFS | Протокол-фундамент |
| **Civis** | Люди по ценностям + маркетплейс | Python, SQLite, Telegram | Первый рабочий матчинг |
| **synapse** (старый) | Соцсеть на ИИ-чатах | концепция | Идейный предок |
| **synapse2** | ИИ-платформа поиска связей | FastAPI, DeepSeek | Веб-версия |
| **agora-mcp** | offers/wants, сетевой | TypeScript, Postgres+pgvector | Сетевой протокол |
| **mcp-server** | 90+ инструментов + Synapse | Python, Flask | MCP-интерфейс |

**Стратегия (вариант A):** не сливать репозитории, а унифицировать протокол. Общая спека `synapse-protocol` — JSON-схема для item (offer/want), profile, contact, exchange. На неё ссылаются и Synapse, и Agora, и NoKing.

---

## Текущее состояние

Реализовано (смержено в `main`):
- **Батч 1** — PR / Issues / Releases / Tags / batch-push, meta (`list_my_tools`, `describe_tool`), web (`web_fetch`, `web_search`), утилиты (base64/hash/json/uuid/date/regex/diff) → ~54 инструмента.
- **Батч 2** — branches, gists, Actions control (`dispatch`/`rerun`/`cancel`/`list_workflows`/`list_artifacts`), security alerts (`dependabot`/`code-scanning`/`secret-scanning`), repo info → ~75.
- **Батч 3** — web (`rss_read`, `html_to_markdown`), данные (`csv_parse`/`csv_generate`/`yaml_to_json`/`json_to_yaml`/`markdown_to_html`), commits (`get_commit_diff`, `list_directory`, `get_file_blame`) → ~85.
- **Батч 4** — sandboxed local filesystem: `read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`. По умолчанию **выключено** (`ENABLE_LOCAL_TOOLS=1`). См. `SANDBOX.md`.
- **Батч 5** — sandboxed local git: `git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`. Тот же флаг `ENABLE_LOCAL_TOOLS`.
- **Батч 6** — sandboxed shell / python: `run_command`, `run_python`. Флаг `ENABLE_LOCAL_SHELL=1`.
- **Батч 7a** — каркас Synapse без эмбеддингов: `publish_profile`, `search_people` (keyword-MVP), `propose_contact`, `save_note`, `search_notes`, `index_github`. Флаг `ENABLE_SYNAPSE=1`, данные в `SYNAPSE_DATA_DIR`.
- **Repo admin** — `update_repo_info` (description / homepage / topics).

---

## Единый sandbox-пул инструментов

Батчи 4–6 готовы: localfs + git + shell объединяются в **один изолированный workspace**:

- один `LOCAL_TOOLS_ROOT` (= `/workspace`) — общий whitelist;
- раздельные флаги `ENABLE_LOCAL_TOOLS` (fs + git) и `ENABLE_LOCAL_SHELL` (shell);
- всё выполняется под одним `mcp-sandbox` (Linux) / внутри WSL2 без automount;
- shell-команды и git-операции — только внутри `LOCAL_TOOLS_ROOT`.

Дальнейшее усиление — bwrap/Docker (уровни 3–4 в `SANDBOX.md`).

---

## Батч 7b — Эмбеддинг-матчинг в Synapse (следующий)

### Ключевой архитектурный урок (из agora-mcp)

**Item-модель, а не user-модель.** Не хранить одну эмбеддинг на пользователя. Хранить одну эмбеддинг на **item**, где item = `offer` | `want`. У пользователя может быть много items. Матчинг **асимметричный**: offer ↔ чужие want (не offer ↔ offer). Это зеркалит reciprocal-recommendation системы (dating, hiring), а не обычный semantic search.

**Instruction-aware эмбеддинги.** Разные префиксы для offer-роли и want-роли — измеримо улучшает crossed matching. Multilingual (RU+EN): BGE-M3 / multilingual-e5-large.

**Hybrid search.** Vector + structured filters (category, tags, geography). Чистый cosine выдаёт семантически близкое, но практически бесполезное («ищу репетитора по английскому» vs «предлагаю уроки испанского»).

**Freshness.** Items имеют `updated_at` и `active` flag; stale, unconfirmed offers должны decay out, а не накапливаться вечно.

**Outcome feedback.** Нужно capturing (состоялся ли обмен, был ли полезен) — без этого сигнала невозможен behavioral ranking layer.

### Выбор модели эмбеддингов — три опции

| Опция | Как работает | Плюсы | Минусы | Когда выбирать |
|-------|--------------|-------|--------|----------------|
| **A. OpenAI `text-embedding-3-small`** | облачные эмбеддинги через HTTP API (`OPENAI_API_KEY`) | лучшее качество из коробки, ноль локальных ресурсов, 1536 dim | платно (~$0.02 / 1M токенов), данные уходят в OpenAI, нужен интернет | нужен максимум качества и готов платить |
| **B. Локальная `sentence-transformers`** | модель скачивается один раз, работает локально (`all-MiniLM-L6-v2` — 384 dim; `bge-small-en` — 384 dim) | бесплатно, приватно, работает офлайн | ~100–400 MB, нужен CPU (медленно) или GPU, качество ниже OpenAI | приоритет приватности и нулевой стоимости |
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
- Item-модель: `submit_offer`, `submit_want`, `list_my_items`, `deactivate_item` (по образцу agora-mcp).
- `model_me(text)` — строит эмбеддинг-слепок из описания/диалога.
- `find_my_match(query, limit)` — косинусный поиск похожих.
- `draft_profile_from_dialog` — сборка профиля из диалога (ключевая идея Synapse из памяти #16/#17).
- `search_people`/`search_notes` переключаются на эмбеддинги, если провайдер задан; иначе — keyword-MVP (graceful fallback).
- Freshness: `updated_at` + `active` + decay.
- Outcome feedback: `report_match_outcome` (задел для behavioral ranking).

---

## Батч 8 — Авторизация и безопасность для публичного IP

⚠️ **Критично до любого публичного развёртывания.** Сейчас сервер слушает `0.0.0.0:3001`, не проверяет собственный токен, CORS открыт.

### Что нужно

1. **`MCP_AUTH_TOKEN`** — сервер требует `Authorization: Bearer <MCP_AUTH_TOKEN>` на каждый запрос к `/mcp`. Без него — 401.
2. **Разделить заголовки:** `X-MCP-Auth` (доступ к серверу) vs `Authorization: Bearer <github_token>` (GitHub API).
3. **CORS white-list** — вместо `CORS(app)` указать конкретный origin.
4. **Rate limit** — счётчик на IP + окно (60 запросов/мин).
5. **TLS** — reverse-proxy (nginx / caddy) или Cloudflare Tunnel.
6. **Правило:** публичный IP ⇒ локальные инструменты выключены.

### Опции (по умолчанию безопасно)

| Переменная | Что делает |
|-----------|------------|
| `MCP_REQUIRE_AUTH=1` | включает проверку `MCP_AUTH_TOKEN` |
| `MCP_AUTH_TOKEN=...` | сам токен |
| `MCP_CORS_ORIGINS=https://...` | список разрешённых origin через запятую |
| `MCP_RATE_LIMIT=60` | запросов в минуту на IP (0 = без лимита) |
| `ENABLE_LOCAL_TOOLS` | НЕ задавать на публичном IP |
| `ENABLE_LOCAL_SHELL` | НЕ задавать на публичном IP |

---

## Батч 9 — Протокол, сайт, прочее

- **`docs/synapse-protocol.md`** — общая JSON-схема: item (offer/want), profile, contact, exchange. С учётом идей NoKing (двусторонний обмен, репутация) и Agora (item-based эмбеддинги, freshness). На неё ссылаются все репозитории экосистемы.
- **GitHub Pages** — сайт репозитория из README (уже включено, Website в About).
- **Telegram-индексация** для Synapse.
- **Экспорт профиля в gist**.
- **A2A-слой** для negotiation после матча (Stage 3 у Agora).

### Открытые вопросы (не закрыты в концепциях)

1. **Идентичность и верификация** — как проверить, что за профилем реальный человек, а не бот/фейк.
2. **Federation** — обмен items/profiles между разными MCP-серверами (Synapse локально vs Agora на VPS).
3. **Anti-spam** — `propose_contact` без ограничений = флуд.
4. **Demand routing** — как захватить покупателя в момент решения (мысль из памяти #20).
5. **Экономика** — модели монетизации (NoKing предлагает комиссию 0.5–1%).
6. **Разговорный сбор профиля** — `draft_profile_from_dialog` (в 7a не реализовано).

---

## Технические заметки

- Версия проекта — единый источник: `mcp_server/__init__.py` (`__version__`). `server.py` и `pyproject.toml` читают её.
- Инструменты возвращают `str`; обёртка в MCP-контент — на стороне `server.py`.
- Новый файл с инструментами импортируется в `__init__.py` соответствующего подпакета.
- `ToolRegistry.discover()` сканирует подпакеты в `mcp_server/tools/`.
- Единственный канонический декоратор — `mcp_server.core.registry.mcp_tool`.
- Опасные категории (shell, local fs, local git) — отдельные подпакеты, отключаются одной строкой.
- `localfs/__init__.py` и `localgit/__init__.py` сами решают, регистрировать инструменты или нет (по `ENABLE_LOCAL_TOOLS`).
- `shell/__init__.py` — то же, но с флагом `ENABLE_LOCAL_SHELL`.
- `synapse/__init__.py` — то же, но с флагом `ENABLE_SYNAPSE`.
