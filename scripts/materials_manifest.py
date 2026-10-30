#!/usr/bin/env python3
"""Inventory the local Chainwire evidence snapshot, without network or mutation.

Only the two generated outputs are written, and only without --check.
Content availability is deliberately separate from factual verification.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = "docs/research/materials-manifest.json"
OUTPUT_MD = "docs/research/materials-manifest.md"
LEGACY_ROOTS = ("/workspace/web3-engine/", "/Users/i4goth/Desktop/meme-hustle/chainwire/")
BASELINE_COUNTS = {
    "raw_telegram_records": 202,
    "raw_messages_with_two_occurrences": 101,
    "unique_telegram_messages": 101,
    "link_messages": 48,
    "photo_messages": 53,
    "unique_index_urls": 61,
    "photo_files": 53,
    "unique_photo_sha256": 53,
    "kb_files": 35,
    "recovered_files": 22,
}
REPORT = "docs/reference/chainwire-materials-and-server.md"
RECOVERY_LOG = "recovered/README.txt"


class ManifestError(ValueError):
    """A source cannot be safely or unambiguously interpreted."""


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def resolve_source_path(original, root):
    """Translate documented roots and reject traversal/symlinks before opening."""
    root = Path(root).resolve()
    candidate = original
    for prefix in LEGACY_ROOTS:
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
            break
    path = PurePosixPath(candidate)
    if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in candidate:
        raise ManifestError(f"Unsupported source path: {original}")
    relative = path.as_posix()
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ManifestError(f"Symlink inputs are not supported: {original}")
    try:
        (root / relative).resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ManifestError(f"Source path escapes repository: {original}") from exc
    return relative


def material_path(root, original):
    """Allow only corpus/reference files, including for early index reads."""
    relative = resolve_source_path(original, root)
    path = PurePosixPath(relative)
    fixed = {"index_dedup.jsonl", "telegram-corpus/index.jsonl", "funds.csv"}
    suffixes = {
        "telegram-corpus/photos": {".jpg"},
        "telegram-corpus/links": {".txt"},
        "research-bot/data/kb": {".txt", ".md"},
        "recovered": {".txt", ".html", ".json", ".csv"},
        "research-bot/data": {".csv"},
        "docs/reference": {".md", ".json", ".jsonl", ".swift", ".txt", ".csv"},
    }
    allowed = relative in fixed or path.suffix.lower() in suffixes.get(path.parent.as_posix(), set())
    if not allowed or any(part.startswith(".") for part in path.parts):
        raise ManifestError(f"Path is outside allowed material inputs: {original}")
    return Path(root) / relative


def read_material_bytes(root, relative):
    # Every content read goes through both location and symlink checks. Checking
    # only after reading would expose excluded data even if generation then fails.
    return material_path(root, relative).read_bytes()


def read_jsonl(root, relative):
    try:
        lines = read_material_bytes(root, relative).decode("utf-8").splitlines()
    except OSError as exc:
        raise ManifestError(f"Missing or unreadable input: {relative}") from exc
    result = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise ManifestError(f"Blank JSONL record: {relative}:{line_number}")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"Invalid JSON: {relative}:{line_number}") from exc
        if not isinstance(item, dict) or not isinstance(item.get("message_id"), int):
            raise ManifestError(f"Missing integer message_id: {relative}:{line_number}")
        if item.get("type") not in ("link", "photo") or not isinstance(item.get("path"), str):
            raise ManifestError(f"Invalid message type/path: {relative}:{line_number}")
        if not isinstance(item.get("urls"), list) or any(not isinstance(u, str) for u in item["urls"]):
            raise ManifestError(f"Invalid URL list: {relative}:{line_number}")
        result.append((line_number, item))
    return result


def unique_messages(rows, label):
    unique = {}
    locations = defaultdict(list)
    for line, row in rows:
        message_id = row["message_id"]
        if message_id in unique and unique[message_id] != row:
            raise ManifestError(f"Conflicting duplicate message_id {message_id} in {label}")
        unique[message_id] = row
        locations[message_id].append(line)
    return unique, locations


class HtmlEvidence(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.title_parts = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)


def content_state(status, evidence):
    return {"status": status, "evidence": evidence, "full_original_verified": False}


def source_identity(identifier, url=None, evidence=None, reported_label=None):
    return {"id": identifier, "url": url, "evidence": evidence or [], "reported_label": reported_label}


def match_url(urls, token):
    matches = sorted(u for u in urls if token in u)
    return matches[0] if len(matches) == 1 else None


def recovered_source(name, urls):
    # Association comes from the local recovery log plus an exact URL in the index.
    # No URL is reconstructed from an ID or guessed from an author's name.
    tokens = {
        "hodlmod": "/@hodlmod.eth/how_find_gems",
        "nansen": "/following-the-nerds-understanding-smart-money-labels-and-how-to-use-them",
        "thread_stacy": "/stacy_muur/status/1681275480987795457",
        "thread_surfer": "/0xsurferboy/status/1641781790426947587",
        "vcdb": "de9c391f8dd14a8a9a3e01a69f4e0b7f",
        "vc_database_2022": "de9c391f8dd14a8a9a3e01a69f4e0b7f",
        "airtable_messari": "airtable.com/",
        "messari_fundraising": "airtable.com/",
        "at": "airtable.com/",
    }
    stem = Path(name).stem
    token = tokens.get(stem)
    if stem.startswith("notion_") or stem.startswith("tw_"):
        token = stem.split("_", 1)[1]
    if stem.startswith("dune_"):
        token = "/" + stem.removeprefix("dune_")
    return match_url(urls, token) if token else None


def describe_file(relative, data, urls, recovery_date):
    """Only conservative, auditable states; never assess truth from file length."""
    result = {
        "source_identity": source_identity("local-file:" + relative),
        "original_published_at": None,
        "publication_time_evidence": [],
        "imported_at": None,
        "import_time_evidence": [],
        "classification": "unclassified",
        "verification_status": "unverified",
        "completeness": content_state("captured_unverified", ["Local bytes exist; original completeness not checked"]),
    }
    suffix = Path(relative).suffix
    if relative.startswith("telegram-corpus/photos/"):
        result["completeness"] = content_state("image_bytes_present", ["Local image bytes; interpretation and source provenance unverified"])
        return result
    text = data.decode("utf-8")
    header = re.search(r"^SOURCE:\s*(.+)$", text, re.M)
    if header:
        label = header.group(1).strip()
        url = label if re.fullmatch(r"https?://\S+", label) else None
        result["source_identity"] = source_identity("local-file:" + relative, url, [relative + ":SOURCE header"], label)
    dated = re.search(r"^DATED:\s*(.+)$", text, re.M)
    if dated:
        result["reported_date_label"] = dated.group(1)
    if relative.startswith("telegram-corpus/links/"):
        result["completeness"] = content_state("link_only", ["Saved Telegram link/caption, not fetched target content"])
    elif relative.endswith("screenshots_notes.md"):
        result["completeness"] = content_state("summary_with_reported_errors", [REPORT + ": Ошибки, которые нельзя переносить в публичные оценки"])
    elif relative.startswith("recovered/"):
        result["imported_at"] = recovery_date
        result["import_time_evidence"] = [RECOVERY_LOG + ": Recovered header; date only, timezone unknown"] if recovery_date else []
        url = recovered_source(Path(relative).name, urls)
        if url:
            result["source_identity"] = source_identity("local-file:" + relative, url, [RECOVERY_LOG, "index_dedup.jsonl: matching URL/ID"])
        if suffix == ".json":
            obj = json.loads(text)
            if obj.get("code") == 404:
                result["completeness"] = content_state("error_response", [relative + ": code=404, tweet=null"])
            elif "tweet" in obj and obj.get("tweet"):
                tweet = obj["tweet"]
                result["source_identity"] = source_identity("local-file:" + relative, tweet.get("url"), [relative + ": tweet.url"])
                if tweet.get("created_at"):
                    result["original_published_at"] = parsedate_to_datetime(tweet["created_at"]).isoformat()
                    result["publication_time_evidence"] = [relative + ": tweet.created_at (captured API claim, not revalidated)"]
                result["completeness"] = content_state("single_post_captured", [relative + ": tweet object; does not establish full thread recovery"])
            elif "recordMap" in obj and not (set(obj["recordMap"]) - {"__version__"}):
                result["completeness"] = content_state("shell_only", [relative + ": recordMap contains only __version__"])
            elif "recordMap" in obj:
                result["completeness"] = content_state("structured_capture_unverified", [relative + ": nonempty recordMap; public/full content not established"])
            else:
                result["completeness"] = content_state("structured_capture_unverified", [relative + ": JSON data; completeness not established"])
        elif suffix == ".html":
            html = HtmlEvidence()
            html.feed(text)
            result["captured_html_title"] = " ".join(html.title_parts)
            if html.canonical:
                result["source_identity"] = source_identity("local-file:" + relative, html.canonical, [relative + ": canonical link (captured page identity)"])
            if Path(relative).name.startswith("dune_"):
                result["completeness"] = content_state("shell_only", [RECOVERY_LOG + ": Dune dashboards have only titles; HTML title observed"])
            elif Path(relative).name == "5laver_index.html":
                result["completeness"] = content_state("profile_instead_of_article", [relative + ": canonical is author profile", RECOVERY_LOG + ": requested article failed"])
                result["requested_source_url"] = match_url(urls, "/@5laver5lave/1RuGEDvDRr-")
            elif Path(relative).name == "at.html":
                result["completeness"] = content_state("html_capture_unverified", ["Airtable HTML; content recovery represented separately by JSON/CSV"])
        elif Path(relative).name == "thread_surfer.txt":
            result["completeness"] = content_state("partial_thread", [RECOVERY_LOG + ": replies; full root thread not established", REPORT + ": translation also appears in photos 62/63"])
        elif Path(relative).name == "thread_stacy.txt":
            result["completeness"] = content_state("thread_capture_unverified", [RECOVERY_LOG + ": reports 50/50; not independently compared with original thread"])
        elif Path(relative).name == "README.txt":
            result["classification"] = "reference"
            result["completeness"] = content_state("recovery_log", ["Historical recovery claims; not present-day availability"])
    if suffix == ".csv":
        result["classification"] = "reference"
        result["completeness"] = content_state("dataset_capture_unverified", ["Local CSV; rows are not independently verified facts or current data"])
    if relative.startswith("docs/reference/"):
        result["classification"] = "reference"
        status = "machine_transcription_unverified" if "images-ocr" in relative else "reference_snapshot"
        result["completeness"] = content_state(status, ["Supplied historical reference; no new verification or runtime evidence"])
    # A clearly labelled publication date can be recorded with date-only precision.
    # Archive snapshot dates, DATED ranges and OCR-looking dates are never substituted.
    if Path(relative).name == "nansen.txt":
        published = re.search(r"Published on\n([A-Z][a-z]+ \d{1,2}, \d{4})\n", text)
        if published:
            result["original_published_at"] = datetime.strptime(published.group(1), "%B %d, %Y").date().isoformat()
            result["publication_time_evidence"] = [relative + ": Published on label (captured claim, date only)"]
    return result


def build_manifest(root, expected_counts=None):
    root = Path(root).resolve()
    expected_counts = BASELINE_COUNTS if expected_counts is None else expected_counts
    raw_rows = read_jsonl(root, "telegram-corpus/index.jsonl")
    dedup_rows = read_jsonl(root, "index_dedup.jsonl")
    raw, raw_locations = unique_messages(raw_rows, "raw index")
    dedup, dedup_locations = unique_messages(dedup_rows, "deduplicated index")
    issues = []
    if raw != dedup:
        issues.append("Raw and deduplicated message records differ")
    if len(dedup_rows) != len(dedup):
        issues.append("Deduplicated index still contains duplicate message IDs")
    urls = sorted({u for row in dedup.values() for u in row["urls"]})
    required = ["index_dedup.jsonl", "telegram-corpus/index.jsonl", "telegram-corpus/links/all_links.txt", RECOVERY_LOG,
                "docs/reference/sources.json", "docs/reference/chainwire-brand-plan.md", REPORT, "docs/reference/chainwire-images-ocr.md"]
    reference_index = material_path(root, "docs/reference/sources.json")
    reference_sources = json.loads(read_material_bytes(root, "docs/reference/sources.json")) if reference_index.is_file() else []
    required.extend("docs/reference/" + ref["file"] for ref in reference_sources)
    groups = {"photos": "telegram-corpus/photos", "links": "telegram-corpus/links", "kb": "research-bot/data/kb", "recovered": "recovered"}
    paths = set(required)
    for name, directory in groups.items():
        folder = root / resolve_source_path(directory, root)
        if not folder.is_dir():
            raise ManifestError(f"Missing input directory: {directory}")
        # The supplied corpus has flat source directories. Reject unexpected
        # entries before traversal or opening, especially directory symlinks.
        for path in sorted(folder.iterdir()):
            relative = path.relative_to(root).as_posix()
            material_path(root, relative)
            if not path.is_file():
                raise ManifestError(f"Expected a material file: {relative}")
            paths.add(relative)
    # Include reference datasets used by the loader; deliberately exclude runtime DBs,
    # process state, owner metadata, .env and credentials.
    data_directory = root / resolve_source_path("research-bot/data", root)
    paths.update(p.relative_to(root).as_posix() for p in data_directory.glob("*.csv"))
    if material_path(root, "funds.csv").is_file():
        paths.add("funds.csv")
    message_paths = {}
    for mid, row in dedup.items():
        relative = resolve_source_path(row["path"], root)
        message_paths[mid] = relative
        wanted_directory = "telegram-corpus/photos/" if row["type"] == "photo" else "telegram-corpus/links/"
        if not relative.startswith(wanted_directory):
            raise ManifestError(f"Message {mid} path is outside expected {row['type']} directory")
        material_path(root, relative)
        paths.add(relative)
    recovery_text = read_material_bytes(root, RECOVERY_LOG).decode("utf-8") if material_path(root, RECOVERY_LOG).is_file() else ""
    recovery_match = re.search(r"^Recovered (\d{4}-\d{2}-\d{2}):", recovery_text)
    recovery_date = recovery_match.group(1) if recovery_match else None
    file_records = {}
    for relative in sorted(paths):
        path = material_path(root, relative)
        record = {"id": "file:" + relative, "original_path": relative, "original_path_basis": "current supplied path; earlier filesystem path unknown",
                  "resolved_path": relative, "exists": path.is_file(), "sha256": None, "size_bytes": None}
        if not path.is_file():
            issues.append("Missing file: " + relative)
            record.update({"source_identity": source_identity("local-file:" + relative), "original_published_at": None,
                           "publication_time_evidence": [], "imported_at": None, "import_time_evidence": [], "classification": "unclassified",
                           "verification_status": "unverified", "completeness": content_state("missing", ["Referenced local file absent"])})
        else:
            data = read_material_bytes(root, relative)
            record.update({"sha256": sha256(data), "size_bytes": len(data)})
            record.update(describe_file(relative, data, urls, recovery_date))
        file_records[relative] = record
    messages = []
    for mid, row in sorted(dedup.items()):
        relative = message_paths[mid]
        file = file_records[relative]
        file["original_path"] = row["path"]
        file["original_path_basis"] = "index_dedup.jsonl:path"
        file["imported_at"] = row.get("date")
        file["import_time_evidence"] = ["index_dedup.jsonl:date; import, timezone unknown (" + REPORT + ")"]
        identity = source_identity(f"telegram-import:{mid}", evidence=[f"index_dedup.jsonl:{dedup_locations[mid][0]}"], reported_label=row.get("source"))
        file["source_identity"] = identity
        messages.append({"id": f"telegram-import:{mid}", "message_id": mid, "source_identity": identity,
                         "type": row["type"], "original_path": row["path"], "resolved_path": relative, "sha256": file["sha256"],
                         "original_published_at": None, "publication_time_evidence": [], "imported_at": row.get("date"),
                         "import_time_evidence": file["import_time_evidence"], "urls": sorted(set(row["urls"])),
                         "raw_index_lines": raw_locations.get(mid, []), "dedup_index_lines": dedup_locations[mid],
                         "classification": "unclassified", "verification_status": "unverified", "completeness": file["completeness"]})
    # Same bytes establish a local copy relationship, not an independent source.
    by_hash = defaultdict(list)
    for relative, record in file_records.items():
        if record["sha256"]:
            by_hash[record["sha256"]].append(relative)
    for relative, record in file_records.items():
        record["identical_local_files"] = [p for p in by_hash.get(record["sha256"], []) if p != relative]
        if relative.startswith("research-bot/data/kb/") and not record["source_identity"]["url"]:
            copies = [file_records[p] for p in record["identical_local_files"] if p.startswith("recovered/")]
            source_urls = {r["source_identity"]["url"] for r in copies if r["source_identity"]["url"]}
            if len(source_urls) == 1:
                record["source_identity"]["url"] = next(iter(source_urls))
                record["source_identity"]["evidence"] = ["Identical SHA-256 to " + r["resolved_path"] for r in copies]
                record["completeness"] = copies[0]["completeness"]
    sources_record = file_records["docs/reference/sources.json"]
    if sources_record["exists"]:
        for ref in reference_sources:
            relative = "docs/reference/" + ref["file"]
            if relative not in file_records:
                issues.append("Reference snapshot is not inventoried: " + relative)
                continue
            record = file_records[relative]
            record["original_path"] = ref["source"]
            record["original_path_basis"] = "docs/reference/sources.json"
            if record["sha256"] != ref["sha256"]:
                issues.append("Reference snapshot hash differs: " + relative)
    all_links_record = file_records["telegram-corpus/links/all_links.txt"]
    if all_links_record["exists"]:
        all_links = {line.strip() for line in read_material_bytes(root, all_links_record["resolved_path"]).decode("utf-8").splitlines() if line.strip()}
        if all_links != set(urls):
            issues.append("all_links.txt URL set differs from deduplicated index")
    photo_records = [r for p, r in file_records.items() if p.startswith("telegram-corpus/photos/") and r["exists"]]
    photo_hashes = [r["sha256"] for r in photo_records]
    if len(photo_hashes) != len(set(photo_hashes)):
        issues.append("Photo files contain identical SHA-256 values")
    mapped_photos = {message_paths[mid] for mid, row in dedup.items() if row["type"] == "photo"}
    if mapped_photos != {r["resolved_path"] for r in photo_records}:
        issues.append("Photo files and photo-message paths are not a one-to-one set")
    if len(mapped_photos) != sum(row["type"] == "photo" for row in dedup.values()):
        issues.append("Multiple photo messages reference the same file")
    counts = {"raw_telegram_records": len(raw_rows), "unique_telegram_messages": len(dedup), "duplicate_raw_records": len(raw_rows) - len(raw),
              "raw_messages_with_two_occurrences": sum(len(lines) == 2 for lines in raw_locations.values()),
              "link_messages": sum(r["type"] == "link" for r in dedup.values()), "photo_messages": sum(r["type"] == "photo" for r in dedup.values()),
              "unique_index_urls": len(urls), "photo_files": len(photo_records), "unique_photo_sha256": len(set(photo_hashes)),
              "kb_files": sum(p.startswith("research-bot/data/kb/") and r["exists"] for p, r in file_records.items()),
              "recovered_files": sum(p.startswith("recovered/") and r["exists"] for p, r in file_records.items()),
              "inventoried_files": len(file_records), "missing_files": sum(not r["exists"] for r in file_records.values())}
    for key, expected in expected_counts.items():
        if counts[key] != expected:
            issues.append(f"Baseline count {key}: expected {expected}, found {counts[key]}")
    url_records = []
    for url in urls:
        linked = [r for r in file_records.values() if r["source_identity"]["url"] == url or r.get("requested_source_url") == url]
        url_records.append({"id": "url:" + sha256(url.encode("utf-8")), "url": url,
                            "source_identity": source_identity("url:" + sha256(url.encode("utf-8")), url, ["index_dedup.jsonl:urls"]),
                            "original_path": None, "resolved_path": None, "sha256": None,
                            "path_evidence": "Remote URL has no local content path; associated captures listed separately",
                            "telegram_message_ids": [m["message_id"] for m in messages if url in m["urls"]],
                            "local_materials": [{"resolved_path": r["resolved_path"], "sha256": r["sha256"], "completeness": r["completeness"]["status"]} for r in linked],
                            "completeness": content_state("local_capture_unverified" if linked else "url_only", ["Local association does not establish full original recovery"]),
                            "original_published_at": None, "imported_at": None, "verification_status": "unverified"})
    return {"schema_version": 1, "scope": {"project_name": "Chainwire (pilot name)", "languages": ["ru", "en"], "ecosystems": "unrestricted",
              "url_identity": "Exact strings from index_dedup.jsonl; no normalization, redirects or inferred URLs",
              "telegram_identity": "Local import message_id; original channel/message URL unknown when source is null",
              "timestamps": "No clock/mtime values. Publication and import are separate; null means unknown; date-only values retain precision.",
              "classification": "methodology / historical_case / reference / unclassified; only reference assigned mechanically",
              "excluded": ["runtime SQLite databases", "credentials/environment", "owner metadata", "seed accounts", "live network verification"]},
            "baseline_counts": expected_counts, "counts": counts, "raw_occurrences_per_message": dict(sorted(Counter(str(len(v)) for v in raw_locations.values()).items())),
            "issues": sorted(set(issues)), "messages": messages, "urls": url_records, "files": list(file_records.values())}


def render_readme(manifest):
    c = manifest["counts"]
    return f"""# Манифест материалов / Materials manifest

Chainwire — пилотное название. RU и EN обязательны; ограничений по экосистемам нет.
Это инвентаризация сохранённых доказательств, а не утверждённая методология или новое подтверждение фактов.

Запуск из корня репозитория (Python 3.9+, только стандартная библиотека):

```sh
python3 scripts/materials_manifest.py
python3 scripts/materials_manifest.py --check
python3 -m unittest discover -s tests -p 'test_materials_manifest.py' -v
```

Первая команда обновляет только этот README и [JSON](materials-manifest.json). `--check` сравнивает оба результата побайтово, проверяет инварианты и ничего не записывает. Команды не используют сеть, секреты, SQLite или часы. Оригиналы никогда не изменяются. Тесты создают собственные временные каталоги и удаляют их при завершении.

До чтения допускаются только перечисленные в генераторе каталоги и форматы материалов; исходные каталоги корпуса плоские. Переходы `..`, посторонние абсолютные пути, скрытые файлы, symlink-компоненты и ссылки сообщений за пределы соответствующего каталога фото/ссылок отклоняются. Это применяется и к раннему чтению индексов, журнала восстановления и `sources.json`; ссылки на `.env`/SQLite не читаются даже при неуспешной генерации.

Снимок содержит {c['raw_telegram_records']} сырых Telegram-записи, {c['unique_telegram_messages']} уникальное сообщение ({c['link_messages']} ссылочных и {c['photo_messages']} фото), {c['unique_index_urls']} уникальный URL, {c['photo_files']} фото с {c['unique_photo_sha256']} разными SHA-256, {c['kb_files']} KB-файлов и {c['recovered_files']} recovered-файла. Всего учтено {c['inventoried_files']} файлов; отсутствует {c['missing_files']}; нарушений инвариантов {len(manifest['issues'])}.

Модель записей:

- `messages`: локальный `message_id`, номера строк сырых и dedup-индексов, исходный путь, путь в репозитории, SHA-256 оригинальных байтов и URL. `source=null` не превращается в выдуманный Telegram-канал или permalink.
- `files`: все фото/ссылочные файлы, KB, recovered, справочные CSV и снимки документов. `original_path_basis` объясняет, откуда взят исходный путь; для файлов без исторического пути сохранён текущий предоставленный путь. `identical_local_files` связывает копии по байтовому хешу, не считает их независимыми источниками.
- `urls`: 61 точная строка из индекса, сообщения с этой ссылкой и связанные локальные материалы. URL-хеш в ID идентифицирует строку, а не удалённый контент; SHA-256 контента хранится у локальных файлов. Ссылки внутри статей не расширяют эти 61 URL. Для URL без файла физический путь/хеш содержимого неизвестен.
- `completeness` описывает наблюдаемое наличие: ссылка, изображение, текст, отдельный пост, неполный тред, оболочка, ошибка, сводка или OCR. `full_original_verified=false` и `verification_status=unverified` применяются ко всем записям. Размер текста не доказывает полноту.
- `original_published_at` отделён от `imported_at`. Даты Telegram — импорт без timezone. `Recovered` — дата из исторического журнала, не время импорта KB-копии. Публикация заполняется только при явном `tweet.created_at` или `Published on`; это утверждения сохранённого источника с указанием доказательства. Неизвестные даты остаются `null`. Даты Wayback, диапазоны `DATED`, OCR и mtime не подставляются вместо публикации.
- `classification` допускает `methodology`, `historical_case`, `reference`, `unclassified`. Автоматически назначается только очевидный справочный тип; содержательная классификация и проверка методики ещё предстоят.

Ограничения и дальнейшая работа:

- `--check` подтверждает совпадение локального снимка и отсутствие перечисленных структурных ошибок. Он не проверяет актуальность сайтов, авторство, точность OCR, корректность утверждений или готовность публикации RU/EN.
- Оболочки Notion/Dune, 404 tweet, профиль Teletype вместо статьи и неполный Surf-тред отмечены отдельно. Восстановление Stacy «50/50» остаётся заявлением журнала. OCR остаётся машинной расшифровкой; общая сводка содержит ошибки по историческому отчёту. Их нельзя автоматически включать в проверенную методику.
- Связи recovered с URL опираются на журнал и точные URL/ID индекса либо canonical/tweet.url внутри снимка. При неоднозначности URL остаётся `null`. Связь одной страницы с несколькими исходниками и полная генеалогия преобразований пока не восстановлены.
- В манифест не входят рабочие БД, учётные данные, owner metadata, seed accounts и состояние сервера. Изменение генератора требует отдельной проверки; `--check` не является независимой приёмкой. Этот результат не подключает OCR к боту и не выполняет deployment.
- Базовые количества зафиксированы по предоставленному корпусу. При намеренном обновлении корпуса изменение `BASELINE_COUNTS`, JSON и доказательств должно пройти review; `--check` не принимает дрейф автоматически.

English: This deterministic local inventory preserves original bytes and source uncertainty. It separates publication from import dates and captured content from verified content. A passing check proves local reproducibility and structural consistency only; no source, OCR, methodology, bilingual publication or deployment is accepted by this script.
""".encode("utf-8")


def generated_outputs(manifest):
    return {OUTPUT_JSON: canonical_bytes(manifest), OUTPUT_MD: render_readme(manifest)}


def check_outputs(root, outputs):
    stale = []
    for relative, data in outputs.items():
        path = root / resolve_source_path(relative, root)
        if not path.is_file() or path.read_bytes() != data:
            stale.append(relative)
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="read-only comparison with checked-in outputs")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (defaults to this script's checkout)")
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(args.root)
    except (ManifestError, OSError, ValueError) as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return 1
    if manifest["issues"]:
        for issue in manifest["issues"]:
            print("Manifest issue: " + issue, file=sys.stderr)
        return 1
    outputs = generated_outputs(manifest)
    if args.check:
        try:
            stale = check_outputs(args.root, outputs)
        except ManifestError as exc:
            print(f"Manifest error: {exc}", file=sys.stderr)
            return 1
        if stale:
            print("Stale or missing generated output: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("Manifest OK: deterministic outputs match; 101 messages, 61 URLs, 53 unique photos; no structural issues.")
    else:
        for relative, data in outputs.items():
            path = args.root / resolve_source_path(relative, args.root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print("Wrote " + ", ".join(outputs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
