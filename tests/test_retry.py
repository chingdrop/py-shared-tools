"""Tests for shared_tools/retry.py: exception retries, result-shape retries,
backoff timing, and the degrade-gracefully-rather-than-raise contract.
"""

import pytest

from shared_tools.retry import call_with_retry


def _no_sleep(_seconds):
    """Injected in place of time.sleep so tests run instantly."""


def test_succeeds_on_first_try_no_warnings():
    result, warnings = call_with_retry(lambda: "ok", sleep=_no_sleep)
    assert result == "ok"
    assert warnings == []


def test_retries_on_retryable_exception_then_succeeds():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("boom")
        return "ok"

    result, warnings = call_with_retry(
        flaky, retries=3, retryable_exceptions=(ValueError,), sleep=_no_sleep
    )
    assert result == "ok"
    assert len(calls) == 2
    assert len(warnings) == 1
    assert "ValueError" in warnings[0]


def test_non_retryable_exception_propagates_immediately():
    def always_raises():
        raise KeyError("not retryable")

    with pytest.raises(KeyError):
        call_with_retry(always_raises, retryable_exceptions=(ValueError,), sleep=_no_sleep)


def test_retries_on_retryable_result_then_succeeds():
    calls = []

    def returns_bad_shape_once():
        calls.append(1)
        return "bad" if len(calls) < 2 else "good"

    result, warnings = call_with_retry(
        returns_bad_shape_once,
        retries=3,
        is_retryable_result=lambda r: r != "good",
        sleep=_no_sleep,
    )
    assert result == "good"
    assert len(calls) == 2
    assert "unusable result" in warnings[0]


def test_default_never_retries_on_result_shape():
    # No is_retryable_result passed -> whatever func() returns is accepted.
    result, warnings = call_with_retry(lambda: "anything", sleep=_no_sleep)
    assert result == "anything"
    assert warnings == []


def test_exhausts_retries_and_degrades_gracefully_never_raises():
    calls = []

    def always_bad():
        calls.append(1)
        return "bad"

    result, warnings = call_with_retry(
        always_bad, retries=2, is_retryable_result=lambda r: True, sleep=_no_sleep
    )
    assert result is None  # never raises; degrades to None
    assert len(calls) == 3  # 1 initial + 2 retries, never more
    assert "exhausted 3 attempt(s)" in warnings[-1]


def test_exhausts_retries_on_persistent_exception():
    def always_raises():
        raise ValueError("persistent")

    result, warnings = call_with_retry(
        always_raises, retries=2, retryable_exceptions=(ValueError,), sleep=_no_sleep
    )
    assert result is None
    assert len(warnings) == 4  # 3 raised-exception warnings (all attempts) + 1 final summary


def test_backoff_doubles_between_attempts():
    sleeps = []

    def always_bad():
        return "bad"

    call_with_retry(
        always_bad,
        retries=3,
        backoff_factor=1.0,
        is_retryable_result=lambda r: True,
        sleep=sleeps.append,
    )
    assert sleeps == [1.0, 2.0, 4.0]  # never slept after the final attempt


def test_never_sleeps_after_final_attempt():
    sleeps = []
    call_with_retry(
        lambda: "bad", retries=0, is_retryable_result=lambda r: True, sleep=sleeps.append
    )
    assert sleeps == []  # only one attempt total (retries=0); nothing to wait between


def test_retries_zero_means_single_attempt():
    calls = []

    def counts():
        calls.append(1)
        raise ValueError("x")

    with pytest.raises(ValueError):
        # No retryable_exceptions configured -> propagates on the first call.
        call_with_retry(counts, retries=5, sleep=_no_sleep)
    assert len(calls) == 1
