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


def smoke(systemd=False):
    user = pwd.getpwnam('renyyt')
    group = grp.getgrnam('renyyt')
    assert user.pw_uid != 0 and group.gr_gid != 0
    assert Path('/etc/renyyt').stat().st_mode & 0o777 == 0o700
    assert Path('/etc/renyyt/renyyt.env').stat().st_mode & 0o777 == 0o600
    assert Path('/var/lib/renyyt').stat().st_uid == user.pw_uid
    run('/usr/bin/renyyt', '--check')
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
                with urllib.request.urlopen('http://127.0.0.1:8787/ready', timeout=.2) as response:
                    assert json.load(response)['status'] == 'ready'
                break
            except OSError:
                time.sleep(.1)
        else:
            raise AssertionError('Service did not become ready')
        with urllib.request.urlopen('http://127.0.0.1:8787/README.et.md') as response:
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
    parser.add_argument('--systemd', action='store_true')
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Run only as root in a disposable environment'
    suffix = '.' + args.format
    initial = str(next(args.packages.glob('*' + suffix)).resolve())
    upgrade = str(next(args.upgrades.glob('*' + suffix)).resolve())
    install = ('apt-get', 'install', '-y') if args.format == 'deb' else ('dnf', 'install', '-y')
    remove = ('apt-get', 'remove', '-y', 'renyyt') if args.format == 'deb' else ('dnf', 'remove', '-y', '--noautoremove', 'renyyt')
    config = Path('/etc/renyyt/renyyt.env')
    state = Path('/var/lib/renyyt')
    control = Path('/var/lib/renyyt-package')
    run(*install, initial)
    smoke(args.systemd)
    config.write_text(config.read_text() + '# synthetic retained configuration\n')
    saved = config.read_bytes()
    (state / 'synthetic.sqlite3').write_bytes(b'synthetic data')
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
    # Exercise the retained shell path, independent of Python cleanup.
    run('/bin/sh', str(control / 'purge'), '--state-only')
    if args.format == 'deb':
        run('dpkg', '--purge', 'renyyt')
    for path in (state, control, config.parent):
        assert not path.exists(), str(path)
    try:
        pwd.getpwnam('renyyt')
    except KeyError:
        pass
    else:
        raise AssertionError('Package-created user retained after purge')
    # A second install also tests ordinary erase of an unchanged RPM config.
    run(*install, initial)
    saved = config.read_bytes()
    run(*remove)
    assert config.read_bytes() == saved
    run(str(control / 'purge'))
    # Purge while installed must remove both payload and retained state.
    run(*install, initial)
    run('/usr/sbin/renyyt-purge')
    assert not Path('/usr/bin/renyyt').exists()
    assert not control.exists() and not state.exists() and not config.parent.exists()
    print('Native install, upgrade, remove and purge: OK')


if __name__ == '__main__':
    main()
