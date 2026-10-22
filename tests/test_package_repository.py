"""Release trust checks run without importing production keys or installing packages."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('package_repository', Path(__file__).resolve().parents[1] / 'scripts/package_repository.py')
repository = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repository)


class RepositoryTrustTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.release = self.root / 'v1.0.2'
        self.release.mkdir()
        self.deb = self.release / 'renyyt_1.0.2-1_all.deb'
        self.rpm = self.release / 'renyyt-1.0.2-1.noarch.rpm'
        self.deb.write_bytes(b'synthetic-deb')
        self.rpm.write_bytes(b'synthetic-rpm')
        self.checksums = self.release / 'SHA256SUMS'
        self.checksums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in (self.deb, self.rpm)))

    def identities(self, args, **kwargs):
        if args[0] == 'rpm':
            return 'renyyt 1.0.2 1 noarch'
        return 'Package: renyyt\nVersion: 1.0.2-1\nArchitecture: all\n'

    def test_verified_identity_and_checksums(self):
        with mock.patch.object(repository, 'run', side_effect=self.identities):
            self.assertEqual(set(repository.verified_packages(self.root)), {self.deb, self.rpm})

    def test_tampering_rejected_before_reading_package_metadata(self):
        for path in (self.deb, self.rpm):
            with self.subTest(path=path.name), mock.patch.object(repository, 'run', side_effect=self.identities):
                data = path.read_bytes()
                path.write_bytes(data + b'tampered')
                with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                    repository.verified_packages(self.root)
                path.write_bytes(data)

    def test_unexpected_package_identity_rejected(self):
        with mock.patch.object(repository, 'run', return_value='unrelated package'):
            with self.assertRaisesRegex(ValueError, 'identity'):
                repository.verified_packages(self.root)

    def test_missing_duplicate_or_incomplete_assets_fail(self):
        self.rpm.unlink()
        with self.assertRaisesRegex(ValueError, 'one deb and one rpm'):
            repository.verified_packages(self.root)
        self.rpm.write_bytes(b'synthetic-rpm')
        self.checksums.write_text(self.checksums.read_text() * 2)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            repository.verified_packages(self.root)

    def test_nonstable_or_unsafe_package_paths_not_selected(self):
        for tag in ('v1.0.2-rc1', '../v1.0.2', 'v1.0.2\n', 'main'):
            self.assertEqual(repository.package_names(tag, [self.deb.name, self.rpm.name]), [])
        self.assertEqual(repository.package_names('v1.0.2', ['../' + self.deb.name]), [])

    def test_download_filters_and_checksums_requirement(self):
        def release(tag, **kwargs):
            return dict(tag_name=tag, draft=False, prerelease=False, assets=[{'name': n} for n in (self.deb.name, self.rpm.name, 'SHA256SUMS')], **kwargs)
        releases = [release('v1.0.2'), dict(release('v1.0.3'), draft=True), dict(release('v1.0.4'), prerelease=True), release('../v1.0.2')]
        with mock.patch.object(repository, 'run', side_effect=['\n'.join(json.dumps(r) for r in releases), b'']) as run:
            destination = self.root / 'downloads'
            destination.mkdir()
            repository.download_releases(destination)
            self.assertEqual(run.call_count, 2)
            self.assertIn('v1.0.2', run.call_args[0][0])
        releases[0]['assets'].pop()
        with mock.patch.object(repository, 'run', return_value=json.dumps(releases[0])):
            with self.assertRaisesRegex(ValueError, 'Missing release checksums'):
                repository.download_releases(self.root)

    def test_signing_key_policy(self):
        # Public key metadata only; no real key material belongs in unit tests.
        record = ['sec', 'u', '4096', '1', 'KEYID', '1', '4102444800', '', '', '', '', 'scSC']
        fingerprint = 'A' * 40
        def listing(fields):
            return ':'.join(fields) + '\nfpr:::::::::' + fingerprint + ':\n'
        with mock.patch.object(repository, 'run', return_value=listing(record)):
            self.assertEqual(repository.signing_identity(self.root), fingerprint)
        for position, value in ((1, 'r'), (2, '2048'), (3, '22'), (6, '1'), (6, ''), (11, 'eE')):
            fields = record.copy()
            fields[position] = value
            with self.subTest(position=position, value=value), mock.patch.object(repository, 'run', return_value=listing(fields)):
                with self.assertRaises(ValueError):
                    repository.signing_identity(self.root)
        with mock.patch.object(repository, 'run', return_value=listing(record) * 2):
            with self.assertRaises(ValueError):
                repository.signing_identity(self.root)


if __name__ == '__main__':
    unittest.main()
