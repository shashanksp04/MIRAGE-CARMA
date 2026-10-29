"""Optional request-local observation; no demo dependency or default I/O."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import logging

_observer = ContextVar("mirage_observer", default=None)
LOG = logging.getLogger(__name__)


@contextmanager
def observe(callback=None):
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def observing():
    return _observer.get() is not None


def emit(event_type, stage, payload=None, status="completed"):
    callback = _observer.get()
    if callback is not None:
        try:
            callback(event_type, stage, payload or {}, status)
        except Exception:
            # Observation must not change any inference behavior, even on failure.
            LOG.exception("Optional inference observer failed")


def observe_tool(stage):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not observing():
                return function(*args, **kwargs)
            emit("tool_started", stage, {"tool": function.__name__, "arguments": kwargs}, "running")
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                emit("tool_failed", stage, {"tool": function.__name__, "error_type": type(exc).__name__}, "failed")
                raise
            emit("tool_completed", stage, {"tool": function.__name__, "result": result})
            return result
        return wrapped
    return decorate
