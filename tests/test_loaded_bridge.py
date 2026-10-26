
"""Loaded-latency is opt-in, single-flight and does not leak internal failures."""

import threading
from types import SimpleNamespace
from unittest.mock import patch

from netdoctor.webdesktop import DashboardAPI


def test_reading_activity_outlook_never_runs_loaded_download(tmp_path):
    calls = []
    api = DashboardAPI(
        data_dir=tmp_path,
        monitor=SimpleNamespace(status=lambda: {"samples": []}),
        loaded_test=lambda **kwargs: calls.append(kwargs),
    )
    assert len(api.get_activity_outlook()["activities"]) == 4
    assert calls == []


def test_explicit_loaded_measurement_uses_four_mib_and_ten_seconds(tmp_path):
    arguments = []
    api = DashboardAPI(
        data_dir=tmp_path,
        loaded_test=lambda **kwargs: arguments.append(kwargs) or "report",
    )
    with patch("netdoctor.webdesktop.summarize_loaded", return_value={"status": "inconclusive"}):
        result = api.check_loaded_latency()
    assert result == {"ok": True, "result": {"status": "inconclusive"}}
    assert arguments == [{"size_mib": 4, "timeout": 10.0}]


def test_concurrent_tests_are_rejected(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    def blocked(**kwargs):
        entered.set()
        assert release.wait(2)
        return "report"

    api = DashboardAPI(data_dir=tmp_path, loaded_test=blocked)
    replies = []
    with patch("netdoctor.webdesktop.summarize_loaded", return_value={}):
        worker = threading.Thread(target=lambda: replies.append(api.check_loaded_latency()))
        worker.start()
        try:
            assert entered.wait(1)
            busy = api.check_loaded_latency()
            assert not busy["ok"]
            assert "already in progress" in busy["error"]
        finally:
            release.set()
            worker.join(2)
    assert replies == [{"ok": True, "result": {}}]


def test_internal_errors_are_sanitized(tmp_path):
    def raises(**kwargs):
        raise RuntimeError("my private environment variable")

    result = DashboardAPI(data_dir=tmp_path, loaded_test=raises).check_loaded_latency()
    assert result["ok"] is False
    assert "private environment" not in result["error"]


def test_previous_speed_is_not_replaced_by_loaded_check(tmp_path):
    api = DashboardAPI(
        data_dir=tmp_path,
        loaded_test=lambda **kwargs: "report",
    )
    reading = {
        "tested_at": "2026-10-26T08:30:00Z",
        "download_mbps": 35.7,
        "upload_mbps": 20.0,
        "latency_ms": 120,
        "jitter_ms": 5,
    }
    api.save_speed(reading)
    with patch("netdoctor.webdesktop.summarize_loaded", return_value={}):
        assert api.check_loaded_latency()["ok"]
    assert api.load_previous_speed()["download_mbps"] == 35.7
