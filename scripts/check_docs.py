#!/usr/bin/env python3
"""Check tracked Markdown file links and documented runtime environment names."""

import ast
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENV_NAME = re.compile(r"(?:RENYYT_[A-Z0-9_]+|PORT)")


def markdown_errors(root, path):
    errors = []
    text = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", path.read_text(encoding="utf-8"), flags=re.M | re.S)
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        target = match.group(1).strip().split(' "', 1)[0].strip("<>")
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        destination = (path.parent / unquote(url.path)).resolve()
        if root.resolve() not in (destination, *destination.parents) or not destination.exists():
            errors.append("%s: missing local link %s" % (path.relative_to(root), target))
    return errors


def environment_errors(root):
    documented = set(re.findall(r"^#?\s*((?:RENYYT_[A-Z0-9_]+|PORT))=", (root / ".env.example").read_text(), re.M))
    used = set()
    for path in (root / "src" / "renyyt").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and ENV_NAME.fullmatch(node.value):
                used.add(node.value)
    return [".env.example: missing runtime setting " + name for name in sorted(used - documented)]


def main():
    names = subprocess.check_output(["git", "ls-files", "-z", "--", "*.md"], cwd=ROOT).decode().split("\0")
    errors = environment_errors(ROOT)
    for name in filter(None, names):
        errors.extend(markdown_errors(ROOT, ROOT / name))
    if errors:
        raise SystemExit("\n".join(errors))
    print("Markdown file links and .env.example runtime settings: OK")


if __name__ == "__main__":
    main()
