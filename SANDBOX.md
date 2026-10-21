# SANDBOX.md — изолированный запуск MCP с доступом к локальным файлам

Эти инструкции относятся к localfs/localgit (`ENABLE_LOCAL_TOOLS=1`), а также более опасным shell/process (`ENABLE_LOCAL_SHELL=1`). Ревизия документации 10 · 2026-10-16.

Цель — минимизировать права и явно задать OS-изоляцию. **Сам пакет не гарантирует, что агент видит только одну папку.** Cwd/path guards не заменяют sandbox, защиту секретов, сетевую policy и ограничения ресурсов.

---

## Клиентская среда и серверный workspace — разные границы

`LOCAL_TOOLS_ROOT` ограничивает рабочую директорию локальных tools на MCP-сервере; это **не общий диск с клиентом**. Например, Notion `/data/input.zip` недоступен VPS по тому же имени. `run_command`/server-local `path` не передают bytes; cwd-ограничение само по себе не является полной OS-изоляцией shell. Защита чтения/записи вне workspace зависит также от пользователя, sandbox/container и service policy.

Новый канал [#88 → #89](docs/binary-transfer-plan.md) пока запланирован: доказанный client transport → отдельный bounded staging → scoped opaque `file_id` → Release assets. Нельзя считать произвольный path или незавершённый upload валидным file_id. Нужны authentication/owner isolation, проверка bytes/size/SHA-256, квоты/TTL/cleanup, no traversal/symlink/SSRF и redaction tickets/секретов. Сам сервер не получает доступ к клиентскому sandbox.

Не ослаблять изоляцию TEST/production и не включать shell для решения передачи файла. Тот же GitHub PAT сохраняет права в обоих окружениях; отдельный Unix-пользователь не ограничивает GitHub-доступ. [Карта](docs/project-map.md) · [Roadmap](ROADMAP.md).

Малый synthetic client→TEST probe #88 выполнен через file-backed arguments и проверку в памяти; это не upload API и не основание включать shell в production. [Ограничения](docs/binary-transfer-plan.md#предварительная-feasibility--2026-10-15). Production обновлён отдельно на `b78b209…` без ослабления flags; [снимок окружений](docs/deployment-status.md).

## Уровни изоляции

| Уровень | Что даёт | Когда использовать |
|---|---|---|
| **1. Отдельный non-root пользователь** | Ограничения DAC/UID; только если ему не выданы sudo, общие writable пути или опасные группы/IPC | Минимум привилегий, не полноценный sandbox |
| **2. `bubblewrap`** | Mount/PID/network namespaces согласно явно выбранным bind/unshare options | Policy надо адаптировать и проверить; имя программы само по себе не изолирует |
| **3. Docker/Podman** | Namespaces и настраиваемые CPU/RAM/PID/filesystem/network ограничения | Лимиты, read-only rootfs, non-root и volumes задаются явно; docker socket не монтировать |

Уровни 2 и 3 — опционально, см. ROADMAP.md.

---

## Linux (нативный)

### 1. Создать пользователя

```bash
sudo adduser --disabled-password --gecos "" mcp-sandbox
sudo mkdir -p /home/mcp-sandbox/workspace
sudo chown -R mcp-sandbox:mcp-sandbox /home/mcp-sandbox/workspace
```

### 2. Установить сервер (от mcp-sandbox)

Нужны системные `git`, `python3` и пакет поддержки venv (например `python3-venv` на Ubuntu); устанавливает администратор. Использовать venv, не системный pip/`--user` под PEP 668. Ниже обычная установка пакета из checkout; для разработки editable install выбирается отдельно.

```bash
sudo -u mcp-sandbox -H bash -lc '
  cd ~ && git clone https://github.com/LeonidYasin/mcp-server.git
  python3 -m venv ~/venv
  ~/venv/bin/python -m pip install ~/mcp-server
'
```

### 3. Запустить

```bash
sudo -u mcp-sandbox -H bash -lc '
  cd ~/mcp-server
  ENABLE_LOCAL_TOOLS=1 \
  LOCAL_TOOLS_ROOT=/home/mcp-sandbox/workspace \
  ~/venv/bin/python -m mcp_server.server
'
```

### 4. (Опционально) Уровень 2 — bubblewrap policy

Это **не готовый production recipe**: прежний минимальный пример не монтировал Python environment и не настраивал cwd/import path. Не копировать непроверенную команду как доказательство изоляции.

Для конкретного дистрибутива и установленного venv явно выбрать и проверить:

- read-only Python runtime, необходимые loader/libs и установленный пакет; не открывать весь home или `/etc` ради удобства;
- единственный необходимый writable workspace, отдельный `/tmp`, private PID namespace и `/proc`;
- `cwd`/`HOME`/`LOCAL_TOOLS_ROOT` внутри workspace; отсутствие SSH/docker/agent sockets, токенов и лишних environment values;
- network namespace: полный запрет сети делает GitHub/web tools неработоспособными и не предоставляет HTTP-доступ к сервису с host. Доступ клиента и разрешённые outbound destinations требуют отдельного дизайна;
- cgroup/resource/disk/log quotas отдельно: `bubblewrap` сам не выставляет CPU/RAM/PID/disk limits;
- negative tests изоляции и shutdown/descendant cleanup. Не ослаблять policy, чтобы обойти failing smoke.

WSL/bubblewrap/container deployment не запускался в текущем docs PR. Проверки конкретной OS policy и рабочего HTTP-доступа — отдельный acceptance gate.

---

## Windows через WSL2

### 1. Поставить WSL2 (если ещё нет)

```powershell
wsl --install -d Ubuntu
wsl --set-default-version 2
```

### 2. Отключить automount — КРИТИЧНО

По умолчанию WSL2 монтирует `C:\` в `/mnt/c`, и пользователь внутри WSL может
писать в `C:\Users\<you>\`. Чтобы это закрыть, создайте файл:

```bash
sudo tee /etc/wsl.conf >/dev/null <<'EOF'
[automount]
enabled = false

[interop]
enabled = false
appendWindowsPath = false
EOF
```

Затем из PowerShell перезапустите WSL:

```powershell
wsl --shutdown
```

Это отключает автоматическое монтирование Windows-дисков и Win32 interop в данной WSL-конфигурации. Проверить результат после перезапуска; уже смонтированные/manual mounts, дополнительные shares, sockets и права администратора — отдельные риски. WSL сам по себе не превращает обычного пользователя в полностью изолированный sandbox.

### 3. Создать пользователя внутри WSL

```bash
sudo adduser --disabled-password --gecos "" mcp-sandbox
sudo mkdir -p /home/mcp-sandbox/workspace
sudo chown -R mcp-sandbox:mcp-sandbox /home/mcp-sandbox/workspace
```

### 4. Установить и запустить сервер под mcp-sandbox

```bash
sudo -u mcp-sandbox -H bash -lc '
  cd ~ && git clone https://github.com/LeonidYasin/mcp-server.git
  python3 -m venv ~/venv
  ~/venv/bin/python -m pip install ~/mcp-server
'

sudo -u mcp-sandbox -H bash -lc '
  cd ~/mcp-server
  ENABLE_LOCAL_TOOLS=1 \
  LOCAL_TOOLS_ROOT=/home/mcp-sandbox/workspace \
  ~/venv/bin/python -m mcp_server.server
'
```

### 5. Доступ из Windows

WSL2 автоматически пробрасывает порт на Windows как `localhost`. В настройках
DeepSeek++ укажите `http://127.0.0.1:3001/mcp`.

Проверка из PowerShell:

```powershell
curl http://127.0.0.1:3001/health
```

---

## Env-переменные

| Переменная | По умолчанию | Что делает |
|---|---|---|
| `ENABLE_LOCAL_TOOLS` | (пусто) | `1`, `true`, `yes`, `on` (без учёта регистра/краевых пробелов) — localfs + localgit; прочие значения выключают. |
| `LOCAL_TOOLS_ROOT` | `~/workspace` | Корень path/cwd guards. Не запрещает произвольному shell/Python читать другие доступные OS файлы. |
| `LOCAL_TOOLS_MAX_READ_BYTES` | `1000000` | Лимит на чтение файла. |
| `LOCAL_TOOLS_MAX_WRITE_BYTES` | `1000000` | Лимит на запись файла. |
| `LOCAL_TOOLS_MAX_LIST_ENTRIES` | `1000` | Лимит элементов в листинге. |
| `LOCAL_TOOLS_MAX_GREP_MATCHES` | `200` | Лимит совпадений в поиске. |
| `ENABLE_LOCAL_SHELL` | (пусто) | `1`/`true`/`yes`/`on` — включает `run_command`/`run_python`, а также `start_background`/`stop_process`/`process_status`/`tail_log` (см. ниже). |
| `LOCAL_TOOLS_SHELL_TIMEOUT` | `60` | Таймаут `run_command`/`run_python`; не обещает остановку всех отделившихся потомков. |
| `LOCAL_TOOLS_MAX_OUTPUT_BYTES` | `200000` | Process: UTF-8 byte cap (clamped 1–1000000); shell legacy truncates characters after capturing output, не hard memory limit. |
| `LOCAL_TOOLS_STOP_TIMEOUT` | `10` | Сколько секунд `stop_process` ждёт после SIGTERM; допустимо 0–30, без автоматического SIGKILL. |

---

## Фоновые процессы (`start_background` / `stop_process` / `process_status` / `tail_log`)

Отдельная опасность внутри `ENABLE_LOCAL_SHELL`, а не новая категория: те же
права, что и у `run_command`, но результат — **живой процесс, который остаётся
после ответа инструмента**. `run_command` ждёт direct child с timeout через `subprocess.run`; это не гарантия зачистки всех потомков/групп.
`start_background` не получает lifetime timeout, это его смысл (например, поднять `node dist/index.js`
и не уронить его через 30 секунд).

Что важно знать:

- Bookkeeping (pid + Linux identity, cmd, cwd, лог) хранится в
  `LOCAL_TOOLS_ROOT/.mcp_processes/<name>.{json,log}`. Файлы сохраняются при
  перезапуске, но живые процессы **не обязаны** его переживать: default systemd
  `KillMode=control-group` останавливает потомков сервиса. Новая session не
  выводит процесс из cgroup. Не ослабляйте KillMode неявно.
- Перед сигналом сверяются boot ID, start ticks, UID, PGID и SID; stale/legacy
  identity не получает сигнал. Управление требует Linux `/proc`.
- Metadata/logs открываются без следования symlinks, hardlinks/FIFO отклоняются;
  tail_log использует canonical path и bounded UTF-8 bytes вместо чтения всего лога.
- Подробный контракт, ограничения PID race, lifetime и секретов: [process manager](docs/process-manager.md).
- `stop_process` шлёт сигнал **всей группе процессов** (`os.killpg`), не
  только сохранённому pid — иначе `bash -c "...; sleep N"` может не
  среагировать на SIGTERM вовремя (bash откладывает обработку trap до
  возврата из синхронного foreground-потомка).
- То же action deny-list, что у `run_command` (`sudo`, `rm -rf /`, `mkfs`, ...).
- Никакой доп. изоляции по CPU/RAM/времени жизни — заглянувший сюда процесс
  живёт, пока жив сам, или пока его не остановят явно. Уровень 2/3
  (bwrap/Docker) ограничивает это так же, как и остальные local-tools.

---

## Что НЕ закрывает обычный пользователь

Ниже — риски, для которых нужна проверенная OS/container/network/resource policy. Простое наличие bwrap/Docker не доказывает, что они закрыты:

1. Чтение world-readable файлов (`/etc/passwd`, логи, конфиги с `o+r`).
2. Полный доступ в сеть (если хендлер скомпрометируют).
3. DoS: fork-бомба, забивание диска/RAM.
4. Доступ к `ssh-agent`, docker-сокету и другим IPC.

Для arbitrary shell/process отдельный non-root user — лишь минимум. Не включать на личной машине с ценными данными или в production без проверенной policy, независимо от path guard. Установка/перезапуск сервисов и реальная проверка изоляции в этом docs PR не выполняются.

## Read-only discoverability candidate

`audit_repo_seo` не использует localfs/shell/process и не расширяет sandbox. Public GitHub GET по умолчанию без токена; private — явный opt-in. Нет fetch внешних ссылок/установки пакетов/изменений репо. [Контракт и бюджеты](docs/repo-discoverability.md).
