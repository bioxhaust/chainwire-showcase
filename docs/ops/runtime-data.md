# Runtime-данные и изоляция путей (CW-002i)

## Пути

Разрешение путей — `resolve_runtime_paths()` в `research-bot/research_bot/config.py`; `db.py` и `kb.py` берут пути только из config.

| Переменная | По умолчанию | Что изменяется |
|---|---|---|
| `RB_DATA_DIR` | `research-bot/data` | исходные входы (`kb/`, `funds.csv`, `seed_accounts.json`, …) и кеши рядом с ними: `funds_2026.csv`, `raises_cache.json` |
| `RB_DB` | `<data>/bot.sqlite` | seen/predictions/posts/kv (в kv — Telegraph token) |
| `RB_KB_DB` | `<data>/kb.sqlite` | FTS-индекс KB, пересобирается из источников |
| `RB_CORPUS` | `<repo>/index_dedup.jsonl` | только чтение |
| `RB_ENV` | не задан (legacy) | `test`, `staging`, `production`, `legacy` |

Правила:
- `RB_ENV=test|staging` требует явный `RB_DATA_DIR`; ни DATA, ни bot DB, ни KB DB не могут лежать в `research-bot/data`. Иначе — `RuntimeIsolationError` при импорте.
- Ложная изоляция запрещена: при `RB_ENV` не задан или `RB_ENV=legacy` изменяемые пути (DATA с кешами, bot DB, KB DB) должны быть либо все в `research-bot/data`, либо все вне его. Любая смесь (только `RB_DB`, только `RB_KB_DB`, `RB_DATA_DIR` вне при KB/DB в legacy и т.п.) — `RuntimeIsolationError` при импорте.
- **`RB_ENV=production` разрешает частичное переопределение явно**: например, `RB_DB` вне `research-bot/data` при общих KB и кешах. Это осознанный выбор оператора, а не изоляция; для тестов и staging он не применяется.
- bot DB и KB DB — разные файлы.
- Значения по умолчанию без переменных не изменились (legacy-запуск работает как раньше).

Подготовка тестового/staging-окружения:

```sh
mkdir -p /path/run && rsync -a --exclude '*.sqlite' research-bot/data/ /path/run/data/
RB_ENV=staging RB_DATA_DIR=/path/run/data RB_CORPUS=/path/run/index_dedup.jsonl python -m research_bot ...
```

## Runtime SQLite в Git

`research-bot/data/bot.sqlite` и `kb.sqlite` сняты с отслеживания (`git rm --cached`) в CW-002i; файлы остаются на диске и игнорируются `.gitignore` (`research-bot/data/`, `*.sqlite`). Исходный корпус (`research-bot/data/kb/`, csv, seed) остаётся в Git.

Резервные копии (вне репозитория): `/Users/i4goth/Desktop/CWIRE/salvage/cw-002i-runtime-sqlite/`, `SHA256SUMS`:

- `bot.sqlite` = `bot.HEAD-76c48c4.sqlite`: `1336c536b5b7272d3e63436eb0752c9bb867506a9c5fcff745eca2e66cd8e2d3`
- `kb.sqlite` = `kb.HEAD-76c48c4.sqlite`: `97eb529ed13dce0ca4428190874732bacdac9c1f76622ca6db83c09472684673`

**Внимание при слиянии:** checkout/merge коммита, удаляющего файлы из индекса, удалит их из рабочей копии того checkout. Перед обновлением любого checkout с рабочими БД сделать копию, затем при необходимости восстановить.

### Восстановление (проверено)

```sh
B=/Users/i4goth/Desktop/CWIRE/salvage/cw-002i-runtime-sqlite
(cd "$B" && shasum -a 256 -c SHA256SUMS)
cp -p "$B/bot.sqlite" "$B/kb.sqlite" research-bot/data/
shasum -a 256 research-bot/data/bot.sqlite research-bot/data/kb.sqlite   # сравнить с SHA выше
python3 -c "import sqlite3,sys;[print(f, sqlite3.connect(f'file:{f}?mode=ro',uri=True).execute('pragma integrity_check').fetchone()[0]) for f in sys.argv[1:]]" research-bot/data/bot.sqlite research-bot/data/kb.sqlite
git status --short research-bot/data   # пусто: файлы игнорируются
```

Альтернатива: `git show 76c48c4:research-bot/data/bot.sqlite > ...` (история не переписывалась).

## Аудит доступов (без значений)

- `bot.sqlite`, таблица `kv`: 3 строки; ключ с признаком учётных данных — `telegraph_token`, значение непустое. Значение не выводилось.
- Файл попал в историю Git коммитом `e9df6ab` (2026-10-30 15:36:56 +0300) и остаётся в истории после снятия с отслеживания. Telegraph access token нужно считать раскрытым: отозвать/перевыпустить (владелец доступов) и включить в общий аудит SEC-01. Переписывание истории — отдельное решение владельца.
- `.env` не читался.

## Не в зоне CW-002i

- `.gitignore` игнорирует весь `research-bot/data/`, включая отслеживаемый исходный корпус `research-bot/data/kb/` и csv: новые файлы корпуса молча не попадут в Git. Выносится в отдельную карточку.

`funds.py`, `hot.py`, `scoring.py`, `discovery/*` пишут/читают через `config.DATA`, поэтому следуют `RB_DATA_DIR` без правок. Отдельный каталог для кешей (отделить от входов) потребует передачи этих файлов.
