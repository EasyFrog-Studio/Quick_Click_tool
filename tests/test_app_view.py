import time

import pytest

from app import ViewState, describe
from clicker_core import Snapshot, Status


def test_initial_idle_shows_paused_and_zero():
    view = describe(Snapshot(Status.IDLE, 0, None, None))
    assert view == ViewState("已暫停", "muted", "已點擊 0", None, "開始連點 (F4)")


def test_idle_after_manual_stop_keeps_count_and_progress():
    view = describe(Snapshot(Status.IDLE, 37, 100, None))
    assert view.status_text == "已暫停"
    assert view.counter_text == "已點擊 37 / 100"
    assert view.progress == pytest.approx(0.37)


def test_running_with_limit():
    view = describe(Snapshot(Status.RUNNING, 37, 100, None))
    assert view == ViewState("連點中", "success", "已點擊 37 / 100", pytest.approx(0.37), "停止連點 (F4)")


def test_running_unlimited_hides_bar():
    view = describe(Snapshot(Status.RUNNING, 1234, None, None))
    assert view.counter_text == "已點擊 1234"
    assert view.progress is None
    assert view.button_text == "停止連點 (F4)"


@pytest.mark.parametrize("limit", [20, 500])
def test_completed_names_limit_and_full_bar(limit):
    view = describe(Snapshot(Status.COMPLETED, limit, limit, None))
    assert view.status_text == f"已完成 {limit} 次"
    assert view.tone == "primary"
    assert view.counter_text == f"已點擊 {limit} / {limit}"
    assert view.progress == pytest.approx(1.0)
    assert view.button_text == "開始連點 (F4)"


def test_failsafe_is_warning():
    view = describe(Snapshot(Status.FAILSAFE, 12, None, None))
    assert view.status_text == "已強制停止（滑鼠移到螢幕角落）"
    assert view.tone == "warning"
    assert view.counter_text == "已點擊 12"
    assert view.button_text == "開始連點 (F4)"


@pytest.mark.parametrize("message", ["boom", "存取被拒"])
def test_error_shows_message(message):
    view = describe(Snapshot(Status.ERROR, 3, 10, message))
    assert view.status_text == f"發生錯誤：{message}"
    assert view.tone == "danger"
    assert view.progress == pytest.approx(0.3)


@pytest.fixture(scope="module")
def tk_root():
    import customtkinter as ctk

    # Tcl on Windows fails intermittently when a second Tk interpreter is created in one process.
    root = ctk.CTk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def ui(tk_root):
    import customtkinter as ctk
    from app import App
    from clicker_core import Clicker

    window = ctk.CTkToplevel(tk_root)
    window.withdraw()
    clicker = Clicker(lambda: None, RuntimeError)
    app = App(window, clicker)
    yield app, clicker
    app.on_close()


def _fill(app, interval, count):
    app.interval_entry.delete(0, "end")
    app.interval_entry.insert(0, interval)
    app.count_entry.delete(0, "end")
    app.count_entry.insert(0, count)


def test_invalid_interval_shows_error_and_does_not_start(ui):
    app, clicker = ui
    _fill(app, "abc", "")
    app.on_toggle()
    assert app.interval_hint.cget("text") == "間隔秒數格式錯誤"
    assert app.count_hint.cget("text") == "留空 = 不限次數"
    assert clicker.snapshot().status == Status.IDLE


def test_invalid_count_shows_error_and_does_not_start(ui):
    app, clicker = ui
    _fill(app, "0.05", "0")
    app.on_toggle()
    assert app.count_hint.cget("text") == "點擊次數需為正整數"
    assert app.interval_hint.cget("text") == "最小 0.01 秒，數值越小越快"
    assert clicker.snapshot().status == Status.IDLE


def test_both_invalid_show_both_errors(ui):
    app, clicker = ui
    _fill(app, "", "1.5")
    app.on_toggle()
    assert app.interval_hint.cget("text") == "請輸入間隔秒數"
    assert app.count_hint.cget("text") == "點擊次數需為正整數"
    assert clicker.snapshot().status == Status.IDLE


def test_valid_starts_locks_inputs_then_stops(ui):
    app, clicker = ui
    _fill(app, "abc", "")
    app.on_toggle()
    _fill(app, "0.01", "")
    app.on_toggle()
    assert clicker.snapshot().status == Status.RUNNING
    assert app.interval_hint.cget("text") == "最小 0.01 秒，數值越小越快"
    app.refresh()
    assert app.interval_entry.cget("state") == "disabled"
    assert app.count_entry.cget("state") == "disabled"
    assert app.button.cget("text") == "停止連點 (F4)"
    app.on_toggle()
    assert clicker.snapshot().status == Status.IDLE
    app.refresh()
    assert app.interval_entry.cget("state") == "normal"


def test_queued_toggle_is_drained_by_poll(ui):
    app, clicker = ui
    _fill(app, "0.01", "5")
    app.queue.put("toggle")
    app.poll()
    deadline = time.time() + 2
    while clicker.snapshot().status == Status.RUNNING and time.time() < deadline:
        time.sleep(0.01)
    app.refresh()
    assert clicker.snapshot().status == Status.COMPLETED
    assert app.status_label.cget("text") == "已完成 5 次"
    assert app.counter_label.cget("text") == "已點擊 5 / 5"
