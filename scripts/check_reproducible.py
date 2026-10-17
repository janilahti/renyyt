#!/usr/bin/env python3
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns('.git', '.venv', 'node_modules', 'build', 'dist', '*.egg-info', '*.tar.gz', '*.whl', '__pycache__', '.coverage', 'coverage.json', 'htmlcov', 'playwright-report', 'test-results')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run_copy(source, destination, epoch):
    shutil.copytree(str(source), str(destination), ignore=IGNORE)
    env = os.environ.copy()
    env['SOURCE_DATE_EPOCH'] = str(epoch)
    subprocess.run([sys.executable, 'scripts/build.py'], cwd=str(destination), env=env, check=True)
    subprocess.run([sys.executable, 'scripts/package.py'], cwd=str(destination), env=env, check=True, stdout=subprocess.DEVNULL)
    wheel_dir = destination / 'wheelhouse'
    wheel_dir.mkdir()
    subprocess.run(
        [sys.executable, '-m', 'pip', 'wheel', '.', '--no-deps', '--no-build-isolation', '--disable-pip-version-check', '-w', str(wheel_dir)],
        cwd=str(destination), env=env, check=True, stdout=subprocess.DEVNULL,
    )
    release = next(destination.glob('renyyt-*.tar.gz'))
    wheel = next(wheel_dir.glob('renyyt-*.whl'))
    return release, wheel


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build Renyyt twice and verify byte-for-byte reproducibility.')
    parser.add_argument('--epoch', type=int, default=1700000000, help='SOURCE_DATE_EPOCH used for both builds')
    args = parser.parse_args(argv)
    if args.epoch < 0:
        parser.error('--epoch must not be negative')
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        release1, wheel1 = run_copy(ROOT, base / 'one', args.epoch)
        release2, wheel2 = run_copy(ROOT, base / 'two', args.epoch)
        pairs = [('release archive', release1, release2), ('wheel', wheel1, wheel2)]
        failed = False
        for label, first, second in pairs:
            a, b = sha256(first), sha256(second)
            print('%s: %s %s' % (label, a, 'OK' if a == b else 'DIFF'))
            failed = failed or a != b
        return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
