#!/usr/bin/env python3
"""Build a signed CI fixture and prove metadata/package tampering is detected."""

import argparse
from datetime import timedelta
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import mock

import package_repository as repository
from package_repository import build_site, published_packages, verified_packages


def run(args, **kwargs):
    return subprocess.check_output([str(a) for a in args], **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--upgrades', type=Path, required=True)
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
            # Simulate yesterday's publication so renewal must advance metadata.
            yesterday = repository.datetime.now(repository.timezone.utc) - timedelta(days=1)
            with mock.patch.object(repository, 'datetime', wraps=repository.datetime) as clock:
                clock.now.return_value = yesterday
                fingerprint = build_site(verified_packages(source), site, home)
            # Adopt a legacy site, retain packages absent from Releases, sign only additions.
            old = published_packages(site, root / 'previous', home)
            original = {p.name: p.read_bytes() for p in old}
            additions = sorted(p for p in args.upgrades.iterdir() if p.suffix in ('.deb', '.rpm'))
            assert len(additions) == 2 and not set(original) & {p.name for p in additions}
            renewed = root / 'renewed'
            with mock.patch.object(repository, 'run', wraps=repository.run) as calls:
                build_site(additions, renewed, home, old)
                assert sum(call.args[0][0] == 'rpmsign' for call in calls.call_args_list) == 1
            assert (site / 'apt/Release').read_bytes() != (renewed / 'apt/Release').read_bytes()
            retained = published_packages(renewed, root / 'retained', home)
            assert {p.name for p in retained} == set(original) | {p.name for p in additions}
            for package in retained:
                if package.name in original:
                    assert package.read_bytes() == original[package.name], package.name
            # A scheduled refresh must not re-sign existing RPMs, even when unsigned
            # Release assets are downloaded again. No sleep/timestamp luck in this check.
            repeated = root / 'repeated'
            with mock.patch.object(repository, 'run', wraps=repository.run) as calls:
                build_site(verified_packages(source) + additions, repeated, home, retained)
                assert not any(call.args[0][0] == 'rpmsign' for call in calls.call_args_list)
            again = published_packages(repeated, root / 'again', home)
            assert {p.name: p.read_bytes() for p in again} == {p.name: p.read_bytes() for p in retained}
            for suffix in ('.deb', '.rpm'):
                conflict = root / next(p.name for p in old if p.suffix == suffix)
                shutil.copyfile(str(next(p for p in additions if p.suffix == suffix)), str(conflict))
                try:
                    build_site([conflict], root / ('conflict' + suffix), home, retained)
                except ValueError as error:
                    assert 'cannot be replaced' in str(error), error
                else:
                    raise AssertionError('Same-name replacement accepted: ' + suffix)
            # Corruption at either metadata level or in a package must stop recovery.
            for relative in ('apt/Release', 'apt/Packages', 'rpm/repodata/repomd.xml',
                             next(p.relative_to(site).as_posix() for p in (site / 'rpm/repodata').glob('*-primary.xml.gz')),
                             'apt/pool/' + next(p.name for p in old if p.suffix == '.deb'),
                             'rpm/Packages/' + next(p.name for p in old if p.suffix == '.rpm')):
                damaged = site / relative
                saved = damaged.read_bytes()
                damaged.write_bytes(saved + b'tampered')
                try:
                    published_packages(site, root / ('reject-' + damaged.name), home)
                except (ValueError, subprocess.CalledProcessError):
                    pass
                else:
                    raise AssertionError('Tampered previous state accepted: ' + relative)
                finally:
                    damaged.write_bytes(saved)
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
            # Client jobs consume the refreshed repository and the new revision.
            shutil.rmtree(str(site))
            shutil.copytree(str(repeated), str(site))
            print('Immutable packages, append/refresh/replacement checks, public-key verification and tampering: OK; ' + fingerprint)
        finally:
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'gpg-agent'], check=False)


if __name__ == '__main__':
    main()
