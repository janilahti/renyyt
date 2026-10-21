"""Provenance survives extraction/installation without Git or runtime overrides."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from renyyt.build_info import build_info, source_info


class BuildInfoTests(unittest.TestCase):
    def test_installed_manifest_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(folder)
            (root / 'dist').mkdir()
            (root / 'dist/asset-manifest.json').write_text(json.dumps({'builtAt': '2026-10-20T10:00:00Z', 'gitCommit': 'a' * 40}))
            self.assertEqual(build_info(root), {'builtAt': '2026-10-20T10:00:00Z', 'gitCommit': 'a' * 40})
            with mock.patch.dict(os.environ, {'RENYYT_BUILD_TIME': 'custom', 'RENYYT_GIT_COMMIT': 'override'}):
                self.assertEqual(build_info(root), {'builtAt': 'custom', 'gitCommit': 'override'})
            (root / 'dist/asset-manifest.json').write_text('broken')
            self.assertEqual(build_info(root), {'builtAt': '', 'gitCommit': ''})

    def test_source_without_build_and_stale_build(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(folder)
            (root / '.git').mkdir()
            result = subprocess.CompletedProcess([], 0, 'b' * 40 + '\n2026-10-20T10:00:00+00:00\n')
            with mock.patch('renyyt.build_info.subprocess.run', return_value=result):
                expected = {'builtAt': '2026-10-20T10:00:00+00:00', 'gitCommit': 'b' * 40}
                self.assertEqual(build_info(root), expected)
                (root / 'dist').mkdir()
                (root / 'dist/asset-manifest.json').write_text(json.dumps({'builtAt': 'old', 'gitCommit': 'a' * 40}))
                self.assertEqual(build_info(root), expected)
            with mock.patch('renyyt.build_info.subprocess.run', side_effect=FileNotFoundError):
                self.assertEqual(source_info(root), {})
