#!/usr/bin/env python3
"""Destructive native lifecycle smoke test: ONLY in disposable containers/CI VMs."""
import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import time
import urllib.request


def run(*args):
    subprocess.run(args, check=True)


def smoke(systemd=False, push_python=None):
    user = pwd.getpwnam('renyyt')
    group = grp.getgrnam('renyyt')
    assert user.pw_uid != 0 and group.gr_gid != 0
    assert Path('/etc/renyyt.env').stat().st_mode & 0o777 == 0o600
    assert Path('/var/lib/renyyt').stat().st_uid == user.pw_uid
    run('/usr/bin/renyyt', '--check')
    # If the distribution supplies the optional library, exercise its actual
    # VAPID API without sending notifications or printing private key material.
    provider = push_python or '/usr/bin/python3'
    probe = subprocess.run([provider, '-c', 'import pywebpush'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    if push_python:
        assert probe.returncode == 0, 'Configured optional Python cannot import pywebpush'
    if probe.returncode == 0:
        generated = subprocess.check_output([provider, '/usr/bin/renyyt', 'reminders', 'generate-vapid'], text=True)
        assert 'RENYYT_VAPID_PRIVATE_KEY=' in generated and 'RENYYT_VAPID_PUBLIC_KEY=' in generated
        print('PUSH_AVAILABILITY: optional library and VAPID generation OK')
        if push_python and systemd:
            # Exercise the documented override and internal scheduler with fresh
            # ephemeral keys. Never print them or send a real notification.
            config = Path('/etc/renyyt.env')
            config.write_text(config.read_text() + generated +
                              'RENYYT_REMINDERS_ENABLED=true\n'
                              'RENYYT_REMINDERS_INTERNAL_SCHEDULER=true\n'
                              'RENYYT_REMINDERS_TIMEZONE=UTC\n'
                              'RENYYT_VAPID_SUBJECT=mailto:admin@example.com\n')
            override = Path('/etc/systemd/system/renyyt.service.d/push.conf')
            override.parent.mkdir(mode=0o755, parents=True)
            override.write_text('[Service]\nExecStart=\nExecStart=' + provider + ' /usr/bin/renyyt\n')
            run('systemctl', 'daemon-reload')
    for language in ('fi', 'en', 'sv', 'uk', 'ar', 'fa', 'vi', 'zh-Hans', 'et'):
        assert Path('/usr/share/renyyt/README.' + language + '.md').is_file()
    assert not list(Path('/usr/lib/renyyt').rglob('*.pyc'))
    process = None
    if systemd:
        run('systemctl', 'enable', '--now', 'renyyt.service')
    else:
        def identity():
            os.setgroups([])
            os.setgid(group.gr_gid)
            os.setuid(user.pw_uid)
        process = subprocess.Popen(['/usr/bin/renyyt'], cwd='/var/lib/renyyt', preexec_fn=identity)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18514/ready', timeout=.2) as response:
                    assert json.load(response)['status'] == 'ready'
                break
            except OSError:
                time.sleep(.1)
        else:
            raise AssertionError('Service did not become ready')
        with urllib.request.urlopen('http://127.0.0.1:18514/README.et.md') as response:
            assert response.status == 200
    finally:
        if process:
            process.send_signal(signal.SIGTERM)
            assert process.wait(timeout=15) == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable', action='store_true', required=True)
    parser.add_argument('--format', choices=('deb', 'rpm'), required=True)
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--upgrades', type=Path, required=True)
    parser.add_argument('--legacy-packages', type=Path, help='Released 1.0.0 packages for migration checks')
    parser.add_argument('--systemd', action='store_true')
    parser.add_argument('--push-python', help='Optional isolated Python interpreter to test with systemd')
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Run only as root in a disposable environment'
    suffix = '.' + args.format
    initial = str(next(args.packages.glob('*' + suffix)).resolve())
    upgrade = str(next(args.upgrades.glob('*' + suffix)).resolve())
    install = ('apt-get', 'install', '-y') if args.format == 'deb' else ('dnf', 'install', '-y')
    remove = ('apt-get', 'remove', '-y', 'renyyt') if args.format == 'deb' else ('dnf', 'remove', '-y', '--noautoremove', 'renyyt')
    config = Path('/etc/renyyt.env')
    state = Path('/var/lib/renyyt')
    control = Path('/var/lib/renyyt-package')
    # Sentinels outside package ownership must survive every remove/purge path.
    sentinels = (Path('/opt/renyyt/native-test-preserve'), Path('/var/lib/renyyt-custom/native-test-preserve'))
    for sentinel in sentinels:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text('unrelated synthetic data')
    run(*install, initial)
    if args.format == 'deb':
        suggestion = subprocess.check_output(['dpkg-query', '-W', '-f=${Suggests}', 'renyyt'], text=True)
    else:
        suggestion = subprocess.check_output(['rpm', '-q', '--suggests', 'renyyt'], text=True)
    assert 'python3-pywebpush' in suggestion
    smoke(args.systemd, args.push_python)
    config.write_text(config.read_text() + '# synthetic retained configuration\n')
    saved = config.read_bytes()
    (state / 'synthetic.sqlite3').write_bytes(b'synthetic data')
    (state / 'external-link').symlink_to(sentinels[1].parent, target_is_directory=True)
    run(*install, upgrade)
    assert config.read_bytes() == saved
    if args.systemd:
        run('systemctl', 'is-active', '--quiet', 'renyyt.service')
        run('systemctl', 'disable', '--now', 'renyyt.service')
        run(*install, initial, '--allow-downgrades')
        assert subprocess.run(['systemctl', 'is-active', '--quiet', 'renyyt.service']).returncode != 0
        assert subprocess.run(['systemctl', 'is-enabled', '--quiet', 'renyyt.service']).returncode != 0
    run(*remove)
    assert config.read_bytes() == saved
    assert (state / 'synthetic.sqlite3').read_bytes() == b'synthetic data'
    assert not Path('/usr/bin/renyyt').exists()
    assert not Path('/usr/lib/renyyt').exists()
    # Model Python being autoremoved: the retained command and Debian postrm
    # must complete without being able to execute /usr/bin/python3.
    python = Path('/usr/bin/python3')
    hidden_python = Path('/usr/bin/python3.native-test-hidden')
    python.rename(hidden_python)
    try:
        run('/bin/sh', str(control / 'purge'))
    finally:
        hidden_python.rename(python)
    if args.format == 'deb':
        run('dpkg', '--purge', 'renyyt')
    for path in (state, control, config):
        assert not path.exists(), str(path)
    try:
        pwd.getpwnam('renyyt')
    except KeyError:
        pass
    else:
        raise AssertionError('Package-created user retained after purge')
    # A second install tests ordinary erase with unchanged configuration.
    run(*install, initial)
    saved = config.read_bytes()
    run(*remove)
    assert config.read_bytes() == saved
    run(str(control / 'purge'))
    # Purge while installed must remove both payload and retained state.
    run(*install, initial)
    (state / 'external-link').symlink_to(sentinels[1].parent, target_is_directory=True)
    run('/usr/sbin/renyyt-purge')
    assert not Path('/usr/bin/renyyt').exists()
    assert not control.exists() and not state.exists() and not config.exists()
    # Native hooks must also preserve identities and extra configuration that
    # existed independently of the package, even on an actual distribution.
    run('groupadd', '--system', 'renyyt')
    run('useradd', '--system', '--gid', 'renyyt', '--no-create-home', 'renyyt')
    old_uid, old_gid = pwd.getpwnam('renyyt').pw_uid, grp.getgrnam('renyyt').gr_gid
    run(*install, initial)
    extra = Path('/etc/renyyt-native-test-admin.txt')
    extra.write_text('unrelated configuration')
    run(*remove)
    config.unlink()
    config.symlink_to(sentinels[0])
    run(str(control / 'purge'))
    assert pwd.getpwnam('renyyt').pw_uid == old_uid
    assert grp.getgrnam('renyyt').gr_gid == old_gid
    assert extra.read_text() == 'unrelated configuration'
    assert not config.exists() and not config.is_symlink()
    for sentinel in sentinels:
        assert sentinel.read_text() == 'unrelated synthetic data'
    if args.legacy_packages:
        legacy_package = str(next(args.legacy_packages.glob('*' + suffix)).resolve())
        run(*install, legacy_package)
        legacy_config = Path('/etc/renyyt/renyyt.env')
        original = legacy_config.read_bytes()
        assert b'RENYYT_PORT=8787' in original
        run(*install, upgrade)
        assert config.read_bytes() == original  # Preserve the existing explicit port.
        assert config.stat().st_mode & 0o777 == 0o600
        assert not legacy_config.exists()
        assert not legacy_config.parent.exists()
        if args.systemd:
            run('systemctl', 'enable', '--now', 'renyyt.service')
            for attempt in range(100):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8787/ready', timeout=.2) as response:
                        assert json.load(response)['status'] == 'ready'
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise AssertionError('Migrated service did not use its retained port')
        run('/usr/sbin/renyyt-purge')
        assert not config.exists() and not state.exists() and not control.exists()
        for sentinel in sentinels:
            assert sentinel.read_text() == 'unrelated synthetic data'
        print('Released 1.0.0 upgrade, flat config migration and explicit port preservation: OK')
    print('Native lifecycle and preservation of unrelated files/identities: OK')


if __name__ == '__main__':
    main()
