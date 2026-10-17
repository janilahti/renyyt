import json
import socket
import time
from http.cookiejar import CookieJar
from typing import List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, Request

from .errors import ApiError
from .validation import validate_services_payload


UPSTREAM_BASE = "https://extranet.pjhoy.fi/pirkka/"


def _is_expected_upstream_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return (
        parsed.scheme.lower() == "https"
        and parsed.netloc.lower() == "extranet.pjhoy.fi"
        and parsed.path.startswith("/pirkka/")
    )


def _looks_like_login_page(url: str, body: str) -> bool:
    lowered_url = (url or "").lower()
    if "login_error" in lowered_url or "j_acegi_security_check" in lowered_url:
        return True
    lowered_body = (body or "").lower()
    markers = ("j_username", "j_password", "j_acegi_security_check")
    return sum(marker in lowered_body for marker in markers) >= 2


def _login_target_kind(url: str) -> str:
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return "invalid"
    if "/pirkka/secure/" in path:
        return "secure"
    if "login" in path or "j_acegi_security_check" in path:
        return "login"
    return "other"


def fetch_services(username: str, password: str, suffixes: List[str], session_timeout, login_timeout, services_timeout, metrics=None, debug=None, trace=None):
    def record(stage, started, outcome="success"):
        if metrics is not None:
            metrics.record_upstream(stage, time.monotonic() - started, outcome)

    def safe_debug(phase, **fields):
        if debug:
            debug(phase, **fields)

    def sensitive_trace(phase, **fields):
        if trace:
            trace(phase, **fields)

    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "Renyyt/1.0")]
    try:
        started = time.monotonic()
        safe_debug("session_request", method="GET", endpoint="session", timeout=session_timeout)
        try:
            session = opener.open(UPSTREAM_BASE, timeout=session_timeout)
            session_status = getattr(session, "status", None) or session.getcode()
            session_type = session.headers.get("Content-Type", "")
            session_raw = session.read().decode("utf-8", errors="replace")
        except Exception:
            record("session", started, "error")
            raise
        else:
            elapsed = int((time.monotonic() - started) * 1000)
            record("session", started)
            safe_debug("session_response", status=session_status, content_type=session_type, bytes=len(session_raw.encode("utf-8")), elapsed_ms=elapsed)

        body_text = urlencode({"j_username": username, "j_password": password, "remember-me": "false"})
        body = body_text.encode("utf-8")
        login_url = UPSTREAM_BASE + "j_acegi_security_check?target=2"
        req = Request(login_url, data=body, method="POST")
        started = time.monotonic()
        safe_debug("login_request", method="POST", endpoint="login", timeout=login_timeout)
        try:
            login = opener.open(req, timeout=login_timeout)
            final_url = login.geturl()
            login_status = getattr(login, "status", None) or login.getcode()
            login_type = login.headers.get("Content-Type", "")
            login_raw = login.read().decode("utf-8", errors="replace")
        except Exception:
            record("login", started, "error")
            raise
        else:
            elapsed = int((time.monotonic() - started) * 1000)
            record("login", started)
            login_target = _login_target_kind(final_url)
            safe_debug(
                "login_response",
                status=login_status,
                content_type=login_type,
                target=login_target,
                authenticated=not _looks_like_login_page(final_url, login_raw),
                elapsed_ms=elapsed,
            )
        if not _is_expected_upstream_url(final_url):
            raise ApiError(
                "UPSTREAM_UNEXPECTED_REDIRECT",
                "Renyy redirected the login flow to an unexpected location.",
                502,
            )
        if _looks_like_login_page(final_url, login_raw):
            raise ApiError("AUTH_FAILED", "Authentication failed. Check the customer number and password.", 401)

        parts = username.split("-")
        prefix = "%s-%s" % (parts[0], parts[1]) if len(parts) >= 2 else username
        customer_numbers = ["%s-%s" % (prefix, s) for s in suffixes] if suffixes else [username]
        query = urlencode([("customerNumbers[]", n) for n in customer_numbers])
        url = UPSTREAM_BASE + "secure/get_services_by_customer_numbers.do?" + query
        started = time.monotonic()
        safe_debug("services_request", method="GET", endpoint="services", customer_count=len(customer_numbers), timeout=services_timeout)
        try:
            resp = opener.open(url, timeout=services_timeout)
            status = getattr(resp, "status", None) or resp.getcode()
            services_final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="replace")
        except Exception:
            record("services", started, "error")
            raise
        else:
            elapsed = int((time.monotonic() - started) * 1000)
            record("services", started)
            safe_debug("services_response", status=status, content_type=content_type, bytes=len(raw.encode("utf-8")), elapsed_ms=elapsed)
        if not _is_expected_upstream_url(services_final_url):
            raise ApiError(
                "UPSTREAM_UNEXPECTED_REDIRECT",
                "Renyy redirected the data request to an unexpected location.",
                502,
            )
        if _looks_like_login_page(services_final_url, raw):
            raise ApiError(
                "AUTH_SESSION_FAILED",
                "Kirjautumissessio ei pysynyt voimassa. Renyyn kirjautumistapa on voinut muuttua.",
                502,
            )
        if "json" not in content_type.lower():
            raise ApiError("UPSTREAM_INVALID_RESPONSE", "Renyy returned an unexpected response instead of JSON data.", 502)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Never TRACE-log a response merely because the server claimed a JSON
            # content type. Login/error HTML is occasionally mislabeled upstream.
            raise ApiError("UPSTREAM_INVALID_JSON", "Renyy returned invalid JSON data.", 502)
        validate_services_payload(data)
        # TRACE is intentionally limited to successfully parsed API JSON.
        sensitive_trace(
            "services_json_response",
            status=status,
            body=json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            elapsed_ms=elapsed,
        )
        return data, customer_numbers
    except ApiError:
        raise
    except HTTPError as e:
        raise ApiError("UPSTREAM_HTTP_ERROR", "The Renyy service returned an error (HTTP %s)." % e.code, 502, upstream_status=e.code)
    except (socket.timeout, TimeoutError):
        raise ApiError("UPSTREAM_TIMEOUT", "The connection to the Renyy service timed out. Try again later.", 504)
    except URLError as e:
        if isinstance(getattr(e, "reason", None), socket.timeout):
            raise ApiError("UPSTREAM_TIMEOUT", "The connection to the Renyy service timed out. Try again later.", 504)
        raise ApiError("UPSTREAM_CONNECTION_ERROR", "Could not connect to the Renyy service.", 502)
