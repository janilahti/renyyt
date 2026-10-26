#!/usr/bin/env python3
"""Publish signed APT/DNF repositories from verified stable release assets."""

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from email.parser import Parser
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
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

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


def verified_packages(source, allow_empty=False):
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
    if not result and not allow_empty:
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


def checked_bytes(data, digest, size=None):
    if (not re.fullmatch(r'[0-9a-f]{64}', digest)
            or hashlib.sha256(data).hexdigest() != digest
            or (size is not None and len(data) != int(size))):
        raise ValueError('Published repository checksum mismatch')
    return data


def published_packages(source, destination, home):
    """Recover existing packages through signed APT/DNF metadata, including legacy sites.

    Only the configured signing key is trusted, never a key fetched from Pages.
    Missing/unavailable/invalid previous state is fatal, not an empty repository.
    A local directory exercises the identical trust chain in offline CI.
    """
    destination.mkdir()
    keyring = destination / 'trusted.gpg'
    keyring.write_bytes(run(['gpg', '--homedir', home, '--batch', '--export', signing_identity(home)]))

    def fetch(name):
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', name) or any(p in ('', '.', '..') for p in name.split('/')):
            raise ValueError('Unsafe published repository path: ' + name)
        if isinstance(source, Path):
            path = source / name
            if any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError('Symlink in published repository')
            return path.read_bytes()
        if not source.startswith('https://'):
            raise ValueError('Previous repository requires HTTPS')
        request = Request(source.rstrip('/') + '/' + name, headers={'Cache-Control': 'no-cache'})
        with urlopen(request, timeout=60) as response:
            data = response.read(256 * 1024 * 1024 + 1)
        if len(data) > 256 * 1024 * 1024:
            raise ValueError('Published repository file exceeds limit')
        return data

    def authenticated(name, signature):
        data = fetch(name)
        target = destination / 'metadata'
        target.write_bytes(data)
        signed = destination / 'metadata.asc'
        signed.write_bytes(fetch(signature))
        run(['gpgv', '--keyring', keyring.resolve(), signed, target])
        return data

    release = Parser().parsestr(authenticated('apt/Release', 'apt/Release.gpg').decode())
    hashes = [line.split() for line in release['SHA256'].splitlines() if line.strip()]
    entries = [entry for entry in hashes if len(entry) == 3 and entry[2] == 'Packages']
    if len(entries) != 1:
        raise ValueError('Expected one authenticated APT Packages index')
    digest, size, _ = entries[0]
    index = checked_bytes(fetch('apt/Packages'), digest, size)
    packages = []

    def recover(name, digest, size):
        if not (re.fullmatch(r'apt/pool/renyyt_\d+\.\d+\.\d+-\d+_all\.deb', name)
                or re.fullmatch(r'rpm/Packages/renyyt-\d+\.\d+\.\d+-\d+\.noarch\.rpm', name)):
            raise ValueError('Unexpected published package path: ' + name)
        target = destination / Path(name).name
        if target.exists():
            raise ValueError('Duplicate published package: ' + name)
        target.write_bytes(checked_bytes(fetch(name), digest, size))
        packages.append(target)

    for paragraph in index.decode().strip().split('\n\n'):
        fields = Parser().parsestr(paragraph)
        recover('apt/' + fields['Filename'], fields['SHA256'], fields['Size'])
    repomd = ET.fromstring(authenticated('rpm/repodata/repomd.xml', 'rpm/repodata/repomd.xml.asc'))
    ns = {'r': 'http://linux.duke.edu/metadata/repo', 'c': 'http://linux.duke.edu/metadata/common'}
    primary = repomd.findall("r:data[@type='primary']", ns)
    if len(primary) != 1:
        raise ValueError('Expected one authenticated RPM primary index')
    primary = primary[0]
    checksum = primary.find('r:checksum', ns)
    location = primary.find('r:location', ns).attrib['href']
    if checksum.attrib['type'] != 'sha256' or not re.fullmatch(r'repodata/[A-Za-z0-9_-]+-primary\.xml\.gz', location):
        raise ValueError('Unexpected RPM primary index')
    compressed = checked_bytes(fetch('rpm/' + location), checksum.text, primary.findtext('r:size', namespaces=ns))
    metadata = ET.fromstring(gzip.decompress(compressed))
    for package in metadata.findall('c:package', ns):
        checksum = package.find('c:checksum', ns)
        if checksum.attrib['type'] != 'sha256':
            raise ValueError('RPM package requires SHA256')
        recover('rpm/' + package.find('c:location', ns).attrib['href'], checksum.text,
                package.find('c:size', ns).attrib['package'])
    if not any(p.suffix == '.deb' for p in packages) or not any(p.suffix == '.rpm' for p in packages):
        raise ValueError('Previous repository must contain deb and rpm packages')
    return packages


def rpm_content(path):
    # RPM signing changes the signature header, not the immutable main header or payload.
    run(['rpmkeys', '--checksig', '--nosignature', path])
    result = run(['rpm', '-qp', '--qf', '%{SHA256HEADER}\n%{PAYLOADDIGEST}\n', path], text=True)
    fields = result.splitlines()
    if len(fields) != 2 or any(not re.fullmatch(r'[0-9a-f]{64}', field) for field in fields):
        raise ValueError('RPM requires immutable header and payload SHA256 digests')
    return fields


def build_site(packages, output, home, previous=()):
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
    retained = {p.name: p for p in previous}
    if len(retained) != len(previous):
        raise ValueError('Duplicate previous package filename')
    incoming = {p.name: p for p in packages}
    if len(incoming) != len(packages):
        raise ValueError('Duplicate package filename')
    for name in retained.keys() & incoming.keys():
        old, new = retained[name], incoming[name]
        same = (old.read_bytes() == new.read_bytes()) if old.suffix == '.deb' else rpm_content(old) == rpm_content(new)
        if not same:
            raise ValueError('Published package cannot be replaced: ' + name)
    for name, source in sorted({**incoming, **retained}.items()):
        folder = apt / 'pool' if source.suffix == '.deb' else rpm / 'Packages'
        destination = folder / source.name
        if destination.exists():
            raise ValueError('Duplicate package filename: ' + source.name)
        shutil.copyfile(str(source), str(destination))
        if source.suffix == '.rpm' and name not in retained:
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
    previous = parser.add_mutually_exclusive_group()
    previous.add_argument('--previous-url', default=BASE_URL, help='Existing HTTPS repository; required to remain available')
    previous.add_argument('--previous', type=Path, help='Existing signed site directory (offline validation)')
    previous.add_argument('--bootstrap', action='store_true', help='Explicit first publication ONLY; never use to recover a failed refresh')
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
            old = [] if args.bootstrap else published_packages(args.previous or args.previous_url, root / 'previous', home)
            fingerprint = build_site(verified_packages(source, allow_empty=bool(old)), args.output.resolve(), home, old)
            print('Repository public signing key: ' + fingerprint)
        finally:
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'gpg-agent'], check=False)


if __name__ == '__main__':
    main()
