# Политика источников (CW-004a)

Каталог: [sources/catalog.json](../../sources/catalog.json), проверка — `tests/test_sources.py`.

## Охват

Вся криптосфера. Ни одна сеть, регулирование или тип событий не исключены. Каталог — стартовый приоритетный набор, а не закрытый список: новые сети и источники добавляются без изменения схемы. Обязательны RU и EN источники.

Категории: `official_project` (команды сетей/протоколов), `regulator`, `security` (инциденты), `funding`, `exchange`, `media_context`, `data_api`, `context_research`.

## Сети

`networks` — идентификаторы CAIP-2 как в `schemas/chainwire.v1.schema.json` (`NetworkId`). Указываются только известные id (bip122 для Bitcoin, eip155:N, solana:…). Если id для сети в проекте не зафиксирован (Aptos, Sui, Cardano), поле пустое, а сеть отражена в `topics`. Пустой `networks` у медиа означает «все сети», а не «никакие».

## Доступность, права и лимиты

- `availability.status = responded` только если endpoint реально ответил HTTP 200 при проверке; записаны код, content-type, время (UTC) и метод. Иначе — `unverified` с фактическим кодом.
- Ответ 200 не означает права на перепубликацию. `terms.status` у всех источников — `unverified`, `reuse_rights = null`, пока условия не прочитаны и не зафиксированы отдельно.
- `limits.observed` — только наблюдённое (403, 429, 402 и т.п.). `limits.documented = null`, пока документация не сверена.
- Медиа (`media_context`) — контекст и сигнал, а не подтверждение факта; факт подтверждается официальным/первичным источником.
- Публикация из источников со статусом `unverified` по правам — только пересказ со ссылкой, без копирования текста.

## Проверка 2026-10-30 (18:41–18:43 МСК)

Итого: 29 источников; ответили 200: 24; не подтверждены: 5; RU: 5; EN: 24.

Не подтверждены: Solana news (429), Arbitrum blog (403), Coinbase blog (403), Binance announcements (202 с пустым телом), DefiLlama raises (402, платный тариф). Для funding подтверждённого бесплатного структурированного API нет — открытый продуктовый вопрос (бюджет источников).

## Пробелы покрытия

Каталог — стартовый набор, а не полный список. Для следующих сетей/регуляторов официальный endpoint при проверке не подтвердился, поэтому они не включены; интегратор открывает отдельную карточку CW-004a2. Время проверки — 2026-10-30, 18:41 МСК (15:41 UTC), curl с Mac пользователя.

| Сеть / источник | Проверенный endpoint | Результат |
|---|---|---|
| Polkadot | https://polkadot.com/blog/rss.xml | 404 |
| Optimism | https://optimism.io/blog/rss.xml | 404 |
| Cosmos | https://blog.cosmos.network/feed | 200, но HTML, не фид |
| TON | https://blog.ton.org/rss.xml | 200, но HTML (страница Telegram), не фид |
| Avalanche | https://avax.network/blog | 403 |
| FATF | https://www.fatf-gafi.org/en/publications.html | 403 (Cloudflare challenge) |
| Cointelegraph RU | https://ru.cointelegraph.com/rss | 410 Gone |

Отсутствие в каталоге не означает исключения сети из охвата.
