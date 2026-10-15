# План бинарного маршрута: #88 → #89

Ревизия документации 6 · 2026-10-15. **Статус: требования и дизайн-гейты, не реализованный API.** Источники: [issue #88](https://github.com/LeonidYasin/mcp-server/issues/88), [issue #89](https://github.com/LeonidYasin/mcp-server/issues/89). На момент triage оба open, комментариев нет. [Roadmap](../ROADMAP.md) · [Карта](project-map.md) · [Tools](../TOOLS.md) · [Sandbox](../SANDBOX.md).

## Что есть и чего пока нет

Исходный код main проверен на `b9787e4f40fe8b62f62dbafa632b60722e44f439`:

| Компонент | Факт | Не означает |
| --- | --- | --- |
| `create_or_update_binary_file` | base64 → `.decode('utf-8')` → текстовая запись в Git | Универсальные ZIP/XLSX/non-UTF-8 bytes, staging или обход большого payload через контекст модели |
| `github/releases.py` | `list_releases`, `create_release`, `get_latest_release`; создание возвращает текстовый URL | Полный release lookup/IDs и upload/list/download assets |
| `download_artifact` | Actions artifact resolver получает проверенный краткоживущий redirect URL | Release asset transport, получение bytes клиентом или проверка их хеша |
| Shell/local tools | Работают на стороне MCP-сервера под его policy | Доступ к `/data/...` клиента или автоматический перенос вложения |

**Целевой маршрут:** bytes клиента → MCP staging → asset приватного GitHub Release → существующий Actions workflow → output artifact → проверенный результат. Не коммитить большие бинарники в Git, не требовать ручную перезагрузку файлов, локальный `gh`, публичные исходники или платного посредника.

## Этап 1 — #88: доказать переход клиент → сервер

До выбора конкретного API проверить возможности реального клиента. Выбрать **один основной транспорт**:

- authenticated streaming HTTP upload с короткоживущим upload ticket; **либо**
- bounded MCP chunks, например `begin_file_upload` → `append_file_chunk` → `finish_file_upload`.

Имена — предложения, инструменты ещё не зарегистрированы. Не обещать, что Notion автоматически отправляет локальное вложение: MCP-сервер сам не получает доступ к клиентскому sandbox. Если доступного механизма нет, это явный blocker, а не повод считать server-side path решением. Не печатать весь base64 большого файла в сообщениях/контексте модели.

### Обязательные свойства staging

- При старте имя, ожидаемые размер и SHA-256; bytes без UTF-8-преобразований.
- При завершении непрозрачный `file_id`, фактический размер, проверенный SHA-256; ID привязан к авторизованному пользователю/сеансу. ID не заменяется произвольным filesystem path.
- Незавершённый или неверный по размеру/хешу upload недоступен downstream.
- Для chunk transport: offset, integrity, идемпотентный повтор одинаковых bytes, отказ на конфликт.
- Лимиты размера/квоты, TTL и cleanup; safe names, no traversal/symlink, isolation между пользователями.
- Не логировать tickets, секреты и содержимое; не добавлять произвольный URL-fetch/SSRF. Старые текстовые API сохраняются.

### Приёмка #88 — пока не выполнена

- [ ] Unit/integration: произвольные non-UTF-8 bytes, ZIP и XLSX сохраняют bytes/size/SHA-256.
- [ ] Неполный upload, неверный hash/size, quota, repeated/conflicting chunks, owner isolation и cleanup.
- [ ] Доказан реальный client→server переход, не только fixture на VPS; документирован доступный клиентский механизм и ограничения.
- [ ] Отдельно разрешённый synthetic прогон порядка **41 МБ** без реальных приватных данных в public fixtures.
- [ ] Runtime registration/schema, README/TOOLS/примеры и ошибки обновлены по реальной реализации.

## Этап 2 — #89: Release assets и Actions

Зависит от #88; согласовать release lookup/IDs с [#64](https://github.com/LeonidYasin/mcp-server/issues/64), не создавать дублирующие реализации.

1. Get release по tag/ID: машинно-читаемые `release_id`, tag, URL, draft/prerelease с сохранением обратной совместимости.
2. Bounded `list_release_assets`: пагинация, ID/name/size/download URL, upstream digest только когда предоставлен GitHub.
3. Streaming upload: owner/repo/release_id + завершённый scoped `file_id`, имя/media type/expected SHA-256 → asset_id/name/size/локально проверенный SHA-256. Без UTF-8 и без всего файла в памяти; локальный digest не выдавать за upstream digest.
4. Authenticated private asset download → безопасный staging → size/hash verification → file_id/метаданные. Если нужен возврат клиенту, доказать и документировать transport: server-local path недостаточен.
5. Документировать минимальные права для конкретных операций и пример существующего Actions workflow с разрешённым токеном. Не расширять permissions или менять workflow чужого проекта автоматически.

`list_release_assets`, `upload_release_asset`, `download_release_asset` здесь — proposed names, **не готовые tools**.

### Безопасность и неопределённый результат

- Конфликт имени — явная ошибка или отдельно подтверждённая замена; не удалять/не перезаписывать asset молча.
- Timeout/неопределённый POST: сначала сверить assets, не повторять запись вслепую и не создавать дубликаты. Связано с #59, но не объявляет #59 исправленным.
- Фиксированные/проверенные GitHub endpoints и кодирование имён; no SSRF, no PAT при redirect на storage/CDN. Сохранить guards существующего artifact download.
- API download endpoint ≠ signed capability URL ≠ уже полученные bytes. Не логировать токены/подписанные ссылки.
- Private inputs нельзя отправлять в public release; не менять privacy автоматически. Synthetic public fixture не доказывает private access.
- IDs/метаданные должны проходить фактическую MCP-нормализацию до клиента, а не оставаться только внутри handler.

### Приёмка #89 — пока не выполнена

- [ ] Unit/integration: upload/list/download, pagination, arbitrary binary bytes, name conflicts, permissions, redirects, unknown POST reconciliation.
- [ ] Отдельно разрешённый E2E synthetic ZIP: реальный клиент → #88 → private Release asset → Actions → output artifact.
- [ ] Actions подтверждает исходные size/SHA-256 **и читает содержимое ZIP**.
- [ ] Обратное получение результата проверено по bytes/size/SHA-256; metadata/URL-only проверки недостаточно.
- [ ] Private-release access проверен в отдельно разрешённом владельцем репозитории; никаких приватных входов в публичных fixtures.
- [ ] Runtime/schema, права, ошибки, README/TOOLS/примеры и карта синхронизированы с реализацией.

## Сквозные зависимости и границы

- **#77:** измерять schemas + arguments + results + turns; передавать bytes вне контекста модели, экономия не отменяет integrity/ownership metadata.
- **#53 / #59:** честные access errors и reconciliation при неизвестном результате записи, без неявных fallback.
- **#69 / PR #87:** Actions artifact attempt ownership отдельно от Release asset identity; неизвестное владение попыткой остаётся unknown.
- **#68 / docs/site:** после реализации обновить реальные examples, проверить ссылки/сборку и фактический Pages deployment. Текущий docs PR ничего не публикует.

Не входит: новый compute service, запуск боевой научной обработки, изменение методики/данных, реальные секреты, платные сервисы, production deploy или публичная публикация приватных исходников. Live mutations, объекты тестирования и крупный прогон требуют отдельного разрешения.
