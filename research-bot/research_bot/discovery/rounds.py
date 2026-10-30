"""New fundraising rounds: DefiLlama raises (free page data); RootData/CryptoRank if API keys set."""
import json, datetime as dt
from ..config import DATA, ROOTDATA_API_KEY, CRYPTORANK_API_KEY
from .. import funds, db
from ..http import S
def discover(days=7, limit=15):
    raises = funds.fetch_raises()
    tiers = funds.fund_tiers()
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - days * 86400
    out = []
    for r in raises:
        if r["date"] < cutoff: continue
        invs = r["leadInvestors"] + r["otherInvestors"]
        w = sum(max((v for f, v in tiers.items() if funds.investor_match(i, f)), default=0) for i in invs)
        key = f"raise:{r['name']}:{r['date']}"
        out.append({"kind": "round", "key": key, "name": r["name"], "priority": w + 2 * sum(1 for i in r["leadInvestors"] if any(funds.investor_match(i, f) for f in tiers)),
                    "round": r["round"], "amount": r.get("amountUsd"), "date": dt.datetime.fromtimestamp(r["date"], dt.timezone.utc).date().isoformat(),
                    "investors": invs, "category": r.get("category"), "chains": r.get("chains")})
    out.sort(key=lambda x: (-x["priority"], -(x["amount"] or 0)))
    if ROOTDATA_API_KEY:
        try:
            j = S.post("https://api.rootdata.com/open/get_fac", headers={"apikey": ROOTDATA_API_KEY, "language": "en"}, json={"page": 1, "page_size": 50}, timeout=30).json()
            for it in (j.get("data") or {}).get("items", []):
                out.append({"kind": "round", "key": f"rootdata:{it.get('project_id')}:{it.get('published_time')}", "name": it.get("name"), "priority": 1,
                            "round": it.get("rounds"), "amount": it.get("amount"), "investors": [x.get("name") for x in it.get("invests", [])]})
        except Exception as e: print("rootdata:", e)
    return [x for x in out if db.is_new(x["key"], "round", x["name"], x)][:limit]
