"""Knowledge base: chunks of Biban's materials in SQLite FTS5 (BM25)."""
import sqlite3, json, csv, re
from .config import DATA, KB_DB, CORPUS
def _chunks(text, size=1200, overlap=150):
    text = re.sub(r"\s+\n", "\n", text); i = 0
    while i < len(text):
        yield text[i:i + size]; i += size - overlap
def build():
    c = sqlite3.connect(KB_DB); c.execute("drop table if exists kb")
    c.execute("create virtual table kb using fts5(source, dated, body, tokenize='unicode61')"); n = 0
    for p in sorted((DATA / "kb").glob("*")):
        t = p.read_text(errors="ignore")
        for ch in _chunks(t): c.execute("insert into kb values(?,?,?)", (p.name, "historical", ch)); n += 1
    if CORPUS.exists():
        for line in open(CORPUS):
            m = json.loads(line); t = (m.get("text") or "") + " " + (m.get("caption") or "")
            if len(t) > 80:
                for ch in _chunks(t): c.execute("insert into kb values(?,?,?)", (f"tg#{m.get('message_id')}", str(m.get("date", ""))[:10], ch)); n += 1
    for fn in ["funds_2026.csv", "funds.csv", "vc_database_2022.csv"]:
        p = DATA / fn
        if p.exists():
            for r in csv.reader(open(p, encoding="utf-8")):
                c.execute("insert into kb values(?,?,?)", (fn, "live" if "2026" in fn else "historical", " | ".join(r)[:1500])); n += 1
    c.commit(); return n
def search(query, k=6):
    if not KB_DB.exists(): build()
    words = [w for w in re.findall(r"\w{3,}", query.lower())][:12]
    if not words: return []
    q = " OR ".join(f'"{w}"' for w in words)
    c = sqlite3.connect(KB_DB)
    try:
        return c.execute("select source, dated, snippet(kb,2,'','','…',60) from kb where kb match ? order by bm25(kb) limit ?", (q, k)).fetchall()
    except sqlite3.OperationalError:
        return []
