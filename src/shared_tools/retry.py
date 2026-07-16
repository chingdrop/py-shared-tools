"""Generic retry-with-backoff for a call that can fail two different ways:
raising an exception, or returning a "successful but unusable" result.

``RestAdapter``'s own ``retries``/``backoff_factor`` (via urllib3's ``Retry``)
already covers HTTP-transport-level failures — a raised connection error, or a
non-2xx status in its ``status_forcelist`` (429/5xx). It has no way to retry a
plain ``200 OK`` whose *body* turns out to be unusable: an HTML error page
served under the wrong content-type, or JSON that decodes fine but isn't the
shape a caller actually needs — both real failure modes for anything scraping
a public API under load (crt.sh's JSON endpoint, HIBP's Pwned Passwords range
endpoint). This module is the other half: a small, HTTP-agnostic retry loop a
caller layers on top of whatever it's calling — ``RestAdapter`` or anything
else — driven by a caller-supplied predicate over the *result*, not just the
transport.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


def call_with_retry[T](
    func: Callable[[], T],
    *,
    retries: int = 3,
    backoff_factor: float = 1.0,
    is_retryable_result: Callable[[T], bool] = lambda result: False,
    retryable_exceptions: tuple[type[Exception], ...] = (),
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T | None, list[str]]:
    """Call ``func()`` up to ``retries + 1`` times, retrying on either a
    caught exception or a "successful but unusable" result.

    Two independent ways an attempt can be treated as a failure:

    * ``func()`` raises one of ``retryable_exceptions`` — caught, recorded as a
      warning, retried. Any other exception propagates immediately and is
      never caught here. The default (``()``) treats nothing as retryable, so
      a caller must opt in explicitly to which exceptions are worth retrying
      rather than this silently swallowing something unrelated (a bug in
      ``func`` itself, say).
    * ``func()`` returns a result for which ``is_retryable_result(result)`` is
      ``True`` — "this isn't the shape I expected," a ``200`` that's actually
      an error page, etc. The default (``lambda result: False``) never treats
      a result as retryable, so a purely exception-driven caller doesn't need
      to pass this at all.

    Backoff is exponential: ``backoff_factor``, ``backoff_factor * 2``,
    ``backoff_factor * 4``, ... between attempts, never slept after the final
    one. ``sleep`` is injectable (pass ``sleep=lambda _: None`` in tests) so a
    retry loop can be exercised without actually waiting or monkeypatching
    ``time.sleep`` globally.

    Returns ``(result, warnings)``: on success, ``result`` is the first
    accepted return value and ``warnings`` lists any earlier failed attempts
    (empty on a first-try success); if every attempt fails, ``result`` is
    ``None`` and the last warning summarizes the exhausted retries. **Never
    raises** for anything covered by ``retryable_exceptions`` or
    ``is_retryable_result`` — that is the whole point: a caller gets a clean
    "here's what happened" back instead of having to wrap this in its own
    try/except, so one flaky upstream response degrades gracefully rather than
    aborting whatever larger operation it's part of.
    """
    warnings: list[str] = []
    delay = backoff_factor
    attempts = retries + 1

    for attempt in range(1, attempts + 1):
        try:
            result = func()
        except retryable_exceptions as exc:
            warnings.append(f"attempt {attempt}/{attempts} raised {exc.__class__.__name__}: {exc}")
        else:
            if not is_retryable_result(result):
                return result, warnings
            warnings.append(f"attempt {attempt}/{attempts} returned an unusable result")

        if attempt < attempts:
            sleep(delay)
            delay *= 2

    final = f"exhausted {attempts} attempt(s); giving up"
    warnings.append(final)
    logger.warning(final)
    return None, warnings
