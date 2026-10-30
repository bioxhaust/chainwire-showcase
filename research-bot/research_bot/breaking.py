"""Breaking/security mode: hacks, exploits, exchange incidents. Clusters headlines from RSS + Google News + TG channels
by the entity they mention; a story confirmed by several independent sources gets posted fast, bypassing token scoring."""
import os, re, json, time, hashlib, datetime as dt
from .config import OPENAI_API_KEY, LLM_BASE_URL, LLM_MODEL
from .http import S
from . import db
from .discovery import news, tgchannels
MIN_SOURCES = int(os.getenv("BREAKING_MIN_SOURCES", "3"))
COOLDOWN_H = float(os.getenv("BREAKING_COOLDOWN_H", "24"))
MAX_AGE_H = float(os.getenv("BREAKING_MAX_AGE_H", "18"))
SEC = re.compile(r"\bhack|exploit|drain|breach|stolen|\bsteal|attack|compromis|outflow|withdrawals? (?:paused|halted|suspended)|halts? withdrawals|"
                 r"insolven|bank run|depeg|rug ?pull|phishing|lazarus|tradertraitor|"
                 r"взлом|взлома|хакер|эксплойт|эксплоит|слив|украл|похищ|дрейн|атак|вывод.{0,20}(?:приостанов|заморож)|депег|скам", re.I)
ALIAS = {"бинанс": "Binance", "байбит": "Bybit", "биржа okx": "OKX", "коинбейс": "Coinbase", "битгет": "Bitget", "гейт": "Gate"}
STOP = set("""the a an and of in on for to with as at by from is are was were be this that it its new live breaking update updates report reports
crypto cryptocurrency bitcoin btc ether ethereum eth market markets price hack hacked hacker hackers exploit attack billion million north korea korean
lazarus tradertraitor news says said how why what who when where after amid over into more fresh security fears record exchange exchanges
dex cex defi web3 world global billions millions today week weekly daily top big major first latest token tokens coin coins usd usdt usdc fbi sec doj us uk eu asia ai x telegram twitter tg rt""".split())
GN_SEC = news.GN + "crypto+(hack+OR+exploit+OR+breach+OR+drained+OR+%22withdrawals+paused%22)+when:1d"
def gather():
    arts = [a for a in news.fetch(max_age_h=MAX_AGE_H)]
    r = news.get(GN_SEC)
    if r is not None and r.ok:
        import xml.etree.ElementTree as ET, email.utils
        try:
            for it in ET.fromstring(r.content).iter("item"):
                arts.append({"source": "GN security", "title": news._text(it, "title"), "link": news._text(it, "link"),
                             "summary": news._text(it, "description")[:300], "ts": news._text(it, "pubDate")})
        except ET.ParseError: pass
    arts += tgchannels.fetch(max_age_h=MAX_AGE_H)
    return arts
def outlet(a):
    if a.get("tg"): return a["source"]
    m = re.search(r" - ([^-]{2,40})$", a["title"])  # Google News appends " - Outlet"
    return m.group(1).strip() if m else a["source"]
def entities(a):
    txt = f"{a['title']} {a.get('summary', '')[:300]}"
    out = set()
    for k, v in ALIAS.items():
        if k in txt.lower(): out.add(v)
    for w in re.findall(r"\$?\b[A-Z][A-Za-z0-9]{2,}\b", txt):
        w = w.lstrip("$")
        if w.lower() not in STOP and not w.isdigit(): out.add(w[0].upper() + w[1:] if not w.isupper() else w)
    return out
def amount(txt):
    m = re.search(r"\$\s?(\d+(?:[.,]\d+)?)\s?(b|bn|billion|m|mn|million|млрд|млн)", txt, re.I)
    if not m: return 0
    v = float(m.group(1).replace(",", ".")); return v * (1e9 if m.group(2).lower() in ("b", "bn", "billion", "млрд") else 1e6)
def clusters(arts):
    sec = [a for a in arts if SEC.search(a["title"] + " " + a.get("summary", "")[:300])]
    by = {}
    for a in sec:
        for e in entities(a): by.setdefault(e, []).append(a)
    res = []
    for e, L in by.items():
        outs = {outlet(a) for a in L}; tg = {a["source"] for a in L if a.get("tg")}
        amt = max((amount(a["title"] + " " + a.get("summary", "")) for a in L), default=0)
        score = len(outs) + 0.5 * len(tg) + (2 if amt >= 1e8 else 1 if amt >= 1e7 else 0)
        res.append({"entity": e, "arts": L, "sources": len(outs), "tg_channels": sorted(tg), "amount": amt, "score": score})
    res.sort(key=lambda c: -c["score"])
    # drop clusters that are mostly a subset of a higher one (e.g. "Binance" vs "TraderTraitor")
    keep = []
    for c in res:
        ids = {a["link"] for a in c["arts"]}
        if any(len(ids & {a["link"] for a in k["arts"]}) >= 0.6 * len(ids) for k in keep): continue
        keep.append(c)
    return keep
def write(c):
    arts = c["arts"][:14]
    prompt = (f"Breaking crypto security story about {c['entity']}. Using ONLY the reports below (do not invent numbers), write a short news article "
              "for a Telegram channel in English AND Russian: what happened (who, how much, when), cause → effect (why it matters for users, "
              "markets, related tokens), what readers should do now (practical: check exposure, withdrawals, beware of phishing/fake refund links). "
              "Mark unconfirmed claims as unconfirmed. Cite reports as [n]. Return ONLY JSON: "
              '{"title_en":str,"title_ru":str,"hook_en":str,"hook_ru":str,"en":str,"ru":str} (articles: 3-5 short paragraphs separated by \\n).\n\n' +
              "\n".join(f"[{i + 1}] ({a['source']}) {a['title']} — {a.get('summary', '')[:300]}" for i, a in enumerate(arts)))
    for _ in range(2):
        try:
            r = S.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=240,
                       json={"model": LLM_MODEL, "temperature": 0.2, "messages": [{"role": "user", "content": prompt}]})
            return json.loads(re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"], re.S).group(0))
        except Exception as e: print("[breaking] write failed:", e)
    return None
def post_for(c):
    from .fmt import Post, E, cut, _footer, link
    from . import telegraph as T
    arts = c["arts"][:14]; w = (write(c) if OPENAI_API_KEY else None) or {}
    stamp = f"{dt.datetime.now():%d.%m.%Y %H:%M}"
    src = [(cut(f"{a['source']}: {a['title']}", 120), a["link"]) for a in arts]
    pages = {}
    for lang in ("en", "ru"):
        meta = (f"Срочно · {stamp} МСК · источников: {c['sources']}" if lang == "ru" else f"Breaking · {stamp} MSK · {c['sources']} sources")
        body = w.get(lang) or "\n".join(f"{a['title']} [{i + 1}]" for i, a in enumerate(arts))
        pages[lang] = [T.p(T.i(meta))] + [T.p(x.strip()) for x in str(body).split("\n") if x.strip()] + _footer(src, lang)
    t_en = w.get("title_en") or f"{c['entity']}: security incident"; t_ru = w.get("title_ru") or f"{c['entity']}: инцидент безопасности"
    head = w.get("title_en") or f"{c['entity']} security incident"
    if not re.match(r"(?i)just in|breaking", head): head = "JUST IN: " + head
    A = [f"🚨 <b>{E(cut(head, 140))}</b>"]
    summ = "\n".join(x for x in [E(cut(w.get("hook_en") or "", 220)), E(cut(w.get("hook_ru") or "", 220))] if x)
    if summ: A.append(summ)
    A.append("#breaking")
    o = Post("\n\n".join(A), t_en, pages["en"], pages["ru"], t_ru)
    hru = t_ru if re.match(r"(?i)срочно", t_ru) else "СРОЧНО: " + t_ru
    from .fmt import mono
    o.ann = {"en": mono("🚨", head, w.get("hook_en"), "#breaking"), "ru": mono("🚨", hru, w.get("hook_ru"), "#срочно")}
    return o
def scan(post=None, dry=False, arts=None):
    post = post or (lambda t, meta=None: print(t))
    cs = clusters(arts if arts is not None else gather()); n = 0
    for c in cs[:5]:
        print(f"[breaking] {c['entity']}: {c['sources']} sources, tg={len(c['tg_channels'])}, ${c['amount']:.0f}, score {c['score']:.1f}")
    for c in cs:
        if c["sources"] < MIN_SOURCES: break
        last = float(db.kv_get(f"breaking:{db.pkey(c['entity'])}", 0) or 0)
        if time.time() - last < COOLDOWN_H * 3600: print(f"[breaking] {c['entity']}: already posted recently"); continue
        post(post_for(c), {"name": c["entity"], "mode": "breaking"})
        if not dry: db.kv_set(f"breaking:{db.pkey(c['entity'])}", time.time())
        n += 1
        if n >= 2: break
    return n
