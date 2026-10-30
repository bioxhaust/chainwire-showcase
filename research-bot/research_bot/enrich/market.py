from ..http import jget
def dexscreener(query=None, mint=None, strict=False):
    if mint:
        j = jget(f"https://api.dexscreener.com/latest/dex/tokens/{mint}") or {}
    else:
        j = jget(f"https://api.dexscreener.com/latest/dex/search?q={query}") or {}
    pairs = [p for p in (j.get("pairs") or []) if p.get("liquidity", {}).get("usd")]
    if query:
        ex = [p for p in pairs if p["baseToken"]["symbol"].lower() == query.lower().lstrip("$")]
        ex = ex or [p for p in pairs if p["baseToken"]["name"].lower() == query.lower()]
        pairs = ex if (ex or strict) else pairs
    if not pairs: return None
    pairs.sort(key=lambda p: -p["liquidity"]["usd"]); p = pairs[0]
    return {"chain": p["chainId"], "dex": p["dexId"], "pair": p["pairAddress"], "token": p["baseToken"], "price_usd": float(p.get("priceUsd") or 0),
            "liq_usd": p["liquidity"]["usd"], "fdv": p.get("fdv"), "mcap": p.get("marketCap"), "vol24": p.get("volume", {}).get("h24"),
            "chg24": p.get("priceChange", {}).get("h24"), "created": p.get("pairCreatedAt"), "socials": (p.get("info") or {}).get("socials"),
            "websites": (p.get("info") or {}).get("websites"), "url": p.get("url"),
            "alt_contracts_same_ticker": len({x["baseToken"]["address"] for x in pairs if x["baseToken"]["symbol"].lower() == p["baseToken"]["symbol"].lower()})}
def coingecko(name):
    s = jget(f"https://api.coingecko.com/api/v3/search?query={name}") or {}
    coins = s.get("coins") or []
    if not coins: return None
    c = jget(f"https://api.coingecko.com/api/v3/coins/{coins[0]['id']}?localization=false&tickers=false&community_data=false&developer_data=false") or {}
    md = c.get("market_data") or {}
    return {"id": c.get("id"), "symbol": c.get("symbol"), "rank": c.get("market_cap_rank"), "price": (md.get("current_price") or {}).get("usd"),
            "mcap": (md.get("market_cap") or {}).get("usd"), "fdv": (md.get("fully_diluted_valuation") or {}).get("usd"),
            "circ": md.get("circulating_supply"), "total": md.get("total_supply"), "max": md.get("max_supply"),
            "ath_chg_pct": (md.get("ath_change_percentage") or {}).get("usd"), "categories": c.get("categories"),
            "twitter": (c.get("links") or {}).get("twitter_screen_name"), "url": f"https://www.coingecko.com/en/coins/{c.get('id')}"}
