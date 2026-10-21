# Воспроизводимая проверка документации

Ревизия 9 · 2026-10-15. [README](../README.md) · [TOOLS](../TOOLS.md) · [Карта](project-map.md) · [HTTP-контракт](http-transport.md).

[Deployment evidence](deployment-status.md) фиксирует отдельные VPS/external/Pages проверки. Локальный pytest не доказывает production deployment, готовность #88/#89 или Mermaid rendering на опубликованном сайте.

## Локальный gate

Из корня checkout в отдельном venv, без production credentials:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]" build
python scripts/check_docs.py
python -m pytest -q
python -c "import mcp_server, mcp_server.server; print('smoke import OK')"
python -m build
git diff --check
```

Windows: создать venv через `py -m venv .venv`, активировать `.venv\Scripts\Activate.ps1`; Linux-only process tests требуют отдельного Linux gate. Не устанавливать пакет в системный Python под PEP 668.

### Что проверяет scripts/check_docs.py

- Два **независимых процесса** discovery с явно выключенными/включёнными `ENABLE_LOCAL_TOOLS`, `ENABLE_LOCAL_SHELL`, `ENABLE_SYNAPSE`, `ENABLE_FILE_UPLOADS`. Это важно: imports и registry discovery кэшируются внутри Python process.
- Полное совпадение имён, handler categories и текущего Bearer gate с [tool-inventory.json](tool-inventory.json). Required parameters должны существовать в schema properties.
- Каждое зарегистрированное имя упомянуто в TOOLS; proposed names не попадают в inventory.
- Обычные inline local Markdown links/images во всех корневых `*.md` и `docs/**/*.md`, существование files/heading fragments; fenced code игнорируется. Это не полный Markdown parser: reference-style/HTML links и внешний HTTP не проверяются.
- UTF-8 replacement chars и незакрытые code fences.

Для source distribution `MANIFEST.in` явно включает Markdown docs, inventory и checker, чтобы документационные тесты не зависели от файлов только в Git checkout. Wheel не обязан содержать repository documentation.

Check не вызывает handlers, не делает GitHub/model requests и не выполняет команды на VPS. Inventory включает registration disabled-tools (`auto_fix_build`), не объявляет каждый handler работоспособным/разрешённым при любых правах. Существующий CI запускает pytest; `tests/test_documentation.py` включает этот guard без изменения workflow. Негативные fixtures проверяют, что missing link/anchor и незакрытый fence действительно обнаруживаются.

### Как обновить inventory при изменении runtime

```bash
python scripts/check_docs.py --write-inventory
git diff -- docs/tool-inventory.json TOOLS.md
python scripts/check_docs.py
```

Regeneration — только явное действие maintainer после проверки кода/schema/docs. Нельзя автоматически переписывать snapshot в CI, иначе drift станет невидимым. Удалённые/добавленные names, flags и token gate требуют review. Snapshot отражает текущий checkout, не production attestation и не обещание будущих API.

## Проверки #88 кандидата

`tests/test_uploads.py`: synthetic binary/ZIP/XLSX round-trip, in-process Flask+mocked GitHub auth, byte/hash integrity, owner/allowlist, bounds/quotas/TTL, exact retry/offset conflicts, parallel SQLite connections, transactional rollback, private filesystem guards, redaction и клиентский helper. Fresh-process discovery: default 113; uploads-only 119; all-enabled 149. Эти tests не требуют root/PAT/сети. Изолированный native TEST gate и реальный клиент→deployed API — отдельные проверки; ~41 МБ не запускается автоматически.

## Дополнительные gates

- **HTTP examples:** `tests/test_documentation.py` проверяет JSON examples из HTTP-контракта через Flask test client и фактические status/headers. Это не внешний client interoperability test.
- **Mermaid:** карта имеет текстовый fallback. Source отрендерен локально mermaid-cli 12.0.0 + Chromium и визуально проверен; это не обещание идентичного layout всех GitHub/site renderers. Существующий Pages workflow опубликовал ревизию 8 после #90; Mermaid на самом сайте визуально ещё не принят.
- **Shell snippets:** Linux bash syntax проверяется отдельно; это не доказательство apt/systemd/Caddy/bwrap/WSL deployment. Никакие root commands не исполняются автоматической проверкой docs.
- **CI:** для точного PR HEAD проверить все Python 3.10–3.13 jobs, не переиспользовать success другого commit. В evidence фиксировать SHA и URL run.
- **TEST vs production:** runtime discovery, exact checkout, restart procedure и dedicated live acceptance — отдельные доказательства; Git metadata cwd не гарантирует загруженный worker code.
- **Pages:** файлы в PR ≠ configured site ≠ successful deployment ≠ проверенное HTTP-содержимое. Не публиковать приватные source data, secrets или signed download URLs. Конфигурация/публикация требуют отдельного gate.

Локальные unit/mocked/HTTP checks не заменяют live GitHub mutations, приватный Release access, реальную передачу файла клиента, OS isolation tests или provider quality. Невыполненные проверки остаются явно pending в ROADMAP/PR; merge и rollout отдельно согласуются.
