#!/usr/bin/python3
"""Root-only lifecycle and purge for the Renyyt deb/rpm packages (stdlib only)."""
import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import uuid

ROOT_UID = 0
CONTROL = Path('/var/lib/renyyt-package')
STATE = Path('/var/lib/renyyt')
CONFIG = Path('/etc/renyyt')  # Legacy 1.0.0 directory; never /etc itself.
CONFIG_FILE = Path('/etc/renyyt.env')
LIBRARY = Path('/usr/lib/renyyt')
RESOURCES = Path('/usr/share/renyyt')
UNIT_DIRECTORY = Path('/etc/systemd/system')
SYSTEM_UNITS = Path('/usr/lib/systemd/system')
PURGE_COMMAND = Path('/usr/sbin/renyyt-purge')
UNITS = ('renyyt.service', 'renyyt-reminders.service', 'renyyt-reminders.timer')


def command(args, check=True):
    return subprocess.run(args, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def exists(path):
    return path.exists() or path.is_symlink()


def trusted_directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != ROOT_UID or info.st_mode & 0o022:
        raise RuntimeError('Unsafe package control directory: %s' % path)


def read_state(required=True):
    if not exists(CONTROL):
        if required:
            raise RuntimeError('No package ownership record; refusing to remove unmanaged files.')
        return None
    trusted_directory(CONTROL)
    path = CONTROL / 'state.json'
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != ROOT_UID or info.st_mode & 0o077:
        raise RuntimeError('Unsafe package ownership record.')
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema') != 1 or value.get('format') not in ('deb', 'rpm'):
        raise RuntimeError('Unsupported package ownership record.')
    return value


def write_file(name, content, mode=0o600):
    trusted_directory(CONTROL)
    temporary = CONTROL / ('.new-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as output:
            output.write(content)
        temporary.chmod(mode)
        os.replace(str(temporary), str(CONTROL / name))
    finally:
        if exists(temporary):
            temporary.unlink()


def save(value):
    write_file('state.json', (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8'))


def source_bytes():
    return globals().get('_BOOTSTRAP_SOURCE') or Path(__file__).read_bytes()


def prepare(package_format):
    if exists(CONTROL):
        value = read_state()
        if value['format'] != package_format:
            raise RuntimeError('A different native package format already owns this installation.')
    else:
        reserved = [STATE, CONFIG, CONFIG_FILE, LIBRARY, RESOURCES, PURGE_COMMAND]
        reserved += [UNIT_DIRECTORY / name for name in UNITS]
        reserved += [UNIT_DIRECTORY / (name + '.d') for name in UNITS]
        reserved += [SYSTEM_UNITS / name for name in UNITS]
        for path in reserved:
            if exists(path):
                raise RuntimeError('Existing unmanaged installation at %s. See deploy/linux/README.md migration instructions.' % path)
        CONTROL.mkdir(mode=0o700)
        value = {'schema': 1, 'format': package_format, 'installed': False,
                 'user_created': False, 'group_created': False, 'uid': None, 'gid': None}
        save(value)
    # This root-owned copy intentionally survives ordinary removal, for RPM purge.
    write_file('purge.py', source_bytes(), 0o700)
    shell = globals().get('_PURGE_SHELL') or Path(__file__).with_name('purge.sh').read_bytes()
    write_file('purge', shell, 0o700)


def systemd_running():
    return Path('/run/systemd/system').is_dir()


def stop_services():
    if not systemd_running():
        return
    for unit in UNITS:
        result = command(['systemctl', 'show', unit, '--property=LoadState', '--value'], check=False)
        if result.stdout.strip() == 'not-found':
            continue
        if result.returncode:
            raise RuntimeError('Cannot determine systemd state for %s; refusing cleanup.' % unit)
        command(['systemctl', 'stop', unit])
        command(['systemctl', 'disable', unit])


def configure_file():
    trusted_directory(CONFIG_FILE.parent)
    legacy = CONFIG / 'renyyt.env'
    if exists(CONFIG):
        trusted_directory(CONFIG)
    if exists(CONFIG_FILE):
        if CONFIG_FILE.is_symlink() or not CONFIG_FILE.is_file():
            raise RuntimeError('Unsafe active configuration path.')
        if exists(legacy):
            raise RuntimeError('Both old and new configuration exist; resolve explicitly before upgrade.')
        if CONFIG_FILE.lstat().st_uid != ROOT_UID:
            raise RuntimeError('Active configuration must be root-owned.')
        CONFIG_FILE.chmod(0o600)
        return
    if exists(legacy):
        info = legacy.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != ROOT_UID:
            raise RuntimeError('Unsafe legacy configuration; refusing migration.')
        content = legacy.read_bytes()
    else:
        content = (LIBRARY / 'renyyt.env.example').read_bytes()
    temporary = CONFIG_FILE.parent / ('.renyyt-env-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as output:
            temporary.chmod(0o600)
            output.write(content)
        # Atomic no-clobber publication, then remove only the migrated file.
        os.link(str(temporary), str(CONFIG_FILE))
    finally:
        if exists(temporary):
            temporary.unlink()
    if exists(legacy):
        legacy.unlink()
    if exists(CONFIG) and not any(CONFIG.iterdir()):
        CONFIG.rmdir()


def configure(package_format):
    value = read_state()
    if value['format'] != package_format:
        raise RuntimeError('Package format does not match ownership record.')
    try:
        group = grp.getgrnam('renyyt')
    except KeyError:
        command(['groupadd', '--system', 'renyyt'])
        group = grp.getgrnam('renyyt')
        value.update(group_created=True, gid=group.gr_gid)
        save(value)
    if group.gr_gid == 0:
        raise RuntimeError('The service group must not be root.')
    if value['group_created'] and group.gr_gid != value['gid']:
        raise RuntimeError('The package-created group was replaced; manual intervention required.')
    try:
        user = pwd.getpwnam('renyyt')
    except KeyError:
        command(['useradd', '--system', '--gid', 'renyyt', '--home-dir', str(STATE),
                 '--no-create-home', '--shell', shutil.which('nologin') or '/usr/sbin/nologin', 'renyyt'])
        user = pwd.getpwnam('renyyt')
        value.update(user_created=True, uid=user.pw_uid)
        save(value)
    if user.pw_uid == 0:
        raise RuntimeError('The service user must not be root.')
    if value['user_created'] and user.pw_uid != value['uid']:
        raise RuntimeError('The package-created user was replaced; manual intervention required.')
    configure_file()
    if exists(STATE):
        if STATE.is_symlink() or not STATE.is_dir():
            raise RuntimeError('Unsafe application state directory.')
    else:
        STATE.mkdir(mode=0o700)
    STATE.chmod(0o700)
    os.chown(str(STATE), user.pw_uid, group.gr_gid)
    if systemd_running():
        command(['systemctl', 'daemon-reload'])
        if value['installed']:
            runner = 'deb-systemd-invoke' if package_format == 'deb' else 'systemctl'
            command([runner, 'try-restart', 'renyyt.service'])
    # New installs remain disabled until the administrator configures and enables them.
    value['installed'] = True
    save(value)


def remove(package_format):
    value = read_state()
    stop_services()
    value['installed'] = False
    save(value)


def removed(package_format):
    value = read_state(required=False)
    if value is None:
        return
    if systemd_running():
        command(['systemctl', 'daemon-reload'])


def remove_tree(path):
    if not exists(path):
        return
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError('Refusing recursive cleanup of non-directory: %s' % path)
    shutil.rmtree(str(path))


def verify_created_identities(value):
    # Refuse before stopping services or deleting data if ownership was reassigned.
    for flag, lookup, attribute, key, label in (
        ('user_created', pwd.getpwnam, 'pw_uid', 'uid', 'User'),
        ('group_created', grp.getgrnam, 'gr_gid', 'gid', 'Group'),
    ):
        if value[flag]:
            try:
                identity = lookup('renyyt')
            except KeyError:
                continue
            if getattr(identity, attribute) != value[key]:
                raise RuntimeError(label + ' identity changed; refusing cleanup.')


def purge_state(package_format):
    value = read_state(required=False)
    if value is None:
        return
    if value['format'] != package_format:
        raise RuntimeError('Package format does not match ownership record.')
    verify_created_identities(value)
    stop_services()
    remove_tree(STATE)
    for suffix in ('', '.rpmsave', '.rpmnew', '.dpkg-old', '.dpkg-dist', '.dpkg-new'):
        path = Path(str(CONFIG_FILE) + suffix)
        if exists(path):
            if path.is_dir() and not path.is_symlink():
                raise RuntimeError('Unexpected directory at configuration file path.')
            path.unlink()
    if exists(CONFIG):
        trusted_directory(CONFIG)
        for suffix in ('', '.rpmsave', '.rpmnew', '.dpkg-old', '.dpkg-dist', '.dpkg-new'):
            path = CONFIG / ('renyyt.env' + suffix)
            if exists(path):
                if path.is_dir() and not path.is_symlink():
                    raise RuntimeError('Unexpected directory at configuration file path.')
                path.unlink()
        try:
            CONFIG.rmdir()
        except OSError:
            # Administrator-created files are not package-owned.
            if not any(CONFIG.iterdir()):
                raise
    for unit in UNITS:
        remove_tree(UNIT_DIRECTORY / (unit + '.d'))
        override = UNIT_DIRECTORY / unit
        if exists(override):
            if override.is_dir() and not override.is_symlink():
                raise RuntimeError('Unexpected directory at systemd unit path.')
            override.unlink()
    if value['user_created']:
        try:
            user = pwd.getpwnam('renyyt')
        except KeyError:
            user = None
        if user:
            if user.pw_uid != value['uid']:
                raise RuntimeError('User identity changed; refusing to delete it.')
            command(['userdel', 'renyyt'])
    if value['group_created']:
        try:
            group = grp.getgrnam('renyyt')
        except KeyError:
            group = None
        if group:
            if group.gr_gid != value['gid']:
                raise RuntimeError('Group identity changed; refusing to delete it.')
            command(['groupdel', 'renyyt'])
    if systemd_running():
        command(['systemctl', 'daemon-reload'])
        command(['systemctl', 'reset-failed', 'renyyt.service'], check=False)
    remove_tree(CONTROL)


def installed(package_format):
    if package_format == 'deb':
        result = command(['dpkg-query', '-W', '-f=${db:Status-Status}', 'renyyt'], check=False)
        return result.returncode == 0 and result.stdout.strip() != 'not-installed'
    return command(['rpm', '-q', '--quiet', 'renyyt'], check=False).returncode == 0


def purge():
    value = read_state(required=False)
    if value is None:
        print('No Renyyt native package state to purge.')
        return
    package_format = value['format']
    verify_created_identities(value)
    if installed(package_format):
        command(['dpkg', '--purge', 'renyyt'] if package_format == 'deb' else ['rpm', '-e', 'renyyt'])
    purge_state(package_format)
    print('Renyyt package-owned configuration, state and created accounts purged.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Renyyt native package lifecycle and complete purge')
    parser.add_argument('action', nargs='?', default='purge',
                        choices=('prepare', 'configure', 'remove', 'removed', 'purge-state', 'purge'))
    parser.add_argument('format', nargs='?', choices=('deb', 'rpm'))
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.error('Run this command as root.')
    if args.action == 'purge':
        purge()
    elif not args.format:
        parser.error('A package format is required for lifecycle hooks.')
    else:
        {'prepare': prepare, 'configure': configure, 'remove': remove,
         'removed': removed, 'purge-state': purge_state}[args.action](args.format)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print('renyyt-package: %s' % error, file=sys.stderr)
        sys.exit(1)
