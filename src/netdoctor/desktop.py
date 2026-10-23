
"""NetDoctor desktop: plain-language diagnosis and optional guided troubleshooting.

Only the Tk main thread updates widgets. Networking runs in background workers.
Neither downloads nor ongoing monitoring start automatically.
"""

import datetime as dt
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from netdoctor import __version__
from netdoctor.desktop_support import (
    DiagnosticWorker,
    WorkerFailure,
    explain,
    export_content,
    text_report,
)
from netdoctor.doctor import DoctorReport
from netdoctor.troubleshoot_window import TroubleshootingWindow

BG = "#0e1726"
CARD = "#19283d"
ALT = "#1e324b"
WHITE = "#f1f5fa"
MUTED = "#bac9d9"
BLUE = "#8ab5ff"
GOOD = "#75dfb7"
WARN = "#ffd18b"


class NetDoctorDesktop:
    """Main overview stays minimal; problem-specific checks open separately."""

    def __init__(
        self,
        root: tk.Tk,
        worker: DiagnosticWorker | None = None,
    ) -> None:
        self.root = root
        self.worker = worker or DiagnosticWorker()
        self.report: DoctorReport | None = None
        self.checked_at = ""
        self.closed = False

        self._details_window: tk.Toplevel | None = None
        self._details_text: tk.Text | None = None
        self._guided: TroubleshootingWindow | None = None

        root.title(f"NetDoctor {__version__}")
        root.geometry("1000x790")
        root.minsize(760, 680)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)

        outer = tk.Frame(
            root,
            bg=BG,
            padx=26,
            pady=17,
        )
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer,
            text="NetDoctor",
            font=("Segoe UI", 25, "bold"),
            bg=BG,
            fg=WHITE,
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            outer,
            text=(
                "Understand your connection "
                "and find the right next step."
            ),
            font=("Segoe UI", 10),
            bg=BG,
            fg=MUTED,
            anchor="w",
        ).pack(
            fill="x",
            pady=(0, 11),
        )

        toolbar = tk.Frame(outer, bg=BG)
        toolbar.pack(
            fill="x",
            pady=(0, 7),
        )

        self.help_button = self._button(
            toolbar,
            "Help with a problem",
            self.open_help,
            BLUE,
            BG,
        )
        self.run_button = self._button(
            toolbar,
            "Check again",
            self.start,
            ALT,
            WHITE,
        )
        self.save_button = self._button(
            toolbar,
            "Save report",
            self.save,
            ALT,
            WHITE,
        )
        self.copy_button = self._button(
            toolbar,
            "Copy report",
            self.copy,
            ALT,
            WHITE,
        )
        self.details_button = self._button(
            toolbar,
            "Technical details",
            self.open_details,
            ALT,
            WHITE,
        )

        for button in (
            self.save_button,
            self.copy_button,
            self.details_button,
        ):
            button.config(state="disabled")

        self.progress = tk.Label(
            outer,
            text="Preparing your first connection check...",
            font=("Segoe UI", 9),
            bg=BG,
            fg=MUTED,
            anchor="w",
        )
        self.progress.pack(
            fill="x",
            pady=(0, 13),
        )

        hero = tk.Frame(
            outer,
            bg=CARD,
            padx=19,
            pady=14,
        )
        hero.pack(
            fill="x",
            pady=(0, 11),
        )

        self.headline = tk.Label(
            hero,
            text="Checking your connection...",
            font=("Segoe UI", 17, "bold"),
            bg=CARD,
            fg=BLUE,
            anchor="w",
            justify="left",
        )
        self.headline.pack(fill="x")

        self.summary = tk.Label(
            hero,
            text=(
                "We will check basic internet access, "
                "website addresses and replies."
            ),
            font=("Segoe UI", 11),
            bg=CARD,
            fg=WHITE,
            anchor="w",
            justify="left",
            wraplength=850,
        )
        self.summary.pack(
            fill="x",
            pady=(7, 0),
        )

        tk.Label(
            outer,
            text="What we checked",
            font=("Segoe UI", 12, "bold"),
            bg=BG,
            fg=WHITE,
            anchor="w",
        ).pack(
            fill="x",
            pady=(1, 7),
        )

        cards = tk.Frame(
            outer,
            bg=BG,
        )
        cards.pack(
            fill="x",
            pady=(0, 11),
        )

        self.card_results: list[tk.Label] = []
        self.card_descriptions: list[tk.Label] = []

        for index, title in enumerate((
            "Internet connections",
            "Finding websites",
            "Quick replies",
        )):
            cards.grid_columnconfigure(
                index,
                weight=1,
                uniform="checks",
            )

            body = tk.Frame(
                cards,
                bg=CARD,
                padx=12,
                pady=10,
            )
            body.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0, 7) if index < 2 else 0,
            )

            tk.Label(
                body,
                text=title,
                font=("Segoe UI", 10, "bold"),
                bg=CARD,
                fg=MUTED,
                anchor="w",
            ).pack(fill="x")

            result = tk.Label(
                body,
                text="Checking...",
                font=("Segoe UI", 12, "bold"),
                bg=CARD,
                fg=WHITE,
                anchor="w",
            )
            result.pack(
                fill="x",
                pady=(6, 3),
            )

            description = tk.Label(
                body,
                text="Collecting results...",
                font=("Segoe UI", 9),
                bg=CARD,
                fg=MUTED,
                anchor="nw",
                justify="left",
                wraplength=250,
                height=3,
            )
            description.pack(fill="x")

            self.card_results.append(result)
            self.card_descriptions.append(description)

        observation = tk.Frame(
            outer,
            bg=CARD,
            padx=19,
            pady=13,
        )
        observation.pack(
            fill="x",
            pady=(0, 9),
        )

        tk.Label(
            observation,
            text="WHAT WE NOTICED",
            font=("Segoe UI", 9, "bold"),
            bg=CARD,
            fg=MUTED,
            anchor="w",
        ).pack(fill="x")

        self.observation_title = tk.Label(
            observation,
            text="Gathering evidence...",
            font=("Segoe UI", 12, "bold"),
            bg=CARD,
            fg=WHITE,
            anchor="w",
            justify="left",
        )
        self.observation_title.pack(
            fill="x",
            pady=(5, 3),
        )

        self.observation_body = tk.Label(
            observation,
            text=(
                "NetDoctor will explain anything "
                "worth checking."
            ),
            font=("Segoe UI", 10),
            bg=CARD,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=850,
        )
        self.observation_body.pack(fill="x")

        action = tk.Frame(
            outer,
            bg=ALT,
            padx=19,
            pady=13,
        )
        action.pack(
            fill="x",
            pady=(0, 10),
        )

        tk.Label(
            action,
            text="WHAT TO DO NEXT",
            font=("Segoe UI", 9, "bold"),
            bg=ALT,
            fg=BLUE,
            anchor="w",
        ).pack(fill="x")

        self.action_body = tk.Label(
            action,
            text="Your next step will appear after the check.",
            font=("Segoe UI", 11),
            bg=ALT,
            fg=WHITE,
            anchor="w",
            justify="left",
            wraplength=850,
        )
        self.action_body.pack(
            fill="x",
            pady=(5, 0),
        )

        self.footnote = tk.Label(
            outer,
            text=(
                "Quick check: no automatic downloads or "
                "settings changes. Choose 'Help with a problem' "
                "for targeted tests."
            ),
            font=("Segoe UI", 9),
            bg=BG,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=850,
        )
        self.footnote.pack(
            fill="x",
            side="bottom",
        )

        root.bind(
            "<Configure>",
            self._resize_labels,
        )
        root.after(100, self._poll)
        root.after(250, self.start)

    @staticmethod
    def _button(
        parent: tk.Widget,
        label: str,
        callback,
        bg: str,
        fg: str,
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=label,
            command=callback,
            bg=bg,
            fg=fg,
            activebackground=BLUE,
            activeforeground=BG,
            disabledforeground=MUTED,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=7,
            cursor="hand2",
            takefocus=True,
        )
        button.pack(
            side="left",
            padx=(0, 8),
        )
        return button

    def _resize_labels(self, _event=None) -> None:
        width = max(
            420,
            self.root.winfo_width() - 105,
        )

        for label in (
            self.summary,
            self.observation_body,
            self.action_body,
            self.footnote,
        ):
            label.config(
                wraplength=width
            )

        for label in self.card_descriptions:
            label.config(
                wraplength=max(
                    160,
                    (self.root.winfo_width() - 135) // 3 - 24,
                )
            )

    def open_help(self) -> None:
        if self.closed:
            return

        if self._guided is not None and not self._guided.closed:
            self._guided.window.lift()
            self._guided.window.focus_set()
            return

        self._guided = TroubleshootingWindow(
            self.root,
            on_close=self._clear_help,
        )

    def _clear_help(self) -> None:
        self._guided = None

    def start(self) -> None:
        if self.closed or not self.worker.start():
            return

        self.report = None
        self.checked_at = ""
        self.run_button.config(state="disabled")

        for button in (
            self.save_button,
            self.copy_button,
            self.details_button,
        ):
            button.config(state="disabled")

        self.headline.config(
            text="Checking your connection...",
            fg=BLUE,
        )
        self.summary.config(
            text="We're running a few small, read-only checks."
        )
        self.observation_title.config(
            text="Gathering evidence...",
            fg=WHITE,
        )
        self.observation_body.config(
            text="We'll explain what the results mean."
        )
        self.action_body.config(
            text="Your next step will appear after the check."
        )
        self.progress.config(
            text="Reading Windows network settings..."
        )

        for result, description in zip(
            self.card_results,
            self.card_descriptions,
        ):
            result.config(
                text="Checking...",
                fg=MUTED,
            )
            description.config(
                text="Collecting results..."
            )

    def _poll(self) -> None:
        if self.closed:
            return

        while True:
            try:
                event = self.worker.events.get_nowait()
            except queue.Empty:
                break

            if event.kind == "progress":
                self.progress.config(
                    text=str(event.value)
                )
            elif event.kind == "success":
                self._show_report(event.value)
            elif event.kind == "failure":
                self._show_failure(event.value)

        self.root.after(
            100,
            self._poll,
        )

    def _show_report(
        self,
        report: DoctorReport,
    ) -> None:
        self.report = report
        self.checked_at = (
            dt.datetime.now()
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S %Z")
        )

        guide = explain(report)

        colors = {
            "good": GOOD,
            "warning": WARN,
            "neutral": MUTED,
        }

        self.headline.config(
            text=guide.headline,
            fg=colors[guide.tone],
        )
        self.summary.config(
            text=guide.explanation
        )
        self.observation_title.config(
            text=guide.observation_title,
            fg=colors[guide.observation_tone],
        )
        self.observation_body.config(
            text=guide.observation
        )
        self.action_body.config(
            text=guide.next_step
        )

        for index, card in enumerate(guide.checks):
            self.card_results[index].config(
                text=card.result,
                fg=colors[card.tone],
            )
            self.card_descriptions[index].config(
                text=card.explanation
            )

        self.progress.config(
            text=f"Last checked: {dt.datetime.now():%I:%M %p}"
        )

        self.run_button.config(state="normal")

        for button in (
            self.save_button,
            self.copy_button,
            self.details_button,
        ):
            button.config(state="normal")

        self._refresh_details()

    def _show_failure(
        self,
        failure: WorkerFailure,
    ) -> None:
        self.headline.config(
            text="We couldn't finish the check",
            fg=WARN,
        )
        self.summary.config(
            text=f"{failure.code}: {failure.message}"
        )
        self.observation_title.config(
            text="No reliable conclusion yet",
            fg=WARN,
        )
        self.observation_body.config(
            text=(
                "The check stopped before we had enough "
                "information. No network settings were changed."
            )
        )
        self.action_body.config(
            text="Check that Windows is connected, then try again."
        )
        self.progress.config(
            text="Check unsuccessful. You can retry."
        )

        for result, description in zip(
            self.card_results,
            self.card_descriptions,
        ):
            result.config(
                text="Not checked",
                fg=MUTED,
            )
            description.config(
                text="No reliable result for this run."
            )

        self.run_button.config(state="normal")

    def _refresh_details(self) -> None:
        if self.report is None or self._details_text is None:
            return

        if (
            self._details_window is None
            or not self._details_window.winfo_exists()
        ):
            return

        self._details_text.config(
            state="normal"
        )
        self._details_text.delete(
            "1.0",
            "end",
        )
        self._details_text.insert(
            "end",
            text_report(
                self.report,
                checked_at=self.checked_at,
            ),
        )
        self._details_text.config(
            state="disabled"
        )

    def open_details(self) -> None:
        if self.report is None:
            return

        if (
            self._details_window is not None
            and self._details_window.winfo_exists()
        ):
            self._details_window.lift()
            self._details_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title(
            "NetDoctor - Detailed network evidence"
        )
        window.geometry("800x580")
        window.minsize(550, 350)
        window.configure(bg=BG)

        frame = tk.Frame(
            window,
            bg=BG,
            padx=16,
            pady=16,
        )
        frame.pack(
            fill="both",
            expand=True,
        )

        tk.Label(
            frame,
            text="Detailed network evidence",
            font=("Segoe UI", 16, "bold"),
            bg=BG,
            fg=WHITE,
            anchor="w",
        ).pack(
            fill="x",
            pady=(0, 5),
        )

        tk.Label(
            frame,
            text=(
                "For troubleshooting or sharing with someone "
                "who understands networking."
            ),
            font=("Segoe UI", 10),
            bg=BG,
            fg=MUTED,
            anchor="w",
        ).pack(
            fill="x",
            pady=(0, 11),
        )

        content = tk.Frame(
            frame,
            bg=CARD,
        )
        content.pack(
            fill="both",
            expand=True,
        )

        text_widget = tk.Text(
            content,
            wrap="word",
            font=("Consolas", 10),
            bg=CARD,
            fg=WHITE,
            selectbackground=ALT,
            relief="flat",
            padx=13,
            pady=11,
        )

        scrollbar = tk.Scrollbar(
            content,
            command=text_widget.yview,
        )
        text_widget.config(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )
        text_widget.pack(
            side="left",
            fill="both",
            expand=True,
        )

        self._details_window = window
        self._details_text = text_widget
        self._refresh_details()

    def save(self) -> None:
        if self.report is None:
            return

        path = filedialog.asksaveasfilename(
            title="Save NetDoctor report",
            defaultextension=".txt",
            initialfile=(
                f"NetDoctor-"
                f"{dt.datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
            ),
            filetypes=[
                ("Readable report", "*.txt"),
                ("Full JSON data", "*.json"),
            ],
        )

        if not path:
            return

        kind = (
            "json"
            if Path(path).suffix.lower() == ".json"
            else "txt"
        )

        try:
            Path(path).write_text(
                export_content(
                    self.report,
                    kind=kind,
                    checked_at=self.checked_at,
                ),
                encoding="utf-8",
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror(
                "Could not save report",
                str(exc),
                parent=self.root,
            )
            return

        self.progress.config(
            text=f"Saved {Path(path).name}"
        )

    def copy(self) -> None:
        if self.report is None:
            return

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(
                text_report(
                    self.report,
                    checked_at=self.checked_at,
                )
            )
            self.root.update_idletasks()
        except tk.TclError:
            messagebox.showerror(
                "Clipboard unavailable",
                "Could not copy the report.",
                parent=self.root,
            )
        else:
            self.progress.config(
                text="Report copied to clipboard."
            )

    def close(self) -> None:
        if self.closed:
            return

        if self._guided is not None and not self._guided.closed:
            self._guided.close()

        self.closed = True
        self.root.destroy()


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError:
        return 1

    NetDoctorDesktop(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
