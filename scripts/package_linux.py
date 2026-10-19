#!/usr/bin/env python3
"""Build dependency-light deb/all and rpm/noarch packages from the same payload."""
import argparse
import base64
import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def epoch():
    value = int(os.environ.get('SOURCE_DATE_EPOCH', str(int(time.time()))))
    if value < 0:
        raise ValueError('SOURCE_DATE_EPOCH must be nonnegative')
    return value


def copy_file(source, destination, mode=0o644):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(source), str(destination))
    destination.chmod(mode)


def write(destination, content, mode=0o644):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding='utf-8')
    destination.chmod(mode)


def load_script(root, name):
    specification = importlib.util.spec_from_file_location('renyyt_' + name, Path(root) / ('scripts/' + name + '.py'))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def stage(root, destination, stamp):
    root, destination = Path(root), Path(destination)
    include = load_script(root, 'package').include
    for source in sorted((root / 'src/renyyt').rglob('*.py')):
        if include(root, source):
            copy_file(source, destination / 'usr/lib/renyyt' / source.relative_to(root / 'src'))
    for folder in ('web', 'dist'):
        for source in sorted((root / folder).rglob('*')):
            if source.is_file() and include(root, source):
                copy_file(source, destination / 'usr/share/renyyt' / source.relative_to(root))
    for name in ('README.md', 'TECHNICAL.md', 'TESTING.md', 'API.md', 'CHANGELOG.md', 'VERSION', 'LICENSE', '.env.example'):
        copy_file(root / name, destination / 'usr/share/renyyt' / name)
    for source in sorted(root.glob('README.*.md')):
        copy_file(source, destination / 'usr/share/renyyt' / source.name)
    copy_file(root / 'deploy/linux/lifecycle.py', destination / 'usr/lib/renyyt/lifecycle.py')
    copy_file(root / 'deploy/linux/purge.sh', destination / 'usr/lib/renyyt/purge.sh')
    write(destination / 'usr/bin/renyyt', '''#!/usr/bin/python3
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/usr/lib/renyyt")
os.environ.setdefault("RENYYT_DATA_ROOT", "/usr/share/renyyt")
os.environ.setdefault("RENYYT_REMINDERS_DB", "/var/lib/renyyt/reminders.sqlite3")
from renyyt.server import main
sys.exit(main())
''', 0o755)
    write(destination / 'usr/sbin/renyyt-purge', '''#!/usr/bin/python3
import runpy
runpy.run_path("/usr/lib/renyyt/lifecycle.py", run_name="__main__")
''', 0o755)
    service = (root / 'deploy/systemd/renyyt.service.example').read_text(encoding='utf-8')
    service = service.replace('WorkingDirectory=/opt/renyyt', 'WorkingDirectory=/var/lib/renyyt')
    service = service.replace('ExecStart=/opt/renyyt/venv/bin/renyyt', 'ExecStart=/usr/bin/renyyt')
    write(destination / 'usr/lib/systemd/system/renyyt.service', service)
    default_config = '# Renyyt native package settings; edit as root. See /usr/share/renyyt/.env.example.\n' \
        'RENYYT_HOST=127.0.0.1\nRENYYT_PORT=8787\nRENYYT_REMINDERS_DB=/var/lib/renyyt/reminders.sqlite3\n'
    write(destination / 'usr/lib/renyyt/renyyt.env.example', default_config)
    write(destination / 'etc/renyyt/renyyt.env', default_config, 0o600)
    (destination / 'etc/renyyt').chmod(0o700)
    for source in (root / 'deploy').rglob('*.example'):
        copy_file(source, destination / 'usr/share/doc/renyyt/examples' / source.relative_to(root / 'deploy'))
    copy_file(root / 'deploy/linux/README.md', destination / 'usr/share/doc/renyyt/README.md')
    copy_file(root / 'LICENSE', destination / 'usr/share/doc/renyyt/copyright')
    for path in destination.rglob('*'):
        if path.is_dir() and path != destination / 'etc/renyyt':
            path.chmod(0o755)
        os.utime(str(path), (stamp, stamp))
    os.utime(str(destination), (stamp, stamp))


def bootstrap(root, action, package_format):
    encoded = base64.b64encode((Path(root) / 'deploy/linux/lifecycle.py').read_bytes()).decode('ascii')
    shell = base64.b64encode((Path(root) / 'deploy/linux/purge.sh').read_bytes()).decode('ascii')
    code = 'import base64; s=base64.b64decode(%r); h=base64.b64decode(%r); exec(compile(s,"<renyyt-package>","exec"),{"__name__":"__main__","_BOOTSTRAP_SOURCE":s,"_PURGE_SHELL":h})' % (encoded, shell)
    return '/usr/bin/python3 -c %s %s %s' % (shlex.quote(code), action, package_format)


def deb(root, payload, output, version, revision, stamp, environment):
    control = payload / 'DEBIAN'
    write(control / 'control', '''Package: renyyt
Version: %s-%s
Section: web
Priority: optional
Architecture: all
Maintainer: Renyyt maintainers <noreply@github.com>
Pre-Depends: python3 (>= 3.8)
Depends: ca-certificates, passwd, systemd, init-system-helpers
Suggests: python3-pywebpush
Homepage: https://github.com/janilahti/renyyt
Description: Self-hosted waste collection calendar client and proxy
 Dependency-light Python service with a multilingual browser UI.
 Web Push is optional; install the suggested python3-pywebpush when available.
''' % (version, revision))
    # dpkg purge dereferences conffile symlinks before postrm runs. Create the
    # active Debian config in postinst instead; our retained purge unlinks only
    # the exact managed path. RPM keeps its native %config(noreplace) handling.
    config = payload / 'etc/renyyt/renyyt.env'
    config.unlink()
    config.parent.rmdir()
    hooks = {
        'preinst': 'case "$1" in install|upgrade) %s ;; esac\n' % bootstrap(root, 'prepare', 'deb'),
        'postinst': 'case "$1" in configure) %s ;; esac\n' % bootstrap(root, 'configure', 'deb'),
        'prerm': 'case "$1" in remove|deconfigure) %s ;; esac\n' % bootstrap(root, 'remove', 'deb'),
        'postrm': 'case "$1" in remove) if [ -x /usr/bin/python3 ]; then %s; fi ;; purge) if [ -f /var/lib/renyyt-package/purge ]; then /bin/sh /var/lib/renyyt-package/purge --state-only; fi ;; esac\n' % bootstrap(root, 'removed', 'deb'),
    }
    for name, body in hooks.items():
        write(control / name, '#!/bin/sh\nset -eu\n' + body, 0o755)
    control.chmod(0o755)
    for path in [control] + list(control.iterdir()):
        os.utime(str(path), (stamp, stamp))
    target = output / ('renyyt_%s-%s_all.deb' % (version, revision))
    subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '-z9', '--build', str(payload), str(target)],
                   check=True, env=environment)
    shutil.rmtree(str(control))
    # Restore staging for the RPM, with deterministic directory/file mtimes.
    copy_file(payload / 'usr/lib/renyyt/renyyt.env.example', config, 0o600)
    config.parent.chmod(0o700)
    for path in (config, config.parent, config.parent.parent):
        os.utime(str(path), (stamp, stamp))
    return target


def rpm(root, payload, output, version, revision, stamp, environment, workspace):
    top = workspace / 'rpmbuild'
    for directory in ('BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS'):
        (top / directory).mkdir(parents=True)
    shutil.copytree(str(payload), str(top / 'SOURCES/payload'))
    files = []
    for path in sorted(payload.rglob('*')):
        relative = '/' + path.relative_to(payload).as_posix()
        if path.is_dir():
            if relative in ('/usr', '/usr/bin', '/usr/sbin', '/usr/lib', '/usr/share', '/usr/share/doc',
                            '/usr/lib/systemd', '/usr/lib/systemd/system', '/etc'):
                continue
            files.append('%%dir "%s"' % relative)
        else:
            files.append(('%config(noreplace) ' if relative == '/etc/renyyt/renyyt.env' else '') + '"%s"' % relative)
    spec = '''%global debug_package %{nil}
%global __brp_python_bytecompile %{nil}
%global _buildhost reproducible.invalid
%global use_source_date_epoch_as_buildtime 1
%global clamp_mtime_to_source_date_epoch 1
%global _binary_payload w9.gzdio
Name: renyyt
Version: @VERSION@
Release: @REVISION@
Summary: Self-hosted waste collection calendar client and proxy
License: MIT
URL: https://github.com/janilahti/renyyt
BuildArch: noarch
Requires: python3 >= 3.8, ca-certificates, shadow-utils, systemd
Suggests: python3-pywebpush
Requires(pre): python3 >= 3.8
Requires(post): python3 >= 3.8
Requires(preun): python3 >= 3.8
Requires(postun): python3 >= 3.8

%description
Dependency-light Python service with a multilingual browser UI.
Web Push is optional; install the suggested python3-pywebpush when available.

%prep
%build
%install
mkdir -p %{buildroot}
cp -a %{_sourcedir}/payload/. %{buildroot}/

%pre
@PREPARE@
%post
@CONFIGURE@
%preun
if [ "$1" -eq 0 ]; then
@REMOVE@
fi
%postun
if [ "$1" -eq 0 ]; then
@REMOVED@
fi

%files
%defattr(-,root,root,-)
@FILES@
'''
    replacements = {'VERSION': version, 'REVISION': revision, 'FILES': '\n'.join(files),
                    'PREPARE': bootstrap(root, 'prepare', 'rpm'), 'CONFIGURE': bootstrap(root, 'configure', 'rpm'),
                    'REMOVE': bootstrap(root, 'remove', 'rpm'), 'REMOVED': bootstrap(root, 'removed', 'rpm')}
    for key, value in replacements.items():
        spec = spec.replace('@%s@' % key, value)
    path = top / 'SPECS/renyyt.spec'
    write(path, spec)
    subprocess.run(['rpmbuild', '-bb', '--define', '_topdir ' + str(top), str(path)], check=True, env=environment)
    target = output / ('renyyt-%s-%s.noarch.rpm' % (version, revision))
    shutil.copyfile(str(top / 'RPMS/noarch' / target.name), str(target))
    return target


def build(root=ROOT, output=None, formats=('deb', 'rpm'), revision='1'):
    root = Path(root)
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or not re.fullmatch(r'[1-9]\d*', revision):
        raise ValueError('Native packages require a numeric x.y.z version and positive integer revision.')
    output = Path(output or root / 'build/linux').resolve()
    output.mkdir(parents=True, exist_ok=True)
    stamp = epoch()
    environment = dict(os.environ, SOURCE_DATE_EPOCH=str(stamp), TZ='UTC', LC_ALL='C')
    module = load_script(root, 'build')
    previous = os.environ.get('SOURCE_DATE_EPOCH')
    try:
        os.environ['SOURCE_DATE_EPOCH'] = str(stamp)
        module.build(root)
    finally:
        if previous is None:
            os.environ.pop('SOURCE_DATE_EPOCH', None)
        else:
            os.environ['SOURCE_DATE_EPOCH'] = previous
    result = []
    with tempfile.TemporaryDirectory(prefix='renyyt-packages-') as temporary:
        workspace = Path(temporary)
        payload = workspace / 'payload'
        payload.mkdir()
        stage(root, payload, stamp)
        if 'deb' in formats:
            result.append(deb(root, payload, output, version, revision, stamp, environment))
        if 'rpm' in formats:
            result.append(rpm(root, payload, output, version, revision, stamp, environment, workspace))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('deb', 'rpm', 'all'), default='all')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--revision', default='1')
    args = parser.parse_args()
    for path in build(output=args.output, formats=('deb', 'rpm') if args.format == 'all' else (args.format,),
                      revision=args.revision):
        print(path)


if __name__ == '__main__':
    main()
