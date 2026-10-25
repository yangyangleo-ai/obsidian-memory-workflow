import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault-template"
sys.path.insert(0, str(ROOT / "scripts"))
import check_public_content


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("duplicate YAML property")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def metadata(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    return yaml.load(text.split("\n---", 1)[0][4:], Loader=UniqueLoader)


def evaluate(node, path, props):
    if isinstance(node, dict):
        if len(node) != 1:
            raise ValueError("invalid filter")
        op, clauses = next(iter(node.items()))
        values = [evaluate(c, path, props) for c in clauses]
        if op == "and":
            return all(values)
        if op == "or":
            return any(values)
        raise ValueError("unsupported operator")
    match = re.fullmatch(r'([\w.]+) == ("[^"\n]*"|true|false)', node)
    if not match:
        raise ValueError("unsupported static expression")
    key, expected = match.groups()
    wanted = json.loads(expected)
    actual = {"file.ext": Path(path).suffix[1:], "file.folder": Path(path).parent.as_posix()}.get(key, props.get(key))
    return type(actual) is type(wanted) and actual == wanted


class StructureTests(unittest.TestCase):
    def test_workflow_diagram_is_valid_svg(self):
        root = ET.parse(ROOT / "assets/workflow.svg").getroot()
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_all_notes_have_flat_private_metadata(self):
        for p in VAULT.rglob("*.md"):
            with self.subTest(path=p.name):
                meta = metadata(p)
                self.assertEqual(meta["sensitivity"], "private")
                self.assertIs(meta["publish"], False)
                self.assertFalse(any(isinstance(x, dict) for x in meta.values()))

    def test_template_defaults_do_not_certify_success(self):
        templates = list((VAULT / "06-模板").glob("*.md"))
        self.assertEqual(len(templates), 7)
        for p in templates:
            meta = metadata(p)
            self.assertIsNone(meta.get("last_verified"))
            self.assertNotEqual(meta.get("mirror_status"), "VERIFIED")
            self.assertNotEqual(meta.get("write_status"), "COMMITTED")

    def test_wiki_targets_resolve(self):
        for p in VAULT.rglob("*.md"):
            for link in re.findall(r"\[\[([^\]\n]+)\]\]", p.read_text(encoding="utf-8")):
                target = link.split("|", 1)[0].split("#", 1)[0]
                possible = [VAULT / target, VAULT / (target + ".md"), p.parent / (target + ".md")]
                if "/" not in target:
                    possible.extend(VAULT.rglob(target + ".md"))
                self.assertTrue(any(x.is_file() for x in possible), f"unresolved target: {p.name}: {target}")

    def test_repository_relative_markdown_links_resolve(self):
        for p in ROOT.rglob("*.md"):
            if ".git" in p.parts:
                continue
            for link in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
                if "://" in link or link.startswith("#"):
                    continue
                target = link.split("#", 1)[0]
                self.assertTrue((p.parent / target).exists(), f"bad Markdown link {p.name}: {target}")

    def test_bases_yaml_and_views(self):
        spec = yaml.load((VAULT / "00-系统/视图/知识管理.base").read_text(encoding="utf-8"), Loader=UniqueLoader)
        self.assertEqual(len(spec["views"]), 4)
        for view in spec["views"]:
            self.assertEqual(view["type"], "table")

    def test_base_whitelist_excludes_non_opted_in_or_nested_data(self):
        spec = yaml.load((VAULT / "00-系统/视图/知识管理.base").read_text(encoding="utf-8"), Loader=UniqueLoader)
        props = {"management_schema": "obs-v1", "type": "reference-note", "publish": False, "sensitivity": "private"}
        cases = [("07-收件箱/资料/sample.md", props, True),
                 ("05-复盘/知识卡/sample.md", dict(props, type="knowledge-card"), True),
                 ("06-模板/sample.md", props, False),
                 ("99-附件/sample.md", props, False),
                 ("07-收件箱/资料/历史/sample.md", props, False),
                 ("07-收件箱/资料/staging/sample.md", props, False),
                 ("07-收件箱/资料/sample.png", props, False),
                 ("07-收件箱/资料/sample.md", dict(props, sensitivity="restricted"), False),
                 ("07-收件箱/资料/sample.md", dict(props, publish="false"), False),
                 ("07-收件箱/资料/sample.md", dict(props, management_schema=""), False)]
        for path, values, wanted in cases:
            with self.subTest(path=path):
                self.assertIs(evaluate(spec["filters"], path, values), wanted)

    def test_duplicate_yaml_is_rejected(self):
        with self.assertRaises(ValueError):
            yaml.load("status: a\nstatus: b", Loader=UniqueLoader)

    def test_public_sample_receipt_is_not_fake_success(self):
        sample = json.loads((ROOT / "examples/receipt.example.json").read_text())
        self.assertTrue(sample["example_only"])
        self.assertIsNone(sample["source_files"])
        self.assertEqual(sample["mirror_status"], "NOT_CHECKED")

    def test_sensitive_content_scanner(self):
        token = "ghp_" + "x" * 36
        self.assertIn("github-token", check_public_content.scan_text(token))
        private_key = "-----BEGIN " + "PRIVATE KEY-----"
        self.assertIn("private-key", check_public_content.scan_text(private_key))
        self.assertFalse(check_public_content.scan_text("https://example.com/public-docs"))


if __name__ == "__main__":
    unittest.main()
