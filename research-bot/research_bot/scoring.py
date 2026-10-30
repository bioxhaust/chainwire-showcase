import json, re, datetime as dt, csv
from .config import OPENAI_API_KEY, LLM_BASE_URL, LLM_MODEL, DATA
from .prompt import SYSTEM, FEWSHOT_USER, FEWSHOT_ASSISTANT
from . import kb
from .http import S
def fund_context(investors):
    p = DATA / "funds_2026.csv"
    if not investors or not p.exists(): return ""
    from .funds import investor_match
    rows = [r for r in csv.DictReader(open(p, encoding="utf-8")) if any(investor_match(i, r["fund"]) for i in investors)]
    return "\n".join(f"{r['fund']}: {r['unique_projects']} проектов 2024-26, {r['pct_with_token']}% уже с токеном (данные до {r['freshest_record']})" for r in rows)
def heuristic(d):
    s, red, green = 50, [], []
    rc, mk, inv = d.get("rugcheck") or {}, d.get("market") or {}, d.get("investors") or []
    if rc:
        if rc.get("mint_authority"): s -= 25; red.append("mint authority не отозван")
        if rc.get("freeze_authority"): s -= 20; red.append("freeze authority не отозван")
        if (rc.get("top10_pct") or 0) > 30: s -= 15; red.append(f"топ-10 холдеров {rc['top10_pct']}%")
        if rc.get("rugged"): s -= 50; red.append("rugcheck: RUGGED")
        if rc.get("lp_locked_pct") is not None and rc["lp_locked_pct"] < 50: s -= 10; red.append(f"LP залочен {rc['lp_locked_pct']:.0f}%")
        if not rc.get("mint_authority") and not rc.get("freeze_authority"): green.append("mint/freeze отозваны")
    if mk:
        if (mk.get("liq_usd") or 0) < 20000: s -= 10; red.append("ликвидность <$20k")
        if (mk.get("alt_contracts_same_ticker") or 1) > 2: red.append(f"{mk['alt_contracts_same_ticker']} контрактов с тем же тикером (клоны)")
    if d.get("fund_ctx"): s += 15; green.append("фонды из базы: " + ", ".join(inv[:4]))
    elif inv: s += 5; green.append("есть инвесторы: " + ", ".join(inv[:4]))
    x = d.get("x") or {}
    if x.get("bot_follower_flag"): s -= 10; red.append("X: признаки накрученных подписчиков")
    if d.get("kind") == "x" and len(d.get("followed_by", [])) >= 2: s += 10; green.append("подписались несколько смартов")
    s = max(0, min(100, s))
    v = "scam" if s < 21 else ("farm" if d.get("kind") == "round" and not mk and s >= 60 else "enter" if s >= 70 else "watch")
    return {"score": s, "verdict": v, "summary": "Эвристическая оценка (LLM не настроен).", "green": green, "red": red,
            "unverified": ["команда", "токеномика/разлоки", "X-активность"] if not x else ["команда", "токеномика"], "action": "Ручная проверка по чеклисту."}
def llm(d):
    passages = kb.search(" ".join(str(d.get(k, "")) for k in ("name", "category", "round")) + " токеномика скам фонд", k=6)
    ctx = "\n---\n".join(f"[{s} | {dated}] {t}" for s, dated, t in passages)
    user = f"Сегодня {dt.date.today()}. Релевантные выдержки из базы знаний (исторические — учитывай дату):\n{ctx}\n\nСтатистика фондов:\n{d.get('fund_ctx','')}\n\nДанные проекта:\n{json.dumps({k: v for k, v in d.items() if k != 'fund_ctx'}, ensure_ascii=False, default=str)[:8000]}"
    r = S.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=180, json={
        "model": LLM_MODEL, "temperature": 0.2, "messages": [{"role": "system", "content": SYSTEM + "\n\nПРИМЕР формата (это ДРУГОЙ проект, $FLOP; НЕ переносить его факты):\nВход: " + FEWSHOT_USER + "\nВыход: " + FEWSHOT_ASSISTANT},
        {"role": "user", "content": user + "\n\nОценивай ТОЛЬКО этот проект и только по данным выше; чего нет в данных — в unverified."}]})
    txt = r.json()["choices"][0]["message"]["content"]
    return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
def score(d):
    d["fund_ctx"] = fund_context(d.get("investors"))
    if OPENAI_API_KEY:
        try: return llm(d) | {"engine": "llm"}
        except Exception as e: print("LLM failed, fallback:", e)
    return heuristic(d) | {"engine": "heuristic"}
