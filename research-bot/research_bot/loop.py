import time
from .config import POST_MIN_SCORE
import os
NEWS_MIN_IMPORTANCE = int(os.getenv("NEWS_MIN_IMPORTANCE", "4")); NEWS_MAX_POSTS = int(os.getenv("NEWS_MAX_POSTS", "3"))
from . import funds, tracker, db
from .discovery import rounds, pools, xfollows, news
from .pipeline import analyze
def cycle(post=lambda t, meta=None: print(t), per_source=3):
    try:
        r = funds.refresh_if_stale()
        if r: print(f"[funds] refreshed, freshest record {r[1]}")
    except Exception as e: print("[funds]", e)
    items = []
    try:
        from . import breaking; nb = breaking.scan(post); print(f"[breaking] posted {nb}")
    except Exception as e: print("[breaking] error", e)
    try:
        dg, nitems = news.discover()
        print(f"[news] {len(dg)} relevant headlines, {len(nitems)} new projects")
        # digest posts disabled (owner request): post top individual items instead
        top = [d for d in dg if int(d.get("importance") or 0) >= NEWS_MIN_IMPORTANCE][:NEWS_MAX_POSTS]
        if top:
            from .fmt import news_post; W = news.write_digest(top)
            for i, d in enumerate(top): post(news_post(d, W.get(i)), None)
        items += nitems[:per_source + 2]
    except Exception as e: print("[news] error", e)
    for name, fn in [("rounds", lambda: rounds.discover()), ("pools", lambda: pools.discover()), ("x", lambda: xfollows.discover())]:
        try: got = fn(); print(f"[{name}] {len(got)} new"); items += got[:per_source]
        except Exception as e: print(f"[{name}] error {e}")
    for it in items:
        nm = it.get("project") or it.get("name")
        if db.last_post(nm): print(f"[skip] {nm} already posted"); continue
        s, txt = analyze(it)
        if s["score"] >= POST_MIN_SCORE:
            post(txt, {"name": nm, "mode": "new"})
        else: print("(below threshold)\n" + txt)
        print("-" * 60)
    tracker.update()
