"""Regression checks for evidence loss, false certainty and manifest drift."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("materials_manifest", ROOT / "scripts/materials_manifest.py")
manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manifest)


class CorpusFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chainwire-manifest-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [
            {"message_id": 5, "type": "link", "source": None, "caption": "", "text": "https://example.org/article",
             "urls": ["https://example.org/article"], "path": "/workspace/web3-engine/telegram-corpus/links/5.txt", "date": "2026-10-29T17:29:36"},
            {"message_id": 14, "type": "photo", "source": None, "caption": "", "text": "", "urls": [],
             "path": "/workspace/web3-engine/telegram-corpus/photos/14.jpg", "date": "2026-10-29T17:29:36"},
        ]
        self.write_indexes()
        self.write("telegram-corpus/links/5.txt", "https://example.org/article\n")
        self.write("telegram-corpus/links/all_links.txt", "https://example.org/article\nhttps://example.org/article\n")
        self.write("telegram-corpus/photos/14.jpg", b"\xff\xd8example binary photo\xff\xd9")
        self.write("research-bot/data/kb/article_01.txt", "SOURCE: https://example.org/article\nDATED: historical (2021-2025)\n\nA captured article.\n")
        self.write("recovered/README.txt", "Recovered 2026-10-29:\n")
        refs = []
        for name in ("chainwire-brand-plan.md", "chainwire-materials-and-server.md", "chainwire-images-ocr.md"):
            content = "Supplied reference " + name + "\n"
            self.write("docs/reference/" + name, content)
            refs.append({"file": name, "source": "/original/location/" + name, "sha256": manifest.sha256(content.encode())})
        self.write("docs/reference/sources.json", json.dumps(refs))

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))

    def write_indexes(self, raw=None, dedup=None):
        raw = [row for row in self.rows for _ in range(2)] if raw is None else raw
        dedup = self.rows if dedup is None else dedup
        for relative, records in (("telegram-corpus/index.jsonl", raw), ("index_dedup.jsonl", dedup)):
            self.write(relative, "".join(json.dumps(row) + "\n" for row in records))

    def build(self, expected=None):
        return manifest.build_manifest(self.root, expected_counts={} if expected is None else expected)

    def file(self, result, relative):
        return next(f for f in result["files"] if f["resolved_path"] == relative)

    @contextlib.contextmanager
    def forbid_content_reads(self, target):
        """An attempted read fails the test, even if the manifest later errors."""
        original_bytes = Path.read_bytes
        original_text = Path.read_text
        target = target.resolve()

        def guard(reader):
            def checked(path, *args, **kwargs):
                if path.resolve() == target:
                    raise AssertionError("Excluded synthetic target was read")
                return reader(path, *args, **kwargs)
            return checked

        with patch.object(Path, "read_bytes", guard(original_bytes)), patch.object(Path, "read_text", guard(original_text)):
            yield

    def test_legacy_paths_resolve_without_modifying_originals(self):
        before = (self.root / "index_dedup.jsonl").read_bytes()
        result = self.build()
        message = result["messages"][1]
        self.assertEqual(message["original_path"], self.rows[1]["path"])
        self.assertEqual(message["resolved_path"], "telegram-corpus/photos/14.jpg")
        self.assertEqual(message["sha256"], manifest.sha256((self.root / message["resolved_path"]).read_bytes()))
        self.assertEqual((self.root / "index_dedup.jsonl").read_bytes(), before)
        self.assertEqual(result["issues"], [])

    def test_unknown_absolute_and_escaping_paths_are_rejected(self):
        for path in ("/unknown/machine/photo.jpg", "../../outside", "/workspace/web3-engine/../outside", "telegram-corpus/../other"):
            with self.subTest(path=path), self.assertRaises(manifest.ManifestError):
                manifest.resolve_source_path(path, self.root)

    def test_external_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="chainwire-outside-test-") as outside:
            (self.root / "outside-link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(manifest.ManifestError):
                manifest.resolve_source_path("outside-link/file", self.root)

    def test_disallowed_message_path_is_rejected_before_content_read(self):
        for relative in ("research-bot/.env", "research-bot/data/bot.sqlite"):
            with self.subTest(path=relative):
                self.write(relative, "SYNTHETIC_TEST_ONLY=\n")
                self.rows[0]["path"] = "/workspace/web3-engine/" + relative
                self.write_indexes()
                with self.forbid_content_reads(self.root / relative), self.assertRaises(manifest.ManifestError):
                    self.build()

    def test_corpus_internal_symlink_cannot_read_excluded_target(self):
        self.write("research-bot/.env", "SYNTHETIC_TEST_ONLY=\n")
        photo = self.root / "telegram-corpus/photos/14.jpg"
        photo.unlink()
        photo.symlink_to(self.root / "research-bot/.env")
        with self.forbid_content_reads(self.root / "research-bot/.env"), self.assertRaisesRegex(manifest.ManifestError, "Symlink"):
            self.build()

    def test_early_input_symlinks_are_rejected_before_read(self):
        self.write("research-bot/.env", "SYNTHETIC_TEST_ONLY=\n")
        target = self.root / "research-bot/.env"
        for relative in ("index_dedup.jsonl", "telegram-corpus/index.jsonl", "docs/reference/sources.json", "recovered/README.txt",
                         "docs/reference/chainwire-brand-plan.md"):
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.unlink()
                path.symlink_to(target)
                try:
                    with self.forbid_content_reads(target), self.assertRaisesRegex(manifest.ManifestError, "Symlink"):
                        self.build()
                finally:
                    path.unlink()
                    path.write_bytes(original)

    def test_external_file_symlink_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory(prefix="chainwire-external-read-test-") as outside:
            target = Path(outside) / "harmless-fixture.txt"
            target.write_text("SYNTHETIC_TEST_ONLY\n")
            path = self.root / "research-bot/data/kb/article_01.txt"
            path.unlink()
            path.symlink_to(target)
            with self.forbid_content_reads(target), self.assertRaisesRegex(manifest.ManifestError, "Symlink"):
                self.build()

    def test_input_directory_symlink_is_rejected_before_traversal(self):
        original = self.root / "recovered"
        original.rename(self.root / "saved-recovered")
        original.symlink_to(self.root / "saved-recovered", target_is_directory=True)
        with self.forbid_content_reads(self.root / "saved-recovered/README.txt"), self.assertRaisesRegex(manifest.ManifestError, "Symlink"):
            self.build()

    def test_reference_index_cannot_request_an_environment_file(self):
        self.write("docs/reference/.env", "SYNTHETIC_TEST_ONLY=\n")
        sources = json.loads((self.root / "docs/reference/sources.json").read_text())
        sources.append({"file": ".env", "source": "untrusted-input", "sha256": "not-relevant"})
        self.write("docs/reference/sources.json", json.dumps(sources))
        with self.forbid_content_reads(self.root / "docs/reference/.env"), self.assertRaisesRegex(manifest.ManifestError, "allowed material inputs"):
            self.build()

    def test_unlisted_environment_file_in_recovered_is_never_read(self):
        self.write("recovered/.env", "SYNTHETIC_TEST_ONLY=\n")
        with self.forbid_content_reads(self.root / "recovered/.env"), self.assertRaisesRegex(manifest.ManifestError, "allowed material inputs"):
            self.build()

    def test_generated_output_symlink_is_rejected_before_check_read(self):
        outputs = manifest.generated_outputs(self.build())
        self.write("research-bot/.env", "SYNTHETIC_TEST_ONLY=\n")
        output = self.root / manifest.OUTPUT_JSON
        output.parent.mkdir(parents=True)
        output.symlink_to(self.root / "research-bot/.env")
        with self.forbid_content_reads(self.root / "research-bot/.env"), self.assertRaisesRegex(manifest.ManifestError, "Symlink"):
            manifest.check_outputs(self.root, outputs)

    def test_identical_raw_duplicates_are_counted_not_lost(self):
        result = self.build()
        self.assertEqual(result["counts"]["raw_telegram_records"], 4)
        self.assertEqual(result["counts"]["duplicate_raw_records"], 2)
        self.assertEqual(result["raw_occurrences_per_message"], {"2": 2})
        self.assertEqual(result["messages"][0]["raw_index_lines"], [1, 2])

    def test_conflicting_duplicates_cannot_be_silently_deduplicated(self):
        changed = dict(self.rows[0], text="a conflicting capture")
        self.write_indexes(raw=[self.rows[0], changed, self.rows[1]])
        with self.assertRaisesRegex(manifest.ManifestError, "Conflicting duplicate"):
            self.build()

    def test_duplicate_in_dedup_index_is_reported(self):
        self.write_indexes(dedup=self.rows + [self.rows[0]])
        self.assertIn("Deduplicated index still contains duplicate message IDs", self.build()["issues"])

    def test_raw_and_dedup_disagreement_is_reported(self):
        self.write_indexes(raw=self.rows[:1])
        self.assertIn("Raw and deduplicated message records differ", self.build()["issues"])

    def test_missing_message_file_retains_path_and_null_hash(self):
        (self.root / "telegram-corpus/photos/14.jpg").unlink()
        result = self.build()
        record = self.file(result, "telegram-corpus/photos/14.jpg")
        self.assertFalse(record["exists"])
        self.assertIsNone(record["sha256"])
        self.assertEqual(record["completeness"]["status"], "missing")
        self.assertIn("Missing file: telegram-corpus/photos/14.jpg", result["issues"])

    def test_missing_kb_file_breaks_expected_coverage(self):
        (self.root / "research-bot/data/kb/article_01.txt").unlink()
        self.assertIn("Baseline count kb_files: expected 1, found 0", self.build({"kb_files": 1})["issues"])

    def test_missing_index_is_a_clear_error(self):
        (self.root / "index_dedup.jsonl").unlink()
        with self.assertRaisesRegex(manifest.ManifestError, "Missing or unreadable input"):
            self.build()

    def test_import_date_never_becomes_original_publication(self):
        result = self.build()
        message = result["messages"][0]
        self.assertEqual(message["imported_at"], "2026-10-29T17:29:36")
        self.assertIsNone(message["original_published_at"])
        self.assertIsNone(message["source_identity"]["url"])
        kb = self.file(result, "research-bot/data/kb/article_01.txt")
        self.assertIsNone(kb["original_published_at"])
        self.assertIsNone(kb["imported_at"])
        self.assertEqual(kb["reported_date_label"], "historical (2021-2025)")

    def test_source_url_and_precise_date_require_explicit_evidence(self):
        self.write("recovered/tw_123.json", json.dumps({"code": 200, "tweet": {"url": "https://example.org/post/123", "created_at": "Fri Mar 31 12:37:36 +0000 2023"}}))
        record = self.file(self.build(), "recovered/tw_123.json")
        self.assertEqual(record["original_published_at"], "2023-03-31T12:37:36+00:00")
        self.assertEqual(record["imported_at"], "2026-10-29")
        self.assertEqual(record["source_identity"]["url"], "https://example.org/post/123")
        self.assertEqual(record["completeness"]["status"], "single_post_captured")
        self.assertEqual(record["verification_status"], "unverified")

    def test_shell_error_partial_thread_and_ocr_never_become_complete(self):
        self.write("recovered/notion_123.json", '{"recordMap":{"__version__":3}}')
        self.write("recovered/tw_456.json", '{"code":404,"message":"NOT_FOUND","tweet":null}')
        self.write("recovered/thread_surfer.txt", "@somebody A reply, not the methodology thread.\n")
        result = self.build()
        expected = {"recovered/notion_123.json": "shell_only", "recovered/tw_456.json": "error_response",
                    "recovered/thread_surfer.txt": "partial_thread", "docs/reference/chainwire-images-ocr.md": "machine_transcription_unverified"}
        for path, state in expected.items():
            with self.subTest(path=path):
                record = self.file(result, path)
                self.assertEqual(record["completeness"]["status"], state)
                self.assertFalse(record["completeness"]["full_original_verified"])
                self.assertEqual(record["verification_status"], "unverified")

    def test_duplicate_photos_and_unmapped_photos_are_reported(self):
        self.write("telegram-corpus/photos/15.jpg", (self.root / "telegram-corpus/photos/14.jpg").read_bytes())
        issues = self.build()["issues"]
        self.assertIn("Photo files contain identical SHA-256 values", issues)
        self.assertIn("Photo files and photo-message paths are not a one-to-one set", issues)

    def test_all_links_must_match_index_urls(self):
        self.write("telegram-corpus/links/all_links.txt", "https://unexpected.example/\n")
        self.assertIn("all_links.txt URL set differs from deduplicated index", self.build()["issues"])

    def test_snapshot_hash_mismatch_is_reported(self):
        self.write("docs/reference/chainwire-brand-plan.md", "Changed snapshot\n")
        self.assertIn("Reference snapshot hash differs: docs/reference/chainwire-brand-plan.md", self.build()["issues"])

    def test_new_reference_snapshots_are_included_from_source_index(self):
        content = '{"image":"14.jpg","text":"unverified OCR"}\n'
        self.write("docs/reference/chainwire-images-ocr.jsonl", content)
        sources = json.loads((self.root / "docs/reference/sources.json").read_text())
        sources.append({"file": "chainwire-images-ocr.jsonl", "source": "/original/ocr.jsonl", "sha256": manifest.sha256(content.encode())})
        self.write("docs/reference/sources.json", json.dumps(sources))
        result = self.build()
        record = self.file(result, "docs/reference/chainwire-images-ocr.jsonl")
        self.assertEqual(result["issues"], [])
        self.assertEqual(record["original_path"], "/original/ocr.jsonl")
        self.assertEqual(record["completeness"]["status"], "machine_transcription_unverified")

    def test_output_ignores_mtime_and_unrelated_runtime_files(self):
        before = manifest.generated_outputs(self.build())
        for path in self.root.rglob("*"):
            if path.is_file():
                os.utime(path, (1234567, 7654321))
        self.write("research-bot/data/bot.sqlite", b"not a database; must not be read")
        self.write("research-bot/.env", "DO_NOT_READ=private\n")
        self.write("docs/status.md", "Unrelated integration update\n")
        self.assertEqual(manifest.generated_outputs(self.build()), before)

    def test_stale_generated_outputs_are_detected_without_writes(self):
        outputs = manifest.generated_outputs(self.build())
        for path, data in outputs.items():
            self.write(path, data)
        self.assertEqual(manifest.check_outputs(self.root, outputs), [])
        self.write(manifest.OUTPUT_JSON, b"{}\n")
        self.write(manifest.OUTPUT_MD, b"stale\n")
        self.assertEqual(set(manifest.check_outputs(self.root, outputs)), set(outputs))
        self.assertEqual((self.root / manifest.OUTPUT_JSON).read_bytes(), b"{}\n")
        self.assertEqual((self.root / manifest.OUTPUT_MD).read_bytes(), b"stale\n")


class CheckedInSnapshot(unittest.TestCase):
    def test_checked_in_outputs_match_current_corpus_and_are_read_only(self):
        # This test makes ordinary unittest discovery fail on stale generated files.
        before = {p: (ROOT / p).read_bytes() for p in (manifest.OUTPUT_JSON, manifest.OUTPUT_MD)}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = manifest.main(["--check", "--root", str(ROOT)])
        self.assertEqual(code, 0, "Run python3 scripts/materials_manifest.py --check for diagnostics")
        self.assertEqual(before, {p: (ROOT / p).read_bytes() for p in before})


if __name__ == "__main__":
    unittest.main()
