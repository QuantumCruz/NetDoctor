
"""Stage 15 history and monitor behaviour. No real network connections."""

from datetime import datetime, timezone
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.stability import (
    StabilityHistory,
    StabilityMonitor,
    StabilitySample,
    _gateway_address,
    take_sample,
)


def snap(hop="192.168.1.1"):
    return Snapshot(
        (
            Adapter(
                3,
                "WiFi",
                "Wireless",
                "Up",
                "650 Mbps",
                "Wi-Fi",
                ("192.168.1.8",),
                (),
                (),
            ),
        ),
        (
            DefaultRoute(
                "IPv4",
                3,
                hop,
                0,
                5,
            ),
        ),
        (),
    )


def sample(state="ok", ix=1):
    return StabilitySample(
        f"2026-10-24T11:00:{ix:02d}+00:00",
        state,
        state != "failed",
        state == "ok",
        None,
    )


def test_gateway_is_preferred_ipv4():
    assert _gateway_address(snap()) == "192.168.1.1"
    assert _gateway_address(snap("0.0.0.0")) is None
    assert _gateway_address(snap("not an IP")) is None


def test_two_connections_are_ok_and_echo_is_separate():
    output = take_sample(
        "192.168.1.1",
        tcp_probe=lambda *a, **k: SimpleNamespace(
            status="connected"
        ),
        icmp_probe=lambda *a, **k: SimpleNamespace(
            status="timeout"
        ),
        now=lambda: datetime(
            2026,
            10,
            24,
            tzinfo=timezone.utc,
        ),
    )

    assert output.state == "ok"
    assert output.gateway_reply is False
    assert output.checked_at.endswith("+00:00")


def test_one_destination_is_mixed():
    output = take_sample(
        None,
        tcp_probe=lambda address, **k: SimpleNamespace(
            status=(
                "connected"
                if address == "1.1.1.1"
                else "timeout"
            )
        ),
    )

    assert output.state == "mixed"
    assert output.gateway_reply is None


def test_two_timeouts_are_not_assigned_to_isp():
    output = take_sample(
        None,
        tcp_probe=lambda *a, **k: SimpleNamespace(
            status="timeout"
        ),
    )

    assert output.state == "failed"
    assert not output.first_ok
    assert not output.second_ok


def test_probe_exception_does_not_create_failure_sample():
    def boom(*a, **k):
        raise OSError("blocked")

    with pytest.raises(
        RuntimeError,
        match="could not run",
    ):
        take_sample(
            None,
            tcp_probe=boom,
        )


def test_local_history_is_persistent_and_bounded(tmp_path):
    path = tmp_path / "connection-history.sqlite3"
    store = StabilityHistory(
        path,
        max_rows=3,
    )

    for number in range(1, 6):
        store.append(
            sample(
                "ok" if number % 2 else "failed",
                number,
            )
        )

    rows = StabilityHistory(path).recent()

    assert len(rows) == 3
    assert rows[0]["checked_at"].endswith("03+00:00")
    assert rows[-1]["checked_at"].endswith("05+00:00")


def test_history_rejects_unbounded_query(tmp_path):
    history = StabilityHistory(
        tmp_path / "test.db"
    )

    for bad in (0, -1, 1001):
        with pytest.raises(ValueError):
            history.recent(bad)


def wait_for(condition, timeout=1.5):
    deadline = monotonic() + timeout

    while monotonic() < deadline:
        if condition():
            return True

        sleep(0.005)

    return False


def test_monitor_runs_one_sample_stops_and_keeps_history(tmp_path):
    observed = Event()

    def make(_gateway):
        observed.set()
        return sample()

    monitor = StabilityMonitor(
        StabilityHistory(
            tmp_path / "one.db"
        ),
        collector=snap,
        sampler=make,
        interval=1,
    )

    assert monitor.start(5)["ok"]
    assert observed.wait(1)

    assert wait_for(
        lambda: len(
            monitor.status()["samples"]
        ) > 0
    )

    assert not monitor.start(10)["ok"]
    assert monitor.stop()["ok"]

    assert wait_for(
        lambda: not monitor.status()["running"]
    )

    assert monitor.status()["counts"]["ok"] >= 1


def test_sampler_failure_stops_without_fake_outage(tmp_path):
    monitor = StabilityMonitor(
        StabilityHistory(
            tmp_path / "fail.db"
        ),
        collector=snap,
        sampler=lambda gateway: (
            _ for _ in ()
        ).throw(RuntimeError("bad")),
        interval=0.05,
    )

    assert monitor.start(5)["ok"]

    assert wait_for(
        lambda: not monitor.status()["running"]
    )

    status = monitor.status()

    assert (
        "without recording a false outage"
        in status["message"]
    )

    assert status["samples"] == []


def test_invalid_duration_and_idle_stop(tmp_path):
    monitor = StabilityMonitor(
        StabilityHistory(
            tmp_path / "none.db"
        ),
        collector=snap,
    )

    for bad in (0, 1, True, 60):
        assert not monitor.start(bad)["ok"]

    assert monitor.stop()["ok"]
    assert not monitor.status()["running"]


def test_collector_failure_still_allows_public_checks(tmp_path):
    seen = Event()

    def sample_it(gateway):
        assert gateway is None
        seen.set()
        return sample()

    monitor = StabilityMonitor(
        StabilityHistory(
            tmp_path / "collector.db"
        ),
        collector=lambda: (
            _ for _ in ()
        ).throw(
            RuntimeError("collector failed")
        ),
        sampler=sample_it,
        interval=1,
    )

    assert monitor.start(5)["ok"]
    assert seen.wait(1)

    monitor.stop()

    assert wait_for(
        lambda: not monitor.status()["running"]
    )
