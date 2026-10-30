import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from .config import CHANNEL_RU, CHANNEL_EN, ANNOUNCE_IN_CHANNEL, TELEGRAM_BOT_TOKEN, CHANNEL_ID, POST_MIN_SCORE, LOOP_MINUTES, HOT_SCAN_HOURS
from . import db, hot
from .pipeline import analyze, resolve
from . import tracker
from .loop import cycle
async def cmd_analyze(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args: return await u.message.reply_text("Использование: /analyze <тикер|контракт|ссылка>")
    await u.message.reply_text("Анализирую…")
    s, txt = await asyncio.to_thread(analyze, resolve(" ".join(c.args)))
    kb = None
    if hasattr(txt, "publish"):
        from .fmt import with_links
        txt, urls = await asyncio.to_thread(txt.publish); txt = with_links(txt, urls)
    await u.message.reply_html(txt, disable_web_page_preview=True, reply_markup=kb)
async def cmd_stats(u: Update, c): await u.message.reply_text(tracker.stats())
async def autopost(c: ContextTypes.DEFAULT_TYPE):
    posts = []
    await asyncio.to_thread(cycle, lambda t, meta=None: posts.append((t, meta)))
    await send_all(c, posts)
async def send_all(c, posts):
    for t, meta in posts:
        try:
            if ANNOUNCE_IN_CHANNEL and CHANNEL_RU and CHANNEL_EN and hasattr(t, "publish"):
                from . import dual
                urls = [None, None]
                for k, (lang, ch) in enumerate((("ru", CHANNEL_RU), ("en", CHANNEL_EN))):  # RU first; one failing doesn't block the other
                    try:
                        r = await asyncio.to_thread(dual.build, t, lang)
                        if not r: print(f"[dual] {lang} skipped"); continue
                        await c.bot.send_message(ch, r[0], parse_mode="HTML", disable_web_page_preview=True); urls[k] = r[1]
                    except Exception as e: print(f"[send {lang}]", e)
                if meta and any(urls): db.record_post(meta["name"], meta["mode"], meta.get("sig", ""), (urls[1], urls[0]))
                await asyncio.sleep(3); continue
            urls, kb = None, None
            if hasattr(t, "publish"):
                from .fmt import with_links
                t, urls = await asyncio.to_thread(t.publish); t = with_links(t, urls)
            if ANNOUNCE_IN_CHANNEL: await c.bot.send_message(CHANNEL_ID or CHANNEL_RU, t, parse_mode="HTML", disable_web_page_preview=True, reply_markup=kb)
            if meta: db.record_post(meta["name"], meta["mode"], meta.get("sig", ""), urls)
        except Exception as e: print("[send]", e)
        await asyncio.sleep(3)
async def hotpost(c: ContextTypes.DEFAULT_TYPE):
    posts = []
    await asyncio.to_thread(hot.scan, lambda t, meta=None: posts.append((t, meta)))
    await send_all(c, posts)
def run():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("analyze", cmd_analyze)); app.add_handler(CommandHandler("stats", cmd_stats))
    if CHANNEL_ID: app.job_queue.run_repeating(autopost, interval=LOOP_MINUTES * 60, first=10)
    if CHANNEL_ID: app.job_queue.run_repeating(hotpost, interval=HOT_SCAN_HOURS * 3600, first=15 * 60)
    app.run_polling()
