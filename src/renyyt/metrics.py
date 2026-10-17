import threading
import time

def _prom_label(value):
    return str(value).replace("\\\\", "\\\\\\\\").replace("\\\"", "\\\\\\\"").replace("\\n", "\\\\n")

class Metrics:
    API_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self, version="dev", git_commit="", readiness=None, rate_stats=None, cache_stats=None):
        self.version = version
        self.git_commit = git_commit
        self.readiness = readiness or (lambda: (True, {}))
        self.rate_stats = rate_stats or (lambda: {"tracked_clients": 0, "blocked_clients": 0})
        self.cache_stats = cache_stats or (lambda: {"enabled": False, "entries": 0, "bytes": 0, "hits": 0, "misses": 0, "evictions": 0, "expired": 0})
        self.lock = threading.Lock()
        self.started_at = time.time()
        self.process_start_unixtime = self.started_at
        self.http = {}
        self.http_response_bytes = {}
        self.active_http = 0
        self.api_attempts = 0
        self.api_success = 0
        self.api_errors = {}
        self.api_duration_sum = 0.0
        self.api_duration_buckets = {b: 0 for b in self.API_BUCKETS}
        self.last_success = 0.0
        self.upstream_duration_sum = {}
        self.upstream_calls = {}
        self.upstream_errors = {}
        self.upstream_last_success = {}
        self.rate_limited = 0
        self.schema_warnings = 0
        self.unknown_fields = 0
        self.http_duration_sum = {}
        self.http_duration_count = {}

    def request_started(self):
        with self.lock:
            self.active_http += 1

    def request_finished(self):
        with self.lock:
            self.active_http = max(0, self.active_http - 1)

    def record_http(self, method, route, status, response_bytes=0, duration=None):
        key = (method, route, int(status))
        route_key = (method, route)
        with self.lock:
            self.http[key] = self.http.get(key, 0) + 1
            self.http_response_bytes[key] = self.http_response_bytes.get(key, 0) + int(response_bytes or 0)
            if duration is not None:
                self.http_duration_sum[route_key] = self.http_duration_sum.get(route_key, 0.0) + float(duration)
                self.http_duration_count[route_key] = self.http_duration_count.get(route_key, 0) + 1

    def record_api(self, duration, code=None):
        duration = float(duration)
        with self.lock:
            self.api_attempts += 1
            self.api_duration_sum += duration
            for bucket in self.API_BUCKETS:
                if duration <= bucket:
                    self.api_duration_buckets[bucket] += 1
            if code is None:
                self.api_success += 1
                self.last_success = time.time()
            else:
                self.api_errors[code] = self.api_errors.get(code, 0) + 1

    def record_upstream(self, stage, duration, outcome="success"):
        key = (stage, outcome)
        with self.lock:
            self.upstream_calls[key] = self.upstream_calls.get(key, 0) + 1
            self.upstream_duration_sum[stage] = self.upstream_duration_sum.get(stage, 0.0) + float(duration)
            if outcome != "success":
                self.upstream_errors[key] = self.upstream_errors.get(key, 0) + 1
            else:
                self.upstream_last_success[stage] = time.time()

    def record_rate_limited(self):
        with self.lock:
            self.rate_limited += 1

    def record_schema_warnings(self, count=1):
        with self.lock:
            self.schema_warnings += int(count)

    def record_unknown_fields(self, count=1):
        with self.lock:
            self.unknown_fields += int(count)

    def render(self, openmetrics=False):
        with self.lock:
            lines = [
                "# HELP renyyt_uptime_seconds Process uptime in seconds.",
                "# TYPE renyyt_uptime_seconds gauge",
                "renyyt_uptime_seconds %.3f" % (time.time() - self.started_at),
                "# HELP renyyt_process_start_unixtime Process start time as Unix time.",
                "# TYPE renyyt_process_start_unixtime gauge",
                "renyyt_process_start_unixtime %.3f" % self.process_start_unixtime,
                "# HELP renyyt_build_info Build information.",
                "# TYPE renyyt_build_info gauge",
                'renyyt_build_info{version="%s",git_commit="%s"} 1' % (_prom_label(self.version), _prom_label(self.git_commit)),
                "# HELP renyyt_http_active_requests Current active HTTP requests.",
                "# TYPE renyyt_http_active_requests gauge",
                "renyyt_http_active_requests %d" % self.active_http,
                "# HELP renyyt_http_requests_total HTTP requests by method, route and status.",
                "# TYPE renyyt_http_requests_total counter",
            ]
            for (method, route, status), count in sorted(self.http.items()):
                lines.append('renyyt_http_requests_total{method="%s",route="%s",status="%s"} %d' % (method, route, status, count))
            lines.extend([
                "# HELP renyyt_http_response_bytes_total HTTP response body bytes by method, route and status.",
                "# TYPE renyyt_http_response_bytes_total counter",
            ])
            for (method, route, status), total in sorted(self.http_response_bytes.items()):
                lines.append('renyyt_http_response_bytes_total{method="%s",route="%s",status="%s"} %d' % (method, route, status, total))
            lines.extend([
                "# HELP renyyt_http_response_bytes_count HTTP response body size sample count by method, route and status.",
                "# TYPE renyyt_http_response_bytes_count counter",
            ])
            for (method, route, status), count in sorted(self.http.items()):
                lines.append('renyyt_http_response_bytes_count{method="%s",route="%s",status="%s"} %d' % (method, route, status, count))
            lines.extend([
                "# HELP renyyt_http_request_duration_seconds_sum Total HTTP request duration by method and route.",
                "# TYPE renyyt_http_request_duration_seconds_sum counter",
            ])
            for (method, route), total in sorted(self.http_duration_sum.items()):
                lines.append('renyyt_http_request_duration_seconds_sum{method="%s",route="%s"} %.6f' % (method, route, total))
            lines.extend([
                "# HELP renyyt_http_request_duration_seconds_count HTTP request duration sample count by method and route.",
                "# TYPE renyyt_http_request_duration_seconds_count counter",
            ])
            for (method, route), count in sorted(self.http_duration_count.items()):
                lines.append('renyyt_http_request_duration_seconds_count{method="%s",route="%s"} %d' % (method, route, count))
            ready, readiness_checks = self.readiness()
            rate_stats = self.rate_stats()
            lines.extend([
                "# HELP renyyt_ready Whether the application is currently ready to serve requests.",
                "# TYPE renyyt_ready gauge",
                "renyyt_ready %d" % (1 if ready else 0),
                "# HELP renyyt_readiness_check Individual readiness checks.",
                "# TYPE renyyt_readiness_check gauge",
            ])
            for check, ok in sorted(readiness_checks.items()):
                lines.append('renyyt_readiness_check{check="%s"} %d' % (_prom_label(check), 1 if ok else 0))
            lines.extend([
                "# HELP renyyt_rate_limited_total API requests rejected by the authentication rate limiter.",
                "# TYPE renyyt_rate_limited_total counter",
                "renyyt_rate_limited_total %d" % self.rate_limited,
                "# HELP renyyt_rate_limit_tracked_clients Current clients retained by the in-memory rate limiter.",
                "# TYPE renyyt_rate_limit_tracked_clients gauge",
                "renyyt_rate_limit_tracked_clients %d" % rate_stats.get("tracked_clients", 0),
                "# HELP renyyt_rate_limit_blocked_clients Current blocked clients in the in-memory rate limiter.",
                "# TYPE renyyt_rate_limit_blocked_clients gauge",
                "renyyt_rate_limit_blocked_clients %d" % rate_stats.get("blocked_clients", 0),
                "# HELP renyyt_rate_limit_cleanup_runs_total In-memory rate limiter cleanup passes.",
                "# TYPE renyyt_rate_limit_cleanup_runs_total counter",
                "renyyt_rate_limit_cleanup_runs_total %d" % rate_stats.get("cleanup_runs", 0),
                "# HELP renyyt_rate_limit_pruned_clients_total Expired client entries removed by the rate limiter.",
                "# TYPE renyyt_rate_limit_pruned_clients_total counter",
                "renyyt_rate_limit_pruned_clients_total %d" % rate_stats.get("pruned_clients", 0),
                "# HELP renyyt_upstream_schema_warnings_total Service-level upstream schema warnings.",
                "# TYPE renyyt_upstream_schema_warnings_total counter",
                "renyyt_upstream_schema_warnings_total %d" % self.schema_warnings,
                "# HELP renyyt_upstream_unknown_fields_total Unknown upstream fields observed in diagnostic scanning.",
                "# TYPE renyyt_upstream_unknown_fields_total counter",
                "renyyt_upstream_unknown_fields_total %d" % self.unknown_fields,
            ])
            lines.extend([
                "# HELP renyyt_api_requests_total Renyy API proxy attempts.", "# TYPE renyyt_api_requests_total counter", "renyyt_api_requests_total %d" % self.api_attempts,
                "# HELP renyyt_api_success_total Successful Renyy API proxy requests.", "# TYPE renyyt_api_success_total counter", "renyyt_api_success_total %d" % self.api_success,
                "# HELP renyyt_api_request_duration_seconds Renyy API request duration.", "# TYPE renyyt_api_request_duration_seconds histogram",
            ])
            cumulative = 0
            for bucket in self.API_BUCKETS:
                cumulative = self.api_duration_buckets[bucket]
                lines.append('renyyt_api_request_duration_seconds_bucket{le="%s"} %d' % (bucket, cumulative))
            lines.append('renyyt_api_request_duration_seconds_bucket{le="+Inf"} %d' % self.api_attempts)
            lines.append("renyyt_api_request_duration_seconds_sum %.6f" % self.api_duration_sum)
            lines.append("renyyt_api_request_duration_seconds_count %d" % self.api_attempts)
            lines.extend([
                "# HELP renyyt_api_last_success_unixtime Last successful Renyy API proxy request as Unix time.", "# TYPE renyyt_api_last_success_unixtime gauge", "renyyt_api_last_success_unixtime %.3f" % self.last_success,
                "# HELP renyyt_api_errors_total Renyy API proxy errors by code.", "# TYPE renyyt_api_errors_total counter",
            ])
            for code, count in sorted(self.api_errors.items()):
                lines.append('renyyt_api_errors_total{code="%s"} %d' % (_prom_label(code), count))
            lines.extend([
                "# HELP renyyt_api_outcomes_total Renyy API proxy outcomes by code.",
                "# TYPE renyyt_api_outcomes_total counter",
                'renyyt_api_outcomes_total{code="success"} %d' % self.api_success,
            ])
            for code, count in sorted(self.api_errors.items()):
                lines.append('renyyt_api_outcomes_total{code="%s"} %d' % (_prom_label(code), count))
            lines.extend(["# HELP renyyt_upstream_calls_total Upstream calls by stage and outcome.", "# TYPE renyyt_upstream_calls_total counter"])
            for (stage, outcome), count in sorted(self.upstream_calls.items()):
                lines.append('renyyt_upstream_calls_total{stage="%s",outcome="%s"} %d' % (_prom_label(stage), _prom_label(outcome), count))
            lines.extend(["# HELP renyyt_upstream_duration_seconds_sum Total upstream duration by stage.", "# TYPE renyyt_upstream_duration_seconds_sum counter"])
            for stage, total in sorted(self.upstream_duration_sum.items()):
                lines.append('renyyt_upstream_duration_seconds_sum{stage="%s"} %.6f' % (_prom_label(stage), total))
            lines.extend(["# HELP renyyt_upstream_last_success_unixtime Last successful upstream call by stage as Unix time.", "# TYPE renyyt_upstream_last_success_unixtime gauge"])
            for stage, stamp in sorted(self.upstream_last_success.items()):
                lines.append('renyyt_upstream_last_success_unixtime{stage="%s"} %.3f' % (_prom_label(stage), stamp))
            cache = self.cache_stats()
            lines.extend([
                "# HELP renyyt_cache_enabled Whether the in-memory API response cache is enabled.",
                "# TYPE renyyt_cache_enabled gauge",
                "renyyt_cache_enabled %d" % (1 if cache.get("enabled") else 0),
                "# HELP renyyt_cache_entries Current cached API responses.",
                "# TYPE renyyt_cache_entries gauge",
                "renyyt_cache_entries %d" % cache.get("entries", 0),
                "# HELP renyyt_cache_bytes Current cached response bytes.",
                "# TYPE renyyt_cache_bytes gauge",
                "renyyt_cache_bytes %d" % cache.get("bytes", 0),
                "# HELP renyyt_cache_hits_total API response cache hits.",
                "# TYPE renyyt_cache_hits_total counter",
                "renyyt_cache_hits_total %d" % cache.get("hits", 0),
                "# HELP renyyt_cache_misses_total API response cache misses.",
                "# TYPE renyyt_cache_misses_total counter",
                "renyyt_cache_misses_total %d" % cache.get("misses", 0),
                "# HELP renyyt_cache_evictions_total API response cache LRU/size evictions.",
                "# TYPE renyyt_cache_evictions_total counter",
                "renyyt_cache_evictions_total %d" % cache.get("evictions", 0),
                "# HELP renyyt_cache_expired_total API response cache TTL expirations.",
                "# TYPE renyyt_cache_expired_total counter",
                "renyyt_cache_expired_total %d" % cache.get("expired", 0),
            ])
            if openmetrics:
                lines.append("# EOF")
            return ("\n".join(lines) + "\n").encode("utf-8")

