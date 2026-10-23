
"""Optional guided troubleshooting window. Tk interactions stay on the UI thread."""

import queue
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from netdoctor.troubleshoot import (
    GuidanceInputError,
    GuidedResult,
    GuidedWorker,
)

BG = "#0e1726"
CARD = "#19283d"
ALT = "#1e324b"
WHITE = "#f1f5fa"
MUTED = "#bac9d9"
BLUE = "#8ab5ff"
GOOD = "#75dfb7"
WARN = "#ffd18b"


class TroubleshootingWindow:
    """Symptom selection is optional; nothing downloads without confirmation."""

    def __init__(
        self,
        parent: tk.Tk,
        *,
        on_close: Callable[[], None] | None = None,
        worker: GuidedWorker | None = None,
    ) -> None:
        self.parent = parent
        self.on_close = on_close
        self.worker = worker or GuidedWorker()
        self.closed = False

        self.window = tk.Toplevel(parent)
        self.window.title("NetDoctor - Help with a problem")
        self.window.geometry("860x680")
        self.window.minsize(660, 580)
        self.window.configure(bg=BG)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        main = tk.Frame(
            self.window,
            bg=BG,
            padx=22,
            pady=18,
        )
        main.pack(fill="both", expand=True)

        tk.Label(
            main,
            text="What's happening with your internet?",
            bg=BG,
            fg=WHITE,
            font=("Segoe UI", 19, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            main,
            text=(
                "Choose what you're experiencing. "
                "NetDoctor will run a focused check."
            ),
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(5, 14))

        self.buttons: list[tk.Button] = []

        self._choice(
            main,
            "My internet feels slow",
            "A small download and response-time check (up to 4 MiB).",
            self.start_slow,
        )

        self._choice(
            main,
            "My connection keeps dropping",
            "A short watch of public connections, roughly half a minute.",
            self.start_drops,
        )

        website_box = tk.Frame(
            main,
            bg=CARD,
            padx=12,
            pady=10,
        )
        website_box.pack(
            fill="x",
            pady=(0, 9),
        )

        tk.Label(
            website_box,
            text="A website won't open",
            font=("Segoe UI", 11, "bold"),
            bg=CARD,
            fg=WHITE,
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            website_box,
            text=(
                "Enter its HTTPS address. We check the server "
                "connection, not page content."
            ),
            font=("Segoe UI", 9),
            bg=CARD,
            fg=MUTED,
            anchor="w",
        ).pack(
            fill="x",
            pady=(2, 7),
        )

        row = tk.Frame(
            website_box,
            bg=CARD,
        )
        row.pack(fill="x")

        self.website_entry = tk.Entry(
            row,
            font=("Segoe UI", 11),
            bg=ALT,
            fg=WHITE,
            insertbackground=WHITE,
            relief="flat",
            borderwidth=7,
        )
        self.website_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 10),
        )

        website_button = tk.Button(
            row,
            text="Check website",
            command=self.start_website,
            bg=BLUE,
            fg=BG,
            activebackground=WHITE,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=6,
        )
        website_button.pack(side="right")

        self.buttons.append(website_button)

        self.website_entry.bind(
            "<Return>",
            lambda _event: self.start_website(),
        )

        self.progress = tk.Label(
            main,
            text="No extra tests have been started.",
            font=("Segoe UI", 10),
            bg=BG,
            fg=MUTED,
            anchor="w",
        )
        self.progress.pack(
            fill="x",
            pady=(7, 8),
        )

        answer = tk.Frame(
            main,
            bg=CARD,
            padx=15,
            pady=12,
        )
        answer.pack(
            fill="both",
            expand=True,
        )

        self.headline = tk.Label(
            answer,
            text="Select the problem you want to investigate",
            bg=CARD,
            fg=WHITE,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            justify="left",
            wraplength=740,
        )
        self.headline.pack(
            fill="x",
            pady=(0, 7),
        )

        self.explanation = tk.Label(
            answer,
            text=(
                "You'll get a clear explanation and "
                "a practical next step."
            ),
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=740,
        )
        self.explanation.pack(fill="x")

        tk.Label(
            answer,
            text="WHAT TO DO NEXT",
            bg=CARD,
            fg=BLUE,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(
            fill="x",
            pady=(13, 5),
        )

        self.action = tk.Label(
            answer,
            text="Choose a problem above to get recommendations.",
            bg=CARD,
            fg=WHITE,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=740,
        )
        self.action.pack(fill="x")

        self.evidence = tk.Label(
            answer,
            text="",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=740,
        )
        self.evidence.pack(
            fill="x",
            pady=(12, 0),
        )

        self.note = tk.Label(
            answer,
            text="No router, DNS, or Windows settings will be changed.",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=740,
        )
        self.note.pack(
            fill="x",
            pady=(9, 0),
        )

        self.window.bind(
            "<Configure>",
            self._on_resize,
        )

        self.window.after(
            100,
            self._poll,
        )

    def _choice(
        self,
        parent: tk.Widget,
        title: str,
        detail: str,
        action,
    ) -> None:
        panel = tk.Frame(
            parent,
            bg=CARD,
            padx=12,
            pady=8,
        )
        panel.pack(
            fill="x",
            pady=(0, 9),
        )

        button = tk.Button(
            panel,
            text=title,
            command=action,
            font=("Segoe UI", 11, "bold"),
            bg=ALT,
            fg=WHITE,
            activebackground=BLUE,
            relief="flat",
            padx=11,
            pady=7,
            anchor="w",
        )
        button.pack(
            side="left",
            padx=(0, 13),
        )

        tk.Label(
            panel,
            text=detail,
            font=("Segoe UI", 9),
            bg=CARD,
            fg=MUTED,
            anchor="w",
            justify="left",
        ).pack(
            side="left",
            fill="x",
            expand=True,
        )

        self.buttons.append(button)

    def _on_resize(self, _event=None) -> None:
        width = max(
            450,
            self.window.winfo_width() - 105,
        )

        for label in (
            self.headline,
            self.explanation,
            self.action,
            self.evidence,
            self.note,
        ):
            label.config(
                wraplength=width
            )

    def start_slow(self) -> None:
        if self.worker.running:
            return

        if not messagebox.askyesno(
            "Small download required",
            "To check whether downloads affect response times, "
            "NetDoctor will download up to 4 MiB of test data. "
            "This can use mobile data. Continue?",
            parent=self.window,
        ):
            return

        self._start("slow")

    def start_drops(self) -> None:
        self._start("drops")

    def start_website(self) -> None:
        self._start(
            "website",
            website=self.website_entry.get(),
        )

    def _start(
        self,
        problem: str,
        *,
        website: str = "",
    ) -> None:
        if self.closed or self.worker.running:
            return

        try:
            started = self.worker.start(
                problem,
                website=website,
            )
        except GuidanceInputError as exc:
            self.progress.config(
                text=str(exc),
                fg=WARN,
            )
            return

        if not started:
            return

        for button in self.buttons:
            button.config(state="disabled")

        self.website_entry.config(
            state="disabled"
        )

        self.headline.config(
            text="Checking...",
            fg=BLUE,
        )
        self.explanation.config(
            text=(
                "This check is running without "
                "blocking the window."
            )
        )
        self.action.config(
            text="NetDoctor will explain the results here."
        )
        self.evidence.config(text="")
        self.note.config(
            text="No network settings are being changed."
        )
        self.progress.config(
            text="Starting the selected check...",
            fg=MUTED,
        )

    def _poll(self) -> None:
        if self.closed:
            return

        finished = False

        while True:
            try:
                event = self.worker.events.get_nowait()
            except queue.Empty:
                break

            if event.kind == "progress":
                self.progress.config(
                    text=str(event.value),
                    fg=MUTED,
                )

            elif event.kind == "result":
                self._show_result(event.value)
                finished = True

            else:
                self.headline.config(
                    text="This check could not finish",
                    fg=WARN,
                )
                self.explanation.config(
                    text=str(event.value)
                )
                self.action.config(
                    text=(
                        "Check your connection "
                        "and try again."
                    )
                )
                self.progress.config(
                    text="Check unsuccessful.",
                    fg=WARN,
                )
                finished = True

        if finished:
            for button in self.buttons:
                button.config(state="normal")

            self.website_entry.config(
                state="normal"
            )

        self.window.after(
            100,
            self._poll,
        )

    def _show_result(
        self,
        report: GuidedResult,
    ) -> None:
        self.headline.config(
            text=report.headline,
            fg=WHITE,
        )
        self.explanation.config(
            text=report.explanation
        )
        self.action.config(
            text=report.next_step
        )
        self.evidence.config(
            text=(
                "WHAT WE MEASURED\n"
                + "\n".join(report.evidence)
            )
        )
        self.note.config(
            text=report.note
        )
        self.progress.config(
            text=(
                "Check completed. Choose another "
                "problem if needed."
            ),
            fg=GOOD,
        )

    def close(self) -> None:
        if self.closed:
            return

        if self.worker.running:
            self.worker.stop()
            # The loaded test has a byte cap but cannot
            # immediately cancel an active network read.

        self.closed = True
        self.window.destroy()

        if self.on_close is not None:
            self.on_close()
