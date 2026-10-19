#!/usr/bin/env python3
import argparse
import fnmatch
import gzip
import io
import os
import tarfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "build", "node_modules", "playwright-report", "test-results", "htmlcov", ".ruff_cache", ".pytest_cache"}
EXCLUDED_PATTERNS = {"*.pyc", "*.pyo", "*.tar.gz", "*.zip", "*.whl", "*.deb", "*.rpm", "*.gz", ".coverage", "coverage.json", "*.sqlite", "*.sqlite-*", "*.sqlite3", "*.sqlite3-*", "*.db", "*.db-*"}


def include(root, path):
    rel = path.relative_to(root)
    if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in rel.parts):
        return False
    if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
        return False
    return not any(fnmatch.fnmatch(path.name, pattern) for pattern in EXCLUDED_PATTERNS)


def source_date_epoch():
    raw = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        raise ValueError("SOURCE_DATE_EPOCH must be an integer Unix timestamp")
    if value < 0:
        raise ValueError("SOURCE_DATE_EPOCH must not be negative")
    return value


def package(root=ROOT, out=None):
    root = Path(root)
    version = (root / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    out = Path(out) if out else root / ("renyyt-%s.tar.gz" % version)
    if out.exists():
        out.unlink()
    epoch = source_date_epoch()
    gzip_mtime = epoch if epoch is not None else None
    with out.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=gzip_mtime) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for path in sorted(root.rglob("*")):
                    if not path.is_file() or not include(root, path):
                        continue
                    data = path.read_bytes()
                    info = tarfile.TarInfo((Path("renyyt") / path.relative_to(root)).as_posix())
                    info.size = len(data)
                    info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = epoch if epoch is not None else int(path.stat().st_mtime)
                    tar.addfile(info, io.BytesIO(data))
    return out


def package_zip(root=ROOT, out=None):
    root = Path(root)
    version = (root / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    out = Path(out) if out else root / ("renyyt-%s.zip" % version)
    if out.exists():
        out.unlink()
    epoch = source_date_epoch()
    # Write the production build after sources: extractors that reset mtimes
    # must not make an unchanged packaged build appear stale at startup.
    paths = sorted(root.rglob("*"), key=lambda path: (path.relative_to(root).parts[0] == "dist", path.as_posix()))
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            if not path.is_file() or not include(root, path):
                continue
            timestamp = epoch if epoch is not None else int(path.stat().st_mtime)
            # ZIP's DOS timestamp range is 1980–2107, with two-second precision.
            timestamp = min(4354819198, max(315532800, timestamp))
            info = zipfile.ZipInfo((Path("renyyt") / path.relative_to(root)).as_posix(), time.gmtime(timestamp)[:6])
            info.create_system = 3
            mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return out


def main():
    parser = argparse.ArgumentParser(description="Create Renyyt source release archives.")
    parser.add_argument("--format", choices=("tar.gz", "zip", "all"), default="tar.gz")
    args = parser.parse_args()
    if args.format in ("tar.gz", "all"):
        print(package())
    if args.format in ("zip", "all"):
        print(package_zip())


if __name__ == "__main__":
    main()
