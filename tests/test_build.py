#!/usr/bin/env python3
import gzip
import importlib.util
import json
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("renyyt_build", str(REPO_ROOT / "scripts" / "build.py"))
buildmod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(buildmod)
PKG_SPEC = importlib.util.spec_from_file_location("renyyt_package", str(REPO_ROOT / "scripts" / "package.py"))
packmod = importlib.util.module_from_spec(PKG_SPEC)
PKG_SPEC.loader.exec_module(packmod)


class BuildTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "web").mkdir()
        (self.root / "web" / "index.html").write_text('<link href="styles.css"><script src="i18n.js"></script><script src="helpers.js"></script><script src="app.js"></script>', encoding="utf-8")
        (self.root / "web" / "styles.css").write_text("body{}", encoding="utf-8")
        (self.root / "web" / "i18n.js").write_text("window.i18n=1;", encoding="utf-8")
        (self.root / "web" / "helpers.js").write_text("window.x=1;", encoding="utf-8")
        (self.root / "web" / "app.js").write_text("console.log(1);", encoding="utf-8")
        (self.root / "web" / "service-worker.js").write_text("self.addEventListener(\"fetch\",()=>{});", encoding="utf-8")
        brand = self.root / "web" / "assets" / "brand"
        brand.mkdir(parents=True)
        for name in ("logo.svg", "favicon.svg", "favicon.ico", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "maskable-192.png", "maskable-512.png", "site.webmanifest"):
            (brand / name).write_bytes(("asset:" + name).encode("utf-8"))
        (self.root / "VERSION").write_text("9.8.7\n", encoding="utf-8")
        (self.root / "LICENSE").write_text("MIT test\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_fingerprints_assets_and_rewrites_index(self):
        manifest = buildmod.build(self.root)
        self.assertEqual(set(manifest["assets"]), {"app.js", "helpers.js", "i18n.js", "styles.css"})
        self.assertEqual(manifest["version"], "9.8.7")
        self.assertEqual(manifest["manifestVersion"], 1)
        html = (self.root / "dist" / "index.html").read_text(encoding="utf-8")
        for source, rel in manifest["assets"].items():
            self.assertTrue((self.root / "dist" / rel).is_file())
            self.assertIn(rel, html)
        self.assertFalse((self.root / "dist" / "index.html.gz").exists())
        self.assertTrue((self.root / "dist" / "brand" / "logo.svg").is_file())
        self.assertTrue((self.root / "dist" / "service-worker.js").is_file())
        self.assertTrue(manifest["serviceWorker"])
        self.assertEqual(set(manifest["brand"]), {"logo.svg", "favicon.svg", "favicon.ico", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "maskable-192.png", "maskable-512.png", "site.webmanifest"})

    def test_release_package_excludes_precompressed_and_cache_files(self):
        (self.root / "README.md").write_text("# Test\n", encoding="utf-8")
        (self.root / "TECHNICAL.md").write_text("# Technical\n", encoding="utf-8")
        (self.root / "index.html.gz").write_bytes(b"gzip")
        cache = self.root / "__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"pyc")
        dist = self.root / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("prod", encoding="utf-8")
        out = self.root.parent / "release-test.tar.gz"
        try:
            packmod.package(self.root, out)
            with tarfile.open(str(out), "r:gz") as tar:
                names = set(tar.getnames())
            self.assertIn("renyyt/README.md", names)
            self.assertIn("renyyt/TECHNICAL.md", names)
            self.assertIn("renyyt/LICENSE", names)
            self.assertIn("renyyt/dist/index.html", names)
            self.assertNotIn("renyyt/index.html.gz", names)
            self.assertFalse(any(name.endswith(".gz") for name in names))
            self.assertFalse(any("__pycache__" in name for name in names))
        finally:
            if out.exists():
                out.unlink()

    def test_default_release_archive_uses_renyyt_name(self):
        (self.root / "README.md").write_text("# Test\n", encoding="utf-8")
        out = packmod.package(self.root)
        try:
            self.assertEqual(out.name, "renyyt-9.8.7.tar.gz")
            with tarfile.open(str(out), "r:gz") as tar:
                self.assertTrue(all(name == "renyyt" or name.startswith("renyyt/") for name in tar.getnames()))
        finally:
            if out.exists():
                out.unlink()

    def test_source_date_epoch_makes_build_metadata_and_gzip_reproducible(self):
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH":"1700000000"}):
            manifest1 = buildmod.build(self.root, gzip_output=True)
            first = (self.root / "dist" / "index.html.gz").read_bytes()
            manifest2 = buildmod.build(self.root, gzip_output=True)
            second = (self.root / "dist" / "index.html.gz").read_bytes()
        self.assertEqual(manifest1["builtAt"], "2023-11-14T22:13:20+00:00")
        self.assertEqual(manifest1, manifest2)
        self.assertEqual(first, second)

    def test_source_date_epoch_makes_release_archive_reproducible(self):
        (self.root / "README.md").write_text("# Test\n", encoding="utf-8")
        out1 = self.root.parent / "release-one.tar.gz"
        out2 = self.root.parent / "release-two.tar.gz"
        try:
            with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH":"1700000000"}):
                packmod.package(self.root, out1)
                packmod.package(self.root, out2)
            self.assertEqual(out1.read_bytes(), out2.read_bytes())
        finally:
            for out in (out1, out2):
                if out.exists(): out.unlink()

    def test_package_excludes_private_env_files_but_keeps_example(self):
        (self.root / ".env").write_text("SECRET=one\n", encoding="utf-8")
        (self.root / ".env.production").write_text("SECRET=two\n", encoding="utf-8")
        (self.root / ".env.example").write_text("# SECRET=example\n", encoding="utf-8")
        out = self.root.parent / "release-env-test.tar.gz"
        try:
            packmod.package(self.root, out)
            with tarfile.open(out, "r:gz") as archive:
                names = set(archive.getnames())
            self.assertIn("renyyt/.env.example", names)
            self.assertNotIn("renyyt/.env", names)
            self.assertNotIn("renyyt/.env.production", names)
        finally:
            if out.exists():
                out.unlink()

    def test_package_excludes_runtime_databases_and_tool_caches(self):
        private_paths = ["reminders.sqlite3", "reminders.sqlite3-wal", "reminders.sqlite3-shm",
                         "state/reminders.db", "state/reminders.db-journal", "state/backup.sqlite",
                         ".ruff_cache/results", ".pytest_cache/results", "renyyt-test.whl"]
        for name in private_paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic runtime state\n", encoding="utf-8")
        out = self.root.parent / "release-runtime-test.tar.gz"
        try:
            packmod.package(self.root, out)
            with tarfile.open(out, "r:gz") as archive:
                names = set(archive.getnames())
            for name in private_paths:
                self.assertNotIn("renyyt/" + name, names)
        finally:
            if out.exists():
                out.unlink()

    def test_zip_matches_tar_contents_and_excludes_private_and_generated_files(self):
        (self.root / "README.et.md").write_text("# Prügikastide tühjendused\n", encoding="utf-8")
        (self.root / ".env").write_text("SYNTHETIC=value\n", encoding="utf-8")
        (self.root / "reminders.sqlite3-wal").write_text("synthetic state\n", encoding="utf-8")
        (self.root / "old.zip").write_bytes(b"old archive")
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "1700000000"}):
            tar_path = packmod.package(self.root)
            zip_path = packmod.package_zip(self.root)
        with tarfile.open(tar_path) as tar, zipfile.ZipFile(zip_path) as zipped:
            expected = {entry.name: tar.extractfile(entry).read() for entry in tar.getmembers()}
            actual = {name: zipped.read(name) for name in zipped.namelist()}
            self.assertEqual(actual, expected)
            self.assertEqual(actual["renyyt/README.et.md"].decode(), "# Prügikastide tühjendused\n")
            self.assertNotIn("renyyt/.env", actual)
            self.assertNotIn("renyyt/reminders.sqlite3-wal", actual)
            self.assertNotIn("renyyt/old.zip", actual)
            self.assertTrue(all(name.startswith("renyyt/") for name in actual))
            self.assertEqual(zipped.getinfo("renyyt/README.et.md").external_attr >> 16, 0o100644)

    def test_zip_is_reproducible_and_clamps_pre_1980_timestamps(self):
        executable = self.root / "run.py"
        executable.write_text("# synthetic executable\n", encoding="utf-8")
        executable.chmod(0o755)
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "0"}):
            out = packmod.package_zip(self.root)
            first = out.read_bytes()
            os.utime(executable, (1700000000, 1700000000))
            self.assertEqual(first, packmod.package_zip(self.root).read_bytes())
        with zipfile.ZipFile(out) as zipped:
            self.assertEqual(zipped.getinfo("renyyt/run.py").date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(zipped.getinfo("renyyt/run.py").external_attr >> 16, 0o100755)

    def test_optional_gzip_covers_index_and_all_built_assets(self):
        manifest = buildmod.build(self.root, gzip_output=True)
        targets = [self.root / "dist" / "index.html", self.root / "dist" / "service-worker.js"] + [self.root / "dist" / rel for rel in manifest["assets"].values()]
        for target in targets:
            compressed_path = Path(str(target) + ".gz")
            self.assertTrue(compressed_path.is_file(), compressed_path)
            self.assertEqual(gzip.decompress(compressed_path.read_bytes()), target.read_bytes())
        for name in ("logo.svg", "favicon.svg", "site.webmanifest"):
            target = self.root / "dist" / "brand" / name
            compressed_path = Path(str(target) + ".gz")
            self.assertTrue(compressed_path.is_file(), compressed_path)
            self.assertEqual(gzip.decompress(compressed_path.read_bytes()), target.read_bytes())


if __name__ == "__main__":
    unittest.main()
