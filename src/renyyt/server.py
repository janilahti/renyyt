#!/usr/bin/env python3
import argparse
import json
import mimetypes
import ipaddress
import os
import re
import socket
import smtplib
import sys
import time
import threading
import uuid
import signal
from datetime import datetime, timezone
from email.utils import formatdate, parsedate_to_datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

from .config import (
    LOG_LEVELS, ConfigError, load_config as _load_config, normalize_base_path,
    parse_trusted_proxies, parse_ip_networks, env_float, env_int, env_csv, bootstrap_environment,
)
from .errors import ApiError
from .metrics import Metrics
from .rate_limit import RateLimiter
from .validation import validate_services_payload, collect_unknown_fields
from . import upstream
from .feedback import FeedbackRateLimiter, feedback_enabled, send_feedback, validate_feedback_payload
from .cache import ResponseCache
from .reminders import ReminderStore, ReminderError, PushDependencyError, InternalReminderScheduler, push_dependencies_available, parse_run_times, scheduler_timezone, run_due

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
LOADED_ENV_FILE = bootstrap_environment(_SOURCE_ROOT)

def resolve_data_root():
    """Resolve runtime data for both a source checkout and an installed package."""
    configured = os.environ.get("RENYYT_DATA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve(), False

    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "web" / "index.html").is_file():
        return source_root, True

    installed_root = Path(sys.prefix) / "share" / "renyyt"
    if (installed_root / "web" / "index.html").is_file():
        return installed_root, False

    # Keep a deterministic path for readiness diagnostics if installation data is missing.
    return installed_root, False


REPO_ROOT, SOURCE_CHECKOUT = resolve_data_root()
WEB_ROOT = REPO_ROOT / "web"
DIST_ROOT = REPO_ROOT / "dist"
INDEX = WEB_ROOT / "index.html"
INDEX_GZ = WEB_ROOT / "index.html.gz"
README = REPO_ROOT / "README.md"
README_LANGUAGES = ("fi", "en", "sv", "uk", "ar", "fa", "vi", "zh-Hans", "et")
LOCALIZED_READMES = frozenset("README.%s.md" % lang for lang in README_LANGUAGES)
STYLES = WEB_ROOT / "styles.css"
APP_JS = WEB_ROOT / "app.js"
I18N_JS = WEB_ROOT / "i18n.js"
HELPERS_JS = WEB_ROOT / "helpers.js"
SOURCE_SERVICE_WORKER = WEB_ROOT / "service-worker.js"
PROD_SERVICE_WORKER = DIST_ROOT / "service-worker.js"
ASSETS_DIR = DIST_ROOT / "assets"
ASSET_MANIFEST = DIST_ROOT / "asset-manifest.json"
PROD_INDEX = DIST_ROOT / "index.html"
PROD_INDEX_GZ = DIST_ROOT / "index.html.gz"
VERSION_FILE = REPO_ROOT / "VERSION"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
API_DOC = REPO_ROOT / "API.md"
TECHNICAL_DOC = REPO_ROOT / "TECHNICAL.md"
BRAND_SOURCE_DIR = WEB_ROOT / "assets" / "brand"
BRAND_DIST_DIR = DIST_ROOT / "brand"
ROOT = REPO_ROOT
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

def load_config(repo_root=None):
    return _load_config(repo_root or REPO_ROOT)

CONFIG = load_config(REPO_ROOT)
APP_BASE_PATH = CONFIG["base_path"]
SESSION_TIMEOUT = CONFIG["session_timeout"]
LOGIN_TIMEOUT = CONFIG["login_timeout"]
SERVICES_TIMEOUT = CONFIG["services_timeout"]
LOG_LEVEL = CONFIG["log_level"]
LOG_FORMAT = CONFIG["log_format"]
APP_VERSION = CONFIG["version"]
BUILD_TIME = CONFIG["build_time"]
GIT_COMMIT = CONFIG["git_commit"]
ALLOWED_ORIGINS = CONFIG["allowed_origins"]
ALLOWED_HOSTS = CONFIG["allowed_hosts"]
TRUSTED_PROXIES = CONFIG["trusted_proxies"]
MAX_REQUEST_BODY = CONFIG["max_request_body"]
CLIENT_SOCKET_TIMEOUT = CONFIG["client_socket_timeout"]
RATE_LIMIT_ATTEMPTS = CONFIG["rate_limit_attempts"]
RATE_LIMIT_WINDOW = CONFIG["rate_limit_window"]
RATE_LIMIT_BLOCK = CONFIG["rate_limit_block"]
RATE_LIMIT_CLEANUP_INTERVAL = CONFIG["rate_limit_cleanup_interval"]
RATE_LIMIT_WHITELIST = CONFIG["rate_limit_whitelist"]
SMTP_HOST = CONFIG["smtp_host"]
SMTP_PORT = CONFIG["smtp_port"]
SMTP_USER = CONFIG["smtp_user"]
SMTP_PASSWORD = CONFIG["smtp_password"]
SMTP_FROM = CONFIG["smtp_from"]
SMTP_TO = CONFIG["smtp_to"]
SMTP_STARTTLS = CONFIG["smtp_starttls"]
SMTP_SSL = CONFIG["smtp_ssl"]
SMTP_TIMEOUT = CONFIG["smtp_timeout"]
FEEDBACK_RATE_LIMIT = CONFIG["feedback_rate_limit"]
FEEDBACK_RATE_WINDOW = CONFIG["feedback_rate_window"]
FEEDBACK_MAX_DATA_BYTES = CONFIG["feedback_max_data_bytes"]
CACHE_MAX_ENTRIES = CONFIG["cache_max_entries"]
CACHE_TTL_SECONDS = CONFIG["cache_ttl_seconds"]
CACHE_MAX_BYTES = CONFIG["cache_max_bytes"]
FIXTURE_FILE_SETTING = CONFIG["fixture_file"]
PWA_ENABLED = CONFIG["pwa_enabled"]
REMINDERS_ENABLED = CONFIG["reminders_enabled"]
REMINDERS_DB_SETTING = CONFIG["reminders_db"]
REMINDERS_INTERNAL_SCHEDULER = CONFIG["reminders_internal_scheduler"]
REMINDERS_RUN_TIMES = CONFIG["reminders_run_times"]
REMINDERS_TIMEZONE = CONFIG["reminders_timezone"]
VAPID_PRIVATE_KEY = CONFIG["vapid_private_key"]
VAPID_PUBLIC_KEY = CONFIG["vapid_public_key"]
VAPID_SUBJECT = CONFIG["vapid_subject"]
PUSH_TTL = CONFIG["push_ttl"]
TRUSTED_PROXY_NETWORKS = parse_trusted_proxies(TRUSTED_PROXIES)
RATE_LIMIT_WHITELIST_NETWORKS = parse_ip_networks(RATE_LIMIT_WHITELIST, "RENYYT_RATE_LIMIT_WHITELIST")


def reminder_db_path():
    if REMINDERS_DB_SETTING:
        path = Path(REMINDERS_DB_SETTING).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path.resolve()
    configured_root = os.environ.get("RENYYT_DATA_ROOT", "").strip()
    if configured_root:
        return (Path(configured_root).expanduser().resolve() / "reminders.sqlite3")
    return (Path.home() / ".local" / "share" / "renyyt" / "reminders.sqlite3").resolve()


def validate_reminder_config(require_dependencies=False):
    if not REMINDERS_ENABLED:
        return None
    if not PWA_ENABLED:
        raise ConfigError("RENYYT_REMINDERS_ENABLED requires RENYYT_PWA_ENABLED=true.")
    if not (VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY and VAPID_SUBJECT):
        raise ConfigError("Web Push reminders require RENYYT_VAPID_PRIVATE_KEY, RENYYT_VAPID_PUBLIC_KEY and RENYYT_VAPID_SUBJECT.")
    if not (VAPID_SUBJECT.startswith("mailto:") or VAPID_SUBJECT.startswith("https://")):
        raise ConfigError("RENYYT_VAPID_SUBJECT must be a mailto: or https:// URI.")
    parse_run_times(REMINDERS_RUN_TIMES)
    scheduler_timezone(REMINDERS_TIMEZONE)
    if require_dependencies and not push_dependencies_available():
        raise ConfigError("Web Push dependencies are not installed. Install with: pip install 'renyyt[push]'")
    return reminder_db_path()


REMINDER_STORE = None
REMINDER_SCHEDULER = None


def _fixture_path():
    if not FIXTURE_FILE_SETTING:
        return None
    path = Path(FIXTURE_FILE_SETTING).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _load_fixture(username, suffixes):
    path = _fixture_path()
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError("RENYYT_FIXTURE_FILE could not be read: %s" % exc)
    except json.JSONDecodeError as exc:
        raise ConfigError("RENYYT_FIXTURE_FILE is not valid JSON: %s" % exc)
    if isinstance(data, list):
        services = data
        customer_numbers = None
    elif isinstance(data, dict) and isinstance(data.get("services"), list):
        services = data["services"]
        customer_numbers = data.get("customerNumbers")
        if customer_numbers is not None and not isinstance(customer_numbers, list):
            raise ConfigError("RENYYT_FIXTURE_FILE customerNumbers must be a list when present.")
    else:
        raise ConfigError("RENYYT_FIXTURE_FILE must contain a services array or a Renyyt API response object.")
    validate_services_payload(services)
    if customer_numbers is None:
        parts = username.split("-")
        prefix = "%s-%s" % (parts[0], parts[1]) if len(parts) >= 2 else username
        customer_numbers = ["%s-%s" % (prefix, item) for item in suffixes] if suffixes else [username]
    return services, [str(item) for item in customer_numbers]


def validate_fixture_file():
    if not FIXTURE_FILE_SETTING:
        return None
    # Use a synthetic identity only to validate fallback customer-number generation.
    _load_fixture("00-0000000-00", [])
    return _fixture_path()


def detect_production_build():
    build_present = ASSET_MANIFEST.exists() or PROD_INDEX.exists() or ASSETS_DIR.exists()
    if not (ASSET_MANIFEST.exists() and PROD_INDEX.exists() and ASSETS_DIR.is_dir()):
        return False, {}, "incomplete" if build_present else "absent"
    try:
        manifest = json.loads(ASSET_MANIFEST.read_text(encoding="utf-8"))
        if manifest.get("manifestVersion") != 1:
            return False, {}, "unsupported_manifest_version"
        assets = manifest.get("assets", {})
        required = {"app.js", "helpers.js", "i18n.js", "styles.css"}
        if set(assets) != required:
            return False, {}, "asset_set_mismatch"
        prod_html = PROD_INDEX.read_text(encoding="utf-8")
        for source, rel in assets.items():
            path = DIST_ROOT / rel
            if not path.is_file() or path.parent != ASSETS_DIR:
                return False, {}, "asset_missing"
            match = re.match(r"^assets/([A-Za-z0-9_-]+)\.([0-9a-f]{12})\.(js|css)$", rel)
            if not match:
                return False, {}, "asset_name_invalid"
            import hashlib
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            if digest != match.group(2):
                return False, {}, "asset_hash_mismatch"
            if rel not in prod_html:
                return False, {}, "index_reference_missing"
            if ('src="%s"' % source) in prod_html or ('href="%s"' % source) in prod_html:
                return False, {}, "source_reference_remaining"
        brand = manifest.get("brand", {})
        required_brand = {"logo.svg", "favicon.svg", "favicon.ico", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "maskable-192.png", "maskable-512.png", "site.webmanifest"}
        if set(brand) != required_brand or not BRAND_DIST_DIR.is_dir():
            return False, {}, "brand_set_mismatch"
        import hashlib
        for name, expected in brand.items():
            brand_path = BRAND_DIST_DIR / name
            if not brand_path.is_file() or hashlib.sha256(brand_path.read_bytes()).hexdigest() != expected:
                return False, {}, "brand_hash_mismatch"
        service_worker_hash = manifest.get("serviceWorker")
        if not service_worker_hash or not PROD_SERVICE_WORKER.is_file():
            return False, {}, "service_worker_missing"
        if hashlib.sha256(PROD_SERVICE_WORKER.read_bytes()).hexdigest() != service_worker_hash:
            return False, {}, "service_worker_hash_mismatch"
        # File mtimes are meaningful in a source checkout, but installation tools may
        # rewrite them. Installed builds are therefore validated by content hashes only.
        if SOURCE_CHECKOUT:
            source_mtimes = [INDEX.stat().st_mtime, APP_JS.stat().st_mtime, HELPERS_JS.stat().st_mtime, I18N_JS.stat().st_mtime, STYLES.stat().st_mtime, SOURCE_SERVICE_WORKER.stat().st_mtime]
            if BRAND_SOURCE_DIR.is_dir():
                source_mtimes.extend(p.stat().st_mtime for p in BRAND_SOURCE_DIR.iterdir() if p.is_file())
            newest_source = max(source_mtimes)
            if PROD_INDEX.stat().st_mtime < newest_source or ASSET_MANIFEST.stat().st_mtime < newest_source:
                return False, {}, "stale"
        return True, assets, "valid"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False, {}, "invalid"


PRODUCTION_BUILD_AVAILABLE, PRODUCTION_ASSETS, PRODUCTION_BUILD_STATUS = detect_production_build()
ACTIVE_INDEX = PROD_INDEX if PRODUCTION_BUILD_AVAILABLE else INDEX
ACTIVE_INDEX_GZ = PROD_INDEX_GZ if PRODUCTION_BUILD_AVAILABLE else INDEX_GZ
ACTIVE_BRAND_DIR = BRAND_DIST_DIR if PRODUCTION_BUILD_AVAILABLE else BRAND_SOURCE_DIR
SERVICE_WORKER = PROD_SERVICE_WORKER if PRODUCTION_BUILD_AVAILABLE else SOURCE_SERVICE_WORKER


def _adjacent_gzip(path):
    return Path(str(path) + ".gz")


def _usable_precompressed_gzip(path):
    gz_path = _adjacent_gzip(path)
    if not gz_path.is_file():
        return None
    if path.is_file() and gz_path.stat().st_mtime < path.stat().st_mtime:
        return None
    return gz_path


def detect_index_sources():
    """Check index representations once when the process starts."""
    plain_exists = ACTIVE_INDEX.exists()
    gzip_usable = _usable_precompressed_gzip(ACTIVE_INDEX) is not None
    return plain_exists, gzip_usable


def detect_precompressed_static():
    """Cache usable adjacent .gz representations for known static resources."""
    paths = [STYLES, I18N_JS, HELPERS_JS, APP_JS, SERVICE_WORKER, README, CHANGELOG, API_DOC, TECHNICAL_DOC]
    paths.extend(README.parent / name for name in sorted(LOCALIZED_READMES))
    if PRODUCTION_BUILD_AVAILABLE:
        paths.extend(DIST_ROOT / rel for rel in PRODUCTION_ASSETS.values())
    if ACTIVE_BRAND_DIR.is_dir():
        paths.extend(p for p in ACTIVE_BRAND_DIR.iterdir() if p.is_file() and p.suffix.lower() in (".svg", ".webmanifest"))
    result = {}
    for path in paths:
        gz_path = _usable_precompressed_gzip(path)
        if gz_path is not None:
            result[path] = gz_path
    return result


INDEX_PLAIN_AVAILABLE, INDEX_GZIP_AVAILABLE = detect_index_sources()
PRECOMPRESSED_STATIC = detect_precompressed_static()


def file_validator(path):
    """Lightweight ETag + Last-Modified without hashing file contents."""
    stat = path.stat()
    etag = '"%x-%x"' % (stat.st_mtime_ns, stat.st_size)
    last_modified = formatdate(stat.st_mtime, usegmt=True)
    return etag, last_modified


def readiness_state():
    index_ready = bool(INDEX_PLAIN_AVAILABLE or INDEX_GZIP_AVAILABLE)
    checks = {
        "index": index_ready,
        "styles": STYLES.exists(),
        "javascript": APP_JS.exists(),
        "i18n": I18N_JS.exists(),
        "helpers": HELPERS_JS.exists(),
        "productionBuild": PRODUCTION_BUILD_STATUS in ("absent", "valid"),
        "buildManifest": PRODUCTION_BUILD_STATUS in ("absent", "valid"),
        "readme": README.exists(),
        "localizedReadmes": all((README.parent / name).is_file() for name in LOCALIZED_READMES),
        "apiDoc": API_DOC.exists(),
        "technicalDoc": TECHNICAL_DOC.exists(),
        "serviceWorker": (not PWA_ENABLED) or SERVICE_WORKER.exists(),
        "version": VERSION_FILE.exists(),
        "changelog": CHANGELOG.exists(),
        "brandAssets": ACTIVE_BRAND_DIR.is_dir() and all((ACTIVE_BRAND_DIR / name).is_file() for name in ("logo.svg", "favicon.svg", "favicon.ico", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "maskable-192.png", "maskable-512.png", "site.webmanifest")),
        "config": True,
    }
    return all(checks.values()), checks



RATE_LIMITER = RateLimiter(RATE_LIMIT_ATTEMPTS, RATE_LIMIT_WINDOW, RATE_LIMIT_BLOCK, RATE_LIMIT_CLEANUP_INTERVAL)
FEEDBACK_LIMITER = FeedbackRateLimiter(FEEDBACK_RATE_LIMIT, FEEDBACK_RATE_WINDOW)
RESPONSE_CACHE = ResponseCache(CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS, CACHE_MAX_BYTES)
METRICS = Metrics(APP_VERSION, GIT_COMMIT, readiness=readiness_state, rate_stats=RATE_LIMITER.stats, cache_stats=RESPONSE_CACHE.stats)



def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _response_with_freshness(payload, data_source):
    """Return response JSON bytes with dynamic freshness metadata."""
    data = dict(payload)
    fetched_at = data.get("upstreamFetchedAt")
    age = None
    if fetched_at:
        try:
            parsed = datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age = max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))
        except (TypeError, ValueError):
            age = None
    data["upstreamAgeSeconds"] = age
    data["dataSource"] = data_source
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def fetch_services(username, password, suffixes, debug=None, trace=None):
    fixture = _load_fixture(username, suffixes) if FIXTURE_FILE_SETTING else None
    if fixture is not None:
        services, numbers = fixture
        if debug:
            debug("fixture_response", endpoint="fixture", bytes=len(json.dumps(services, ensure_ascii=False).encode("utf-8")))
        if trace:
            trace("services_json_response", status=200, body=json.dumps(services, ensure_ascii=False, separators=(",", ":")), elapsed_ms=0)
        return services, numbers
    return upstream.fetch_services(
        username, password, suffixes,
        SESSION_TIMEOUT, LOGIN_TIMEOUT, SERVICES_TIMEOUT,
        metrics=METRICS, debug=debug, trace=trace,
    )

class Handler(BaseHTTPRequestHandler):
    server_version = "Renyyt/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(CLIENT_SOCKET_TIMEOUT)

    def _peer_ip(self):
        return self.client_address[0] if self.client_address else ""

    def _trusted_proxy(self):
        if not TRUSTED_PROXY_NETWORKS:
            return False
        try:
            addr = ipaddress.ip_address(self._peer_ip())
            return any(addr in network for network in TRUSTED_PROXY_NETWORKS)
        except ValueError:
            return False

    def _external_host(self):
        if self._trusted_proxy():
            forwarded = (self.headers.get("X-Forwarded-Host") or "").split(",", 1)[0].strip()
            if forwarded:
                return forwarded.lower()
        return (self.headers.get("Host") or "").strip().lower()

    def _external_proto(self):
        if self._trusted_proxy():
            forwarded = (self.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip().lower()
            if forwarded in ("http", "https"):
                return forwarded
        return "http"

    def _client_ip(self):
        peer = self._peer_ip()
        if not self._trusted_proxy():
            return peer
        forwarded = [item.strip() for item in (self.headers.get("X-Forwarded-For") or "").split(",") if item.strip()]
        chain = forwarded + ([peer] if peer else [])
        for value in reversed(chain):
            try:
                addr = ipaddress.ip_address(value)
            except ValueError:
                continue
            if any(addr in network for network in TRUSTED_PROXY_NETWORKS):
                continue
            return value
        return forwarded[0] if forwarded else peer

    def _rate_limit_exempt(self, client_ip=None):
        value = client_ip or self._client_ip()
        if not RATE_LIMIT_WHITELIST_NETWORKS:
            return False
        try:
            addr = ipaddress.ip_address(value)
            return any(addr in network for network in RATE_LIMIT_WHITELIST_NETWORKS)
        except ValueError:
            return False

    def _request_id(self):
        value = getattr(self, "_renyyt_request_id", None)
        if value:
            return value
        supplied = self.headers.get("X-Request-ID", "").strip() if hasattr(self, "headers") else ""
        if supplied and REQUEST_ID_RE.match(supplied) and self._trusted_proxy():
            value = supplied
        else:
            value = uuid.uuid4().hex[:16]
        self._renyyt_request_id = value
        return value

    def _log(self, level, event, **fields):
        level = level.upper()
        if LOG_LEVELS.get(level, 100) < LOG_LEVELS[LOG_LEVEL]:
            return
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        clean = {key: str(value).replace("\r", " ").replace("\n", " ") for key, value in fields.items() if value is not None}
        if LOG_FORMAT == "json":
            payload = {"timestamp": stamp, "level": level, "request_id": self._request_id(), "event": event}
            payload.update(clean)
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), file=sys.stderr, flush=True)
            return
        parts = [stamp, level, "request_id=%s" % self._request_id(), "event=%s" % event]
        parts.extend("%s=%s" % (key, value) for key, value in clean.items())
        print(" ".join(parts), file=sys.stderr, flush=True)

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; "
            "style-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-src 'none'; worker-src 'self'"
        )
        self.send_header("X-Request-ID", self._request_id())

    def _metric_route(self):
        path = self._app_path()
        known = {"/", "/index.html", "/embed", "/styles.css", "/i18n.js", "/helpers.js", "/app.js", "/service-worker.js", "/README.md", "/API.md", "/TECHNICAL.md", "/CHANGELOG.md", "/health", "/ready", "/version", "/metrics", "/metrics/openmetrics", "/api/v1/renyyt", "/api/v1/features", "/api/v1/feedback", "/api/v1/reminders/sync", "/api/v1/reminders/unsubscribe"}
        if path and path.startswith("/assets/"):
            return "/assets/*"
        known.update("/" + name for name in LOCALIZED_READMES)
        return path if path in known else "not_found"

    def _send(self, status, body: bytes, content_type="text/plain; charset=utf-8",
              cache_control="no-store", content_encoding=None, vary=None,
              etag=None, last_modified=None, extra_headers=None):
        duration = time.monotonic() - getattr(self, "_renyyt_request_started", time.monotonic())
        METRICS.record_http(self.command, self._metric_route(), status, len(body or b""), duration=duration)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self._security_headers()
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
        if vary:
            self.send_header("Vary", vary)
        if etag:
            self.send_header("ETag", etag)
        if last_modified:
            self.send_header("Last-Modified", last_modified)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, str(value))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _send_redirect(self, status, location):
        METRICS.record_http(self.command, "base_path_redirect", status, 0, duration=time.monotonic() - getattr(self, "_renyyt_request_started", time.monotonic()))
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()

    def _send_not_modified(self, cache_control, etag, last_modified, vary=None):
        METRICS.record_http(self.command, self._metric_route(), 304, 0, duration=time.monotonic() - getattr(self, "_renyyt_request_started", time.monotonic()))
        self.send_response(304)
        self.send_header("Cache-Control", cache_control)
        self._security_headers()
        if vary:
            self.send_header("Vary", vary)
        if etag:
            self.send_header("ETag", etag)
        if last_modified:
            self.send_header("Last-Modified", last_modified)
        self.end_headers()

    def _is_not_modified(self, etag, last_modified):
        inm = self.headers.get("If-None-Match")
        if inm and etag:
            return any(tag.strip() in (etag, "*") for tag in inm.split(","))
        ims = self.headers.get("If-Modified-Since")
        if ims and last_modified:
            try:
                request_time = parsedate_to_datetime(ims)
                resource_time = parsedate_to_datetime(last_modified)
                return resource_time <= request_time
            except (TypeError, ValueError, OverflowError):
                pass
        return False

    def _request_path(self):
        return urlsplit(self.path).path

    def _app_path(self):
        path = self._request_path()
        if not APP_BASE_PATH:
            return path
        if path == APP_BASE_PATH:
            return "/"
        prefix = APP_BASE_PATH + "/"
        if not path.startswith(prefix):
            return None
        return path[len(APP_BASE_PATH):]

    def _send_static_file(self, path, content_type, cache_control="no-cache", vary=None,
                          content_encoding=None, allow_precompressed=True):
        selected = path
        selected_encoding = content_encoding
        selected_vary = vary
        if allow_precompressed and not content_encoding:
            gzip_path = PRECOMPRESSED_STATIC.get(path)
            if gzip_path is not None:
                selected_vary = "Accept-Encoding"
                if "gzip" in (self.headers.get("Accept-Encoding", "").lower()):
                    selected = gzip_path
                    selected_encoding = "gzip"

        etag, last_modified = file_validator(selected)
        if self._is_not_modified(etag, last_modified):
            self._send_not_modified(cache_control, etag, last_modified, vary=selected_vary)
            return
        self._send(
            200, selected.read_bytes(), content_type, cache_control=cache_control,
            content_encoding=selected_encoding, vary=selected_vary, etag=etag, last_modified=last_modified,
        )

    def _send_index(self):
        if not PWA_ENABLED:
            if not INDEX_PLAIN_AVAILABLE:
                self._send(500, b"index.html not found")
                return
            try:
                body = ACTIVE_INDEX.read_text(encoding="utf-8")
                body = re.sub(r"\s*<link rel=\"manifest\" href=\"brand/site\.webmanifest\"\s*/?>", "", body)
                self._send(200, body.encode("utf-8"), "text/html; charset=utf-8", cache_control="no-cache", vary="Accept-Encoding")
            except OSError:
                self._send(500, b"index.html not found")
            return

        accept_encoding = self.headers.get("Accept-Encoding", "").lower()
        gzip_ok = "gzip" in accept_encoding

        if gzip_ok and INDEX_GZIP_AVAILABLE:
            self._send_static_file(
                _adjacent_gzip(ACTIVE_INDEX),
                "text/html; charset=utf-8",
                cache_control="no-cache",
                content_encoding="gzip",
                vary="Accept-Encoding",
            )
        elif INDEX_PLAIN_AVAILABLE:
            self._send_static_file(
                ACTIVE_INDEX,
                "text/html; charset=utf-8",
                cache_control="no-cache",
                vary="Accept-Encoding",
            )
        elif INDEX_GZIP_AVAILABLE:
            self._send(
                406,
                b"Only gzip-compressed index.html is available; client did not accept gzip.",
                cache_control="no-store",
                vary="Accept-Encoding",
            )
        else:
            self._send(500, b"index.html or usable index.html.gz not found")

    def _handle_get_or_head(self):
        if APP_BASE_PATH and self._request_path() == APP_BASE_PATH:
            self._send_redirect(308, APP_BASE_PATH + "/")
            return
        path = self._app_path()
        if path is None:
            self._send(404, b"Not found")
            return
        if path in ("/", "/index.html", "/embed"):
            self._send_index()
        elif path == "/styles.css":
            if STYLES.exists():
                self._send_static_file(STYLES, "text/css; charset=utf-8", cache_control="no-cache")
            else:
                self._send(404, b"styles.css not found")
        elif path == "/i18n.js":
            if I18N_JS.exists():
                self._send_static_file(I18N_JS, "text/javascript; charset=utf-8", cache_control="no-cache")
            else:
                self._send(404, b"i18n.js not found")
        elif path == "/helpers.js":
            if HELPERS_JS.exists():
                self._send_static_file(HELPERS_JS, "text/javascript; charset=utf-8", cache_control="no-cache")
            else:
                self._send(404, b"helpers.js not found")
        elif path == "/app.js":
            if APP_JS.exists():
                self._send_static_file(APP_JS, "text/javascript; charset=utf-8", cache_control="no-cache")
            else:
                self._send(404, b"app.js not found")
        elif path == "/service-worker.js":
            if PWA_ENABLED and SERVICE_WORKER.exists():
                self._send_static_file(SERVICE_WORKER, "text/javascript; charset=utf-8", cache_control="no-cache", allow_precompressed=False)
            else:
                self._send(404, b"service-worker.js not found")
        elif path and path.startswith("/brand/"):
            name = path[len("/brand/"):]
            if name == "site.webmanifest" and not PWA_ENABLED:
                self._send(404, b"PWA is disabled")
                return
            if name and "/" not in name and "\\" not in name:
                asset = ACTIVE_BRAND_DIR / name
                if asset.is_file():
                    content_type = mimetypes.guess_type(str(asset))[0] or "application/octet-stream"
                    if name.endswith(".webmanifest"):
                        content_type = "application/manifest+json; charset=utf-8"
                    elif name.endswith(".svg"):
                        content_type = "image/svg+xml; charset=utf-8"
                    self._send_static_file(asset, content_type, cache_control="no-cache")
                else:
                    self._send(404, b"Brand asset not found")
            else:
                self._send(404, b"Brand asset not found")
        elif path and path.startswith("/assets/"):
            rel = path.lstrip("/")
            allowed = set(PRODUCTION_ASSETS.values()) if PRODUCTION_BUILD_AVAILABLE else set()
            if rel in allowed:
                asset = DIST_ROOT / rel
                ctype = "text/css; charset=utf-8" if rel.endswith(".css") else "text/javascript; charset=utf-8"
                self._send_static_file(asset, ctype, cache_control="public, max-age=31536000, immutable")
            else:
                self._send(404, b"Asset not found")
        elif path and path.lstrip("/") in LOCALIZED_READMES:
            localized = README.parent / path.lstrip("/")
            if localized.is_file():
                self._send_static_file(localized, "text/markdown; charset=utf-8", cache_control="no-cache")
            else:
                self._send(404, b"Localized README not found")
        elif path == "/README.md":
            if README.exists():
                self._send_static_file(
                    README, "text/markdown; charset=utf-8", cache_control="no-cache"
                )
            else:
                self._send(404, b"README.md not found")
        elif path == "/API.md":
            if API_DOC.exists():
                self._send_static_file(API_DOC, "text/markdown; charset=utf-8", cache_control="no-cache")
            else:
                self._send(404, b"API.md not found")
        elif path == "/TECHNICAL.md":
            if TECHNICAL_DOC.exists():
                self._send_static_file(TECHNICAL_DOC, "text/markdown; charset=utf-8", cache_control="no-cache")
            else:
                self._send(404, b"TECHNICAL.md not found")
        elif path == "/CHANGELOG.md":
            if CHANGELOG.exists():
                self._send_static_file(
                    CHANGELOG, "text/markdown; charset=utf-8", cache_control="no-cache"
                )
            else:
                self._send(404, b"CHANGELOG.md not found")
        elif path == "/api/v1/features":
            payload = json.dumps({"feedback": feedback_enabled(CONFIG), "pwa": PWA_ENABLED, "reminders": {"enabled": REMINDERS_ENABLED, "vapidPublicKey": VAPID_PUBLIC_KEY if REMINDERS_ENABLED else None}}, ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8", cache_control="no-store")
        elif path == "/health":
            self._send(
                200, b'{"status":"ok"}', "application/json; charset=utf-8",
                cache_control="no-store"
            )
        elif path == "/version":
            body = json.dumps({
                "version": APP_VERSION,
                "buildTime": BUILD_TIME or None,
                "gitCommit": GIT_COMMIT or None,
                "apiVersions": ["v1"],
                "apiDefault": "/api/v1/renyyt",
                "repository": "https://github.com/janilahti/renyyt",
            }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8", cache_control="no-cache")
        elif path in ("/metrics", "/metrics/openmetrics"):
            accept = (self.headers.get("Accept") or "").lower()
            openmetrics = path.endswith("/openmetrics") or "application/openmetrics-text" in accept
            ctype = "application/openmetrics-text; version=1.0.0; charset=utf-8" if openmetrics else "text/plain; version=0.0.4; charset=utf-8"
            self._send(200, METRICS.render(openmetrics=openmetrics), ctype, cache_control="no-store")
        elif path == "/ready":
            ready, checks = readiness_state()
            body = json.dumps(
                {"status": "ready" if ready else "not_ready", "checks": checks},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            self._send(
                200 if ready else 503,
                body,
                "application/json; charset=utf-8",
                cache_control="no-store",
            )
        else:
            self._send(404, b"Not found")

    def do_GET(self):
        self._renyyt_request_started = time.monotonic()
        METRICS.request_started()
        try:
            self._handle_get_or_head()
        finally:
            METRICS.request_finished()

    def do_HEAD(self):
        self._renyyt_request_started = time.monotonic()
        METRICS.request_started()
        try:
            self._handle_get_or_head()
        finally:
            METRICS.request_finished()

    def _send_api_error(self, error):
        body = json.dumps(
            {"error": error.message, "code": error.code}, ensure_ascii=False
        ).encode("utf-8")
        headers = {"Retry-After": error.retry_after} if error.retry_after else None
        self._send(
            error.status, body, "application/json; charset=utf-8",
            cache_control="no-store", extra_headers=headers
        )

    def _send_method_not_allowed(self):
        self._send(
            405, b"Method not allowed", cache_control="no-store",
            extra_headers={"Allow": "GET, HEAD, POST, OPTIONS"}
        )

    def _validate_api_origin(self):
        host = self._external_host()
        if ALLOWED_HOSTS and host not in [item.lower() for item in ALLOWED_HOSTS]:
            raise ApiError("HOST_NOT_ALLOWED", "The request Host is not allowed.", 403)
        origin = (self.headers.get("Origin") or "").strip()
        if not origin:
            return
        normalized_allowed = [item.rstrip("/") for item in ALLOWED_ORIGINS]
        if normalized_allowed and origin.rstrip("/") in normalized_allowed:
            return
        try:
            parsed_origin = urlsplit(origin)
            origin_host = parsed_origin.netloc.lower()
            origin_proto = parsed_origin.scheme.lower()
        except ValueError:
            origin_host = ""
            origin_proto = ""
        if not normalized_allowed and origin_host and origin_host == host and origin_proto == self._external_proto():
            return
        raise ApiError("ORIGIN_NOT_ALLOWED", "The browser request Origin is not allowed.", 403)

    def _read_json_body(self, max_bytes=None):
        if max_bytes is None:
            max_bytes = MAX_REQUEST_BODY
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if not (content_type == "application/json" or content_type.endswith("+json")):
            raise ApiError("UNSUPPORTED_MEDIA_TYPE", "The API accepts JSON requests only.", 415)
        transfer_encoding = (self.headers.get("Transfer-Encoding") or "").strip()
        if transfer_encoding:
            raise ApiError("UNSUPPORTED_TRANSFER_ENCODING", "Transfer-Encoding is not supported for API requests.", 400)
        content_lengths = self.headers.get_all("Content-Length") or []
        if not content_lengths:
            raise ApiError("LENGTH_REQUIRED", "Content-Length-otsake puuttuu.", 411)
        if len(content_lengths) != 1:
            raise ApiError("INVALID_CONTENT_LENGTH", "Multiple Content-Length headers are not allowed.", 400)
        raw_length = content_lengths[0]
        try:
            length = int(raw_length)
        except ValueError:
            raise ApiError("INVALID_CONTENT_LENGTH", "Content-Length ei ollut kelvollinen.", 400)
        if length < 0:
            raise ApiError("INVALID_CONTENT_LENGTH", "Content-Length ei ollut kelvollinen.", 400)
        if length > max_bytes:
            raise ApiError("REQUEST_TOO_LARGE", "The request body is too large.", 413)
        try:
            raw_body = self.rfile.read(length)
            if len(raw_body) != length:
                raise ApiError("INCOMPLETE_REQUEST_BODY", "The request body ended before Content-Length bytes were received.", 400)
            payload = json.loads(raw_body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError("INVALID_REQUEST_JSON", "The request JSON is invalid.", 400)
        if not isinstance(payload, dict):
            raise ApiError("INVALID_REQUEST", "The request JSON body must be an object.", 400)
        return payload

    def _handle_feedback_post(self):
        if not feedback_enabled(CONFIG):
            raise ApiError("FEEDBACK_DISABLED", "Feedback is not configured on this server.", 404)
        client_ip = self._client_ip()
        allowed, retry_after = FEEDBACK_LIMITER.check_and_record(client_ip)
        if not allowed:
            raise ApiError("FEEDBACK_RATE_LIMITED", "Too many feedback messages. Try again later.", 429, retry_after=retry_after)
        payload = self._read_json_body(max_bytes=min(1048576, max(MAX_REQUEST_BODY, FEEDBACK_MAX_DATA_BYTES + 8192)))
        try:
            message, reply_to, collection_json = validate_feedback_payload(payload, FEEDBACK_MAX_DATA_BYTES)
        except ValueError as exc:
            raise ApiError("INVALID_FEEDBACK", str(exc), 400)
        metadata = {
            "version": APP_VERSION,
            "request_id": self._request_id(),
        }
        user_agent = (self.headers.get("User-Agent") or "").strip()
        if user_agent:
            metadata["user_agent"] = user_agent[:300].replace("\n", " ").replace("\r", " ")

        smtp_started = time.monotonic()

        def smtp_debug(phase, **fields):
            self._log("DEBUG", "feedback_smtp", phase=phase, **fields)

        def smtp_trace(phase, **fields):
            self._log("TRACE", "feedback_smtp_sensitive", phase=phase, **fields)

        try:
            send_feedback(CONFIG, message, reply_to=reply_to, metadata=metadata, collection_json=collection_json, debug=smtp_debug, sensitive_trace=smtp_trace if LOG_LEVEL == "TRACE" else None)
        except (socket.timeout, TimeoutError) as exc:
            self._log(
                "ERROR", "feedback_smtp_timeout",
                error_type=type(exc).__name__,
                elapsed_ms=int((time.monotonic() - smtp_started) * 1000),
                smtp_host=CONFIG["smtp_host"], smtp_port=CONFIG["smtp_port"],
            )
            raise ApiError("FEEDBACK_SMTP_TIMEOUT", "Feedback email delivery timed out.", 504)
        except (smtplib.SMTPException, OSError) as exc:
            smtp_code = getattr(exc, "smtp_code", None)
            self._log(
                "ERROR", "feedback_smtp_error",
                error_type=type(exc).__name__, smtp_code=smtp_code,
                elapsed_ms=int((time.monotonic() - smtp_started) * 1000),
                smtp_host=CONFIG["smtp_host"], smtp_port=CONFIG["smtp_port"],
            )
            raise ApiError("FEEDBACK_SMTP_ERROR", "Feedback email delivery failed.", 502)

        self._log("DEBUG", "feedback_smtp_success", elapsed_ms=int((time.monotonic() - smtp_started) * 1000))
        out = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
        self._send(200, out, "application/json; charset=utf-8", cache_control="no-store")

    def _handle_reminder_post(self, path):
        if not REMINDERS_ENABLED or REMINDER_STORE is None:
            raise ApiError("REMINDERS_DISABLED", "Push reminders are not enabled on this server.", 404)
        payload = self._read_json_body()
        subscription = payload.get("subscription")
        try:
            if path == "/api/v1/reminders/unsubscribe":
                REMINDER_STORE.unsubscribe(subscription)
                body = {"ok": True, "subscribed": False}
            else:
                reminders = payload.get("reminders", [])
                locale = payload.get("locale", "fi")
                sid, count = REMINDER_STORE.sync(subscription, reminders, locale=locale)
                body = {"ok": True, "subscribed": True, "reminders": count, "subscriptionId": sid[:12]}
        except ReminderError as exc:
            raise ApiError("INVALID_REMINDER_REQUEST", str(exc), 400)
        self._send(200, json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json; charset=utf-8", cache_control="no-store")

    def do_POST(self):
        self._renyyt_request_started = time.monotonic()
        METRICS.request_started()
        path = self._app_path()
        if path not in ("/api/v1/renyyt", "/api/v1/feedback", "/api/v1/reminders/sync", "/api/v1/reminders/unsubscribe"):
            self._send(404, b"Not found")
            METRICS.request_finished()
            return
        started = time.monotonic()
        try:
            self._validate_api_origin()
            if path == "/api/v1/feedback":
                self._handle_feedback_post()
                return
            if path in ("/api/v1/reminders/sync", "/api/v1/reminders/unsubscribe"):
                self._handle_reminder_post(path)
                return
            client_ip = self._client_ip()
            rate_limit_exempt = self._rate_limit_exempt(client_ip)
            allowed, retry_after = (True, 0) if rate_limit_exempt else RATE_LIMITER.check(client_ip)
            if not allowed:
                METRICS.record_rate_limited()
                raise ApiError(
                    "RATE_LIMITED",
                    "Too many failed authentication attempts. Try again later.",
                    429, retry_after=retry_after,
                )

            payload = self._read_json_body()

            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", ""))
            raw_suffixes = payload.get("suffixes", [])
            if not isinstance(raw_suffixes, list):
                raise ApiError("INVALID_REQUEST", "The suffixes field must be a list.", 400)
            suffixes = [str(x).strip() for x in raw_suffixes if str(x).strip()]
            if not username or not password:
                raise ApiError("MISSING_CREDENTIALS", "Asiakasnumero ja salasana ovat pakollisia.", 400)

            cache_key = RESPONSE_CACHE.make_key(username, password, suffixes) if RESPONSE_CACHE.enabled else None
            if LOG_LEVEL == "TRACE":
                self._log(
                    "TRACE", "api_json_request_sensitive",
                    body=json.dumps({"username": username, "password": password, "suffixes": suffixes}, ensure_ascii=False, separators=(",", ":")),
                )
            cache_fingerprint = cache_key[:12] if cache_key else ""

            def upstream_debug(phase, **fields):
                self._log("DEBUG", "upstream_http", phase=phase, **fields)

            def upstream_trace(phase, **fields):
                self._log("TRACE", "upstream_http_sensitive", phase=phase, **fields)

            # Serialize only fills for the same opaque cache key. Different customers
            # and cache hits remain independent; a concurrent duplicate waits for the
            # first request and then consumes the cached result.
            with RESPONSE_CACHE.key_lock(cache_key):
                cached = RESPONSE_CACHE.get(cache_key) if cache_key else None
                if cached is not None:
                    stats = RESPONSE_CACHE.stats()
                    self._log(
                        "DEBUG", "api_cache", result="hit", key=cache_fingerprint, bytes=len(cached),
                        entries=stats["entries"], cache_bytes=stats["bytes"],
                    )
                    try:
                        cached_payload = json.loads(cached)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        cached_payload = {"services": [], "customerNumbers": [], "warnings": []}
                    response_body = _response_with_freshness(cached_payload, "memory-cache")
                    if LOG_LEVEL == "TRACE":
                        self._log("TRACE", "api_json_response_sensitive", source="cache", body=response_body.decode("utf-8", errors="replace"))
                    RATE_LIMITER.clear(client_ip) if not rate_limit_exempt else None
                    METRICS.record_api(time.monotonic() - started)
                    self._send(
                        200, response_body, "application/json; charset=utf-8", cache_control="no-store",
                        extra_headers={"X-Renyyt-Cache": "HIT"},
                    )
                    self._log("INFO", "api_success", source="memory-cache", cache="HIT",
                              duration_ms=round((time.monotonic() - started) * 1000, 1))
                    return
                if cache_key:
                    stats = RESPONSE_CACHE.stats()
                    self._log(
                        "DEBUG", "api_cache", result="miss", key=cache_fingerprint,
                        entries=stats["entries"], cache_bytes=stats["bytes"],
                    )
                else:
                    self._log(
                        "DEBUG", "api_cache", result="disabled",
                        max_entries=CACHE_MAX_ENTRIES, ttl_seconds=CACHE_TTL_SECONDS, max_bytes=CACHE_MAX_BYTES,
                    )

                services, numbers = fetch_services(username, password, suffixes, debug=upstream_debug, trace=upstream_trace if LOG_LEVEL == "TRACE" else None)
                warnings = validate_services_payload(services)
                unknown_fields = collect_unknown_fields(services)
                if unknown_fields:
                    METRICS.record_unknown_fields(len(unknown_fields))
                    self._log(
                        "DEBUG",
                        "upstream_unknown_fields",
                        count=len(unknown_fields),
                        fields=",".join("%s:%s" % (item["field"], item["type"]) for item in unknown_fields),
                    )
                if warnings:
                    METRICS.record_schema_warnings(len(warnings))
                    self._log("WARNING", "upstream_schema_warning", count=len(warnings))
                RATE_LIMITER.clear(client_ip) if not rate_limit_exempt else None
                source = "fixture" if FIXTURE_FILE_SETTING else "upstream"
                base_payload = {
                    "services": services,
                    "customerNumbers": numbers,
                    "warnings": warnings,
                    "upstreamFetchedAt": None if FIXTURE_FILE_SETTING else _utc_now_iso(),
                }
                # Cache the canonical payload. Dynamic age/source values are added only
                # when a response is emitted, so cached data never carries a stale age.
                cached_bytes = json.dumps(base_payload, ensure_ascii=False).encode("utf-8")
                out = _response_with_freshness(base_payload, source)
                if cache_key:
                    stored = RESPONSE_CACHE.put(cache_key, cached_bytes)
                    stats = RESPONSE_CACHE.stats()
                    self._log(
                        "DEBUG", "api_cache", result="stored" if stored else "not_stored",
                        key=cache_fingerprint, bytes=len(out), entries=stats["entries"], cache_bytes=stats["bytes"],
                        max_bytes=CACHE_MAX_BYTES,
                    )
                if LOG_LEVEL == "TRACE":
                    self._log("TRACE", "api_json_response_sensitive", source="fixture" if FIXTURE_FILE_SETTING else "upstream", body=out.decode("utf-8", errors="replace"))
                METRICS.record_api(time.monotonic() - started)
                self._send(
                    200, out, "application/json; charset=utf-8", cache_control="no-store",
                    extra_headers={"X-Renyyt-Cache": "MISS" if cache_key else "DISABLED"},
                )
                self._log("INFO", "api_success", source=source, cache="MISS" if cache_key else "DISABLED",
                          duration_ms=round((time.monotonic() - started) * 1000, 1))
        except ApiError as e:
            if e.code == "AUTH_FAILED":
                client_ip = locals().get("client_ip", self._client_ip())
                if self._rate_limit_exempt(client_ip):
                    blocked, retry_after = False, 0
                else:
                    blocked, retry_after = RATE_LIMITER.record_failure(client_ip)
                if blocked:
                    METRICS.record_rate_limited()
                    e = ApiError(
                        "RATE_LIMITED",
                        "Too many failed authentication attempts. Try again later.",
                        429, retry_after=retry_after,
                    )
            if path not in ("/api/v1/feedback", "/api/v1/reminders/sync", "/api/v1/reminders/unsubscribe"):
                METRICS.record_api(time.monotonic() - started, e.code)
            self._log(
                "WARNING" if e.status < 500 else "ERROR",
                "feedback_error" if path == "/api/v1/feedback" else ("reminder_error" if path.startswith("/api/v1/reminders/") else "api_error"),
                code=e.code,
                status=e.status,
                upstream_status=e.upstream_status,
            )
            self._send_api_error(e)
        except socket.timeout:
            if path not in ("/api/v1/feedback", "/api/v1/reminders/sync", "/api/v1/reminders/unsubscribe"):
                METRICS.record_api(time.monotonic() - started, "CLIENT_TIMEOUT")
            error = ApiError("CLIENT_TIMEOUT", "Receiving the HTTP request timed out.", 408)
            self._send_api_error(error)
        except Exception as e:
            if path not in ("/api/v1/feedback", "/api/v1/reminders/sync", "/api/v1/reminders/unsubscribe"):
                METRICS.record_api(time.monotonic() - started, "INTERNAL_ERROR")
            self._log("ERROR", "feedback_unexpected_error" if path == "/api/v1/feedback" else ("reminder_unexpected_error" if path.startswith("/api/v1/reminders/") else "unexpected_error"), error_type=type(e).__name__, status=500)
            error = ApiError("INTERNAL_ERROR", "An unexpected server error occurred.", 500)
            self._send_api_error(error)
        finally:
            METRICS.request_finished()

    def do_PUT(self):
        self._send_method_not_allowed()

    def do_PATCH(self):
        self._send_method_not_allowed()

    def do_DELETE(self):
        self._send_method_not_allowed()

    def do_OPTIONS(self):
        self._renyyt_request_started = time.monotonic()
        METRICS.request_started()
        try:
            if APP_BASE_PATH and self._request_path() == APP_BASE_PATH:
                self._send_redirect(308, APP_BASE_PATH + "/")
                return
            path = self._app_path()
            if path is None:
                self._send(404, b"Not found")
                return
            if path in ("/api/v1/renyyt", "/api/v1/feedback", "/api/v1/reminders/sync", "/api/v1/reminders/unsubscribe"):
                self._send(204, b"", cache_control="no-store", extra_headers={"Allow": "POST, OPTIONS"})
                return
            static_paths = {
                "/", "/index.html", "/embed", "/styles.css", "/i18n.js", "/helpers.js", "/app.js",
                "/README.md", "/API.md", "/TECHNICAL.md", "/CHANGELOG.md", "/service-worker.js", "/health", "/ready", "/version",
                "/metrics", "/metrics/openmetrics", "/api/v1/features",
            }
            asset_known = False
            if path and path.startswith("/assets/") and PRODUCTION_BUILD_AVAILABLE:
                asset_known = path.lstrip("/") in set(PRODUCTION_ASSETS.values())
            brand_known = bool(path and path.startswith("/brand/") and "/" not in path[len("/brand/"):] and (ACTIVE_BRAND_DIR / path[len("/brand/"):]).is_file())
            if path in static_paths or path.lstrip("/") in LOCALIZED_READMES or asset_known or brand_known:
                self._send(204, b"", cache_control="no-store", extra_headers={"Allow": "GET, HEAD, OPTIONS"})
                return
            self._send(404, b"Not found")
        finally:
            METRICS.request_finished()

    def do_CONNECT(self):
        self._send_method_not_allowed()

    def do_TRACE(self):
        self._send_method_not_allowed()

    def log_message(self, fmt, *args):
        # BaseHTTPRequestHandler calls this for access logging. Never log request bodies or credentials.
        self._log(
            "INFO",
            "access",
            remote=self._client_ip() or "-",
            method=getattr(self, "command", "-"),
            path=self._request_path() if hasattr(self, "path") else "-",
            result=(fmt % args).replace("\n", " "),
        )




def _background_log(level, event, **fields):
    level = str(level).upper()
    if LOG_LEVELS.get(level, 100) < LOG_LEVELS[LOG_LEVEL]:
        return
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    clean = {key: str(value).replace("\r", " ").replace("\n", " ") for key, value in fields.items() if value is not None}
    if LOG_FORMAT == "json":
        payload = {"timestamp": stamp, "level": level, "event": event}
        payload.update(clean)
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), file=sys.stderr, flush=True)
        return
    parts = [stamp, level, "event=%s" % event]
    parts.extend("%s=%s" % (key, value) for key, value in clean.items())
    print(" ".join(parts), file=sys.stderr, flush=True)


def _run_reminder_cli(argv):
    parser = argparse.ArgumentParser(prog="renyyt reminders", description="Renyyt Web Push reminder maintenance")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run-due", help="Send all reminders that are due and exit")
    run_parser.add_argument("--limit", type=int, default=100, help="Maximum number of due reminders to process")
    sub.add_parser("stats", help="Show reminder store statistics")
    sub.add_parser("generate-vapid", help="Generate VAPID key values for .env (requires renyyt[push])")
    args = parser.parse_args(argv)
    if args.command == "generate-vapid":
        try:
            import base64
            from py_vapid import Vapid02
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            print("renyyt: Web Push dependencies are not installed. Install with: pip install 'renyyt[push]'", file=sys.stderr)
            return 2
        vapid = Vapid02()
        vapid.generate_keys()
        private_value = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
        public_value = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        enc = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")
        print("RENYYT_VAPID_PRIVATE_KEY=%s" % enc(private_value))
        print("RENYYT_VAPID_PUBLIC_KEY=%s" % enc(public_value))
        print("# Set RENYYT_VAPID_SUBJECT separately, e.g. mailto:admin@example.com")
        return 0
    try:
        db_path = validate_reminder_config(require_dependencies=(args.command == "run-due"))
    except ConfigError as exc:
        print("renyyt: configuration error: %s" % exc, file=sys.stderr)
        return 2
    if not REMINDERS_ENABLED or db_path is None:
        print("renyyt: reminders are disabled (set RENYYT_REMINDERS_ENABLED=true).", file=sys.stderr)
        return 2
    store = ReminderStore(db_path)
    if args.command == "stats":
        stats = store.stats()
        print("Reminder store: %s" % db_path)
        print("Subscriptions: %s" % stats["subscriptions"])
        print("Pending reminders: %s" % stats["pending"])
        return 0
    stats = run_due(CONFIG, store, logger=_background_log, limit=max(1, args.limit))
    print("Due: {due}, sent: {sent}, gone: {gone}, failed: {failed}".format(**stats))
    return 1 if stats["failed"] else 0

class ShutdownRequested(Exception):
    pass


def _sigterm_handler(signum, frame):
    raise ShutdownRequested()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "reminders":
        return _run_reminder_cli(argv[1:])
    parser = argparse.ArgumentParser(prog="renyyt", description="Renyyt waste collection schedule viewer server")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument("--check", action="store_true", help="Validate configuration and required runtime files without starting the server")
    args = parser.parse_args(argv)

    if args.check:
        try:
            fixture_path = validate_fixture_file()
            reminder_db = validate_reminder_config(require_dependencies=REMINDERS_ENABLED)
        except ConfigError as exc:
            print("renyyt: configuration error: %s" % exc, file=sys.stderr)
            return 2
        if SMTP_SSL and SMTP_STARTTLS:
            print("renyyt: configuration error: RENYYT_SMTP_SSL and RENYYT_SMTP_STARTTLS cannot both be enabled.", file=sys.stderr)
            return 2
        if SMTP_USER and not SMTP_PASSWORD:
            print("renyyt: configuration error: RENYYT_SMTP_PASSWORD is required when RENYYT_SMTP_USER is set.", file=sys.stderr)
            return 2
        ready, checks = readiness_state()
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            print("renyyt: check failed: %s" % ", ".join(failed), file=sys.stderr)
            return 1
        print("renyyt: configuration and runtime files OK")
        print("Environment file: %s" % (str(LOADED_ENV_FILE) if LOADED_ENV_FILE else "not loaded"))
        print("Feedback SMTP: %s" % ("enabled" if feedback_enabled(CONFIG) else "disabled"))
        print("Upstream fixture: %s" % (str(fixture_path) if fixture_path else "disabled"))
        print("PWA: %s" % ("enabled" if PWA_ENABLED else "disabled"))
        print("Push reminders: %s" % (
            "enabled (db=%s, scheduler=%s, run_times=%s, timezone=%s, sender=%s)" % (
                reminder_db,
                "internal" if REMINDERS_INTERNAL_SCHEDULER else "external",
                REMINDERS_RUN_TIMES,
                REMINDERS_TIMEZONE,
                "installed" if push_dependencies_available() else "not installed",
            ) if REMINDERS_ENABLED else "disabled"
        ))
        print("API memory cache: %s" % (
            "enabled (max_entries=%s, ttl=%ss, max_bytes=%s)" % (CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS, CACHE_MAX_BYTES)
            if RESPONSE_CACHE.enabled else "disabled"
        ))
        if LOG_LEVEL == "TRACE":
            print("WARNING: TRACE logging may include credentials, Renyy customer data and sensitive SMTP traffic.")
        return 0

    try:
        fixture_path = validate_fixture_file()
        reminder_db = validate_reminder_config(require_dependencies=REMINDERS_ENABLED)
    except ConfigError as exc:
        parser.error(str(exc))
    if SMTP_SSL and SMTP_STARTTLS:
        parser.error("RENYYT_SMTP_SSL and RENYYT_SMTP_STARTTLS cannot both be enabled")
    if SMTP_USER and not SMTP_PASSWORD:
        parser.error("RENYYT_SMTP_PASSWORD is required when RENYYT_SMTP_USER is set")

    global REMINDER_STORE, REMINDER_SCHEDULER
    if REMINDERS_ENABLED:
        REMINDER_STORE = ReminderStore(reminder_db)
        if REMINDERS_INTERNAL_SCHEDULER:
            REMINDER_SCHEDULER = InternalReminderScheduler(CONFIG, REMINDER_STORE, logger=_background_log)
    host, port = CONFIG["host"], CONFIG["port"]
    server = ThreadingHTTPServer((host, port), Handler)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _sigterm_handler)
    print("renyyt: http://%s:%s%s" % (host, port, APP_BASE_PATH or "/"))
    if APP_BASE_PATH:
        print("Base path: %s" % APP_BASE_PATH)
    print("Version: %s%s" % (APP_VERSION, (" (" + GIT_COMMIT + ")") if GIT_COMMIT else ""))
    print("Log level: %s (%s)" % (LOG_LEVEL, LOG_FORMAT))
    if LOG_LEVEL == "TRACE":
        print("WARNING: TRACE logging may include credentials, Renyy customer data and sensitive SMTP traffic.", file=sys.stderr)
    print("Production build: %s" % PRODUCTION_BUILD_STATUS)
    print("Upstream fixture: %s" % (str(fixture_path) if fixture_path else "disabled"))
    print("API memory cache: %s" % (
        "enabled (max_entries=%s, ttl=%ss, max_bytes=%s)" % (CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS, CACHE_MAX_BYTES)
        if RESPONSE_CACHE.enabled else "disabled"
    ))
    RESPONSE_CACHE.start_janitor()
    if REMINDER_SCHEDULER:
        REMINDER_SCHEDULER.start()
        print("Push reminders: enabled (internal scheduler: %s; timezone: %s)" % (REMINDERS_RUN_TIMES, REMINDERS_TIMEZONE))
    elif REMINDERS_ENABLED:
        print("Push reminders: enabled (external scheduler; db=%s)" % reminder_db)
    else:
        print("Push reminders: disabled")
    print(
        "Upstream timeouts: session=%ss login=%ss services=%ss" %
        (SESSION_TIMEOUT, LOGIN_TIMEOUT, SERVICES_TIMEOUT)
    )
    try:
        server.serve_forever()
    except (KeyboardInterrupt, ShutdownRequested):
        print("\nServer stopped.")
    finally:
        if REMINDER_SCHEDULER:
            REMINDER_SCHEDULER.stop()
        RESPONSE_CACHE.stop_janitor()
        signal.signal(signal.SIGTERM, previous_sigterm)
        server.server_close()


if __name__ == "__main__":
    main()
