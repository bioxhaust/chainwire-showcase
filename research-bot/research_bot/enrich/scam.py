from ..http import jget
def rugcheck(mint):
    j = jget(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report")
    if not j: return None
    holders = j.get("topHolders") or []
    top10 = sum(h.get("pct", 0) for h in holders[:10])
    markets = j.get("markets") or []
    lp_locked = max((m.get("lp", {}).get("lpLockedPct", 0) for m in markets), default=None)
    return {"score_norm": j.get("score_normalised"), "risks": [f"{r['name']} ({r.get('level')})" for r in j.get("risks", [])],
            "mint_authority": j.get("mintAuthority"), "freeze_authority": j.get("freezeAuthority"), "top10_pct": round(top10, 1),
            "lp_locked_pct": lp_locked, "creator": j.get("creator"), "rugged": j.get("rugged"), "insiders_detected": j.get("graphInsidersDetected"),
            "url": f"https://rugcheck.xyz/tokens/{mint}"}
