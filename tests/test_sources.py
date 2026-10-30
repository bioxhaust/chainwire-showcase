"""CW-004a: source catalog is complete, honest about availability and uses CAIP-2 ids."""

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "sources/catalog.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schemas/chainwire.v1.schema.json").read_text(encoding="utf-8"))
CATEGORIES = {"official_project", "regulator", "security", "funding", "exchange", "media_context", "data_api", "context_research"}
TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class SourceCatalog(unittest.TestCase):
    src = CATALOG["sources"]

    def test_size_and_unique_ids(self):
        self.assertTrue(20 <= len(self.src) <= 30)
        self.assertEqual(len({s["id"] for s in self.src}), len(self.src))

    def test_required_fields(self):
        for s in self.src:
            self.assertIn(s["category"], CATEGORIES, s["id"])
            self.assertIn(s["language"], {"ru", "en"}, s["id"])
            self.assertIn(s["endpoint"]["kind"], {"rss", "atom", "api", "page"}, s["id"])
            self.assertTrue(s["endpoint"]["url"].startswith("https://"), s["id"])
            self.assertIn("observed", s["limits"]); self.assertIn("documented", s["limits"])

    def test_both_languages(self):
        self.assertTrue({"ru", "en"} <= {s["language"] for s in self.src})

    def test_coverage(self):
        topics = {t for s in self.src for t in s["topics"]}
        cats = {s["category"] for s in self.src}
        for t in ("bitcoin", "ethereum", "l2", "solana", "other_l1", "regulation", "security", "funding", "exchange"):
            self.assertIn(t, topics)
        self.assertTrue({"regulator", "security", "funding", "exchange", "official_project"} <= cats)

    def test_caip2_network_ids(self):
        pattern = re.compile(SCHEMA["$defs"]["NetworkId"]["pattern"])
        for s in self.src:
            for n in s["networks"]:
                self.assertRegex(n, pattern, s["id"])

    def test_availability_not_invented(self):
        for s in self.src:
            a = s["availability"]
            self.assertRegex(a["checked_at"], TS)
            self.assertIsInstance(a["http_status"], int)
            self.assertEqual(a["status"] == "responded", a["http_status"] == 200, s["id"])
            self.assertIn(a["status"], {"responded", "unverified"})

    def test_rights_unverified_until_reviewed(self):
        for s in self.src:
            self.assertEqual(s["terms"]["status"], "unverified", s["id"])
            self.assertIsNone(s["terms"]["reuse_rights"], s["id"])
            self.assertIsNone(s["terms"]["url"], s["id"])
            self.assertIsNone(s["limits"]["documented"], s["id"])

    def test_policy_counts_match_catalog(self):
        text = (ROOT / "docs/editorial/source-policy.md").read_text(encoding="utf-8")
        m = re.search(r"Итого: (\d+) источников; ответили 200: (\d+); не подтверждены: (\d+); RU: (\d+); EN: (\d+)\.", text)
        self.assertIsNotNone(m)
        src = CATALOG["sources"]
        responded = sum(s["availability"]["status"] == "responded" for s in src)
        expected = (len(src), responded, len(src) - responded,
                    sum(s["language"] == "ru" for s in src), sum(s["language"] == "en" for s in src))
        self.assertEqual(tuple(map(int, m.groups())), expected)

    def test_coverage_gaps_documented(self):
        text = (ROOT / "docs/editorial/source-policy.md").read_text(encoding="utf-8")
        gaps = text.split("## Пробелы покрытия", 1)[1]
        for name in ("Polkadot", "Optimism", "Cosmos", "TON", "Avalanche", "FATF", "CW-004a2"):
            self.assertIn(name, gaps)


if __name__ == "__main__":
    unittest.main()
