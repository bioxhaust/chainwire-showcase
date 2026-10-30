"""News worker: free RSS -> LLM extraction (projects/tickers/event) -> dedupe -> items for enrichment + digest."""
import json, re, hashlib, html, datetime as dt, email.utils
import xml.etree.ElementTree as ET
from ..http import get, S
from ..config import OPENAI_API_KEY, LLM_BASE_URL, LLM_MODEL
from .. import db
GN = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="
FEEDS = {
    "The Block": "https://www.theblock.co/rss.xml", "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Decrypt": "https://decrypt.co/feed", "Cointelegraph": "https://cointelegraph.com/rss", "The Defiant": "https://thedefiant.io/api/feed",
    "Blockworks": GN + "site:blockworks.co+when:2d",
    "GN airdrop/points": GN + "crypto+(airdrop+OR+%22points+program%22+OR+%22season+1%22)+when:2d",
    "GN testnet/TGE": GN + "crypto+(testnet+OR+TGE+OR+%22token+launch%22+OR+mainnet)+when:2d",
    "GN raises": GN + "crypto+(raises+OR+%22seed+round%22+OR+%22series+A%22)+when:2d",
}
EVENTS = ["airdrop", "points", "testnet", "mainnet", "tge", "listing", "raise", "hack", "unlock", "other"]
def _text(e, tag):
    x = e.find(tag); return html.unescape(re.sub("<[^>]+>", " ", x.text or "")).strip() if x is not None and x.text else ""
def fetch(max_age_h=36):
    out, now = [], dt.datetime.now(dt.timezone.utc)
    for src, url in FEEDS.items():
        r = get(url)
        if r is None or not r.ok: print(f"[news] {src} fail"); continue
        try: root = ET.fromstring(r.content)
        except ET.ParseError: continue
        for it in root.iter("item"):
            t, link = _text(it, "title"), _text(it, "link")
            try: ts = email.utils.parsedate_to_datetime(_text(it, "pubDate"))
            except Exception: ts = now
            if (now - ts).total_seconds() > max_age_h * 3600: continue
            out.append({"source": src, "title": t, "link": link, "summary": _text(it, "description")[:300], "ts": ts.isoformat()})
    try:
        from . import tgchannels; out += tgchannels.fetch(max_age_h)
    except Exception as e: print("[news] tg channels error", e)
    seen, res = set(), []
    for a in out:  # dedupe across feeds by normalized title
        k = re.sub(r"\W+", "", a["title"].lower())[:80]
        if k not in seen: seen.add(k); res.append(a)
    return res
KW = re.compile(r"взлом|эксплойт|аирдроп|дроп|тестнет|поинт|airdrop|points|testnet|mainnet|TGE|token launch|launch|raises|raised|funding|seed|series [a-c]|listing|lists|unlock|hack|exploit", re.I)
def llm_extract(arts):
    """Batch extraction with LLM; returns list of {i, projects:[{name,ticker}], event, importance 1-5}."""
    prompt = ("Extract crypto projects from headlines. For each headline index return JSON list items "
              '{"i":int,"projects":[{"name":str,"ticker":str|null}],"event":one of ' + json.dumps(EVENTS) +
              ',"importance":1-5}. Skip macro/BTC-price/regulation-only news (projects=[]). importance 5 = new airdrop/points/testnet/TGE of a promising project, big raise, or a major hack/exploit/exchange incident (event=hack). Headlines prefixed [TG @...] are Telegram channel posts (often Russian). Return ONLY the JSON list.\n\n' +
              "\n".join(f"{i}. [{a['source']}] {a['title']} — {a['summary'][:160]}" for i, a in enumerate(arts)))
    r = S.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=180,
               json={"model": LLM_MODEL, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
    j = r.json()
    if "choices" not in j: raise RuntimeError(str(j)[:200])
    return json.loads(re.search(r"\[.*\]", j["choices"][0]["message"]["content"], re.S).group(0))
def rule_extract(arts):
    res = []
    for i, a in enumerate(arts):
        m = KW.search(a["title"])
        if not m: continue
        ev = next((e for e in EVENTS if e in m.group(0).lower()), "raise" if re.search("rais|fund|seed|series", m.group(0), re.I) else "other")
        tick = re.findall(r"\$([A-Z]{2,10})\b", a["title"]) or re.findall(r"\(([A-Z]{2,10})\)", a["title"]); name = re.match(r"([A-Z][\w.]+(?: [A-Z][\w.]+)?)", a["title"])
        res.append({"i": i, "projects": [{"name": name.group(1) if name else a["title"][:30], "ticker": tick[0] if tick else None}], "event": ev, "importance": 3})
    return res
def discover(limit=40):
    arts = [a for a in fetch() if db.is_new("news:" + hashlib.md5(a["link"].encode()).hexdigest(), "news", a["title"][:200], a)]
    if not arts: return [], []
    ext = []
    for k in range(0, min(len(arts), limit), 20):
        chunk = arts[k:k + 20]
        e = None
        for attempt in range(2 if OPENAI_API_KEY else 0):
            try: e = llm_extract(chunk); break
            except Exception as ex: print("[news] LLM extract failed:", ex)
        if e is None: e = rule_extract(chunk)
        for x in e:
            if isinstance(x, dict) and isinstance(x.get("i"), int) and 0 <= x["i"] < len(chunk): x["i"] += k; ext.append(x)
    digest, items = [], []
    for x in ext:
        a = arts[x["i"]]; ps = [p for p in x.get("projects") or [] if p.get("name")]
        if not ps: continue
        digest.append({**a, "event": x.get("event"), "importance": int(x.get("importance") or 1), "projects": ps})
        if int(x.get("importance") or 1) >= 3:
            for p in ps[:2]:
                key = f"proj:{re.sub(r'\\W+', '', p['name'].lower())}"
                if db.is_new(key, "news-project", p["name"], a):
                    items.append({"kind": "news", "key": key, "name": p.get("ticker") or p["name"], "project": p["name"], "event": x.get("event"),
                                  "headline": a["title"], "link": a["link"], "priority": int(x.get("importance") or 1)})
    from collections import Counter
    cnt = Counter(re.sub(r"\W+", "", p["name"].lower()) for d in digest for p in d["projects"][:1])
    for d in digest:
        if cnt[re.sub(r"\W+", "", d["projects"][0]["name"].lower())] >= 3: d["importance"] += 1
    digest.sort(key=lambda d: -d["importance"]); items.sort(key=lambda d: -d["priority"])
    return digest, items
EMO = {"airdrop": "🪂", "points": "🎯", "testnet": "🧪", "mainnet": "🚀", "tge": "🪙", "listing": "📈", "raise": "💰", "hack": "🔓", "unlock": "🔑"}
def format_digest(digest, n=12):
    if not digest: return ""
    L = [f"🗞 Крипто-новости {dt.datetime.now():%d.%m %H:%M} (МСК)"]
    for d in digest[:n]:
        L.append(f"{EMO.get(d['event'], '•')} {d['title']} — {d['source']}\n{d['link']}")
    return "\n".join(L)

def write_digest(items):
    """Bilingual own-words retelling per headline. Returns {i: {en, ru, take_en, take_ru}}."""
    if not items or not OPENAI_API_KEY: return {}
    prompt = ("Ты пишешь обзор крипто-новостей для канала. Для каждой новости ниже напиши своими словами пересказ в 1-2 предложения (что произошло, кто, цифры — "
              "ТОЛЬКО из заголовка и описания, ничего не выдумывай) и короткий вывод (1 предложение: к чему это ведёт / что делать фармеру или холдеру). "
              'На английском и русском. Верни ТОЛЬКО JSON-список: [{"i":int,"head_en":"short punchy headline, newswire style","head_ru":"то же по-русски","en":str,"take_en":str,"ru":str,"take_ru":str}].\n\n' +
              "\n".join(f"{i}. [{a.get('source')}] {a['title']} — {str(a.get('summary') or '')[:300]}" for i, a in enumerate(items)))
    for _ in range(2):
        try:
            r = S.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=240,
                       json={"model": LLM_MODEL, "temperature": 0.2, "messages": [{"role": "user", "content": prompt}]})
            L = json.loads(re.search(r"\[.*\]", r.json()["choices"][0]["message"]["content"], re.S).group(0))
            return {x["i"]: x for x in L if isinstance(x, dict) and isinstance(x.get("i"), int)}
        except Exception as e: print("[digest] write failed:", e)
    return {}
