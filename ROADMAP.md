# ROADMAP — расширение MCP-сервера

Дорожная карта развития **mcp-server**. Цель — превратить сервер из GitHub-обёртки в универсальный «швейцарский нож» для агента.

> **Source of truth:** версия — `pyproject.toml`; список инструментов — рантайм `list_my_tools` + [`TOOLS.md`](TOOLS.md).
> **Ревизия ROADMAP: 4 · 2026-10-11** (см. README → Source of truth).

Легенда приоритетов:
- 🔴 высокий — блокирует базовые сценарии, делать первым
- 🟡 средний — ощутимо расширяет возможности
- 🟢 низкий — нишевое / требует осторожности

---

## План надёжности GitHub — 2026-10-11

Срез: открытые issues #53, #58–#69; открытые PR #56 и #57. Это план разработки через небольшие PR, **не разрешение менять production, сливать PR, публиковать releases или менять настройки чужих репозиториев**. Предыдущие функциональные батчи ниже сохранены как долгосрочный backlog.

### Порядок реализации

| Шаг | Приоритет | Issue / область | Отдельный PR и критерий завершения |
| --- | --- | --- | --- |
| 1 | Быстрое исправление | [#65](https://github.com/LeonidYasin/mcp-server/issues/65) — compare bounds | Единый max_files для summary/patch; 0 допустим, неверные лимиты отклоняются до API; SHA снимка, total/returned/truncated, ограничения patch bytes/lines, честная неполнота upstream; three-dot документирован. |
| 2 | P0 — сохранность данных | [#60](https://github.com/LeonidYasin/mcp-server/issues/60) — batch push | Сохранение executable/symlink modes одним tree-read, whitelist явных modes, expected_head_sha и отказ при конкурентном изменении. Не обходить ограничения force-push. |
| 3 | P0 — честный статус | [#61](https://github.com/LeonidYasin/mcp-server/issues/61) — statuses + checks | Пагинация обоих источников; success/failure/pending/no_checks/unknown; cancelled/timed_out не success, пустые legacy statuses не pending сами по себе. Branch protection отдельно. |
| 4 | P0 — безопасный merge | [#62](https://github.com/LeonidYasin/mcp-server/issues/62) — PR preflight | Полные SHA/draft/mergeable metadata; expected_head_sha передаётся как sha; disallowed method и изменившийся HEAD завершаются без merge. Зависит от достоверного чтения checks, но не обещает protection eligibility. |
| 5 | P0 — ложный success | [#67](https://github.com/LeonidYasin/mcp-server/issues/67) — draft transitions | GraphQL ready/draft mutations, ошибки permissions/closed/merged, идемпотентность и read-after-write. Согласовать с #57, не дублировать его проверку required args. |
| 6 | P0 — скачивание | [#63](https://github.com/LeonidYasin/mcp-server/issues/63) — artifacts | Получать 302 Location на сервере; HTTPS/host validation; Authorization не уходит на CDN; signed URL не попадает в persistent logs. Проверять 401/403/expired. |
| 7a | P1 — Actions identity | [#69](https://github.com/LeonidYasin/mcp-server/issues/69) — run attempts | run_attempt и SHA/time metadata; attempt-specific endpoints/cache; точные artifact ID, duplicate names. Не смешивать старую и новую попытки. |
| 7b | P1 — Actions diagnostics | [#69](https://github.com/LeonidYasin/mcp-server/issues/69), [#58](https://github.com/LeonidYasin/mcp-server/issues/58) — logs / Android | Fixtures per-step и combined-job ZIP, границы job/step или явный unsupported fallback. Затем compiler errors Kotlin/Java/Rust выше warnings, failed run не success. |
| 8a | P1 — диагностика доступа | [#53](https://github.com/LeonidYasin/mcp-server/issues/53) — HTTP errors | 403 может означать permissions, policy или rate limit; 404 — not found либо скрытый доступ. Подсказки без утверждения единственной причины и без раскрытия токена; никаких скрытых fallback. |
| 8b | P1 — диагностика протокола | [#59](https://github.com/LeonidYasin/mcp-server/issues/59) — create_issue persistence | Разделить GitHub effect и сохранение истории клиента. В main уже есть _normalize_content: сначала regression tests и проверка причины; не объявлять labels виноватыми без репро и не делать автоматический повтор потенциально успешного POST. |
| 9 | P1 — lifecycle releases | [#64](https://github.com/LeonidYasin/mcp-server/issues/64) — tags/releases | Сначала atomic update_tag + expected_old_sha и explicit force; затем отдельный PR get/update release + assets. Stable tags не перезаписывать неявно; сохранить assets, без delete/create обхода permissions. |
| 10 | P2 — новые возможности | [#68](https://github.com/LeonidYasin/mcp-server/issues/68) — repo features / Pages | Сначала only-supplied has_issues/has_discussions + read-back; затем Pages GET/POST/PUT с проверкой branch/path и deployment status. Configured, deployed и HTTP verified — разные состояния. |
| 11 | P2 — secrets boundary | [#66](https://github.com/LeonidYasin/mcp-server/issues/66) — Actions secrets | Public key + metadata listing; encrypted_value/key_id mutation. Plaintext только через реальную secure-input capability; без неё только заранее зашифрованный payload. Delete — отдельно и явно; values читать невозможно. |

P0 — приоритет по риску; шаг 1 выбран как маленькое изолированное исправление для запуска PR-процесса. Шаги 7a/7b и 8a/8b намеренно разделены, чтобы не объединять несколько независимых подсистем в один PR.

### Уже открытые PR

- [#57](https://github.com/LeonidYasin/mcp-server/pull/57): required args в update_pull_request. Нужны regression tests и актуальный CI; не заменяет #67 и #62.
- [#56](https://github.com/LeonidYasin/mcp-server/pull/56): background process manager. Отдельный security review: PID reuse, process-group ownership, cwd/env, logs и восстановление bookkeeping. Не дублировать ветку; не считать безопасность доказанной описанием PR.

### Gate для каждого шага

1. Прочитать issue, комментарии, актуальный код и пересекающиеся PR.
2. Отдельная feature/fix ветка от актуального main; regression test сначала, затем минимальное изменение и schema/docs в том же PR.
3. Локально весь pytest + smoke import; CI Python 3.10–3.13 и wheel build. В PR различать фактически выполненные проверки и запланированные.
4. Проверка tool schema/runtime discovery; negative cases, bounds, redaction, no incidental mutation. Mocked тесты не заменяют live-тесты.
5. Изменяющий GitHub integration test — только на явно разрешённом disposable объекте, без настоящих секретов и production deployment. Если не выполнен, явно указать это.
6. Ревью и зелёный CI до merge; issue закрывается только после merge и выполнения критериев. Невыполненные части — явные follow-ups, не ложный «готово».

### Финальная синхронизация документации и сайта

После согласованного этапа кодовых исправлений — отдельный documentation/site PR:

- README, TOOLS, SANDBOX, инструкции запуска и тестирования, примеры вызовов и schema contracts сверить с кодом, runtime discovery и feature flags. Обновить версии/счётчики без неподтверждённых чисел.
- ROADMAP актуализировать по merged PR и фактически закрытым acceptance criteria; оставшиеся issues не выдавать за выполненные.
- Майндмэп: найти существующий источник; если его нет, добавить версионируемый источник в репозиторий. Разделить архитектуру, инструменты, безопасность и этапы развития; согласовать его с ROADMAP.
- GitHub Pages: сначала проверить текущую конфигурацию/источник сайта. Подготовить согласованную документацию, проверить относительные ссылки, сборку и отсутствие секретов; настроить deployment только с нужными правами, без обхода ограничений.
- Проверить реальный deployment URL, commit/status и опубликованное HTTP-содержимое. «Файлы загружены» не означает «сайт опубликован». GitHub Pages — статическая документация, не хостинг MCP runtime.
- Не публиковать токены, Caddy secrets, приватные данные и неподтверждённые результаты; создать redacted примеры production/test конфигураций.
- Финальный review: ссылки, примеры, установка с чистого окружения, матрица CI и отметки live/mock проверки. Отдельно согласовать rollout боевого сервера и rollback.

Это финальный gate выбранного этапа, а не обещание закрыть весь backlog одним PR.

### Статус выполнения

- [x] Выполнен triage открытых issues и учтены #56/#57.
- [x] PR #57 слит: `5b7c2dd74715bdef32834102d423726bc2eac8a9`; 50 pytest + 28 live HTTP negative checks на тестовом VPS, CI Python 3.10–3.13 success. Production не обновлён.
- [x] Шаг 1 / #65: [PR #71](https://github.com/LeonidYasin/mcp-server/pull/71) слит: `ccd1c6fb475c86dc9630d0b06cbf6527b721e150`; issue #65 закрыт. 92 pytest на VPS, live TEST MCP limits/patch/identical-SHA checks и CI Python 3.10–3.13 success. Production не обновлён.
- [x] PR #56 слит: `85b3b5091864f26bc329cbc4f3ecf39ee068a579`; 150 pytest на VPS, remote TEST MCP TERM/KILL/status/log/metadata checks и systemd control-group restart cleanup passed. Linux identity/no-follow/limits и ограничения документированы. Production не обновлён, shell в production не включён.
- [x] Шаг 2 / #60: [PR #72](https://github.com/LeonidYasin/mcp-server/pull/72) слит: `1dfd6ba98065ca8cc15261bb243b9a443e951641`; issue #60 закрыт. 206 pytest на VPS + native bare-Git fixture, live GitHub сохранение executable/symlink modes и stale-HEAD conflict на разрешённой отдельной test branch; CI Python 3.10–3.13 success. Production не обновлён.
- [x] Шаг 3 / #61: [PR #73](https://github.com/LeonidYasin/mcp-server/pull/73) слит: `21bbafc89b0f08df717e12682318ff303634eef7`; issue #61 закрыт. 270 pytest на VPS, wheel/sdist build и CI Python 3.10–3.13 success; deployed TEST schema + live GitHub success/no_checks/output-cap/unknown checks passed. Production не обновлён.
- [ ] Шаг 4 / #62: [PR #74](https://github.com/LeonidYasin/mcp-server/pull/74) открыт — structured PR metadata, обязательный expected_head_sha, method-policy/checks preflight, повторный read перед единственным guarded PUT; unconfirmed не повторяется автоматически. Локально 333 pytest и wheel/sdist build success. Deployed TEST и merge gate пока не выполнены.
- [ ] Шаги 5–11: запланированы, не реализованы этим обновлением.
- [ ] Финальная синхронизация документации, майндмэпа и GitHub Pages: запланирована; опубликованный сайт ещё не проверен.

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
| **mcp-server** | GitHub/MCP-инструменты + Synapse | Python, Flask | MCP-интерфейс |

**Стратегия (вариант A):** не сливать репозитории, а унифицировать протокол. Общая спека `synapse-protocol` — JSON-схема для item (offer/want), profile, contact, exchange. На неё ссылаются и Synapse, и Agora, и NoKing.

---

## Текущее состояние

Точный набор зарегистрированных инструментов зависит от feature flags и проверяется `list_my_tools` на выбранной сборке; старые статические счётчики не подтверждают runtime-каталог. Реализовано (смержено в `main`):

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

⚠️ **Критично до любого публичного развёртывания.** В текущем `main` сервер по умолчанию слушает `127.0.0.1:3001` (можно явно переопределить `MCP_HOST`), не проверяет отдельный собственный токен, CORS открыт. Loopback не заменяет аутентификацию при публикации через reverse proxy.

1. **`MCP_AUTH_TOKEN`** — требовать `Authorization: Bearer <MCP_AUTH_TOKEN>` на каждый запрос к `/mcp`.
2. **Разделить заголовки:** `X-MCP-Auth` (доступ к серверу) vs `Authorization: Bearer <github_token>` (GitHub API).
3. **CORS white-list** — вместо `CORS(app)`.
4. **Rate limit** — счётчик на IP + окно.
5. **TLS** — reverse-proxy (nginx / caddy) или Cloudflare Tunnel.
