import re
from .enrich import market, scam, xmetrics
from .scoring import score
from . import db
EMO = {"farm": "🌾", "enter": "🟢", "watch": "👀", "scam": "🚫"}
def resolve(q):
    q = q.strip()
    m = re.search(r"([1-9A-HJ-NP-Za-km-z]{32,44})", q)
    if m: return {"kind": "pool", "name": q, "mint": m.group(1), "key": f"sol:{m.group(1)}"}
    m = re.search(r"(?:x|twitter)\.com/(\w+)", q)
    if m: return {"kind": "x", "name": m.group(1), "handle": m.group(1), "key": f"x:{m.group(1)}"}
    return {"kind": "query", "name": q.lstrip("$"), "key": f"q:{q.lower()}"}
def enrich(item):
    d = dict(item)
    if d.get("mint"):
        d["market"] = market.dexscreener(mint=d["mint"]); d["rugcheck"] = scam.rugcheck(d["mint"])
    else:
        d["market"] = market.dexscreener(query=d["name"], strict=d.get("kind") in ("round", "news"))
        if d["market"] and d["market"]["chain"] == "solana":
            d["rugcheck"] = scam.rugcheck(d["market"]["token"]["address"])
        if d.get("kind") not in ("round", "news") or d["market"]: d["coingecko"] = market.coingecko(d["name"])
    cg, mk = d.get("coingecko") or {}, d.get("market") or {}
    if cg.get("mcap") and mk and (mk.get("mcap") or mk.get("fdv") or 0) * 50 < cg["mcap"]:
        d["market_mismatch"] = mk.get("url"); d["market"] = None; d.pop("rugcheck", None)  # DEX pair is likely a clone
    h = d.get("handle") or (d.get("coingecko") or {}).get("twitter")
    d["x"] = xmetrics.xmetrics(h) or d.get("x")
    return d
def report(d, s):
    mk, rc, cg = d.get("market") or {}, d.get("rugcheck") or {}, d.get("coingecko") or {}
    L = [f"{EMO.get(s['verdict'],'')} {d['name']} — {s['score']}/100 · {s['verdict'].upper()} ({s.get('engine')})"]
    if d.get("kind") == "round": L.append(f"Раунд: {d.get('round')} ${(d.get('amount') or 0)/1e6:.1f}M · {d.get('date')} · {d.get('category')} · {', '.join(d.get('investors', [])[:6])}")
    if mk: L.append(f"Рынок: ${mk['price_usd']:.6g} · mcap {mk.get('mcap') or mk.get('fdv')} · liq ${mk['liq_usd']:,.0f} · vol24 {mk.get('vol24')} · {mk['url']}")
    if cg: L.append(f"CoinGecko: rank {cg.get('rank')} · circ {cg.get('circ')} / max {cg.get('max')} · {cg.get('url')}")
    if rc: L.append(f"Rugcheck: mint={'ДА' if rc.get('mint_authority') else 'нет'} freeze={'ДА' if rc.get('freeze_authority') else 'нет'} top10={rc.get('top10_pct')}% LP lock={rc.get('lp_locked_pct')} · {rc.get('url')}")
    if d.get("headline"): L.append(f"Новость ({d.get('event')}): {d['headline']} {d.get('link','')}")
    if d.get("followed_by"): L.append("Подписались: " + ", ".join(d["followed_by"]))
    L.append(s.get("summary", ""))
    if s.get("green"): L.append("✅ " + "; ".join(s["green"]))
    if s.get("red"): L.append("⚠️ " + "; ".join(s["red"]))
    if s.get("unverified"): L.append("❔ не проверено: " + "; ".join(s["unverified"]))
    L.append("➡️ " + s.get("action", "")); L.append("Не финсовет.")
    return "\n".join(x for x in L if x)
def analyze(item):
    from .fmt import project_post
    d = enrich(item); s = score(d); txt = project_post(d, s)
    mk = d.get("market") or {}
    db.save_prediction(d["key"], d["name"], int(s["score"]), s["verdict"], mk.get("price_usd"), mk.get("mcap") or mk.get("fdv"), txt)
    return s, txt
