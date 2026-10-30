"""CW-001b: corrections layer references originals by path+SHA and keeps arithmetic honest."""

import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals/fixtures/corrections/corrections.json"
MANIFEST = ROOT / "docs/research/materials-manifest.json"
OCR = ROOT / "docs/reference/chainwire-images-ocr.jsonl"


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


class Corrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.by_id = {c["id"]: c for c in cls.data["corrections"]}
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.manifest = {f["resolved_path"]: f["sha256"] for f in manifest["files"]}
        cls.ocr = {json.loads(l)["file"]: json.loads(l)["text"] for l in OCR.read_text(encoding="utf-8").splitlines() if l.strip()}

    def refs(self):
        for c in self.data["corrections"]:
            yield c["source"]["path"], c["source"]["sha256"]
            if "distorted_copy" in c:
                yield c["distorted_copy"]["path"], c["distorted_copy"]["sha256"]
            for d in c.get("ocr_discrepancies", []):
                yield d["ocr_path"], d["ocr_sha256"]

    def test_references_match_manifest_and_unmodified_bytes(self):
        for path, digest in self.refs():
            self.assertEqual(self.manifest.get(path), digest, path)
            self.assertEqual(sha(path), digest, path)

    def test_original_claims_still_present(self):
        art = (ROOT / "research-bot/data/kb/article_05.txt").read_text(encoding="utf-8")
        self.assertIn(self.by_id["COR-002"]["claim_in_source"]["quote"], art)
        notes = (ROOT / "research-bot/data/kb/screenshots_notes.md").read_text(encoding="utf-8")
        self.assertIn(self.by_id["COR-003"]["distorted_copy"]["quote"], notes)
        self.assertIn(self.by_id["COR-004"]["claim_in_source"]["quote"], notes)

    def test_ocr_discrepancies_recorded_against_ocr_text(self):
        for cid, image in (("COR-001", "16.jpg"), ("COR-003", "94.jpg")):
            for d in self.by_id[cid]["ocr_discrepancies"]:
                self.assertIn(d["ocr_text"], self.ocr[image])
            self.assertEqual(self.by_id[cid]["visual_check"]["status"], "visually_checked")

    def test_amm_constant_product(self):
        c = self.by_id["COR-001"]
        i, r = c["inputs"], c["corrected"]
        k = i["pool_tokens"] * i["pool_quote_usd"]
        quote_after = i["pool_quote_usd"] + i["buy_usd"]
        tokens_after = k / quote_after
        self.assertEqual(quote_after, r["pool_quote_after_usd"])
        self.assertEqual(tokens_after, r["pool_tokens_after"])
        self.assertEqual(i["pool_tokens"] - tokens_after, r["tokens_out"])
        self.assertAlmostEqual(quote_after / tokens_after, r["final_price_usd"])
        self.assertAlmostEqual(i["pool_quote_usd"] / i["pool_tokens"], r["initial_price_usd"])
        self.assertAlmostEqual(r["final_price_usd"] / r["initial_price_usd"], r["multiple"])
        self.assertNotEqual(c["claim_in_source"]["final_price_usd"], r["final_price_usd"])

    def test_supply_growth(self):
        c = self.by_id["COR-002"]
        a, b = c["inputs"]["circulating_share_percent"], c["inputs"]["target_share_percent"]
        self.assertAlmostEqual((b / a - 1) * 100, c["corrected"]["growth_percent"])
        self.assertEqual(b - a, c["corrected"]["percentage_points"])
        self.assertEqual(c["corrected"]["growth_percent"], 150)

    def test_wallet_figures_preserved(self):
        c = self.by_id["COR-003"]["corrected"]
        self.assertEqual((c["wallets_total"], c["wallets_qualified"]), (660000, 66000))
        self.assertEqual(c["threshold"], {"metric": "volume_usd", "gt": 20})
        self.assertIn(self.by_id["COR-003"]["ocr_preserves"]["quote"], self.ocr["94.jpg"])

    def test_layerzero_date_unverified(self):
        c = self.by_id["COR-004"]
        self.assertEqual(c["status"], "unverified")
        self.assertIsNone(c["confirmed_date"])
        self.assertIsNone(c["primary_source"])


if __name__ == "__main__":
    unittest.main()
