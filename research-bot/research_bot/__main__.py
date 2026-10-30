import argparse, time
from .config import LOOP_MINUTES
from . import funds, kb, tracker
from .pipeline import analyze, resolve
from .loop import cycle
def main():
    ap = argparse.ArgumentParser(prog="research_bot")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("analyze"); a.add_argument("q")
    for c in ["once", "loop", "telegram", "refresh-funds", "build-kb", "stats", "hot", "breaking", "tg"]: sub.add_parser(c)
    x = ap.parse_args()
    if x.cmd == "analyze": print(analyze(resolve(x.q))[1])
    elif x.cmd == "once": cycle()
    elif x.cmd == "loop":
        while True: cycle(); time.sleep(LOOP_MINUTES * 60)
    elif x.cmd == "refresh-funds": rows, fr, n = funds.refresh(); print(f"{len(rows)} funds, {n} raises 2024+, freshest {fr}")
    elif x.cmd == "build-kb": print(kb.build(), "chunks")
    elif x.cmd == "hot":
        from . import hot; hot.scan(dry=True)
    elif x.cmd == "breaking":
        from . import breaking; breaking.scan(dry=True)
    elif x.cmd == "tg":
        from .discovery import tgchannels; st = {}; ps = tgchannels.fetch(48, st); print(st); [print(p["ts"], p["link"], p["title"][:90]) for p in ps[:40]]
    elif x.cmd == "stats": print(tracker.stats())
    elif x.cmd == "telegram":
        from .tgbot import run; run()
    else: ap.print_help()
main()
