import sqlite3, json, time
from .config import DB_PATH
SCHEMA = """
create table if not exists seen(key text primary key, kind text, name text, first_seen int, payload text);
create table if not exists predictions(id integer primary key, key text, name text, ts int, score int, verdict text,
  price_usd real, mcap real, report text, price_7d real, price_30d real, checked_ts int);
create table if not exists posts(pkey text, name text, mode text, posted_at int, deadline_sig text);
create table if not exists kv(k text primary key, v text);
"""
def conn():
    c = sqlite3.connect(DB_PATH); c.executescript(SCHEMA)
    cols = [r[1] for r in c.execute("pragma table_info(posts)")]
    for col in ("telegraph_url", "telegraph_url_ru"):
        if col not in cols: c.execute(f"alter table posts add column {col} text"); c.commit()
    return c
def is_new(key, kind, name, payload=None):
    c = conn()
    if c.execute("select 1 from seen where key=?", (key,)).fetchone(): return False
    c.execute("insert into seen values(?,?,?,?,?)", (key, kind, name, int(time.time()), json.dumps(payload or {}, default=str)[:20000]))
    c.commit(); return True
def save_prediction(key, name, score, verdict, price, mcap, report):
    c = conn(); c.execute("insert into predictions(key,name,ts,score,verdict,price_usd,mcap,report) values(?,?,?,?,?,?,?,?)",
        (key, name, int(time.time()), score, verdict, price, mcap, report)); c.commit()
def kv_get(k, d=None):
    r = conn().execute("select v from kv where k=?", (k,)).fetchone(); return r[0] if r else d
def kv_set(k, v):
    c = conn(); c.execute("insert or replace into kv values(?,?)", (k, str(v))); c.commit()

import re as _re
def pkey(name): return _re.sub(r"\W+", "", str(name or "").lower())
def last_post(name):
    return conn().execute("select mode, posted_at, deadline_sig from posts where pkey=? order by posted_at desc limit 1", (pkey(name),)).fetchone()
def record_post(name, mode, deadline_sig="", urls=None):
    urls = urls or (None, None)
    c = conn(); c.execute("insert into posts(pkey,name,mode,posted_at,deadline_sig,telegraph_url,telegraph_url_ru) values(?,?,?,?,?,?,?)",
                          (pkey(name), name, mode, int(time.time()), deadline_sig or "", urls[0], urls[1])); c.commit()
