
"""Entirely offline tests for cloud-region TCP measurement and ranking."""

import json
import socket
from itertools import count

import pytest

from netdoctor.cloud_regions import (
    ENDPOINTS,
    RegionEndpoint,
    compare_regions,
    main,
    measure_region,
)


ENDPOINT = ENDPOINTS[0]


def resolved(*args):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("203.0.113.7", 443),
        )
    ]


def test_endpoints_include_only_curated_providers_and_https_hosts():
    assert {
        item.provider for item in ENDPOINTS
    } == {"AWS", "Oracle"}

    assert len({
        item.hostname for item in ENDPOINTS
    }) == len(ENDPOINTS)

    assert all(
        item.hostname.endswith(
            ("amazonaws.com", "oraclecloud.com")
        )
        for item in ENDPOINTS
    )


def test_successful_handshakes_compute_median_and_variation():
    timings = iter([25, 29, 28])
    addresses = []

    def connect(address, port, timeout):
        addresses.append((address, port, timeout))
        return next(timings)

    result = measure_region(
        ENDPOINT,
        resolver=resolved,
        connector=connect,
    )

    assert result.status == "measured"
    assert result.median_ms == 28
    assert result.variation_ms == 1
    assert result.samples_ms == (25, 29, 28)

    assert addresses == [
        ("203.0.113.7", 443, 1.5)
    ] * 3


def test_partial_connection_is_not_called_packet_loss():
    attempts = iter([
        OSError("blocked"),
        41,
        45,
    ])

    def connect(*_):
        result = next(attempts)

        if isinstance(result, Exception):
            raise result

        return result

    result = measure_region(
        ENDPOINT,
        resolver=resolved,
        connector=connect,
    )

    assert result.status == "partial"
    assert result.median_ms == 43
    assert result.successful == 2
    assert "not a packet-loss measurement" in result.note


def test_resolution_failure_does_not_probe():
    def fail(*_):
        raise socket.gaierror("cannot resolve")

    result = measure_region(
        ENDPOINT,
        resolver=fail,
        connector=lambda *_: pytest.fail(
            "Unexpected TCP call"
        ),
    )

    assert result.status == "unavailable"
    assert result.successful == 0
    assert result.median_ms is None


def test_unreachable_endpoint_is_inconclusive():
    def fail(*_):
        raise TimeoutError("timeout")

    result = measure_region(
        ENDPOINT,
        resolver=resolved,
        connector=fail,
    )

    assert result.status == "unavailable"
    assert "packet loss" not in result.note.lower()


def test_nonfinite_probes_are_discarded():
    times = iter([
        float("nan"),
        float("inf"),
        12,
    ])

    result = measure_region(
        ENDPOINT,
        resolver=resolved,
        connector=lambda *_: next(times),
    )

    assert result.status == "partial"
    assert result.samples_ms == (12,)
    assert result.variation_ms is None


@pytest.mark.parametrize(
    "attempts,timeout",
    [
        (0, 1),
        (6, 1),
        (True, 1),
        (3, 0),
        (3, float("nan")),
        (3, 6),
    ],
)
def test_limits_rejected_before_network(attempts, timeout):
    with pytest.raises(ValueError):
        measure_region(
            ENDPOINT,
            attempts=attempts,
            timeout=timeout,
            resolver=lambda *_: pytest.fail(
                "Unexpected DNS call"
            ),
        )


def test_comparison_ranks_only_measured_endpoints():
    targets = (
        RegionEndpoint(
            "AWS", "a", "A", "a.amazonaws.com"
        ),
        RegionEndpoint(
            "Oracle", "b", "B", "b.oraclecloud.com"
        ),
        RegionEndpoint(
            "AWS", "c", "C", "c.amazonaws.com"
        ),
    )

    timings = {
        "203.0.113.1": 30,
        "203.0.113.2": 15,
        "203.0.113.3": 100,
    }

    def resolve(host, *args):
        addresses = {
            "a.amazonaws.com": "203.0.113.1",
            "b.oraclecloud.com": "203.0.113.2",
            "c.amazonaws.com": "203.0.113.3",
        }

        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (addresses[host], 443),
            )
        ]

    def connect(address, port, timeout):
        if address.endswith(".3"):
            raise TimeoutError("not reachable")

        return timings[address]

    report = compare_regions(
        endpoints=targets,
        resolver=resolve,
        connector=connect,
        workers=2,
    )

    assert [
        row["region"] for row in report["results"]
    ] == ["b", "a", "c"]

    assert (
        report["best_observed_endpoint"]["region"] == "b"
    )

    assert report["results"][-1]["status"] == "unavailable"
    assert "TCP" in report["method"]

    json.dumps(report)


def test_one_successful_connection_cannot_be_declared_best():
    calls = count()

    def connect(*_):
        if next(calls) == 0:
            return 18

        raise TimeoutError("timeout")

    report = compare_regions(
        endpoints=(ENDPOINT,),
        resolver=resolved,
        connector=connect,
    )

    assert report["best_observed_endpoint"] is None


def test_provider_filter_never_probes_others():
    report = compare_regions(
        provider="AWS",
        resolver=resolved,
        connector=lambda *_: 27,
    )

    assert len(report["results"]) == 5

    assert all(
        row["provider"] == "AWS"
        for row in report["results"]
    )


def test_bad_filters_are_rejected():
    with pytest.raises(ValueError):
        compare_regions(
            provider="Unknown",
            resolver=resolved,
        )

    with pytest.raises(ValueError):
        compare_regions(
            workers=0,
            resolver=resolved,
        )

    with pytest.raises(ValueError):
        compare_regions(
            endpoints=[],
            resolver=resolved,
        )


def test_cli_is_noninteractive_when_comparison_is_mocked(
    monkeypatch,
    capsys,
):
    from netdoctor import cloud_regions

    monkeypatch.setattr(
        cloud_regions,
        "compare_regions",
        lambda **kwargs: {
            "results": [],
            "best_observed_endpoint": None,
            "disclaimer": "TCP only",
            "method": "TCP",
        },
    )

    assert main(["--json"]) == 0

    assert json.loads(
        capsys.readouterr().out
    )["method"] == "TCP"
