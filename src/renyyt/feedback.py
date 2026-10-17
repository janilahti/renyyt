import re
import smtplib
import ssl
import threading
import time
from collections import defaultdict, deque
from email.message import EmailMessage

_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


class FeedbackRateLimiter:
    def __init__(self, limit=5, window=600.0):
        self.limit = int(limit)
        self.window = float(window)
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_record(self, key, now=None):
        now = time.monotonic() if now is None else float(now)
        cutoff = now - self.window
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(events[0] + self.window - now + 0.999))
                return False, retry_after
            events.append(now)
            return True, 0

    def clear(self):
        with self._lock:
            self._events.clear()


def feedback_enabled(config):
    return bool(config.get("smtp_host") and config.get("smtp_from") and config.get("smtp_to"))


def validate_feedback_payload(payload, max_collection_data_bytes=262144):
    if not isinstance(payload, dict):
        raise ValueError("The request JSON body must be an object.")
    message = str(payload.get("message", "")).strip()
    email = str(payload.get("email", "")).strip()
    if not message:
        raise ValueError("Feedback message is required.")
    if len(message) > 4000:
        raise ValueError("Feedback message is too long.")
    if len(email) > 254:
        raise ValueError("Feedback reply address is too long.")
    collection_data = payload.get("collectionData")
    collection_json = None
    if collection_data is not None:
        try:
            import json
            collection_json = json.dumps(collection_data, ensure_ascii=False, indent=2).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("Attached collection data must be valid JSON.")
        if len(collection_json) > int(max_collection_data_bytes):
            raise ValueError("Attached collection data is too large.")
    return message, email, collection_json


def _safe_reply_to_header(value):
    """Return a conservative Reply-To value, or empty string for free-form input."""
    value = (value or "").strip()
    if not value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return ""
    return value if _EMAIL_RE.fullmatch(value) else ""


def send_feedback(config, message, reply_to="", metadata=None, collection_json=None, debug=None, sensitive_trace=None):
    mail = EmailMessage()
    mail["Subject"] = "Renyyt feedback"
    mail["From"] = config["smtp_from"]
    mail["To"] = config["smtp_to"]
    reply_to_header = _safe_reply_to_header(reply_to)
    if reply_to_header:
        mail["Reply-To"] = reply_to_header

    lines = [message]
    if reply_to:
        lines.extend(["", "Reply address: %s" % reply_to])
    if metadata:
        lines.append("")
        lines.append("Technical information:")
        for key in sorted(metadata):
            lines.append("%s: %s" % (key, metadata[key]))
    mail.set_content("\n".join(lines))
    if collection_json is not None:
        mail.add_attachment(collection_json, maintype="application", subtype="json", filename="renyyt-collection-data.json")

    def trace(phase, **fields):
        if debug:
            debug(phase, **fields)

    def unsafe_trace(phase, **fields):
        if sensitive_trace:
            sensitive_trace(phase, **fields)

    timeout = config["smtp_timeout"]
    transport = "ssl" if config["smtp_ssl"] else ("starttls" if config["smtp_starttls"] else "plain")
    trace("connect_start", host=config["smtp_host"], port=config["smtp_port"], transport=transport, timeout=timeout, auth=bool(config["smtp_user"]))
    unsafe_trace("message", smtp_user=config["smtp_user"], smtp_password=config["smtp_password"], smtp_from=config["smtp_from"], smtp_to=config["smtp_to"], reply_to=reply_to, message=mail.as_string())
    started = time.monotonic()
    if config["smtp_ssl"]:
        client = smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"], timeout=timeout, context=ssl.create_default_context())
    else:
        client = smtplib.SMTP(config["smtp_host"], config["smtp_port"], timeout=timeout)
    if sensitive_trace:
        client._print_debug = lambda *parts: unsafe_trace("protocol", line=" ".join(str(part) for part in parts))
        client.set_debuglevel(1)
    trace("connected", elapsed_ms=int((time.monotonic() - started) * 1000))
    try:
        ehlo_code, ehlo_response = client.ehlo()
        trace("ehlo_complete", smtp_code=ehlo_code)
        unsafe_trace("ehlo_response", smtp_code=ehlo_code, response=ehlo_response.decode("utf-8", errors="replace") if isinstance(ehlo_response, bytes) else ehlo_response)
        if config["smtp_starttls"] and not config["smtp_ssl"]:
            trace("starttls_start")
            tls_code, tls_response = client.starttls(context=ssl.create_default_context())
            trace("starttls_complete", smtp_code=tls_code)
            unsafe_trace("starttls_response", smtp_code=tls_code, response=tls_response.decode("utf-8", errors="replace") if isinstance(tls_response, bytes) else tls_response)
            ehlo_code, ehlo_response = client.ehlo()
            unsafe_trace("ehlo_tls_response", smtp_code=ehlo_code, response=ehlo_response.decode("utf-8", errors="replace") if isinstance(ehlo_response, bytes) else ehlo_response)
        if config["smtp_user"]:
            trace("auth_start")
            auth_code, auth_response = client.login(config["smtp_user"], config["smtp_password"])
            trace("auth_complete", smtp_code=auth_code)
            unsafe_trace("auth_response", smtp_code=auth_code, response=auth_response.decode("utf-8", errors="replace") if isinstance(auth_response, bytes) else auth_response)
        trace("send_start")
        refused = client.send_message(mail)
        trace("send_complete", elapsed_ms=int((time.monotonic() - started) * 1000), refused_count=len(refused or {}))
        unsafe_trace("send_response", refused=repr(refused))
    finally:
        try:
            client.quit()
            trace("quit_complete")
        except (OSError, smtplib.SMTPException):
            client.close()
            trace("connection_closed")
