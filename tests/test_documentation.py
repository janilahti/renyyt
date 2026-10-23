"""Keep the lightweight documentation gate useful for broken links/config drift."""

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("check_docs", Path(__file__).resolve().parents[1] / "scripts/check_docs.py")
docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docs)


class DocumentationChecks(unittest.TestCase):
    def test_visual_renderer_matches_playwright_dependency(self):
        root = Path(__file__).resolve().parents[1]
        version = json.loads((root / "package.json").read_text())["devDependencies"]["@playwright/test"]
        runner = (root / "scripts" / "test_visual.sh").read_text()
        self.assertRegex(runner, r"visual_image='mcr\.microsoft\.com/playwright:v" + re.escape(version) +
                         r"-noble@sha256:[0-9a-f]{64}'")

    def test_in_app_docs_must_not_link_to_unserved_markdown_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "TESTING.md").write_text("# Testing\n")
            path = root / "README.md"
            path.write_text("[Tests](TESTING.md)\n")
            self.assertEqual(len(docs.markdown_errors(root, path)), 1)
            path.write_text("[Tests](https://github.com/example/project/blob/main/TESTING.md)\n")
            self.assertEqual(docs.markdown_errors(root, path), [])

    def test_links_resolve_from_the_document_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "deploy").mkdir()
            (root / "README.md").write_text("# README\n")
            path = root / "deploy" / "README.md"
            path.write_text('[Home](../README.md#title) [Web](https://example.invalid) [Anchor](#local)\n'
                            '```text\n[Example](not-a-file.md)\n```\n')
            self.assertEqual(docs.markdown_errors(root, path), [])
            path.write_text('[Broken](missing.md)\n[Escape](../../outside.md)\n')
            self.assertEqual(len(docs.markdown_errors(root, path)), 2)

    def test_new_runtime_setting_must_be_documented(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "src" / "renyyt"
            source.mkdir(parents=True)
            (source / "config.py").write_text('setting = "RENYYT_NEW_SETTING"\n')
            example = root / ".env.example"
            example.write_text("# RENYYT_OTHER_SETTING=\n")
            self.assertEqual(docs.environment_errors(root), ['.env.example: missing runtime setting RENYYT_NEW_SETTING'])
            example.write_text("# RENYYT_NEW_SETTING=\n")
            self.assertEqual(docs.environment_errors(root), [])
