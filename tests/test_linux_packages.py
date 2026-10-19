"""Native package ownership, removal and purge regressions without host changes."""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
lifecycle = None
if sys.platform.startswith('linux'):
    SPEC = importlib.util.spec_from_file_location('renyyt_lifecycle', ROOT / 'deploy/linux/lifecycle.py')
    lifecycle = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(lifecycle)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux package lifecycle')
class NativeLifecycleChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        names = {'CONTROL': 'var/lib/renyyt-package', 'STATE': 'var/lib/renyyt', 'CONFIG': 'etc/renyyt',
                 'LIBRARY': 'usr/lib/renyyt', 'RESOURCES': 'usr/share/renyyt', 'UNIT_DIRECTORY': 'etc/systemd/system',
                 'SYSTEM_UNITS': 'usr/lib/systemd/system', 'PURGE_COMMAND': 'usr/sbin/renyyt-purge'}
        for name, relative in names.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            patch = mock.patch.object(lifecycle, name, path)
            patch.start()
            self.addCleanup(patch.stop)
        self.users, self.groups, self.calls = {}, {}, []
        for name, replacement in [('ROOT_UID', os.getuid()), ('command', self.command), ('systemd_running', lambda: False)]:
            patch = mock.patch.object(lifecycle, name, replacement)
            patch.start()
            self.addCleanup(patch.stop)
        for target, replacement in [('pwd.getpwnam', lambda key: self.lookup(self.users, key)),
                                    ('grp.getgrnam', lambda key: self.lookup(self.groups, key)),
                                    ('os.chown', lambda *args: None)]:
            patch = mock.patch.object(
                getattr(lifecycle, target.split('.')[0]), target.split('.')[1], replacement)
            patch.start()
            self.addCleanup(patch.stop)

    @staticmethod
    def lookup(values, key):
        if key not in values:
            raise KeyError(key)
        return values[key]

    def command(self, args, check=True):
        self.calls.append(args)
        if args[0] == 'groupadd':
            self.groups['renyyt'] = SimpleNamespace(gr_gid=9001)
        elif args[0] == 'useradd':
            self.users['renyyt'] = SimpleNamespace(pw_uid=9002)
        elif args[0] == 'userdel':
            self.users.pop('renyyt')
        elif args[0] == 'groupdel':
            self.groups.pop('renyyt')
        return SimpleNamespace(returncode=0, stdout='loaded\n', stderr='')

    def install(self, package_format='deb'):
        lifecycle.prepare(package_format)
        lifecycle.CONFIG.mkdir(mode=0o700)
        (lifecycle.CONFIG / 'renyyt.env').write_text('RENYYT_PORT=8899\n')
        lifecycle.configure(package_format)
        (lifecycle.STATE / 'reminders.sqlite3').write_bytes(b'synthetic state')
        (lifecycle.STATE / 'reminders.sqlite3-wal').write_bytes(b'synthetic sidecar')

    def test_remove_preserves_data_and_purge_removes_owned_files_and_accounts(self):
        self.install()
        lifecycle.remove('deb')
        lifecycle.removed('deb')
        self.assertTrue((lifecycle.CONFIG / 'renyyt.env').is_file())
        self.assertTrue((lifecycle.STATE / 'reminders.sqlite3').is_file())
        self.assertIn('renyyt', self.users)
        outside = self.root / 'outside'
        outside.write_text('keep')
        lifecycle.purge_state('deb')
        lifecycle.purge_state('deb')
        for path in (lifecycle.CONFIG, lifecycle.STATE, lifecycle.CONTROL):
            self.assertFalse(path.exists())
        self.assertEqual(self.users, {})
        self.assertEqual(self.groups, {})
        self.assertEqual(outside.read_text(), 'keep')

    def test_rpm_erase_restores_even_unchanged_config(self):
        self.install('rpm')
        lifecycle.remove('rpm')
        shutil.rmtree(str(lifecycle.CONFIG))  # Simulate RPM removing an unchanged %config.
        lifecycle.removed('rpm')
        self.assertEqual((lifecycle.CONFIG / 'renyyt.env').read_text(), 'RENYYT_PORT=8899\n')
        self.assertEqual(lifecycle.CONFIG.stat().st_mode & 0o777, 0o700)
        lifecycle.purge_state('rpm')
        self.assertFalse(lifecycle.CONTROL.exists())

    def test_preexisting_identities_survive_upgrade_and_purge(self):
        self.users['renyyt'] = SimpleNamespace(pw_uid=7001)
        self.groups['renyyt'] = SimpleNamespace(gr_gid=7002)
        self.install()
        lifecycle.prepare('deb')
        lifecycle.configure('deb')
        self.assertFalse(lifecycle.read_state()['user_created'])
        self.assertFalse(lifecycle.read_state()['group_created'])
        lifecycle.purge_state('deb')
        self.assertEqual(self.users['renyyt'].pw_uid, 7001)
        self.assertEqual(self.groups['renyyt'].gr_gid, 7002)

    def test_upgrade_does_not_enable_stopped_service(self):
        self.install()
        self.calls.clear()
        with mock.patch.object(lifecycle, 'systemd_running', return_value=True):
            lifecycle.configure('deb')
        self.assertIn(['deb-systemd-invoke', 'try-restart', 'renyyt.service'], self.calls)
        self.assertFalse(any('enable' in call or 'start' in call for call in self.calls))

    def test_unmanaged_installation_is_not_adopted(self):
        lifecycle.CONFIG.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'unmanaged'):
            lifecycle.prepare('deb')
        self.assertFalse(lifecycle.CONTROL.exists())
        self.assertEqual(self.calls, [])

    def test_replaced_account_is_not_deleted(self):
        self.install()
        self.users['renyyt'] = SimpleNamespace(pw_uid=12345)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            lifecycle.purge_state('deb')
        self.assertNotIn(['userdel', 'renyyt'], self.calls)
        self.assertTrue(lifecycle.CONTROL.is_dir())

    def test_state_symlink_cannot_delete_external_directory(self):
        self.install()
        shutil.rmtree(str(lifecycle.STATE))
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('untouched')
        lifecycle.STATE.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, 'non-directory'):
            lifecycle.purge_state('deb')
        self.assertEqual((outside / 'keep').read_text(), 'untouched')

    def test_untrusted_control_metadata_is_rejected(self):
        self.install()
        (lifecycle.CONTROL / 'state.json').chmod(0o666)
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
            lifecycle.purge_state('deb')
        self.assertTrue(lifecycle.STATE.is_dir())
        self.assertIn('renyyt', self.users)

    def test_purge_removes_native_package_before_its_state(self):
        self.install('rpm')
        self.calls.clear()
        with mock.patch.object(lifecycle, 'installed', return_value=True):
            lifecycle.purge()
        self.assertEqual(self.calls[0], ['rpm', '-e', 'renyyt'])
        self.assertFalse(lifecycle.STATE.exists())
        self.assertFalse(lifecycle.CONTROL.exists())

    def test_default_service_identity_cannot_be_root(self):
        self.users['renyyt'] = SimpleNamespace(pw_uid=0)
        self.groups['renyyt'] = SimpleNamespace(gr_gid=9001)
        lifecycle.prepare('deb')
        with self.assertRaisesRegex(RuntimeError, 'must not be root'):
            lifecycle.configure('deb')


class NativePayloadChecks(unittest.TestCase):
    def test_payload_permissions_resources_and_private_file_exclusions(self):
        specification = importlib.util.spec_from_file_location('renyyt_package_linux', ROOT / 'scripts/package_linux.py')
        packager = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(packager)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'source'
            payload = Path(folder) / 'payload'
            root.mkdir()
            payload.mkdir()
            for directory in ('scripts', 'deploy'):
                shutil.copytree(str(ROOT / directory), str(root / directory))
            for name in ('README.md', 'TECHNICAL.md', 'TESTING.md', 'API.md', 'CHANGELOG.md', 'VERSION', 'LICENSE', '.env.example'):
                shutil.copyfile(str(ROOT / name), str(root / name))
            for source in ROOT.glob('README.*.md'):
                shutil.copyfile(str(source), str(root / source.name))
            for name in ('src/renyyt/__init__.py', 'web/app.js', 'dist/index.html', 'dist/assets/app.hash.js',
                         'web/.env', 'web/.env.production', 'web/reminders.sqlite3-wal', 'dist/old.deb',
                         'dist/old.rpm', 'dist/assets/app.js.gz', 'src/renyyt/__pycache__/private.py'):
                source = root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text('synthetic content')
            packager.stage(root, payload, 1700000000)
            names = {path.relative_to(payload).as_posix() for path in payload.rglob('*') if path.is_file()}
            for name in ('usr/lib/renyyt/renyyt/__init__.py', 'usr/share/renyyt/dist/index.html',
                         'usr/share/renyyt/dist/assets/app.hash.js', 'usr/share/renyyt/README.et.md'):
                self.assertIn(name, names)
            self.assertFalse(any(name.endswith(('.deb', '.rpm', '.gz', '-wal', '/.env', '.production', 'private.py')) for name in names))
            self.assertEqual((payload / 'etc/renyyt').stat().st_mode & 0o777, 0o700)
            self.assertEqual((payload / 'etc/renyyt/renyyt.env').stat().st_mode & 0o777, 0o600)
            self.assertEqual((payload / 'usr/bin/renyyt').stat().st_mode & 0o777, 0o755)
            unit = (payload / 'usr/lib/systemd/system/renyyt.service').read_text()
            self.assertIn('ExecStart=/usr/bin/renyyt', unit)
            self.assertNotIn('/opt/renyyt', unit)
