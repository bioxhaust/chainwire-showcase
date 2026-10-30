"""Pluggable article publisher. PUBLISHER=telegraph (default) | teletype (not implemented: no official teletype.in publishing API)."""
import os
def publish_pair(title_en, en, title_ru, ru):
    """Publish EN + RU pages (Telegraph-style node lists) cross-linked; return (en_url, ru_url)."""
    name = os.getenv("PUBLISHER", "telegraph").lower()
    if name == "telegraph":
        from .telegraph import publish_pair as f; return f(title_en, en, title_ru, ru)
    if name == "teletype":
        raise NotImplementedError("teletype publisher not implemented (needs account session; no public API)")
    raise ValueError(f"unknown PUBLISHER={name}")
