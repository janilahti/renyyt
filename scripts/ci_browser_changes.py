#!/usr/bin/env python3
"""Select server checks and UI checks conservatively from the complete Git diff."""

import ast
import json
import os
import re
import subprocess
from pathlib import Path

LIGHTWEIGHT_ONLY = {b".github/dependabot.yml"}
CONTAINER_ONLY = {b"Dockerfile", b".dockerignore"}
INTERNAL_ONLY = {b"src/renyyt/metrics.py"}
SERVER = b"src/renyyt/server.py"


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return call_name(node.value) + "." + node.attr
    return ""


def is_log_statement(node):
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    call = node.value
    if call_name(call.func) != "self._log" or len(call.args) != 2:
        return False
    if not all(isinstance(arg, ast.Constant) and isinstance(arg.value, str) for arg in call.args):
        return False
    # Restrict arguments: no assignments, awaits, comprehensions, unpacking or
    # arbitrary calls that could conceal a behavioral change in a log field.
    allowed = (ast.Constant, ast.Name, ast.Load, ast.Attribute, ast.Call, ast.keyword,
               ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.UnaryOp, ast.USub, ast.IfExp)
    for keyword in call.keywords:
        if keyword.arg is None:
            return False
        for value in ast.walk(keyword.value):
            if not isinstance(value, allowed):
                return False
            if isinstance(value, ast.Call):
                if value.keywords or call_name(value.func) not in {"round", "len", "str", "time.monotonic"}:
                    return False
    return True


class WithoutLogging(ast.NodeTransformer):
    def visit_ClassDef(self, node):
        if node.name != "Handler":
            return node
        for method in node.body:
            if isinstance(method, ast.FunctionDef) and method.name in {"_log", "log_message"}:
                method.body = []
        return self.generic_visit(node)

    def visit_Expr(self, node):
        return None if is_log_statement(node) else node


def logging_only(base, head):
    try:
        trees = []
        for revision in (base, head):
            source = subprocess.check_output(
                ["git", "show", revision + ":" + SERVER.decode()], stderr=subprocess.PIPE,
            )
            tree = WithoutLogging().visit(ast.parse(source))
            trees.append(ast.dump(tree))
        return trees[0] == trees[1]
    except (OSError, subprocess.CalledProcessError, SyntaxError, ValueError):
        return False


def changed_paths(event_name, event):
    if event_name == "pull_request":
        pull = event.get("pull_request", {})
        base = pull.get("base", {}).get("sha", "")
        head = pull.get("head", {}).get("sha", "")
        separator = "..."  # Whole PR, excluding unrelated changes on the base branch.
    elif event_name == "push":
        base, head = event.get("before", ""), event.get("after", "")
        separator = ".."  # Every commit in this push, including deleted paths.
        if base in ("0" * 40, "0" * 64):
            default_branch = event.get("repository", {}).get("default_branch")
            if not default_branch:
                return None
            try:
                base = subprocess.check_output(
                    ["git", "rev-parse", "--verify", "refs/remotes/origin/" + default_branch + "^{commit}"],
                    stderr=subprocess.PIPE,
                ).decode().strip()
            except (OSError, subprocess.CalledProcessError):
                return None
            separator = "..."  # First push: compare the new branch with the default branch.
    else:
        return None  # Manual runs and unknown events always run the full suite.

    for revision in (base, head):
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) or set(revision) == {"0"}:
            return None
    try:
        if separator == "...":
            base = subprocess.check_output(["git", "merge-base", base, head], stderr=subprocess.PIPE).decode().strip()
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-status", "-z", base + ".." + head, "--"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None  # Missing history must never silently bypass checks.
    fields = result.stdout.rstrip(b"\0").split(b"\0")
    if not all(fields) or len(fields) % 2:
        return None
    return list(zip(fields[::2], fields[1::2])), base, head


def select_checks(event_name, event):
    changes = changed_paths(event_name, event)
    if not changes:
        return True, True
    paths, base, head = changes
    code_paths = [(status, path) for status, path in paths if not path.endswith(b".md") and path not in LIGHTWEIGHT_ONLY]
    for status, path in code_paths:
        if path in CONTAINER_ONLY:
            continue
        # Added/deleted/renamed code takes the conservative full-check path.
        if status != b"M":
            return True, True
        if path in INTERNAL_ONLY:
            continue
        if path.startswith(b"tests/test_") and path.endswith(b".py") and path.count(b"/") == 1:
            continue
        if path == SERVER and logging_only(base, head):
            continue
        return True, True
    return bool(code_paths), False


def main():
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        full, browser = select_checks(os.environ.get("GITHUB_EVENT_NAME"), event)
    except (KeyError, OSError, ValueError, AttributeError, TypeError):
        full, browser = True, True
    print("full=" + str(full).lower())
    print("browser=" + str(browser).lower())


if __name__ == "__main__":
    main()
