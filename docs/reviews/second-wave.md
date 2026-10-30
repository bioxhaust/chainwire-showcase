# QA второй волны

## CW-001b — ACCEPT

- Проверяемый SHA: `42e6f02` (база `2809423`), review checkout `worktrees/cw-review`, detached HEAD. QA /root/qa функциональные файлы не менял.
- Зона: 3 файла, все в зоне карточки, оригиналы корпуса не изменены (SHA 16.jpg `90af2b42…`, 94.jpg `3d9d4c44…` совпадают с manifest и байтами).
- QA сам просмотрел 16.jpg и 94.jpg: OCR-расхождения «0.15»/«0.1$», «4.5-55»/«4.5-5$», «256»/«25%», «LO»/«L0» подтверждены; 660к/66к/объём >$20 верны, искажение в `screenshots_notes.md:21` зафиксировано.
- Пересчёт: AMM k=4e11 → 1 000 000 токенов, $0.40, ×4; supply 100/40 → +150%. Дата LayerZero — unverified, null.
- Прогоны: unittest 47/47 OK; check_repository PASS; manifest --check OK; git diff --check пусто.
- P3 (не блокируют): P3-1 `visual_check.image_text` подтверждается только ручным QA — пометить явно; P3-2 на 94.jpg не учтены «ЛО»/«Lo» и зачёркнутое «геее»; P3-3 в COR-001 явно назвать ошибку источника «500.000 токенов».
- Интеграция: merge `9fa858f`, повторно 47/47, оба checker OK.

## CW-002b — RETURN → ACCEPT

- Раунд 1 на `cdb2a4e`: RETURN. P2: kind факта не связан со значением; дубли fact id; висячие ссылки; доставка на неодобренную локаль; валидатор не импортируем. Мутации: `/tmp/cwqa/mut.py`.
- Раунд 2 на `307fe6f`: ACCEPT. Семантический JSON-diff схемы: изменились только NetworkId (CAIP-2 размеры) и FactValue (anyOf по kind). 40 новых мутаций (`/tmp/cwqa/mut2.py`) — все ожидаемо; 16/17 исходных пойманы, оставшаяся (текст vs факты) передана CW-004c. Модуль `schemas/chainwire_contract.py` импортируется без tests.
- Прогоны: 55/55 OK, check_repository PASS, manifest --check OK, diff --check чисто.
- P3 открыто: `solana:mainnet`/`ton:mainnet` в README и примере не канонические CAIP-2 → CW-002b2.
- Решения интегратора: tests/test_contracts.py в зоне; jsonschema отложен; CAIP-2 и kind:target согласованы; FactPack — отдельная сущность.
- Интеграция: merge `03bc7a4`, 55/55, оба checker OK.

## CW-004a — RETURN → ACCEPT

- Раунд 1 `e85b8ad`: RETURN. P2: неверные итоги в политике (фактически 29/24/5); не записаны пробелы Polkadot/Optimism/Cosmos/TON/Avalanche. P3: подделанные limits/terms.url не ловились. 13 endpoint перепроверены curl — совпали.
- Раунд 2 `36fb128`: ACCEPT. Тест сверяет итоги политики с каталогом; 7 endpoint пробелов перепроверены; srcmut.py 9/9, srcmut2.py — все мутации пойманы.
- Права/условия всех 29 источников: unverified/null.

## CW-002i — RETURN → ACCEPT

- Раунд 1 `073befc`: RETURN. P2: смесь legacy/изолированных путей без RB_ENV проходила. Бэкапы SQLite проверены (shasum, integrity_check).
- Раунд 2 `666a891`: ACCEPT. Правило «все или ничего» без RB_ENV и при legacy; production с частичным переопределением разрешён решением интегратора и задокументирован. rtmut.py 26/26.
- Найдено: непустой `telegraph_token` в bot.sqlite и в истории Git → SEC-01.
- Интеграция: `c29d652` (CW-004a), `0b78707` (CW-002i). Перед merge локальные SQLite скопированы в `CWIRE/salvage/integration-pre-002i/` и восстановлены, SHA совпали. Ran 82 тестов OK, оба checker OK.
