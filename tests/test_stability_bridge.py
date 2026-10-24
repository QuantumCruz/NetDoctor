
"""Stage 15 pywebview bridge: stability actions remain explicit and isolated."""

from types import SimpleNamespace

from netdoctor.webdesktop import DashboardAPI


class FakeMonitor:
    def __init__(self):
        self.calls = []

    def start(self, minutes):
        self.calls.append(
            ("start", minutes)
        )

        return {
            "ok": True,
            "message": "Stability watch started.",
        }

    def stop(self):
        self.calls.append(
            ("stop",)
        )

        return {
            "ok": True,
            "message": "Monitoring stopped.",
        }

    def status(self):
        self.calls.append(
            ("status",)
        )

        return {
            "running": False,
            "samples": [],
            "counts": {
                "ok": 0,
                "mixed": 0,
                "failed": 0,
            },
        }


def test_overview_does_not_start_stability_watch():
    monitor = FakeMonitor()

    api = DashboardAPI(
        monitor=monitor,
        collector=lambda: "snapshot",
        diagnose=lambda _: SimpleNamespace(
            status="reachable",
            interface="WiFi",
            gateway="router",
        ),
        presenter=lambda _: SimpleNamespace(
            headline="Working",
            explanation="OK",
            observation="No issue",
            next_step="None",
        ),
        intelligence=lambda _: SimpleNamespace(
            to_dict=lambda: {
                "wifi": {
                    "status": "Not available",
                },
                "vpn": {
                    "status": "Not checked",
                },
                "proxy": {
                    "status": "Not checked",
                },
                "hotspot": "Not determined",
                "isp": "Not checked",
                "cgnat": "Not checked",
            }
        ),
    )

    assert api.get_overview()["status"] == "reachable"
    assert monitor.calls == []


def test_monitor_controls_are_explicit():
    monitor = FakeMonitor()
    api = DashboardAPI(
        monitor=monitor
    )

    assert api.start_stability_watch(5)["ok"]

    assert (
        api.get_stability_status()["running"]
        is False
    )

    assert api.stop_stability_watch()["ok"]

    assert monitor.calls == [
        ("start", 5),
        ("status",),
        ("stop",),
    ]


def test_shutdown_stops_monitor():
    monitor = FakeMonitor()
    api = DashboardAPI(
        monitor=monitor
    )

    api.shutdown()

    assert monitor.calls == [
        ("stop",),
    ]


def test_monitor_failures_do_not_leak_exceptions():
    monitor = FakeMonitor()

    def fail(*args):
        raise RuntimeError(
            "private detail"
        )

    monitor.start = fail

    api = DashboardAPI(
        monitor=monitor
    )

    result = api.start_stability_watch(10)

    assert not result["ok"]
    assert "private detail" not in result["message"]
