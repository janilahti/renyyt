import contextlib
import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import ConfigError


class ReminderError(Exception):
    pass


class PushDependencyError(ReminderError):
    pass


def push_dependencies_available():
    try:
        import pywebpush  # noqa: F401
        return True
    except ImportError:
        return False


def _subscription_id(endpoint):
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def _ensure_parent(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class ReminderStore:
    def __init__(self, path):
        self.path = _ensure_parent(path)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _initialize(self):
        with self._lock, contextlib.closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                  id TEXT PRIMARY KEY,
                  endpoint TEXT NOT NULL UNIQUE,
                  p256dh TEXT NOT NULL,
                  auth TEXT NOT NULL,
                  locale TEXT NOT NULL DEFAULT 'fi',
                  created_at REAL NOT NULL,
                  updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reminders (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  subscription_id TEXT NOT NULL REFERENCES push_subscriptions(id) ON DELETE CASCADE,
                  collection_date TEXT NOT NULL,
                  label TEXT NOT NULL,
                  trigger_at REAL NOT NULL,
                  sent_at REAL,
                  created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS reminders_due_idx ON reminders(sent_at, trigger_at);
                CREATE INDEX IF NOT EXISTS reminders_subscription_idx ON reminders(subscription_id);
                """
            )

    @staticmethod
    def validate_subscription(value):
        if not isinstance(value, dict):
            raise ReminderError("subscription must be an object")
        endpoint = str(value.get("endpoint") or "").strip()
        keys = value.get("keys") or {}
        p256dh = str(keys.get("p256dh") or "").strip()
        auth = str(keys.get("auth") or "").strip()
        if not endpoint.startswith("https://") or len(endpoint) > 4096:
            raise ReminderError("subscription endpoint must be an HTTPS URL")
        if not p256dh or not auth or len(p256dh) > 512 or len(auth) > 512:
            raise ReminderError("subscription keys are missing or invalid")
        return endpoint, p256dh, auth

    @staticmethod
    def validate_reminders(items, max_items=128):
        if not isinstance(items, list):
            raise ReminderError("reminders must be a list")
        if len(items) > max_items:
            raise ReminderError("too many reminders")
        out = []
        now = time.time()
        for item in items:
            if not isinstance(item, dict):
                raise ReminderError("each reminder must be an object")
            collection_date = str(item.get("collectionDate") or "").strip()
            label = str(item.get("label") or "").strip()[:200]
            trigger_at = str(item.get("triggerAt") or "").strip()
            if not collection_date or len(collection_date) > 32 or not label or not trigger_at:
                raise ReminderError("reminder is missing required fields")
            try:
                dt = datetime.fromisoformat(trigger_at.replace("Z", "+00:00"))
            except ValueError:
                raise ReminderError("triggerAt must be ISO-8601")
            if dt.tzinfo is None:
                raise ReminderError("triggerAt must include a timezone")
            timestamp = dt.timestamp()
            # Ignore reminders already well in the past; allow a small clock skew.
            if timestamp < now - 3600:
                continue
            if timestamp > now + 370 * 86400:
                raise ReminderError("triggerAt is too far in the future")
            out.append((collection_date, label, timestamp))
        return out

    def sync(self, subscription, reminders, locale="fi"):
        endpoint, p256dh, auth = self.validate_subscription(subscription)
        rows = self.validate_reminders(reminders)
        locale = str(locale or "fi")[:16]
        sid = _subscription_id(endpoint)
        now = time.time()
        with self._lock, contextlib.closing(self._connect()) as conn, conn:
            sent = {
                (row["collection_date"], row["label"], round(row["trigger_at"], 3))
                for row in conn.execute(
                    "SELECT collection_date, label, trigger_at FROM reminders WHERE subscription_id=? AND sent_at IS NOT NULL",
                    (sid,),
                )
            }
            conn.execute(
                """INSERT INTO push_subscriptions(id, endpoint, p256dh, auth, locale, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET endpoint=excluded.endpoint,p256dh=excluded.p256dh,
                     auth=excluded.auth,locale=excluded.locale,updated_at=excluded.updated_at""",
                (sid, endpoint, p256dh, auth, locale, now, now),
            )
            conn.execute("DELETE FROM reminders WHERE subscription_id=? AND sent_at IS NULL", (sid,))
            inserted = 0
            for collection_date, label, trigger_at in rows:
                if (collection_date, label, round(trigger_at, 3)) in sent:
                    continue
                conn.execute(
                    "INSERT INTO reminders(subscription_id,collection_date,label,trigger_at,created_at) VALUES(?,?,?,?,?)",
                    (sid, collection_date, label, trigger_at, now),
                )
                inserted += 1
        return sid, inserted

    def unsubscribe(self, subscription):
        endpoint, _p256dh, _auth = self.validate_subscription(subscription)
        sid = _subscription_id(endpoint)
        with self._lock, contextlib.closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM push_subscriptions WHERE id=?", (sid,))
        return sid

    def due(self, now=None, limit=100):
        now = time.time() if now is None else float(now)
        with self._lock, contextlib.closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """SELECT r.id AS reminder_id,r.collection_date,r.label,r.trigger_at,
                          s.id AS subscription_id,s.endpoint,s.p256dh,s.auth,s.locale
                   FROM reminders r JOIN push_subscriptions s ON s.id=r.subscription_id
                   WHERE r.sent_at IS NULL AND r.trigger_at<=?
                   ORDER BY r.trigger_at,r.id LIMIT ?""",
                (now, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_sent(self, reminder_id, sent_at=None):
        sent_at = time.time() if sent_at is None else float(sent_at)
        with self._lock, contextlib.closing(self._connect()) as conn, conn:
            conn.execute("UPDATE reminders SET sent_at=? WHERE id=?", (sent_at, int(reminder_id)))

    def delete_subscription_id(self, subscription_id):
        with self._lock, contextlib.closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM push_subscriptions WHERE id=?", (subscription_id,))

    def stats(self):
        with self._lock, contextlib.closing(self._connect()) as conn, conn:
            subscriptions = conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM reminders WHERE sent_at IS NULL").fetchone()[0]
        return {"subscriptions": subscriptions, "pending": pending}


def notification_text(locale, label, collection_date):
    lang = (locale or "fi").split("-", 1)[0].lower()
    titles = {
        "fi": "Renyyt – tyhjennysmuistutus",
        "en": "Renyyt – collection reminder",
        "sv": "Renyyt – tömningspåminnelse",
        "uk": "Renyyt – нагадування про вивезення",
    }
    bodies = {
        "fi": "{label}: tyhjennys {date}",
        "en": "{label}: collection on {date}",
        "sv": "{label}: tömning {date}",
        "uk": "{label}: вивезення {date}",
    }
    return titles.get(lang, titles["fi"]), bodies.get(lang, bodies["fi"]).format(label=label, date=collection_date)


def send_web_push(config, row, base_path=""):
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        raise PushDependencyError("Web Push dependencies are not installed. Install with: pip install 'renyyt[push]'")

    title, body = notification_text(row.get("locale"), row["label"], row["collection_date"])
    url = (base_path or "") + "/"
    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "tag": "renyyt-%s" % row["reminder_id"],
    }, ensure_ascii=False, separators=(",", ":"))
    subscription = {
        "endpoint": row["endpoint"],
        "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
    }
    claims = {"sub": config["vapid_subject"]}
    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=config["vapid_private_key"],
            vapid_claims=claims,
            ttl=config.get("push_ttl", 86400),
        )
        return "sent", None
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            return "gone", status
        raise ReminderError("Web Push delivery failed%s" % ((" (HTTP %s)" % status) if status else ""))


def run_due(config, store, logger=None, now=None, limit=100):
    due = store.due(now=now, limit=limit)
    stats = {"due": len(due), "sent": 0, "gone": 0, "failed": 0}
    for row in due:
        try:
            result, status = send_web_push(config, row, base_path=config.get("base_path", ""))
            if result == "gone":
                store.delete_subscription_id(row["subscription_id"])
                stats["gone"] += 1
                if logger:
                    logger("WARNING", "reminder_subscription_gone", subscription=row["subscription_id"][:12], status=status)
                continue
            store.mark_sent(row["reminder_id"], sent_at=now)
            stats["sent"] += 1
            if logger:
                logger("INFO", "reminder_sent", reminder_id=row["reminder_id"], subscription=row["subscription_id"][:12])
        except Exception as exc:
            stats["failed"] += 1
            if logger:
                logger("ERROR", "reminder_send_failed", reminder_id=row["reminder_id"], error_type=type(exc).__name__)
    return stats


def parse_run_times(value):
    items = []
    for raw in str(value or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split(":")
        if len(parts) != 2:
            raise ConfigError("RENYYT_REMINDERS_RUN_TIMES must contain HH:MM values.")
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            raise ConfigError("RENYYT_REMINDERS_RUN_TIMES must contain HH:MM values.")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ConfigError("RENYYT_REMINDERS_RUN_TIMES contains an invalid time %r." % raw)
        items.append((hour, minute))
    if not items:
        raise ConfigError("RENYYT_REMINDERS_RUN_TIMES must contain at least one HH:MM value.")
    return sorted(set(items))


def scheduler_timezone(name):
    name = str(name or "local").strip()
    if not name or name.lower() == "local":
        return datetime.now().astimezone().tzinfo
    if name.upper() == "UTC":
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        raise ConfigError("Named reminder time zones require Python 3.9+; use RENYYT_REMINDERS_TIMEZONE=local or UTC on Python 3.8.")
    try:
        return ZoneInfo(name)
    except Exception:
        raise ConfigError("RENYYT_REMINDERS_TIMEZONE is not a valid IANA time zone: %s" % name)


def next_scheduler_run(run_times, tz, now=None):
    now = now or datetime.now(tz)
    candidates = []
    for day_offset in (0, 1, 2):
        day = (now + timedelta(days=day_offset)).date()
        for hour, minute in run_times:
            candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            if candidate > now:
                candidates.append(candidate)
    return min(candidates)


class InternalReminderScheduler:
    def __init__(self, config, store, logger=None):
        self.config = config
        self.store = store
        self.logger = logger
        self._stop = threading.Event()
        self._thread = None
        self.run_times = parse_run_times(config["reminders_run_times"])
        self.tz = scheduler_timezone(config["reminders_timezone"])

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="renyyt-reminders", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        while not self._stop.is_set():
            next_run = next_scheduler_run(self.run_times, self.tz)
            delay = max(0.0, next_run.timestamp() - time.time())
            if self.logger:
                self.logger("INFO", "reminder_scheduler_next", run_at=next_run.isoformat())
            if self._stop.wait(delay):
                return
            try:
                stats = run_due(self.config, self.store, logger=self.logger)
                if self.logger:
                    self.logger("INFO", "reminder_scheduler_complete", **stats)
            except Exception as exc:
                if self.logger:
                    self.logger("ERROR", "reminder_scheduler_failed", error_type=type(exc).__name__)
