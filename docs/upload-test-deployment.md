# Отдельный loopback TEST для кандидата #88

Ревизия документации 9 · 2026-10-15. [API](file-uploads.md) · [Состояние окружений](deployment-status.md) · [Roadmap](../ROADMAP.md).

`scripts/deploy_upload_test.py` — root-оркестратор нового временного контура. Запускать только после review/CI по точному полному SHA и проверки checksum самого скрипта. Это ручное действие оператора, не часть pytest и не production deployment.

- Новый Unix user/unit: `mcp-upload-test` / `mcp-upload-test.service`.
- Source/venv: `/home/mcp-upload-test/repo`, `/home/mcp-upload-test/venv`, после установки root-owned/read-only для service user. Private staging — `/home/mcp-upload-test/staging`, mode 0700, отдельный owner.
- Bind только `127.0.0.1:3004`. Порт 3003 уже занят на VPS, его не использовать и не освобождать вслепую.
- Shell/local/Synapse выключены, uploads включены. GitHub allowlist задаётся явно numeric IDs; не брать чужой owner из аргументов клиента и не использовать `*`.
- Fresh GitHub /user verification по-прежнему обязательна. GitHub MCP identity и Bearer другого подключения могут принадлежать разным пользователям; при отказе allowlist не расширяется автоматически.
- Все Git/pip/project Python операции выполняются от нового непривилегированного пользователя; root только создаёт account, права и новый systemd unit. Зависимости ставятся в НОВЫЙ venv из exact публичных wheels версий проверенного native TEST. Существующие venv/dependencies не меняются, никаких apt upgrades/reboot.
- Лимиты 256 MiB RAM, 25% CPU, 32 tasks; запись только в staging/private runtime/tmp. Unit НЕ включается в autostart и автоматически останавливается через 7200 секунд.
- Скрипт отказывает при существующем account/home/unit, занятом порте или изменившемся HEAD PR #91. Не переустанавливает и не стирает найденные файлы. Нужны минимум 2 GiB свободного места.
- Проверяет health/build/119 tools нового процесса и fingerprints production, текущего TEST #87, Caddy и соседнего Agora. Никаких stop/restart/reload этих сервисов; systemd daemon-reload перечитывает unit files, не перезапускает работающие services.
- При ошибке останавливается только новый unit (если создан); account/files/private log остаются для проверки. Не выполнять blind rerun или rm -rf. Root log: `/root/mcp-upload-setup-<id>/setup.log`, не публиковать целиком.

Пример формы вызова (SHA/IDs должны быть реально проверены, placeholders не копировать):

```bash
python3 deploy_upload_test.py --target "$REVIEWED_FULL_SHA" --allow-user "$VERIFIED_GITHUB_USER_ID"
```

Скрипт НЕ читает PAT/API keys/Caddy config и НЕ открывает публичный endpoint. `LOOPBACK TEST READY` означает только localhost/schema/изоляцию, не authenticated upload acceptance. Далее отдельно согласовать защищённый доступ и настоящий client→новые инструменты с size/hash verification. Большой ~41 MiB, private inputs, Release/Actions и закрытие #88 остаются pending. Текущий незавершённый TEST #87 не заменяется.
