
"""Activity insights never initiate network probes or conflate old history."""

from datetime import datetime, timezone

from netdoctor.webdesktop import DashboardAPI


class FakeMonitor:
    def __init__(self, samples=None):
        self._samples = samples or []
        self.calls = []

    def status(self):
        self.calls.append("status")
        return {
            "samples": self._samples,
            "running": False,
        }

    def start(self, minutes):
        raise AssertionError("Monitoring must not start")

    def stop(self):
        self.calls.append("stop")
        return {"ok": True}


def reading():
    return {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "download_mbps": 35.7,
        "upload_mbps": 21.7,
        "latency_ms": 135,
        "jitter_ms": 5,
    }


def make(tmp_path, monitor=None):
    return DashboardAPI(
        data_dir=tmp_path,
        monitor=monitor or FakeMonitor(),
        collector=lambda: (
            _ for _ in ()
        ).throw(
            AssertionError("collector must not run")
        ),
        public_lookup=lambda *_a, **_k: (
            _ for _ in ()
        ).throw(
            AssertionError("lookup must not run")
        ),
    )


def test_activity_insights_do_not_call_network_or_start_monitor(tmp_path):
    monitor = FakeMonitor()
    result = make(tmp_path, monitor).get_activity_outlook(reading())

    assert len(result["activities"]) == 4
    assert monitor.calls == ["status"]


def test_activity_insights_can_use_saved_speed(tmp_path):
    api = make(tmp_path)
    api.save_speed(reading())

    result = api.get_activity_outlook()

    assert result["tested_at"] is not None
    assert "4K" in result["activities"][0]["status"]


def test_no_speed_history_shows_not_tested(tmp_path):
    result = make(tmp_path).get_activity_outlook()

    assert result["activities"][0]["status"] == "Speed test needed"


def test_corrupted_client_input_is_not_interpreted(tmp_path):
    result = make(tmp_path).get_activity_outlook({
        "tested_at": "yesterday",
        "download_mbps": 1e300,
    })

    assert result["activities"][0]["status"] == "Speed test needed"
