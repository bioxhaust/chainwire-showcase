# Chainwire research bot — current baseline

Chainwire is a pilot name. The product covers the whole crypto sector; RU and EN are required together. Existing adapters and command input formats are implementation limits, not a two-ecosystem product scope. Current plan and evidence: [project references](../docs/reference/README.md). Installation facts and release blockers: [baseline](../docs/ops/baseline.md).

## RU: установка и безопасная проверка

Из корня checkout, где находятся `research-bot/`, `scripts/` и `tests/`, установите зависимости в отдельный venv Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r research-bot/requirements.txt
```

Установка скачивает пакеты; это сетевой шаг подготовки. `requirements.txt` содержит диапазоны версий, поэтому это проверяемый способ установки, а не побайтово воспроизводимый lockfile.

После установки выполняйте из того же корня **только эти офлайн-проверки**:

```sh
.venv/bin/python -B scripts/check_repository.py
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Для самих проверок достаточно Python 3.12 и Git: checker и текущие тесты используют стандартную библиотеку. Они разбирают Python через AST, не импортируют `research_bot`/`config`, не загружают `.env`, не вызывают LLM/HTTP и не открывают рабочие SQLite. Тесты создают отдельные временные Git-репозитории. Ключ `-B` запрещает запись bytecode. Проверка не читает вложенные worktrees, venv или symlinks исходников; `.env` проверяется только по именам в Git-индексе. Эти проверки не доказывают корректность runtime или доставки.

[`.env.example`](.env.example) — полный перечень переменных, читаемых кодом, с пустыми **закомментированными** значениями. В нем нет ключей, каналов или адресов частных сервисов. Офлайн-проверке `.env` не нужен. Для отдельно разрешённого runtime можно создать локальный игнорируемый `.env` из шаблона, затем заполнить и раскомментировать нужные строки. Не раскомментируйте пустые числовые настройки: `int('')`/`float('')` приводят к ошибке. Неиспользуемые строки оставляйте закомментированными, чтобы сохранить значения по умолчанию в коде. `ANNOUNCE_IN_CHANNEL` по умолчанию включён; пустая строка его не отключает. Копирование шаблона и отсутствие ключей **не включают офлайн-режим**.

`once` и `analyze` **не являются безопасными no-network dry-run**. Они обращаются к внешним источникам, могут вызывать LLM при наличии ключа, менять CSV/кеши и SQLite; ветки публикации могут создавать внешние страницы. Печать в stdout не исключает других побочных эффектов. `hot`/`breaking` с внутренним `dry=True` также не означают отсутствие сети. `build-kb` пересоздаёт KB; `stats` использует соединение, которое может создавать/менять схему. Даже `--help` импортирует конфигурацию. Не используйте эти команды как smoke-test checkout.

`research-bot/data/bot.sqlite` и `kb.sqlite` уже отслеживаются Git вопреки текущему ignore. `RB_DB` перенаправляет только базу бота: KB и другие файлы всё равно привязаны к `data/`. Отделение runtime-данных, аудит сохранённых токенов и корректный no-network режим — следующие отдельные задачи; существующий корпус не удалён. До них запускайте runtime только по утверждённой процедуре с изолированными данными и после закрытия блока доступа/секретов.

## EN: install and validate safely

Run the two installation commands above from the repository root using Python 3.12. Dependency installation uses the network. Version ranges are not a lockfile. Run the two validation commands from the same directory afterward; they require only Python and Git and run offline.

The checker parses source as AST, compares the configuration inventory with `.env.example`, rejects tracked private `.env` files (including `.env.production`; `*.example` is allowed), and reports tracked databases. It does not import bot configuration, load credentials, contact an LLM/network service, or open runtime SQLite. Current unit tests use temporary fixtures and test those safety boundaries. Passing these checks is not a runtime, staging or delivery test.

All supported variables appear in `.env.example` as commented empty assignments. Leave unused settings commented so numeric defaults remain valid. No `.env` is needed for offline validation. For a separately authorized runtime, populate a local ignored `.env`; never commit real values. Empty credentials do not disable public HTTP calls or database writes. Channel announcements are enabled by default; an empty value does not disable them.

`once` and `analyze` are **not safe no-network dry runs**: they can contact sources/LLMs, change local data and, in publishing paths, create external pages. `hot`/`breaking` dry flags do not guarantee offline execution. `build-kb` rebuilds the KB, `stats` can initialize/migrate database tables, and even CLI help imports configuration. `RB_DB` relocates only the bot database, not the KB/caches. Treat live commands as operational actions, not repository checks.

The corpus and tracked databases are retained. Credential rotation and access audit, isolated runtime data, and a real offline runtime mode remain separate work. See the [baseline evidence and limits](../docs/ops/baseline.md); no deployment is claimed here.

## Existing CLI reference — operational commands

After an approved runtime setup, invoke commands from `research-bot/` using `../.venv/bin/python -m research_bot <command>`. This is a reference, not a validation recipe:

- `analyze '<query>'`: accepts a name/ticker, supported mint address or X URL; enrichment and prediction storage.
- `once`, `loop`, `telegram`: one cycle, continuous cycles or Telegram service with delivery.
- `refresh-funds`, `build-kb`, `stats`: refresh data, rebuild KB or read statistics through the runtime database layer.
- `hot`, `breaking`, `tg`: source scanning; network and runtime state may be involved.

The historical “% with token” measure approximates whether a project name is found in DefiLlama protocols/CoinGecko. It does not establish an airdrop or an investment outcome.
