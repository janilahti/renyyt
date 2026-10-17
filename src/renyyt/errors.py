class ConfigError(ValueError):
    pass


class ApiError(Exception):
    def __init__(self, code, message, status=400, upstream_status=None, retry_after=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.upstream_status = upstream_status
        self.retry_after = retry_after
