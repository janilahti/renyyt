# Renyyt native Linux packages

The `deb` (`all`) and `rpm` (`noarch`) base packages use the distribution's Python
3.8 or newer. They do not install with pip or bundle Python. Web Push is suggested through `Suggests: python3-pywebpush`, never required or
automatically enabled; there is no separate Renyyt add-on package. The supported families are Debian/Ubuntu,
Fedora and RHEL 9+ (including compatible derivatives).

Build with Python, `dpkg-deb` and/or `rpmbuild`:

```bash
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python3 scripts/package_linux.py --format all
```

Outputs are in `build/linux`. `--revision 2` builds a subsequent package revision
without changing the application version. Build once in a fixed toolchain when
comparing reproducibility; RPM/deb toolchain versions can change output bytes.

## Install and start

```bash
sudo apt install ./renyyt_0.9.0-1_all.deb
# Fedora/RHEL alternative:
sudo dnf install ./renyyt-0.9.0-1.noarch.rpm

sudoedit /etc/renyyt/renyyt.env
sudo systemctl enable --now renyyt.service
```

Installation creates a service account, private state/configuration directories
and a hardened systemd unit. The service starts only after the administrator
enables it; the default listener is `127.0.0.1:8787`. Set trusted proxy/base path
as described in [TECHNICAL.md](../../TECHNICAL.md).

Code: `/usr/lib/renyyt`; public resources: `/usr/share/renyyt`; executable:
`/usr/bin/renyyt`; unit: `/usr/lib/systemd/system/renyyt.service`. The configuration
file is root-owned mode 0600, and systemd reads it before dropping privileges.
Application state is under `/var/lib/renyyt`, owned by the service account, mode
0700. Package ownership records and the retained purge helper live in the
root-owned mode-0700 `/var/lib/renyyt-package` directory. The service user must
never be able to write that helper or its metadata.

On Debian the configure hook creates the active environment file if missing;
it is deliberately not registered as a dpkg conffile, because dpkg purge can
follow a conffile symlink and delete its external target before postrm runs.
The root-owned retained purge hook unlinks only the managed configuration path.
The packaged default is `/usr/lib/renyyt/renyyt.env.example`. RPM uses
`%config(noreplace)` and rejects unsafe configuration links during ordinary erase.

Upgrades preserve the environment file and database and restart a running
service. A stopped or disabled service is not automatically enabled. The
reminder unit/timer examples are documentation only; the base package installs
only the HTTP service.

## Optional Web Push setup

Both formats declare `Suggests: python3-pywebpush`. Suggestions normally remain
uninstalled; their display depends on the package manager. This metadata cannot
make a missing distribution package available. The checked default repositories
for Debian 12/13, Ubuntu 22.04/24.04, Fedora 44 and Rocky Linux 9/10 did not provide
`python3-pywebpush` (2026-10-19). Use the isolated-venv instructions below unless
your enabled repositories supply it. Check your release/repositories first:

```bash
apt-cache policy python3-pywebpush
# If a candidate exists:
sudo apt install python3-pywebpush

# Fedora/RHEL alternative:
dnf list --available python3-pywebpush
# If available:
sudo dnf install python3-pywebpush
```

RHEL-compatible systems may need an administrator-approved additional repository
such as EPEL; availability in EPEL has not been verified, and enabling it alone
does not guarantee package availability. Do not
use `sudo pip` or `--break-system-packages` to modify distribution Python.

### If the distribution has no suitable package

Use an administrator-managed virtual environment for the optional library while
keeping the native Renyyt payload and systemd hardening. Debian/Ubuntu needs
`sudo apt install python3-venv` first. Fedora/RHEL uses its distribution Python's
venv support. Install the same Python-version-specific library versions as the
Renyyt push extra. The creation command refuses an existing venv; do not overwrite
an old manual installation. Migrate or reuse it deliberately instead:

```bash
sudo sh -ec 'test ! -e /opt/renyyt/venv; test ! -L /opt/renyyt/venv; umask 022; python3 -m venv /opt/renyyt/venv'
sudo /opt/renyyt/venv/bin/python -m pip install \
  'pywebpush==1.14.1; python_version < "3.10"' \
  'pywebpush>=2.5,<3; python_version >= "3.10"'
sudo install -d -m 0755 /etc/systemd/system/renyyt.service.d
sudoedit /etc/systemd/system/renyyt.service.d/push.conf
```

Write this override (the empty `ExecStart` resets the packaged command):

```ini
[Service]
ExecStart=
ExecStart=/opt/renyyt/venv/bin/python /usr/bin/renyyt
```

Use `/opt/renyyt/venv/bin/python /usr/bin/renyyt` instead of `renyyt` for the
reminder CLI commands below. The virtual environment is outside package ownership:
maintain its dependencies and recreate it after a distribution Python upgrade.
After disabling/stopping the service, it can be removed explicitly with
`sudo rm -rf -- /opt/renyyt/venv`, only if this setup created it exclusively
for optional dependencies. Keep other files under `/opt/renyyt`; an old manual
checkout may share that parent directory. Native purge removes the service override but
retains this manually created directory, like other custom external paths.

### Keys, configuration and scheduling

Generate keys locally; do not paste the private key into logs or bug reports:

```bash
renyyt reminders generate-vapid
sudoedit /etc/renyyt/renyyt.env
```

Copy the generated key values and add these settings. Keep the existing
root-owned 0600 file permissions. Replace the subject with your contact address:

```dotenv
RENYYT_REMINDERS_ENABLED=true
RENYYT_REMINDERS_DB=/var/lib/renyyt/reminders.sqlite3
RENYYT_VAPID_PRIVATE_KEY=<generated-private-value>
RENYYT_VAPID_PUBLIC_KEY=<generated-public-value>
RENYYT_VAPID_SUBJECT=mailto:admin@example.com
RENYYT_REMINDERS_INTERNAL_SCHEDULER=true
RENYYT_REMINDERS_RUN_TIMES=07:00,18:00
RENYYT_REMINDERS_TIMEZONE=Europe/Helsinki
```

The recommended native setup uses the HTTP service's internal scheduler, so no
additional service/timer or Renyyt package is needed. Do not run an external
reminder timer at the same time. Named timezones need Python 3.9+ and OS timezone
data; use `UTC` on Python 3.8.

```bash
sudo systemctl daemon-reload
sudo systemctl restart renyyt.service
sudo systemctl status renyyt.service
sudo journalctl -u renyyt.service -n 30 --no-pager
```

For a first installation use `sudo systemctl enable --now renyyt.service` after
configuration. Check for dependency/configuration errors in the service log.
The public browser URL must use HTTPS through your reverse proxy (localhost is
only a development exception). Enable notifications in the UI and grant browser
permission; on iOS/iPadOS 16.4+ first add the app to the home screen. Run a normal
collection fetch to synchronize the selected bins and dates. The server stores
subscriptions and collection snapshots, never upstream login credentials, so
future successful browser fetches keep reminders current. Outbound HTTPS access
to the browser's push service is required. Preserve VAPID keys across upgrades;
changing keys requires browsers to subscribe again.

To disable reminders, set `RENYYT_REMINDERS_ENABLED=false` and
`RENYYT_REMINDERS_INTERNAL_SCHEDULER=false`, then restart the service. Shared
optional dependencies are managed by apt/dnf; Renyyt purge does not force their
removal. Ordinary remove/purge of Renyyt otherwise keeps its documented semantics.

## Ordinary removal

```bash
sudo apt remove renyyt
# or:
sudo dnf remove renyyt
```

This stops and disables the service and removes installed code, resources and
units. It retains `/etc/renyyt/renyyt.env`, `/var/lib/renyyt`, the service identity
and `/var/lib/renyyt-package`. RPM may also keep its standard `.rpmsave` backup.
An unchanged RPM configuration file is restored by the erase hook so ordinary
removal preserves settings in both formats.

## Complete purge

This intentionally deletes modified configuration, the default state directory
(including any reminder database and SQLite sidecars), Renyyt systemd overrides,
and the user/group if the package created them. Back up anything needed first.

```bash
# While installed (deb or rpm):
sudo renyyt-purge

# Debian alternative, including after an ordinary remove:
sudo apt purge renyyt

# Either format after ordinary removal:
sudo /var/lib/renyyt-package/purge
```

The retained shell entry point also works when Python has been autoremoved after
an ordinary removal. It still needs the standard account-management tools
(`passwd` on Debian/Ubuntu, `shadow-utils` on Fedora/RHEL).

The purge command first removes the installed native package if necessary, then
cleans its recorded state. Cleanup is idempotent; Debian purge can be repeated. After a successful purge,
the retained command itself is gone. The retained helper removes
itself and its ownership record at the end. Pre-existing accounts are retained;
a replaced account with a different UID/GID is never deleted silently.

Custom data paths outside `/var/lib/renyyt`, administrator-created extra files,
proxy configuration, shared Python/systemd packages and system-wide journal or
package-manager logs remain under administrator/system control. Purge does not
read an environment file to decide arbitrary recursive deletion paths.

## Migrating a manual installation

The first native installation refuses to adopt existing `/etc/renyyt`,
`/var/lib/renyyt`, native code/resource paths or manually installed Renyyt units.
This prevents an uninstall from deleting files that the package did not create.
Stop the old service, back up and move those paths/units aside, then install the
package. Copy the wanted environment settings/database into the new managed
paths and enable the native service. Keep the old `/opt/renyyt` checkout or remove
it manually when migration is verified. An existing `renyyt` user/group can be
reused; the package records that it must not delete those identities on purge.
