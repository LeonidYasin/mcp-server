# Release lookup и asset metadata — read-only этап #64/#89

Кандидат добавляет **два** инструмента: `get_release` и `list_release_assets`. Основан на `main` после #113, не на ветке upload PR #91. Это независимый read-only foundation, не реализация asset upload/download, tag update, publish или Actions E2E. До merge сверить пересекающиеся docs/inventory с PR #91; кандидаты не разворачиваются автоматически.

## Контракт

Оба handler возвращают JSON-строку внутри обычного MCP `content[0].text`. Проверять `ok`, не только HTTP200 внешнего MCP. Общие `owner`, `repo` ограничены GitHub identity; no arbitrary URL/path.

### get_release

```json
{"owner":"OWNER","repo":"REPO","tag":"v1.0.0"}
```

Либо `release_id` — положительный int, **ровно один** селектор. Tag со slash кодируется единым URL segment; опасные/невалидные параметры отвергаются до запроса. Проверяются совпадение ID/точного tag и типы draft/prerelease ответа. Возвращаются release_id/tag/name/target_commitish/draft/prerelease, даты и безопасные URL; тело описания и assets не включаются. `target_commitish` не выдается за resolved commit SHA.

`get_release` никогда не создаёт второй release на404, не публикует draft и не меняет tag. Старые list/create/latest handlers и их текстовые ответы сохранены без изменений.

### list_release_assets

```json
{"owner":"OWNER","repo":"REPO","release_id":123,"limit":25,"page":1}
```

Одна страница, limit1–100 (default25), page>=1. Возвращает assets с asset_id/name/label/size/content_type/state, датами и API/browser URL. Это **Release assets**, не Actions artifacts.

`digest` — только предоставленная GitHub строка; `digest_source=github` либо null. Она не выдаётся за локально вычисленный SHA-256 или проверенные bytes. Ни download URL, ни Link не запрашиваются. Метаданные URL с чужим origin, query/fragment/credentials не отражаются.

`pagination.scope=single_page`; `total_count=null`. При next Link возвращается числовой next_page без следования URL. Короткая страница означает has_next=false; полная страница без next Link — has_next=null, не обещание исчерпывающего списка. Неполная/невалидная страница отвергается целиком, дубли ID также отказ.

## Transport и ограничения

Только GET фиксированного `https://api.github.com`, без redirects, mutation/retry/fallback. Новые методы не используют legacy `_request`, который теряет HTTP-status и следует redirects. Stream закрывается на всех выходах; response<=512KiB, JSON result<=64KiB. При большом выводе уменьшить limit; скрытой обрезки строк/страниц нет. Connect/read timeout15s, проверяемый elapsed budget35s между чанками; это **не** строгий wall-clock deadline (блокирующее чтение может закончиться позднее).

401 → authentication_failed;403 → access_denied_or_rate_limited;404 → **not_found_or_inaccessible**, не доказательство отсутствия приватного/draft release;429 → rate_limited. Redirects отказ, unexpected shape/identity отказ, тело ошибок/exception text/PAT не выводятся. Permission restriction не обходится.

Требуемый repo access и token permissions проверять по [официальному Release API](https://docs.github.com/en/rest/releases/releases#get-a-release) и выбранной identity; отсутствие доступа не обходится. По контракту GitHub lookup по tag ориентирован на published release; draft доступность через tag не обещается. Здесь нет создания токенов, secrets или изменения permissions. Публичный read-only smoke не доказывает private/draft access с реальным PAT.

## Приёмка и границы

Unit/HTTP transport fixtures проверяют validation, selector identity, encoding, JSON/types, pagination/null digest, malformed/oversized responses, redirect refusal,401/403/404/429/5xx, bounded output и redaction. Не выполняются Release/asset mutations, Actions dispatch, deployment или root-команды.

Следующие части #89: streaming upload из verified file_id, bounded authenticated download в staging, integrity, name-conflict и unknown-POST reconciliation, затем отдельно разрешённый private-release/Actions/result E2E. #64 update_tag/update_release тоже вне этого read-only среза.

[Roadmap](../ROADMAP.md) · [Карта](project-map.md) · [Файловый план](binary-transfer-plan.md) · [Tools](../TOOLS.md).
