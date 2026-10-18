#!/usr/bin/env python3
import contextlib
import gzip
import hashlib
import io
import time
import http.client
import importlib.util
import json
import os
import socket
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
SRC = REPO_ROOT / "src"
import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
import renyyt.server as renyy
from renyyt.config import ConfigError, load_env_file, bootstrap_environment
from renyyt.feedback import _safe_reply_to_header, validate_feedback_payload
from renyyt.cache import ResponseCache



class EnvFileTestCase(unittest.TestCase):
    def test_env_file_supports_spaces_quotes_comments_and_process_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                'PLAIN=value with spaces\n'
                'QUOTED="quoted value with spaces"\n'
                "SINGLE='single quoted value'\n"
                'COMMENTED=value # comment\n'
                'export EXPORTED=ok\n'
                'KEEP=file-value\n',
                encoding="utf-8",
            )
            env = {"KEEP": "process-value"}
            self.assertTrue(load_env_file(path, environ=env))
            self.assertEqual(env["PLAIN"], "value with spaces")
            self.assertEqual(env["QUOTED"], "quoted value with spaces")
            self.assertEqual(env["SINGLE"], "single quoted value")
            self.assertEqual(env["COMMENTED"], "value")
            self.assertEqual(env["EXPORTED"], "ok")
            self.assertEqual(env["KEEP"], "process-value")

    def test_env_file_rejects_malformed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("NOT_AN_ASSIGNMENT\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_env_file(path, environ={})


class CliTestCase(unittest.TestCase):
    def test_version_flag_prints_version_without_starting_server(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            renyy.main(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "renyyt %s" % renyy.APP_VERSION)

    def test_help_describes_schedule_viewer(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            renyy.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("Renyyt waste collection schedule viewer server", output.getvalue())

    def test_check_validates_without_starting_server(self):
        output = io.StringIO()
        with mock.patch.object(renyy, "readiness_state", return_value=(True, {"config": True})), \
             mock.patch.object(renyy, "SMTP_SSL", False), mock.patch.object(renyy, "SMTP_STARTTLS", True), \
             mock.patch.object(renyy, "SMTP_USER", ""), contextlib.redirect_stdout(output):
            result = renyy.main(["--check"])
        self.assertEqual(result, 0)
        self.assertIn("configuration and runtime files OK", output.getvalue())
        self.assertIn("Environment file:", output.getvalue())


    def test_bootstrap_environment_loads_source_checkout_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("1.0\n", encoding="utf-8")
            (root / ".env").write_text("RENYYT_SMTP_HOST=smtp.example.test\n", encoding="utf-8")
            env = {}
            with mock.patch.dict(os.environ, env, clear=True):
                loaded = bootstrap_environment(root)
                self.assertEqual(loaded, root / ".env")
                self.assertEqual(os.environ.get("RENYYT_SMTP_HOST"), "smtp.example.test")

    def test_reminder_cli_stats_and_run_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reminders.sqlite3"
            with mock.patch.object(renyy, "REMINDERS_ENABLED", True), \
                 mock.patch.object(renyy, "validate_reminder_config", return_value=db), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(renyy.main(["reminders", "stats"]), 0)
                self.assertIn("Subscriptions: 0", output.getvalue())
            with mock.patch.object(renyy, "REMINDERS_ENABLED", True), \
                 mock.patch.object(renyy, "validate_reminder_config", return_value=db), \
                 mock.patch.object(renyy, "run_due", return_value={"due":1,"sent":1,"gone":0,"failed":0}), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(renyy.main(["reminders", "run-due"]), 0)
                self.assertIn("sent: 1", output.getvalue())

    def test_reminder_generate_vapid_requires_optional_dependency(self):
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *args, **kwargs):
            if name in ("py_vapid", "cryptography.hazmat.primitives") or name.startswith("py_vapid"):
                raise ImportError(name)
            return real_import(name, *args, **kwargs)
        with mock.patch("builtins.__import__", side_effect=fake_import), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(renyy.main(["reminders", "generate-vapid"]), 2)
            self.assertIn("renyyt[push]", err.getvalue())

    def test_reminder_configuration_validation(self):
        with mock.patch.object(renyy, "REMINDERS_ENABLED", False):
            self.assertIsNone(renyy.validate_reminder_config())
        with mock.patch.object(renyy, "REMINDERS_ENABLED", True), mock.patch.object(renyy, "PWA_ENABLED", False):
            with self.assertRaises(ConfigError): renyy.validate_reminder_config()
        with mock.patch.object(renyy, "REMINDERS_ENABLED", True), mock.patch.object(renyy, "PWA_ENABLED", True), \
             mock.patch.object(renyy, "VAPID_PRIVATE_KEY", ""), mock.patch.object(renyy, "VAPID_PUBLIC_KEY", ""), mock.patch.object(renyy, "VAPID_SUBJECT", ""):
            with self.assertRaises(ConfigError): renyy.validate_reminder_config()
        with mock.patch.object(renyy, "REMINDERS_ENABLED", True), mock.patch.object(renyy, "PWA_ENABLED", True), \
             mock.patch.object(renyy, "VAPID_PRIVATE_KEY", "priv"), mock.patch.object(renyy, "VAPID_PUBLIC_KEY", "pub"), mock.patch.object(renyy, "VAPID_SUBJECT", "bad"), \
             mock.patch.object(renyy, "REMINDERS_RUN_TIMES", "07:00"), mock.patch.object(renyy, "REMINDERS_TIMEZONE", "UTC"):
            with self.assertRaises(ConfigError): renyy.validate_reminder_config()

    def test_feedback_reply_address_can_be_free_form_but_reply_to_header_is_conservative(self):
        message, reply, collection_json = validate_feedback_payload({"message": "Hello", "email": "reply@example.com"})
        self.assertEqual((message, reply, collection_json), ("Hello", "reply@example.com", None))
        self.assertEqual(_safe_reply_to_header(reply), "reply@example.com")
        message2, reply2, collection_json2 = validate_feedback_payload({"message": "Hello", "email": "call me instead"})
        self.assertEqual(reply2, "call me instead")
        self.assertIsNone(collection_json2)
        self.assertEqual(_safe_reply_to_header(reply2), "")
        self.assertEqual(_safe_reply_to_header("good@example.com\nBcc: attacker@example.com"), "")


class ResponseCacheTestCase(unittest.TestCase):
    def test_cache_requires_entries_and_ttl(self):
        self.assertFalse(ResponseCache(0, 60).enabled)
        self.assertFalse(ResponseCache(10, 0).enabled)
        self.assertTrue(ResponseCache(10, 60).enabled)

    def test_cache_hides_credentials_in_key_and_expires(self):
        now = [100.0]
        cache = ResponseCache(2, 5, 1024, clock=lambda: now[0])
        key = cache.make_key("01-SECRET-00", "super-secret", ["01"])
        self.assertNotIn("SECRET", key)
        self.assertNotIn("super-secret", key)
        cache.put(key, b'{"services":[]}')
        self.assertEqual(cache.get(key), b'{"services":[]}')
        now[0] = 106.0
        self.assertIsNone(cache.get(key))
        self.assertEqual(cache.stats()["entries"], 0)

    def test_cache_evicts_lru_and_respects_byte_limit(self):
        cache = ResponseCache(2, 60, 7)
        cache.put("a", b"aaa")
        cache.put("b", b"bbb")
        self.assertEqual(cache.get("a"), b"aaa")
        cache.put("c", b"ccc")
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), b"aaa")
        self.assertEqual(cache.get("c"), b"ccc")

    def test_key_lock_serializes_same_key_but_not_other_keys(self):
        cache = ResponseCache(10, 60, 1024)
        entered = []
        first_ready = threading.Event()
        release_first = threading.Event()

        def worker(name, key, hold=False):
            with cache.key_lock(key):
                entered.append(name)
                if hold:
                    first_ready.set()
                    release_first.wait(1)

        t1 = threading.Thread(target=worker, args=("same-1", "same", True))
        t2 = threading.Thread(target=worker, args=("same-2", "same"))
        t3 = threading.Thread(target=worker, args=("other", "other"))
        t1.start(); self.assertTrue(first_ready.wait(1)); t2.start(); t3.start()
        t3.join(1)
        self.assertIn("other", entered)
        self.assertNotIn("same-2", entered)
        release_first.set(); t1.join(1); t2.join(1)
        self.assertIn("same-2", entered)


class FakeResponse:
    def __init__(self, body=b"", content_type="text/plain", url="https://extranet.pjhoy.fi/pirkka/secure/get_services_by_customer_numbers.do"):
        self._body = body
        self.headers = {"Content-Type": content_type}
        self._url = url

    def read(self):
        return self._body

    def geturl(self):
        return self._url

    def getcode(self):
        return 200


class FakeOpener:
    def __init__(self, items):
        self.items = list(items)
        self.addheaders = []
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.index = root / "index.html"
        self.index_gz = root / "index.html.gz"
        self.readme = root / "README.md"
        self.styles = root / "styles.css"
        self.app_js = root / "app.js"
        self.i18n_js = root / "i18n.js"
        self.helpers_js = root / "helpers.js"
        self.index.write_text("<!doctype html><title>test</title>", encoding="utf-8")
        self.index_gz.write_bytes(gzip.compress(self.index.read_bytes()))
        self.index_gz.touch()
        self.readme.write_text("# Test\n", encoding="utf-8")
        for name in renyy.LOCALIZED_READMES:
            (root / name).write_text("# Synthetic localized guide\n", encoding="utf-8")
        self.styles.write_text("body { color: black; }\n", encoding="utf-8")
        self.app_js.write_text("console.log('test');\n", encoding="utf-8")
        self.i18n_js.write_text("window.RenyytI18n = {};\n", encoding="utf-8")
        self.helpers_js.write_text("window.RenyytHelpers = {};\n", encoding="utf-8")

        self.old = {
            "INDEX": renyy.INDEX,
            "INDEX_GZ": renyy.INDEX_GZ,
            "README": renyy.README,
            "STYLES": renyy.STYLES,
            "APP_JS": renyy.APP_JS,
            "I18N_JS": renyy.I18N_JS,
            "HELPERS_JS": renyy.HELPERS_JS,
            "ACTIVE_INDEX": renyy.ACTIVE_INDEX,
            "ACTIVE_INDEX_GZ": renyy.ACTIVE_INDEX_GZ,
            "PRODUCTION_BUILD_AVAILABLE": renyy.PRODUCTION_BUILD_AVAILABLE,
            "PRODUCTION_ASSETS": renyy.PRODUCTION_ASSETS,
            "PRODUCTION_BUILD_STATUS": renyy.PRODUCTION_BUILD_STATUS,
            "RATE_LIMIT_WHITELIST_NETWORKS": renyy.RATE_LIMIT_WHITELIST_NETWORKS,
            "TRUSTED_PROXY_NETWORKS": renyy.TRUSTED_PROXY_NETWORKS,
            "APP_BASE_PATH": renyy.APP_BASE_PATH,
            "INDEX_PLAIN_AVAILABLE": renyy.INDEX_PLAIN_AVAILABLE,
            "INDEX_GZIP_AVAILABLE": renyy.INDEX_GZIP_AVAILABLE,
            "PRECOMPRESSED_STATIC": renyy.PRECOMPRESSED_STATIC,
            "LOG_LEVEL": renyy.LOG_LEVEL,
            "ALLOWED_ORIGINS": renyy.ALLOWED_ORIGINS,
            "ALLOWED_HOSTS": renyy.ALLOWED_HOSTS,
            "METRICS": renyy.METRICS,
            "RATE_LIMITER": renyy.RATE_LIMITER,
            "MAX_REQUEST_BODY": renyy.MAX_REQUEST_BODY,
        }
        renyy.INDEX = self.index
        renyy.INDEX_GZ = self.index_gz
        renyy.README = self.readme
        renyy.STYLES = self.styles
        renyy.APP_JS = self.app_js
        renyy.I18N_JS = self.i18n_js
        renyy.HELPERS_JS = self.helpers_js
        renyy.PRODUCTION_BUILD_AVAILABLE = False
        renyy.PRODUCTION_ASSETS = {}
        renyy.PRODUCTION_BUILD_STATUS = "absent"
        renyy.RATE_LIMIT_WHITELIST_NETWORKS = []
        renyy.ACTIVE_INDEX = self.index
        renyy.ACTIVE_INDEX_GZ = self.index_gz
        renyy.TRUSTED_PROXY_NETWORKS = []
        renyy.APP_BASE_PATH = ""
        renyy.LOG_LEVEL = "ERROR"
        renyy.ALLOWED_ORIGINS = []
        renyy.ALLOWED_HOSTS = []
        renyy.RATE_LIMITER = renyy.RateLimiter(3, 60, 120)
        renyy.METRICS = renyy.Metrics(readiness=renyy.readiness_state, rate_stats=renyy.RATE_LIMITER.stats)
        renyy.MAX_REQUEST_BODY = 16384
        renyy.INDEX_PLAIN_AVAILABLE, renyy.INDEX_GZIP_AVAILABLE = renyy.detect_index_sources()
        renyy.PRECOMPRESSED_STATIC = renyy.detect_precompressed_static()

        self.httpd = renyy.ThreadingHTTPServer(("127.0.0.1", 0), renyy.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.httpd.server_address

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        for name, value in self.old.items():
            setattr(renyy, name, value)
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=3)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        result = (resp.status, dict(resp.getheaders()), data)
        conn.close()
        return result

    def raw_request(self, payload):
        sock = socket.create_connection((self.host, self.port), timeout=3)
        try:
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            sock.close()

    def test_index_has_no_cache_and_validators(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertIn("ETag", headers)
        self.assertIn("Last-Modified", headers)
        self.assertEqual(headers.get("Vary"), "Accept-Encoding")
        self.assertEqual(body, self.index.read_bytes())

    def test_index_etag_returns_304(self):
        status, headers, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        etag = headers["ETag"]
        status2, headers2, body2 = self.request("GET", "/", headers={"If-None-Match": etag})
        self.assertEqual(status2, 304)
        self.assertEqual(body2, b"")
        self.assertEqual(headers2["ETag"], etag)
        self.assertEqual(headers2["Cache-Control"], "no-cache")

    def test_gzip_is_only_sent_when_accepted(self):
        status, headers, body = self.request("GET", "/", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertEqual(gzip.decompress(body), self.index.read_bytes())

        status2, headers2, body2 = self.request("GET", "/")
        self.assertEqual(status2, 200)
        self.assertNotIn("Content-Encoding", headers2)
        self.assertEqual(body2, self.index.read_bytes())

    def test_static_css_uses_adjacent_gzip_when_available_and_accepted(self):
        css_gz = Path(str(self.styles) + ".gz")
        css_gz.write_bytes(gzip.compress(self.styles.read_bytes()))
        css_gz.touch()
        renyy.PRECOMPRESSED_STATIC = renyy.detect_precompressed_static()

        status, headers, body = self.request("GET", "/styles.css", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertEqual(headers.get("Vary"), "Accept-Encoding")
        self.assertEqual(gzip.decompress(body), self.styles.read_bytes())

        status2, headers2, body2 = self.request("GET", "/styles.css")
        self.assertEqual(status2, 200)
        self.assertNotIn("Content-Encoding", headers2)
        self.assertEqual(headers2.get("Vary"), "Accept-Encoding")
        self.assertEqual(body2, self.styles.read_bytes())

    def test_readme_has_no_cache_and_304(self):
        status, headers, body = self.request("GET", "/README.md")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertEqual(body, self.readme.read_bytes())
        status2, _, body2 = self.request("GET", "/README.md", headers={"If-None-Match": headers["ETag"]})
        self.assertEqual(status2, 304)
        self.assertEqual(body2, b"")

    def test_api_returns_service_schema_warnings_without_failing_entire_response(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        services = [
            {"ASTNextDate":"2026-10-02","ASTVali":"4","tariff":{"productgroup":"SEK"}},
            {"ASTNextDate":"2026-99-99","ASTVali":"2","tariff":{"productgroup":"BIO"}},
        ]
        with mock.patch.object(renyy, "fetch_services", return_value=(services, ["01-0000633-00"])):
            status, _, body = self.request("POST", "/api/v1/renyyt", body=payload, headers={"Content-Type":"application/json","Content-Length":str(len(payload))})
        self.assertEqual(status, 200)
        parsed = json.loads(body.decode("utf-8"))
        self.assertEqual(len(parsed["services"]), 2)
        self.assertEqual(parsed["warnings"][0]["code"], "INVALID_DATE")

    def test_api_response_includes_upstream_freshness_metadata(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        services = [{"ASTNextDate":"2026-10-02","ASTVali":"4","tariff":{"productgroup":"SEK"}}]
        with mock.patch.object(renyy, "fetch_services", return_value=(services, ["01-0000633-00"])), mock.patch.object(renyy, "_utc_now_iso", return_value="2026-10-04T18:00:00Z"):
            status, _, body = self.request("POST", "/api/v1/renyyt", body=payload, headers={"Content-Type":"application/json","Content-Length":str(len(payload))})
        self.assertEqual(status, 200)
        parsed = json.loads(body.decode("utf-8"))
        self.assertEqual(parsed["upstreamFetchedAt"], "2026-10-04T18:00:00Z")
        self.assertEqual(parsed["dataSource"], "upstream")
        self.assertIsInstance(parsed["upstreamAgeSeconds"], int)
        self.assertGreaterEqual(parsed["upstreamAgeSeconds"], 0)

    def test_health_api_and_ready_are_no_store(self):
        status, headers, _ = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")

        status_ready, ready_headers, ready_body = self.request("GET", "/ready")
        self.assertEqual(status_ready, 200)
        self.assertEqual(ready_headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(ready_body.decode("utf-8"))["status"], "ready")

        payload = json.dumps({}).encode("utf-8")
        status2, headers2, body2 = self.request(
            "POST", "/api/v1/renyyt", body=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        self.assertEqual(status2, 400)
        self.assertEqual(headers2["Cache-Control"], "no-store")
        parsed = json.loads(body2.decode("utf-8"))
        self.assertEqual(parsed["code"], "MISSING_CREDENTIALS")

    def test_ready_fails_when_required_file_is_missing(self):
        renyy.INDEX_PLAIN_AVAILABLE = False
        renyy.INDEX_GZIP_AVAILABLE = False
        status, _, body = self.request("GET", "/ready")
        self.assertEqual(status, 503)
        parsed = json.loads(body.decode("utf-8"))
        self.assertEqual(parsed["status"], "not_ready")
        self.assertFalse(parsed["checks"]["index"])

    def test_base_path_routes(self):
        renyy.APP_BASE_PATH = "/renyy"
        status, _, _ = self.request("GET", "/renyy/")
        self.assertEqual(status, 200)
        status2, _, _ = self.request("GET", "/renyy/embed")
        self.assertEqual(status2, 200)
        status3, _, _ = self.request("GET", "/renyy/README.md")
        self.assertEqual(status3, 200)
        status4, _, _ = self.request("GET", "/renyy/ready")
        self.assertEqual(status4, 200)
        self.assertEqual(self.request("GET", "/renyy/styles.css")[0], 200)
        self.assertEqual(self.request("GET", "/renyy/app.js")[0], 200)
        status5, _, _ = self.request("GET", "/")
        self.assertEqual(status5, 404)

    def test_head_static_routes_match_get_headers_without_body(self):
        get_status, get_headers, get_body = self.request("GET", "/")
        head_status, head_headers, head_body = self.request("HEAD", "/")
        self.assertEqual(head_status, get_status)
        self.assertEqual(head_body, b"")
        self.assertEqual(head_headers["Content-Length"], str(len(get_body)))
        self.assertEqual(head_headers["ETag"], get_headers["ETag"])
        self.assertEqual(head_headers["Cache-Control"], "no-cache")

        r_status, r_headers, r_body = self.request("GET", "/README.md")
        rh_status, rh_headers, rh_body = self.request("HEAD", "/README.md")
        self.assertEqual(rh_status, r_status)
        self.assertEqual(rh_body, b"")
        self.assertEqual(rh_headers["Content-Length"], str(len(r_body)))
        self.assertEqual(rh_headers["ETag"], r_headers["ETag"])

    def test_conditional_head_returns_304(self):
        status, headers, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        status2, headers2, body2 = self.request("HEAD", "/", headers={"If-None-Match": headers["ETag"]})
        self.assertEqual(status2, 304)
        self.assertEqual(body2, b"")
        self.assertEqual(headers2["ETag"], headers["ETag"])
        self.assertEqual(headers2["Cache-Control"], "no-cache")

    def test_head_health_and_ready_have_no_body(self):
        status, headers, body = self.request("HEAD", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Cache-Control"], "no-store")
        status2, headers2, body2 = self.request("HEAD", "/ready")
        self.assertEqual(status2, 200)
        self.assertEqual(body2, b"")
        self.assertEqual(headers2["Cache-Control"], "no-store")

    def test_base_path_without_trailing_slash_redirects(self):
        renyy.APP_BASE_PATH = "/renyy"
        status, headers, body = self.request("GET", "/renyy")
        self.assertEqual(status, 308)
        self.assertEqual(headers["Location"], "/renyy/")
        self.assertEqual(body, b"")

    def test_head_respects_base_path(self):
        renyy.APP_BASE_PATH = "/renyy"
        status, _, body = self.request("HEAD", "/renyy/embed")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        status2, _, _ = self.request("HEAD", "/embed")
        self.assertEqual(status2, 404)

    def test_security_and_request_id_headers_present(self):
        status, headers, _ = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
        csp = headers.get("Content-Security-Policy", "")
        self.assertIn("script-src 'self'", csp)
        self.assertIn("style-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertRegex(headers.get("X-Request-ID", ""), r"^[A-Za-z0-9._-]+$")

    def test_valid_supplied_request_id_is_echoed_from_trusted_proxy(self):
        renyy.TRUSTED_PROXY_NETWORKS = [renyy.ipaddress.ip_network("127.0.0.0/8")]
        _, headers, _ = self.request("GET", "/health", headers={"X-Request-ID": "proxy-123"})
        self.assertEqual(headers["X-Request-ID"], "proxy-123")

    def test_supplied_request_id_is_ignored_from_untrusted_client(self):
        _, headers, _ = self.request("GET", "/health", headers={"X-Request-ID": "proxy-123"})
        self.assertNotEqual(headers["X-Request-ID"], "proxy-123")

    def test_non_object_request_json_is_400(self):
        payload = b"[]"
        status, _, body = self.request(
            "POST", "/api/v1/renyyt", body=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body.decode("utf-8"))["code"], "INVALID_REQUEST")


    def test_static_assets_have_validators_and_no_cache(self):
        for path, expected_type, expected_body in (
            ("/styles.css", "text/css", self.styles.read_bytes()),
            ("/i18n.js", "text/javascript", self.i18n_js.read_bytes()),
            ("/helpers.js", "text/javascript", self.helpers_js.read_bytes()),
            ("/app.js", "text/javascript", self.app_js.read_bytes()),
        ):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertTrue(headers["Content-Type"].startswith(expected_type))
            self.assertEqual(headers["Cache-Control"], "no-cache")
            self.assertIn("ETag", headers)
            self.assertEqual(body, expected_body)
            status2, _, body2 = self.request("GET", path, headers={"If-None-Match": headers["ETag"]})
            self.assertEqual(status2, 304)
            self.assertEqual(body2, b"")

    def test_version_endpoint(self):
        with mock.patch.object(renyy, "APP_VERSION", "1.2.3"), \
             mock.patch.object(renyy, "BUILD_TIME", "2026-10-01T20:00:00Z"), \
             mock.patch.object(renyy, "GIT_COMMIT", "abc123"):
            status, headers, body = self.request("GET", "/version")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-cache")
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["version"], "1.2.3")
        self.assertEqual(data["gitCommit"], "abc123")

    def test_metrics_endpoint_and_api_counters(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        with mock.patch.object(renyy, "fetch_services", return_value=([], ["01-0000633-00"])):
            status, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers={
                "Content-Type": "application/json", "Content-Length": str(len(payload)),
                "Host": "%s:%s" % (self.host, self.port),
            })
        self.assertEqual(status, 200)
        mstatus, headers, body = self.request("GET", "/metrics")
        text = body.decode("utf-8")
        self.assertEqual(mstatus, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("renyyt_api_requests_total 1", text)
        self.assertIn("renyyt_api_success_total 1", text)
        self.assertIn("renyyt_http_requests_total", text)

    def test_cross_origin_api_request_is_rejected(self):
        payload = b'{}'
        status, _, body = self.request("POST", "/api/v1/renyyt", body=payload, headers={
            "Content-Type": "application/json", "Content-Length": str(len(payload)),
            "Host": "renyyt.example.test", "Origin": "https://evil.example.test",
        })
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body.decode("utf-8"))["code"], "ORIGIN_NOT_ALLOWED")

    def test_same_host_origin_is_allowed(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        with mock.patch.object(renyy, "fetch_services", return_value=([], ["01-0000633-00"])):
            status, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers={
                "Content-Type": "application/json", "Content-Length": str(len(payload)),
                "Host": "renyyt.example.test", "Origin": "http://renyyt.example.test",
            })
        self.assertEqual(status, 200)

    def test_configured_origin_and_host_rules(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        renyy.ALLOWED_ORIGINS = ["https://portal.example.test"]
        renyy.ALLOWED_HOSTS = ["backend.internal"]
        with mock.patch.object(renyy, "fetch_services", return_value=([], ["01-0000633-00"])):
            ok, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers={
                "Content-Type": "application/json", "Content-Length": str(len(payload)),
                "Host": "backend.internal", "Origin": "https://portal.example.test",
            })
        self.assertEqual(ok, 200)
        bad, _, body = self.request("POST", "/api/v1/renyyt", body=payload, headers={
            "Content-Type": "application/json", "Content-Length": str(len(payload)),
            "Host": "other.internal", "Origin": "https://portal.example.test",
        })
        self.assertEqual(bad, 403)
        self.assertEqual(json.loads(body.decode("utf-8"))["code"], "HOST_NOT_ALLOWED")

    def test_ready_checks_frontend_assets(self):
        self.styles.unlink()
        status, _, body = self.request("GET", "/ready")
        self.assertEqual(status, 503)
        data = json.loads(body.decode("utf-8"))
        self.assertFalse(data["checks"]["styles"])


    def test_openmetrics_endpoint_and_accept_negotiation(self):
        status, headers, body = self.request("GET", "/metrics/openmetrics")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/openmetrics-text; version=1.0.0"))
        self.assertTrue(body.decode("utf-8").endswith("# EOF\n"))

        status2, headers2, body2 = self.request("GET", "/metrics", headers={"Accept": "application/openmetrics-text; version=1.0.0"})
        self.assertEqual(status2, 200)
        self.assertTrue(headers2["Content-Type"].startswith("application/openmetrics-text"))
        self.assertTrue(body2.decode("utf-8").endswith("# EOF\n"))

    def test_fingerprinted_asset_uses_immutable_cache(self):
        asset_dir = Path(self.tmp.name) / "assets"
        asset_dir.mkdir(exist_ok=True)
        asset = asset_dir / "app.abc123.js"
        asset.write_text("console.log('prod');\n", encoding="utf-8")
        old_root, old_assets_dir = renyy.DIST_ROOT, renyy.ASSETS_DIR
        try:
            renyy.DIST_ROOT = Path(self.tmp.name)
            renyy.ASSETS_DIR = asset_dir
            renyy.PRODUCTION_BUILD_AVAILABLE = True
            renyy.PRODUCTION_ASSETS = {"app.js": "assets/app.abc123.js"}
            status, headers, body = self.request("GET", "/assets/app.abc123.js")
            self.assertEqual(status, 200)
            self.assertEqual(headers["Cache-Control"], "public, max-age=31536000, immutable")
            self.assertEqual(body, asset.read_bytes())
        finally:
            renyy.DIST_ROOT, renyy.ASSETS_DIR = old_root, old_assets_dir

    def test_forwarded_host_is_used_only_from_trusted_proxy(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        headers = {
            "Content-Type": "application/json", "Content-Length": str(len(payload)),
            "Host": "backend.internal", "X-Forwarded-Host": "public.example", "X-Forwarded-Proto": "https", "Origin": "https://public.example",
        }
        with mock.patch.object(renyy, "fetch_services", return_value=([], ["01-0000633-00"])):
            status, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)
        self.assertEqual(status, 403)
        renyy.TRUSTED_PROXY_NETWORKS = [renyy.ipaddress.ip_network("127.0.0.0/8")]
        with mock.patch.object(renyy, "fetch_services", return_value=([], ["01-0000633-00"])):
            status2, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)
        self.assertEqual(status2, 200)

    def test_metrics_include_histogram_and_upstream_series(self):
        renyy.METRICS.record_api(0.2)
        renyy.METRICS.record_upstream("login", 0.05, "success")
        status, _, body = self.request("GET", "/metrics")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn('renyyt_api_request_duration_seconds_bucket{le="0.25"} 1', text)
        self.assertIn('renyyt_upstream_calls_total{stage="login",outcome="success"} 1', text)
        self.assertIn('renyyt_upstream_duration_seconds_sum{stage="login"}', text)



    def test_api_requires_json_content_type(self):
        body = b"{}"
        status, _, data = self.request(
            "POST", "/api/v1/renyyt", body=body,
            headers={"Content-Type": "text/plain", "Content-Length": str(len(body))},
        )
        self.assertEqual(status, 415)
        self.assertEqual(json.loads(data.decode("utf-8"))["code"], "UNSUPPORTED_MEDIA_TYPE")

    def test_api_rejects_oversized_body(self):
        renyy.MAX_REQUEST_BODY = 8
        body = b'{"username":"x"}'
        status, _, data = self.request(
            "POST", "/api/v1/renyyt", body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(data.decode("utf-8"))["code"], "REQUEST_TOO_LARGE")

    def test_unsupported_methods_return_405_and_allow(self):
        status, headers, body = self.request("PUT", "/api/v1/renyyt", body=b"")
        self.assertEqual(status, 405)
        self.assertEqual(headers.get("Allow"), "GET, HEAD, POST, OPTIONS")
        self.assertEqual(body, b"Method not allowed")

    def test_rate_limiter_blocks_after_auth_failures(self):
        payload = json.dumps({"username": "01-0000633-00", "password": "bad"}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
        auth_error = renyy.ApiError("AUTH_FAILED", "bad", 401)
        with mock.patch.object(renyy, "fetch_services", side_effect=auth_error):
            self.assertEqual(self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)[0], 401)
            self.assertEqual(self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)[0], 401)
            status, response_headers, data = self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)
        self.assertEqual(status, 429)
        self.assertIn("Retry-After", response_headers)
        self.assertEqual(json.loads(data.decode("utf-8"))["code"], "RATE_LIMITED")

    def test_rate_limit_uses_rightmost_untrusted_forwarded_ip(self):
        renyy.TRUSTED_PROXY_NETWORKS = [renyy.ipaddress.ip_network("127.0.0.1/32")]
        renyy.RATE_LIMITER = renyy.RateLimiter(2, 60, 120)
        payload = json.dumps({"username": "01-0000633-00", "password": "bad"}).encode("utf-8")
        base_headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
        auth_error = renyy.ApiError("AUTH_FAILED", "bad", 401)
        with mock.patch.object(renyy, "fetch_services", side_effect=auth_error):
            h1 = dict(base_headers, **{"X-Forwarded-For": "192.0.2.10, 198.51.100.25"})
            h2 = dict(base_headers, **{"X-Forwarded-For": "192.0.2.99, 198.51.100.25"})
            self.assertEqual(self.request("POST", "/api/v1/renyyt", body=payload, headers=h1)[0], 401)
            self.assertEqual(self.request("POST", "/api/v1/renyyt", body=payload, headers=h2)[0], 429)

    def test_metrics_include_readiness_response_bytes_rate_limit_and_upstream_last_success(self):
        renyy.METRICS.record_upstream("services", 0.25, "success")
        renyy.METRICS.record_rate_limited()
        self.request("GET", "/health")
        status, _, body = self.request("GET", "/metrics")
        self.assertEqual(status, 200)
        text = body.decode("utf-8")
        self.assertIn("renyyt_ready 1", text)
        self.assertIn("renyyt_http_response_bytes_total", text)
        self.assertIn("renyyt_http_response_bytes_count", text)
        self.assertIn("renyyt_process_start_unixtime", text)
        self.assertIn("renyyt_api_outcomes_total", text)
        self.assertIn("renyyt_rate_limit_cleanup_runs_total", text)
        self.assertIn("renyyt_rate_limited_total 1", text)
        self.assertIn('renyyt_upstream_last_success_unixtime{stage="services"}', text)
        self.assertIn("renyyt_http_request_duration_seconds_sum", text)
        self.assertIn("renyyt_rate_limit_tracked_clients", text)
        self.assertIn("renyyt_rate_limit_blocked_clients", text)
        self.assertIn("renyyt_upstream_schema_warnings_total", text)
        self.assertIn('renyyt_readiness_check{check="index"} 1', text)

    def test_rate_limiter_stats_report_blocked_and_tracked_clients(self):
        limiter = renyy.RateLimiter(2, 60, 120)
        limiter.record_failure("198.51.100.1", now=1000)
        stats = limiter.stats(now=1001)
        self.assertEqual(stats["tracked_clients"], 1)
        self.assertEqual(stats["blocked_clients"], 0)
        limiter.record_failure("198.51.100.1", now=1002)
        stats2 = limiter.stats(now=1003)
        self.assertEqual(stats2["blocked_clients"], 1)

    def test_rate_limiter_periodic_cleanup_prunes_expired_clients(self):
        limiter = renyy.RateLimiter(3, 10, 20, cleanup_interval=5)
        limiter.record_failure("198.51.100.1", now=100)
        self.assertEqual(limiter.stats(now=101)["tracked_clients"], 1)
        limiter.check("198.51.100.2", now=120)
        stats = limiter.stats(now=120)
        self.assertEqual(stats["tracked_clients"], 0)
        self.assertGreaterEqual(stats["cleanup_runs"], 1)
        self.assertGreaterEqual(stats["pruned_clients"], 1)

    def test_rate_limit_whitelist_bypasses_auth_failure_tracking(self):
        renyy.RATE_LIMIT_WHITELIST_NETWORKS = [renyy.ipaddress.ip_network("127.0.0.0/8")]
        renyy.RATE_LIMITER = renyy.RateLimiter(1, 60, 120)
        payload = json.dumps({"username": "01-0000633-00", "password": "bad"}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
        auth_error = renyy.ApiError("AUTH_FAILED", "bad", 401)
        with mock.patch.object(renyy, "fetch_services", side_effect=auth_error):
            self.assertEqual(self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)[0], 401)
            self.assertEqual(self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)[0], 401)
        self.assertEqual(renyy.RATE_LIMITER.stats()["tracked_clients"], 0)


    def test_service_worker_and_api_document_are_served(self):
        status, headers, body = self.request("GET", "/service-worker.js")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/javascript"))
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertIn(b"CACHE_NAME", body)
        status2, headers2, body2 = self.request("GET", "/API.md")
        self.assertEqual(status2, 200)
        self.assertTrue(headers2["Content-Type"].startswith("text/markdown"))
        self.assertIn(b"POST /api/v1/renyyt", body2)

        technical_status, technical_headers, technical_body = self.request("GET", "/TECHNICAL.md")
        self.assertEqual(technical_status, 200)
        self.assertIn("text/markdown", technical_headers.get("Content-Type", ""))
        self.assertIn(b"#", technical_body)

    def test_localized_guides_support_get_head_base_path_and_validators(self):
        for language in renyy.README_LANGUAGES:
            path = "/README.%s.md" % language
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(b"Synthetic localized guide", body)
            self.assertEqual(headers["Cache-Control"], "no-cache")
            self.assertEqual(self.request("GET", path, headers={"If-None-Match": headers["ETag"]})[0], 304)
            self.assertEqual(self.request("HEAD", path)[2], b"")
            self.assertEqual(self.request("OPTIONS", path)[0], 204)
        estonian = self.readme.parent / "README.et.md"
        compressed = estonian.with_name(estonian.name + ".gz")
        compressed.write_bytes(gzip.compress(estonian.read_bytes()))
        renyy.PRECOMPRESSED_STATIC = renyy.detect_precompressed_static()
        status, headers, body = self.request("GET", "/README.et.md", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(body), estonian.read_bytes())
        self.assertEqual(self.request("GET", "/README.secret.md")[0], 404)
        renyy.APP_BASE_PATH = "/renyyt"
        self.assertEqual(self.request("GET", "/renyyt/README.et.md")[0], 200)

    def test_readiness_detects_a_missing_localized_guide(self):
        path = self.readme.parent / "README.et.md"
        path.unlink()
        self.assertFalse(renyy.readiness_state()[1]["localizedReadmes"])
        self.assertEqual(self.request("GET", "/README.et.md")[0], 404)

    def test_changelog_is_served(self):
        old_changelog = renyy.CHANGELOG
        changelog = Path(self.tmp.name) / "CHANGELOG.md"
        changelog.write_text("# Changes\n", encoding="utf-8")
        renyy.CHANGELOG = changelog
        try:
            status, headers, body = self.request("GET", "/CHANGELOG.md")
            self.assertEqual(status, 200)
            self.assertEqual(headers["Cache-Control"], "no-cache")
            self.assertEqual(body, b"# Changes\n")
        finally:
            renyy.CHANGELOG = old_changelog


    def test_versioned_renyyt_api_route_works_and_legacy_route_is_removed(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        headers = {"Content-Type":"application/json","Content-Length":str(len(payload))}
        services = [{"ASTNextDate":"2026-10-02","ASTVali":"4","tariff":{"productgroup":"SEK"}}]
        with mock.patch.object(renyy, "fetch_services", return_value=(services, ["01-0000633-00"])):
            v1_status, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)
        legacy_status, _, _ = self.request("POST", "/api/renyy", body=payload, headers=headers)
        old_v1_status, _, _ = self.request("POST", "/api/v1/renyy", body=payload, headers=headers)
        self.assertEqual(v1_status, 200)
        self.assertEqual(legacy_status, 404)
        self.assertEqual(old_v1_status, 404)

    def test_version_endpoint_advertises_v1_api(self):
        status, _, body = self.request("GET", "/version")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["apiDefault"], "/api/v1/renyyt")
        self.assertIn("v1", data["apiVersions"])

    def test_options_supports_versioned_api(self):
        status, headers, body = self.request("OPTIONS", "/api/v1/renyyt")
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertEqual(headers.get("Allow"), "POST, OPTIONS")



    def test_malformed_json_is_400(self):
        body = b'{"username":'
        status, _, response = self.request("POST", "/api/v1/renyyt", body=body, headers={"Content-Type":"application/json", "Content-Length":str(len(body))})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(response.decode("utf-8"))["code"], "INVALID_REQUEST_JSON")

    def test_invalid_utf8_json_is_400(self):
        body = b'\xff\xfe'
        status, _, response = self.request("POST", "/api/v1/renyyt", body=body, headers={"Content-Type":"application/json", "Content-Length":str(len(body))})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(response.decode("utf-8"))["code"], "INVALID_REQUEST_JSON")

    def test_duplicate_content_length_is_rejected(self):
        response = self.raw_request(
            b"POST /api/v1/renyyt HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
        )
        self.assertIn(b" 400 ", response.split(b"\r\n", 1)[0])
        self.assertIn(b"INVALID_CONTENT_LENGTH", response)

    def test_truncated_request_body_is_rejected(self):
        response = self.raw_request(
            b"POST /api/v1/renyyt HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 100\r\nConnection: close\r\n\r\n{}"
        )
        self.assertIn(b" 400 ", response.split(b"\r\n", 1)[0])
        self.assertIn(b"INCOMPLETE_REQUEST_BODY", response)

    def test_chunked_transfer_encoding_is_rejected(self):
        response = self.raw_request(
            b"POST /api/v1/renyyt HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n2\r\n{}\r\n0\r\n\r\n"
        )
        self.assertIn(b" 400 ", response.split(b"\r\n", 1)[0])
        self.assertIn(b"UNSUPPORTED_TRANSFER_ENCODING", response)

    def test_malformed_request_line_is_rejected_by_http_server(self):
        response = self.raw_request(b"THIS IS NOT HTTP\r\n\r\n")
        self.assertTrue(b"400" in response or b"Bad request" in response)

    def test_oversized_header_line_is_rejected_by_http_server(self):
        response = self.raw_request(
            b"GET / HTTP/1.1\r\nHost: localhost\r\nX-Oversized: " + (b"x" * 70000) + b"\r\nConnection: close\r\n\r\n"
        )
        self.assertIn(b" 431 ", response.split(b"\r\n", 1)[0])

    def test_credentials_never_appear_in_error_logs(self):
        username = "01-SECRET-CUSTOMER-00"
        password = "super-secret-password"
        payload = json.dumps({"username": username, "password": password, "suffixes": []}).encode("utf-8")
        stderr = io.StringIO()
        old_level = renyy.LOG_LEVEL
        renyy.LOG_LEVEL = "DEBUG"
        try:
            with mock.patch.object(renyy, "fetch_services", side_effect=renyy.ApiError("UPSTREAM_CONNECTION_ERROR", username + " " + password, 502)), contextlib.redirect_stderr(stderr):
                status, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers={"Content-Type":"application/json", "Content-Length":str(len(payload))})
        finally:
            renyy.LOG_LEVEL = old_level
        self.assertEqual(status, 502)
        logs = stderr.getvalue()
        self.assertNotIn(username, logs)
        self.assertNotIn(password, logs)

    def test_api_memory_cache_serves_second_identical_request_without_upstream(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        headers = {"Content-Type":"application/json","Content-Length":str(len(payload))}
        services = [{"ASTNextDate":"2026-10-02","ASTVali":"4","tariff":{"productgroup":"SEK"}}]
        old_cache = renyy.RESPONSE_CACHE
        renyy.RESPONSE_CACHE = ResponseCache(2, 60, 1024 * 1024)
        try:
            with mock.patch.object(renyy, "fetch_services", return_value=(services, ["01-0000633-00"])) as upstream_fetch:
                status1, h1, body1 = self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)
                status2, h2, body2 = self.request("POST", "/api/v1/renyyt", body=payload, headers=headers)
            self.assertEqual((status1, status2), (200, 200))
            parsed1 = json.loads(body1.decode("utf-8"))
            parsed2 = json.loads(body2.decode("utf-8"))
            self.assertEqual(parsed1["services"], parsed2["services"])
            self.assertEqual(parsed1["upstreamFetchedAt"], parsed2["upstreamFetchedAt"])
            self.assertEqual(parsed1["dataSource"], "upstream")
            self.assertEqual(parsed2["dataSource"], "memory-cache")
            self.assertIsInstance(parsed1["upstreamAgeSeconds"], int)
            self.assertIsInstance(parsed2["upstreamAgeSeconds"], int)
            self.assertGreaterEqual(parsed2["upstreamAgeSeconds"], parsed1["upstreamAgeSeconds"])
            self.assertEqual(h1.get("X-Renyyt-Cache"), "MISS")
            self.assertEqual(h2.get("X-Renyyt-Cache"), "HIT")
            self.assertEqual(upstream_fetch.call_count, 1)
        finally:
            renyy.RESPONSE_CACHE = old_cache

    def test_api_memory_cache_coalesces_concurrent_identical_requests(self):
        payload = json.dumps({"username":"01-0000633-00","password":"secret","suffixes":[]}).encode("utf-8")
        headers = {"Content-Type":"application/json","Content-Length":str(len(payload))}
        services = [{"ASTNextDate":"2026-10-02","ASTVali":"4","tariff":{"productgroup":"SEK"}}]
        old_cache = renyy.RESPONSE_CACHE
        renyy.RESPONSE_CACHE = ResponseCache(20, 60, 1024 * 1024)
        calls = []
        calls_lock = threading.Lock()
        def slow_fetch(*args, **kwargs):
            with calls_lock:
                calls.append(1)
            time.sleep(0.15)
            return services, ["01-0000633-00"]
        results = []
        start = threading.Barrier(6)
        def client():
            start.wait()
            results.append(self.request("POST", "/api/v1/renyyt", body=payload, headers=headers))
        threads = [threading.Thread(target=client) for _ in range(5)]
        try:
            with mock.patch.object(renyy, "fetch_services", side_effect=slow_fetch):
                for thread in threads: thread.start()
                start.wait()
                for thread in threads: thread.join(3)
            self.assertEqual(len(results), 5)
            self.assertTrue(all(item[0] == 200 for item in results))
            self.assertEqual(len(calls), 1)
            cache_headers = [item[1].get("X-Renyyt-Cache") for item in results]
            self.assertEqual(cache_headers.count("MISS"), 1)
            self.assertEqual(cache_headers.count("HIT"), 4)
        finally:
            renyy.RESPONSE_CACHE = old_cache

    def test_fixture_file_bypasses_upstream_and_accepts_api_response_shape(self):
        fixture = Path(self.tmp.name) / "fixture.json"
        fixture.write_text(json.dumps({
            "services": [{"ASTNextDate":"2026-10-02","ASTVali":"4","tariff":{"productgroup":"FIXTURE"}}],
            "customerNumbers": ["fixture-customer"],
            "warnings": []
        }), encoding="utf-8")
        old_setting = renyy.FIXTURE_FILE_SETTING
        renyy.FIXTURE_FILE_SETTING = str(fixture)
        try:
            with mock.patch.object(renyy.upstream, "fetch_services", side_effect=AssertionError("upstream must not be called")):
                services, numbers = renyy.fetch_services("fake-user", "fake-password", [])
            self.assertEqual(services[0]["tariff"]["productgroup"], "FIXTURE")
            self.assertEqual(numbers, ["fixture-customer"])
        finally:
            renyy.FIXTURE_FILE_SETTING = old_setting

    def test_trace_logs_only_api_json_and_debug_hides_credentials(self):
        username = "01-TRACE-CUSTOMER-00"
        password = "trace-secret-password"
        payload = json.dumps({"username":username,"password":password,"suffixes":[]}).encode("utf-8")
        services = [{"ASTNextDate":"2026-10-02","ASTAsnro":"TRACE-CUSTOMER","tariff":{"productgroup":"SEK"}}]
        old_level = renyy.LOG_LEVEL
        stderr = io.StringIO()
        try:
            renyy.LOG_LEVEL = "TRACE"
            with mock.patch.object(renyy, "fetch_services", return_value=(services, [username])), contextlib.redirect_stderr(stderr):
                status, _, _ = self.request("POST", "/api/v1/renyyt", body=payload, headers={"Content-Type":"application/json","Content-Length":str(len(payload))})
        finally:
            renyy.LOG_LEVEL = old_level
        self.assertEqual(status, 200)
        logs = stderr.getvalue()
        self.assertIn("api_json_request_sensitive", logs)
        self.assertIn(username, logs)
        self.assertIn(password, logs)
        self.assertIn("api_json_response_sensitive", logs)
        self.assertNotIn("<html", logs.lower())
        self.assertNotIn("javascript", logs.lower())

    def test_features_reports_feedback_only_as_boolean(self):
        with mock.patch.dict(renyy.CONFIG, {"smtp_host":"smtp.example", "smtp_from":"from@example.com", "smtp_to":"to@example.com"}, clear=False):
            status, headers, body = self.request("GET", "/api/v1/features")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(body.decode("utf-8")), {"feedback": True, "pwa": True, "reminders": {"enabled": False, "vapidPublicKey": None}})
        self.assertNotIn(b"smtp.example", body)


    def test_reminder_features_and_sync_endpoint(self):
        from renyyt.reminders import ReminderStore
        old_enabled = renyy.REMINDERS_ENABLED
        old_key = renyy.VAPID_PUBLIC_KEY
        old_store = renyy.REMINDER_STORE
        try:
            renyy.REMINDERS_ENABLED = True
            renyy.VAPID_PUBLIC_KEY = "public-vapid-key"
            renyy.REMINDER_STORE = ReminderStore(Path(self.tmp.name) / "reminders.sqlite3")
            status, _, body = self.request("GET", "/api/v1/features")
            self.assertEqual(status, 200)
            features = json.loads(body.decode("utf-8"))
            self.assertEqual(features["reminders"], {"enabled": True, "vapidPublicKey": "public-vapid-key"})
            trigger = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)
            collection = trigger + timedelta(days=1)
            payload = json.dumps({
                "subscription": {"endpoint":"https://push.example/sub/abc", "keys":{"p256dh":"p256","auth":"auth"}},
                "locale": "fi",
                "reminders": [{"collectionDate":collection.date().isoformat(), "label":"Sekajäte", "triggerAt":trigger.isoformat()}],
            }).encode("utf-8")
            status, _, body = self.request("POST", "/api/v1/reminders/sync", body=payload, headers={"Content-Type":"application/json","Content-Length":str(len(payload))})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body.decode("utf-8"))["subscribed"])
            self.assertEqual(renyy.REMINDER_STORE.stats(), {"subscriptions":1,"pending":1})
            unsub = json.dumps({"subscription": {"endpoint":"https://push.example/sub/abc", "keys":{"p256dh":"p256","auth":"auth"}}}).encode("utf-8")
            status, _, _ = self.request("POST", "/api/v1/reminders/unsubscribe", body=unsub, headers={"Content-Type":"application/json","Content-Length":str(len(unsub))})
            self.assertEqual(status, 200)
            self.assertEqual(renyy.REMINDER_STORE.stats(), {"subscriptions":0,"pending":0})
        finally:
            renyy.REMINDERS_ENABLED = old_enabled
            renyy.VAPID_PUBLIC_KEY = old_key
            renyy.REMINDER_STORE = old_store

    def test_pwa_can_be_disabled_completely(self):
        old = renyy.PWA_ENABLED
        try:
            renyy.PWA_ENABLED = False
            status, _, body = self.request("GET", "/api/v1/features")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body.decode("utf-8"))["pwa"], False)
            status, _, body = self.request("GET", "/service-worker.js")
            self.assertEqual(status, 404)
            status, _, body = self.request("GET", "/brand/site.webmanifest")
            self.assertEqual(status, 404)
            status, _, body = self.request("GET", "/")
            self.assertEqual(status, 200)
            self.assertNotIn(b'rel="manifest"', body)
        finally:
            renyy.PWA_ENABLED = old

    def test_feedback_endpoint_sends_only_feedback_fields_and_server_metadata(self):
        payload = json.dumps({"message":"Hello", "email":"reply@example.com"}).encode("utf-8")
        config_patch = {"smtp_host":"smtp.example", "smtp_from":"from@example.com", "smtp_to":"to@example.com"}
        old_limiter = renyy.FEEDBACK_LIMITER
        renyy.FEEDBACK_LIMITER = renyy.FeedbackRateLimiter(5, 600)
        try:
            with mock.patch.dict(renyy.CONFIG, config_patch, clear=False), mock.patch.object(renyy, "send_feedback") as sender:
                status, _, body = self.request("POST", "/api/v1/feedback", body=payload, headers={"Content-Type":"application/json", "Content-Length":str(len(payload)), "User-Agent":"Test Browser"})
        finally:
            renyy.FEEDBACK_LIMITER = old_limiter
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8")), {"ok": True})
        args, kwargs = sender.call_args
        self.assertEqual(args[1], "Hello")
        self.assertEqual(kwargs["reply_to"], "reply@example.com")
        self.assertEqual(kwargs["metadata"]["version"], renyy.APP_VERSION)
        self.assertEqual(kwargs["metadata"]["user_agent"], "Test Browser")

    def test_feedback_can_attach_collection_json_with_explicit_payload(self):
        payload = json.dumps({"message":"UI issue", "email":"", "collectionData":{"services":[{"ASTAsnro":"123","ASTNextDate":"2026-10-10"}],"warnings":[]}}).encode("utf-8")
        config_patch = {"smtp_host":"smtp.example", "smtp_from":"from@example.com", "smtp_to":"to@example.com"}
        old_limiter = renyy.FEEDBACK_LIMITER
        renyy.FEEDBACK_LIMITER = renyy.FeedbackRateLimiter(5, 600)
        try:
            with mock.patch.dict(renyy.CONFIG, config_patch, clear=False), mock.patch.object(renyy, "send_feedback") as sender:
                status, _, body = self.request("POST", "/api/v1/feedback", body=payload, headers={"Content-Type":"application/json", "Content-Length":str(len(payload))})
        finally:
            renyy.FEEDBACK_LIMITER = old_limiter
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8")), {"ok": True})
        collection_json = sender.call_args.kwargs["collection_json"]
        self.assertIsInstance(collection_json, bytes)
        attached = json.loads(collection_json.decode("utf-8"))
        self.assertEqual(attached["services"][0]["ASTAsnro"], "123")

    def test_feedback_rejects_collection_json_over_limit(self):
        with self.assertRaises(ValueError):
            validate_feedback_payload({"message":"x", "collectionData":{"blob":"x" * 200}}, max_collection_data_bytes=32)

    def test_feedback_smtp_timeout_is_504_not_client_408(self):
        payload = json.dumps({"message":"Hello", "email":""}).encode("utf-8")
        config_patch = {"smtp_host":"smtp.example", "smtp_from":"from@example.com", "smtp_to":"to@example.com"}
        old_limiter = renyy.FEEDBACK_LIMITER
        renyy.FEEDBACK_LIMITER = renyy.FeedbackRateLimiter(5, 600)
        try:
            with mock.patch.dict(renyy.CONFIG, config_patch, clear=False), mock.patch.object(renyy, "send_feedback", side_effect=socket.timeout("smtp timeout")):
                status, _, body = self.request("POST", "/api/v1/feedback", body=payload, headers={"Content-Type":"application/json", "Content-Length":str(len(payload))})
        finally:
            renyy.FEEDBACK_LIMITER = old_limiter
        self.assertEqual(status, 504)
        self.assertEqual(json.loads(body.decode("utf-8"))["code"], "FEEDBACK_SMTP_TIMEOUT")

    def test_feedback_debug_log_does_not_include_message_or_reply_address(self):
        payload = json.dumps({"message":"SECRET FEEDBACK BODY", "email":"secret-reply@example.com"}).encode("utf-8")
        config_patch = {"smtp_host":"smtp.example", "smtp_port":587, "smtp_from":"from@example.com", "smtp_to":"to@example.com"}
        old_limiter = renyy.FEEDBACK_LIMITER
        old_level = renyy.LOG_LEVEL
        renyy.FEEDBACK_LIMITER = renyy.FeedbackRateLimiter(5, 600)
        renyy.LOG_LEVEL = "DEBUG"
        stderr = io.StringIO()
        def fake_send(config, message, reply_to="", metadata=None, collection_json=None, debug=None, sensitive_trace=None):
            debug("connect_start", host="smtp.example", port=587, transport="starttls", timeout=10, auth=True)
            debug("send_complete", elapsed_ms=12)
        try:
            with mock.patch.dict(renyy.CONFIG, config_patch, clear=False), mock.patch.object(renyy, "send_feedback", side_effect=fake_send), contextlib.redirect_stderr(stderr):
                status, _, _ = self.request("POST", "/api/v1/feedback", body=payload, headers={"Content-Type":"application/json", "Content-Length":str(len(payload))})
        finally:
            renyy.FEEDBACK_LIMITER = old_limiter
            renyy.LOG_LEVEL = old_level
        self.assertEqual(status, 200)
        logs = stderr.getvalue()
        self.assertIn("event=feedback_smtp", logs)
        self.assertNotIn("SECRET FEEDBACK BODY", logs)
        self.assertNotIn("secret-reply@example.com", logs)

    def test_feedback_is_hidden_when_smtp_is_not_configured(self):
        with mock.patch.dict(renyy.CONFIG, {"smtp_host":"", "smtp_from":"", "smtp_to":""}, clear=False):
            status, _, body = self.request("GET", "/api/v1/features")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8")), {"feedback": False, "pwa": True, "reminders": {"enabled": False, "vapidPublicKey": None}})


class ProductionBuildValidationTestCase(unittest.TestCase):
    def test_manifest_integrity_detects_valid_and_tampered_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            web = root / "web"; dist = root / "dist"; assets_dir = dist / "assets"; brand_src = web / "assets" / "brand"; brand_dist = dist / "brand"
            web.mkdir(); dist.mkdir(); assets_dir.mkdir(); brand_src.mkdir(parents=True); brand_dist.mkdir()
            sources = {
                "index.html": '<link href="styles.css"><script src="i18n.js"></script><script src="helpers.js"></script><script src="app.js"></script>',
                "styles.css": "body{}",
                "i18n.js": "window.i18n=1;",
                "helpers.js": "window.x=1;",
                "app.js": "console.log(1);",
                "service-worker.js": "self.addEventListener('fetch',()=>{});",
            }
            for name, content in sources.items():
                (web / name).write_text(content, encoding="utf-8")
            mapping = {}
            for name in ("styles.css", "i18n.js", "helpers.js", "app.js"):
                data = (web / name).read_bytes()
                src = Path(name)
                out_name = "%s.%s%s" % (src.stem, hashlib.sha256(data).hexdigest()[:12], src.suffix)
                (assets_dir / out_name).write_bytes(data)
                mapping[name] = "assets/" + out_name
            html = sources["index.html"]
            for source, built in mapping.items():
                html = html.replace('href="%s"' % source, 'href="%s"' % built)
                html = html.replace('src="%s"' % source, 'src="%s"' % built)
            prod_index = dist / "index.html"; prod_index.write_text(html, encoding="utf-8")
            prod_sw = dist / "service-worker.js"; prod_sw.write_bytes((web / "service-worker.js").read_bytes())
            brand_names = ("logo.svg", "favicon.svg", "favicon.ico", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "maskable-192.png", "maskable-512.png", "site.webmanifest")
            brand = {}
            for name in brand_names:
                data = ("brand:" + name).encode("utf-8")
                (brand_src / name).write_bytes(data)
                (brand_dist / name).write_bytes(data)
                brand[name] = hashlib.sha256(data).hexdigest()
            manifest = dist / "asset-manifest.json"
            manifest.write_text(json.dumps({"manifestVersion":1,"assets":mapping,"brand":brand,"serviceWorker":hashlib.sha256(prod_sw.read_bytes()).hexdigest()}), encoding="utf-8")
            old = time.time() - 10
            for name in sources:
                os.utime(str(web / name), (old, old))
            now = time.time()
            os.utime(str(prod_index), (now, now)); os.utime(str(manifest), (now, now))
            with mock.patch.multiple(
                renyy,
                ASSET_MANIFEST=manifest, PROD_INDEX=prod_index, ASSETS_DIR=assets_dir, DIST_ROOT=dist,
                BRAND_SOURCE_DIR=brand_src, BRAND_DIST_DIR=brand_dist,
                INDEX=web / "index.html", STYLES=web / "styles.css", I18N_JS=web / "i18n.js", HELPERS_JS=web / "helpers.js", APP_JS=web / "app.js", SOURCE_SERVICE_WORKER=web / "service-worker.js", PROD_SERVICE_WORKER=prod_sw,
            ):
                available, assets, status = renyy.detect_production_build()
                self.assertTrue(available); self.assertEqual(status, "valid"); self.assertEqual(assets, mapping)
                (assets_dir / Path(mapping["app.js"]).name).write_text("tampered", encoding="utf-8")
                available2, _, status2 = renyy.detect_production_build()
                self.assertFalse(available2); self.assertEqual(status2, "asset_hash_mismatch")


class OptionsAndPortTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "index.html").write_text("<html></html>", encoding="utf-8")
        self.old = (renyy.INDEX, renyy.ACTIVE_INDEX, renyy.INDEX_PLAIN_AVAILABLE, renyy.INDEX_GZIP_AVAILABLE, renyy.APP_BASE_PATH)
        renyy.INDEX = root / "index.html"
        renyy.ACTIVE_INDEX = renyy.INDEX
        renyy.INDEX_PLAIN_AVAILABLE = True
        renyy.INDEX_GZIP_AVAILABLE = False
        renyy.APP_BASE_PATH = ""
        self.httpd = renyy.ThreadingHTTPServer(("127.0.0.1", 0), renyy.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.httpd.server_address

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close(); self.thread.join(timeout=2)
        renyy.INDEX, renyy.ACTIVE_INDEX, renyy.INDEX_PLAIN_AVAILABLE, renyy.INDEX_GZIP_AVAILABLE, renyy.APP_BASE_PATH = self.old
        self.tmp.cleanup()

    def request(self, method, path):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=3)
        conn.request(method, path)
        resp = conn.getresponse(); body = resp.read(); headers = dict(resp.getheaders()); status = resp.status; conn.close()
        return status, headers, body

    def test_options_reports_allowed_methods_without_cors(self):
        status, headers, body = self.request("OPTIONS", "/")
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Allow"), "GET, HEAD, OPTIONS")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(body, b"")
        status, headers, body = self.request("OPTIONS", "/api/v1/renyyt")
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Allow"), "POST, OPTIONS")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(body, b"")
        self.assertEqual(self.request("OPTIONS", "/does-not-exist")[0], 404)

    def test_port_environment_fallback(self):
        with mock.patch.dict(os.environ, {"PORT": "9090"}, clear=False):
            with mock.patch.dict(os.environ, {"RENYYT_PORT": ""}, clear=False):
                os.environ.pop("RENYYT_PORT", None)
                cfg = renyy.load_config()
                self.assertEqual(cfg["port"], 9090)
        with mock.patch.dict(os.environ, {"PORT": "9090", "RENYYT_PORT": "9191"}, clear=False):
            cfg = renyy.load_config()
            self.assertEqual(cfg["port"], 9191)


class ConfigTestCase(unittest.TestCase):
    def test_default_upstream_timeouts(self):
        keys = ["RENYYT_SESSION_TIMEOUT", "RENYYT_LOGIN_TIMEOUT", "RENYYT_SERVICES_TIMEOUT"]
        clean = {k: os.environ.get(k) for k in keys}
        try:
            for key in keys:
                os.environ.pop(key, None)
            cfg = renyy.load_config()
        finally:
            for key, value in clean.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.assertEqual(cfg["session_timeout"], 10.0)
        self.assertEqual(cfg["login_timeout"], 15.0)
        self.assertEqual(cfg["services_timeout"], 20.0)

    def test_config_reads_documented_environment(self):
        with mock.patch.dict(os.environ, {
            "RENYYT_HOST": "0.0.0.0",
            "RENYYT_PORT": "9000",
            "RENYYT_BASE_PATH": "/foo/",
            "RENYYT_SESSION_TIMEOUT": "1.5",
            "RENYYT_LOGIN_TIMEOUT": "2",
            "RENYYT_SERVICES_TIMEOUT": "3",
            "RENYYT_LOG_LEVEL": "warning",
            "RENYYT_LOG_FORMAT": "json",
            "RENYYT_VERSION": "2.0.0",
            "RENYYT_BUILD_TIME": "2026-10-01T20:00:00Z",
            "RENYYT_GIT_COMMIT": "abc123",
            "RENYYT_ALLOWED_ORIGINS": "https://one.example,https://two.example",
            "RENYYT_ALLOWED_HOSTS": "one.example,two.example",
            "RENYYT_TRUSTED_PROXIES": "127.0.0.1,10.0.0.0/8",
            "RENYYT_MAX_REQUEST_BODY": "32768",
            "RENYYT_CLIENT_SOCKET_TIMEOUT": "12",
            "RENYYT_RATE_LIMIT_ATTEMPTS": "5",
            "RENYYT_RATE_LIMIT_WINDOW": "120",
            "RENYYT_RATE_LIMIT_BLOCK": "240",
            "RENYYT_RATE_LIMIT_CLEANUP_INTERVAL": "30",
            "RENYYT_RATE_LIMIT_WHITELIST": "127.0.0.1,10.10.0.0/16",
        }, clear=False):
            cfg = renyy.load_config()
        self.assertEqual(cfg["host"], "0.0.0.0")
        self.assertEqual(cfg["port"], 9000)
        self.assertEqual(cfg["base_path"], "/foo")
        self.assertEqual(cfg["session_timeout"], 1.5)
        self.assertEqual(cfg["log_level"], "WARNING")
        self.assertEqual(cfg["log_format"], "json")
        self.assertEqual(cfg["version"], "2.0.0")
        self.assertEqual(cfg["git_commit"], "abc123")
        self.assertEqual(cfg["allowed_origins"], ["https://one.example", "https://two.example"])
        self.assertEqual(cfg["allowed_hosts"], ["one.example", "two.example"])
        self.assertEqual(cfg["trusted_proxies"], ["127.0.0.1", "10.0.0.0/8"])
        self.assertEqual(cfg["max_request_body"], 32768)
        self.assertEqual(cfg["client_socket_timeout"], 12.0)
        self.assertEqual(cfg["rate_limit_attempts"], 5)
        self.assertEqual(cfg["rate_limit_window"], 120.0)
        self.assertEqual(cfg["rate_limit_block"], 240.0)
        self.assertEqual(cfg["rate_limit_cleanup_interval"], 30.0)
        self.assertEqual(cfg["rate_limit_whitelist"], ["127.0.0.1", "10.10.0.0/16"])

    def test_invalid_config_fails_fast(self):
        with mock.patch.dict(os.environ, {"RENYYT_PORT": "70000"}, clear=False):
            with self.assertRaises(renyy.ConfigError):
                renyy.load_config()
        with mock.patch.dict(os.environ, {"RENYYT_LOG_LEVEL": "LOUD"}, clear=False):
            with self.assertRaises(renyy.ConfigError):
                renyy.load_config()
        with mock.patch.dict(os.environ, {"RENYYT_LOG_FORMAT": "xml"}, clear=False):
            with self.assertRaises(renyy.ConfigError):
                renyy.load_config()
        with self.assertRaises(renyy.ConfigError):
            renyy.parse_trusted_proxies(["not-an-ip"])
        with self.assertRaises(renyy.ConfigError):
            renyy.parse_ip_networks(["not-an-ip"], "RENYYT_RATE_LIMIT_WHITELIST")
        with mock.patch.dict(os.environ, {"RENYYT_MAX_REQUEST_BODY": "100"}, clear=False):
            with self.assertRaises(renyy.ConfigError):
                renyy.load_config()

    def test_sigterm_handler_requests_shutdown(self):
        with self.assertRaises(renyy.ShutdownRequested):
            renyy._sigterm_handler(None, None)



class UpstreamTestCase(unittest.TestCase):
    def _fetch_with(self, items):
        opener = FakeOpener(items)
        with mock.patch.object(renyy.upstream, "build_opener", return_value=opener):
            result = renyy.fetch_services("01-0000633-00", "secret", [])
        return result, opener

    def _success_items(self, services):
        return [
            FakeResponse(b"session"),
            FakeResponse(b"ok", url="https://extranet.pjhoy.fi/pirkka/secure/front.do"),
            FakeResponse(json.dumps(services).encode("utf-8"), "application/json; charset=utf-8"),
        ]

    def test_auth_failed(self):
        items = [
            FakeResponse(b"session"),
            FakeResponse(b"bad", url="https://extranet.pjhoy.fi/pirkka/login_error"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "wrong", [])
        self.assertEqual(ctx.exception.code, "AUTH_FAILED")
        self.assertEqual(ctx.exception.status, 401)

    def test_auth_failed_when_login_form_is_returned_without_login_error_url(self):
        login_html = b'<form action="j_acegi_security_check"><input name="j_username"><input name="j_password"></form>'
        items = [
            FakeResponse(b"session"),
            FakeResponse(login_html, "text/html", url="https://extranet.pjhoy.fi/pirkka/"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "wrong", [])
        self.assertEqual(ctx.exception.code, "AUTH_FAILED")
        self.assertEqual(ctx.exception.status, 401)

    def test_login_redirect_outside_expected_upstream_is_rejected(self):
        items = [
            FakeResponse(b"session"),
            FakeResponse(b"ok", "text/html", url="https://example.invalid/secure/front.do"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_UNEXPECTED_REDIRECT")
        self.assertEqual(ctx.exception.status, 502)

    def test_services_redirect_back_to_login_is_reported_as_session_failure(self):
        items = [
            FakeResponse(b"session"),
            FakeResponse(b"ok", url="https://extranet.pjhoy.fi/pirkka/secure/front.do"),
            FakeResponse(b'<form><input name="j_username"><input name="j_password"></form>', "text/html", url="https://extranet.pjhoy.fi/pirkka/login.do"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "AUTH_SESSION_FAILED")
        self.assertEqual(ctx.exception.status, 502)

    def test_services_redirect_outside_expected_upstream_is_rejected(self):
        items = [
            FakeResponse(b"session"),
            FakeResponse(b"ok", url="https://extranet.pjhoy.fi/pirkka/secure/front.do"),
            FakeResponse(b"[]", "application/json", url="https://example.invalid/data.json"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_UNEXPECTED_REDIRECT")
        self.assertEqual(ctx.exception.status, 502)

    def test_timeout(self):
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener([socket.timeout()])):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_TIMEOUT")
        self.assertEqual(ctx.exception.status, 504)

    def test_urlerror_timeout(self):
        err = URLError(socket.timeout())
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener([err])):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_TIMEOUT")

    def test_upstream_http_500(self):
        err = HTTPError("https://example.invalid", 500, "boom", {}, None)
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener([err])):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_HTTP_ERROR")
        self.assertEqual(ctx.exception.upstream_status, 500)

    def test_invalid_json(self):
        items = [
            FakeResponse(b"session"),
            FakeResponse(b"ok", url="https://extranet.pjhoy.fi/pirkka/secure/front.do"),
            FakeResponse(b"{not json", "application/json"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_INVALID_JSON")

    def test_non_json_upstream_response(self):
        items = [
            FakeResponse(b"session"),
            FakeResponse(b"ok", url="https://extranet.pjhoy.fi/pirkka/secure/front.do"),
            FakeResponse(b"<html>maintenance</html>", "text/html"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_INVALID_RESPONSE")

    def test_mislabeled_html_is_never_trace_logged_as_json(self):
        trace_events = []
        html = b"<html><script>window.secret='not-json'</script></html>"
        items = [
            FakeResponse(b"session"),
            FakeResponse(b"ok", url="https://extranet.pjhoy.fi/pirkka/secure/front.do"),
            FakeResponse(html, "application/json; charset=utf-8"),
        ]
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener(items)):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services(
                    "01-0000633-00", "secret", [],
                    trace=lambda phase, **fields: trace_events.append((phase, fields)),
                )
        self.assertEqual(ctx.exception.code, "UPSTREAM_INVALID_JSON")
        self.assertEqual(trace_events, [])

    def test_connection_error(self):
        err = URLError(OSError("network unreachable"))
        with mock.patch.object(renyy.upstream, "build_opener", return_value=FakeOpener([err])):
            with self.assertRaises(renyy.ApiError) as ctx:
                renyy.fetch_services("01-0000633-00", "secret", [])
        self.assertEqual(ctx.exception.code, "UPSTREAM_CONNECTION_ERROR")

    def test_upstream_debug_is_safe_and_trace_contains_sensitive_diagnostics(self):
        debug_events = []
        trace_events = []
        services = [{"ASTNextDate":"2026-10-19","ASTAsnro":"SECRET-CUSTOMER","tariff":{"productgroup":"SEK"}}]
        opener = FakeOpener(self._success_items(services))
        with mock.patch.object(renyy.upstream, "build_opener", return_value=opener):
            renyy.fetch_services(
                "01-SECRET-CUSTOMER-00", "super-secret-password", [],
                debug=lambda phase, **fields: debug_events.append((phase, fields)),
                trace=lambda phase, **fields: trace_events.append((phase, fields)),
            )
        safe_text = repr(debug_events)
        sensitive_text = repr(trace_events)
        self.assertNotIn("01-SECRET-CUSTOMER-00", safe_text)
        self.assertNotIn("super-secret-password", safe_text)
        self.assertNotIn("SECRET-CUSTOMER", safe_text)
        self.assertNotIn("01-SECRET-CUSTOMER-00", sensitive_text)
        self.assertNotIn("super-secret-password", sensitive_text)
        self.assertIn("SECRET-CUSTOMER", sensitive_text)
        self.assertIn("services_response", safe_text)
        self.assertIn("services_json_response", sensitive_text)
        self.assertNotIn("session", sensitive_text)
        self.assertNotIn("login", sensitive_text)

    def test_empty_service_list_is_valid(self):
        (services, numbers), _ = self._fetch_with(self._success_items([]))
        self.assertEqual(services, [])
        self.assertEqual(numbers, ["01-0000633-00"])

    def test_service_without_next_date_is_valid(self):
        data = [{"ASTNimi": "JÄTEASTIA 660 L", "ASTVali": "4", "tariff": {"productgroup": "SEK"}}]
        warnings = renyy.validate_services_payload(data)
        self.assertEqual(warnings, [])

    def test_seasonal_interval_is_valid(self):
        data = [{
            "ASTNextDate": "2026-10-19",
            "ASTVali": "2",
            "ASTVali2": "4",
            "ASTVoim1": "18",
            "ASTVoim2": "40",
            "ASTVoim21": "41",
            "ASTVoim22": "17",
            "tariff": {"productgroup": "BIO"},
        }]
        self.assertEqual(renyy.validate_services_payload(data), [])

    def test_kimppa_without_kirpros_is_valid(self):
        data = [{
            "ASTNextDate": "2026-10-19",
            "ASTVali": "2",
            "kimppa": {"KIMNimi1": "KIMPPA TESTI"},
            "tariff": {"productgroup": "BIO"},
        }]
        self.assertEqual(renyy.validate_services_payload(data), [])

    def test_schema_rejects_wrong_top_level(self):
        with self.assertRaises(renyy.ApiError) as ctx:
            renyy.validate_services_payload({"services": []})
        self.assertEqual(ctx.exception.code, "UPSTREAM_SCHEMA_ERROR")

    def test_schema_bad_date_becomes_service_warning(self):
        warnings = renyy.validate_services_payload([{"ASTNextDate": "2026-99-99"}])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["code"], "INVALID_DATE")
        self.assertEqual(warnings[0]["field"], "ASTNextDate")

    def test_schema_accepts_unknown_fields_without_warning(self):
        data = [{"ASTNextDate":"2026-10-19", "futureRenyyField":{"nested": [1, 2, 3]}}]
        self.assertEqual(renyy.validate_services_payload(data), [])

    def test_schema_non_object_service_becomes_warning(self):
        warnings = renyy.validate_services_payload(["unexpected", {"ASTNextDate": "2026-10-19"}])
        self.assertEqual(warnings[0]["code"], "SERVICE_NOT_OBJECT")


class VersioningAndDiagnosticsTest(unittest.TestCase):
    def test_unknown_field_diagnostics_report_only_path_and_type(self):
        data = [{
            "ASTNextDate": "2026-10-19",
            "futureRenyyField": {"secret": "must-not-appear"},
            "tariff": {"productgroup": "BIO", "futureTariffField": 123},
            "kimppa": {"KIMNimi1": "KIMPPA", "futureKimppaField": [1, 2]},
        }]
        diagnostics = renyy.collect_unknown_fields(data)
        self.assertIn({"field": "futureRenyyField", "type": "object"}, diagnostics)
        self.assertIn({"field": "tariff.futureTariffField", "type": "number"}, diagnostics)
        self.assertIn({"field": "kimppa.futureKimppaField", "type": "array"}, diagnostics)
        self.assertNotIn("must-not-appear", json.dumps(diagnostics))

    def test_metrics_exposes_unknown_field_counter(self):
        metrics = renyy.Metrics(readiness=lambda: (True, {}), rate_stats=lambda: {})
        metrics.record_unknown_fields(2)
        rendered = metrics.render().decode("utf-8")
        self.assertIn("renyyt_upstream_unknown_fields_total 2", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
