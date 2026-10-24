
"""Local React dashboard bridge: network diagnosis, privacy-aware Wi-Fi,
and opt-in public exit-IP lookups. Speed results stay on this device.
"""

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from netdoctor.desktop_support import explain
from netdoctor.doctor import run_doctor
from netdoctor.network_intel import collect_intelligence
from netdoctor.public_network import PublicLookupError, inspect_public_network
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


def _wifi_adapter_fallback(snapshot, network: dict) -> None:
    """Use Windows adapter metadata even when location-gated WLAN API fails.

    A reported adapter link speed is a negotiated link, not an internet speed.
    Do not label unavailable WLAN telemetry as disabled Wi-Fi.
    """
    wifi = network.get("wifi")
    if not isinstance(wifi, dict):
        return
    candidates = [a for a in snapshot.adapters if a.is_up and (
        re.search(r"wi[ -]?fi|wireless|wlan|802\.11", f"{a.name} {a.description}", re.I)
    )]
    route = snapshot.preferred_route("IPv4") or snapshot.preferred_route("IPv6")
    selected = next((a for a in candidates if route and a.index == route.interface_index), None)
    if selected is None and len(candidates) == 1:
        selected = candidates[0]
    if selected is None:
        return
    wifi["adapter_name"] = selected.name
    wifi["adapter_description"] = selected.description
    wifi["adapter_link_speed"] = selected.link_speed or None
    if wifi.get("status") != "Connected":
        wifi.update({
            "status": "Connected (details unavailable)",
            "signal_percent": None,
            "signal_label": "Unavailable",
            "detail": (
                "Windows reports an active Wi-Fi adapter, but detailed signal and "
                "network-name information was not available. Windows location privacy "
                "restrictions are one possible reason. NetDoctor does not bypass them. "
                "Adapter link speed is not internet download speed."
            ),
        })


class DashboardAPI:
    """Expose read-only dashboard calls, plus explicit speed result persistence."""

    def __init__(
        self,
        *,
        collector: Callable = collect_snapshot,
        diagnose: Callable = run_doctor,
        presenter: Callable = explain,
        intelligence: Callable = collect_intelligence,
        public_lookup: Callable = inspect_public_network,
        data_dir: Path | None = None,
    ) -> None:
        self._collector = collector
        self._diagnose = diagnose
        self._presenter = presenter
        self._intelligence = intelligence
        self._public_lookup = public_lookup
        self._data_dir = data_dir or _data_dir()

    @staticmethod
    def _empty_overview() -> dict:
        return {
            "status": "unverified",
            "headline": "Connection check unavailable",
            "explanation": "NetDoctor could not finish the short network check.",
            "observation": "No reliable conclusion was collected.",
            "next_step": "Check your Windows connection and try again.",
            "interface": "Not determined",
            "gateway": "Not determined",
            "vpn": "Not checked",
            "proxy": "Not checked",
            "hotspot": "Not determined",
            "isp": "Not checked",
            "cgnat": "Not checked",
            "network": None,
        }

    def get_overview(self) -> dict:
        try:
            snapshot = self._collector()
            report = self._diagnose(snapshot)
            guide = self._presenter(report)
        except Exception:
            return self._empty_overview()
        output = {
            **self._empty_overview(),
            "status": report.status,
            "headline": guide.headline,
            "explanation": guide.explanation,
            "observation": guide.observation,
            "next_step": guide.next_step,
            "interface": report.interface or "Not determined",
            "gateway": report.gateway or "Not determined",
        }
        try:
            detail = self._intelligence(snapshot).to_dict()
            _wifi_adapter_fallback(snapshot, detail)
            output.update({
                "network": detail,
                "vpn": detail["vpn"]["status"],
                "proxy": detail["proxy"]["status"],
                "hotspot": detail["hotspot"],
                "isp": detail["isp"],
                "cgnat": detail["cgnat"],
            })
        except Exception:
            pass
        return output

    def check_public_connection(self, router_wan_ipv4: str = "") -> dict:
        """Only invoked by the user's button; never by the overview call.

        WAN input is validated locally and never sent to the lookup service.
        """
        try:
            if not isinstance(router_wan_ipv4, str):
                raise ValueError("Enter a numeric router WAN IPv4 address or leave it empty.")
            snapshot = self._collector()
            result = self._public_lookup(
                snapshot, router_wan_ipv4=router_wan_ipv4
            )
            return {"ok": True, "report": result.to_dict()}
        except (ValueError, PublicLookupError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            return {"ok": False, "error": (
                "Public connection information is unavailable right now. "
                "No network settings were changed."
            )}

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
        print("NetDoctor dashboard has not been built. Run 'npm install' "
              "and 'npm run build' inside ui/ first.")
        return 2
    try:
        import webview
    except ImportError:
        print("Install the desktop requirements: python -m pip install -e '.[desktop]'")
        return 2
    webview.create_window(
        "NetDoctor", url=str(WEB_BUILD), js_api=DashboardAPI(),
        width=1180, height=790, min_size=(930, 650),
    )
    webview.start(http_server=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
