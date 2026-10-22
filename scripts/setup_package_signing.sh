#!/usr/bin/env bash
# Owner-only bootstrap: keep the private key outside Git and upload via stdin.
set -euo pipefail
if [ "$#" != 1 ]; then
  echo 'Usage: bash scripts/setup_package_signing.sh /secure/new/backup-directory' >&2
  exit 1
fi
umask 077
backup=$(realpath -m -- "$1")
source_root=$(git rev-parse --show-toplevel)
case "$backup/" in "$source_root/"*) echo 'Choose a backup directory outside the repository.' >&2; exit 1;; esac
if [ -e "$backup" ] || [ -L "$backup" ]; then
  echo 'Backup directory already exists; refusing to overwrite signing material.' >&2
  exit 1
fi
mkdir -p -- "$backup"
chmod 0700 "$backup"
mkdir -m 0700 "$backup/gnupg"
gpg --homedir "$backup/gnupg" --batch --pinentry-mode loopback --passphrase '' \
  --quick-generate-key 'Renyyt package repository <noreply@github.com>' rsa4096 sign 2y
fingerprint=$(gpg --homedir "$backup/gnupg" --batch --with-colons --list-secret-keys | awk -F: '$1 == "fpr" {print $10; exit}')
gpg --homedir "$backup/gnupg" --batch --armor --export-secret-keys "$fingerprint" > "$backup/private-key.asc"
gpg --homedir "$backup/gnupg" --batch --armor --export "$fingerprint" > "$backup/public-key.asc"
printf '%s\n' "$fingerprint" > "$backup/fingerprint.txt"
gh secret set PACKAGE_SIGNING_KEY --repo janilahti/renyyt < "$backup/private-key.asc"
gpgconf --homedir "$backup/gnupg" --kill gpg-agent
printf 'Signing key stored in GitHub Actions. Public fingerprint: %s\nPrivate backup: %s\n' "$fingerprint" "$backup"
