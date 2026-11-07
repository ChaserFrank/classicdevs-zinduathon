"""Holds the current request id in a contextvar so log records anywhere can include it."""

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
