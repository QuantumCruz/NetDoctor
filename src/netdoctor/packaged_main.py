"""NetDoctor's self-contained Windows entry point and offline bundle smoke check.

The development entry point is unchanged. A frozen build uses sys._MEIPASS to
locate bundled Vite assets, and deliberately requires Chromium WebView2.
"""

import json
import sys
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
    """Verify Vite output, including CSS loaded by JavaScript chunks.

    Vite may inject CSS with its JavaScript runtime rather than emit an HTML
    stylesheet link. In that case, compiled CSS inside the assets directory
    is valid. Referenced HTML assets must still exist.
    """
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

    # Vite/React may load CSS through JavaScript rather than from index.html.
    # Only use this fallback when HTML has no declared stylesheet.
    # Broken declared stylesheet references must still fail validation.
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


def launch() -> int:
    frontend = inspect_frontend()

    if not frontend["ok"]:
        _show_error(
            "NetDoctor's dashboard files are missing or incomplete. "
            "Keep the entire NetDoctor folder together and rebuild the app."
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

    except Exception:
        _show_error(
            "NetDoctor could not start its Windows dashboard. "
            "Check that Microsoft Edge WebView2 Runtime is installed, "
            "and keep the complete NetDoctor folder together."
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