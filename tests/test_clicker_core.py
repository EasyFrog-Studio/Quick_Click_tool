import threading
import time

import pytest

from clicker_core import (
    MIN_INTERVAL,
    Clicker,
    InputError,
    Status,
    parse_count,
    parse_interval,
)


def test_parse_interval_valid_values():
    assert parse_interval("0.01") == 0.01
    assert parse_interval(" 1.5 ") == 1.5


def test_parse_interval_invalid_blank():
    with pytest.raises(InputError) as exc:
        parse_interval("")
    assert exc.value.field == "interval"
    assert exc.value.message


def test_parse_interval_invalid_non_number():
    with pytest.raises(InputError) as exc:
        parse_interval("abc")
    assert exc.value.field == "interval"
    assert exc.value.message


def test_parse_interval_invalid_too_small():
    with pytest.raises(InputError) as exc:
        parse_interval("0.005")
    assert exc.value.field == "interval"
    assert exc.value.message


def test_parse_interval_invalid_nan_inf():
    with pytest.raises(InputError):
        parse_interval("nan")
    with pytest.raises(InputError):
        parse_interval("inf")


def test_parse_count_blank_is_none():
    assert parse_count("") is None
    assert parse_count("   ") is None


def test_parse_count_valid_values():
    assert parse_count("100") == 100
    assert parse_count(" 3 ") == 3


def test_parse_count_invalid_zero_and_negative():
    with pytest.raises(InputError) as exc:
        parse_count("0")
    assert exc.value.field == "count"
    with pytest.raises(InputError):
        parse_count("-5")


def test_parse_count_invalid_non_integer_forms():
    with pytest.raises(InputError):
        parse_count("1.5")
    with pytest.raises(InputError):
        parse_count("abc")
    with pytest.raises(InputError):
        parse_count("1e3")


def test_parse_count_rejects_non_decimal_digit_characters():
    with pytest.raises(InputError) as exc:
        parse_count("²")
    assert exc.value.field == "count"
    with pytest.raises(InputError):
        parse_count("3²")


class FakeFailsafe(Exception):
    pass


def make_recording_click(calls):
    def click():
        calls.append(1)
    return click


def wait_until_not_running(clicker, timeout=2.0):
    deadline = time.time() + timeout
    while clicker.snapshot().status == Status.RUNNING and time.time() < deadline:
        time.sleep(0.01)


@pytest.mark.parametrize("limit", [3, 7])
def test_start_with_limit_completes_exactly(limit):
    calls = []
    clicker = Clicker(make_recording_click(calls), FakeFailsafe)
    clicker.start(MIN_INTERVAL, limit)
    wait_until_not_running(clicker)
    snap = clicker.snapshot()
    assert snap.status == Status.COMPLETED
    assert snap.count == limit
    assert len(calls) == limit


def test_unlimited_run_then_stop_keeps_count():
    calls = []
    clicker = Clicker(make_recording_click(calls), FakeFailsafe)
    clicker.start(MIN_INTERVAL, None)
    time.sleep(0.1)
    clicker.stop()
    snap = clicker.snapshot()
    assert snap.status == Status.IDLE
    assert snap.count > 0
    count_at_stop = snap.count
    time.sleep(0.05)
    assert clicker.snapshot().count == count_at_stop
    assert len(calls) == count_at_stop


def test_new_round_after_completion_resets_count():
    calls = []
    gate = threading.Event()
    gate.set()

    def click():
        gate.wait()
        calls.append(1)

    clicker = Clicker(click, FakeFailsafe)
    clicker.start(MIN_INTERVAL, 5)
    wait_until_not_running(clicker)
    assert clicker.snapshot().count > 0

    gate.clear()
    clicker.start(MIN_INTERVAL, None)
    assert clicker.snapshot().count == 0
    gate.set()
    clicker.stop()


def test_rapid_start_stop_never_runs_two_threads_concurrently():
    lock = threading.Lock()
    state = {"current": 0, "max": 0}

    def click():
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        time.sleep(0.005)
        with lock:
            state["current"] -= 1

    clicker = Clicker(click, FakeFailsafe)
    for i in range(30):
        if i % 3 == 2:
            clicker.stop()
        else:
            clicker.start(MIN_INTERVAL, None)
        time.sleep(0.005)
    clicker.stop()
    time.sleep(0.05)
    assert state["max"] == 1


def test_stop_mid_round_then_start_resets_count():
    calls = []
    clicker = Clicker(make_recording_click(calls), FakeFailsafe)
    clicker.start(MIN_INTERVAL, 1000)
    time.sleep(0.1)
    clicker.stop()
    assert clicker.snapshot().count > 0
    clicker.start(5.0, 1000)
    snap = clicker.snapshot()
    clicker.stop()
    assert snap.status == Status.RUNNING
    assert snap.count <= 1


def test_failsafe_exception_sets_failsafe_status():
    def click():
        raise FakeFailsafe("edge hit")

    clicker = Clicker(click, FakeFailsafe)
    clicker.start(MIN_INTERVAL, None)
    wait_until_not_running(clicker)
    assert clicker.snapshot().status == Status.FAILSAFE


def test_other_exception_sets_error_status_with_message():
    def click():
        raise OSError("boom")

    clicker = Clicker(click, FakeFailsafe)
    clicker.start(MIN_INTERVAL, None)
    wait_until_not_running(clicker)
    snap = clicker.snapshot()
    assert snap.status == Status.ERROR
    assert snap.error == "boom"


def test_exception_without_message_still_reports_its_type():
    def click():
        raise OSError()

    clicker = Clicker(click, FakeFailsafe)
    clicker.start(MIN_INTERVAL, None)
    wait_until_not_running(clicker)
    snap = clicker.snapshot()
    assert snap.status == Status.ERROR
    assert snap.error == "OSError"


def test_stop_is_prompt_with_long_interval():
    calls = []
    clicker = Clicker(make_recording_click(calls), FakeFailsafe)
    clicker.start(5.0, None)
    time.sleep(0.05)
    started = time.time()
    clicker.stop()
    elapsed = time.time() - started
    assert elapsed < 1.0
    assert clicker.snapshot().status == Status.IDLE
