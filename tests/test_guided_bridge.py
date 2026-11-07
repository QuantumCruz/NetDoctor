"""Offline tests for guided troubleshooting through the desktop bridge."""

import threading
from types import SimpleNamespace as NS

import pytest

from netdoctor.models import (
    Adapter,
    DefaultRoute,
    EndpointCheck,
    Snapshot,
)
from netdoctor.webdesktop import DashboardAPI


def network_snapshot():
    return Snapshot(
        adapters=(
            Adapter(
                index=7,
                name="Wi-Fi",
                description="Wireless adapter",
                status="Up",
                link_speed="866 Mbps",
                medium="Wi-Fi",
                ipv4=("192.168.1.10",),
                ipv6=(),
                dns=("1.1.1.1",),
            ),
        ),
        default_routes=(
            DefaultRoute(
                family="IPv4",
                interface_index=7,
                next_hop="192.168.1.1",
                route_metric=10,
                interface_metric=25,
            ),
        ),
        warnings=(),
    )


def doctor_report():
    return NS(
        latency=None,
        dns=NS(
            observations=(
                NS(status="answered"),
            )
        ),
        connectivity=NS(
            checks=(
                EndpointCheck(
                    "www.cloudflare.com",
                    True,
                    True,
                    "Connected",
                ),
                EndpointCheck(
                    "www.microsoft.com",
                    True,
                    True,
                    "Connected",
                ),
            )
        ),
    )


def website_report():
    return {
        "status": "responded",
        "stage": "complete",
        "headline": "Website responded over HTTPS",
        "explanation": "The HTTPS endpoint responded.",
        "next_step": "Compare download performance separately.",
        "http_status": 200,
        "target": "https://github.com/",
        "address_family": "IPv4",
        "dns_ms": 12.0,
        "tcp_ms": 25.0,
        "tls_ms": 30.0,
        "response_ms": 40.0,
    }


def test_guided_without_website_does_not_run_website_check(
    tmp_path,
):
    calls = []

    api = DashboardAPI(
        collector=lambda: network_snapshot(),
        diagnose=lambda snapshot: doctor_report(),
        website_checker=lambda target: calls.append(target),
        data_dir=tmp_path,
    )

    response = api.run_guided_troubleshooting()

    assert response["ok"] is True
    assert response["report"]["website"] is None
    assert len(response["report"]["steps"]) == 4
    assert calls == []


def test_guided_website_integration(tmp_path):
    targets = []

    def checker(target):
        targets.append(target)
        return website_report()

    api = DashboardAPI(
        collector=lambda: network_snapshot(),
        diagnose=lambda snapshot: doctor_report(),
        website_checker=checker,
        data_dir=tmp_path,
    )

    response = api.run_guided_troubleshooting(
        "github.com"
    )

    assert response["ok"] is True
    assert targets == ["github.com"]

    report = response["report"]

    assert report["website"]["http_status"] == 200
    assert report["steps"][2]["status"] == "confirmed"
    assert report["steps"][3]["status"] == "confirmed"


@pytest.mark.parametrize(
    "target",
    [
        None,
        123,
        "x" * 513,
        "http://github.com",
        "https://127.0.0.1",
        "https://localhost",
        "https://github.com:8080",
    ],
)
def test_invalid_targets_do_not_start_checks(
    tmp_path,
    target,
):
    calls = []

    api = DashboardAPI(
        collector=lambda: calls.append("collector"),
        diagnose=lambda snapshot: calls.append("doctor"),
        website_checker=lambda website: calls.append("website"),
        data_dir=tmp_path,
    )

    response = api.run_guided_troubleshooting(target)

    assert response["ok"] is False
    assert calls == []


def test_unexpected_errors_are_sanitized(tmp_path):
    def broken():
        raise RuntimeError("private implementation secret")

    api = DashboardAPI(
        collector=broken,
        data_dir=tmp_path,
    )

    response = api.run_guided_troubleshooting()

    assert response["ok"] is False
    assert "private implementation secret" not in str(response)
    assert not api._guided_lock.locked()


def test_invalid_website_report_is_rejected(tmp_path):
    api = DashboardAPI(
        collector=lambda: network_snapshot(),
        diagnose=lambda snapshot: doctor_report(),
        website_checker=lambda target: {"unexpected": True},
        data_dir=tmp_path,
    )

    response = api.run_guided_troubleshooting(
        "github.com"
    )

    assert response["ok"] is False
    assert "invalid report" in response["error"]
    assert not api._guided_lock.locked()
    assert not api._website_lock.locked()


def test_simultaneous_guided_runs_are_rejected(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    responses = []

    def collect():
        entered.set()
        assert release.wait(5)
        return network_snapshot()

    api = DashboardAPI(
        collector=collect,
        diagnose=lambda snapshot: doctor_report(),
        data_dir=tmp_path,
    )

    thread = threading.Thread(
        target=lambda: responses.append(
            api.run_guided_troubleshooting()
        )
    )

    thread.start()

    try:
        assert entered.wait(5)

        duplicate = api.run_guided_troubleshooting()

        assert duplicate["ok"] is False
        assert "already running" in duplicate["error"]

    finally:
        release.set()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert responses[0]["ok"] is True


def test_website_check_lock_is_shared(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    responses = []

    def checker(target):
        entered.set()
        assert release.wait(5)
        return website_report()

    api = DashboardAPI(
        collector=lambda: network_snapshot(),
        diagnose=lambda snapshot: doctor_report(),
        website_checker=checker,
        data_dir=tmp_path,
    )

    thread = threading.Thread(
        target=lambda: responses.append(
            api.check_website("github.com")
        )
    )

    thread.start()

    try:
        assert entered.wait(5)

        duplicate = api.run_guided_troubleshooting(
            "github.com"
        )

        assert duplicate["ok"] is False
        assert "already running" in duplicate["error"]

    finally:
        release.set()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert responses[0]["ok"] is True
    assert not api._website_lock.locked()


def test_no_guided_tests_run_during_api_creation(tmp_path):
    calls = []

    api = DashboardAPI(
        collector=lambda: calls.append("collector"),
        diagnose=lambda snapshot: calls.append("doctor"),
        website_checker=lambda target: calls.append("website"),
        data_dir=tmp_path,
    )

    assert api is not None
    assert calls == []