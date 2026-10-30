"""Live fund stats: DefiLlama raises (public page data, free) x token existence (DefiLlama protocols + CoinGecko list).
Refresh daily -> data/funds_2026.csv, data/raises_cache.json."""
import csv, json, re, time, datetime as dt
from .config import DATA
from .http import get, jget
from . import db

ALIASES = {"a16z": "a16z crypto", "binance": "binance labs", "polychain": "polychain capital", "multicoin": "multicoin capital",
           "pantera": "pantera capital", "jump": "jump crypto", "variant": "variant fund", "sequoia": "sequoia capital",
           "paradigm": "paradigm", "coinbase ventures": "coinbase ventures", "blockchain capital": "blockchain capital"}
def norm(s): return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
FUND_SYNONYMS = {"binance labs": ["binance labs", "yzi labs", "binance"], "jump crypto": ["jump crypto", "jump trading", "jump capital"],
                 "a16z crypto": ["a16z crypto", "a16z", "andreessen horowitz", "a16z crypto speedrun"]}

def target_funds():
    """funds.csv table2 + vc_database_2022 top-tier (rank<=25) -> {canonical: tier_info}"""
    out = {}
    rows = list(csv.reader(open(DATA / "funds.csv", encoding="utf-8")))
    for r in rows[1:]:
        if len(r) > 15 and r[12].strip() and r[13].strip().isdigit():
            out[ALIASES.get(r[12].strip().lower(), r[12].strip().lower())] = {"src": "funds.csv", "old_total": r[13], "old_airdrop": r[14], "old_pct": r[15]}
    try:
        vr = list(csv.DictReader(open(DATA / "vc_database_2022.csv", encoding="utf-8")))
        namecol = next(k for k in vr[0] if any((x.get(k) or "") == "Paradigm" for x in vr))
        for x in vr:
            rk = (x.get("🏅 Rank") or "").strip()
            if rk.isdigit() and int(rk) <= 25:
                n = x[namecol].strip().lower(); n = ALIASES.get(n, n)
                out.setdefault(n, {"src": "vc_database_2022"})["vc2022_rank"] = rk
    except Exception as e:
        print("vc_db parse:", e)
    return out

def fetch_raises():
    r = get("https://defillama.com/raises")
    m = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', r.text) if r is not None else None
    if not m:
        j = jget("https://api.llama.fi/raises")  # paid since 2025 (402) but try anyway
        return (j or {}).get("raises", [])
    return json.loads(m.group(1))["props"]["pageProps"]["raises"]

def token_index():
    names = set()
    for p in jget("https://api.llama.fi/protocols") or []:
        if p.get("gecko_id") or (p.get("symbol") and p["symbol"] != "-"):
            names.add(norm(p["name"]))
    for c in jget("https://api.coingecko.com/api/v3/coins/list") or []:
        names.add(norm(c["name"]))
    return names

def investor_match(inv, fund):
    i = norm(inv); syns = [norm(s) for s in FUND_SYNONYMS.get(fund, [fund])]
    return any(i == s or i.startswith(s + " ") for s in syns)

def refresh(since="2024-01-01"):
    raises = fetch_raises()
    if not raises: raise RuntimeError("no raises data")
    json.dump(raises, open(DATA / "raises_cache.json", "w"))
    tokens = token_index()
    t0 = dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp()
    recent = [x for x in raises if x["date"] >= t0]
    freshest = dt.datetime.fromtimestamp(max(x["date"] for x in raises), dt.timezone.utc).date().isoformat()
    funds = target_funds(); rows = []
    for f, info in funds.items():
        deals = [x for x in recent if any(investor_match(i, f) for i in x["leadInvestors"] + x["otherInvestors"])]
        projs = {}
        for d in deals: projs.setdefault(d["name"], d)
        tge = [n for n in projs if norm(n) in tokens]
        tokenless = sorted(projs.values(), key=lambda d: -d["date"])
        tokenless = [f'{d["name"]} ({d["round"] or "?"}, {dt.datetime.fromtimestamp(d["date"], dt.timezone.utc):%Y-%m}, {d.get("category") or ""})' for d in tokenless if norm(d["name"]) not in tokens]
        rows.append({"fund": f, "source_list": info.get("src"), "vc2022_rank": info.get("vc2022_rank", ""),
                     "old_total_deals": info.get("old_total", ""), "old_airdrop_pct": info.get("old_pct", ""),
                     "deals_2024_2026": len(deals), "unique_projects": len(projs), "projects_with_token": len(tge),
                     "pct_with_token": round(100 * len(tge) / len(projs), 1) if projs else 0,
                     "tokenless_count": len(tokenless), "tokenless_latest": "; ".join(tokenless[:25]),
                     "freshest_record": freshest})
    rows.sort(key=lambda r: -r["unique_projects"])
    with open(DATA / "funds_2026.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    db.kv_set("funds_refreshed", int(time.time())); db.kv_set("raises_freshest", freshest)
    return rows, freshest, len(recent)

def refresh_if_stale(hours=24):
    last = int(db.kv_get("funds_refreshed", 0))
    if time.time() - last > hours * 3600 or not (DATA / "funds_2026.csv").exists():
        return refresh()

def fund_tiers():
    """fund name -> weight for prioritizing rounds."""
    t = {}
    p = DATA / "funds_2026.csv"
    if p.exists():
        for r in csv.DictReader(open(p, encoding="utf-8")):
            t[r["fund"]] = 3 if r["source_list"] == "funds.csv" else 2
    return t
