"""New Solana pools (sol-tracker logic: new pools -> filter liquidity/age -> rugcheck in enrich). GeckoTerminal + DexScreener profiles, free."""
from ..http import jget
from .. import db
MIN_LIQ = 20000
def discover(limit=10):
    out = []
    j = jget("https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1") or {}
    for p in j.get("data", []):
        a = p["attributes"]; liq = float(a.get("reserve_in_usd") or 0)
        if liq < MIN_LIQ: continue
        mint = p["relationships"]["base_token"]["data"]["id"].split("_", 1)[-1]
        out.append({"kind": "pool", "key": f"sol:{mint}", "name": a["name"].split(" / ")[0], "mint": mint, "liq": liq,
                    "pool": a["address"], "created": a.get("pool_created_at"), "priority": liq / 1e5})
    for t in (jget("https://api.dexscreener.com/token-boosts/latest/v1") or [])[:30]:
        if t.get("chainId") == "solana":
            out.append({"kind": "pool", "key": f"sol:{t['tokenAddress']}", "name": t.get("description", "")[:30] or t["tokenAddress"][:6],
                        "mint": t["tokenAddress"], "priority": 0.5, "note": "paid dexscreener boost"})
    seen = set(); res = []
    for x in sorted(out, key=lambda x: -x["priority"]):
        if x["key"] in seen: continue
        seen.add(x["key"])
        if db.is_new(x["key"], "pool", x["name"], x): res.append(x)
    return res[:limit]
