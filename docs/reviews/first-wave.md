# CW-003a — Independent first-wave review

Date: 30 October 2026, Europe/Moscow. Reviewer: `/root/qa`; implementation authors: `/root/materials`, `/root/platform`; integrator: `/root`. Review worktree: `/Users/i4goth/Desktop/CWIRE/worktrees/cw-review`, detached at each reviewed SHA. Review followed `/Users/i4goth/.agents/skills/code-review/SKILL.md`.

**QA verdict: PASS for the first-wave changes listed below after corrections.** No unresolved critical or major finding remains in this scope. Technical acceptance and the combined integration run belong to the integrator and are recorded separately in [status.md](../status.md). This verdict does not accept runtime publication, methodology, staging or deployment.

## Findings and resolutions

1. **P2 / major — manifest opened an excluded path before rejecting it. Resolved.** On `28994eb9a32d00a8e10ef4ab1b2ddc114ce20e57`, a Telegram-index path pointing to `research-bot/.env` was added to the file inventory after an issue was recorded; the subsequent file loop still attempted to read it. Internal symlinks could also redirect allowed input paths to excluded files. QA reproduced the attempted read using a temporary synthetic fixture and a `Path.read_bytes` guard, which interrupted before any protected content was read. No real credentials were read. Author correction `e4bd4a1d4dc29a05f134033d1fbbb885da0aeeb9` rejects disallowed message paths immediately, routes input reads through a location/format allowlist, and rejects symlink components before early index/reference/log reads and output comparison. QA repeated the original reproducer: rejection occurs before the protected read. All 28 material tests pass, including eight new path-safety regressions.

2. **Minor — two historical source links lacked current snapshot targets. Resolved.** The source report linked `chainwire-images-ocr.jsonl` and `chainwire-image-ocr.swift`; neither was initially included in the reference snapshot mapping. Correction `cd2ec7d4c5a6b88dbcc62599cfe85b95502d7154` adds both supplied files and hashes. All five snapshots match their recorded SHA-256 and original supplied files; all 77 absolute Markdown source links resolve through the documented mapping. Remote URLs were not fetched.

3. **Minor — the new runtime-data task overlapped Research ownership of `kb.py`. Resolved.** Governance follow-up `75bfecc38c6386a797b889bf47e0aace9e9c2617` added Platform task CW-002i with `kb.py` in its scope. Correction `c17603f40801e75eb5bb7e938415a1868daf5813` explicitly transfers that file to Platform for CW-002i and makes Research CW-001d wait for acceptance and ownership return. Follow-up `94612a11b6aeef904940007d9078b92357e28f0b` also records sequential `fmt.py` ownership and its dependency. No concurrent file ownership is authorized by these transfers.

The initial unassigned QA/work-not-started board entry was corrected in `cd2ec7d` once QA began. It was a status update, not a claim of product acceptance.

## Reviewed commits and changed scope

- **CW-002s:** `a0ce50ff75bca31da9030740dc6d4b441baa3f0c`. Reviewed deletion metadata only; never requested the `.env` deletion patch or credential values.
- **CW-000a sources:** `0108b0e36eeb14bef3344e4856b58cbcddbb1cf8`, corrected by `cd2ec7d4c5a6b88dbcc62599cfe85b95502d7154`.
- **CW-000a governance:** `6639effbc0bcd3a1f1df100002213d10f55bd31c`; relevant subsequent board/ownership changes through `94612a11b6aeef904940007d9078b92357e28f0b`.
- **CW-002a Platform:** base `0108b0e`; author commits `b27fd47f7c90f9cf85828e830c245a64df067784` and final `6a88b0e8d564566814dee0b1db8ad14478685e2f`. Six owned files: `.github/workflows/checks.yml`, `scripts/check_repository.py`, `tests/test_repository_checks.py`, `research-bot/.env.example`, `research-bot/README.md`, `docs/ops/baseline.md`. Integration copies: `9d5c312` and `95a5ec6`; QA verified the final six-file contents match the author head exactly.
- **CW-001a Materials:** base `0108b0e`; owned author commits `82a32e02e1b42c1c69c9e09fdb41b02eea90b49b`, `28994eb9a32d00a8e10ef4ab1b2ddc114ce20e57`, and final `e4bd4a1d4dc29a05f134033d1fbbb885da0aeeb9`. Four owned files: `scripts/materials_manifest.py`, `tests/test_materials_manifest.py`, `docs/research/materials-manifest.json`, `docs/research/materials-manifest.md`. Integration copies: `10f944e`, `229b54b`, `fe20488`; QA verified the final four-file contents match the author head exactly. Intervening `bae123d` is the worker's copy of reference correction `cd2ec7d`, not another Materials result to integrate.

No functional bot modules, corpus source bytes, existing databases or external services were changed by the reviewed implementation. QA authored only this report in the integration checkout.

## Independent local verification

Commands ran from `/Users/i4goth/Desktop/CWIRE/worktrees/cw-review`. Python source was parsed or the new tooling/tests were imported; `research_bot` runtime modules were never imported.

**Governance and sources:** read the source plan, materials report, integration policy, scope and board. Initial board: 40 unique cards with owner, allowed files, dependencies, acceptance and separate written/checked/accepted/deployed fields; all dependency IDs existed, no cycles. The later runtime-data task makes 41 cards and adds a dependency before migrations. QA repeated the field/dependency/cycle validation on the updated 41-card board after the ownership changes; it passed. The complete crypto scope, Bitcoin and other ecosystems, RU/EN, shared facts and separate destinations remain explicit. Future roles are not represented as already running agents. Historical server observations are distinguished from current evidence. File transfers and readiness gates are documented.

The five reference SHA-256 values were recalculated with `hashlib.sha256(path.read_bytes())` and compared with `docs/reference/sources.json` and the original files named there. For the 77 local source links, the documented legacy-root mapping was applied and each target's existence checked; all passed after `cd2ec7d`.

**Secret-file state:** `git show --format=fuller --name-status a0ce50f` was used instead of a patch. File existence, `git ls-files --error-unmatch research-bot/.env`, and `git check-ignore --quiet research-bot/.env` established that integration retains its local ignored, untracked file. The Materials, Platform and QA worktrees contain no `.env`; it is untracked and ignored in each. No credential validity claim was made.

**Platform final head `6a88b0e`:** a fresh temporary venv was created using the existing managed interpreter; it was removed automatically after validation. These exact operations succeeded:

```sh
/Users/i4goth/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 -m venv /var/folders/4d/vk27rw_x0m1cglfkd9k3p_sr0000gn/T/cw-qa-venv-tg4c8emv
/var/folders/4d/vk27rw_x0m1cglfkd9k3p_sr0000gn/T/cw-qa-venv-tg4c8emv/bin/python --version
/var/folders/4d/vk27rw_x0m1cglfkd9k3p_sr0000gn/T/cw-qa-venv-tg4c8emv/bin/python -m pip install -r research-bot/requirements.txt
/var/folders/4d/vk27rw_x0m1cglfkd9k3p_sr0000gn/T/cw-qa-venv-tg4c8emv/bin/python -m pip check
/var/folders/4d/vk27rw_x0m1cglfkd9k3p_sr0000gn/T/cw-qa-venv-tg4c8emv/bin/python -B scripts/check_repository.py
/var/folders/4d/vk27rw_x0m1cglfkd9k3p_sr0000gn/T/cw-qa-venv-tg4c8emv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Result: Python **3.12.11**; dependency installation exit 0; `pip check`: **No broken requirements found**; checker: **31 Python files, 27 environment variables**; **12/12 tests passed**. Direct packages resolved to requests 2.34.2, python-telegram-bot 22.8 and python-dotenv 1.2.4. Tests also passed independently under existing Python 3.12.13 before the documentation-only final commit. The author's Homebrew/expat venv failure is accurately retained as a host-specific observation; successful managed installation is separate evidence. Installation is the only network setup step and did not run the bot.

**Materials final head `e4bd4a1`:**

```sh
/Users/i4goth/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 -B scripts/materials_manifest.py --check
/Users/i4goth/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 -B -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Result: `--check` exit 0, generated files match, **28/28 tests passed**, whitespace check clean. QA also repeated the original synthetic excluded-path reproducer independently under Python 3.12.13; it now raises `ManifestError` before the guarded read.

Independent manifest inspection recalculated all **172 file hashes** with no mismatch: **202 raw records / 101 unique messages**, **48 link messages / 53 photo messages**, **61 exact URLs**, **53 distinct photo hashes**, **35 KB files**, **22 recovered files**, zero missing files. All message publication times and original Telegram source URLs remain unknown. Every file/message/URL has `verification_status=unverified` and `full_original_verified=false`. Four shells, a 404 response, an incomplete thread and a profile captured instead of an article remain explicitly distinguished. Availability is not misrepresented as verified original completeness; import dates are separate from publication evidence. The path correction leaves the JSON inventory unchanged.

Before/after SHA-256 checks on both tracked SQLite files match the safe review baseline, and the QA worktree remained clean after all commands. Tests use temporary fixtures, including synthetic forbidden paths. No real `.env` contents or database rows were read, and no runtime connection, publication or server mutation was performed.

## Boundaries and handoff

- **Reviewed documents and local tests:** completed as above. File hashes prove byte identity; they do not prove the factual correctness of the source material or OCR.
- **Hosted CI:** workflow configuration was reviewed; no GitHub Actions run occurred in this task. Local success must not be described as a green hosted CI run.
- **Integration:** Platform and Materials author/integration content parity was checked. The separate suites above were run by QA; the combined run below is explicitly integrator-reported evidence.
- **Deployment and product:** none performed or accepted. There is no new verified API/site/Telegram RU+EN vertical result, no staging publication, and no new server smoke test.
- **Existing release blockers:** credentials require rotation/revocation and access audit; Git history and retained runtime databases remain audit inputs. This review did not inspect values or validate keys. Runtime data isolation is queued as CW-002i. The path guard is not a general scanner of arbitrary historical files.

The remaining work follows the single integration queue. This report is evidence for the first technical wave, not a percentage of overall product readiness.

## Integrator's combined verification

Integrator `/root` reported the combined run at integrated HEAD `fe20488` after Materials mappings `82a32e0 → 10f944e`, `28994eb → 229b54b`, `e4bd4a1 → fe20488` and Platform mappings `b27fd47 → 9d5c312`, `6a88b0e → 95a5ec6`.

Cwd: `/Users/i4goth/Desktop/CWIRE/chainwire`. Interpreter: managed Python 3.12.11 at `/Users/i4goth/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12`.

- `python -B scripts/check_repository.py`: PASS, **33 AST files / 27 environment variables**.
- `python -B scripts/materials_manifest.py --check`: PASS, **101 messages / 61 URLs / 53 unique photos**.
- `python -B -m unittest discover -s tests -p 'test_*.py' -v`: **40/40 passed**.
- `git diff --check`: PASS; integration checkout clean before this report was added.

QA independently verified the approved files match their integrated copies; the commands in this final section were reported by the integrator, not rerun by QA. Final technical acceptance is the integrator's board update. No GitHub push, hosted CI run, server change or deployment was performed.
