#!/usr/bin/env python3
"""Skip host-browser tests only for changes confined to the container recipe."""

import json
import os
import re
import subprocess
from pathlib import Path

CONTAINER_ONLY = {b"Dockerfile", b".dockerignore"}


def browser_tests_needed(event_name, event):
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
                return True
            try:
                base = subprocess.check_output(
                    ["git", "rev-parse", "--verify", "refs/remotes/origin/" + default_branch + "^{commit}"],
                    stderr=subprocess.PIPE,
                ).decode().strip()
            except (OSError, subprocess.CalledProcessError):
                return True
            separator = "..."  # First push: compare the new branch with the default branch.
    else:
        return True  # Manual runs and unknown events always run the full suite.

    for revision in (base, head):
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) or set(revision) == {"0"}:
            return True
    try:
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base + separator + head, "--"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return True  # Missing history must never silently bypass checks.
    paths = result.stdout.rstrip(b"\0").split(b"\0")
    return any(path not in CONTAINER_ONLY for path in paths)


def main():
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        needed = browser_tests_needed(os.environ.get("GITHUB_EVENT_NAME"), event)
    except (KeyError, OSError, ValueError, AttributeError, TypeError):
        needed = True
    print("browser=" + str(needed).lower())


if __name__ == "__main__":
    main()
