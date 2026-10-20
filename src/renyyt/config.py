import os
import ipaddress
import re
import shlex
from pathlib import Path

from .errors import ConfigError

LOG_LEVELS = {"TRACE": 5, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
LOG_FORMATS = {"text", "json"}
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_env_value(raw, path, line_number):
    value = raw.strip()
    if not value:
        return ""
    if value[0] in ("'", '"'):
        try:
            parts = shlex.split(value, comments=True, posix=True)
        except ValueError as exc:
            raise ConfigError("%s:%s: invalid quoted value: %s" % (path, line_number, exc))
        if len(parts) != 1:
            raise ConfigError("%s:%s: quoted .env value must contain exactly one value." % (path, line_number))
        return parts[0]

    # In an unquoted value, a whitespace-prefixed # starts a comment.
    match = re.search(r"\s+#", value)
    if match:
        value = value[:match.start()].rstrip()
    return value


def load_env_file(path, environ=None, required=False):
    """Load a small, dependency-free .env file without overriding existing values."""
    env = os.environ if environ is None else environ
    path = Path(path)
    if not path.is_file():
        if required:
            raise ConfigError("Environment file does not exist: %s" % path)
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError("Could not read environment file %s: %s" % (path, exc))

    for line_number, original in enumerate(lines, 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigError("%s:%s: expected NAME=VALUE." % (path, line_number))
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not _ENV_NAME_RE.match(name):
            raise ConfigError("%s:%s: invalid environment variable name %r." % (path, line_number, name))
        if name in env:
            continue
        env[name] = _parse_env_value(raw_value, path, line_number)
    return True


def bootstrap_environment(source_root):
    """Load RENYYT_ENV_FILE or a conventional .env before config is resolved."""
    explicit = os.environ.get("RENYYT_ENV_FILE", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        load_env_file(path, required=True)
        return path

    candidates = []
    source_root = Path(source_root)
    if (source_root / "VERSION").is_file():
        candidates.append(source_root / ".env")
    configured_root = os.environ.get("RENYYT_DATA_ROOT", "").strip()
    if configured_root:
        candidates.append(Path(configured_root).expanduser() / ".env")
    candidates.append(Path.cwd() / ".env")

    seen = set()
    for path in candidates:
        key = str(path.absolute())
        if key in seen:
            continue
        seen.add(key)
        if load_env_file(path):
            return path
    return None


def normalize_base_path(value):
    value = (value or "").strip()
    if not value or value == "/":
        return ""
    return "/" + value.strip("/")


def env_float(name, default):
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError("%s must be a number (got %r)." % (name, raw))
    if value <= 0:
        raise ConfigError("%s must be greater than 0." % name)
    return value


def env_nonnegative_float(name, default=0):
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError("%s must be a number (got %r)." % (name, raw))
    if value < 0:
        raise ConfigError("%s must be at least 0." % name)
    return value


def parse_int(name, raw, minimum=None, maximum=None):
    raw = str(raw).strip()
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError("%s must be an integer (got %r)." % (name, raw))
    if minimum is not None and value < minimum:
        raise ConfigError("%s must be at least %s." % (name, minimum))
    if maximum is not None and value > maximum:
        raise ConfigError("%s must be at most %s." % (name, maximum))
    return value


def env_int(name, default, minimum=None, maximum=None):
    return parse_int(name, os.environ.get(name, str(default)), minimum, maximum)


def env_csv(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def env_bool(name, default=False):
    raw = os.environ.get(name, "1" if default else "0").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError("%s must be a boolean (0/1, false/true, no/yes, off/on)." % name)


def read_version_file(repo_root):
    try:
        value = (Path(repo_root) / "VERSION").read_text(encoding="utf-8").strip()
        return value or "dev"
    except OSError:
        return "dev"


def load_config(repo_root):
    log_level = os.environ.get("RENYYT_LOG_LEVEL", "INFO").strip().upper()
    if log_level not in LOG_LEVELS:
        raise ConfigError("RENYYT_LOG_LEVEL must be one of: %s." % ", ".join(LOG_LEVELS))
    log_format = os.environ.get("RENYYT_LOG_FORMAT", "text").strip().lower()
    if log_format not in LOG_FORMATS:
        raise ConfigError("RENYYT_LOG_FORMAT must be text or json.")
    host = os.environ.get("RENYYT_HOST", "127.0.0.1").strip()
    if not host:
        raise ConfigError("RENYYT_HOST must not be empty.")

    # Cloud Run ja monet muut container-palvelut tarjoavat portin PORT-muuttujassa.
    port_raw = os.environ.get("RENYYT_PORT", os.environ.get("PORT", "18514"))

    version_default = read_version_file(repo_root)
    return {
        "host": host,
        "port": parse_int("RENYYT_PORT/PORT", port_raw, 1, 65535),
        "base_path": normalize_base_path(os.environ.get("RENYYT_BASE_PATH", "")),
        "session_timeout": env_float("RENYYT_SESSION_TIMEOUT", 10),
        "login_timeout": env_float("RENYYT_LOGIN_TIMEOUT", 15),
        "services_timeout": env_float("RENYYT_SERVICES_TIMEOUT", 20),
        "log_level": log_level,
        "log_format": log_format,
        "version": os.environ.get("RENYYT_VERSION", version_default).strip() or version_default,
        "build_time": os.environ.get("RENYYT_BUILD_TIME", "").strip(),
        "git_commit": os.environ.get("RENYYT_GIT_COMMIT", "").strip(),
        "allowed_origins": env_csv("RENYYT_ALLOWED_ORIGINS"),
        "allowed_hosts": env_csv("RENYYT_ALLOWED_HOSTS"),
        "trusted_proxies": env_csv("RENYYT_TRUSTED_PROXIES"),
        "max_request_body": env_int("RENYYT_MAX_REQUEST_BODY", 16384, 1024, 1048576),
        "client_socket_timeout": env_float("RENYYT_CLIENT_SOCKET_TIMEOUT", 30),
        "rate_limit_attempts": env_int("RENYYT_RATE_LIMIT_ATTEMPTS", 8, 1, 1000),
        "rate_limit_window": env_float("RENYYT_RATE_LIMIT_WINDOW", 300),
        "rate_limit_block": env_float("RENYYT_RATE_LIMIT_BLOCK", 600),
        "rate_limit_cleanup_interval": env_float("RENYYT_RATE_LIMIT_CLEANUP_INTERVAL", 300),
        "rate_limit_whitelist": env_csv("RENYYT_RATE_LIMIT_WHITELIST"),
        "smtp_host": os.environ.get("RENYYT_SMTP_HOST", "").strip(),
        "smtp_port": env_int("RENYYT_SMTP_PORT", 587, 1, 65535),
        "smtp_user": os.environ.get("RENYYT_SMTP_USER", "").strip(),
        "smtp_password": os.environ.get("RENYYT_SMTP_PASSWORD", ""),
        "smtp_from": os.environ.get("RENYYT_SMTP_FROM", os.environ.get("RENYYT_SMTP_USER", "")).strip(),
        "smtp_to": os.environ.get("RENYYT_SMTP_TO", "").strip(),
        "smtp_starttls": env_bool("RENYYT_SMTP_STARTTLS", True),
        "smtp_ssl": env_bool("RENYYT_SMTP_SSL", False),
        "smtp_timeout": env_float("RENYYT_SMTP_TIMEOUT", 10),
        "feedback_rate_limit": env_int("RENYYT_FEEDBACK_RATE_LIMIT", 5, 1, 100),
        "feedback_rate_window": env_float("RENYYT_FEEDBACK_RATE_WINDOW", 600),
        "feedback_max_data_bytes": env_int("RENYYT_FEEDBACK_MAX_DATA_BYTES", 262144, 1024, 1048576),
        "cache_max_entries": env_int("RENYYT_CACHE_MAX_ENTRIES", 0, 0, 10000),
        "cache_ttl_seconds": env_nonnegative_float("RENYYT_CACHE_TTL_SECONDS", 0),
        "cache_max_bytes": env_int("RENYYT_CACHE_MAX_BYTES", 16777216, 1, 1073741824),
        "fixture_file": os.environ.get("RENYYT_FIXTURE_FILE", "").strip(),
        "pwa_enabled": env_bool("RENYYT_PWA_ENABLED", True),
        "reminders_enabled": env_bool("RENYYT_REMINDERS_ENABLED", False),
        "reminders_db": os.environ.get("RENYYT_REMINDERS_DB", "").strip(),
        "reminders_internal_scheduler": env_bool("RENYYT_REMINDERS_INTERNAL_SCHEDULER", False),
        "reminders_run_times": os.environ.get("RENYYT_REMINDERS_RUN_TIMES", "07:00,18:00").strip(),
        "reminders_timezone": os.environ.get("RENYYT_REMINDERS_TIMEZONE", "local").strip() or "local",
        "vapid_private_key": os.environ.get("RENYYT_VAPID_PRIVATE_KEY", "").strip(),
        "vapid_public_key": os.environ.get("RENYYT_VAPID_PUBLIC_KEY", "").strip(),
        "vapid_subject": os.environ.get("RENYYT_VAPID_SUBJECT", "").strip(),
        "push_ttl": env_int("RENYYT_PUSH_TTL", 86400, 60, 2419200),
    }


def parse_ip_networks(values, setting_name):
    networks = []
    for value in values:
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            raise ConfigError("%s contains an invalid IP/CIDR value %r." % (setting_name, value))
    return networks


def parse_trusted_proxies(values):
    return parse_ip_networks(values, "RENYYT_TRUSTED_PROXIES")
