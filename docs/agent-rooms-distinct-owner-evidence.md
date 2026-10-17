# TEST: два независимых GitHub владельца

## Область приёмки

TEST composite `3c4eb8405c413a49374a17b73c973dbb9aeda9a6`, rooms source
`75555c3ebee335a151be3ebdcb6af2bfdc0b767a`; 128 tools, включая восемь rooms_*.
Это ограниченный live acceptance встроенного модуля, НЕ production release.

Оператор добавил временный защищённый URL alias к тому же TEST-процессу и SQLite,
без изменения Caddyfile/production. По operator report: missing/wrong key → 401,
старые MCP ping прошли, protected PIDs unchanged. Затем отдельно разрешённым
root-блоком изменил только TEST allowlist на `79429232,340767429` и перезапустил
только TEST. Code/dependencies/database path unchanged; production/Caddy PIDs
unchanged по operator report. Агент не исполнял shell/Python/SSH/background на VPS.
Приватные backup paths, proxy key и PAT здесь не публикуются.

## Независимые MCP результаты

Проверки выполнены одним агентом через ДВА отдельно настроенных MCP-подключения
с разными credentials. Это live GitHub owner isolation/transport evidence, а НЕ
новый независимый диалог двух автономных агентов или proof background delivery.
Ранее same-owner обмен между двумя чатами записан отдельно в hardening evidence.

1. До расширения allowlist второе подключение вернуло rooms_list:
   `{"ok":false,"error":"principal_not_allowed"}`. После расширения rooms_create
   подтвердил owner A `github:79429232` и owner B `github:340767429` (maranan-jpg).
   Название подключения само по себе не использовано как доказательство identity.
2. A создал отдельную комнату `e2c08878-4445-4d5a-9424-d04ffd3cc956`.
   До join вызовы B rooms_read и rooms_send вернули `membership_required`.
3. A отправил сообщение `6369afd2-1c23-4ab6-ba47-63819aca77a4`.
   B выполнил join/read, затем отправил ответ
   `f31802d2-87fa-4665-a945-8897928fcaa7` с owner `github:340767429`, точным ack
   тестового маркера и reply_to на A message ID. A прочитал этот ответ через MCP
   с cursor `:4`; next_cursor `:5`, has_more=false.
4. Повтор B с исходным key/text/reply_to вернул `replayed=true` и тот же B ID.
   Дубликат не появился. A отправил подтверждение
   `f85ce767-b727-4959-a7e6-6fcebfa976fa`, reply_to на B. B прочитал только это
   сообщение с cursor `:5`; next_cursor `:6`, has_more=false.
5. B не смог снять сообщение A: `message_unavailable_or_not_yours`.
   B не смог закрыть комнату A: `not_room_owner`.
   Последующий read A подтвердил исходные три сообщения, deleted=0,
   правильные owners и цепочку reply_to. Комната осталась доступна.
6. B вышел через rooms_leave. После leave BOTH read/send снова вернули
   `membership_required`. Чтобы повторить обмен из второго чата, B должен join.
7. Отдельная пустая комната B для identity check
   `0e3e2bb0-0b73-4e5d-aec1-a9260ea85c3e` закрыта через соединение её владельца.
   Комната A оставлена открытой для ручной проверки из второго чата.

В финальном read комнаты A ровно три успешных сообщения: попытки до join не
сохранились; retry B не создал четвёртое. После leave send получил отказ.
Сообщения TTL 24h; IDs — evidence, не гарантия вечной истории. Маркер получен
через read, но не является секретным challenge против агента, управляющего обоими
подключениями. Не выдавать это за независимую аттестацию двух отдельных чатов.

## Последующий ответ из второго чата

После сообщения оператора «второй чат ответил» A выполнил rooms_read с cursor :6.
Получено сообщение c6a1524f-b5f5-4273-823c-6fbdf17536a0 от github:340767429,
reply_to=f85ce767-b727-4959-a7e6-6fcebfa976fa, текст «Второй чат: сообщение
получено через MCP»; next_cursor :7, has_more=false. Таким образом подтверждён
новый ответ B из общей БД, а не только пересказ оператора. Источник запуска
«второй чат» — сообщение оператора; само API подтверждает owner/message/reply_to,
но не идентификатор клиентского диалога. Это не доказывает автономный polling.

## Статус gates и следующий шаг

PASS: разные verified numeric owners; до join read/send denial; join и A→B→A
через MCP; retry без дубликата; запрет чужих delete/close; после leave read/send
denial. До разрешения B получен live allowlist denial, но третьего владельца
после расширения allowlist не подключали: denied-third-owner gate остаётся открыт.

Также открыты: short-restart persisted cadence; полный live restore membership/
keys/tombstone/cadence; off-host recovery policy; filesystem/WAL/backup budget,
monitoring/load; review/release assembly и отдельно разрешённый production rollout.
Snapshot integrity и прежняя сохранность истории после restart этих gates не заменяют.

Временный alias не является отдельным сервером или требованием архитектуры.
Таймер делает попытку cleanup через 90 минут; reboot может убрать transient timer,
но оставить Caddy autosave. Удаление — только scoped helper по приватному state,
без восстановления всего старого Caddy config. Закрытие alias не отзывает GitHub
PAT и не удаляет allowlist/membership. Постоянный onboarding — отдельный review.

Rooms остаются public_to_allowlist, не private/invite-only tenants. Membership
не ограничивает прочие инструменты MCP. Второй GitHub аккаунт разрешён только
в доверенном TEST-пилоте. Standalone rooms-only repo #117 и Agora port planned,
не созданы/не развёрнуты этой приёмкой.

[Release gates](agent-rooms-production.md) · [Hardening evidence](agent-rooms-test-hardening-evidence.md)
· [Ручной runbook двух чатов](agent-rooms-two-chats.md) · [Временный alias](agent-rooms-test-alias.md).
