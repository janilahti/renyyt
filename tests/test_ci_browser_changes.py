"""Exercise CI selection with actual Git history and GitHub event payloads."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_browser_changes.py"
SERVER_SOURCE = '''import time
class Handler:
    def _log(self, level, event, **fields):
        print(level, event, fields)
    def log_message(self, fmt, *args):
        self._log("INFO", "access", message=str(fmt))
    def do_POST(self):
        started = time.monotonic()
        self._send(200, b"ok")
'''


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
        self.base = self.commit({"Dockerfile": "FROM python:3.13-slim\n", "web/app.js": "original\n",
                                 "src/renyyt/server.py": SERVER_SOURCE,
                                 "src/renyyt/metrics.py": "counter = 0\n",
                                 "tests/test_server.py": "# Original Python tests\n"})

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
        head = self.commit({"Dockerfile": "FROM python:3.13-slim-bookworm\n", ".dockerignore": "node_modules\n"})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=false")

    def test_new_branch_compares_with_default_branch(self):
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        head = self.commit({"Dockerfile": "FROM python:3.13-slim-bookworm\n"})
        event = {"before": "0" * 40, "after": head, "repository": {"default_branch": "main"}}
        self.assertEqual(self.selection("push", event), "full=true\nbrowser=false")
        event["after"] = self.commit({"web/app.js": "changed\n"})
        self.assertEqual(self.selection("push", event), "full=true\nbrowser=true")

    def test_new_branch_without_default_branch_history_runs_browsers(self):
        event = {"before": "0" * 40, "after": self.base, "repository": {"default_branch": "main"}}
        self.assertEqual(self.selection("push", event), "full=true\nbrowser=true")

    def test_whole_push_includes_earlier_application_changes(self):
        middle = self.commit({"web/app.js": "changed\n"})
        head = self.commit({"Dockerfile": "FROM python:3.13-slim-bookworm\n"})
        self.assertEqual(self.selection("push", {"before": middle, "after": head}), "full=true\nbrowser=false")
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=true")

    def test_pr_includes_earlier_application_changes(self):
        self.commit({"web/app.js": "changed\n"})
        head = self.commit({"Dockerfile": "FROM python:3.13-slim-bookworm\n"})
        event = {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}
        self.assertEqual(self.selection("pull_request", event), "full=true\nbrowser=true")

    def test_pr_excludes_unrelated_base_branch_changes(self):
        self.git("checkout", "--quiet", "-b", "container")
        head = self.commit({"Dockerfile": "FROM python:3.13-slim-bookworm\n"})
        self.git("checkout", "--quiet", "main")
        base = self.commit({"web/app.js": "unrelated change\n"})
        event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
        self.assertEqual(self.selection("pull_request", event), "full=true\nbrowser=false")

    def test_deleted_or_renamed_application_file_runs_browsers(self):
        self.git("mv", "-f", "web/app.js", "Dockerfile")
        head = self.commit({})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=true")

    def test_server_build_test_config_and_unknown_changes_run_browsers(self):
        base = self.base
        for path in ["src/renyyt/server.py", "scripts/build.py", "tests/e2e/app.spec.js",
                     "playwright.config.js", ".github/workflows/ci.yml", "unknown-file"]:
            with self.subTest(path=path):
                head = self.commit({path: "synthetic change\n"})
                self.assertEqual(self.selection("push", {"before": base, "after": head}), "full=true\nbrowser=true")
                base = head

    def test_server_logging_metrics_and_python_tests_skip_ui_checks(self):
        head = self.commit({
            "src/renyyt/server.py": SERVER_SOURCE +
            '        self._log("INFO", "api_success", source="upstream", cache="MISS" if cache_key else "DISABLED", duration_ms=round((time.monotonic() - started) * 1000, 1))\n',
            "src/renyyt/metrics.py": "counter = 1\n",
            "tests/test_server.py": "# Updated Python tests\n",
            "README.md": "Logging docs\n",
        })
        for event_name, event in [
            ("push", {"before": self.base, "after": head}),
            ("pull_request", {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}),
        ]:
            self.assertEqual(self.selection(event_name, event), "full=true\nbrowser=false")
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.assertEqual(self.selection("push", {"before": "0" * 40, "after": head,
                                              "repository": {"default_branch": "main"}}),
                         "full=true\nbrowser=false")

    def test_logging_methods_and_comments_skip_ui_checks(self):
        changed = SERVER_SOURCE.replace("print(level, event, fields)", 'print({"event": event})')
        changed = changed.replace('message=str(fmt)', 'message="changed"')
        head = self.commit({"src/renyyt/server.py": changed + "# Server comment\n"})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=false")

    def test_server_behavior_and_unsafe_log_arguments_run_ui_checks(self):
        changes = [
            SERVER_SOURCE.replace('b"ok"', 'b"changed-response"'),
            SERVER_SOURCE.replace('_send(200', '_send(201'),
            SERVER_SOURCE + '        self.send_header("Content-Type", "text/html")\n',
            SERVER_SOURCE + '        self._log("INFO", "api_success", result=self.change_response())\n',
            SERVER_SOURCE + '        self._log("INFO", "api_success", result=(changed := True))\n',
            SERVER_SOURCE + '        self._log("INFO", "api_success", **payload)\n',
            SERVER_SOURCE + '        if self.should_log():\n            self._log("INFO", "api_success")\n',
            SERVER_SOURCE + '        self._send = replacement\n',
            'malformed python ???\n',
        ]
        for source in changes:
            with self.subTest(source=source):
                head = self.commit({"src/renyyt/server.py": source})
                self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=true")

    def test_internal_tail_does_not_hide_earlier_api_change_in_pr(self):
        middle = self.commit({"src/renyyt/server.py": SERVER_SOURCE.replace('b"ok"', 'b"changed"')})
        head = self.commit({"src/renyyt/metrics.py": "counter = 1\n"})
        self.assertEqual(self.selection("push", {"before": middle, "after": head}), "full=true\nbrowser=false")
        event = {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}
        self.assertEqual(self.selection("pull_request", event), "full=true\nbrowser=true")

    def test_internal_mixed_with_ui_and_config_runs_ui_checks(self):
        for path in ("web/app.js", "tests/fixtures/e2e-services.json", "src/renyyt/upstream.py",
                     "src/renyyt/config.py", "src/renyyt/cache.py", "src/renyyt/rate_limit.py",
                     "scripts/ci_browser_changes.py", ".github/workflows/ci.yml"):
            with self.subTest(path=path):
                # Compare only this commit's changes, without earlier subtests.
                base = self.git("rev-parse", "HEAD")
                head = self.commit({"src/renyyt/metrics.py": path + "\n", path: "changed\n"})
                self.assertEqual(self.selection("push", {"before": base, "after": head}), "full=true\nbrowser=true")

    def test_deleted_or_renamed_internal_code_runs_ui_checks(self):
        self.git("mv", "src/renyyt/metrics.py", "metrics.md")
        head = self.commit({})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=true")

    def test_pr_logging_comparison_uses_merge_base(self):
        self.git("checkout", "--quiet", "-b", "logging")
        head = self.commit({"src/renyyt/server.py": SERVER_SOURCE + '        self._log("INFO", "done")\n'})
        self.git("checkout", "--quiet", "main")
        base = self.commit({"src/renyyt/server.py": SERVER_SOURCE.replace('b"ok"', 'b"unrelated"')})
        event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
        self.assertEqual(self.selection("pull_request", event), "full=true\nbrowser=false")

    def test_missing_history_empty_diff_and_new_branch_run_browsers(self):
        for base in ["f" * 40, "0" * 40, self.base, ""]:
            with self.subTest(base=base):
                self.assertEqual(self.selection("push", {"before": base, "after": self.base}), "full=true\nbrowser=true")

    def test_markdown_only_changes_use_light_checks(self):
        head = self.commit({"README.md": "docs\n", "deploy/cloud-run/README.md": "deployment docs\n",
                            ".github/copilot-instructions.md": "instructions\n"})
        for event_name, event in [
            ("push", {"before": self.base, "after": head}),
            ("pull_request", {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}),
        ]:
            self.assertEqual(self.selection(event_name, event), "full=false\nbrowser=false")
        deleted = self.commit({"README.md": None})
        self.assertEqual(self.selection("push", {"before": head, "after": deleted}), "full=false\nbrowser=false")

    def test_markdown_mixed_with_container_retains_container_checks(self):
        head = self.commit({"README.md": "docs\n", "Dockerfile": "FROM python:3.13-slim-bookworm\n"})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=false")

    def test_renaming_code_to_markdown_still_runs_full_suite(self):
        self.git("mv", "web/app.js", "notes.md")
        head = self.commit({})
        self.assertEqual(self.selection("push", {"before": self.base, "after": head}), "full=true\nbrowser=true")

    def test_documentation_tail_does_not_hide_earlier_code_in_pr(self):
        middle = self.commit({"web/app.js": "changed\n"})
        head = self.commit({"README.md": "docs\n"})
        self.assertEqual(self.selection("push", {"before": middle, "after": head}), "full=false\nbrowser=false")
        event = {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}
        self.assertEqual(self.selection("pull_request", event), "full=true\nbrowser=true")

    def test_manual_unknown_and_malformed_events_run_browsers(self):
        for name, event in [("workflow_dispatch", {}), ("unknown", {}), ("pull_request", {}),
                            ("push", {"before": None}), ("push", [])]:
            with self.subTest(name=name, event=event):
                self.assertEqual(self.selection(name, event), "full=true\nbrowser=true")


if __name__ == "__main__":
    unittest.main()
