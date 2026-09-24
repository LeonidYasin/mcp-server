# SANDBOX.md — изолированный запуск MCP с доступом к локальным файлам

Эти инструкции нужны, если вы включаете инструменты `read_local_file`,
`write_local_file`, `list_local_dir`, `search_in_files` (флаг `ENABLE_LOCAL_TOOLS=1`).

Цель: агент видит **только** одну папку и не может навредить системе,
другим пользователям или вашему Windows-диску.

---

## Уровни изоляции

| Уровень | Что даёт | Когда использовать |
|---|---|---|
| **1. Обычный Linux-пользователь** | Не может писать в систему, чужие home, убивать чужие процессы | Базовый минимум (по умолчанию) |
| **2. `bubblewrap`** | + нет сети, нет чужих процессов, только `/workspace` | Если нужна сильная изоляция |
| **3. Docker/Podman** | + лимиты CPU/RAM/PID, read-only rootfs | Продакшн |

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

```bash
sudo -u mcp-sandbox -H bash -lc '
  cd ~ && git clone https://github.com/LeonidYasin/mcp-server.git
  cd mcp-server && pip install --user -e .
'
```

### 3. Запустить

```bash
sudo -u mcp-sandbox -H bash -lc '
  cd ~/mcp-server
  ENABLE_LOCAL_TOOLS=1 \
  LOCAL_TOOLS_ROOT=/home/mcp-sandbox/workspace \
  python -m mcp_server.server
'
```

### 4. (Опционально) Уровень 2 — bubblewrap

```bash
sudo -u mcp-sandbox bwrap \
  --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
  --ro-bind /etc /etc \
  --ro-bind /home/mcp-sandbox/mcp-server /app \
  --bind /home/mcp-sandbox/workspace /workspace \
  --tmpfs /tmp --proc /proc --dev /dev \
  --unshare-all --die-with-parent \
  env ENABLE_LOCAL_TOOLS=1 LOCAL_TOOLS_ROOT=/workspace \
  python -m mcp_server.server
```

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
appendWindowsPath = false
EOF
```

Затем из PowerShell перезапустите WSL:

```powershell
wsl --shutdown
```

После перезапуска `/mnt/c`, `/mnt/d` будут недоступны — изоляция от Windows-диска.

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
  cd mcp-server && pip install --user -e .
'

sudo -u mcp-sandbox -H bash -lc '
  cd ~/mcp-server
  ENABLE_LOCAL_TOOLS=1 \
  LOCAL_TOOLS_ROOT=/home/mcp-sandbox/workspace \
  python -m mcp_server.server
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
| `ENABLE_LOCAL_TOOLS` | (пусто) | `1` — включает localfs-инструменты. Всё остальное — выключено. |
| `LOCAL_TOOLS_ROOT` | `~/workspace` | Whitelist-корень. Всё вне — отказ. |
| `LOCAL_TOOLS_MAX_READ_BYTES` | `1000000` | Лимит на чтение файла. |
| `LOCAL_TOOLS_MAX_WRITE_BYTES` | `1000000` | Лимит на запись файла. |
| `LOCAL_TOOLS_MAX_LIST_ENTRIES` | `1000` | Лимит элементов в листинге. |
| `LOCAL_TOOLS_MAX_GREP_MATCHES` | `200` | Лимит совпадений в поиске. |

---

## Что НЕ закрывает обычный пользователь

Эти векторы закрываются только bwrap/Docker (уровни 2–3):

1. Чтение world-readable файлов (`/etc/passwd`, логи, конфиги с `o+r`).
2. Полный доступ в сеть (если хендлер скомпрометируют).
3. DoS: fork-бомба, забивание диска/RAM.
4. Доступ к `ssh-agent`, docker-сокету и другим IPC.

Для локального использования на своей машине уровень 1 — разумный минимум.
