import datetime as dt
from ..config import X_BEARER_TOKEN
from ..http import jget
def xmetrics(handle):
    if not X_BEARER_TOKEN or not handle: return None
    H = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    u = jget(f"https://api.x.com/2/users/by/username/{handle.lstrip('@')}?user.fields=created_at,public_metrics,verified", headers=H)
    if not u or "data" not in u: return None
    d = u["data"]; m = d["public_metrics"]
    t = jget(f"https://api.x.com/2/users/{d['id']}/tweets?max_results=10&tweet.fields=public_metrics", headers=H) or {}
    eng = [x["public_metrics"]["like_count"] + x["public_metrics"]["retweet_count"] for x in t.get("data", [])]
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))).days
    avg = sum(eng) / len(eng) if eng else 0
    return {"handle": d["username"], "followers": m["followers_count"], "age_days": age, "avg_eng_last10": round(avg, 1),
            "eng_rate_pct": round(100 * avg / max(m["followers_count"], 1), 3),
            "bot_follower_flag": m["followers_count"] > 20000 and avg / max(m["followers_count"], 1) < 0.0005}
