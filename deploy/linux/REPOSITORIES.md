# APT and DNF repositories

Renyyt's project-specific GitHub Pages site hosts architecture-independent
Debian/Ubuntu and Fedora/RHEL 9+ packages:

- Site: <https://janilahti.github.io/renyyt/>
- APT: <https://janilahti.github.io/renyyt/apt/>
- DNF: <https://janilahti.github.io/renyyt/rpm/>

The maintainer must complete the owner setup below before these URLs become
available. Repository support does not expand the distribution/runtime support:
Python 3.8+, systemd, Debian/Ubuntu and Fedora/RHEL 9+ families. Packages remain
`all`/`noarch`; Web Push is still an optional Suggests dependency.

## Debian and Ubuntu

Install `ca-certificates` and `curl` from your distribution first. Download the
repository's public key and source configuration into administrator-owned paths:

```bash
sudo install -d -m 0755 /etc/apt/keyrings
curl --fail --show-error --silent --location \
  https://janilahti.github.io/renyyt/renyyt-keyring.gpg -o /tmp/renyyt-keyring.gpg
# Inspect the key with: gpg --show-keys --with-fingerprint /tmp/renyyt-keyring.gpg
# Compare its full fingerprint with the maintainer's published fingerprint.
sudo install -m 0644 /tmp/renyyt-keyring.gpg /etc/apt/keyrings/renyyt.gpg
curl --fail --show-error --silent --location \
  https://janilahti.github.io/renyyt/renyyt.sources -o /tmp/renyyt.sources
sudo install -m 0644 /tmp/renyyt.sources /etc/apt/sources.list.d/renyyt.sources
sudo apt update
sudo apt install renyyt
```

The flat repository's suite is `./`, with no distribution codename or components.
`Signed-By` limits this key's authority to the Renyyt source. Do not use `apt-key`,
`trusted=yes` or allow unauthenticated packages. APT authenticates the signed
Release/InRelease, then the index and package SHA256 checksums; deb files do not
need individual embedded signatures.

Subsequent updates:

```bash
sudo apt update
sudo apt install --only-upgrade renyyt
```

Normal `apt upgrade` also includes Renyyt. A package already installed manually
can receive newer versions from the repository without reinstalling it.

## Fedora and RHEL-compatible distributions

```bash
curl --fail --show-error --silent --location \
  https://janilahti.github.io/renyyt/renyyt-signing-key.asc -o /tmp/renyyt-signing-key.asc
# Inspect and compare the full fingerprint before importing.
gpg --show-keys --with-fingerprint /tmp/renyyt-signing-key.asc
sudo rpm --import /tmp/renyyt-signing-key.asc
curl --fail --show-error --silent --location \
  https://janilahti.github.io/renyyt/renyyt.repo -o /tmp/renyyt.repo
sudo install -m 0644 /tmp/renyyt.repo /etc/yum.repos.d/renyyt.repo
sudo dnf install renyyt
```

If `gpg` is absent, install your distribution's GnuPG package to inspect the key.
DNF may ask to accept the key separately for metadata verification: compare the
full fingerprint again. Both `gpgcheck=1` and `repo_gpgcheck=1` must stay enabled.
Subsequent updates use `sudo dnf upgrade renyyt` or normal `dnf upgrade`.

RPM copies in Pages are individually signed. Their bytes/checksums differ from
the original unsigned GitHub Release RPMs; those assets and their SHA256SUMS stay
unchanged. APT copies are byte-identical to the Release debs. Repository metadata
authenticates the copies served by each repository.

## Configuration and removal

After installation, edit `/etc/renyyt.env`, then explicitly start the service:

```bash
sudoedit /etc/renyyt.env
sudo systemctl enable --now renyyt.service
```

The listener defaults to `127.0.0.1:18514`. Existing settings/data and running
service state are preserved during upgrades. See [package lifecycle and Web
Push instructions](README.md) for the complete behavior.

Ordinary `apt remove renyyt` / `dnf remove renyyt` retains settings/data.
`sudo renyyt-purge` is the explicit destructive purge while installed; after
removal, use `sudo apt purge renyyt` or `sudo /var/lib/renyyt-package/purge`.

Repository configuration and trust keys are administrator-added files, not owned
by the Renyyt package. To stop receiving updates, remove only the files you added:

```bash
# APT:
sudo rm -- /etc/apt/sources.list.d/renyyt.sources /etc/apt/keyrings/renyyt.gpg
sudo apt update

# DNF alternative:
sudo rm -- /etc/yum.repos.d/renyyt.repo
sudo dnf clean metadata
```

If retiring the RPM signing key, list `rpm -qa 'gpg-pubkey*'`, inspect the matching
entry with `rpm -qi`, and erase only the entry whose fingerprint matches Renyyt.
Do not remove other repositories' keys. DNF also has its own repository metadata
key cache, handled through its repository cache management. Package purge never
deletes administrator-managed repository files or shared trust stores.

## Owner setup (once, after merging the implementation)

Initial setup requires a GitHub CLI login permitted to manage this
repository's secrets and Pages. Never paste the private key into an issue, PR,
chat or Git commit.

1. Generate a dedicated RSA-4096 signing-only key with a two-year expiry, keep a
   private backup outside the clone and upload it to the `PACKAGE_SIGNING_KEY`
   repository Actions secret:

   ```bash
   git switch main
   git pull --ff-only
   bash scripts/setup_package_signing.sh "$HOME/.local/share/renyyt-repository-signing"
   ```

   The helper refuses an existing backup directory. Securely back up the whole
   directory, including the revocation certificate in `gnupg/openpgp-revocs.d`.
   The unattended signing key has no passphrase; GitHub encrypts the secret at
   rest, and the local backup is private mode 0700/0600. CI uses a disposable key
   and never receives this production secret. Record/publish the full public
   fingerprint printed by the helper through a trusted channel.

2. In repository **Settings → Pages**, choose **GitHub Actions** as the build
   source. This affects only `janilahti/renyyt`; do not configure a custom domain.
   The equivalent initial API command, only if Pages is not already configured:

   ```bash
   gh api --method POST repos/janilahti/renyyt/pages -f build_type=workflow
   ```

3. If the `github-pages` environment has branch restrictions, allow the default
   branch and stable `v*` release tags, because the release workflow calls the
   publisher from its tag. Preserve any required-reviewer policy; scheduled
   renewal will also need approval when such a policy is configured.

4. Backfill existing stable releases (including 1.0.2) without making a new release:

   ```bash
   gh workflow run package-repositories.yml --repo janilahti/renyyt --ref main
   ```

   Confirm its deployment succeeds, open the Pages site, compare the published
   fingerprint with the backup and test installation with a fresh disposable
   Debian/Ubuntu and Fedora/RHEL client.

`release.yml` explicitly calls the publisher after creating a successful stable
release; a `release: published` trigger would not run for a release created by
`GITHUB_TOKEN`. Publication has its own serialized concurrency group and atomic
Pages artifact deployment. A failed build leaves the previous site deployed.
Production secrets are available only to the publishing workflow; fork/PR CI
builds use their own disposable key. Do not run production publishing on arbitrary
branches or with unreviewed scripts. Required permissions are contents:read for
release downloads, pages:write and id-token:write for deployment.

## Renewal, retention and recovery

- The publisher rebuilds from **all stable numeric releases with both native
  assets**, verifies each release's SHA256SUMS and package identity, and retains
  those versions in the APT pool/RPM package directory. Drafts and prereleases
  never enter these repositories. Removing/changing a public release can remove
  its packages on the next publication; do not rewrite stable release assets.
- The weekly Monday refresh renews APT's 30-day `Valid-Until`. Monitor failed
  workflows; GitHub can disable scheduled workflows in an inactive public
  repository. Re-enable and dispatch before metadata expires. Do not bypass
  expiration/signature checks on clients. DNF caches metadata for six hours.
- The build refuses expired/revoked keys, unsuitable algorithms and keys expiring
  within 30 days. Renew the **same key** before then, using its private backup:

  ```bash
  gpg --homedir "$HOME/.local/share/renyyt-repository-signing/gnupg" \
    --quick-set-expire PUBLIC_FINGERPRINT 2y
  gpg --homedir "$HOME/.local/share/renyyt-repository-signing/gnupg" --armor \
    --export-secret-keys PUBLIC_FINGERPRINT | \
    gh secret set PACKAGE_SIGNING_KEY --repo janilahti/renyyt
  gh workflow run package-repositories.yml --repo janilahti/renyyt --ref main
  ```

  Refresh the exported private/public backups too. Users must refresh their local
  public key when its expiry changes; document the unchanged fingerprint.
- Losing/compromising a key requires a deliberate rotation: announce the new
  fingerprint and distribute the new key through a trusted channel, update the
  Actions secret, republish and have users replace their APT keyring/import the
  new RPM key. Do not silently disable verification. Keep the revocation
  certificate separately; publish it if the old key is compromised.
- GitHub Pages is static hosting and provides no automatic apt/dnf execution on
  users' machines. Normal package-manager updates include Renyyt once configured;
  unattended update policy remains the administrator's choice. These downloads
  do not increment GitHub Release asset download counters.

## Local validation

On a disposable Linux build environment, install `dpkg-dev`, `rpm`, `createrepo-c`
and `gnupg`, build the existing Linux packages, then run:

```bash
python3 scripts/test_package_repository.py --packages build/linux --output build/repository-test
```

This signs with an ephemeral key, verifies signatures using a fresh public-only
trust store and rejects modified metadata and RPM content. The CI client matrix
installs, removes and purges through APT on Debian 12/Ubuntu 24.04 and DNF on
Fedora 44/Rocky Linux 9. APT also rejects an untrusted key. Native-package lifecycle
coverage for all seven supported CI distributions remains in place.
