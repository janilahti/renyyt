"""Exercise CI selection with actual Git history and GitHub event payloads."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_browser_changes.py"


class BrowserChangesTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "--quiet", "-b", "main")
        self.git("config", "user.name", "CI test")
        self.git("config", "user.email", "ci@example.invalid")
        self.base = self.commit({"Dockerfile": "FROM python:3.11-slim\n", "web/app.js": "original\n"})

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, stderr=subprocess.PIPE).decode().strip()

    def commit(self, files):
        for name, content in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                path.unlink()
            else:
                path.write_text(content, encoding="utf-8")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "Synthetic CI change")
        return self.git("rev-parse", "HEAD")

    def selection(self, event_name, event):
        event_path = self.root / "event.json"
        event_path.write_text(json.dumps(event), encoding="utf-8")
        env = dict(os.environ, GITHUB_EVENT_NAME=event_name, GITHUB_EVENT_PATH=str(event_path))
        return subprocess.check_output([sys.executable, str(SCRIPT)], cwd=self.repo, env=env).decode().strip()

    def test_container_only_push_skips_browsers(self):
        head = self.commit({"Dockerfile": "FROM python:3.13-slim\n", ".dockerignore": "node_modules\n"})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "browser=false")

    def test_new_branch_compares_with_default_branch(self):
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        head = self.commit({"Dockerfile": "FROM python:3.13-slim\n"})
        event = {"before": "0" * 40, "after": head, "repository": {"default_branch": "main"}}
        self.assertEqual(self.selection("push", event), "browser=false")
        event["after"] = self.commit({"web/app.js": "changed\n"})
        self.assertEqual(self.selection("push", event), "browser=true")

    def test_new_branch_without_default_branch_history_runs_browsers(self):
        event = {"before": "0" * 40, "after": self.base, "repository": {"default_branch": "main"}}
        self.assertEqual(self.selection("push", event), "browser=true")

    def test_whole_push_includes_earlier_application_changes(self):
        middle = self.commit({"web/app.js": "changed\n"})
        head = self.commit({"Dockerfile": "FROM python:3.13-slim\n"})
        self.assertEqual(self.selection("push", {"before": middle, "after": head}), "browser=false")
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "browser=true")

    def test_pr_includes_earlier_application_changes(self):
        self.commit({"web/app.js": "changed\n"})
        head = self.commit({"Dockerfile": "FROM python:3.13-slim\n"})
        event = {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}
        self.assertEqual(self.selection("pull_request", event), "browser=true")

    def test_pr_excludes_unrelated_base_branch_changes(self):
        self.git("checkout", "--quiet", "-b", "container")
        head = self.commit({"Dockerfile": "FROM python:3.13-slim\n"})
        self.git("checkout", "--quiet", "main")
        base = self.commit({"web/app.js": "unrelated change\n"})
        event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
        self.assertEqual(self.selection("pull_request", event), "browser=false")

    def test_deleted_or_renamed_application_file_runs_browsers(self):
        self.git("mv", "-f", "web/app.js", "Dockerfile")
        head = self.commit({})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "browser=true")

    def test_server_build_test_config_docs_and_unknown_changes_run_browsers(self):
        base = self.base
        for path in ["src/renyyt/server.py", "scripts/build.py", "tests/e2e/app.spec.js",
                     "playwright.config.js", ".github/workflows/ci.yml", "README.md", "unknown-file"]:
            with self.subTest(path=path):
                head = self.commit({path: "synthetic change\n"})
                self.assertEqual(self.selection("push", {"before": base, "after": head}), "browser=true")
                base = head

    def test_missing_history_empty_diff_and_new_branch_run_browsers(self):
        for base in ["f" * 40, "0" * 40, self.base, ""]:
            with self.subTest(base=base):
                self.assertEqual(self.selection("push", {"before": base, "after": self.base}), "browser=true")

    def test_manual_unknown_and_malformed_events_run_browsers(self):
        for name, event in [("workflow_dispatch", {}), ("unknown", {}), ("pull_request", {}),
                            ("push", {"before": None}), ("push", [])]:
            with self.subTest(name=name, event=event):
                self.assertEqual(self.selection(name, event), "browser=true")


if __name__ == "__main__":
    unittest.main()
