# Renyyt native Linux packages

The `deb` (`all`) and `rpm` (`noarch`) base packages use the distribution's Python
3.8 or newer. They do not install with pip or bundle Python. Web Push dependencies
are not part of these packages yet. The supported families are Debian/Ubuntu,
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

Upgrades preserve the environment file and database and restart a running
service. A stopped or disabled service is not automatically enabled. The
reminder unit/timer examples are documentation only; the base package installs
only the HTTP service.

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
