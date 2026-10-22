#!/usr/bin/env python3
"""Publish signed APT/DNF repositories from verified stable release assets."""

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REPOSITORY = 'janilahti/renyyt'
BASE_URL = 'https://janilahti.github.io/renyyt'
VERSION = re.compile(r'v(\d+\.\d+\.\d+)')


def run(args, **kwargs):
    return subprocess.check_output([str(arg) for arg in args], **kwargs)


def package_names(tag, names):
    match = VERSION.fullmatch(tag)
    if not match:
        return []
    version = re.escape(match[1])
    patterns = (r'renyyt_' + version + r'-\d+_all\.deb',
                r'renyyt-' + version + r'-\d+\.noarch\.rpm')
    selected = sorted(name for name in names if any(re.fullmatch(pattern, name) for pattern in patterns))
    if selected and (len(selected) != 2 or {Path(name).suffix for name in selected} != {'.deb', '.rpm'}):
        raise ValueError('Expected one deb and one rpm in ' + tag)
    return selected


def download_releases(destination):
    # One JSON object per line supports GitHub's pagination without retaining credentials.
    raw = run(['gh', 'api', '--paginate', 'repos/' + REPOSITORY + '/releases',
               '--jq', '.[] | tojson'], text=True)
    for line in raw.splitlines():
        release = json.loads(line)
        tag = release['tag_name']
        if release['draft'] or release['prerelease'] or not VERSION.fullmatch(tag):
            continue
        names = {asset['name'] for asset in release['assets']}
        packages = package_names(tag, names)
        if not packages:
            continue  # Releases before native packaging are deliberately excluded.
        if 'SHA256SUMS' not in names:
            raise ValueError('Missing release checksums: ' + tag)
        folder = destination / tag
        folder.mkdir()
        args = ['gh', 'release', 'download', tag, '--repo', REPOSITORY, '--dir', str(folder)]
        for name in packages + ['SHA256SUMS']:
            args.extend(['--pattern', name])
        run(args)


def verified_packages(source):
    result = []
    for folder in sorted(source.iterdir()):
        if not folder.is_dir() or not VERSION.fullmatch(folder.name):
            continue
        names = package_names(folder.name, [path.name for path in folder.iterdir()])
        if not names:
            continue
        checksums = {}
        for line in (folder / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split()
            if not re.fullmatch(r'[0-9a-f]{64}', digest) or name in checksums:
                raise ValueError('Invalid or duplicate release checksum')
            checksums[name] = digest
        for name in names:
            path = folder / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != checksums.get(name):
                raise ValueError('Release checksum mismatch: ' + name)
            version = VERSION.fullmatch(folder.name)[1]
            if name.endswith('.deb'):
                fields = run(['dpkg-deb', '-f', path, 'Package', 'Version', 'Architecture'], text=True)
                expected = {'Package: renyyt', 'Version: ' + re.fullmatch(r'renyyt_(.+)_all.deb', name)[1], 'Architecture: all'}
                if set(fields.splitlines()) != expected:
                    raise ValueError('Unexpected deb package identity: ' + name)
            else:
                fields = run(['rpm', '-qp', '--qf', '%{NAME} %{VERSION} %{RELEASE} %{ARCH}', path], text=True)
                revision = re.fullmatch(r'renyyt-' + re.escape(version) + r'-(\d+).noarch.rpm', name)[1]
                if fields != 'renyyt ' + version + ' ' + revision + ' noarch':
                    raise ValueError('Unexpected rpm package identity: ' + name)
            result.append(path)
    if not result:
        raise ValueError('No stable native release packages found')
    return result


def signing_identity(home):
    listing = run(['gpg', '--homedir', home, '--batch', '--with-colons', '--list-secret-keys'], text=True)
    keys = [line.split(':') for line in listing.splitlines() if line.startswith('sec:')]
    fingerprints = [line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')]
    if len(keys) != 1 or not fingerprints:
        raise ValueError('Use exactly one dedicated repository signing key')
    key = keys[0]
    if key[1] in ('r', 'e', 'd') or 's' not in key[11].lower():
        raise ValueError('Repository key cannot sign')
    if key[3] != '1' or int(key[2]) < 3072:
        raise ValueError('Repository signing requires RSA 3072 bits or stronger')
    if not key[6] or int(key[6]) < int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()):
        raise ValueError('Repository signing key must expire more than 30 days from now')
    return fingerprints[0]


def sign(home, fingerprint, source, destination, clear=False):
    mode = '--clearsign' if clear else '--detach-sign'
    run(['gpg', '--homedir', home, '--batch', '--yes', '--local-user', fingerprint,
         '--digest-algo', 'SHA256', '--armor', '--output', destination, mode, source])


def build_site(packages, output, home):
    fingerprint = signing_identity(home)
    if output.exists():
        raise ValueError('Output must not already exist: ' + str(output))
    apt, rpm = output / 'apt', output / 'rpm'
    (apt / 'pool').mkdir(parents=True)
    (rpm / 'Packages').mkdir(parents=True)
    public = run(['gpg', '--homedir', home, '--batch', '--export', fingerprint])
    (output / 'renyyt-keyring.gpg').write_bytes(public)
    armored = run(['gpg', '--homedir', home, '--batch', '--armor', '--export', fingerprint])
    (output / 'renyyt-signing-key.asc').write_bytes(armored)
    (output / 'signing-key-fingerprint.txt').write_text(fingerprint + '\n')
    for source in packages:
        folder = apt / 'pool' if source.suffix == '.deb' else rpm / 'Packages'
        destination = folder / source.name
        if destination.exists():
            raise ValueError('Duplicate package filename: ' + source.name)
        shutil.copyfile(str(source), str(destination))
        if source.suffix == '.rpm':
            run(['rpmsign', '--define', '_gpg_name ' + fingerprint,
                 '--define', '_gpg_path ' + str(home), '--define', '__gpg /usr/bin/gpg',
                 '--define', '_gpg_digest_algo sha256', '--addsign', destination])
    index = run(['dpkg-scanpackages', '--multiversion', 'pool', '/dev/null'], cwd=str(apt))
    (apt / 'Packages').write_bytes(index)
    (apt / 'Packages.gz').write_bytes(gzip.compress(index, mtime=0))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    release = ('Origin: Renyyt\nLabel: Renyyt\nSuite: stable\nCodename: stable\n'
               'Architectures: all\nDescription: Renyyt stable packages\n'
               'Date: ' + format_datetime(now, usegmt=True) + '\n'
               'Valid-Until: ' + format_datetime(now + timedelta(days=30), usegmt=True) + '\nSHA256:\n')
    for name in ('Packages', 'Packages.gz'):
        data = (apt / name).read_bytes()
        release += ' ' + hashlib.sha256(data).hexdigest() + ' ' + str(len(data)) + ' ' + name + '\n'
    (apt / 'Release').write_text(release)
    sign(home, fingerprint, apt / 'Release', apt / 'InRelease', clear=True)
    sign(home, fingerprint, apt / 'Release', apt / 'Release.gpg')
    run(['createrepo_c', '--unique-md-filenames', rpm])
    sign(home, fingerprint, rpm / 'repodata/repomd.xml', rpm / 'repodata/repomd.xml.asc')
    (output / 'renyyt.repo').write_text(
        '[renyyt]\nname=Renyyt stable\nbaseurl=' + BASE_URL + '/rpm/\n'
        'enabled=1\ngpgcheck=1\nrepo_gpgcheck=1\ngpgkey=' + BASE_URL + '/renyyt-signing-key.asc\n'
        'metadata_expire=6h\nsslverify=1\n')
    (output / 'renyyt.sources').write_text(
        'Types: deb\nURIs: ' + BASE_URL + '/apt/\nSuites: ./\n'
        'Signed-By: /etc/apt/keyrings/renyyt.gpg\n')
    (output / '.nojekyll').touch()
    (output / 'index.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width"><title>Renyyt package repositories</title>'
        '<h1>Renyyt package repositories</h1><p>Stable APT and DNF packages.</p>'
        '<p><a href="https://github.com/janilahti/renyyt/blob/main/deploy/linux/REPOSITORIES.md">'
        'Installation, updates and removal instructions</a></p>'
        '<p>Signing key fingerprint: <code>' + html.escape(fingerprint) + '</code></p>'
        '<ul><li><a href="renyyt-keyring.gpg">APT keyring</a></li>'
        '<li><a href="renyyt-signing-key.asc">ASCII public key</a></li>'
        '<li><a href="renyyt.sources">APT source</a></li>'
        '<li><a href="renyyt.repo">DNF repository</a></li></ul>'
        '<p>Updated ' + html.escape(now.isoformat()) + '</p></html>\n')
    return fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--packages', type=Path, help='Local vX.Y.Z release folders with SHA256SUMS (tests/offline builds)')
    args = parser.parse_args()
    private_key = os.environ.pop('PACKAGE_SIGNING_KEY', '')
    if not private_key:
        parser.error('PACKAGE_SIGNING_KEY is required; run the documented owner setup first')
    with tempfile.TemporaryDirectory(prefix='renyyt-repository-') as temporary:
        root = Path(temporary)
        home = root / 'gnupg'
        home.mkdir(mode=0o700)
        try:
            run(['gpg', '--homedir', home, '--batch', '--import'], input=private_key.encode())
            del private_key
            source = args.packages
            if source is None:
                source = root / 'releases'
                source.mkdir()
                download_releases(source)
            fingerprint = build_site(verified_packages(source), args.output.resolve(), home)
            print('Repository public signing key: ' + fingerprint)
        finally:
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'gpg-agent'], check=False)


if __name__ == '__main__':
    main()
