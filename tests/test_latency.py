from unittest.mock import patch

import pytest

from netdoctor.icmp import EchoResult
from netdoctor.latency import (
    LatencyError,
    _summarize,
    measure_latency,
)
from netdoctor.models import Adapter, DefaultRoute, Snapshot


def _snapshot(route=True):
    adapter = Adapter(
        6,
        "WiFi",
        "Wireless",
        "Up",
        "866 Mbps",
        "Wi-Fi (inferred)",
        ("192.168.1.2",),
        (),
        ("192.168.1.1",),
    )

    routes = (
        (DefaultRoute(
            "IPv4",
            6,
            "192.168.1.1",
            10,
            25,
        ),)
        if route else ()
    )

    return Snapshot(
        (adapter,),
        routes,
        (),
    )


def _reply(ms):
    return EchoResult("reply", ms, "OK")


def _timeout():
    return EchoResult("timeout", None, "No response")


def test_summary_uses_real_samples_and_adjacent_successful_changes():
    samples = (
        _reply(10),
        _reply(15),
        _reply(10),
        _timeout(),
        _reply(30),
    )

    result = _summarize(
        "test",
        "1.1.1.1",
        "public",
        samples,
    )

    assert result.replies == 4
    assert result.timeouts == 1
    assert result.loss_percent == 20.0
    assert result.median_ms == 12.5
    assert result.p95_ms == 30
    assert result.variation_ms == 5.0


def test_all_unanswered_is_inconclusive_not_confirmed_loss():
    result = _summarize(
        "test",
        "1.1.1.1",
        "public",
        (_timeout(), _timeout()),
    )

    assert result.loss_percent is None
    assert result.median_ms is None


def test_transport_errors_cannot_be_mislabeled_as_packet_loss():
    result = _summarize(
        "test",
        "1.1.1.1",
        "public",
        (
            _reply(15),
            EchoResult("error", None, "System error"),
        ),
    )

    assert result.loss_percent is None
    assert result.errors == 1


def test_gateway_and_public_targets_are_measured():
    calls = []

    def probe(ip, *, timeout_ms):
        calls.append((ip, timeout_ms))
        return _reply(
            12 if ip == "192.168.1.1" else 32
        )

    report = measure_latency(
        _snapshot(),
        count=3,
        interval=0,
        probe=probe,
    )

    assert [
        r.address for r in report.targets
    ] == [
        "192.168.1.1",
        "1.1.1.1",
        "8.8.8.8",
    ]

    assert len(calls) == 9
    assert report.targets[0].median_ms == 12
    assert report.targets[1].median_ms == 32

    assert len(
        report.to_dict()["targets"][0]["samples"]
    ) == 3


def test_icmp_blocking_does_not_get_diagnosed_as_internet_failure():
    report = measure_latency(
        _snapshot(),
        count=2,
        interval=0,
        probe=lambda *_args, **_kwargs: _timeout(),
    )

    titles = [
        finding.title
        for finding in report.findings
    ]

    assert "Public ICMP results are inconclusive" in titles
    assert "Gateway ICMP replies were not confirmed" in titles

    assert all(
        "internet is down" not in item.explanation.lower()
        for item in report.findings
    )


def test_custom_host_replaces_public_defaults_and_keeps_gateway():
    calls = []

    def probe(ip, *, timeout_ms):
        calls.append(ip)
        return _reply(2)

    with patch(
        "netdoctor.latency.socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("203.0.113.5", 0))
        ],
    ):
        result = measure_latency(
            _snapshot(),
            count=2,
            interval=0,
            targets=("example.net",),
            probe=probe,
        )

    assert [
        r.address for r in result.targets
    ] == [
        "192.168.1.1",
        "203.0.113.5",
    ]

    assert calls == [
        "192.168.1.1",
        "192.168.1.1",
        "203.0.113.5",
        "203.0.113.5",
    ]


def test_no_route_skips_gateway_without_crashing():
    report = measure_latency(
        _snapshot(False),
        count=2,
        interval=0,
        probe=lambda *_args, **_kwargs: _reply(20),
    )

    assert len(report.targets) == 2

    assert any(
        f.title == "Gateway latency was not measured"
        for f in report.findings
    )


def test_interval_is_not_applied_after_last_probe():
    delays = []

    measure_latency(
        _snapshot(),
        count=2,
        interval=0.25,
        probe=lambda *_args, **_kwargs: _reply(20),
        sleep=delays.append,
    )

    assert delays == [0.25] * 3


def test_invalid_target_is_friendly_error():
    with patch(
        "netdoctor.latency.socket.getaddrinfo",
        side_effect=OSError("No DNS"),
    ):
        with pytest.raises(
            LatencyError,
            match="Could not resolve",
        ):
            measure_latency(
                _snapshot(),
                count=2,
                interval=0,
                targets=("invalid.test",),
                probe=lambda *_args, **_kwargs: _reply(1),
            )