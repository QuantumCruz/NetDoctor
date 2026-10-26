"""Stage 22: persisted network separation and safe SQLite migration.

Offline only; no external IP probes or Windows configuration changes.
"""

import sqlite3
from datetime import datetime, timezone
from threading import Event
from time import monotonic, sleep

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.network_context import network_signature
from netdoctor.stability import (
    StabilityHistory,
    StabilityMonitor,
    StabilitySample,
)


def snapshot(gateway="192.168.1.1"):
    return Snapshot(
        (
            Adapter(
                6,
                "WiFi",
                "Intel wireless",
                "Up",
                "650 Mbps",
                "Wi-Fi",
                ("192.168.1.4",),
                (),
                (),
            ),
        ),
        (
            DefaultRoute(
                "IPv4",
                6,
                gateway,
                0,
                20,
            ),
        ),
        (),
    )


def sample(state="ok", second=0):
    return StabilitySample(
        datetime(
            2026, 10, 26, 12, 0, second,
            tzinfo=timezone.utc,
        ).isoformat(),
        state,
        state != "failed",
        state == "ok",
        None,
    )


def until(condition, timeout=2):
    end = monotonic() + timeout

    while monotonic() < end:
        if condition():
            return True

        sleep(0.005)

    return False


def test_sqlite_migration_retains_preexisting_samples(tmp_path):
    path = tmp_path / "old.sqlite3"

    with sqlite3.connect(path) as db:
        db.execute(
            """CREATE TABLE samples (
                id INTEGER PRIMARY KEY,
                checked_at TEXT NOT NULL,
                state TEXT NOT NULL,
                first_ok INTEGER NOT NULL,
                second_ok INTEGER NOT NULL,
                gateway_reply INTEGER
            )"""
        )

        db.execute(
            "INSERT INTO samples"
            "(checked_at,state,first_ok,second_ok,gateway_reply) "
            "VALUES (?,?,?,?,?)",
            (
                sample().checked_at,
                "ok",
                1,
                1,
                None,
            ),
        )

    history = StabilityHistory(path)

    assert len(history.recent()) == 1
    assert history.recent(network_key="new") == []

    history.append(
        sample("mixed", 1),
        network_key="new",
    )

    assert [
        item["state"]
        for item in history.recent()
    ] == ["ok", "mixed"]

    assert [
        item["state"]
        for item in history.recent(network_key="new")
    ] == ["mixed"]

    assert history.other_count("new") == 1


def test_separate_networks_do_not_mix_counts(tmp_path):
    history = StabilityHistory(
        tmp_path / "a.db"
    )

    a = network_signature(snapshot())
    b = network_signature(
        snapshot("10.0.0.1")
    )

    history.append(
        sample("ok"),
        network_key=a,
    )

    history.append(
        sample("failed", 1),
        network_key=b,
    )

    history.append(
        sample("mixed", 2)
    )

    assert [
        item["state"]
        for item in history.recent(network_key=a)
    ] == ["ok"]

    assert [
        item["state"]
        for item in history.recent(network_key=b)
    ] == ["failed"]

    assert history.other_count(a) == 2
    assert history.other_count(b) == 2


def test_watch_shows_only_current_network(tmp_path):
    active = [snapshot()]
    seen = Event()

    def sampler(_gateway):
        seen.set()
        return sample()

    history = StabilityHistory(
        tmp_path / "history.db"
    )

    history.append(
        sample("failed", 1),
        network_key=network_signature(
            snapshot("10.10.0.1")
        ),
    )

    monitor = StabilityMonitor(
        history,
        collector=lambda: active[0],
        sampler=sampler,
        interval=1,
    )

    assert monitor.start(5)["ok"]
    assert seen.wait(1)

    assert until(
        lambda: monitor.status()["counts"]["ok"] == 1
    )

    status = monitor.status()

    assert status["counts"] == {
        "ok": 1,
        "mixed": 0,
        "failed": 0,
    }

    assert status["other_network_count"] == 1
    assert status["history_scope"] == "current"

    monitor.stop()

    assert until(
        lambda: not monitor.status()["running"]
    )

    active[0] = snapshot("10.10.0.1")

    sleep(0.02)

    # Force a fresh snapshot without waiting for cache expiry.
    monitor._cache_time = float("-inf")

    switched = monitor.status()

    assert switched["counts"]["failed"] == 1
    assert switched["counts"]["ok"] == 0


def test_mid_session_route_switch_ends_monitor(tmp_path):
    active = [snapshot()]
    seen = Event()

    def sampler(_gateway):
        seen.set()
        return sample()

    monitor = StabilityMonitor(
        StabilityHistory(
            tmp_path / "route.db"
        ),
        collector=lambda: active[0],
        sampler=sampler,
        interval=0.06,
    )

    assert monitor.start(5)["ok"]
    assert seen.wait(1)

    active[0] = snapshot("192.168.55.1")

    assert until(
        lambda: not monitor.status()["running"]
    )

    status = monitor.status()

    assert (
        "configuration changed"
        in status["message"]
    )

    assert status["counts"]["ok"] == 0

    assert monitor.history.other_count(
        network_signature(active[0])
    ) == 1


def test_unidentified_session_visible_only_while_active(tmp_path):
    seen = Event()

    monitor = StabilityMonitor(
        StabilityHistory(
            tmp_path / "unknown.db"
        ),
        collector=lambda: None,
        sampler=lambda gateway: (
            seen.set() or sample()
        ),
        interval=1,
    )

    assert monitor.start(5)["ok"]
    assert seen.wait(1)

    assert until(
        lambda: monitor.status()["counts"]["ok"] == 1
    )

    assert monitor.status()["history_scope"] == "session"

    monitor.stop()

    assert until(
        lambda: not monitor.status()["running"]
    )

    assert (
        monitor.status()["history_scope"]
        == "unverified"
    )

    assert monitor.status()["samples"] == []
    assert len(monitor.history.recent()) == 1


def test_history_limit_remains_bounded_across_networks(tmp_path):
    history = StabilityHistory(
        tmp_path / "bounds.db",
        max_rows=3,
    )

    for index in range(5):
        history.append(
            sample("ok", index),
            network_key=(
                "a" if index % 2 else "b"
            ),
        )

    assert len(history.recent()) == 3

    assert (
        history.other_count("a")
        + len(history.recent(network_key="a"))
        == 3
    )