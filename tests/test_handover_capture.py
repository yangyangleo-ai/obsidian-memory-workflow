import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _common import SafetyError, sha256
import capture_source
import handover

ROOT = Path(__file__).resolve().parents[1]


class LocalFixture(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="obsidian-capture-test-"))
        self.vault = self.root / "vault"
        self.vault.mkdir()
        (self.vault / "state.md").write_text("fictional state: music permission unknown", encoding="utf-8")
        self.selection = self.root / "selection.json"
        self.selection.write_text(json.dumps({"schema_version": 1, "files": ["state.md"]}))
        self.clip = self.root / "excerpt.txt"
        self.clip.write_text("My reading note about a public document.", encoding="utf-8")

    def tearDown(self):
        assert self.root.name.startswith("obsidian-capture-test-")
        shutil.rmtree(self.root)

    def export(self, **kw):
        return handover.export_packet(self.vault, self.selection, kw.get("output", self.root / "packet"))

    def capture(self, **kw):
        return capture_source.capture(self.vault, self.clip,
                                      kw.pop("url", "https://example.com/public-docs"),
                                      kw.pop("title", "Fictional excerpt"), **kw)


class HandoverTests(LocalFixture):
    def test_export_is_local_bounded_and_not_model_tested(self):
        before = sha256(self.vault / "state.md")
        result = self.export()
        self.assertEqual(result["status"], "EXPORTED_NOT_MODEL_TESTED")
        self.assertEqual(sha256(self.vault / "state.md"), before)
        self.assertEqual(handover.verify_packet(self.vault, self.root / "packet")["status"], "UNCHANGED")

    def test_changed_source_marks_stale(self):
        self.export()
        (self.vault / "state.md").write_text("changed source", encoding="utf-8")
        self.assertEqual(handover.verify_packet(self.vault, self.root / "packet")["status"], "STALE")

    def test_unselected_note_does_not_expand_scope_or_stale_packet(self):
        self.export()
        (self.vault / "unselected.md").write_text("not in the allowed packet", encoding="utf-8")
        self.assertEqual(handover.verify_packet(self.vault, self.root / "packet")["status"], "UNCHANGED")
        self.assertNotIn("not in the allowed packet", (self.root / "packet/handover.md").read_text(encoding="utf-8"))

    def test_packet_tampering_is_rejected(self):
        self.export()
        (self.root / "packet/handover.md").write_text("edited", encoding="utf-8")
        with self.assertRaises(SafetyError):
            handover.verify_packet(self.vault, self.root / "packet")

    def test_output_is_exclusive_and_outside_vault(self):
        self.export()
        for output in [self.root / "packet", self.vault / "packet", self.root]:
            with self.subTest(output=output), self.assertRaises(SafetyError):
                self.export(output=output)

    def test_scope_rejects_traversal_hidden_missing_and_duplicates(self):
        for names in [["../secret.md"], [".obsidian/config.md"], ["missing.md"], ["state.md", "STATE.md"]]:
            self.selection.write_text(json.dumps({"schema_version": 1, "files": names}))
            with self.subTest(names=names), self.assertRaises(SafetyError):
                self.export()

    def test_size_and_credential_guard(self):
        for text in ["x" * 24001, "ghp_" + "x" * 36]:
            (self.vault / "state.md").write_text(text, encoding="utf-8")
            with self.assertRaises(SafetyError):
                self.export()

    def test_source_drift_aborts_before_output(self):
        with mock.patch.object(handover, "sha256", return_value="0" * 64), self.assertRaises(SafetyError):
            self.export()
        self.assertFalse((self.root / "packet").exists())

    def test_example_selection_resolves_and_retains_unknowns(self):
        selection = json.loads((ROOT / "examples/handover-selection.json").read_text(encoding="utf-8"))
        self.assertEqual(len(selection["files"]), 3)
        for name in selection["files"]:
            self.assertTrue(handover.scoped_file(ROOT / "vault-template", name).is_file())


class CaptureTests(LocalFixture):
    def test_preview_does_not_write(self):
        result = self.capture()
        self.assertEqual(result["status"], "PREVIEW")
        self.assertFalse((self.vault / "07-收件箱").exists())

    def test_capture_stays_unverified_and_points_to_excerpt_hash(self):
        result = self.capture(apply=True)
        self.assertEqual(result["status"], "CAPTURED_UNVERIFIED")
        text = (self.vault / result["relative"]).read_text(encoding="utf-8")
        self.assertIn('evidence_status: "unverified"', text)
        self.assertIn('last_verified: null', text)
        self.assertIn('source_accessed: null', text)
        self.assertIn('publish: false', text)
        self.assertIn('supplied-excerpt-file-not-whole-page', text)
        self.assertEqual(result["source_excerpt_sha256"], sha256(self.clip))

    def test_actual_access_date_is_explicit_not_capture_date(self):
        result = self.capture(accessed="2025-01-02")
        self.assertIn('source_accessed: "2025-01-02"', result["preview"])
        for date in ["2025-1-2", "not-a-date", "2999-01-01"]:
            with self.subTest(date=date), self.assertRaises((SafetyError, ValueError)):
                self.capture(accessed=date)

    def test_duplicate_does_not_overwrite_manual_triage(self):
        first = self.capture(apply=True)
        note = self.vault / first["relative"]
        note.write_text("manual triage", encoding="utf-8")
        again = self.capture(apply=True)
        self.assertEqual(again["status"], "ALREADY_PRESENT_REVIEW_EXISTING")
        self.assertEqual(note.read_text(), "manual triage")

    def test_changed_excerpt_keeps_separate_version(self):
        first = self.capture(apply=True)
        self.clip.write_text("another reviewed excerpt", encoding="utf-8")
        second = self.capture(apply=True)
        self.assertNotEqual(first["relative"], second["relative"])
        self.assertTrue((self.vault / first["relative"]).exists())

    def test_private_token_and_non_https_urls_rejected(self):
        for url in ["http://example.com", "https://localhost/private", "https://127.0.0.1/x",
                    "https://10.0.0.1/x", "https://example.com/?token=hidden", "https://user:pass@example.com/x",
                    "https://host.internal/x", "https://example.com/#token", "https://example.com:999/x"]:
            with self.subTest(url=url), self.assertRaises((SafetyError, ValueError)):
                self.capture(url=url)

    def test_title_cannot_add_yaml_fields(self):
        with self.assertRaises(SafetyError):
            self.capture(title="Title\npublish: true")

    def test_source_markup_cannot_become_active_embed(self):
        self.clip.write_text('![[private]] <iframe src="https://example.com"></iframe>\n```run', encoding="utf-8")
        result = self.capture(apply=True)
        text = (self.vault / result["relative"]).read_text(encoding="utf-8")
        self.assertNotIn('![[private]]', text)
        self.assertNotIn('<iframe', text)
        self.assertNotIn('\n```run', text)

    def test_empty_binary_and_oversized_input_rejected(self):
        for data in [b"", b"a\x00b", b"x" * 24001]:
            self.clip.write_bytes(data)
            with self.assertRaises(SafetyError):
                self.capture()

    def test_symlink_excerpt_rejected_when_allowed(self):
        link = self.root / "linked.txt"
        try:
            link.symlink_to(self.clip)
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(SafetyError):
            capture_source.capture(self.vault, link, "https://example.com/x", "source")


class ClipperStructureTests(unittest.TestCase):
    def test_official_trigger_only_matches_official_domains(self):
        spec = json.loads((ROOT / "examples/web-clipper/obsidian-docs.json").read_text(encoding="utf-8"))
        pattern = re.compile(spec["triggers"][0][1:-1])
        self.assertRegex("https://obsidian.md/help/bases", pattern)
        self.assertRegex("https://help.obsidian.md/bases", pattern)
        self.assertNotRegex("https://obsidian.md.example.com/help", pattern)
        self.assertNotRegex("https://obsidianXmd/help", pattern)

    def test_templates_are_selection_only_and_have_private_defaults(self):
        files = list((ROOT / "examples/web-clipper").glob("*.json"))
        self.assertEqual(len(files), 2)
        for file in files:
            spec = json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(spec["schemaVersion"], "0.1.0")
            self.assertEqual(spec["behavior"], "create")
            self.assertEqual(spec["path"], "07-收件箱/资料")
            self.assertNotIn("vault", spec)
            self.assertIn("{{selection", spec["noteContentFormat"])
            self.assertNotIn("{{content", spec["noteContentFormat"])
            self.assertNotIn('{{"', json.dumps(spec, ensure_ascii=False).replace('\\"', '"'))
            properties = {p["name"]: p for p in spec["properties"]}
            self.assertEqual(properties["publish"]["value"], "false")
            self.assertEqual(properties["publish"]["type"], "checkbox")
            self.assertEqual(properties["evidence_status"]["value"], "unverified")


if __name__ == "__main__":
    unittest.main()
