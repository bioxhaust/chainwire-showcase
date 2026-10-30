"""Accuracy tracking: fill price_7d/price_30d for past predictions."""
import time
from . import db
from .enrich import market
def update():
    c = db.conn(); now = time.time(); n = 0
    for pid, key, ts, p7, p30 in c.execute("select id,key,ts,price_7d,price_30d from predictions where price_usd is not null").fetchall():
        col = "price_7d" if p7 is None and now - ts > 7 * 86400 else "price_30d" if p30 is None and now - ts > 30 * 86400 else None
        if not col or not key.startswith("sol:"): continue
        m = market.dexscreener(mint=key[4:])
        if m: c.execute(f"update predictions set {col}=?, checked_ts=? where id=?", (m["price_usd"], int(now), pid)); n += 1
    c.commit(); return n
def stats():
    rows = db.conn().execute("select verdict, count(*), avg(case when price_7d is not null then price_7d/price_usd-1 end) from predictions group by verdict").fetchall()
    return "\n".join(f"{v}: {n} прогнозов, средн. 7д {('%+.0f%%' % (r*100)) if r is not None else 'н/д'}" for v, n, r in rows) or "пока пусто"
