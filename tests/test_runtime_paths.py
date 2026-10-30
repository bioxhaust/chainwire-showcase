"""CW-002i: explicit, separate runtime paths; no false isolation; runtime SQLite untracked.

Imports research_bot.config with a stub dotenv (no .env is read) and a cleared environment.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "research-bot"
LEGACY = (BOT / "data").resolve()
RB_VARS = ("RB_ENV", "RB_DATA_DIR", "RB_DB", "RB_KB_DB", "RB_CORPUS")


def load_modules(*names, **env):
    """Import research_bot modules with a no-op dotenv stub and only the given RB_* variables."""
    calls = []
    stub = types.ModuleType("dotenv")
    stub.load_dotenv = lambda *a, **k: calls.append(a)  # never opens .env
    clean = {k: v for k, v in os.environ.items() if k not in RB_VARS}
    clean.update(env)
    with mock.patch.dict(sys.modules, {"dotenv": stub}), mock.patch.dict(os.environ, clean, clear=True):
        if str(BOT) not in sys.path:
            sys.path.insert(0, str(BOT))
        for name in [m for m in sys.modules if m == "research_bot" or m.startswith("research_bot.")]:
            del sys.modules[name]
        modules = [importlib.import_module("research_bot." + n) for n in names]
    return modules[0] if len(modules) == 1 else modules


def load_config(**env):
    return load_modules("config", **env)


class RuntimePathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()

    def resolve(self, **kw):
        return load_config(RB_ENV="test", RB_DATA_DIR=str(self.tmp)).resolve_runtime_paths(root=BOT, **kw)

    def test_isolated_env_puts_every_mutable_path_outside_legacy(self):
        cfg = load_config(RB_ENV="test", RB_DATA_DIR=str(self.tmp))
        for value in (cfg.DATA, Path(cfg.DB_PATH), cfg.KB_DB):
            self.assertTrue(Path(value).resolve().is_relative_to(self.tmp), value)
            self.assertFalse(Path(value).resolve().is_relative_to(LEGACY), value)
        self.assertNotEqual(Path(cfg.DB_PATH), cfg.KB_DB)

    def test_staging_requires_explicit_data_dir(self):
        cfg = load_config(RB_ENV="test", RB_DATA_DIR=str(self.tmp))
        for env in ("test", "staging"):
            with self.assertRaises(cfg.RuntimeIsolationError):
                cfg.resolve_runtime_paths(rb_env=env, root=BOT)

    def test_isolated_env_refuses_any_legacy_path(self):
        cfg = load_config(RB_ENV="test", RB_DATA_DIR=str(self.tmp))
        with self.assertRaises(cfg.RuntimeIsolationError):
            cfg.resolve_runtime_paths(rb_env="staging", data_dir=str(self.tmp), kb_db=str(LEGACY / "kb.sqlite"), root=BOT)
        with self.assertRaises(cfg.RuntimeIsolationError):
            cfg.resolve_runtime_paths(rb_env="test", data_dir=str(LEGACY), root=BOT)

    def test_rb_db_alone_is_not_false_isolation(self):
        cfg = load_config(RB_ENV="test", RB_DATA_DIR=str(self.tmp))
        with self.assertRaises(cfg.RuntimeIsolationError):
            cfg.resolve_runtime_paths(db=str(self.tmp / "bot.sqlite"), root=BOT)
        # importing with only RB_DB refuses too
        with self.assertRaisesRegex(RuntimeError, "false isolation"):
            load_config(RB_DB=str(self.tmp / "bot.sqlite"))

    def test_mixed_placement_refused_without_env_or_with_legacy(self):
        cfg = load_config()
        out, leg = self.tmp, LEGACY
        mixes = [dict(db=str(out / "b.sqlite")), dict(kb_db=str(out / "k.sqlite")),
                 dict(data_dir=str(out), kb_db=str(leg / "kb.sqlite")), dict(data_dir=str(out), db=str(leg / "bot.sqlite")),
                 dict(db=str(out / "b.sqlite"), kb_db=str(out / "k.sqlite"))]  # data/caches still legacy
        for env in (None, "legacy"):
            for kw in mixes:
                with self.subTest(env=env, **kw), self.assertRaisesRegex(cfg.RuntimeIsolationError, "false isolation"):
                    cfg.resolve_runtime_paths(rb_env=env, root=BOT, **kw)
        full = cfg.resolve_runtime_paths(data_dir=str(out), root=BOT)  # everything moved: consistent
        self.assertTrue(full["kb_db"].is_relative_to(out))

    def test_production_partial_override_is_explicitly_allowed(self):
        cfg = load_config()
        paths = cfg.resolve_runtime_paths(rb_env="production", db=str(self.tmp / "b.sqlite"), root=BOT)
        self.assertEqual(paths["kb_db"], LEGACY / "kb.sqlite")

    def test_legacy_defaults_unchanged(self):
        cfg = load_config()
        self.assertEqual(Path(cfg.DB_PATH), LEGACY / "bot.sqlite")
        self.assertEqual(cfg.KB_DB, LEGACY / "kb.sqlite")
        self.assertEqual(cfg.CORPUS, (ROOT / "index_dedup.jsonl").resolve())

    def test_db_and_kb_must_differ_and_env_validated(self):
        cfg = load_config(RB_ENV="test", RB_DATA_DIR=str(self.tmp))
        with self.assertRaises(cfg.RuntimeIsolationError):
            cfg.resolve_runtime_paths(rb_env="test", data_dir=str(self.tmp), db=str(self.tmp / "x"), kb_db=str(self.tmp / "x"), root=BOT)
        with self.assertRaises(cfg.RuntimeIsolationError):
            cfg.resolve_runtime_paths(rb_env="prod", root=BOT)

    def test_db_and_kb_modules_write_only_to_isolated_paths(self):
        (self.tmp / "kb").mkdir()
        (self.tmp / "kb" / "note.txt").write_text("isolated runtime corpus about restaking " * 5)
        corpus = self.tmp / "corpus.jsonl"
        corpus.write_text("")
        legacy_before = {p: p.stat().st_mtime_ns for p in LEGACY.glob("*.sqlite")}
        db, kb = load_modules("db", "kb", RB_ENV="test", RB_DATA_DIR=str(self.tmp), RB_CORPUS=str(corpus))
        self.assertTrue(db.is_new("k1", "test", "name"))
        self.assertFalse(db.is_new("k1", "test", "name"))
        self.assertGreater(kb.build(), 0)
        self.assertTrue(kb.search("restaking"))
        self.assertTrue((self.tmp / "bot.sqlite").exists() and (self.tmp / "kb.sqlite").exists())
        self.assertEqual(legacy_before, {p: p.stat().st_mtime_ns for p in LEGACY.glob("*.sqlite")})

    def test_runtime_sqlite_not_tracked_and_ignored(self):
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached"], capture_output=True, text=True, check=True).stdout
        self.assertFalse([p for p in tracked.splitlines() if p.endswith((".sqlite", ".sqlite3", ".db"))])
        for path in ("research-bot/data/bot.sqlite", "research-bot/data/kb.sqlite"):
            self.assertEqual(subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", path]).returncode, 0, path)

    def test_source_corpus_still_tracked(self):
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "research-bot/data/kb"], capture_output=True, text=True, check=True).stdout
        self.assertGreaterEqual(len(tracked.splitlines()), 35)


if __name__ == "__main__":
    unittest.main()
