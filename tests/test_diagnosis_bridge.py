
"""Stage 18 bridge: combining existing results cannot initiate a new probe."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from netdoctor.webdesktop import DashboardAPI


class Monitor:
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append("history")
        return {"samples": []}


def api(tmp_path, monitor=None, loaded=None):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "No background network calls are allowed"
        )

    return DashboardAPI(
        data_dir=tmp_path,
        monitor=monitor or Monitor(),
        loaded_test=loaded or forbidden,
        collector=forbidden,
        diagnose=forbidden,
        intelligence=forbidden,
        public_lookup=forbidden,
    )


def reading():
    return {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "download_mbps": 42,
        "upload_mbps": 8,
        "latency_ms": 20,
        "jitter_ms": 2,
    }


def test_read_only_diagnosis_does_not_run_probes(tmp_path):
    monitor = Monitor()

    result = api(
        tmp_path, monitor
    ).get_diagnosis_insights(
        {"status": "reachable"},
        reading(),
    )

    assert result["headline"]
    assert monitor.calls == ["history"]


def test_saved_speed_can_be_used_without_live_speed_test(tmp_path):
    instance = api(tmp_path)
    instance.save_speed(reading())

    assert instance.get_diagnosis_insights(
        {"status": "reachable"}
    )["speed_fresh"]


def test_successful_loaded_test_available_to_diagnosis(tmp_path):
    instance = api(
        tmp_path,
        loaded=lambda **kw: "report",
    )

    stamp = datetime.now(timezone.utc).isoformat()

    with patch(
        "netdoctor.webdesktop.summarize_loaded",
        return_value={
            "tested_at": stamp,
            "status": "increase_observed",
            "change_ms": 60,
        },
    ):
        assert instance.check_loaded_latency()["ok"]

    result = instance.get_diagnosis_insights(
        {"status": "reachable"}
    )

    assert any(
        item["code"] == "load_delay"
        for item in result["findings"]
    )


def test_invalid_speed_and_monitor_failure_fail_open(tmp_path):
    instance = api(tmp_path)

    instance._monitor.status = lambda: (
        _ for _ in ()
    ).throw(RuntimeError("hidden"))

    result = instance.get_diagnosis_insights(
        {"status": "reachable"},
        {"tested_at": "garbage"},
    )

    assert result["speed_fresh"] is False
    assert "hidden" not in str(result)
