"""Build provenance for installed artifacts and unbuilt source checkouts."""
import json
import os
import subprocess
from pathlib import Path


def source_info(root):
    root = Path(root)
    # Do not accidentally report an enclosing repository for an extracted package.
    if not (root / '.git').exists():
        return {}
    try:
        result = subprocess.run(
            ['git', '-C', str(root), 'log', '-1', '--format=%H%n%cI'],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True, timeout=2,
        )
        commit, stamp = result.stdout.strip().splitlines()
        return {'gitCommit': commit, 'builtAt': stamp}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def build_info(root):
    root = Path(root)
    try:
        manifest = json.loads((root / 'dist/asset-manifest.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            manifest = {}
    except (OSError, ValueError):
        manifest = {}
    source = source_info(root)
    # A build from another revision must not describe the current checkout.
    if source and source.get('gitCommit') != manifest.get('gitCommit'):
        manifest = source
    return {
        'builtAt': os.environ.get('RENYYT_BUILD_TIME', '').strip() or manifest.get('builtAt', ''),
        'gitCommit': os.environ.get('RENYYT_GIT_COMMIT', '').strip() or manifest.get('gitCommit', ''),
    }
