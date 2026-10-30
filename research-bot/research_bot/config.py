import os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except ImportError: pass
LEGACY_DATA = ROOT / "data"
ISOLATED_ENVS = ("test", "staging")


class RuntimeIsolationError(RuntimeError):
    """Refuse partial isolation: a separate bot DB with a shared KB/cache is not isolation."""


def resolve_runtime_paths(rb_env=None, data_dir=None, db=None, kb_db=None, corpus=None, root=ROOT):
    """Pure path resolution (CW-002i). Returns dict of absolute paths; raises on false isolation.

    data:   directory with source inputs and the mutable caches written beside them
            (funds_2026.csv, raises_cache.json); in test/staging it must be an explicit copy.
    db:     bot SQLite (seen/predictions/posts/kv incl. Telegraph token).
    kb_db:  knowledge-base FTS SQLite (rebuilt from sources).
    corpus: read-only Telegram corpus (index_dedup.jsonl).
    """
    root = pathlib.Path(root).resolve()
    legacy = (root / "data").resolve()
    env = (rb_env or "").strip().lower() or None
    if env is not None and env not in ISOLATED_ENVS + ("production", "legacy"):
        raise RuntimeIsolationError("RB_ENV must be one of test, staging, production, legacy")
    data = pathlib.Path(data_dir).expanduser().resolve() if data_dir else legacy
    paths = {
        "data": data,
        "db": pathlib.Path(db).expanduser().resolve() if db else data / "bot.sqlite",
        "kb_db": pathlib.Path(kb_db).expanduser().resolve() if kb_db else data / "kb.sqlite",
        "corpus": pathlib.Path(corpus).expanduser().resolve() if corpus else root.parent / "index_dedup.jsonl",
    }

    def in_legacy(path):
        return path == legacy or legacy in path.parents

    mutable = ("data", "db", "kb_db")
    if env in ISOLATED_ENVS:
        if not data_dir:
            raise RuntimeIsolationError(f"RB_ENV={env} requires explicit RB_DATA_DIR (a copy of research-bot/data)")
        shared = [name for name in mutable if in_legacy(paths[name])]
        if shared:
            raise RuntimeIsolationError(f"RB_ENV={env} must not use legacy research-bot/data for: {', '.join(shared)}")
    elif env in (None, "legacy"):
        # Mixed placement looks isolated while other mutable state stays shared: refuse.
        placement = {name: in_legacy(paths[name]) for name in mutable}
        if len(set(placement.values())) > 1:
            shared = ", ".join(n for n, v in placement.items() if v)
            moved = ", ".join(n for n, v in placement.items() if not v)
            raise RuntimeIsolationError(f"false isolation: {moved} outside research-bot/data but {shared} shared; "
                                        "set RB_DATA_DIR for all mutable paths, or RB_ENV=production to accept a partial override")
    # RB_ENV=production: partial overrides are an explicit operator choice (docs/ops/runtime-data.md).
    if len({paths["db"], paths["kb_db"]}) != 2:
        raise RuntimeIsolationError("bot DB and KB DB must be different files")
    return paths


_PATHS = resolve_runtime_paths(os.getenv("RB_ENV"), os.getenv("RB_DATA_DIR"), os.getenv("RB_DB"),
                               os.getenv("RB_KB_DB"), os.getenv("RB_CORPUS"))
DATA = _PATHS["data"]
DB_PATH = str(_PATHS["db"])
KB_DB = _PATHS["kb_db"]
CORPUS = _PATHS["corpus"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")  # any OpenAI-compatible (xAI, OpenRouter, Groq, local)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
ROOTDATA_API_KEY = os.getenv("ROOTDATA_API_KEY")
CRYPTORANK_API_KEY = os.getenv("CRYPTORANK_API_KEY")
POST_MIN_SCORE = int(os.getenv("POST_MIN_SCORE", "55"))
LOOP_MINUTES = int(os.getenv("LOOP_MINUTES", "30"))
HOT_SCAN_HOURS = float(os.getenv("HOT_SCAN_HOURS", "4"))
HOT_MIN_SCORE = int(os.getenv("HOT_MIN_SCORE", "70"))
HOT_MAX_POSTS = int(os.getenv("HOT_MAX_POSTS", "3"))
HOT_MAX_CANDIDATES = int(os.getenv("HOT_MAX_CANDIDATES", "30"))
HOT_MIN_MENTIONS = int(os.getenv("HOT_MIN_MENTIONS", "2"))
HOT_DEADLINE_DAYS = int(os.getenv("HOT_DEADLINE_DAYS", "14"))
ANNOUNCE_IN_CHANNEL = os.getenv("ANNOUNCE_IN_CHANNEL", "true").lower() not in ("0", "false", "no")
CHANNEL_RU = os.getenv("CHANNEL_RU"); CHANNEL_EN = os.getenv("CHANNEL_EN")
