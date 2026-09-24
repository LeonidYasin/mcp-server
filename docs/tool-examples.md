# Tool examples catalog

Здесь собраны примеры использования инструментов MCP-сервера. До батча 19
эти примеры дублировались в `description` каждого `@mcp_tool` и раздували
ответ `tools/list`, из-за чего клиент DeepSeek++ упирался в `kQuotaBytes`.
Теперь `description` держим одной строкой, а все примеры, паттерны и
расширенные пояснения — здесь.

Соглашение: раздел заводится только для инструментов с нетривиальными
паттернами/примерами. Тривиальные (`list_branches`, `get_me`, `list_tags`
и т.п.) сюда не попадают.

---

## file_ops

### grep_file
Поиск по файлу без вычитывания всего тела.

```jsonc
{
  "owner": "LeonidYasin",
  "repo": "mcp-server",
  "path": "mcp_server/tools/github/file_ops.py",
  "pattern": "def grep_file",
  "regex": false,
  "case_sensitive": false,
  "max_matches": 20,
  "ref": "main"
}
```

### read_file_chunk
Возвращает жёстко ограниченный кусок (≤ 32 KB) с заголовком
`[строки N-M из K]` и подсказкой следующего `offset`.

```jsonc
{ "owner": "o", "repo": "r", "path": "big.log", "ref": "main", "offset": 0, "limit": 400 }
```

### read_multiple_files
Чтение пачки файлов одним вызовом — удобно для ревью PR, когда надо
посмотреть 3–5 файлов сразу.

### read_full_file
Склеивает файл из кусков (бюджет ~24 KB на срез), в конце ставит
`(конец файла)` либо предупреждение о достижении `max_bytes`.
Используй, когда `get_file_contents` вернул `[truncated]`.

---

## workflows / workflow_runs

### get_workflow_run_logs — типовые `grep_pattern`

Строки, которые чаще всего ищут в логах Android/iOS-сборки:

```
e: file
error:
Unresolved reference
Caused by
FAILURE:
Execution failed for task
```

Поведение:
- `grep_pattern` — regex, ищется по **всем** файлам архива;
- `grep_context` — строк контекста вокруг совпадения (по умолчанию 1, как `grep -C1`);
- одинаковые совпадения из разных файлов помечаются `(same as ...)`;
- `tail_lines=0` — отдавать только результат grep, без хвоста логов.

### read_run_logs_offset
Читает лог рана порциями. Начинать с `offset=0`, `limit=200`;
увеличивать `offset`, пока в ответе присутствует `next_offset`.

### grep_run_logs
Поиск по логу конкретного рана:
- `pattern` — подстрока или регексп (при `regex=true`);
- `context_lines` — сколько строк вокруг матча вернуть.

### grep_workflow_logs
Поиск по логам всех шагов workflow по имени файла workflow
(например `.github/workflows/android.yml`). Полезно, когда `run_id` неизвестен.

### get_workflow_run_status
Мгновенный (неблокирующий) снимок: `status`, `conclusion`, `jobs[]`
со статусами/результатами и списком проваленных шагов.
Заменяет polling в `watch_build`.

---

## pull_requests

### get_review_threads
Возвращает ревью-треды. Чтобы **закрыть** тред, нужен `threadId`
вида `PRRT_kwDOxxx`, не числовой id комментария.

### resolve_review_thread / unresolve_review_thread
Идемпотентны: повторный resolve уже resolved-треда — no-op.

---

## batch

### move_file
Git не умеет «move» через один REST-вызов; `move_file` делает
create + delete в одном коммите. Требует `sha` исходного файла.

---

## batch 19 — журнал выноса

| Файл | Инструмент | Что вынесено |
|------|-----------|--------------|
| workflows.py | get_workflow_run_logs | примеры `grep_pattern` → раздел workflows |
| workflow_runs.py | get_workflow_run_status | пояснение «заменяет polling» → раздел workflows |
| file_ops.py | grep_file, read_file_chunk, read_full_file | примеры → раздел file_ops |

_(дополняется по мере сжатия)_
