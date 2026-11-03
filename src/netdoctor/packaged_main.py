
"""NetDoctor's self-contained Windows entry point and offline bundle smoke check.

A frozen build uses sys._MEIPASS for Vite assets and the Chromium WebView2
renderer. Startup failures are recorded locally, not discarded.
"""

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


REQUIRED_BRIDGE = (
    "get_overview",
    "load_previous_speed",
    "save_speed",
    "get_diagnosis_insights",
    "get_activity_outlook",
    "get_stability_status",
    "start_stability_watch",
    "stop_stability_watch",
    "check_public_connection",
    "check_loaded_latency",
    "get_network_context_status",
)


class _AssetReferences(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self.stylesheets = []
        self.root_present = False

    def handle_starttag(self, tag, attrs):
        properties = dict(attrs)

        if properties.get("id") == "root":
            self.root_present = True

        if tag == "script" and properties.get("src"):
            self.scripts.append(properties["src"])

        if (
            tag == "link"
            and properties.get("rel") == "stylesheet"
            and properties.get("href")
        ):
            self.stylesheets.append(properties["href"])


def frontend_directory() -> Path:
    """Find assets under the PyInstaller bundle or source project root."""
    bundle = (
        getattr(sys, "_MEIPASS", None)
        if getattr(sys, "frozen", False)
        else None
    )

    root = Path(bundle) if bundle else Path(__file__).resolve().parents[2]

    return root / "ui" / "dist"


def inspect_frontend(directory: Path | None = None) -> dict:
    """Verify Vite output, including CSS loaded by JavaScript chunks."""
    directory = Path(directory) if directory is not None else frontend_directory()
    index = directory / "index.html"

    problems = []
    js_count = 0
    css_count = 0

    if not index.is_file():
        return {
            "ok": False,
            "js_assets": 0,
            "css_assets": 0,
            "problems": ["Compiled index.html is missing."],
        }

    try:
        html = index.read_text(encoding="utf-8")
        parser = _AssetReferences()
        parser.feed(html)

    except (OSError, UnicodeError, ValueError):
        return {
            "ok": False,
            "js_assets": 0,
            "css_assets": 0,
            "problems": ["Compiled index.html could not be read."],
        }

    if not parser.root_present:
        problems.append("Dashboard root element is missing.")

    if not parser.scripts:
        problems.append("Compiled JavaScript entry is missing.")

    base = directory.resolve()

    for kind, urls in (
        ("script", parser.scripts),
        ("stylesheet", parser.stylesheets),
    ):
        for url in urls:
            parsed = urlsplit(url)
            relative = unquote(parsed.path)

            if (
                parsed.scheme
                or parsed.netloc
                or relative.startswith("/")
                or not relative
                or "\\" in relative
            ):
                problems.append(f"Non-local {kind} asset reference.")
                continue

            asset = (base / relative).resolve()

            if not asset.is_relative_to(base):
                problems.append(f"Asset path leaves the bundle: {kind}.")
                continue

            if not asset.is_file():
                problems.append(f"Referenced {kind} asset is missing.")
                continue

            if kind == "script" and asset.suffix == ".js":
                js_count += 1

            if kind == "stylesheet" and asset.suffix == ".css":
                css_count += 1

    if not parser.stylesheets:
        assets_dir = base / "assets"

        if assets_dir.is_dir():
            for css_file in assets_dir.rglob("*.css"):
                compiled = css_file.resolve()

                if (
                    compiled.is_relative_to(base)
                    and compiled.is_file()
                    and compiled.stat().st_size > 0
                ):
                    css_count += 1

    if not js_count:
        problems.append("No compiled JavaScript asset was verified.")

    if not css_count:
        problems.append("No compiled CSS asset was verified.")

    return {
        "ok": not problems,
        "js_assets": js_count,
        "css_assets": css_count,
        "problems": problems,
    }


def smoke_check(directory: Path | None = None) -> dict:
    """Check assets and bridge imports without network requests or a GUI."""
    assets = inspect_frontend(directory)
    missing_bridge = []

    try:
        from netdoctor.webdesktop import DashboardAPI

        missing_bridge = [
            name
            for name in REQUIRED_BRIDGE
            if not callable(getattr(DashboardAPI, name, None))
        ]

    except Exception:
        missing_bridge = [
            "Python dashboard bridge could not be imported."
        ]

    problems = list(assets["problems"])

    try:
        import webview

        if not callable(getattr(webview, "create_window", None)):
            problems.append(
                "Desktop windowing library is incomplete."
            )

    except Exception:
        problems.append(
            "Desktop windowing library could not be imported."
        )

    if missing_bridge:
        problems.append(
            "Required dashboard bridge methods are unavailable."
        )

    return {
        "ok": not problems,
        "frozen": bool(getattr(sys, "frozen", False)),
        "js_assets": assets["js_assets"],
        "css_assets": assets["css_assets"],
        "bridge_methods_checked": len(REQUIRED_BRIDGE),
        "problems": problems,
        "note": (
            "This does not verify the WebView2 renderer or visible buttons."
        ),
    }


def _startup_log_path() -> Path:
    """Keep exception details in the user's private app-data directory."""
    local_data = os.environ.get("LOCALAPPDATA")
    root = (
        Path(local_data) / "NetDoctor"
        if local_data
        else Path.home() / ".netdoctor"
    )
    return root / "logs" / "startup.log"


def _write_startup_error(phase: str, error: BaseException) -> Path | None:
    """Record the original traceback without requiring a console window."""
    path = _startup_log_path()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and path.stat().st_size > 1_048_576:
            archived = path.with_name("startup.previous.log")
            path.replace(archived)

        with path.open("a", encoding="utf-8") as output:
            output.write(
                "\n--- NetDoctor startup failure ---\n"
                f"UTC: {datetime.now(timezone.utc).isoformat()}\n"
                f"Stage: {phase}\n"
                f"Frozen: {bool(getattr(sys, 'frozen', False))}\n"
            )
            traceback.print_exception(
                type(error),
                error,
                error.__traceback__,
                file=output,
            )

        return path

    except OSError:
        return None


def _show_error(message: str) -> None:
    """Make frozen startup errors visible without a terminal window."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                message,
                "NetDoctor",
                0x10,
            )
            return

        except Exception:
            pass

    print(message, file=sys.stderr)


def _report_startup_error(
    stage: str,
    error: Exception,
    message: str,
) -> None:
    log_path = _write_startup_error(stage, error)

    if log_path is not None:
        _show_error(
            f"{message}\n\nTechnical details: {log_path}"
        )
    else:
        _show_error(
            f"{message}\n\nThe diagnostic log could not be saved."
        )


def launch() -> int:
    try:
        frontend = inspect_frontend()

    except Exception as exc:
        _report_startup_error(
            "frontend inspection",
            exc,
            "NetDoctor could not verify its bundled dashboard files.",
        )
        return 2

    if not frontend["ok"]:
        _report_startup_error(
            "frontend validation",
            RuntimeError("; ".join(frontend["problems"])),
            "NetDoctor's dashboard files are missing or incomplete. "
            "Keep the entire NetDoctor folder together.",
        )
        return 2

    try:
        import webview
        from netdoctor.webdesktop import DashboardAPI

        api = DashboardAPI()

        webview.create_window(
            "NetDoctor",
            url=str(frontend_directory() / "index.html"),
            js_api=api,
            width=1180,
            height=790,
            min_size=(930, 650),
        )

        try:
            webview.start(
                gui="edgechromium",
                http_server=True,
            )
        finally:
            api.shutdown()

        return 0

    except Exception as exc:
        _report_startup_error(
            "Windows dashboard initialization",
            exc,
            "NetDoctor could not start its Windows dashboard. "
            "The exact error has been saved for diagnosis.",
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    args = list(
        sys.argv[1:] if argv is None else argv
    )

    if len(args) == 2 and args[0] == "--smoke-report":
        result = smoke_check()

        try:
            destination = Path(args[1])

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            destination.write_text(
                json.dumps(result, indent=2),
                encoding="utf-8",
            )

        except OSError:
            return 2

        return 0 if result["ok"] else 2

    if args:
        _show_error(
            "Invalid NetDoctor argument. "
            "Use --smoke-report FILE for offline verification."
        )
        return 2

    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
