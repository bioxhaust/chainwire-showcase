import time, requests
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (research-bot)"
def get(url, retries=3, **kw):
    kw.setdefault("timeout", 30)
    for i in range(retries):
        try:
            r = S.get(url, **kw)
            if r.status_code == 429:
                time.sleep(3 * (i + 1)); continue
            return r
        except requests.RequestException:
            time.sleep(2 * (i + 1))
    return None
def jget(url, **kw):
    r = get(url, **kw)
    try:
        return r.json() if r is not None and r.ok else None
    except ValueError:
        return None
