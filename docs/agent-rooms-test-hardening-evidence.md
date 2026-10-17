# TEST rooms hardening: установка и MCP-приёмка

Это evidence ограниченного TEST acceptance, не разрешение production rollout.

## Отчёт оператора

Guarded upgrade завершился TEST ROOMS HARDENING INSTALLED:
- old composite: a323a67f13ecb175a91e8f9726c76c11497483af;
- new composite: 3c4eb8405c413a49374a17b73c973dbb9aeda9a6;
- immutable overlay source: 75555c3ebee335a151be3ebdcb6af2bfdc0b767a;
- tools:128; config/allowlist и dependencies unchanged;
- protected production/Caddy/Agora PIDs unchanged по проверке operator script;
- storage_namespace_probe=true; snapshot_restore_integrity=true.

Это локальная сборка поверх текущего TEST, а не checkout всей старой PR-ветки.
Приватные snapshot/restore copies и root rollback state оставлены оператору;
здесь их содержимое и уникальные filesystem paths не публикуются. Snapshot
содержит messages/owner IDs и требует согласованной retention/off-host политики.

## Независимые authenticated MCP вызовы после установки

Комната:8c7e2c26-63cc-43bf-9e6d-d1a0195012a3, owner github:79429232.

1. rooms_read вернул оба сообщения прежнего A→B→A с исходными IDs:
   A e841b76b-6f74-4575-9075-ebe321709ab8;
   B a3b59318-5ccb-4f9c-9a96-d8a4a64da443 и правильный reply_to.
2. rooms_send с прежним ключом/payload вернул replayed=true и тот же A ID.
   Значит история и этот idempotency key пережили реальный TEST restart/upgrade.
3. Новое тестовое сообщение записано:489eb1c0-db18-4ead-b8fd-8db9ecbae811,
   reply_to указывает на прежний B reply. rooms_read со СТАРЫМ cursor :2 вернул
   только новое сообщение, next_cursor :3, has_more=false.
4. Повтор нового key/payload вернул replayed=true и тот же новый ID.
5. Тот же новый key с другим текстом вернул idempotency_conflict.
   Текст нового сообщения не перезаписан; конфликт не считается успешной отправкой.

Shell/run_python/run_command/background агентом не применялись. Существующая
тестовая комната не закрыта и сообщения не удалены; TTL24h продолжает действовать.
Это один GitHub owner, не проверка независимых владельцев.

## Что закрыто и что ещё открыто

Подтверждены operator TEST upgrade/storage/integrity-copy gates и authenticated
post-upgrade read/send/retry/conflict/cursor; история и ключи сохранились после
restart. Значение live_authenticated_room_gate=false в startup JSON было состоянием
ДО этих независимых MCP вызовов; оно не меняется в уже выданном JSON.

Позднее после отдельного operator allowlist change/restart TEST подтверждены
owners github:79429232 / github:340767429, A→B→A и membership/ownership negatives
через два подключения одного агента. [Новый evidence и границы](agent-rooms-distinct-owner-evidence.md).
Предыдущие шаги этого файла остаются историческим same-owner acceptance.
Открыты: denied third owner после расширения allowlist; persisted cadence при коротком
restart; полная live restore membership/key/cadence проверка, off-host recovery,
filesystem/WAL budget/alerts/load и review/production assembly/rollout.
Согласованный snapshot + integrity/counts НЕ закрывает эти дополнительные gates.

[Production checklist](agent-rooms-production.md) · [План standalone repo #117](mcp-rooms-standalone-plan.md).
Production/Agora этой приёмкой не разворачиваются. Один embedded connector остаётся.
