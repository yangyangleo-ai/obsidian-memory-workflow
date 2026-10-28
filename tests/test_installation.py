import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from _common import SafetyError
import install_workspace as setup


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='obsidian-install-test-')
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.target = self.root / 'workspace with space-示例'
        names = ['PUBLIC_FILES.txt', 'VERSION', '.gitignore', 'START_HERE.md', 'AI_START_HERE.md',
                 'AGENTS.md', 'CLAUDE.md', 'GEMINI.md', '.github/copilot-instructions.md',
                 '.cursor/rules/project-memory.mdc', 'vault-template/首页.md']
        for name in names:
            file = self.source / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('fictional fixture\n', encoding='utf-8')
        (self.source / 'VERSION').write_text('0.2.0\n', encoding='utf-8')
        self.listing = self.source / 'PUBLIC_FILES.txt'
        self.listing.write_text('\n'.join(names) + '\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def install(self, **options):
        return setup.install(self.source, self.target, **options)

    def test_preview_is_read_only(self):
        self.assertEqual(self.install(preview=True)['status'], 'PREVIEW')
        self.assertFalse(self.target.exists())

    def test_install_verifies_files_and_keeps_model_untested(self):
        result = self.install()
        self.assertEqual(result['status'], 'INSTALLED_FILES_VERIFIED')
        self.assertEqual(result['ai_acceptance'], 'NOT_TESTED')
        self.assertEqual(setup.installation_report(self.target)['changed_files'], [])
        self.assertFalse((self.target / '.git').exists())
        self.assertFalse((self.target / '.obsidian').exists())
        self.assertIn('/vault-template/', (self.target / '.gitignore').read_text())

    def test_rerun_preserves_user_changes_and_receipt(self):
        self.install()
        note = self.target / 'vault-template/首页.md'
        note.write_text('my own edited notes', encoding='utf-8')
        receipt = (self.target / setup.RECEIPT).read_bytes()
        result = self.install()
        self.assertFalse(result['written'])
        self.assertEqual(result['changed_files'], ['vault-template/首页.md'])
        self.assertEqual(note.read_text(encoding='utf-8'), 'my own edited notes')
        self.assertEqual((self.target / setup.RECEIPT).read_bytes(), receipt)

    def test_existing_foreign_or_empty_directory_is_never_merged(self):
        self.target.mkdir()
        (self.target / 'mine.md').write_text('keep')
        with self.assertRaises(SafetyError):
            self.install()
        self.assertEqual(list(self.target.iterdir()), [self.target / 'mine.md'])

    def test_overlap_and_missing_parent_rejected(self):
        for target in [self.source, self.source / 'child', self.root, self.root / 'missing/child']:
            with self.subTest(target=target), self.assertRaises(SafetyError):
                setup.install(self.source, target)

    def test_git_ancestor_rejected(self):
        (self.root / '.git').mkdir()
        with self.assertRaises(SafetyError):
            self.install()
        self.assertFalse(self.target.exists())

    def test_incomplete_source_is_not_installed(self):
        (self.source / 'CLAUDE.md').unlink()
        with self.assertRaises(SafetyError):
            self.install()
        self.assertFalse(self.target.exists())

    def test_traversal_runtime_and_duplicate_allowlist_rejected(self):
        before = self.listing.read_text(encoding='utf-8')
        for name in ['../outside.md', 'runtime/state.json', '.env.local', 'version', 'a\\b', '/abs']:
            self.listing.write_text(before + name + '\n', encoding='utf-8')
            with self.subTest(name=name), self.assertRaises(SafetyError):
                self.install()
            self.assertFalse(self.target.exists())

    def test_binary_and_oversized_source_rejected(self):
        file = self.source / 'START_HERE.md'
        for data in [b'a\x00b', b'x' * 200001, b'\xff\xfe']:
            file.write_bytes(data)
            with self.subTest(size=len(data)), self.assertRaises((SafetyError, UnicodeError)):
                self.install()
            self.assertFalse(self.target.exists())

    def test_partial_failure_never_gets_success_receipt_or_cleanup(self):
        with mock.patch.object(setup, 'write_new', side_effect=OSError('simulated interruption')):
            with self.assertRaises(OSError):
                self.install()
        self.assertTrue(self.target.exists())
        self.assertFalse((self.target / setup.RECEIPT).exists())
        with self.assertRaises(SafetyError):
            self.install()

    def test_tampered_receipt_paths_cannot_read_outside(self):
        self.install()
        receipt = self.target / setup.RECEIPT
        info = json.loads(receipt.read_text(encoding='utf-8'))
        info['files'] = {'../outside.md': '0' * 64}
        receipt.write_text(json.dumps(info), encoding='utf-8')
        with self.assertRaises(SafetyError):
            self.install()

    def test_malformed_receipt_root_is_rejected(self):
        self.install()
        (self.target / setup.RECEIPT).write_text('[]', encoding='utf-8')
        with self.assertRaises(SafetyError):
            self.install()

    def test_linked_source_rejected_when_platform_allows(self):
        note = self.source / 'START_HERE.md'
        other = self.root / 'outside.md'
        other.write_text('outside', encoding='utf-8')
        note.unlink()
        try:
            note.symlink_to(other)
        except OSError:
            self.skipTest('symlink creation not available')
        with self.assertRaises(SafetyError):
            self.install()

    def native(self):
        shell = shutil.which('powershell.exe')
        if os.name != 'nt' or not shell:
            self.skipTest('Windows PowerShell 5.1 native test is Windows-only')
        result = subprocess.run([shell, '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(ROOT / 'scripts/install_workspace.ps1'),
                                 '-SourceRoot', str(self.source), '-Target', str(self.target)],
                                capture_output=True, timeout=60)
        text = result.stdout.decode('utf-8', errors='replace').strip()
        return result.returncode, json.loads(text)

    def test_windows_native_install_and_python_receipt_agree(self):
        code, result = self.native()
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'INSTALLED_FILES_VERIFIED')
        self.assertEqual(setup.installation_report(self.target)['changed_files'], [])
        self.assertEqual((self.target / '.gitignore').read_bytes(), setup.payload(self.source)['.gitignore'])

    def test_windows_native_repeat_preserves_notes(self):
        code, result = self.native()
        self.assertEqual(code, 0, result)
        note = self.target / 'vault-template/首页.md'
        note.write_text('keep my edited note', encoding='utf-8')
        code, result = self.native()
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'ALREADY_PRESENT_USER_DATA_PRESERVED')
        self.assertEqual(note.read_text(), 'keep my edited note')

    def test_windows_native_rejects_foreign_folder(self):
        self.target.mkdir()
        code, result = self.native()
        self.assertEqual(code, 2, result)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_windows_native_rejects_bad_allowlist(self):
        before = self.listing.read_text(encoding='utf-8')
        self.listing.write_text(before + '../outside.md\n', encoding='utf-8')
        code, result = self.native()
        self.assertEqual(code, 2, result)
        self.assertFalse(self.target.exists())

    def test_windows_native_rejects_missing_source_before_writing(self):
        (self.source / 'CLAUDE.md').unlink()
        code, result = self.native()
        self.assertEqual(code, 2, result)
        self.assertFalse(self.target.exists())


class AdapterTests(unittest.TestCase):
    def test_adapters_keep_one_shared_entry(self):
        for name in ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', '.github/copilot-instructions.md',
                     '.cursor/rules/project-memory.mdc']:
            with self.subTest(name=name):
                self.assertIn('AI_START_HERE.md', (ROOT / name).read_text(encoding='utf-8'))
        self.assertIn('alwaysApply: true', (ROOT / '.cursor/rules/project-memory.mdc').read_text())

    def test_acceptance_example_does_not_claim_model_success(self):
        info = json.loads((ROOT / 'examples/ai-acceptance.example.json').read_text())
        self.assertEqual(info['status'], 'NOT_TESTED')
        self.assertFalse(info['human_reviewed'])
        self.assertTrue(all(value is None for value in info['checks'].values()))


if __name__ == '__main__':
    unittest.main()
