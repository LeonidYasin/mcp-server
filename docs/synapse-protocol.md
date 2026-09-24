# Synapse Protocol v0

Общая JSON-схема для экосистемы проектов автора:
**NoKing**, **Civis**, **synapse** (старый), **synapse2**, **agora-mcp**, **mcp-server**.

Цель: дать всем репозиториям один формат для item, profile, contact,
exchange и match, чтобы данные были совместимы между инстансами.

Статус: **draft v0**. Ломающие изменения допускаются до v1.0.

---

## 1. Принципы

1. **Item важнее user.** Базовая единица матчинга — item (`offer` или `want`),
   а не пользователь. У одного пользователя много items.
2. **Асимметричный матчинг.** `offer` матчится против чужих `want`, и наоборот.
   Симметричный поиск (offer ↔ offer) — не то, что нужно.
3. **Согласие по умолчанию.** Контакт раскрывается только после явного
   `contact_request` с обеих сторон. Публикация профиля ≠ раскрытие контакта.
4. **Свежесть.** У item есть `active` и `updated_at`. Устаревшие items
   деградируют из матчинга, а не копятся вечно.
5. **Переносимость.** Профиль и items — переносимый JSON. Хочешь — держи
   в gist, хочешь — на своём MCP-сервере.
6. **Инструкционные эмбеддинги.** Роль item (`offer` / `want`) кодируется
   отдельным префиксом при вычислении эмбеддинга. Это улучшает crossed matching.
7. **Явное версионирование.** Каждый объект содержит `schema` версию.

---

## 2. Объекты

### 2.1. `profile`

Переносимая карточка пользователя. Не содержит секретов; контакт —
опционален и раскрывается только по согласию.

```json
{
  "schema": "synapse/v0",
  "profile_id": "string [A-Za-z0-9_.-]{1,80}",
  "display_name": "string",
  "values": ["string"],
  "intents": ["string"],
  "contact": {
    "type": "email | telegram | github | none",
    "value": "string"
  },
  "identities": {
    "github": "string?",
    "telegram": "string?"
  },
  "items": ["item_id"],
  "published_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

- `profile_id` — уникальный, генерируется автором.
- `contact` — **не показывается** другим; используется только после
  принятого `contact_request`.
- `values` / `intents` — свободные строки, не рубрики.

### 2.2. `item`

Единица матчинга. Бывает двух типов.

```json
{
  "schema": "synapse/v0",
  "item_id": "string",
  "type": "offer | want",
  "owner_id": "profile_id",
  "text": "string",
  "category": "string?",
  "tags": ["string"],
  "geo": "string?",
  "active": true,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "embedding_ref": "string?"
}
```

- `text` — свободное описание, в словах автора.
- `embedding_ref` — ссылка на вектор в локальном/внешнем хранилище.
  Сам вектор в JSON **не** хранится (это большое бинарное значение).
- `active=false` — item выведен из матчинга (исполнен, неактуален).

### 2.3. `match`

Результат матчинга. Асимметричен по построению.

```json
{
  "schema": "synapse/v0",
  "match_id": "string",
  "item_a": "item_id (offer)",
  "item_b": "item_id (want)",
  "owner_a": "profile_id",
  "owner_b": "profile_id",
  "score": 0.0,
  "source": "embedding | keyword | hybrid",
  "created_at": "ISO-8601",
  "outcome": "unknown | accepted | rejected | exchanged"
}
```

- `score` — число в [0, 1]; сравнивать можно только внутри одного провайдера.
- `outcome` — задел под behavioral ranking (Stage 2 у Agora).

### 2.4. `contact_request`

Запрос на раскрытие контакта. Контакт раскрывается только при `status=accepted`.

```json
{
  "schema": "synapse/v0",
  "request_id": "string",
  "from_profile_id": "profile_id",
  "to_profile_id": "profile_id",
  "match_id": "string?",
  "message": "string?",
  "status": "pending | accepted | declined",
  "created_at": "ISO-8601",
  "resolved_at": "ISO-8601?"
}
```

### 2.5. `exchange` (из NoKing)

Двусторонний обмен ценностями. Не обязательно деньги: товары, услуги,
время, права, голоса, данные.

```json
{
  "schema": "synapse/v0",
  "exchange_id": "string",
  "side_a": { "profile_id": "...", "gives": "item_id", "receives": "item_id" },
  "side_b": { "profile_id": "...", "gives": "item_id", "receives": "item_id" },
  "terms": "string?",
  "status": "draft | agreed | in_progress | completed | disputed | cancelled",
  "created_at": "ISO-8601",
  "completed_at": "ISO-8601?",
  "reputation_refs": ["string"]
}
```

- `side_a.gives` должен совпадать с `side_b.receives` (и наоборот).
- `reputation_refs` — ссылки на внешние записи о репутации (NoKing / DAO).

### 2.6. `note` (личное, не публикуется)

```json
{
  "schema": "synapse/v0",
  "note_id": "string",
  "text": "string",
  "tags": ["string"],
  "created_at": "ISO-8601"
}
```

---

## 3. Матчинг

### 3.1. Провайдеры эмбеддингов

| Провайдер | Модель | Размерность | Префиксы ролей |
|-----------|--------|-------------|----------------|
| `openai` | `text-embedding-3-small` | 1536 | нет (используем короткий role-префикс в тексте) |
| `local` | `all-MiniLM-L6-v2` / `bge-small-en` | 384 | да (`offer:`, `want:`) |
| `ollama` | `nomic-embed-text` | 768 | да (`offer:`, `want:`) |

Если провайдер не задан — используется keyword-скоринг (fallback).

### 3.2. Гибридный поиск

Кандидаты берутся по косинусной близости, затем фильтруются по:

- `category` (точное совпадение),
- `tags` (пересечение),
- `geo` (точное совпадение или пусто),
- `active = true`,
- freshness (`updated_at` не старше `SYNAPSE_FRESHNESS_DAYS`, по умолчанию 90).

Только после фильтров считается финальный скор.

### 3.3. Свежесть

- Item с `active=false` **не участвует** в матчинге.
- Item с `updated_at` старше порога получает понижающий коэффициент.
- `exchange.status` в `completed | cancelled` делает связанные items неактивными.

---

## 4. Согласие и приватность

1. Публикация `profile` и `item` **не** раскрывает контакт.
2. Контакт передаётся между двумя сторонами **только** при
   `contact_request.status = accepted`.
3. Сырые диалоги и embeddings **не** публикуются: только
   `text` и `embedding_ref` (локально).
4. Federation (обмен items между инстансами) — только по явному
   согласию владельца. Формат обмена — `item` + `profile` без `contact`.

---

## 5. Совместимость с agora-mcp

Agora-mcp использует ту же item-модель (`offer` / `want`),
но хранит эмбеддинги server-side в Postgres + pgvector. Чтобы
совместить:

- объекты `item` / `profile` импортируются в Agora через
  `submit_offer` / `submit_want` (сервер сам посчитает эмбеддинг);
- `search_matches` возвращает `match` в том же формате;
- `contact_request` / `exchange` добавляются поверх как отдельный слой
  (у Agora сейчас не описаны — это задел на Stage 2).

---

## 6. Версионирование схемы

- Каждый объект содержит `"schema": "synapse/v0"`.
- Ломающие изменения → `v1`.
- Совместимые расширения → добавление необязательных полей, без бампа `v0`.

---

## 7. Что дальше

- В батче 7b реализуются `submit_offer`, `submit_want`, `list_my_items`,
  `deactivate_item`, `model_me`, `find_my_match`, `draft_profile_from_dialog`.
- В батче 9 — `docs/synapse-protocol.md` синхронизируется с реальной
  реализацией (сейчас это v0, черновик).
- В Agora — `contact_request` / `exchange` добавляются как Stage 2.
