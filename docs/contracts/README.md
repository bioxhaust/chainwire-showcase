# Контракт Chainwire v1 (CW-002b)

Схема: `schemas/chainwire.v1.schema.json` (JSON Schema 2020-12). Пример RU/EN: `docs/contracts/examples/bundle.ru-en.json`. Проверка: импортируемый модуль `schemas/chainwire_contract.py` (только stdlib): `validate()` — подмножество JSON Schema, `invariants()` — межсущностные правила, `delivery_key()`. Тесты: `tests/test_contracts.py`.

## Сущности (раздельные)

| Сущность | Назначение |
|---|---|
| `Source` | Снимок источника: URL, издатель, primary/secondary, sha256 содержимого, время получения. |
| `Event` | Обнаруженное событие; ссылки на источники и проекты, сети события. |
| `Evidence` | Утверждение из конкретного источника с локатором; статус unverified/verified/rejected + аудит проверки. |
| `Project` | Идентичность проекта: один `project_id` на несколько сетей и адресов. |
| `Assessment` | Раздельные оценки: quality, risk, completeness, urgency; версия методики/модели/промпта; ссылки на evidence. |
| `FactPack` | Один пакет фактов события — единый источник чисел/имён/дат для всех языков. |
| `ArticleRevision` | Ревизия статьи; `supersedes_id` и `change_reason` для исправлений; draft/approved с аудитом. |
| `LocaleVersion` | Текст ревизии на одном языке из того же FactPack; ревью отдельно на язык. |
| `Delivery` | Одна доставка = ревизия × язык × назначение. |

## Правила

- **Вся криптосфера.** Сеть — идентификатор CAIP-2 `namespace:reference` (namespace `[-a-z0-9]{3,8}`, reference `[-_a-zA-Z0-9]{1,32}`, как в CAIP-2; не перечисление) (`eip155:1`, `solana:mainnet`, `bip122:…`, `cosmos:cosmoshub-4`, `ton:mainnet`, …). Экосистемы — открытые теги. Новая сеть не требует изменения схемы. Адрес без сети не идентифицирует актив.
- **Неизвестное = `null`**, не 0/false/пустая строка. Поля «может быть неизвестно» обязательны и nullable: отсутствие ключа — ошибка, а не «неизвестно». `Fact.value = null` — неизвестное значение; `Assessment.risk/quality/urgency = null` — не оценено.
- **Языки.** `locale` — тег BCP 47; RU и EN обязательны для approved-ревизии (обе версии approved и используют полный общий FactPack). Другие языки можно добавлять.
- **Ключ доставки.** `idempotency_key = sha256(JSON [revision_id, locale, destination], компактно, UTF-8)`; уникален в наборе. Назначение — открытый идентификатор `kind:target` (`telegram:channel_ru`, `telegraph:article`, `web:site`).
- **Состояния доставки:** `pending` (попыток нет) → `leased` (владелец + срок аренды) → `succeeded` (только с внешним подтверждением) | `retryable` (неотправка подтверждена, есть `last_error` и `available_at`) | `uncertain` (таймаут/истёкшая аренда после возможной отправки; повтор только после сверки `reconciliation`). Состояния `sent` нет; режим draft не создаёт успешных доставок.
- Доставка возможна только для approved-ревизии, у которой версия на этом языке тоже approved. `succeeded` несовместимо со сверкой `not_delivered`; `available_at`/`updated_at` не раньше `created_at`.
- `Fact.value.kind` определяет тип: text→строка, integer→целое, decimal→строка-число, boolean→bool, timestamp→date-time. id фактов уникальны в пакете.

## Что вне схемы и передано другим карточкам

JSON Schema не выражает ссылки между сущностями; их проверяет `invariants()` (все ссылки, включая `fact_ids` черновых версий, `supersedes_id`, `project_ids`/`assessment_ids` пакета; evidence из того же события; полный FactPack у RU/EN; ключ доставки; согласованность полей состояния).

- Тайминг повторов (backoff, `available_at` относительно `updated_at`) и поток сверки `uncertain` — **CW-002d/CW-002e**.
- Соответствие текста RU/EN значениям фактов (числа, имена, даты в `body`) — **CW-004c**. Переходы состояний (claim/result/expire/reconcile) — задача CW-002d/CW-002e; черновая реализация сохранена вне репозитория в `salvage/contracts.py.bak` как справочный материал.
