# MCP GitHub Server

[![version](https://img.shields.io/badge/version-0.4.3-blue)](pyproject.toml)
[![tools](https://img.shields.io/badge/tools-runtime_registry-brightgreen)](TOOLS.md)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

Расширяемый MCP HTTP-сервер с модульной архитектурой и автоматическим обнаружением инструментов. Изначально вырос из обёртки над GitHub API, сейчас — универсальный набор инструментов для агента.

Сервер реализует **MCP Streamable HTTP transport** (JSON-RPC 2.0 поверх `POST /mcp`).

---

## 📌 Source of truth

| Что | Где источник правды |
|-----|---------------------|
| **Версия** | `mcp_server/__init__.py::__version__` — **0.4.3**; `pyproject.toml` читает её через dynamic version |
| **Список инструментов** | рантайм-реестр: `list_my_tools`; каталог — [`TOOLS.md`](TOOLS.md); состав зависит от feature flags |
| **Схема инструмента** | `describe_tool(name)` |
| **Документация** | ревизия **7** от **2026-10-15** |

> **Ревизия документации: 7 · 2026-10-15.** Инкрементируется при каждом значимом изменении README/ROADMAP/TOOLS/SANDBOX. При расхождении доков и рантайма — прав рантайм (код), доки приводим к нему. Ревизия 4: добавлен раздел «Продакшен (Gunicorn + Caddy)». Ревизия 5: добавлен подраздел «Пошаговый деплой на Ubuntu VPS», а также Windows/Waitress и примечание про PEP 668/venv. Ревизия 6: синхронизированы roadmap, карта проекта и границы планируемого бинарного канала #88 → #89; это документация, не реализация этих задач. Ревизия 7: полный runtime/docs audit, stateless HTTP-контракт, OS-границы и автоматические inventory/link/example guards.

---

## Статус проекта и новые задачи

- [Roadmap](ROADMAP.md) — приоритеты и проверяемые gates; [карта проекта](docs/project-map.md) — архитектура и зависимости. Код в `main`, кандидат в TEST и production — разные состояния.
- **Новый файловый маршрут запланирован, не реализован:** [#88](https://github.com/LeonidYasin/mcp-server/issues/88) (реальные bytes клиент → staging) → [#89](https://github.com/LeonidYasin/mcp-server/issues/89) (Release assets → Actions → проверяемый результат). Подробности и ограничения — [в плане](docs/binary-transfer-plan.md).
- `/data/...` в среде клиента **не является путём на MCP-сервере**. `run_command`, локальные файловые API и серверный `path` не передают файл между средами. Возможность реального клиента отправлять bytes надо доказать отдельно.
- `create_or_update_binary_file` сейчас декодирует base64 **как UTF-8** и записывает файл в Git: это не универсальный ZIP/XLSX upload и не staging. `download_artifact` относится к **Actions artifacts**, а не к Release assets.
- [PR #87](https://github.com/LeonidYasin/mcp-server/pull/87) — Draft, artifact attempt identity: не выдавать установку кандидата в TEST за завершённый live acceptance. `auto_fix_build` в `main` отключён; безопасная замена — [#86](https://github.com/LeonidYasin/mcp-server/issues/86).
- Эти планы не разрешают production deploy, публикацию приватных файлов, изменение приватности репозитория, платные сервисы или реальные вычисления. GitHub Pages — отдельный статический сайт; публикация не подтверждена этим PR.

---

## Возможности

**Актуальный состав инструментов:** `list_my_tools` на выбранном сервере и `describe_tool(name)`; каталог — [`TOOLS.md`](TOOLS.md). Инструменты разложены по подпакетам `mcp_server/tools/`. Каждый подпакет — независимая категория, которую можно включать и отключать отдельно.

### 🐙 `github/` — GitHub API

Файлы, коммиты, ветки, PR (включая review-threads), issues, releases, tags, gists, Actions/workflows, search, security-алерты.

| Группа | Инструменты |
|--------|-------------|
| Файлы | `get_file_contents`, `create_or_update_file`, `create_or_update_file_with_sha`, `create_or_update_binary_file`, `delete_file`, `move_file`, `replace_in_file`, `read_file_chunk`, `read_full_file`, `grep_file`, `list_directory` |
| Коммиты | `list_commits`, `get_commit_status`, `get_commit_diff`, `get_file_blame` |
| Ветки / сравнение | `list_branches`, `get_branch`, `create_branch`, `delete_branch`, `compare_branches`, `merge_branches` |
| PR | `create_pull_request`, `list_pull_requests`, `get_pull_request`, `update_pull_request`, `merge_pull_request`, `close_pull_request`, `add_pr_comment`, `request_pr_review`, `get_review_threads`, `resolve_review_thread`, `unresolve_review_thread` |
| Issues / метки | `create_issue`, `list_issues`, `get_issue`, `close_issue`, `add_issue_comment`, `add_labels` |
| Releases / Tags | `list_releases`, `create_release`, `get_latest_release`, `list_tags`, `create_tag`, `delete_tag` |
| Gists | `create_gist`, `list_gists`, `get_gist`, `update_gist` |
| Actions / Workflows | `dispatch_workflow`, `rerun_workflow`, `rerun_failed_jobs`, `cancel_workflow`, `list_workflows`, `list_workflow_runs`, `get_workflow_by_file`, `list_artifacts`, `download_artifact`, `get_workflow_run_status`, `get_workflow_run_steps`, `get_workflow_logs_preview`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `read_run_logs_offset`, `grep_run_logs`, `grep_workflow_logs` |
| Search | `search_code`, `search_commits`, `search_issues`, `search_repositories` |
| Security | `list_dependabot_alerts`, `list_code_scanning_alerts`, `list_secret_scanning_alerts` |
| Repo info / admin | `get_repo_info`, `get_repo_languages`, `get_repo_topics`, `list_repo_contributors`, `update_repo_info`, `get_repo_tree` |
| Batch | `push_multiple_files`, `read_multiple_files` |

> **Большие файлы.** `get_file_contents` отдаёт файл целиком — для больших файлов клиент может обрезать ответ (`[truncated]`). Используйте `read_file_chunk(owner, repo, path, ref, offset, limit)`: жёстко ограниченный кусок строк (≤ 32 KB). Поиск по файлу — `grep_file(...)`. Файл целиком без угадывания чанков — `read_full_file(...)` (сам подбирает размер, склеивает части, ставит `(конец файла)` либо предупреждение о бюджете `max_bytes`).
>
> **Прямые ссылки на файл.** `get_file_contents`/`read_full_file` в начале ответа возвращают `🔗` (blob) и `📄` (raw) ссылки.

### 🏗️ `build/` — сборка и отладка (13)

`watch_build`, `auto_fix_build`, `get_android_build_error`, `get_ios_build_error`, `get_run_logs_by_step`, `get_step_logs_via_checks`, `get_latest_workflow_error`, `get_workflow_run_logs`, `get_full_workflow_logs`, `get_workflow_by_file`, `list_workflow_runs`, `get_latest_run_id`, `get_workflow_run_steps`

### 🌐 `web/` — веб (4)

`web_fetch`, `web_search` (DuckDuckGo HTML, без API-ключа), `rss_read`, `html_to_markdown`

### 🧰 `utils/` — утилиты и данные (15)

`base64_encode`, `base64_decode`, `hash_text`, `json_format`, `json_query`, `uuid_generate`, `timestamp_now`, `date_convert`, `regex_test`, `text_diff`, `csv_parse`, `csv_generate`, `yaml_to_json`, `json_to_yaml`, `markdown_to_html`

### 🧭 `meta/` — мета-инструменты (2)

`list_my_tools`, `describe_tool`

### 🧠 `synapse/` — находимость людей (`ENABLE_SYNAPSE=1`)

При `ENABLE_SYNAPSE=1` зарегистрированы **14 инструментов**: `publish_profile`, `search_people`, `propose_contact`, `save_note`, `search_notes`, `index_github`, `submit_offer`, `submit_want`, `list_my_items`, `deactivate_item`, `model_me`, `find_my_match`, `draft_profile_from_dialog`, `report_match_outcome`. Item/embedding-код уже в main; регистрация не доказывает качество matching или доступность настроенного provider. Без provider используется keyword fallback. Протокол — [`docs/synapse-protocol.md`](docs/synapse-protocol.md).

### 🔒 `localfs/` — локальные файлы (4, по умолчанию выключено)

`read_local_file`, `write_local_file`, `list_local_dir`, `search_in_files`. Флаг `ENABLE_LOCAL_TOOLS=1`, корень `LOCAL_TOOLS_ROOT`. См. [`SANDBOX.md`](SANDBOX.md).

### 🔒 `localgit/` — git в workspace (6, по умолчанию выключено)

`git_status`, `git_log`, `git_diff`, `git_commit`, `git_push`, `git_pull`. Тот же флаг.

### 🔒 `shell/` — sandboxed shell / python (2, по умолчанию выключено)

`run_command`, `run_python`. Флаг `ENABLE_LOCAL_SHELL=1`; **cwd** ограничен `LOCAL_TOOLS_ROOT`, но исполняемый код имеет права пользователя сервера и может обращаться к другим доступным файлам/сети. Это не OS sandbox.

### 🔒 `process/` — фоновые процессы (4, Linux-only runtime)

`start_background`, `stop_process`, `process_status`, `tail_log`. Тот же `ENABLE_LOCAL_SHELL=1`; Linux identity guard, группы процессов, bounded чтение логов. [Контракт](docs/process-manager.md). См. [`SANDBOX.md`](SANDBOX.md).

---

## Установка

```bash
git clone https://github.com/LeonidYasin/mcp-server.git
cd mcp-server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

На Ubuntu с PEP 668 не устанавливать пакет в системный Python. Для разработки в уже активированном venv:

```bash
python -m pip install -e ".[dev]"
```

Для обычного запуска достаточно `python -m pip install -e .`; `[dev]` добавляет pytest для проверки проекта.

## Запуск

### Локально / для разработки

```bash
python -m mcp_server.server
```

По умолчанию сервер слушает **`http://127.0.0.1:3001`**, MCP-эндпоинт — `POST /mcp`. Bind можно явно переопределить `MCP_HOST`/`MCP_PORT`. `GET /health` показывает версию/build, `tool_count`, список инструментов и факт наличия заголовка последнего запроса, но не сам токен. При внешнем доступе защищать и `/health`: он раскрывает диагностическую информацию.

> ⚠️ **Это dev-режим.** Внутри используется встроенный dev-сервер Werkzeug; это не production deployment boundary, независимо от режима обработки потоков. Для локальной работы и отладки — ок, для боевого сервера — нет (см. раздел «Продакшен» ниже).

Токен GitHub передаётся заголовком `Authorization: Bearer <token>`.

### Продакшен (Gunicorn + Caddy)

Для боевого развёртывания используется классическая слоёная схема:

```
Интернет ──HTTPS(443)──▶ Caddy ──HTTP(127.0.0.1:3001)──▶ Gunicorn ──WSGI──▶ Flask app
```

- **Caddy** — принимает HTTPS, проверяет ключ клиента, проксирует на loopback.
- **Gunicorn** — production WSGI-сервер: несколько воркеров, устойчивость к падениям, корректная обработка сигналов.
- **Flask app** — сам код (`mcp_server.server:app`), без изменений.

#### 1. Установка зависимостей

```bash
pip install -e ".[prod]"   # gunicorn (Linux/macOS)
# или, если extra ещё не заведён в pyproject.toml:
pip install -e . gunicorn
```

#### 2. Запуск через Gunicorn

```bash
# слушаем ТОЛЬКО локальный интерфейс — из интернета напрямую недоступно
gunicorn mcp_server.server:app \
  --bind 127.0.0.1:3001 \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

Почему `--bind 127.0.0.1`: сервер не должен торчать в интернет сам по себе. Снаружи его закрывает Caddy, который терминирует TLS и аутентификацию. `--workers 2` — достаточно для одного пользователя/агента; при росте нагрузки увеличивается до `2 × CPU + 1`.

#### 3. Caddy (TLS + аутентификация по ключу)

Caddyfile (минимальный рабочий конфиг):

```caddy
mcp.example.com {
    # ключ клиента Claude передаётся в отдельном заголовке,
    # чтобы не конфликтовать с Authorization: Bearer <github_token>,
    # который уходит дальше в GitHub API
    @authorized header X-API-Key "<СЕКРЕТНЫЙ_КЛЮЧ_КЛИЕНТА>"

    handle @authorized {
        reverse_proxy 127.0.0.1:3001
    }

    handle {
        respond "Unauthorized" 401
    }
}
```

`mcp.example.com` Caddy сам получит и будет продлевать TLS-сертификат Let's Encrypt. Запросы без правильного `X-API-Key` отсекаются на входе и до приложения не доходят.

#### 4. systemd-юнит (автозапуск)

`/etc/systemd/system/mcp-server.service`:

```ini
[Unit]
Description=MCP GitHub Server
After=network.target

[Service]
Type=simple
User=mcp
WorkingDirectory=/opt/mcp-server
ExecStart=/opt/mcp-server/.venv/bin/gunicorn mcp_server.server:app \
    --bind 127.0.0.1:3001 --workers 2 --timeout 120
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-server
sudo systemctl status mcp-server
```

#### 5. Клиент (например, Claude как кастомный коннектор)

- **URL:** `https://mcp.example.com/mcp`
- **Request header:** `X-API-Key: <СЕКРЕТНЫЙ_КЛЮЧ_КЛИЕНТА>`
- GitHub-токен по-прежнему передаётся в `Authorization: Bearer <github_token>` и доходит до приложения как есть — Caddy его не трогает.

> **Почему не использовать dev-сервер в production.** `main()` по умолчанию использует loopback (`MCP_HOST=127.0.0.1`, `MCP_PORT=3001`, `debug=False`), но это не полноценная граница безопасности. Нужны production WSGI, TLS, аутентификация на proxy и OS policy. Явный `MCP_HOST=0.0.0.0` без такой защиты опасен; GitHub PAT не заменяет отдельную авторизацию доступа к MCP.

#### 6. Windows: Gunicorn не подходит — используйте Waitress

**Gunicorn не работает на Windows.** Он зависит от POSIX-модуля `fcntl`, которого в Windows нет:

```
ModuleNotFoundError: No module named 'fcntl'
```

Для Windows production-запуска есть **Waitress** — чистый Python WSGI-сервер, многопоточный, без POSIX-зависимостей и с официальной поддержкой Windows.

```bash
pip install waitress
waitress-serve --host=127.0.0.1 --port=3001 --threads=4 mcp_server.server:app
```

Остальная схема не меняется: Waitress так же слушает `127.0.0.1:3001` за reverse proxy (Caddy/Nginx/IIS), а Caddy терминирует TLS и проверяет `X-API-Key`.

| Платформа | WSGI-сервер | Причина |
|-----------|-------------|---------|
| Linux / macOS | **Gunicorn** | стандарт де-факто, multi-process |
| Windows | **Waitress** | чистый Python, multi-thread, без `fcntl` |

> **Для локального HTTP smoke на Windows** достаточно dev-сервера. Это не заменяет pytest, Linux process-manager tests, CI и live gates; process tools требуют Linux `/proc`. Waitress — вариант production WSGI для Windows, не замена OS-изоляции.

#### 7. Пошаговый деплой на Ubuntu VPS (проверено вживую)

Ниже — последовательность, реально отработанная на Ubuntu 24.04 VPS (2026-09-27): Gunicorn + Caddy + DuckDNS, снаружи проверено `curl`.

**Разделение ролей.** Команды помечены: `# root` — под root (или через sudo), `$ mcp` — под сервисным пользователем. Сервисный пользователь запускает приложение, но не имеет прав на systemd/apt/Caddy.

**Шаг 1. Сервисный пользователь (под root).**

Пользователь создаётся **с домашней папкой и shell**, но **без sudo**. Это важно: у него должны работать локальные инструменты (`localfs`, `localgit`, `shell`, работа с БД), поэтому нужен `$HOME` и `/bin/bash`. Ограничение только одно — нет прав за пределами `$HOME` и нет sudo.

```bash
# root
adduser --disabled-password --gecos "" mcp
# опционально: убедиться, что НЕ в группе sudo
deluser mcp sudo 2>/dev/null || true
```

**Шаг 2. Установка venv-пакетов (под root).**

Ubuntu 24.04 блокирует `pip install` в системный Python (PEP 668, `externally-managed-environment`). Поэтому ставим через venv:

```bash
# root
apt install -y python3-venv python3-full
```

**Шаг 3. Проект и venv (под сервисным пользователем).**

```bash
# mcp
cd ~
git clone https://github.com/LeonidYasin/mcp-server.git
cd mcp-server
python3 -m venv .venv
.venv/bin/pip install -e . gunicorn
```

Ключевое: `pip` — именно из venv (`.venv/bin/pip`), а не системный. И venv создаётся **под тем же пользователем**, который будет запускать сервис — чтобы файлы принадлежали ему.

**Шаг 4. systemd-юнит (под root).**

`/etc/systemd/system/mcp-server.service`:

```ini
[Unit]
Description=MCP GitHub Server
After=network.target

[Service]
Type=simple
User=mcp
Group=mcp
WorkingDirectory=/home/mcp/mcp-server
ExecStart=/home/mcp/mcp-server/.venv/bin/gunicorn mcp_server.server:app \
    --bind 127.0.0.1:3001 --workers 2 --timeout 120
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# root
systemctl daemon-reload
systemctl enable --now mcp-server
systemctl status mcp-server      # ожидаем: active (running)
```

Проверка изнутри (можно под любым пользователем):

```bash
curl -s http://127.0.0.1:3001/health | head -c 200
```

Должен вернуться JSON с `tool_count` и списком инструментов.

**Шаг 5. Домен.**

Нужен публичный домен, указывающий на IP VPS. Бесплатный вариант — [DuckDNS](https://www.duckdns.org): регистрируешь поддомен `имя.duckdns.org`, указываешь IP VPS. Проверка:

```bash
dig +short имя.duckdns.org      # должен вернуть публичный IP VPS
```

Домен обязателен: клиенты (в т.ч. Claude как кастомный коннектор) требуют URL вида `https://домен`, а Let's Encrypt выдаёт сертификат на домен. GitHub Pages для этого не подходит — он отдаёт только статику и не умеет проксировать на VPS.

**Шаг 6. Caddy: HTTPS + аутентификация по ключу (под root).**

Сгенерировать ключ клиента:

```bash
# root
openssl rand -hex 32
```

`/etc/caddy/Caddyfile`:

```caddy
имя.duckdns.org {
    # ключ клиента в отдельном заголовке, чтобы не конфликтовать
    # с Authorization: Bearer <github_token>, который уходит в GitHub API
    @authorized header X-API-Key "<СЕКРЕТНЫЙ_КЛЮЧ_КЛИЕНТА>"

    handle @authorized {
        reverse_proxy 127.0.0.1:3001
    }

    handle {
        respond "Unauthorized" 401
    }
}
```

```bash
# root
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
systemctl status caddy           # ожидаем: active (running)
```

Caddy сам получит и будет продлевать сертификат Let's Encrypt. Запросы без правильного `X-API-Key` отсекаются на входе (401) и до приложения не доходят.

**Шаг 7. Проверка снаружи (с любой машины, не с VPS).**

```bash
# без ключа — ожидаем 401
curl -i https://имя.duckdns.org/health

# с ключом — ожидаем 200 и JSON
curl -i -H "X-API-Key: <СЕКРЕТНЫЙ_КЛЮЧ_КЛИЕНТА>" https://имя.duckdns.org/health
```

Заголовок `Server: gunicorn` и `Via: 1.1 Caddy` в ответе подтверждают, что цепочка Caddy → Gunicorn работает.

**Шаг 8. Подключение клиента (например, Claude как кастомный коннектор).**

- **URL:** `https://имя.duckdns.org/mcp`
- **Request header:** `X-API-Key: <СЕКРЕТНЫЙ_КЛЮЧ_КЛИЕНТА>`

GitHub-токен по-прежнему передаётся в `Authorization: Bearer <github_token>` и доходит до приложения как есть — Caddy его не трогает.

**Шаг 9. Файрвол (опционально, под root).**

Gunicorn слушает только `127.0.0.1`, поэтому порт 3001 извне недоступен и без файрвола. Как дополнительный слой:

```bash
# root
ufw allow 22/tcp     # SSH — СНАЧАЛА, иначе потеряешь доступ
ufw allow 80/tcp     # HTTP-01 challenge для Let's Encrypt
ufw allow 443/tcp    # HTTPS
ufw enable
ufw status
```

Порт 3001 в UFW открывать не нужно.

### Включение локальных инструментов

```bash
export ENABLE_LOCAL_TOOLS=1          # localfs + localgit
export ENABLE_LOCAL_SHELL=1          # shell + process (опасные OS-права; только изолированная среда)
export ENABLE_SYNAPSE=1              # synapse
export LOCAL_TOOLS_ROOT=/workspace   # whitelist-корень (по умолчанию ~/workspace)
python -m mcp_server.server
```

## Подключение к DeepSeek++

- **URL:** `http://127.0.0.1:3001/mcp`
- **Тип:** HTTP
- **Заголовок:** `Authorization: Bearer <ваш_github_token>`

> **Транспорт:** используйте клиентский режим MCP Streamable HTTP, поддерживающий JSON-ответы на `POST /mcp`. Текущая реализация stateless: не выдаёт `Mcp-Session-Id`, не поддерживает SSE-поток (`GET /mcp` возвращает 405) и не реализует resumable sessions. Названия режимов в конкретном клиенте не гарантируют совместимость; клиент, требующий SSE или обязательный session ID, нужно проверять отдельно. [Фактический HTTP-контракт и offline smoke](docs/http-transport.md).

---

## 📚 Документация и Skills

| Файл | Что внутри |
|------|------------|
| [`README.md`](README.md) | этот файл: установка, запуск, обзор подпакетов, Source of truth |
| [`TOOLS.md`](TOOLS.md) | каталог по подпакетам, контракты и явно обозначенные ограничения |
| [`ROADMAP.md`](ROADMAP.md) | дорожная карта: текущие issues/PR, зависимости #88 → #89, сделанные батчи и backlog |
| [`docs/project-map.md`](docs/project-map.md) | карта архитектуры, доверительных границ и статусов разработки |
| [`docs/binary-transfer-plan.md`](docs/binary-transfer-plan.md) | план #88 → #89: клиентские bytes, staging, Release assets, Actions и критерии приёмки |
| [`SANDBOX.md`](SANDBOX.md) | границы localfs/localgit/shell/process, уровни 1–3 и ограничения |
| [`docs/http-transport.md`](docs/http-transport.md) | stateless HTTP-контракт, token gate и безопасный offline smoke |
| [`docs/validation.md`](docs/validation.md) | воспроизводимые проверки каталога, ссылок, тестов и сборки |
| [`docs/tool-inventory.json`](docs/tool-inventory.json) | автоматически сверяемые default/all-enabled профили реестра |
| [`docs/synapse-protocol.md`](docs/synapse-protocol.md) | JSON-схема обмена (item: offer/want, profile, contact, exchange) |
| [`docs/skills/github-mcp-safe-workflow/SKILL.md`](docs/skills/github-mcp-safe-workflow/SKILL.md) | **Skill для ИИ-агентов**: безопасный workflow работы с GitHub через MCP |

> **Skills** (`docs/skills/`) — это инструкции для ИИ-агентов, как правильно и безопасно пользоваться инструментами этого сервера. Каждый Skill — отдельная папка с `SKILL.md`. Новые Skills добавляйте рядом и упоминайте здесь.

---

## Структура проекта

```
mcp-server/
├── pyproject.toml           # dynamic version из mcp_server/__init__.py
├── README.md
├── ROADMAP.md
├── SANDBOX.md
├── TOOLS.md                 # полный каталог инструментов
├── docs/
│   ├── http-transport.md     # HTTP-контракт и ограничения
│   ├── validation.md         # проверка документации и сборки
│   ├── tool-inventory.json   # проверяемый snapshot реестра
│   ├── project-map.md        # архитектура, границы и статусы
│   ├── binary-transfer-plan.md # план #88 → #89 (не готовый API)
│   ├── synapse-protocol.md   # JSON-схема item/profile/contact/exchange
│   └── skills/               # Skills для ИИ-агентов (см. ниже)
└── mcp_server/
    ├── server.py            # Flask HTTP-сервер (MCP transport, token handling)
    ├── core/
    │   ├── tool.py          # Tool dataclass
    │   └── registry.py      # ToolRegistry + @mcp_tool
    └── tools/
        ├── build/           # сборка и отладка
        ├── github/          # GitHub API
        ├── localfs/         # локальные файлы (ENABLE_LOCAL_TOOLS)
        ├── localgit/        # git в workspace (ENABLE_LOCAL_TOOLS)
        ├── meta/            # list_my_tools, describe_tool
        ├── process/         # фоновые процессы (ENABLE_LOCAL_SHELL, Linux)
        ├── shell/           # shell/python (ENABLE_LOCAL_SHELL)
        ├── synapse/         # находимость людей (ENABLE_SYNAPSE)
        ├── utils/           # утилиты и данные
        └── web/             # web_fetch, web_search, rss, html
```

---

## Как добавить новый инструмент

### Шаг 1. Создайте файл в нужном подпакете

Учебный пример формы декоратора на существующем `create_branch` (не создавайте второй tool с тем же именем — в реестре names должны быть уникальными):

```python
"""MCP tool: create_branch - создаёт новую ветку."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="create_branch",
    description="Создаёт новую ветку в репозитории",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "branch": {"type": "string", "description": "Имя новой ветки"},
        "from_branch": {"type": "string", "description": "Источник (по умолчанию main)"},
    },
    required=["owner", "repo", "branch"],
)
def create_branch(client: GitHubClient, owner: str, repo: str, branch: str, from_branch: str = "main") -> dict:
    """Создать новую ветку."""
    ...
```

### Шаг 2. Подключите файл в `__init__.py` подпакета

Реестр (`mcp_server/core/registry.py`) регистрирует **только то, что явно импортировано** в `mcp_server/tools/<подпакет>/__init__.py`. Без импорта функция не станет инструментом.

### Шаг 3. Обновите доки

Добавьте инструмент в [`TOOLS.md`](TOOLS.md) и, если нужно, в этот README. Обновите snapshot (`python scripts/check_docs.py --write-inventory`), проверьте diff и выполните `python scripts/check_docs.py` + `python -m pytest -q`. Inventory regeneration не заменяет review: планируемые API в snapshot не включать. Инкрементируйте **ревизию документации** в блоке Source of truth. См. [validation](docs/validation.md).
