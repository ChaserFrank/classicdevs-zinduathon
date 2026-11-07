"""Logging filter that stamps every record with the current request id."""

import logging

from .request_context import request_id_var


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Django logs 4xx/5xx after the middleware chain has returned, so the contextvar is already
        # reset; those records carry the request object, which holds the id.
        request = getattr(record, "request", None)
        record.request_id = getattr(request, "request_id", None) or request_id_var.get()
        return True
