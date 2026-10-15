# HTTP transport: реализованный контракт и ограничения

Ревизия документации 7 · 2026-10-15. Источник — `mcp_server/server.py`, не общее описание MCP или возможностей конкретного клиента. Здесь описана текущая реализация; это не сертификат полного соответствия всем версиям MCP. [README](../README.md) · [Validation](validation.md).

## Адреса и lifecycle

- Dev bind: `MCP_HOST=127.0.0.1`, `MCP_PORT=3001`, `debug=False`; публичный доступ только через явно защищённый deployment.
- `POST /mcp`: JSON-RPC request → обычный JSON response, **не SSE**.
- `GET /mcp`: 405, `Allow: POST`. `OPTIONS /mcp`: 204. DELETE/session termination не реализован.
- `initialize`: принимает advertised protocol version из списка `2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05`; неизвестная версия заменяется на первую. Возвращает serverInfo/build и tools capability. Само объявление версии не доказывает все возможности её спецификации.
- `notifications/initialized` и другие `notifications/*`: 202, без JSON response body.
- `ping`: JSON-RPC result `{}`. `tools/list`: полный текущий registry без pagination. `tools/call`: вызов зарегистрированного handler.
- **Stateless:** не создаёт/не проверяет `Mcp-Session-Id`, не поддерживает reconnect/resume/event stream. `initialize` не создаёт обязательную серверную сессию.
- `GET /health`: runtime version/build/catalog, `last_request` только про наличие Authorization, не secret value. Защищать на proxy: это всё равно диагностическая информация. Last request хранится в памяти конкретного worker, не единый cluster-wide audit.
- Не поддерживаются JSON-RPC batch и произвольные MCP methods. Не обещать строгую generic schema validation для всех аргументов: `tools/call` передаёт их handler; конкретные инструменты имеют собственные проверки.

`_build_info()` читает Git metadata текущего cwd при запросе; commit из health не является immutable attestation загруженного кода, особенно если checkout меняли без restart. Проверять deployment procedure, точный checkout, service restart и runtime schema совместно.

## Два разных credential boundary

1. **Доступ к MCP:** в примере README его защищает Caddy `X-API-Key` + TLS. Приложение само не проверяет отдельный MCP access secret; tokenless tools и discovery без proxy доступны без такого контроля. CORS открыт, не считать его аутентификацией.
2. **GitHub:** приложение извлекает `Authorization: Bearer <github_token>`, создаёт GitHubClient для handler. В поле Bearer token клиента обычно вводится только PAT, без повторного префикса. Не дублировать Authorization отдельным header. PAT permissions не сужаются выбором TEST-пользователя OS.

Текущий `_tool_needs_token` основан на имени, а не на том, обращается ли handler к GitHub. Без Bearer разрешены только exact names `list_my_tools`, `describe_tool`, `web_fetch`, `web_search` и prefixes `base64_`, `hash_`, `json_`, `uuid_`, `timestamp_`, `date_`, `regex_`, `text_`.

Поэтому **CSV, yaml_to_json, RSS/html conversion, local tools и Synapse сейчас также проходят Bearer gate**, хотя некоторым handlers GitHub не нужен. Это ограничение реализации, не рекомендация расширять права PAT и не исправлено этим docs PR. Запрос GitHub без нужных permissions может отказать независимо от успешного initialize/discovery. `get_commit_status=success` не означает разрешённый merge.

`tools/call` возвращает нормализованные MCP text content blocks; не предполагать `structuredContent` для всех методов. JSON внутри строки `metadata:` — часть контракта конкретных инструментов, не универсальное поле транспорта. Исключения handler могут попадать в diagnostic logs: не включать verbose tracing секретов и не обещать полную redaction всех сторонних ошибок.

## Safe offline examples

Эти JSON requests проверяются через Flask test client, **без сети, PAT, приватных файлов или мутаций**:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"offline-doc-smoke","version":"1"}}}
```

```json
{"jsonrpc":"2.0","id":2,"method":"ping"}
```

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"hash_text","arguments":{"text":"hello","algo":"sha256"}}}
```

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"describe_tool","arguments":{"name":"get_pull_request"}}}
```

Для live read-only GitHub вызова сначала загрузить schema и permissions в выбранном deployment. Mutating examples/merge/release/service restart не являются smoke по умолчанию. Не переносить токены, headers или signed download capabilities в коммиты/CI logs.
