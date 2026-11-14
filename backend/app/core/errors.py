"""Typed application exceptions mapped cleanly to HTTP responses and SSE error codes."""


class ExploreError(Exception):
    """Structured error carrying machine code, HTTP status, and user-facing advice."""

    def __init__(self, error_code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
