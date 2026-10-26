"""Route changes keep saved speed from informing current-network diagnosis."""

import json

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.webdesktop import DashboardAPI


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


def reading():
    return {
        "tested_at": "2026-10-26T11:00:00+00:00",
        "download_mbps": 30.0,
        "upload_mbps": 10.0,
        "latency_ms": 40.0,
        "jitter_ms": 5.0,
    }


def test_saved_speed_is_tagged_and_matches_before_route_switch(tmp_path):
    active = [snapshot()]

    api = DashboardAPI(
        data_dir=tmp_path,
        collector=lambda: active[0],
    )

    assert (
        api.get_network_context_status()["state"]
        == "no_reading"
    )

    assert api.save_speed(reading()) == {
        "saved": True
    }

    raw = json.loads(
        (
            tmp_path / "last-speed.json"
        ).read_text(encoding="utf-8")
    )

    assert raw["network_signature"].startswith("n1-")

    assert (
        api.load_previous_speed()["network_context"]["state"]
        == "matching"
    )


def test_network_switch_excludes_old_speed_from_diagnosis(tmp_path):
    active = [snapshot()]

    api = DashboardAPI(
        data_dir=tmp_path,
        collector=lambda: active[0],
    )

    api.save_speed(reading())

    active[0] = snapshot(
        gateway="192.168.2.1"
    )

    cached = api.load_previous_speed()

    assert (
        cached["network_context"]["state"]
        == "changed"
    )

    assert (
        api.get_network_context_status()["state"]
        == "changed"
    )

    diagnosis = api.get_diagnosis_insights(
        {"status": "reachable"},
        cached,
    )

    assert diagnosis["speed_fresh"] is False

    activity = api.get_activity_outlook(cached)

    assert (
        activity["activities"][0]["status"]
        == "Speed test needed"
    )


def test_old_legacy_speed_file_is_warning_not_corruption(tmp_path):
    (
        tmp_path / "last-speed.json"
    ).write_text(
        json.dumps(reading()),
        encoding="utf-8",
    )

    api = DashboardAPI(
        data_dir=tmp_path,
        collector=snapshot,
    )

    old = api.load_previous_speed()

    assert old["download_mbps"] == 30.0

    assert (
        old["network_context"]["state"]
        == "unverified"
    )


def test_unavailable_route_keeps_speed_but_context_unknown(tmp_path):
    api = DashboardAPI(
        data_dir=tmp_path,
        collector=lambda: None,
    )

    api.save_speed(reading())

    assert (
        api.get_network_context_status()["state"]
        == "unverified"
    )

    assert (
        api.load_previous_speed()["download_mbps"]
        == 30.0
    )


def test_context_lookup_does_not_initiate_external_tests(tmp_path):
    calls = []

    def collector():
        calls.append("local snapshot")
        return snapshot()

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "An external test must not run."
        )

    api = DashboardAPI(
        data_dir=tmp_path,
        collector=collector,
        loaded_test=forbidden,
        public_lookup=forbidden,
    )

    api.save_speed(reading())

    assert (
        api.get_network_context_status()["state"]
        == "matching"
    )

    assert calls == [
        "local snapshot",
        "local snapshot",
    ]