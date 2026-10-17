import hashlib
import hmac
import json
import secrets
import threading
from contextlib import contextmanager
import time
from collections import OrderedDict


class ResponseCache:
    """Thread-safe in-memory LRU+TTL cache with HMAC-derived opaque keys."""

    def __init__(self, max_entries=0, ttl_seconds=0, max_bytes=16 * 1024 * 1024, clock=None):
        self.max_entries = int(max_entries or 0)
        self.ttl_seconds = float(ttl_seconds or 0)
        self.max_bytes = int(max_bytes or 0)
        self.clock = clock or time.monotonic
        self._secret = secrets.token_bytes(32)
        self._items = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._key_locks = {}
        self._key_locks_guard = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expired = 0

    @property
    def enabled(self):
        return self.max_entries > 0 and self.ttl_seconds > 0

    def make_key(self, username, password, suffixes):
        payload = json.dumps(
            {"username": username, "password": password, "suffixes": list(suffixes)},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _prune_expired_locked(self, now):
        dead = [key for key, item in self._items.items() if item[0] <= now]
        for key in dead:
            _expires, value = self._items.pop(key)
            self._bytes -= len(value)
            self.expired += 1

    def prune(self):
        if not self.enabled:
            return 0
        with self._lock:
            before = len(self._items)
            self._prune_expired_locked(self.clock())
            return before - len(self._items)

    def get(self, key):
        if not self.enabled:
            return None
        now = self.clock()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            expires, value = item
            if expires <= now:
                self._items.pop(key, None)
                self._bytes -= len(value)
                self.expired += 1
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key, value):
        if not self.enabled:
            return False
        value = bytes(value)
        if self.max_bytes > 0 and len(value) > self.max_bytes:
            return False
        now = self.clock()
        with self._lock:
            self._prune_expired_locked(now)
            previous = self._items.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous[1])
            self._items[key] = (now + self.ttl_seconds, value)
            self._bytes += len(value)
            while len(self._items) > self.max_entries or (self.max_bytes > 0 and self._bytes > self.max_bytes):
                _old_key, (_expires, old_value) = self._items.popitem(last=False)
                self._bytes -= len(old_value)
                self.evictions += 1
            return key in self._items

    def stats(self):
        with self._lock:
            return {
                "enabled": self.enabled,
                "entries": len(self._items),
                "bytes": self._bytes,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "expired": self.expired,
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "max_bytes": self.max_bytes,
            }


    @contextmanager
    def key_lock(self, key):
        """Serialize cache fills for one opaque key without blocking other keys."""
        if not self.enabled or not key:
            yield
            return
        with self._key_locks_guard:
            entry = self._key_locks.get(key)
            if entry is None:
                entry = [threading.Lock(), 0]
                self._key_locks[key] = entry
            entry[1] += 1
            lock = entry[0]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._key_locks_guard:
                entry[1] -= 1
                if entry[1] == 0:
                    self._key_locks.pop(key, None)

    def start_janitor(self):
        if not self.enabled or self._thread is not None:
            return
        interval = max(1.0, min(self.ttl_seconds / 2.0, 60.0))

        def worker():
            while not self._stop.wait(interval):
                self.prune()

        self._thread = threading.Thread(target=worker, name="renyyt-cache-janitor", daemon=True)
        self._thread.start()

    def stop_janitor(self):
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
