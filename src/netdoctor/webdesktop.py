
"""React/Vite NetDoctor dashboard with a narrow Python diagnostic bridge.

The GUI is served locally by pywebview. No externally reachable control API,
no network changes, and no speed-test traffic until the user requests it.
"""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from netdoctor.desktop_support import explain
from netdoctor.doctor import run_doctor
from netdoctor.windows import collect_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_BUILD = PROJECT_ROOT / "ui" / "dist" / "index.html"


def _data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "NetDoctor" if local else Path.home() / ".netdoctor"


def _value(raw: Any, *, maximum: float) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Invalid speed measurement type.")
    value = float(raw)
    if not math.isfinite(value) or value < 0 or value > maximum:
        raise ValueError("Speed measurement is outside supported bounds.")
    return round(value, 3)


class DashboardAPI:
    """Expose only the three operations the local dashboard needs."""

    def __init__(
        self,
        *,
        collector: Callable = collect_snapshot,
        diagnose: Callable = run_doctor,
        presenter: Callable = explain,
        data_dir: Path | None = None,
    ) -> None:
        self._collector = collector
        self._diagnose = diagnose
        self._presenter = presenter
        self._data_dir = data_dir or _data_dir()

    def get_overview(self) -> dict:
        try:
            snapshot = self._collector()
            report = self._diagnose(snapshot)
            guide = self._presenter(report)
            return {
                "status": report.status,
                "headline": guide.headline,
                "explanation": guide.explanation,
                "observation": guide.observation,
                "next_step": guide.next_step,
                "interface": report.interface or "Not determined",
                "gateway": report.gateway or "Not determined",
                "vpn": "Not checked",
                "hotspot": "Not checked",
                "isp": "Not checked",
                "cgnat": "Not checked",
            }
        except Exception:
            return {
                "status": "unverified",
                "headline": "Connection check unavailable",
                "explanation": "NetDoctor could not finish the short network check.",
                "observation": "No reliable conclusion was collected.",
                "next_step": "Check your Windows connection and try again.",
                "interface": "Not determined",
                "gateway": "Not determined",
                "vpn": "Not checked",
                "hotspot": "Not checked",
                "isp": "Not checked",
                "cgnat": "Not checked",
            }

    def load_previous_speed(self) -> dict | None:
        path = self._data_dir / "last-speed.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            return self._validated(raw)
        except (OSError, ValueError, TypeError, KeyError):
            return None

    @staticmethod
    def _validated(reading: dict) -> dict:
        if not isinstance(reading, dict):
            raise ValueError("Invalid speed report.")
        tested_at = reading.get("tested_at")
        if not isinstance(tested_at, str) or len(tested_at) > 40:
            raise ValueError("Invalid test timestamp.")
        try:
            parsed = datetime.fromisoformat(tested_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Invalid test timestamp.") from exc
        if parsed.tzinfo is None:
            raise ValueError("Test timestamp must include a timezone.")
        return {
            "tested_at": parsed.astimezone(timezone.utc).isoformat(),
            "download_mbps": _value(reading.get("download_mbps"), maximum=100000),
            "upload_mbps": _value(reading.get("upload_mbps"), maximum=100000),
            "latency_ms": _value(reading.get("latency_ms"), maximum=60000),
            "jitter_ms": _value(reading.get("jitter_ms"), maximum=60000),
        }

    def save_speed(self, reading: dict) -> dict:
        """Persist only bounded numeric results; no hostnames or network secrets."""
        validated = self._validated(reading)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        path = self._data_dir / "last-speed.json"
        temp = self._data_dir / "last-speed.json.tmp"
        try:
            temp.write_text(json.dumps(validated, indent=2), encoding="utf-8")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        return {"saved": True}


def main() -> int:
    if not WEB_BUILD.is_file():
        print(
            "NetDoctor dashboard has not been built. "
            "Run 'npm install' and 'npm run build' inside ui/ first."
        )
        return 2

    try:
        import webview
    except ImportError:
        print(
            "Install the desktop requirements: "
            "python -m pip install -e '.[desktop]'"
        )
        return 2

    webview.create_window(
        "NetDoctor",
        url=str(WEB_BUILD),
        js_api=DashboardAPI(),
        width=1180,
        height=790,
        min_size=(930, 650),
    )
    webview.start(http_server=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
