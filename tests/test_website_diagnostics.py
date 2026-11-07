
"""Entirely offline tests for safe, opt-in HTTPS website checks."""

import socket
import ssl

import pytest

from netdoctor.website_diagnostics import (
    WebsiteTargetError,
    _target,
    diagnose_website,
)


def resolve(host, port, *, type):
    assert port == 443
    assert type == socket.SOCK_STREAM

    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("8.8.8.8", 443),
        )
    ]


class FakeConnection:
    def __init__(
        self,
        code=b"HTTP/1.1 200 OK\r\n",
        error=None,
    ):
        self.code = code
        self.error = error
        self.request = b""
        self.host = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def settimeout(self, timeout):
        assert 0 < timeout <= 3.0

    def connect(self, address):
        self.address = address

        if isinstance(self.error, Exception):
            raise self.error

    def sendall(self, data):
        self.request += data

    def recv(self, size):
        result, self.code = (
            self.code[:size],
            self.code[size:],
        )
        return result


class FakeContext:
    def __init__(self, conn, error=None):
        self.conn = conn
        self.error = error

    def set_alpn_protocols(self, protocols):
        assert protocols == ["http/1.1"]

    def wrap_socket(self, conn, *, server_hostname):
        assert server_hostname == "github.com"

        if self.error:
            raise self.error

        return conn


def run(
    code=b"HTTP/1.1 200 OK\r\n",
    *,
    connect_error=None,
    tls_error=None,
):
    connection = FakeConnection(
        code,
        error=connect_error,
    )
    ctx = FakeContext(
        connection,
        error=tls_error,
    )

    report = diagnose_website(
        "github.com/releases",
        resolver=resolve,
        socket_factory=lambda *args: connection,
        tls_context_factory=lambda: ctx,
    )

    return report, connection


@pytest.mark.parametrize(
    "bad",
    [
        "",
        " ",
        "http://github.com",
        "https://localhost",
        "https://127.0.0.1",
        "http://192.168.1.1",
        "https://169.254.169.254",
        "https://100.64.1.1",
        "https://github.com:444",
        "https://a@github.com",
        "https://github.com/?token=abc",
        "https://github.com/#abc",
        "https://github.com/hey\r\nX: true",
        "https://bad_host.com",
        "https://github.com\\admin",
        "https://a",
        "https://github.com/" + "a" * 520,
    ],
)
def test_unsafe_or_invalid_targets_never_pass(bad):
    with pytest.raises(WebsiteTargetError):
        _target(bad)


def test_normalization_and_punycode():
    assert _target("GITHUB.COM")[2] == (
        "https://github.com/"
    )
    assert _target("github.com/releases")[2] == (
        "https://github.com/releases"
    )
    assert _target("https://github.com:443/a")[2] == (
        "https://github.com/a"
    )


def test_success_uses_one_head_and_no_body():
    report, conn = run()

    assert report["status"] == "responded"
    assert report["stage"] == "complete"
    assert report["http_status"] == 200
    assert report["address_family"] == "IPv4"
    assert conn.address == ("8.8.8.8", 443)

    assert conn.request == (
        b"HEAD /releases HTTP/1.1\r\n"
        b"Host: github.com\r\n"
        b"User-Agent: NetDoctor/0.3\r\n"
        b"Accept: */*\r\n"
        b"Connection: close\r\n\r\n"
    )

    assert "download" in report["limitation"].lower()


@pytest.mark.parametrize(
    "status",
    [103, 403, 405, 429, 500, 301],
)
def test_http_response_is_not_equated_with_network_outage(
    status,
):
    report, _ = run(
        f"HTTP/1.1 {status} X\r\n".encode()
    )

    assert report["http_status"] == status
    assert report["stage"] == "complete"

    assert report["status"] == (
        "inconclusive"
        if status in (103, 405)
        else "responded"
    )


def test_dns_failure_cannot_be_called_outage():
    def no_dns(*args, **kwargs):
        raise socket.gaierror("private detail")

    report = diagnose_website(
        "github.com",
        resolver=no_dns,
    )

    assert report["stage"] == "dns"
    assert report["status"] == "inconclusive"
    assert "private detail" not in str(report)


def test_private_dns_results_never_connected():
    def private(*args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1", 443),
            )
        ]

    report = diagnose_website(
        "github.com",
        resolver=private,
        socket_factory=lambda *args: pytest.fail(
            "Network called"
        ),
    )

    assert report["stage"] == "dns"
    assert report["status"] == "inconclusive"


def test_failed_tcp_is_inconclusive():
    report, conn = run(
        connect_error=TimeoutError()
    )

    assert report["stage"] == "tcp"
    assert report["tcp_ms"] is None
    assert conn.request == b""


def test_certificate_validation_failure_is_specific_and_safe():
    report, conn = run(
        tls_error=ssl.SSLCertVerificationError(
            "my secret"
        )
    )

    assert report["stage"] == "tls"
    assert "certificate" in report["headline"].lower()
    assert "my secret" not in str(report)
    assert conn.request == b""


def test_malformed_http_is_inconclusive():
    report, _ = run(b"HELLO\r\n")

    assert report["stage"] == "http"
    assert report["status"] == "inconclusive"


def test_timeout_validation():
    with pytest.raises(WebsiteTargetError):
        diagnose_website(
            "github.com",
            timeout=10,
            resolver=lambda *_: pytest.fail(
                "DNS called"
            ),
        )
