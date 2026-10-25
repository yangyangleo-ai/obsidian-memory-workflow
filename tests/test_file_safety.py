import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _common import SafetyError, checked_path, extended, inventory, relative_name, sha256
import safe_write
import vault_backup


class Isolated(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="obsidian-workflow-test-"))
        self.source = self.root / "vault"
        self.source.mkdir()
        (self.source / "note.md").write_text("fictional original\n", encoding="utf-8")
        self.target = self.root / "mirror"
        self.receipts = self.root / "control" / "receipts"

    def tearDown(self):
        # Only this test's newly created temporary tree; never a user's vault.
        assert self.root.name.startswith("obsidian-workflow-test-")
        shutil.rmtree(extended(self.root))


class BackupTests(Isolated):
    def test_mirror_copies_and_hashes_every_file(self):
        nested = self.source / "资料"
        nested.mkdir()
        (nested / "例子.md").write_text("虚构资料\n", encoding="utf-8")
        result = vault_backup.perform("mirror", self.source, self.target, self.receipts)
        self.assertEqual(result["source_files"], 2)
        self.assertEqual(result["sha256_difference_count"], 0)
        self.assertEqual(inventory(self.source), inventory(self.target))
        self.assertTrue(Path(result["receipt"]).is_file())

    def test_extra_history_is_retained(self):
        self.target.mkdir()
        extra = self.target / "old.md"
        extra.write_text("preserve this", encoding="utf-8")
        result = vault_backup.perform("mirror", self.source, self.target, self.receipts)
        self.assertEqual(result["extra_history"], ["old.md"])
        self.assertEqual(extra.read_text(), "preserve this")

    def test_changed_mirror_content_is_updated(self):
        vault_backup.perform("mirror", self.source, self.target, self.receipts)
        (self.source / "note.md").write_text("new fictional content", encoding="utf-8")
        vault_backup.perform("mirror", self.source, self.target, self.receipts)
        self.assertEqual(sha256(self.source / "note.md"), sha256(self.target / "note.md"))

    def test_preserved_old_mtime_does_not_hide_new_file(self):
        vault_backup.perform("mirror", self.source, self.target, self.receipts)
        new = self.source / "old-date-new-file.md"
        new.write_text("new path", encoding="utf-8")
        os.utime(new, (1, 1))
        result = vault_backup.perform("mirror", self.source, self.target, self.receipts)
        self.assertEqual(result["source_files"], 2)

    def test_overlapping_paths_are_rejected(self):
        for source, target, receipts in [(self.source, self.source, self.receipts),
                                         (self.source, self.source / "backup", self.receipts),
                                         (self.source, self.root, self.receipts),
                                         (self.source, self.target, self.source / "receipts")]:
            with self.subTest(target=target), self.assertRaises(SafetyError):
                vault_backup.perform("mirror", source, target, receipts)

    def test_root_and_home_are_rejected(self):
        for value in [Path(self.root.anchor), Path.home()]:
            with self.assertRaises(SafetyError):
                checked_path(value)

    def test_empty_source_is_not_certified(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(SafetyError):
            vault_backup.perform("mirror", empty, self.target, self.receipts)

    def test_source_drift_fails_without_success_receipt(self):
        original_copy = vault_backup.copy_required

        def changed(*args):
            original_copy(*args)
            (self.source / "note.md").write_text("external concurrent edit", encoding="utf-8")

        with mock.patch.object(vault_backup, "copy_required", side_effect=changed), self.assertRaises(SafetyError):
            vault_backup.perform("mirror", self.source, self.target, self.receipts)
        self.assertFalse(self.receipts.exists())

    def test_bad_copy_is_not_certified(self):
        original_copy = vault_backup.copy_required

        def bad_copy(*args):
            original_copy(*args)
            (self.target / "note.md").write_text("corrupt", encoding="utf-8")

        with mock.patch.object(vault_backup, "copy_required", side_effect=bad_copy), self.assertRaises(SafetyError):
            vault_backup.perform("mirror", self.source, self.target, self.receipts)

    def test_snapshot_then_full_isolated_restore(self):
        result = vault_backup.perform("snapshot", self.source, self.target, self.receipts)
        restored = self.root / "restored"
        recovery = vault_backup.perform("restore-check", self.target, restored, self.receipts,
                                        Path(result["manifest"]), result["manifest_sha256"])
        self.assertEqual(recovery["status"], "VERIFIED")
        self.assertEqual(inventory(self.source), inventory(restored))

    def test_snapshot_refuses_existing_directory(self):
        self.target.mkdir()
        with self.assertRaises(SafetyError):
            vault_backup.perform("snapshot", self.source, self.target, self.receipts)

    def test_recovery_refuses_existing_directory(self):
        snap = vault_backup.perform("snapshot", self.source, self.target, self.receipts)
        restored = self.root / "restored"
        restored.mkdir()
        with self.assertRaises(SafetyError):
            vault_backup.perform("restore-check", self.target, restored, self.receipts, Path(snap["manifest"]), snap["manifest_sha256"])

    def test_tampered_manifest_hash_is_rejected(self):
        snap = vault_backup.perform("snapshot", self.source, self.target, self.receipts)
        with self.assertRaises(SafetyError):
            vault_backup.perform("restore-check", self.target, self.root / "restored", self.receipts,
                                 Path(snap["manifest"]), "0" * 64)

    def test_modified_snapshot_file_is_rejected(self):
        snap = vault_backup.perform("snapshot", self.source, self.target, self.receipts)
        (self.target / "note.md").write_text("changed after verification", encoding="utf-8")
        with self.assertRaises(SafetyError):
            vault_backup.perform("restore-check", self.target, self.root / "restored", self.receipts,
                                 Path(snap["manifest"]), snap["manifest_sha256"])

    def test_mirror_manifest_is_not_snapshot_evidence(self):
        snap = vault_backup.perform("mirror", self.source, self.target, self.receipts)
        with self.assertRaises(SafetyError):
            vault_backup.perform("restore-check", self.target, self.root / "restored", self.receipts,
                                 Path(snap["manifest"]), snap["manifest_sha256"])

    def test_manifest_traversal_is_rejected(self):
        malicious = self.root / "malicious.json"
        malicious.write_text(json.dumps({"kind": "snapshot", "status": "VERIFIED", "files": {"../outside.md": {"sha256": "0"*64, "bytes": 0}}}))
        with self.assertRaises(SafetyError):
            vault_backup.perform("restore-check", self.source, self.target, self.receipts, malicious, sha256(malicious))

    def test_symlink_is_rejected_when_platform_allows_creation(self):
        link = self.source / "linked.md"
        try:
            link.symlink_to(self.source / "note.md")
        except OSError:
            self.skipTest("symlink creation not available")
        with self.assertRaises(SafetyError):
            vault_backup.perform("mirror", self.source, self.target, self.receipts)

    def test_long_path_inventory_and_mirror(self):
        folder = self.source
        for n in range(5):
            folder = folder / (f"segment{n}-" + "x" * 45)
        extended(folder).mkdir(parents=True)
        extended(folder / "long-note.md").write_text("long path fictional data", encoding="utf-8")
        result = vault_backup.perform("mirror", self.source, self.target, self.receipts)
        self.assertEqual(result["source_files"], 2)
        self.assertEqual(inventory(self.source), inventory(self.target))


class SafeWriteTests(Isolated):
    def setUp(self):
        super().setUp()
        self.candidate = self.root / "reviewed.md"
        self.candidate.write_text("reviewed fictional replacement\n", encoding="utf-8")
        self.backups = self.root / "before-write"

    def invoke(self, **kwargs):
        return safe_write.perform(self.source, kwargs.pop("relative", "note.md"),
                                  kwargs.pop("candidate", self.candidate),
                                  kwargs.pop("expected", sha256(self.source / "note.md")),
                                  kwargs.pop("backup_root", self.backups), **kwargs)

    def test_preview_does_not_write(self):
        before = sha256(self.source / "note.md")
        result = self.invoke()
        self.assertEqual(result["status"], "PREVIEW")
        self.assertEqual(sha256(self.source / "note.md"), before)
        self.assertFalse(self.backups.exists())

    def test_apply_keeps_verified_original_and_diff(self):
        before = sha256(self.source / "note.md")
        result = self.invoke(apply=True)
        self.assertEqual(result["status"], "COMMITTED")
        folder = Path(result["backup_folder"])
        self.assertEqual(sha256(folder / "original/note.md"), before)
        self.assertTrue((folder / "change.diff").is_file())
        self.assertEqual(sha256(self.source / "note.md"), sha256(self.candidate))

    def test_no_change_preserves_mtime(self):
        self.candidate.write_bytes((self.source / "note.md").read_bytes())
        before = (self.source / "note.md").stat().st_mtime_ns
        self.assertEqual(self.invoke(apply=True)["status"], "NO_CHANGE")
        self.assertEqual((self.source / "note.md").stat().st_mtime_ns, before)

    def test_reading_time_conflict_does_not_overwrite(self):
        before = (self.source / "note.md").read_bytes()
        with self.assertRaises(SafetyError):
            self.invoke(expected="0" * 64, apply=True)
        self.assertEqual((self.source / "note.md").read_bytes(), before)

    def test_create_new_file_exclusively(self):
        result = self.invoke(relative="new.md", expected="MISSING", apply=True)
        self.assertEqual(result["status"], "COMMITTED")
        self.assertEqual((self.source / "new.md").read_bytes(), self.candidate.read_bytes())

    def test_missing_claim_cannot_overwrite_existing(self):
        with self.assertRaises(SafetyError):
            self.invoke(expected="MISSING", apply=True)

    def test_conflict_after_backup_is_preserved(self):
        initial = sha256(self.source / "note.md")
        real = safe_write.current_hash
        calls = 0

        def racing(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_text("external edit", encoding="utf-8")
            return real(path)

        with mock.patch.object(safe_write, "current_hash", side_effect=racing), self.assertRaises(SafetyError):
            self.invoke(expected=initial, apply=True)
        self.assertEqual((self.source / "note.md").read_text(), "external edit")
        self.assertTrue(self.candidate.is_file())

    def test_invalid_candidate_encoding_is_rejected(self):
        self.candidate.write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(UnicodeError):
            self.invoke(apply=True)

    def test_binary_nul_is_rejected(self):
        self.candidate.write_bytes(b"text\x00data")
        with self.assertRaises(SafetyError):
            self.invoke(apply=True)

    def test_traversal_and_non_text_targets_are_rejected(self):
        for name in ["../escape.md", "/absolute.md", "note.db", "a/../note.md", "a\\note.md"]:
            with self.subTest(name=name), self.assertRaises(SafetyError):
                self.invoke(relative=name, apply=True)

    def test_backup_inside_source_is_rejected(self):
        with self.assertRaises(SafetyError):
            self.invoke(backup_root=self.source / "backups", apply=True)

    def test_candidate_inside_source_is_rejected(self):
        with self.assertRaises(SafetyError):
            self.invoke(candidate=self.source / "note.md", apply=True)


if __name__ == "__main__":
    unittest.main()
