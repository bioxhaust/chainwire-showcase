"""Telegram HTML formatting for DropSearch posts."""
import html, datetime as dt
E = lambda s: html.escape(str(s or ""), quote=True)
VERD = {"farm": ("🌾", "ФАРМ"), "enter": ("🟢", "ВХОД"), "watch": ("👀", "НАБЛЮДАТЬ"), "scam": ("🚫", "СКАМ")}
EV = {"airdrop": ("🪂", "Аирдропы"), "points": ("🎯", "Поинты"), "testnet": ("🧪", "Тестнеты"), "mainnet": ("🚀", "Мейннеты и запуски"),
      "tge": ("🪙", "TGE"), "listing": ("📈", "Листинги"), "raise": ("💰", "Раунды"), "hack": ("🔓", "Взломы"), "unlock": ("🔑", "Анлоки"), "other": ("📌", "Другое")}
def money(x):
    if x is None: return "н/д"
    x = float(x)
    for d, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= d: return f"${x/d:.1f}{s}"
    return f"${x:.2f}" if x >= 0.01 else f"${x:.3g}"
def bar(score):
    n = round(max(0, min(100, score)) / 10)
    c = "🟩" if score >= 66 else "🟨" if score >= 46 else "🟧" if score >= 21 else "🟥"
    return c * n + "⬜" * (10 - n) + f" <b>{int(score)}</b>/100"
def link(url, text): return f'<a href="{E(url)}">{E(text)}</a>' if url else ""
def cut(s, n):
    s = str(s or "").strip()
    if len(s) <= n: return s
    t = s[:n]; i = max(t.rfind(". "), t.rfind("; "))
    return t[:i + 1] if i > n * 0.5 else t[:n - 1].rstrip() + "…"
class Post(str):
    """Channel announcement + EN/RU Telegraph page specs; published by the sender."""
    def __new__(cls, text, title, en, ru, title_ru=None):
        o = super().__new__(cls, text); o.title, o.en, o.ru, o.title_ru = title, en, ru, title_ru or title; return o
    def publish(self):
        from .publisher import publish_pair
        self.urls = publish_pair(self.title, self.en, self.title_ru, self.ru); return str(self), self.urls
def with_links(text, urls):
    """No inline buttons: article links as clickable text at the bottom (before the source line if present)."""
    L = " · ".join(x for x in [link(urls[0], "📖 Read in English") if urls and urls[0] else "", link(urls[1], "📖 Читать на русском") if urls and len(urls) > 1 and urls[1] else ""] if x)
    return f"{text}\n\n{L}" if L else text
def lang_links(urls, lang):
    if not urls: return ""
    en, ru = link(urls[0], "📖 Read in English"), link(urls[1], "📖 Читать на русском") if len(urls) > 1 else ""
    return " · ".join(x for x in ([ru, en] if lang == "ru" else [en, ru]) if x)
def mono(emo, head, summ, tag=""):
    return "\n\n".join(x for x in [f"{emo} <b>{E(cut(head, 140))}</b>", E(cut(summ or "", 300)), tag] if x)
def buttons(urls):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[InlineKeyboardButton("🇬🇧 English", url=urls[0]), InlineKeyboardButton("🇷🇺 Русский", url=urls[1])]])
import re as _re
from . import telegraph as T
def _strip(h): return html.unescape(_re.sub(r"<[^>]+>", "", h or ""))
def _ticker(d):
    mk, cg = d.get("market") or {}, d.get("coingecko") or {}
    name = d.get("project") or d.get("name")
    return name, ((mk.get("token") or {}).get("symbol") or (cg.get("symbol") or "").upper() or (d["name"] if d.get("name") != name else "")).lstrip("$")
def sources(d):
    mk, rc, cg = d.get("market") or {}, d.get("rugcheck") or {}, d.get("coingecko") or {}
    L = [(d.get("headline") or "Новость / News", d.get("link"))]
    for x in (d.get("hot") or {}).get("deadlines") or []: L.append((x.get("what") or x.get("type") or "Срок", x.get("link")))
    xh = (d.get("x") or {}).get("handle") or d.get("handle") or cg.get("twitter") or next((x.get("url") for x in mk.get("socials") or [] if x.get("type") == "twitter"), None)
    L += [("DexScreener", mk.get("url")), ("Rugcheck", rc.get("url")), ("X", (xh if str(xh).startswith("http") else f"https://x.com/{xh}") if xh else None),
          ("Сайт / Website", next((w.get("url") for w in mk.get("websites") or []), None)), ("CoinGecko", cg.get("url"))]
    seen, out = set(), []
    for t, u in L:
        if u and u not in seen: seen.add(u); out.append((cut(t, 120), u))
    return out
def _facts(d, lang):
    """Fallback article from data only (when LLM gave no article)."""
    ru = lang == "ru"; mk = d.get("market") or {}; name, _ = _ticker(d); S_ = []
    if d.get("headline"): S_.append((f"Повод: новость «{d['headline']}» [1]." if ru else f"Trigger: news report “{d['headline']}” [1]."))
    if d.get("investors") or d.get("kind") == "round":
        inv = ", ".join((d.get("investors") or [])[:6]) or ("не указаны" if ru else "not specified")
        S_.append((f"{name} привлёк раунд {d.get('round') or ''} на {money(d.get('amount')) if d.get('amount') else 'нераскрытую сумму'}; инвесторы: {inv}." if ru else
                   f"{name} raised a {d.get('round') or ''} round of {money(d.get('amount')) if d.get('amount') else 'undisclosed size'}; investors: {inv}."))
    if mk: S_.append((f"Токен торгуется по {money(mk.get('price_usd'))}, капитализация {money(mk.get('mcap') or mk.get('fdv'))}, ликвидность {money(mk.get('liq_usd'))} ({mk.get('chain')})." if ru else
                      f"The token trades at {money(mk.get('price_usd'))}, market cap {money(mk.get('mcap') or mk.get('fdv'))}, liquidity {money(mk.get('liq_usd'))} ({mk.get('chain')})."))
    else: S_.append("Рыночных данных по токену нет — вероятно, токена ещё нет." if ru else "No market data for a token — likely not launched yet.")
    return " ".join(S_)
LBL = {"en": ("What it means", "Risks", "What to do", "Deadlines", "Interest", "Unverified", "Sources", "Not financial advice."),
       "ru": ("Что это значит", "Риски", "Что делать", "Сроки", "Интерес", "Не проверено", "Источники", "Не финансовый совет.")}
VERD_EN = {"farm": "Farm", "enter": "Enter", "watch": "Watch", "scam": "Scam"}
VERD_RU = {"farm": "Фарм", "enter": "Вход", "watch": "Наблюдать", "scam": "Скам"}
def _footer(src, lang):
    L = LBL[lang]; N = []
    if src: N += [T.h(L[6], 3), T.ul([[T.a(u, t)] for t, u in src], "ol")]
    return N + [T.p(T.i(L[7] + " "), T.a("https://t.me/DropSearch", "@DropSearch"))]
def _page(d, s, lang, marker, src):
    ru = lang == "ru"; v = s.get(lang) if isinstance(s.get(lang), dict) else {}; L = LBL[lang]
    vk = s.get("verdict"); verd = (VERD_RU if ru else VERD_EN).get(vk, str(vk))
    meta = f"{verd} · {int(s.get('score', 0))}/100 · {dt.date.today():%d.%m.%Y}"
    if marker: meta = ("Актуально сейчас · " if ru else "Hot now · ") + meta
    N = [T.p(T.i(meta))]
    art = v.get("article") or ((s.get("summary") + "\n\n") if ru and s.get("summary") and s.get("engine") == "llm" else "") + _facts(d, lang)
    N += [T.p(x.strip()) for x in str(art).split("\n") if x.strip()]
    hot = d.get("hot") or {}
    if hot.get("deadlines"):
        N += [T.h(L[3], 3), T.ul([f"{x.get('date') or ('дата не указана' if ru else 'date n/a')} — {x.get('what') or x.get('type')}" for x in hot["deadlines"][:5]]),
              T.p(T.i((f"{hot.get('mentions_7d')} упоминаний за 7 дней, тренд {hot.get('trend')}, срочность {hot.get('urgency')}/100") if ru else
                       f"{hot.get('mentions_7d')} mentions in 7 days, trend {hot.get('trend')}, urgency {hot.get('urgency')}/100"))]
    an = v.get("analysis") or (s.get("green") if ru else [])
    if an: N += [T.h(L[0], 3), T.ul([str(x) for x in an[:4]])]
    rk = v.get("risks") or (s.get("red") if ru else [])
    if rk: N += [T.h(L[1], 3), T.ul([str(x) for x in rk[:4]])]
    act = v.get("action") or (s.get("action") if ru else "Manual check against the checklist.")
    if act: N += [T.h(L[2], 3), T.p(str(act))]
    if s.get("unverified"): N.append(T.p(T.i(f"{L[5]}: " + "; ".join(map(str, s["unverified"][:5])))))
    return N + _footer(src, lang)
def project_post(d, s, marker=None, extra=None):
    name, tick = _ticker(d)
    vk = s.get("verdict"); emo, vtxt = VERD.get(vk, ("•", str(vk).upper())); sc = int(s.get("score", 0))
    title = f"{name}" + (f" (${tick})" if tick and tick.lower() != str(name).lower() else "")
    src = sources(d)
    en, ru = _page(d, s, "en", marker, src), _page(d, s, "ru", marker, src)
    hk = s.get("hook") if isinstance(s.get("hook"), dict) else {}
    ru_h = hk.get("ru") or cut(s.get("summary") or "", 140); en_h = hk.get("en") or ""
    A = [f"{emo} <b>{E(name)}</b>" + (f" · ${E(tick)}" if tick else "") + f" · <i>{vtxt}</i>", bar(sc)]
    if marker: A.insert(0, marker)
    hooks = ([f"🇷🇺 {E(cut(ru_h, 160))}"] if ru_h else []) + ([f"🇬🇧 {E(cut(en_h, 160))}"] if en_h else [])
    if hooks: A.append("\n".join(hooks))
    mk = d.get("market") or {}
    tags = {d.get("event"), {"round": "raise", "pool": "solana", "x": "smartfollow"}.get(d.get("kind")), vk, mk.get("chain")}
    A.append(" ".join("#" + t for t in sorted(t for t in tags if t and t != "other")) + "\n<i>Не финсовет.</i>")
    return Post("\n\n".join(A), title, en, ru)
EV_EN = {"airdrop": "Airdrops", "points": "Points", "testnet": "Testnets", "mainnet": "Mainnets and launches", "tge": "TGE", "listing": "Listings",
         "raise": "Funding rounds", "hack": "Hacks", "unlock": "Unlocks", "other": "Other"}
def digest_post(digest, per_group=4, total=14):
    if not digest: return ""
    groups = {}
    for d in digest: groups.setdefault(d.get("event") or "other", []).append(d)
    picked = [d for k in EV if k in groups for d in groups[k][:per_group]][:total]
    from .discovery.news import write_digest
    W = write_digest(picked)
    stamp = f"{dt.datetime.now():%d.%m.%Y %H:%M}"
    src = [(d["title"], d["link"]) for d in picked]
    pages = {}
    for lang in ("en", "ru"):
        N = [T.p(T.i(f"{stamp} МСК · {len(picked)} " + ("событий" if lang == "ru" else "events")))]; cur = None
        for i, d in enumerate(picked):
            w = W.get(i, {}); k = d.get("event") or "other"
            if k != cur: cur = k; N.append(T.h((EV.get(k, EV["other"])[1] if lang == "ru" else EV_EN.get(k, "Other")), 3))
            nm = ", ".join(p["name"] for p in d["projects"][:2])
            N.append(T.p(T.b(nm), f" — {w.get(lang) or d['title']} [{i + 1}]"))
            if w.get("take_" + lang): N.append(T.p(T.i(w["take_" + lang])))
        pages[lang] = N + _footer(src, lang)
    names = []
    for k in EV:
        ns = [p["name"] for d in picked if (d.get("event") or "other") == k for p in d["projects"][:1]]
        if ns: names.append(f"{EV[k][0]} " + ", ".join(E(cut(x, 30)) for x in ns[:5]))
    A = [f"🗞 <b>Дайджест DropSearch · Digest</b> · {stamp} МСК", "\n".join(names), "#дайджест #news"]
    return Post("\n\n".join(A), f"DropSearch digest · {stamp}", pages["en"], pages["ru"], f"Дайджест DropSearch · {stamp}")

def deadlines_block(dls):
    L = []
    for x in dls[:4]:
        when = x.get("date") or "дата не указана"
        L.append(f"• <b>{E(when)}</b> — {E(cut(x.get('what') or x.get('type'), 120))}" + (f" · {link(x.get('link'), 'источник')}" if x.get("link") else ""))
    return "⏳ <b>Сроки</b>\n" + "\n".join(L) if L else ""

NEWS_EMO = {"airdrop": "🪂", "points": "🎯", "testnet": "🧪", "mainnet": "🚀", "tge": "🪙", "listing": "📈", "raise": "💰", "hack": "🚨", "unlock": "🔑", "other": "⚡️"}
def news_post(d, w):
    """Single news item, WatcherGuru-style: bold punchy headline, 1-3 sentence summary, links at the bottom."""
    w = w or {}; ev = d.get("event") or "other"
    head = w.get("head_en") or d["title"]
    head = _re.sub(r" - [^-]{2,40}$", "", head)
    if not _re.match(r"(?i)just in|breaking", head) and int(d.get("importance") or 0) >= 4: head = "JUST IN: " + head
    A = [f"{NEWS_EMO.get(ev, '⚡️')} <b>{E(cut(head, 140))}</b>"]
    summ = "\n".join(E(cut(x, 240)) for x in [w.get("en"), w.get("ru")] if x)
    if summ: A.append(summ)
    src = [(d["title"], d["link"])]
    pages = {l: [T.p(T.i(f"{dt.datetime.now():%d.%m.%Y %H:%M} МСК"))] + [T.p(x) for x in [w.get(l), w.get("take_" + l)] if x] + _footer(src, l) for l in ("en", "ru")}
    hru = w.get("head_ru") or w.get("ru") or head
    if int(d.get("importance") or 0) >= 4 and not _re.match(r"(?i)срочно", hru): hru = "СРОЧНО: " + hru
    o = Post("\n\n".join(A), cut(head, 120), pages["en"], pages["ru"], cut(w.get("head_ru") or w.get("ru") or head, 120))
    em = NEWS_EMO.get(ev, "⚡️"); o.ann = {"en": mono(em, head, w.get("en")), "ru": mono(em, hru, w.get("ru"))}
    return o
