"""Two independent articles per post: RU (CIS crypto audience) and EN (global). Not translations.
Each is written by the LLM from the same facts/sources, published as its own Telegraph page, announced monolingually."""
import json, re, html, urllib.parse
import xml.etree.ElementTree as ET
from .config import OPENAI_API_KEY, LLM_BASE_URL, LLM_MODEL
from .http import S, get
from . import telegraph as T
from .fmt import E, cut
def _flat(nodes, out=None, links=None):
    out = [] if out is None else out; links = [] if links is None else links
    for n in nodes or []:
        if isinstance(n, str): out.append(n); continue
        if n.get("tag") == "a" and (n.get("attrs") or {}).get("href"): links.append(((" ".join(_flat(n.get("children"), [], [])[0])).strip(), n["attrs"]["href"]))
        _flat(n.get("children"), out, links)
        if n.get("tag") in ("p", "li", "h3", "h4"): out.append("\n")
    return out, links
def material(post):
    txt, links = _flat(post.en)
    body = re.sub(r"\n\s*\n+", "\n", "".join(txt)).strip()
    src = [(t, u) for t, u in links if "t.me/DropSearch" not in u and "telegra.ph" not in u]
    return body[:5000], src[:15]
def ru_sources(query):
    q = urllib.parse.quote(f"{query} when:3d")
    r = get(f"https://news.google.com/rss/search?hl=ru&gl=RU&ceid=RU:ru&q={q}", retries=2, timeout=20)
    if r is None or not r.ok: return []
    try: items = list(ET.fromstring(r.content).iter("item"))[:6]
    except ET.ParseError: return []
    return [(html.unescape(it.findtext("title") or ""), it.findtext("link") or "") for it in items]
GUIDE = {
 "ru": ("Ты автор русскоязычного крипто-канал ChainWire RU для аудитории из СНГ (фармеры, трейдеры, холдеры). Напиши СВОЮ статью на русском — "
        "не перевод: свой угол, живой тон, контекст для СНГ (доступность бирж/сервисов из РФ/СНГ, P2P, санкционные и KYC-риски, как это касается "
        "типичного фармера/холдера). Причинно-следственный разбор, что делать. Опирайся в первую очередь на русскоязычные источники, если они есть."),
 "en": ("You write for ChainWire EN, a global English crypto news channel. Write YOUR OWN article in English — not a translation: global angle, "
        "crisp newswire tone, market/industry context, cause → effect analysis and what readers should do. Prefer English-language sources."),
}
def write(post, lang, kind, extra_src=()):
    body, src = material(post)
    src = list(extra_src) + src if lang == "ru" else src + list(extra_src)
    head_rule = ("Заголовок короткий и хлёсткий; для срочных новостей начинай с «СРОЧНО:»." if lang == "ru"
                 else "Headline short and punchy; for urgent news start with 'JUST IN:'.")
    prompt = (GUIDE[lang] + f"\nPost type: {kind}. Use ONLY facts from the material and sources below; no invented numbers. "
              "Cite sources as [n]. " + head_rule +
              ' Return ONLY JSON: {"headline":str,"summary":"1-3 sentences for the channel post","article":"4-7 short paragraphs separated by \\n"}.\n\n'
              f"MATERIAL:\n{body}\n\nSOURCES:\n" + "\n".join(f"[{i + 1}] {t} — {u}" for i, (t, u) in enumerate(src)))
    for _ in range(2):
        try:
            r = S.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=300,
                       json={"model": LLM_MODEL, "temperature": 0.5, "messages": [{"role": "user", "content": prompt}]})
            o = json.loads(re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"], re.S).group(0))
            if o.get("headline") and o.get("article"): return o, src
        except Exception as e: print(f"[dual] {lang} write failed:", e)
    return None, src
def kind_of(post):
    s = str(post)
    return "breaking" if "#breaking" in s or "🚨" in s[:3] else "hot" if "АКТУАЛЬНО" in s else "news" if getattr(post, "ann", None) else "project analysis"
def emoji(post): m = re.match(r"\s*(\S+)", str(post)); return m.group(1) if m and not m.group(1).startswith("<") else "⚡️"
def build(post, lang):
    """Returns (announcement_html, url) or None."""
    kind = kind_of(post)
    extra = ru_sources(re.sub(r"[^\w\s$]", " ", post.title)[:80]) if lang == "ru" else []
    o, src = write(post, lang, kind, extra)
    if not o: return None
    ru = lang == "ru"
    nodes = [T.p(x.strip()) for x in str(o["article"]).split("\n") if x.strip()]
    if src: nodes += [T.h("Источники" if ru else "Sources", 3), T.ul([[T.a(u, cut(t, 120) or u)] for t, u in src if u], "ol")]
    nodes.append(T.p(T.i("Не финансовый совет. " if ru else "Not financial advice. "), T.a(f"https://t.me/ChainWire{'RU' if ru else 'EN'}", f"@ChainWire{'RU' if ru else 'EN'}")))
    url = T.publish(cut(o["headline"], 200), nodes)
    em = "🚨" if kind == "breaking" else emoji(post)
    tag = ("#срочно" if ru else "#breaking") if kind == "breaking" else ""
    ann = "\n\n".join(x for x in [f"{em} <b>{E(cut(o['headline'], 140))}</b>", E(cut(o.get("summary") or "", 400)), tag,
                                  f'<a href="{E(url)}">{"📖 Читать статью" if ru else "📖 Read the article"}</a>'] if x)
    return ann, url
