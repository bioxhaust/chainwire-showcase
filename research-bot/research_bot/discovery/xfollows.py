"""New accounts followed by smart/research seed accounts. Needs X_BEARER_TOKEN (X API Basic+ for /following)."""
import json
from ..config import DATA, X_BEARER_TOKEN
from ..http import jget
from .. import db
def seeds(): return json.load(open(DATA / "seed_accounts.json"))
def discover(limit=10, max_seeds=15):
    if not X_BEARER_TOKEN:
        print("[xfollows] X_BEARER_TOKEN not set -> skipped"); return []
    H = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}; counts = {}
    for s in seeds()[:max_seeds]:
        h = s if isinstance(s, str) else s.get("handle")
        u = jget(f"https://api.x.com/2/users/by/username/{h.lstrip('@')}", headers=H)
        if not u or "data" not in u: continue
        f = jget(f"https://api.x.com/2/users/{u['data']['id']}/following?max_results=100&user.fields=created_at,public_metrics,description", headers=H) or {}
        prev = set(json.loads(db.kv_get(f"follow:{h}", "[]"))); cur = [x["username"] for x in f.get("data", [])]
        db.kv_set(f"follow:{h}", json.dumps(cur))
        if prev:
            for x in f.get("data", []):
                if x["username"] not in prev: counts.setdefault(x["username"], {"by": [], "u": x})["by"].append(h)
    out = [{"kind": "x", "key": f"x:{k}", "name": k, "followed_by": v["by"], "x": v["u"], "priority": len(v["by"])} for k, v in counts.items()]
    out.sort(key=lambda x: -x["priority"])
    return [x for x in out if db.is_new(x["key"], "x", x["name"], x)][:limit]
