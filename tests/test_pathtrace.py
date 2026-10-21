
import ctypes
import ipaddress
import sys
from unittest.mock import patch

import pytest

from netdoctor.icmp import ProbeError, _ReplyHeader
from netdoctor.pathtrace import (
    _IPOptions32,
    HopProbe,
    probe_hop_ipv4,
    trace_paths,
)


def _reply(status, address, rtt):
    def send(handle, dst, payload, size, options, output, output_size, timeout):
        assert output_size >= 128
        assert handle == 99
        assert ctypes.cast(options, ctypes.POINTER(_IPOptions32)).contents.ttl == 4
        header = ctypes.cast(output, ctypes.POINTER(_ReplyHeader)).contents
        header.status = status
        header.address = int.from_bytes(ipaddress.IPv4Address(address).packed, sys.byteorder)
        header.round_trip_time = rtt
        return 1
    return send


def test_native_option_struct_uses_documented_eight_byte_layout():
    assert ctypes.sizeof(_IPOptions32) == 8
    assert _IPOptions32.options_data.offset == 4


def test_native_ttl_expired_records_router_address_and_closes_handle():
    closed = []
    with patch(
        "netdoctor.pathtrace._open_api",
        return_value=(lambda: 99, _reply(11013, "192.168.1.1", 3), closed.append),
    ):
        result = probe_hop_ipv4("1.1.1.1", ttl=4)
    assert result == HopProbe("hop", "192.168.1.1", 3.0, "Router reported TTL expired.")
    assert closed == [99]


def test_native_destination_response_stops_trace():
    with patch(
        "netdoctor.pathtrace._open_api",
        return_value=(lambda: 99, _reply(0, "1.1.1.1", 16), lambda _: 1),
    ):
        result = probe_hop_ipv4("1.1.1.1", ttl=4)
    assert result.status == "reached"
    assert result.rtt_ms == 16


def test_native_zero_replies_timeout_is_not_an_outage_claim():
    with (
        patch(
            "netdoctor.pathtrace._open_api",
            return_value=(lambda: 99, lambda *args: 0, lambda _: 1),
        ),
        patch("netdoctor.pathtrace.ctypes.get_last_error", create=True, return_value=11010),
    ):
        result = probe_hop_ipv4("1.1.1.1", ttl=3)
    assert result.status == "timeout"
    assert result.address is None


def test_native_unknown_failure_recorded_as_error():
    with (
        patch(
            "netdoctor.pathtrace._open_api",
            return_value=(lambda: 99, lambda *args: 0, lambda _: 1),
        ),
        patch("netdoctor.pathtrace.ctypes.get_last_error", create=True, return_value=87),
    ):
        result = probe_hop_ipv4("1.1.1.1", ttl=4)
    assert result.status == "error"


@pytest.mark.parametrize(
    "ttl,timeout", [(0, 800), (256, 800), (1, 10), (1, 4000)]
)
def test_invalid_probe_parameters_do_not_send(ttl, timeout):
    with patch(
        "netdoctor.pathtrace._open_api",
        side_effect=AssertionError("native call"),
    ):
        with pytest.raises(ValueError):
            probe_hop_ipv4("1.1.1.1", ttl=ttl, timeout_ms=timeout)


def test_native_invalid_ipv4_rejected_without_api_call():
    with patch(
        "netdoctor.pathtrace._open_api",
        side_effect=AssertionError("native call"),
    ):
        with pytest.raises(ProbeError):
            probe_hop_ipv4("2001:db8::1", ttl=4)


def test_trace_stops_at_destination_and_retains_silent_intermediate_hop():
    calls = []

    def fake(address, *, ttl, timeout_ms):
        calls.append(ttl)
        if ttl == 1:
            return HopProbe("hop", "192.168.1.1", 3, "router")
        if ttl == 2:
            return HopProbe("timeout", None, None, "filtered")
        return HopProbe("reached", address, 24, "arrived")

    report = trace_paths(targets=("1.1.1.1",), max_hops=12, probe=fake)
    assert calls == [1, 2, 3]
    assert report.targets[0].reached
    assert report.targets[0].hops[1].probes[0].status == "timeout"
    assert report.targets[0].stop_reason == "destination_reached"


def test_all_filtered_hops_are_inconclusive():
    report = trace_paths(
        targets=("1.1.1.1",),
        max_hops=3,
        probe=lambda *args, **kwargs: HopProbe("timeout", None, None, "filtered"),
    )
    assert report.targets[0].stop_reason == "hop_limit"
    assert "not fully observed" in report.findings[0].title
    assert "network outage" not in report.findings[0].explanation


def test_probe_error_stops_without_calling_next_hop():
    calls = []

    def fake(address, *, ttl, timeout_ms):
        calls.append(ttl)
        return HopProbe("error", None, None, "bad API")

    report = trace_paths(targets=("1.1.1.1",), max_hops=8, probe=fake)
    assert calls == [1]
    assert report.targets[0].stop_reason == "probe_error"


def test_unreachable_is_recorded_without_blame():
    report = trace_paths(
        targets=("1.1.1.1",),
        max_hops=1,
        probe=lambda *args, **kwargs: HopProbe(
            "unreachable", "192.168.1.1", None, "unreachable"
        ),
    )
    assert any("unreachable response" in finding.title for finding in report.findings)
    assert not report.targets[0].reached


def test_default_targets_are_two_distinct_public_addresses():
    report = trace_paths(
        max_hops=1,
        probe=lambda *args, **kwargs: HopProbe("timeout", None, None, "filtered"),
    )
    assert [t.address for t in report.targets] == ["1.1.1.1", "8.8.8.8"]


@pytest.mark.parametrize(
    "hops,probes,timeout",
    [
        (0, 1, 800),
        (25, 1, 800),
        (5, 0, 800),
        (5, 3, 800),
        (5, 1, 99),
        (5, 1, 3001),
    ],
)
def test_trace_bounds_enforced(hops, probes, timeout):
    with pytest.raises(ValueError):
        trace_paths(max_hops=hops, probes_per_hop=probes, timeout_ms=timeout)
