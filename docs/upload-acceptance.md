# Приёмка бинарного staging #88

Кандидат PR #91; runtime `f39ee020324240833fb008f5c0fc19ad665bc9ca`; feature default OFF. Эта матрица разделяет доказанные проверки и оставшиеся gates. Она не является разрешением merge, production rollout или закрытия issue.

| Gate | Статус и точная граница |
| --- | --- |
| Малый authenticated upload | PASS: 50 bytes / 2 chunks; retry, incomplete refusal, stable file_id и cancel |
| ZIP из sandbox клиента | PASS: 110 124 bytes / 3 chunks через arguments_file_path; финальные size/SHA-256 совпали |
| XLSX из sandbox клиента | PASS: 5 300 bytes; client-side reopen/typed values/ZIP integrity/strict audit; deployed finish size/SHA-256 совпали |
| Active-record count quota | PASS: 8 пустых uploads приняты, девятый quota_exceeded; после cancel тот же запрос принят и затем удалён |
| Cross-owner live isolation | PENDING: нужна отдельная одобренная identity; существующий allowlist не расширялся |
| Byte/global quotas, expiry | PENDING live gates; count quota не доказывает byte quota или TTL |
| Host payload retention | PENDING: приватные аргументы/без base64 в model context не доказывают отсутствие host-internal истории/логов |
| Большой synthetic ~41 MiB / ресурсы #77 | PENDING, только отдельное разрешение; не выполнялся |
| Release/Actions #89 | Не реализован и не проверен end-to-end |

## XLSX и count quota: новые evidence

[Подробная последовательность и ограничения](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204702804). XLSX SHA-256: `df51352f21fb6c7c47a01dcc8741b0c35575a52dca2345aedf7507c987d5f3e1`. Workbook синтетический, без формул, external links и private inputs; client-side structural audit без issues/warnings. Передача проверяет bytes, а не server-side spreadsheet parsing/reopen или обратное скачивание.

Все созданные серверные записи отменены; XLSX status после cancel — not_found_or_expired. Девять quota-записей в сумме созданы/удалены: первые8, затем повтор девятого запроса после освобождения ёмкости. Группировка вызовов не доказывает их реальную одновременность; concurrency stress test не заявлен.

## Временные маршруты

Первые два маршрута удалены оператором: [первый](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204369596), [второй](https://github.com/LeonidYasin/mcp-server/pull/91#issuecomment-6204595072). Для XLSX/count-quota использован третий временный защищённый маршрут; его удаление ещё ожидается. Удаление маршрута само по себе не останавливает loopback service и не удаляет сохранённое клиентское подключение.

## Что считать завершением

[Контракт API](file-uploads.md) · [Roadmap](../ROADMAP.md) · [План #88 → #89](binary-transfer-plan.md). Unit/in-process coverage остаётся отдельной evidence; не подменять им ещё не выполненные live gates. PR остаётся Draft; production и TEST #87 не заменяются автоматически.
