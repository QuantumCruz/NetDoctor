
"""Direct DNS wire protocol and interpretation tests, requiring no internet access."""

import socket
import struct
from unittest.mock import patch

import pytest

from netdoctor.dnsdiagnostics import (
    DnsDiagnosticError, _question_for, diagnose_dns, query_dns,
)
from netdoctor.models import Adapter, DefaultRoute, Snapshot


def _snapshot(dns=("192.168.1.1", "8.8.8.8"), route=True):
    adapters = (Adapter(6, "WiFi", "Wireless", "Up", "866 Mbps",
                        "Wi-Fi (inferred)", ("192.168.1.100",), (), dns),)
    routes = (DefaultRoute("IPv4", 6, "192.168.1.1", 0, 35),) if route else ()
    return Snapshot(adapters, routes, ())


def _response(query, *, flags=0x8180, answers=((1, b"\x5d\xb8\xd7\x0e"),)):
    request_id = struct.unpack_from("!H", query)[0]
    data = struct.pack("!HHHHHH", request_id, flags, 1, len(answers), 0, 0) + query[12:]
    for rr_type, rdata in answers:
        data += b"\xc0\x0c" + struct.pack("!HHIH", rr_type, 1, 60, len(rdata)) + rdata
    return data


def test_wire_query_encodes_hostname_and_A_class_IN():
    question = _question_for("Example.COM.")
    assert question == b"\x07example\x03com\x00\x00\x01\x00\x01"


@pytest.mark.parametrize("hostname", ["", "a..com", "bad_name.com", "a"*64 + ".com", ".com"])
def test_bad_hostname_rejected_before_socket(hostname):
    with pytest.raises(DnsDiagnosticError):
        query_dns("1.1.1.1", hostname, exchange=lambda *_: (_ for _ in ()).throw(AssertionError()))


def test_direct_valid_a_record_is_timed_and_parsed():
    with patch("netdoctor.dnsdiagnostics.time.perf_counter", side_effect=[5, 5.025]):
        result = query_dns("1.1.1.1", "example.com", exchange=lambda _, packet, __: _response(packet))
    assert result.status == "answered"
    assert result.elapsed_ms == 25.0
    assert result.addresses == ("93.184.215.14",)
    assert result.response_code == 0


def test_nxdomain_is_not_described_as_udp_timeout():
    result = query_dns("1.1.1.1", "missing.example.com", exchange=lambda _, packet, __: _response(packet, flags=0x8183, answers=()))
    assert result.status == "nxdomain"
    assert result.response_code == 3


def test_servfail_and_truncation_are_distinct():
    servfail = query_dns("1.1.1.1", "example.com", exchange=lambda _, p, __: _response(p, flags=0x8182, answers=()))
    truncated = query_dns("1.1.1.1", "example.com", exchange=lambda _, p, __: _response(p, flags=0x8380, answers=()))
    assert servfail.status == "server_error"
    assert truncated.status == "truncated"


def test_wrong_transaction_id_is_rejected():
    result = query_dns("1.1.1.1", "example.com", exchange=lambda _, p, __: b"\xff\xff" + _response(p)[2:])
    assert result.status == "invalid_response"
    assert not result.addresses


def test_malformed_answer_is_rejected_safely():
    result = query_dns("1.1.1.1", "example.com", exchange=lambda _, p, __: _response(p)[:-2])
    assert result.status == "invalid_response"


def test_response_without_A_record_is_not_transport_failure():
    result = query_dns("1.1.1.1", "example.com", exchange=lambda _, p, __: _response(p, answers=((5, b"\x04test\x00"),)))
    assert result.status == "no_a_record"


def test_timeout_is_not_claimed_as_windows_dns_failure():
    result = query_dns("1.1.1.1", "example.com", exchange=lambda *_: (_ for _ in ()).throw(socket.timeout()))
    assert result.status == "timeout"
    assert "direct UDP" in result.detail


def test_transport_error_distinct_from_timeout():
    result = query_dns("1.1.1.1", "example.com", exchange=lambda *_: (_ for _ in ()).throw(OSError(101, "unreachable")))
    assert result.status == "transport_error"


def test_query_targets_configured_servers_of_default_route_only():
    requests = []

    def exchange(server, hostname, *, timeout):
        requests.append((server, hostname))
        return query_dns(server, hostname, timeout=timeout, exchange=lambda _, packet, __: _response(packet))

    report = diagnose_dns(_snapshot(), hostnames=("example.com",), query=exchange)
    assert requests == [("192.168.1.1", "example.com"), ("8.8.8.8", "example.com")]
    assert len(report.observations) == 2
    assert report.findings[0].severity == "good"
    assert report.to_dict()["observations"][0]["status"] == "answered"


def test_no_route_does_not_guess_a_dns_server():
    report = diagnose_dns(_snapshot(route=False))
    assert not report.resolvers and not report.observations
    assert "could not be selected" in report.findings[0].title


def test_ipv6_only_dns_addresses_are_not_treated_as_ipv4():
    report = diagnose_dns(_snapshot(dns=("2001:4860:4860::8888",)))
    assert not report.observations
    assert "No IPv4 DNS server" in report.findings[0].title


def test_limits_hostname_count_before_network_calls():
    with pytest.raises(DnsDiagnosticError):
        diagnose_dns(_snapshot(), hostnames=("a.com", "b.com", "c.com", "d.com"))
