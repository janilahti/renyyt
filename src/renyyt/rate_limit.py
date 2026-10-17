import threading
import time


class RateLimiter:
    def __init__(self, attempts, window_seconds, block_seconds, cleanup_interval=300):
        self.attempts = int(attempts)
        self.window_seconds = float(window_seconds)
        self.block_seconds = float(block_seconds)
        self.cleanup_interval = float(cleanup_interval)
        self.lock = threading.Lock()
        self.failures = {}
        self.blocked_until = {}
        self.next_cleanup = 0.0
        self.cleanup_runs = 0
        self.pruned_clients = 0

    def _prune(self, key, now):
        existed = key in self.failures or key in self.blocked_until
        cutoff = now - self.window_seconds
        items = [ts for ts in self.failures.get(key, []) if ts >= cutoff]
        if items:
            self.failures[key] = items
        else:
            self.failures.pop(key, None)
        if self.blocked_until.get(key, 0) <= now:
            self.blocked_until.pop(key, None)
        remains = key in self.failures or key in self.blocked_until
        return 1 if existed and not remains else 0

    def _cleanup_all(self, now, force=False):
        if not force and now < self.next_cleanup:
            return
        keys = set(self.failures) | set(self.blocked_until)
        removed = sum(self._prune(key, now) for key in list(keys))
        self.cleanup_runs += 1
        self.pruned_clients += removed
        self.next_cleanup = now + self.cleanup_interval

    def cleanup(self, now=None):
        now = time.time() if now is None else float(now)
        with self.lock:
            self._cleanup_all(now, force=True)

    def check(self, key, now=None):
        now = time.time() if now is None else float(now)
        with self.lock:
            self._cleanup_all(now)
            self._prune(key, now)
            until = self.blocked_until.get(key, 0)
            if until > now:
                return False, max(1, int(until - now + 0.999))
            return True, 0

    def record_failure(self, key, now=None):
        now = time.time() if now is None else float(now)
        with self.lock:
            self._cleanup_all(now)
            self._prune(key, now)
            items = self.failures.setdefault(key, [])
            items.append(now)
            if len(items) >= self.attempts:
                until = now + self.block_seconds
                self.blocked_until[key] = until
                self.failures.pop(key, None)
                return True, max(1, int(self.block_seconds + 0.999))
            return False, 0

    def clear(self, key):
        with self.lock:
            self.failures.pop(key, None)
            self.blocked_until.pop(key, None)

    def stats(self, now=None):
        now = time.time() if now is None else float(now)
        with self.lock:
            self._cleanup_all(now)
            keys = set(self.failures) | set(self.blocked_until)
            for key in list(keys):
                self._prune(key, now)
            return {
                "tracked_clients": len(set(self.failures) | set(self.blocked_until)),
                "blocked_clients": sum(1 for until in self.blocked_until.values() if until > now),
                "cleanup_runs": self.cleanup_runs,
                "pruned_clients": self.pruned_clients,
            }
