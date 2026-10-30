"""Chainwire v1 contract checks (CW-002b). Stdlib only; importable by tests and later storage/API code.

validate(): subset of JSON Schema 2020-12 used by chainwire.v1.schema.json.
invariants(): cross-entity rules JSON Schema cannot express.
Not covered here (handed off): retry timing / uncertain reconciliation flow -> CW-002d/e;
locale text vs fact values -> CW-004c.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

SCHEMA_PATH = Path(__file__).resolve().with_name("chainwire.v1.schema.json")
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

SUPPORTED = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "properties", "required",
             "additionalProperties", "items", "enum", "const", "pattern", "minLength", "minimum", "maximum",
             "minItems", "uniqueItems", "anyOf", "format"}
TYPES = {"object": dict, "array": list, "string": str, "null": type(None), "boolean": bool}


def _is_type(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[name])


def validate(value, schema=None, path="$"):
    """Return a list of error strings; empty means valid."""
    schema = SCHEMA if schema is None else schema
    unknown = set(schema) - SUPPORTED
    if unknown:
        raise AssertionError(f"validator lacks keywords {sorted(unknown)} at {path}")
    if "$ref" in schema:
        node = SCHEMA
        for part in schema["$ref"].removeprefix("#/").split("/"):
            node = node[part]
        return validate(value, node, path)
    errors = []
    if "anyOf" in schema:
        if all(validate(value, option, path) for option in schema["anyOf"]):
            errors.append(f"{path}: matches no anyOf branch")
        return errors
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, n) for n in names):
            return [f"{path}: expected {names}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: const")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: too short")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: pattern")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{path}: date-time")
    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True) for v in value]
            if len(seen) != len(set(seen)):
                errors.append(f"{path}: duplicate items")
        for i, item in enumerate(value):
            errors += validate(item, schema.get("items", {}), f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        errors += [f"{path}: missing {k}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            errors += [f"{path}: unexpected {k}" for k in value if k not in props]
        for k, v in value.items():
            if k in props:
                errors += validate(v, props[k], f"{path}.{k}")
    return errors


def delivery_key(revision_id, locale, destination):
    raw = json.dumps([revision_id, locale, destination], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ts(value):
    return None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))


def invariants(bundle):
    """Cross-entity rules (subset salvaged from the abandoned pydantic draft)."""
    errors = []
    ids = {zone: {item["id"]: item for item in bundle.get(zone, [])}
           for zone in ("sources", "events", "evidence", "projects", "assessments", "fact_packs", "revisions", "deliveries")}
    for zone, mapping in ids.items():
        if len(mapping) != len(bundle.get(zone, [])):
            errors.append(f"duplicate id in {zone}")

    def ref(zone, key):
        if key not in ids[zone]:
            errors.append(f"missing {zone} reference {key}")
            return None
        return ids[zone][key]

    for e in bundle.get("events", []):
        for k in e["source_ids"]: ref("sources", k)
        for k in e.get("project_ids", []): ref("projects", k)
    for item in bundle.get("evidence", []):
        ev = ref("events", item["event_id"]); ref("sources", item["source_id"])
        if ev and item["source_id"] not in ev["source_ids"]:
            errors.append("evidence source not in its event")
        checked = item["checked_by"] is not None and item["checked_at"] is not None
        if (item["status"] == "unverified") == checked or (item["status"] == "unverified" and item["checked_at"]):
            errors.append(f"evidence {item['id']} verification audit inconsistent")
    for p in bundle.get("projects", []):
        for a in p["addresses"]:
            if a["network"] not in p["networks"]:
                errors.append(f"project {p['id']} address on undeclared network")
    for a in bundle.get("assessments", []):
        ref("projects", a["project_id"])
        for k in a["evidence_ids"]: ref("evidence", k)
    for fp in bundle.get("fact_packs", []):
        ref("events", fp["event_id"])
        fact_ids = [f["id"] for f in fp["facts"]]
        if len(fact_ids) != len(set(fact_ids)):
            errors.append(f"duplicate fact id in fact pack {fp['id']}")
        for k in fp.get("project_ids", []): ref("projects", k)
        for k in fp.get("assessment_ids", []): ref("assessments", k)
        for f in fp["facts"]:
            for k in f["evidence_ids"]:
                e = ref("evidence", k)
                if e and e["event_id"] != fp["event_id"]:
                    errors.append("fact evidence from another event")
    locales = {}
    for loc in bundle.get("locales", []):
        pair = (loc["revision_id"], loc["locale"])
        if pair in locales:
            errors.append(f"duplicate locale {pair}")
        locales[pair] = loc
        rev = ref("revisions", loc["revision_id"])
        if rev and rev["fact_pack_id"] != loc["fact_pack_id"]:
            errors.append("locale uses another fact pack than its revision")
        pack = ids["fact_packs"].get(loc["fact_pack_id"])
        if pack is None:
            errors.append(f"missing fact_packs reference {loc['fact_pack_id']}")
        else:
            known = {f["id"] for f in pack["facts"]}
            for k in loc["fact_ids"]:
                if k not in known:
                    errors.append(f"locale {pair} references unknown fact {k}")
        if (loc["review_status"] == "approved") != (loc["reviewed_by"] is not None and loc["reviewed_at"] is not None):
            errors.append("locale review audit inconsistent")
    for rev in bundle.get("revisions", []):
        pack = ref("fact_packs", rev["fact_pack_id"])
        if (rev["revision"] == 1) != (rev["supersedes_id"] is None):
            errors.append("revision predecessor rule")
        if rev["supersedes_id"] is not None:
            prev = ref("revisions", rev["supersedes_id"])
            if prev and (prev["article_id"] != rev["article_id"] or prev["revision"] != rev["revision"] - 1):
                errors.append("invalid revision predecessor")
        if (rev["status"] == "approved") != (rev["approved_by"] is not None and rev["approved_at"] is not None):
            errors.append("revision approval audit inconsistent")
        if rev["status"] == "approved" and pack:
            for lang in ("ru", "en"):
                loc = locales.get((rev["id"], lang))
                if loc is None or loc["review_status"] != "approved":
                    errors.append(f"approved revision needs reviewed {lang}")
                elif set(loc["fact_ids"]) != {f["id"] for f in pack["facts"]}:
                    errors.append(f"{lang} locale must use the full shared fact pack")
    keys = set()
    for d in bundle.get("deliveries", []):
        rev = ref("revisions", d["revision_id"])
        if d["idempotency_key"] != delivery_key(d["revision_id"], d["locale"], d["destination"]):
            errors.append(f"delivery {d['id']} key != revision x locale x destination")
        if d["idempotency_key"] in keys:
            errors.append("duplicate delivery key")
        keys.add(d["idempotency_key"])
        loc = locales.get((d["revision_id"], d["locale"]))
        if rev and (rev["status"] != "approved" or loc is None or loc["review_status"] != "approved"):
            errors.append("delivery requires approved revision with an approved locale")
        if ts(d["updated_at"]) < ts(d["created_at"]) or ts(d["available_at"]) < ts(d["created_at"]):
            errors.append("delivery timestamps precede creation")
        s = d["state"]
        if (s == "pending") != (d["attempts"] == 0):
            errors.append("pending iff no attempts")
        if (s == "leased") != (d["lease_owner"] is not None and d["lease_until"] is not None):
            errors.append("lease fields only for leased")
        if s == "leased" and ts(d["lease_until"]) <= ts(d["updated_at"]):
            errors.append("lease must expire after update")
        if (s == "succeeded") != (d["external_receipt"] is not None):
            errors.append("receipt only and always for succeeded")
        if s in ("retryable", "uncertain") and d["last_error"] is None:
            errors.append("retryable/uncertain need last_error")
        r = d["reconciliation"]
        if r and r["outcome"] == "delivered" and s != "succeeded":
            errors.append("reconciled delivered must be succeeded")
        if r and r["outcome"] == "not_delivered" and s == "succeeded":
            errors.append("reconciled not_delivered cannot be succeeded")
    return errors
