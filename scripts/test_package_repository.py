#!/usr/bin/env python3
"""Build a signed CI fixture and prove metadata/package tampering is detected."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from package_repository import build_site, verified_packages


def run(args, **kwargs):
    return subprocess.check_output([str(a) for a in args], **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    version = Path('VERSION').read_text().strip()
    with tempfile.TemporaryDirectory(prefix='renyyt-repository-test-') as temporary:
        root = Path(temporary)
        home = root / 'gnupg'
        home.mkdir(mode=0o700)
        try:
            run(['gpg', '--homedir', home, '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
                 '--quick-generate-key', 'Renyyt CI fixture (not for production)', 'rsa3072', 'sign', '2y'])
            source = root / 'releases'
            release = source / ('v' + version)
            release.mkdir(parents=True)
            for package in args.packages.iterdir():
                if package.suffix in ('.deb', '.rpm'):
                    shutil.copyfile(str(package), str(release / package.name))
            (release / 'SHA256SUMS').write_text(''.join(
                hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in release.iterdir()))
            site = args.output.resolve()
            fingerprint = build_site(verified_packages(source), site, home)
            # Verify with a fresh public-only trust store, never the signing home.
            verifier = root / 'verify'
            verifier.mkdir(mode=0o700)
            run(['gpg', '--homedir', verifier, '--batch', '--import', site / 'renyyt-signing-key.asc'])
            for signature, data in ((site / 'apt/InRelease', None),
                                    (site / 'apt/Release.gpg', site / 'apt/Release'),
                                    (site / 'rpm/repodata/repomd.xml.asc', site / 'rpm/repodata/repomd.xml')):
                command = ['gpg', '--homedir', verifier, '--batch', '--verify', signature]
                if data:
                    command.append(data)
                run(command)
            # Modifying signed repository metadata must fail verification.
            tampered = root / 'tampered.xml'
            tampered.write_bytes((site / 'rpm/repodata/repomd.xml').read_bytes() + b'tampered')
            result = subprocess.run(['gpg', '--homedir', str(verifier), '--batch', '--verify',
                                     str(site / 'rpm/repodata/repomd.xml.asc'), str(tampered)], capture_output=True)
            assert result.returncode != 0, 'Tampered metadata unexpectedly verified'
            rpmdb = root / 'rpmdb'
            run(['rpm', '--dbpath', rpmdb, '--import', site / 'renyyt-signing-key.asc'])
            for package in (site / 'rpm/Packages').glob('*.rpm'):
                result = run(['rpmkeys', '--dbpath', rpmdb, '--checksig', package], text=True, env=dict(os.environ, LC_ALL='C'))
                assert 'signatures OK' in result, result
                damaged = root / package.name
                data = bytearray(package.read_bytes())
                data[-1] ^= 1
                damaged.write_bytes(data)
                result = subprocess.run(['rpmkeys', '--dbpath', str(rpmdb), '--checksig', str(damaged)], capture_output=True)
                assert result.returncode != 0, 'Tampered rpm unexpectedly verified'
            assert not list(site.rglob('private*'))
            print('Public-key verification, metadata/package tampering and signed site: OK; ' + fingerprint)
        finally:
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'gpg-agent'], check=False)


if __name__ == '__main__':
    main()
