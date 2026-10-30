"""Public Telegram channels as a news source via the web preview https://t.me/s/<name> (no API key needed)."""
import os, re, html, datetime as dt
from ..http import get
STYLE_REFS = "shtanga0x,crypto_okop,crypt0scamm,moni_talks,cryppi,asati_shill,byrealfarmer,WatcherGuru"  # style references only, not news sources
DEFAULT = ""
def channels():
    return [c.strip().lstrip("@").split("/")[-1] for c in os.getenv("TG_NEWS_CHANNELS", DEFAULT).split(",") if c.strip()]
def _clean(h):
    h = re.sub(r"<br\s*/?>", "\n", h)
    h = re.sub(r"<i class=\"emoji\"[^>]*><b>(.*?)</b></i>", r"\1", h)
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()
def fetch_channel(name, max_age_h=36):
    r = get(f"https://t.me/s/{name}", retries=2, timeout=20)
    if r is None or not r.ok or "tgme_widget_message_wrap" not in r.text: return None  # None = no web preview / failed
    now, out = dt.datetime.now(dt.timezone.utc), []
    for blk in r.text.split("tgme_widget_message_wrap")[1:]:
        m = re.search(r'data-post="([^"]+)"', blk); t = re.search(r'<time datetime="([^"]+)"', blk)
        x = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', blk, re.S)
        if not (m and t and x): continue
        try: ts = dt.datetime.fromisoformat(t.group(1))
        except ValueError: continue
        if (now - ts).total_seconds() > max_age_h * 3600: continue
        text = _clean(x.group(1))
        if len(text) < 25: continue
        first = next((l for l in text.split("\n") if len(l.strip()) > 10), text).strip()
        out.append({"source": f"TG @{name}", "title": first[:200], "link": f"https://t.me/{m.group(1)}", "summary": text[:600],
                    "ts": ts.astimezone(dt.timezone.utc).isoformat(), "tg": True})
    return out
def fetch(max_age_h=36, status=None):
    res = []
    for c in channels():
        got = fetch_channel(c, max_age_h)
        if status is not None: status[c] = -1 if got is None else len(got)
        if got is None: print(f"[tg] @{c}: no web preview / fetch failed"); continue
        res += got
    return res
