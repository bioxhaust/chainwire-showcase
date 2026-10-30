"""CW-002b: contract examples validate against schemas/chainwire.v1.schema.json via schemas/chainwire_contract.py."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "schemas"))
from chainwire_contract import SCHEMA, delivery_key, invariants, validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "docs/contracts/examples/bundle.ru-en.json").read_text(encoding="utf-8"))
class ContractExampleTest(unittest.TestCase):
    def test_example_validates_against_schema(self):
        self.assertEqual(validate(EXAMPLE, SCHEMA), [])

    def test_example_invariants(self):
        self.assertEqual(invariants(EXAMPLE), [])

    def test_ru_and_en_examples_present_and_separate(self):
        langs = {loc["locale"] for loc in EXAMPLE["locales"]}
        self.assertTrue({"ru", "en"} <= langs)
        by_lang = {d["locale"]: [] for d in EXAMPLE["deliveries"]}
        for d in EXAMPLE["deliveries"]:
            by_lang[d["locale"]].append(d["state"])
        self.assertIn("succeeded", by_lang["ru"])
        self.assertIn("retryable", by_lang["en"])  # RU success / EN failure kept apart

    def test_all_delivery_states_exist_and_nothing_else(self):
        states = SCHEMA["$defs"]["Delivery"]["properties"]["state"]["enum"]
        self.assertEqual(states, ["pending", "leased", "succeeded", "retryable", "uncertain"])
        self.assertEqual({d["state"] for d in EXAMPLE["deliveries"]}, set(states))

    def test_entities_are_separate_definitions(self):
        for name in ("Source", "Event", "Evidence", "Project", "Assessment", "ArticleRevision", "LocaleVersion", "Delivery"):
            self.assertIn(name, SCHEMA["$defs"])

    def test_networks_are_open_ids_not_enum(self):
        project = copy.deepcopy(EXAMPLE)
        p = project["projects"][0]
        for net in ("bip122:000000000019d6689c085ae165831e93", "aptos:mainnet", "starknet:SN_MAIN", "newchain:42"):
            p["networks"].append(net)
        p["ecosystems"].append("some-future-ecosystem")
        self.assertEqual(validate(project, SCHEMA), [])
        p["networks"].append("Solana")  # bare names are rejected: namespace:reference required
        self.assertTrue(validate(project, SCHEMA))

    def test_unknown_is_null_not_zero(self):
        bundle = copy.deepcopy(EXAMPLE)
        fact = bundle["fact_packs"][0]["facts"][1]
        self.assertIsNone(fact["value"])
        self.assertIsNone(bundle["assessments"][0]["risk"])
        del fact["value"]  # unknown must be explicit null, not omitted
        self.assertTrue(validate(bundle, SCHEMA))

    def test_delivery_key_is_revision_locale_destination(self):
        bundle = copy.deepcopy(EXAMPLE)
        bundle["deliveries"][0]["locale"] = "en"
        self.assertTrue(any("key" in e for e in invariants(bundle)))
        bundle = copy.deepcopy(EXAMPLE)
        dup = copy.deepcopy(bundle["deliveries"][0]); dup["id"] = "dlv-dup"
        bundle["deliveries"].append(dup)
        self.assertIn("duplicate delivery key", invariants(bundle))

    def test_negative_cases_rejected(self):
        cases = [
            ("deliveries", 0, "state", "sent"),
            ("deliveries", 0, "external_receipt", None),
            ("revisions", 0, "approved_by", None),
            ("evidence", 0, "status", "unverified"),
        ]
        for zone, idx, field, value in cases:
            bundle = copy.deepcopy(EXAMPLE)
            bundle[zone][idx][field] = value
            self.assertTrue(validate(bundle, SCHEMA) or invariants(bundle), (zone, field, value))
        bundle = copy.deepcopy(EXAMPLE)
        bundle["locales"] = [l for l in bundle["locales"] if l["locale"] != "en"]
        self.assertTrue(invariants(bundle))

    def assertCaught(self, mutate, label):
        bundle = copy.deepcopy(EXAMPLE)
        mutate(bundle)
        self.assertTrue(validate(bundle, SCHEMA) or invariants(bundle), label)

    def test_fact_kind_bound_to_value(self):
        fact = lambda b: b["fact_packs"][0]["facts"][0]["value"]
        self.assertCaught(lambda b: fact(b).update(value="abc"), "integer with text")
        self.assertCaught(lambda b: fact(b).update(kind="timestamp", value="nope"), "bad timestamp")
        self.assertCaught(lambda b: fact(b).update(kind="decimal", value=1.5), "decimal must be string")
        self.assertCaught(lambda b: fact(b).update(kind="boolean", value="true"), "boolean as text")

    def test_duplicate_fact_id_in_pack(self):
        self.assertCaught(lambda b: b["fact_packs"][0]["facts"].append(copy.deepcopy(b["fact_packs"][0]["facts"][0])), "dup fact")

    def test_dangling_references(self):
        def draft_locale(b, **kw):
            loc = dict(copy.deepcopy(b["locales"][0]), locale="de", review_status="draft", reviewed_by=None, reviewed_at=None)
            loc.update(kw)
            b["locales"].append(loc)
        self.assertCaught(lambda b: draft_locale(b, fact_ids=["ghost"]), "draft locale unknown fact")
        self.assertCaught(lambda b: b["revisions"].append(dict(copy.deepcopy(b["revisions"][0]), id="r2", revision=2,
                          supersedes_id="ghost", status="draft", approved_by=None, approved_at=None)), "supersedes ghost")
        self.assertCaught(lambda b: b["fact_packs"][0]["project_ids"].append("ghost"), "pack project ghost")
        self.assertCaught(lambda b: b["fact_packs"][0]["assessment_ids"].append("ghost"), "pack assessment ghost")

    def test_delivery_requires_approved_locale(self):
        def mutate(b):
            loc = dict(copy.deepcopy(b["locales"][0]), locale="de", review_status="draft", reviewed_by=None, reviewed_at=None)
            b["locales"].append(loc)
            d = copy.deepcopy(b["deliveries"][0])
            d.update(id="dlv-de", locale="de", idempotency_key=delivery_key(d["revision_id"], "de", d["destination"]))
            b["deliveries"].append(d)
        self.assertCaught(mutate, "delivery to draft locale")

    def test_succeeded_cannot_be_reconciled_not_delivered(self):
        self.assertCaught(lambda b: b["deliveries"][0].update(reconciliation={"outcome": "not_delivered",
                          "checked_by": "op", "checked_at": "2026-10-30T10:21:30Z", "proof": "p"}), "succeeded+not_delivered")

    def test_network_id_is_caip2_sized(self):
        self.assertCaught(lambda b: b["projects"][0]["networks"].append("toolongnamespace:1"), "namespace >8")
        self.assertCaught(lambda b: b["projects"][0]["networks"].append("eip155:" + "1" * 33), "reference >32")


if __name__ == "__main__":
    unittest.main()
