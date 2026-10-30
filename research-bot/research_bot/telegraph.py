"""Telegraph publishing. Token stored in data/bot.sqlite kv table ('telegraph_token')."""
import json
from .http import S
from . import db
API = "https://api.telegra.ph"
def token():
    t = db.kv_get("telegraph_token")
    if t: return t
    r = S.post(f"{API}/createAccount", data={"short_name": "DropSearch", "author_name": "DropSearch", "author_url": "https://t.me/DropSearch"}, timeout=30).json()
    if not r.get("ok"): raise RuntimeError(f"telegraph createAccount: {r}")
    db.kv_set("telegraph_token", r["result"]["access_token"]); return r["result"]["access_token"]
def _call(method, title, nodes):
    r = S.post(f"{API}/{method}", timeout=60, data={"access_token": token(), "title": title[:256], "author_name": "DropSearch",
               "author_url": "https://t.me/DropSearch", "content": json.dumps(nodes, ensure_ascii=False)}).json()
    if not r.get("ok"): raise RuntimeError(f"telegraph {method}: {r}")
    return r["result"]
def publish(title, nodes): return _call("createPage", title, nodes)["url"]
def publish_pair(title_en, en, title_ru, ru):
    """EN page first, RU page links back, then EN is edited to link to RU. Returns (en_url, ru_url)."""
    first = _call("createPage", title_en, en)
    ru_url = _call("createPage", title_ru, [p(a(first["url"], "English version →"))] + ru)["url"]
    _call(f"editPage/{first['path']}", title_en, [p(a(ru_url, "Русская версия →"))] + en)
    return first["url"], ru_url
# node helpers
def p(*c): return {"tag": "p", "children": [x for x in c if x != ""]}
def h(t, lvl=3): return {"tag": f"h{lvl}", "children": [t]}
def b(t): return {"tag": "b", "children": [t]}
def i(t): return {"tag": "i", "children": [t]}
def a(url, t): return {"tag": "a", "attrs": {"href": url}, "children": [t]}
def ul(items, tag="ul"): return {"tag": tag, "children": [{"tag": "li", "children": x if isinstance(x, list) else [x]} for x in items]}
HR = {"tag": "hr"}
