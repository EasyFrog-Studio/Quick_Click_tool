"""GUI-free auto-clicker core: input parsing and the threaded click loop."""
import enum
import math
import threading
from dataclasses import dataclass
from typing import Callable, Optional, Type

MIN_INTERVAL = 0.01


class InputError(ValueError):
    """Carries which field failed and the zh-TW message to show the user."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def parse_interval(text: str) -> float:
    text = text.strip()
    if not text:
        raise InputError("interval", "請輸入間隔秒數")
    try:
        value = float(text)
    except ValueError:
        raise InputError("interval", "間隔秒數格式錯誤") from None
    if math.isnan(value) or math.isinf(value) or value < MIN_INTERVAL:
        raise InputError("interval", f"間隔秒數不可小於 {MIN_INTERVAL} 秒")
    return value


def parse_count(text: str) -> Optional[int]:
    text = text.strip()
    if not text:
        return None
    if not text.isdecimal():
        raise InputError("count", "點擊次數需為正整數")
    value = int(text)
    if value <= 0:
        raise InputError("count", "點擊次數需為正整數")
    return value


class Status(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILSAFE = "failsafe"
    ERROR = "error"


@dataclass(frozen=True)
class Snapshot:
    status: Status
    count: int
    limit: Optional[int]
    error: Optional[str]


class Clicker:
    """start/stop must all be called from one thread; only snapshot is safe from others."""

    def __init__(self, click: Callable[[], None], failsafe_exc: Type[BaseException]):
        self._click = click
        self._failsafe_exc = failsafe_exc
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._status = Status.IDLE
        self._count = 0
        self._limit: Optional[int] = None
        self._error: Optional[str] = None

    def start(self, interval: float, limit: Optional[int]) -> None:
        if self._thread is not None and self._thread.is_alive():
            self.stop()
        with self._lock:
            self._count = 0
            self._limit = limit
            self._error = None
            self._status = Status.RUNNING
        stop_event = threading.Event()
        self._stop_event = stop_event
        self._thread = threading.Thread(
            target=self._run, args=(interval, limit, stop_event), daemon=True
        )
        self._thread.start()

    def _run(self, interval: float, limit: Optional[int], stop_event: threading.Event) -> None:
        while True:
            try:
                self._click()
            except self._failsafe_exc:
                with self._lock:
                    self._status = Status.FAILSAFE
                return
            except Exception as exc:
                with self._lock:
                    self._status = Status.ERROR
                    self._error = str(exc) or type(exc).__name__
                return
            with self._lock:
                self._count += 1
                done = limit is not None and self._count >= limit
                if done:
                    self._status = Status.COMPLETED
            if done:
                return
            if stop_event.wait(interval):
                return

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join()
        with self._lock:
            if self._status == Status.RUNNING:
                self._status = Status.IDLE

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(
                status=self._status,
                count=self._count,
                limit=self._limit,
                error=self._error,
            )
