import socket
from unittest.mock import patch

import pytest

from netdoctor.crosscheck import (
    TcpAttempt,
    _summarize_tcp,
    connect_tcp_ipv4,
    run_crosscheck,
)
from netdoctor.icmp import EchoResult
from netdoctor.models import Adapter, DefaultRoute, Snapshot


def _snapshot():
    return Snapshot(
        (
            Adapter(
                6,
                "Wi-Fi",
                "Wireless adapter",
                "Up",
                "866 Mbps",
                "Wi-Fi (inferred)",
                ("192.168.1.50",),
                (),
                ("192.168.1.1",),
            ),
        ),
        (
            DefaultRoute(
                "IPv4", 6, "192.168.1.1", 10, 25
            ),
        ),
        (),
    )


def _echo(address, *, timeout_ms):
    return EchoResult(
        "reply",
        (
            4 if address == "192.168.1.1"
            else 170 if address == "1.1.1.1"
            else 30
        ),
        "reply",
    )


def _tcp(address, *, port, timeout):
    return TcpAttempt(
        "connected",
        32 if address == "8.8.8.8" else 42,
        "connected",
    )


def test_tcp_ipv4_connect_measures_handshake_and_closes_socket():
    class FakeSocket:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

        def settimeout(self, timeout):
            assert timeout == 1.0

        def connect(self, address):
            assert address == ("1.1.1.1", 443)

    fake = FakeSocket()

    with (
        patch(
            "netdoctor.crosscheck.socket.socket",
            return_value=fake,
        ),
        patch(
            "netdoctor.crosscheck.time.perf_counter",
            side_effect=[5, 5.05],
        ),
    ):
        result = connect_tcp_ipv4(
            "1.1.1.1",
            timeout=1.0,
        )

    assert result.status == "connected"
    assert result.connect_ms == 50.0
    assert fake.closed


def test_tcp_timeout_is_not_reported_as_packet_loss():
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def settimeout(self, value):
            pass

        def connect(self, address):
            raise socket.timeout("timeout")

    with patch(
        "netdoctor.crosscheck.socket.socket",
        return_value=FakeSocket(),
    ):
        result = connect_tcp_ipv4("8.8.8.8")

    assert result.status == "timeout"
    assert result.connect_ms is None


def test_tcp_refusal_classified_separately():
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def settimeout(self, value):
            pass

        def connect(self, address):
            raise ConnectionRefusedError("closed")

    with patch(
        "netdoctor.crosscheck.socket.socket",
        return_value=FakeSocket(),
    ):
        result = connect_tcp_ipv4("127.0.0.1")

    assert result.status == "refused"


def test_socket_error_does_not_crash_diagnosis():
    with patch(
        "netdoctor.crosscheck.socket.socket",
        side_effect=OSError(10051, "unreachable"),
    ):
        result = connect_tcp_ipv4("1.1.1.1")

    assert result.status == "error"
    assert "10051" in result.detail


@pytest.mark.parametrize(
    "address, port, timeout",
    [
        ("not-ip", 443, 1),
        ("1.1.1.1", 0, 1),
        ("1.1.1.1", 443, float("nan")),
        ("1.1.1.1", 443, 8),
    ],
)
def test_invalid_tcp_parameters_are_rejected(
    address, port, timeout
):
    with pytest.raises(ValueError):
        connect_tcp_ipv4(
            address,
            port=port,
            timeout=timeout,
        )


def test_tcp_summary_never_fabricates_rtt_for_failures():
    result = _summarize_tcp(
        "A",
        "1.1.1.1",
        (
            TcpAttempt("timeout", None, "timeout"),
            TcpAttempt("refused", None, "refused"),
        ),
    )

    assert result.median_ms is None
    assert result.timed_out == 1
    assert result.refused == 1


def test_investigation_uses_exact_same_public_ips_without_tcp_gateway():
    icmp_calls = []
    tcp_calls = []
    sleeps = []

    def ping(address, *, timeout_ms):
        icmp_calls.append(address)
        return _echo(address, timeout_ms=timeout_ms)

    def connect(address, *, port, timeout):
        tcp_calls.append((address, port, timeout))
        return _tcp(
            address,
            port=port,
            timeout=timeout,
        )

    report = run_crosscheck(
        _snapshot(),
        count=2,
        interval=0.5,
        timeout_ms=1000,
        icmp_probe=ping,
        tcp_probe=connect,
        sleep=sleeps.append,
    )

    assert icmp_calls == (
        ["192.168.1.1"] * 2
        + ["1.1.1.1"] * 2
        + ["8.8.8.8"] * 2
    )

    assert tcp_calls == (
        [("1.1.1.1", 443, 1.0)] * 2
        + [("8.8.8.8", 443, 1.0)] * 2
    )

    assert len(sleeps) == 5
    assert len(report.to_dict()["tcp"]) == 2

    assert any(
        "differs by destination" in f.title
        for f in report.findings
    )

    assert all(
        "ISP is the cause" not in f.explanation
        for f in report.findings
    )


def test_unanswered_icmp_with_working_tcp_is_not_offline():
    def ping(address, *, timeout_ms):
        if address == "192.168.1.1":
            return EchoResult("reply", 3.0, "reply")

        return EchoResult("timeout", None, "timeout")

    report = run_crosscheck(
        _snapshot(),
        count=2,
        interval=0,
        icmp_probe=ping,
        tcp_probe=_tcp,
    )

    assert any(
        "TCP works although ICMP did not reply" in f.title
        for f in report.findings
    )

    assert all(
        "internet is down" not in f.explanation
        for f in report.findings
    )


def test_different_protocol_medians_generate_a_cautious_finding():
    report = run_crosscheck(
        _snapshot(),
        count=2,
        interval=0,
        icmp_probe=_echo,
        tcp_probe=_tcp,
    )

    assert any(
        "ICMP and TCP timings differ" in f.title
        for f in report.findings
    )


def test_failed_tcp_service_does_not_claim_whole_network_failed():
    report = run_crosscheck(
        _snapshot(),
        count=2,
        interval=0,
        icmp_probe=_echo,
        tcp_probe=lambda *_args, **_kwargs: TcpAttempt(
            "refused", None, "closed"
        ),
    )

    assert any(
        "TCP port 443 was not confirmed" in f.title
        for f in report.findings
    )

    assert all(
        "internet is down" not in f.explanation
        for f in report.findings
    )


def test_custom_target_replaces_public_ips_and_gateway_still_works():
    report = run_crosscheck(
        _snapshot(),
        count=2,
        interval=0,
        targets=("127.0.0.1",),
        icmp_probe=_echo,
        tcp_probe=_tcp,
    )

    assert [
        result.address for result in report.tcp
    ] == ["127.0.0.1"]

    assert [
        result.address for result in report.latency.targets
    ] == ["192.168.1.1", "127.0.0.1"]