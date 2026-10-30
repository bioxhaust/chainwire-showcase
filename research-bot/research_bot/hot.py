"""'Hot now' mode: re-scan known projects for live, time-limited opportunities (deadlines, phases)."""
import csv, json, re, time, datetime as dt, urllib.parse, email.utils
import xml.etree.ElementTree as ET
from .config import (DATA, OPENAI_API_KEY, LLM_BASE_URL, LLM_MODEL, HOT_MIN_SCORE, HOT_MAX_POSTS, HOT_MAX_CANDIDATES,
                     HOT_MIN_MENTIONS, HOT_DEADLINE_DAYS)
from .http import get, S
from . import db
from .pipeline import enrich
from .scoring import score
from .fmt import project_post, deadlines_block
MARK = "🔥 <b>АКТУАЛЬНО СЕЙЧАС</b> · не новость"
MARK_UPD = "🔥 <b>АКТУАЛЬНО СЕЙЧАС</b> · обновление"
Q = '(airdrop OR snapshot OR claim OR testnet OR TGE OR points OR season OR "token launch")'
STOP = {"bitcoin","btc","ethereum","eth","solana","sol","binance","coinbase","okx","ripple","xrp","bitwise","capital","tbd","crypto",
        "polygon","stellar","chainlink","aave","uniswap","usdc","usdt","tether","circle","rlusd","hedera","cardano","dogecoin","sec","cftc","robinhood"}
def bad(nm):
    w = nm.lower().split()
    return len(nm) < 3 or nm.lower() in STOP or (w and w[0] in STOP and len(w) > 1 and w[1] in {"opens","set","adds","launches","says"})
def candidates():
    c, out, cutoff = db.conn(), {}, time.time() - 45 * 86400
    for kind, name, payload in c.execute("select kind,name,payload from seen where kind in ('round','news-project') and first_seen>? order by first_seen desc", (cutoff,)):
        p = json.loads(payload or "{}")
        nm = p.get("project") or name if kind == "news-project" else name
        out.setdefault(db.pkey(nm), {"name": nm, "src": kind, "prio": 2 if kind == "news-project" else 1, "investors": p.get("investors"), "round": p.get("round"), "amount": p.get("amount"), "date": p.get("date")})
    f = DATA / "funds_2026.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8")):
            for part in (r.get("tokenless_latest") or "").split("; ")[:8]:
                nm = part.split(" (")[0].strip()
                if nm:
                    e = out.setdefault(db.pkey(nm), {"name": nm, "src": "funds_tokenless", "prio": 0, "investors": []})
                    e["prio"] += 2; e.setdefault("funds", []).append(r["fund"])
    return sorted((v for v in out.values() if not bad(v["name"])), key=lambda x: -x["prio"])[:HOT_MAX_CANDIDATES]
def gnews(name, days=7):
    url = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=" + urllib.parse.quote(f'"{name}" {Q} when:{days}d')
    r = get(url)
    if r is None or not r.ok: return []
    try: root = ET.fromstring(r.content)
    except ET.ParseError: return []
    res = []
    for it in root.iter("item"):
        t = it.findtext("title") or ""; l = it.findtext("link") or ""
        try: ts = email.utils.parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
        except Exception: ts = ""
        if name.lower() in t.lower(): res.append({"title": t, "link": l, "date": ts})
    return res[:15]
def extract_deadlines(name, arts):
    today = dt.date.today().isoformat()
    prompt = (f"Today is {today}. Project: {name}. From these headlines (last 7 days) extract time-limited windows for users: "
              "snapshot, claim start/end, airdrop checker, testnet phase start/end, points season start/end, TGE/listing date, presale/ICO dates. "
              'Return ONLY JSON: {"deadlines":[{"type":str,"date":"YYYY-MM-DD or null","what":"short Russian description","idx":int}],'
              '"phase_just_opened":bool,"urgency":0-100,"interest_trend":"rising|flat|falling"}. Do not invent dates; only from text.\n\n' +
              "\n".join(f"{i}. ({a['date']}) {a['title']}" for i, a in enumerate(arts)))
    r = S.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=120,
               json={"model": LLM_MODEL, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
    j = r.json()
    if "choices" not in j: raise RuntimeError(str(j)[:200])
    o = json.loads(re.search(r"\{.*\}", j["choices"][0]["message"]["content"], re.S).group(0))
    for d in o.get("deadlines", []):
        i = d.get("idx")
        if isinstance(i, int) and 0 <= i < len(arts): d["link"] = arts[i]["link"]
    return o
def rule_deadlines(arts):
    dls = [{"type": "event", "date": a["date"], "what": a["title"][:120], "link": a["link"]} for a in arts
           if re.search(r"snapshot|claim|checker|testnet|TGE|season|points|airdrop", a["title"], re.I)]
    return {"deadlines": dls[:3], "phase_just_opened": bool(dls), "urgency": 50 if dls else 0, "interest_trend": "flat"}
def window_ok(o):
    today = dt.date.today()
    for d in o.get("deadlines", []):
        try:
            dd = dt.date.fromisoformat(str(d.get("date"))[:10])
            if -1 <= (dd - today).days <= HOT_DEADLINE_DAYS: return True
        except ValueError: pass
    return bool(o.get("phase_just_opened"))
def sig(o): return "|".join(sorted(f"{d.get('type')}:{d.get('date')}" for d in o.get("deadlines", []) if d.get("date")))
def scan(post=None, dry=False):
    post = post or (lambda t, meta=None: print(t))
    cands = candidates(); print(f"[hot] {len(cands)} candidates"); posted = 0
    for c in cands:
        if posted >= HOT_MAX_POSTS: break
        arts = gnews(c["name"])
        if len(arts) < HOT_MIN_MENTIONS: continue
        try: o = extract_deadlines(c["name"], arts) if OPENAI_API_KEY else rule_deadlines(arts)
        except Exception as e: print("[hot] extract fail", c["name"], e); o = rule_deadlines(arts)
        if not window_ok(o): print(f"[hot] {c['name']}: {len(arts)} mentions, no window"); continue
        prev = db.last_post(c["name"]); s_ = sig(o)
        if prev and (not s_ or s_ == prev[2]): print(f"[hot] {c['name']}: already posted ({prev[0]}), no new deadline"); continue
        item = {"kind": "hot", "key": f"hot:{db.pkey(c['name'])}", "name": c["name"], "project": c["name"], "event": (o["deadlines"] or [{}])[0].get("type"),
                "headline": arts[0]["title"], "link": arts[0]["link"], "investors": c.get("investors") or c.get("funds"),
                "round": c.get("round"), "amount": c.get("amount"), "date": c.get("date"),
                "hot": {"mentions_7d": len(arts), "trend": o.get("interest_trend"), "urgency": o.get("urgency"), "deadlines": o.get("deadlines")}}
        d = enrich(item); s = score(d)
        total = round(0.7 * int(s.get("score", 0)) + 0.3 * int(o.get("urgency") or 0))
        if total < HOT_MIN_SCORE: print(f"[hot] {c['name']}: score {s.get('score')} urgency {o.get('urgency')} -> {total} < {HOT_MIN_SCORE}"); continue
        s["score"] = total
        txt = project_post(d, s, marker=MARK_UPD if prev else MARK)  # deadlines/interest rendered from d["hot"]
        meta = {"name": c["name"], "mode": "hot-update" if prev else "hot", "sig": s_}
        post(txt, meta)
        if not dry: pass  # recorded by sender after successful send
        posted += 1
    print(f"[hot] posted {posted}")
    return posted
