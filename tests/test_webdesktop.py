
"""Headless tests for the React desktop's tightly scoped Python bridge."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from netdoctor.webdesktop import DashboardAPI


def bridge(tmp_path: Path) -> DashboardAPI:
    return DashboardAPI(
        collector=lambda: "snapshot",
        diagnose=lambda item: SimpleNamespace(
            status="reachable",
            interface="Wi-Fi",
            gateway="192.168.0.1",
        ),
        presenter=lambda report: SimpleNamespace(
            headline="Basic internet connection works",
            explanation="Two test destinations responded.",
            observation="No confirmed outage.",
            next_step="Run the speed test when you choose.",
        ),
        data_dir=tmp_path,
    )


def test_bridge_returns_uninvented_connection_fields(tmp_path):
    result = bridge(tmp_path).get_overview()
    assert result["status"] == "reachable"
    assert result["interface"] == "Wi-Fi"
    assert result["vpn"] == "Not checked"
    assert result["isp"] == "Not checked"
    assert result["cgnat"] == "Not checked"


def test_unexpected_diagnostics_fail_safely(tmp_path):
    api = DashboardAPI(
        collector=lambda: (_ for _ in ()).throw(RuntimeError("secret")),
        data_dir=tmp_path,
    )
    result = api.get_overview()
    assert result["status"] == "unverified"
    assert "secret" not in json.dumps(result)


def test_saves_and_reloads_last_measured_speed(tmp_path):
    api = bridge(tmp_path)
    reading = {
        "tested_at": "2026-10-23T12:00:00Z",
        "download_mbps": 42.5649,
        "upload_mbps": 9.12,
        "latency_ms": 18.5,
        "jitter_ms": 2.7,
    }

    assert api.load_previous_speed() is None
    assert api.save_speed(reading) == {"saved": True}

    result = api.load_previous_speed()
    assert result["download_mbps"] == 42.565
    assert result["upload_mbps"] == 9.12
    assert result["tested_at"].endswith("+00:00")


@pytest.mark.parametrize("bad", [
    {"tested_at": "invalid", "download_mbps": 20},
    {"tested_at": "2026-10-23T12:00:00", "download_mbps": 20},
    {"tested_at": "2026-10-23T12:00:00Z", "download_mbps": -3},
    {"tested_at": "2026-10-23T12:00:00Z", "upload_mbps": float("nan")},
    {"tested_at": "2026-10-23T12:00:00Z", "download_mbps": True},
    {"tested_at": "2026-10-23T12:00:00Z", "download_mbps": "100"},
])
def test_invalid_speed_results_are_not_persisted(tmp_path, bad):
    api = bridge(tmp_path)
    with pytest.raises(ValueError):
        api.save_speed(bad)
    assert api.load_previous_speed() is None


def test_corrupted_cache_is_ignored(tmp_path):
    (tmp_path / "last-speed.json").write_text(
        "not json",
        encoding="utf8",
    )
    assert bridge(tmp_path).load_previous_speed() is None
