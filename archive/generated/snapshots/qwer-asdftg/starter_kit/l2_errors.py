"""Safe, actionable errors for the LoomQ L2 local entry points."""

from __future__ import annotations


class L2Error(RuntimeError):
    """Base class for errors that may be shown directly to a local user."""


class L2ConfigurationError(L2Error):
    def __init__(self, message: str, *, variable_names: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.variable_names = variable_names


class L2TransportError(L2Error):
    def __init__(self, host: str, timeout_seconds: float) -> None:
        super().__init__(f"cannot reach {host} within {timeout_seconds:g} seconds")
        self.host = host
        self.timeout_seconds = timeout_seconds


class L2ApiError(L2Error):
    def __init__(self, status: int, host: str, request_id: str | None = None) -> None:
        details = f"API at {host} returned HTTP {status}"
        if request_id:
            details += f" (request id: {request_id})"
        super().__init__(details)
        self.status = status
        self.host = host
        self.request_id = request_id


class L2ValidationError(L2Error):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
