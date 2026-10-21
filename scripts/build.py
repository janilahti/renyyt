#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from renyyt.build_info import build_info

SOURCES = ["i18n.js", "helpers.js", "app.js", "styles.css"]


def digest(data):
    return hashlib.sha256(data).hexdigest()[:12]


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


def build_timestamp(epoch=None):
    stamp = datetime.fromtimestamp(epoch, timezone.utc) if epoch is not None else datetime.now(timezone.utc)
    return stamp.isoformat(timespec="seconds")


def write_gzip(source, target, epoch=None):
    with source.open("rb") as src, target.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=epoch) as dst:
            shutil.copyfileobj(src, dst)


def build(repo_root, gzip_output=False):
    repo_root = Path(repo_root)
    epoch = source_date_epoch()
    web_root = repo_root / "web"
    dist_root = repo_root / "dist"
    assets_dir = dist_root / "assets"
    manifest_path = dist_root / "asset-manifest.json"
    prod_index = dist_root / "index.html"
    service_worker_src = web_root / "service-worker.js"
    service_worker_dist = dist_root / "service-worker.js"
    brand_src = web_root / "assets" / "brand"
    brand_dist = dist_root / "brand"

    dist_root.mkdir(exist_ok=True)
    assets_dir.mkdir(exist_ok=True)
    for old in assets_dir.iterdir():
        if old.is_file():
            old.unlink()

    if brand_dist.exists():
        shutil.rmtree(str(brand_dist))
    if brand_src.is_dir():
        shutil.copytree(str(brand_src), str(brand_dist))

    mapping = {}
    for name in SOURCES:
        src = web_root / name
        data = src.read_bytes()
        out_name = "%s.%s%s" % (src.stem, digest(data), src.suffix)
        (assets_dir / out_name).write_bytes(data)
        mapping[name] = "assets/" + out_name

    html = (web_root / "index.html").read_text(encoding="utf-8")
    for source, built in mapping.items():
        html = html.replace('href="%s"' % source, 'href="%s"' % built)
        html = html.replace('src="%s"' % source, 'src="%s"' % built)
    prod_index.write_text(html, encoding="utf-8")
    if service_worker_src.is_file():
        shutil.copyfile(str(service_worker_src), str(service_worker_dist))

    version_path = repo_root / "VERSION"
    release_version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "dev"
    brand_files = {}
    if brand_dist.is_dir():
        for item in sorted(brand_dist.iterdir()):
            if item.is_file():
                brand_files[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
    provenance = build_info(repo_root)
    manifest = {
        "manifestVersion": 1,
        "version": release_version or "dev",
        "builtAt": build_timestamp(epoch) if epoch is not None else (os.environ.get("RENYYT_BUILD_TIME", "").strip() or build_timestamp()),
        "gitCommit": provenance["gitCommit"],
        "index": "index.html",
        "assets": mapping,
        "brand": brand_files,
        "serviceWorker": hashlib.sha256(service_worker_dist.read_bytes()).hexdigest() if service_worker_dist.is_file() else None,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gzip_targets = [prod_index] + [dist_root / rel for rel in mapping.values()]
    if service_worker_dist.is_file():
        gzip_targets.append(service_worker_dist)
    if brand_dist.is_dir():
        gzip_targets.extend(p for p in brand_dist.iterdir() if p.suffix.lower() in (".svg", ".webmanifest"))
    if gzip_output:
        for target in gzip_targets:
            write_gzip(target, Path(str(target) + ".gz"), epoch)
    else:
        for target in gzip_targets:
            gz_target = Path(str(target) + ".gz")
            if gz_target.exists():
                gz_target.unlink()
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Build hashed production assets without external dependencies.")
    parser.add_argument("--gzip", action="store_true", help="Also create precompressed .gz files for the production HTML and JS/CSS assets")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    manifest = build(repo_root, gzip_output=args.gzip)
    print("Built dist/%s with %d fingerprinted assets." % (manifest["index"], len(manifest["assets"])))


if __name__ == "__main__":
    main()
