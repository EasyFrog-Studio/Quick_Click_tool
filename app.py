"""CustomTkinter GUI entry point for the auto-clicker."""
import queue
from dataclasses import dataclass
from typing import Optional

import customtkinter as ctk
import keyboard
import pyautogui

from clicker_core import Clicker, InputError, Snapshot, Status, parse_count, parse_interval

FONT_FAMILY = "Microsoft JhengHei UI"
PRIMARY = ("#0D9488", "#0D9488")
PRIMARY_HOVER = ("#0F766E", "#0F766E")
ACCENT = ("#EA580C", "#EA580C")
ACCENT_HOVER = ("#C2410C", "#C2410C")
TONES = {
    "success": ("#15803D", "#4ADE80"),
    "warning": ("#C2410C", "#FB923C"),
    "danger": ("#B91C1C", "#F87171"),
    "muted": ("#475569", "#94A3B8"),
    "primary": ("#0F766E", "#2DD4BF"),
}
TEXT = ("#0F172A", "#E2E8F0")
WINDOW_BG = ("#F1F5F9", "#0F172A")
CARD_BG = ("#FFFFFF", "#1E293B")
CARD_BORDER = ("#E2E8F0", "#334155")
ENTRY_BG = ("#F8FAFC", "#0F172A")
ENTRY_BORDER = ("#CBD5E1", "#475569")
DISABLED_BG = ("#E2E8F0", "#1E293B")
DISABLED_TEXT = ("#64748B", "#94A3B8")
TRACK = ("#E2E8F0", "#334155")

INTERVAL_HELP = "最小 0.01 秒，數值越小越快"
COUNT_HELP = "留空 = 不限次數"
POLL_MS = 100
PAD = 24


@dataclass(frozen=True)
class ViewState:
    status_text: str
    tone: str
    counter_text: str
    progress: Optional[float]
    button_text: str


def describe(snap: Snapshot) -> ViewState:
    if snap.status == Status.RUNNING:
        status_text, tone = "連點中", "success"
    elif snap.status == Status.COMPLETED:
        status_text, tone = f"已完成 {snap.limit} 次", "primary"
    elif snap.status == Status.FAILSAFE:
        status_text, tone = "已強制停止（滑鼠移到螢幕角落）", "warning"
    elif snap.status == Status.ERROR:
        status_text, tone = f"發生錯誤：{snap.error}", "danger"
    else:
        status_text, tone = "已暫停", "muted"
    if snap.limit is None:
        counter_text, progress = f"已點擊 {snap.count}", None
    else:
        counter_text, progress = f"已點擊 {snap.count} / {snap.limit}", snap.count / snap.limit
    button_text = "停止連點 (F4)" if snap.status == Status.RUNNING else "開始連點 (F4)"
    return ViewState(status_text, tone, counter_text, progress, button_text)


class App:
    def __init__(self, root: ctk.CTk, clicker: Clicker):
        self.root = root
        self.clicker = clicker
        self.queue: "queue.Queue[str]" = queue.Queue()

        root.title("智能滑鼠連點器 v1.0")
        root.resizable(False, False)
        root.configure(fg_color=WINDOW_BG)

        def font(size, weight="normal"):
            return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.pack(padx=PAD, pady=PAD, fill="both", expand=True)

        ctk.CTkLabel(body, text="高速滑鼠連點器", font=font(22, "bold"), text_color=TEXT,
                     anchor="w").pack(fill="x", pady=(0, 16))

        card = ctk.CTkFrame(body, corner_radius=12, fg_color=CARD_BG, border_width=1,
                            border_color=CARD_BORDER)
        card.pack(fill="x")
        card.grid_columnconfigure(0, weight=1)

        def field(row, label, default, helper):
            ctk.CTkLabel(card, text=label, font=font(14, "bold"), text_color=TEXT,
                         anchor="w").grid(row=row, column=0, sticky="w",
                                          padx=(16, 12), pady=(14 if row == 0 else 4, 0))
            entry = ctk.CTkEntry(card, width=140, height=36, corner_radius=8, font=font(14),
                                 fg_color=ENTRY_BG, border_color=ENTRY_BORDER, text_color=TEXT)
            entry.insert(0, default)
            entry.grid(row=row, column=1, sticky="e", padx=(0, 16), pady=(14 if row == 0 else 4, 0))
            hint = ctk.CTkLabel(card, text=helper, font=font(12), text_color=TONES["muted"],
                                anchor="w", height=20)
            hint.grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=16,
                      pady=(2, 14 if row == 2 else 8))
            return entry, hint

        self.interval_entry, self.interval_hint = field(0, "點擊間隔（秒）", "0.05", INTERVAL_HELP)
        self.count_entry, self.count_hint = field(2, "點擊次數", "", COUNT_HELP)

        status_row = ctk.CTkFrame(body, fg_color="transparent")
        status_row.pack(fill="x", pady=(18, 0))
        self.status_dot = ctk.CTkLabel(status_row, text="●", font=font(16), width=18, anchor="w")
        self.status_dot.pack(side="left", anchor="n")
        self.status_label = ctk.CTkLabel(status_row, text="", font=font(16, "bold"), anchor="w",
                                         justify="left", wraplength=270)
        self.status_label.pack(side="left", anchor="n", padx=(6, 0))

        self.counter_label = ctk.CTkLabel(body, text="", font=font(14), text_color=TEXT,
                                          anchor="w", height=24)
        self.counter_label.pack(fill="x", pady=(6, 0))
        # Fixed height keeps the layout still when the bar is hidden.
        bar_slot = ctk.CTkFrame(body, fg_color="transparent", height=16)
        bar_slot.pack(fill="x", pady=(4, 0))
        bar_slot.pack_propagate(False)
        self.progress_bar = ctk.CTkProgressBar(bar_slot, height=8, corner_radius=4,
                                               fg_color=TRACK, progress_color=PRIMARY)
        self.progress_bar.set(0)

        self.button = ctk.CTkButton(body, text="", height=48, corner_radius=10,
                                    font=font(18, "bold"), fg_color=PRIMARY,
                                    hover_color=PRIMARY_HOVER, text_color="#FFFFFF",
                                    command=self.on_toggle)
        self.button.pack(fill="x", pady=(14, 0))

        ctk.CTkLabel(body, text="按 F4 隨時開關 · 滑鼠移到螢幕角落可緊急停止", font=font(12),
                     text_color=TONES["muted"]).pack(pady=(14, 0))

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        self._poll_id = root.after(POLL_MS, self.poll)

    def on_toggle(self) -> None:
        if self.clicker.snapshot().status == Status.RUNNING:
            self.clicker.stop()
            return
        errors = {}
        try:
            interval = parse_interval(self.interval_entry.get())
        except InputError as err:
            errors[err.field] = err.message
        try:
            limit = parse_count(self.count_entry.get())
        except InputError as err:
            errors[err.field] = err.message
        self._show_hint(self.interval_hint, errors.get("interval"), INTERVAL_HELP)
        self._show_hint(self.count_hint, errors.get("count"), COUNT_HELP)
        if not errors:
            self.clicker.start(interval, limit)

    @staticmethod
    def _show_hint(label: ctk.CTkLabel, error: Optional[str], helper: str) -> None:
        if error is None:
            label.configure(text=helper, text_color=TONES["muted"])
        else:
            label.configure(text=error, text_color=TONES["danger"])

    def poll(self) -> None:
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
            self.on_toggle()
        self.refresh()
        self._poll_id = self.root.after(POLL_MS, self.poll)

    def refresh(self) -> None:
        snap = self.clicker.snapshot()
        view = describe(snap)
        colour = TONES[view.tone]
        self.status_dot.configure(text_color=colour)
        self.status_label.configure(text=view.status_text, text_color=colour)
        self.counter_label.configure(text=view.counter_text)
        if view.progress is None:
            self.progress_bar.pack_forget()
        else:
            self.progress_bar.set(view.progress)
            if not self.progress_bar.winfo_manager():
                self.progress_bar.pack(fill="x", pady=4)
        running = snap.status == Status.RUNNING
        if running:
            self.button.configure(text=view.button_text, fg_color=ACCENT, hover_color=ACCENT_HOVER)
        else:
            self.button.configure(text=view.button_text, fg_color=PRIMARY, hover_color=PRIMARY_HOVER)
        for entry in (self.interval_entry, self.count_entry):
            if running:
                entry.configure(state="disabled", fg_color=DISABLED_BG, text_color=DISABLED_TEXT)
            else:
                entry.configure(state="normal", fg_color=ENTRY_BG, text_color=TEXT)

    def on_close(self) -> None:
        self.root.after_cancel(self._poll_id)
        self.clicker.stop()
        keyboard.unhook_all()
        self.root.destroy()


def main() -> None:
    ctk.set_appearance_mode("system")
    pyautogui.PAUSE = 0
    root = ctk.CTk()
    app = App(root, Clicker(pyautogui.click, pyautogui.FailSafeException))
    keyboard.add_hotkey("f4", lambda: app.queue.put("toggle"))
    root.mainloop()


if __name__ == "__main__":
    main()
