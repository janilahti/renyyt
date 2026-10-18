#!/usr/bin/env python3
"""Select light documentation checks, container checks or the full CI suite."""

import json
import os
import re
import subprocess
from pathlib import Path

CONTAINER_ONLY = {b"Dockerfile", b".dockerignore"}


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
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base + separator + head, "--"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None  # Missing history must never silently bypass checks.
    paths = result.stdout.rstrip(b"\0").split(b"\0")
    return paths if all(paths) else None


def select_checks(event_name, event):
    paths = changed_paths(event_name, event)
    if not paths:
        return True, True
    code_paths = [path for path in paths if not path.endswith(b".md")]
    full = bool(code_paths)
    browser = any(path not in CONTAINER_ONLY for path in code_paths)
    return full, browser


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
