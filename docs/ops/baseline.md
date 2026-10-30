# CW-002a: safe repository baseline

This document records local evidence for the current checkout. Chainwire is a pilot name; RU and EN and crypto-wide coverage remain product requirements. The [reference report](../reference/chainwire-materials-and-server.md) and [plan](../reference/chainwire-brand-plan.md) are versioned inputs, not fresh deployment verification.

## Local facts and changes

- Baseline sources: `a0ce50f` stopped tracking `research-bot/.env`; `0108b0e` added the supplied reference snapshots. The integrator preserved the existing local `.env`; this task did not read its values or inspect old secret contents.
- The integrator's baseline inventory found nonempty secret fields. Their validity is unknown. Removing `.env` from the index does not revoke keys and does not clean Git history, existing clones or server copies. Credential rotation/revocation and an access audit are release blockers; the owner of operational access must supply evidence of completion.
- Python 3.12 is the CI target. Dependencies remain the existing version ranges in `research-bot/requirements.txt`; no runtime behavior or configuration defaults changed.
- `.env.example` lists every supported environment variable with empty commented assignments. The offline checker compares it with AST-detected environment access throughout `research_bot/`, including settings outside `config.py`.
- The checker rejects indexed `.env` and `.env.*` files except `*.example`; it only examines their names, never their contents. This is a narrow guard, not a general secret scanner or proof that history/data contain no credentials.
- Both `research-bot/data/bot.sqlite` and `research-bot/data/kb.sqlite` remain tracked. No corpus/data was removed or runtime database opened by this task. `telegraph.py` stores a publishing access token in the bot database's `kv` table; whether a given current file contains a valid token was not assessed here. Treat the tracked DB and history as access-audit inputs.
- Offline checks inspect source zones `research-bot/research_bot`, `scripts`, `tests`, skipping nested worktrees, venvs and source symlinks. They parse code rather than import it, do not load `.env`, and do not call the bot, LLM, network or database APIs. Symlinked configuration templates are rejected. Test fixtures are temporary.

## Commands and evidence

Run from the repository root; see the [RU/EN README](../../research-bot/README.md) for installation and runtime cautions:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r research-bot/requirements.txt
.venv/bin/python -B scripts/check_repository.py
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
```

The install is the only network setup step. The validation commands run offline. CI repeats dependency installation plus the AST/index/template check and offline unit tests on Python 3.12 for pushes and pull requests, with read-only repository permission and no service secrets.

Local validation used two existing Python runtimes in the isolated `cw/cw-002a-baseline` worktree:

- `python3.12 -m venv .venv` failed during `ensurepip`, before requirements installation. The host's `pyexpat` extension could not resolve `_XML_SetAllocTrackerActivationThreshold` from `/usr/lib/libexpat.1.dylib`. Running `.venv/bin/python -m ensurepip --upgrade --default-pip` reproduced that host runtime error. No system libraries were modified.
- `python3.12 -m venv --without-pip .venv` succeeded, providing a fresh Python 3.12.13 environment for the stdlib-only checks. This fallback does not install runtime dependencies.
- `.venv/bin/python -B scripts/check_repository.py` passed: **31 Python files**, **27 environment variables**, no private `.env` in the index; it reported the two retained tracked databases.
- `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v` passed: **12 tests**. These include no runtime execution, no `.env`/database content reads, blocked socket/SQLite connections, unchanged fixture database bytes, rejection of private `.env` in the index, configuration completeness, syntax redaction, and exclusion of worktrees/venvs/symlinks.
- `git diff --check` passed; no tracked data files changed and this worktree has no `.env`.

The existing managed CPython **3.12.11** then completed dependency installation and all checks in a separate fresh temporary environment. Exact commands from the worktree root:

```sh
/Users/i4goth/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 -m venv .venv-verified
.venv-verified/bin/python --version
.venv-verified/bin/python -m pip install -r research-bot/requirements.txt
.venv-verified/bin/python -m pip check
.venv-verified/bin/python -B scripts/check_repository.py
.venv-verified/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
git diff --exit-code -- research-bot/data
test ! -e research-bot/.env
```

All exited 0: Python 3.12.11; requirements installed; `pip check` reported “No broken requirements found”; AST/index/template validation again passed for 31 Python files and 27 variables; all 12 offline tests passed. Resolved direct packages: `requests==2.34.2`, `python-telegram-bot==22.8` (with job-queue extra), `python-dotenv==1.2.4`. This is local installation evidence, not a dependency lock. The temporary `.venv-verified` was removed after verification; no system repair, bot import, live publication or runtime data mutation was performed.

Dependency installation is **verified locally on managed Python 3.12.11**; the separate Homebrew 3.12.13/expat failure remains a host-specific observation. The hosted CI installation/run remains pending: a committed workflow is written configuration until an actual GitHub run succeeds. Independent acceptance belongs to the integrator/reviewer and must cite the result; local execution alone does not constitute acceptance or deployment.

## Historical server snapshot — not repeated by this task

The supplied report records a service in `/opt/research-bot`, systemd startup via `python -m research_bot telegram`, root execution, `Restart=always`, and a live cycle observed on 30 October 2026. It records Python/README/requirements parity through SHA-256 for 31 files because that server installation had no `.git`. It also records 30-minute cycles, four-hour hot scans, RU/EN configuration, and earlier SQLite/network errors. These remain historical statements from that observation; this task did not connect to the server, reread its environment, verify current process health or deploy changes. The old service snapshot cannot establish that the new checker or any future change is deployed.

## Readiness and unresolved work

Written: configuration inventory, bilingual runbook, offline checker/tests and CI workflow. Checked: dependency installation and `pip check` in a fresh managed Python 3.12.11 venv; AST/index/template validation and 12 stdlib tests on Python 3.12.11 and 3.12.13. Hosted CI: unverified. Accepted: pending independent review. Deployed: not performed.

Release remains blocked by credential rotation/access audit (including repository history, clones and potentially credential-bearing runtime data), a controlled runtime data policy, and a separately verified integration/staging path. Existing `once`/`analyze` and `dry=True` scanner flags do not provide no-network isolation. `RB_DB` does not relocate KB/caches, and `stats` can mutate schema through `db.conn()`. These are explicit follow-up inputs for platform work, not claims fixed by this baseline.

The next platform task should provide isolated runtime configuration/data, idempotent migrations and independent delivery recovery for RU/EN before a live vertical path is accepted. Source/model budgets and release access remain external inputs; this task makes no financial, product-ranking or deployment decision.
