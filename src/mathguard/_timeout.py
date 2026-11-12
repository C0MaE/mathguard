"""Run a function with a wall-clock limit (best effort).

``simplify`` and friends can occasionally take minutes. On Unix in the main
thread we use ``SIGALRM``; elsewhere (Windows, threads, Pyodide in the
browser) the call simply runs without a limit.
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

T = TypeVar("T")


class TimeoutExceeded(Exception):
    pass


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    usable = (
        seconds > 0
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")  # missing in Pyodide (WebAssembly)
        and threading.current_thread() is threading.main_thread()
    )
    if not usable:
        yield
        return

    def _handler(signum, frame):  # noqa: ARG001
        raise TimeoutExceeded()

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def run_with_limit(fn: Callable[[], T], seconds: float) -> T | None:
    """Return ``fn()`` or ``None`` if it ran out of time."""
    try:
        with time_limit(seconds):
            return fn()
    except TimeoutExceeded:
        return None
