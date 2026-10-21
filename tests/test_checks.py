
import socket
from unittest.mock import patch

from netdoctor.checks import check_endpoint, diagnose
from netdoctor.models import Adapter, EndpointCheck, Snapshot


def snapshot():
    return Snapshot(adapters=(Adapter(1, "Wi-Fi", "Wireless adapter", "Up", "100 Mbps",
                                      "Wi-Fi (inferred)", ("192.168.0.8",), (), ("1.1.1.1",)),),
                    default_routes=(), warnings=())


def test_dns_failure_is_not_claimed_to_be_offline():
    with patch("netdoctor.checks.socket.getaddrinfo", side_effect=socket.gaierror):
        result = check_endpoint("www.cloudflare.com")
    assert not result.dns_ok and not result.tcp_ok
    report = diagnose(snapshot(), (result,))
    assert report.online_status == "unverified"
    assert "wider connectivity" in report.findings[-1].explanation


def test_one_host_passes_is_partial():
    checks = (EndpointCheck("host1", True, True, "Connected"),
              EndpointCheck("host2", True, False, "Failed"))
    report = diagnose(snapshot(), checks)
    assert report.online_status == "partial"
    assert any("differs by destination" in f.title for f in report.findings)


def test_offline_mode_reports_unchecked():
    report = diagnose(snapshot(), ())
    assert report.online_status == "not_tested"
    assert any("not tested" in f.title for f in report.findings)


def test_tcp_connect_tries_other_ip_family():
    addr = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    class FakeSocket:
        def __init__(self, family, *_):
            self.family = family
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def settimeout(self, _):
            pass
        def connect(self, _):
            if self.family == socket.AF_INET6:
                raise OSError("Unreachable")

    with patch("netdoctor.checks.socket.getaddrinfo", return_value=addr), patch(
        "netdoctor.checks.socket.socket", side_effect=FakeSocket
    ):
        result = check_endpoint("test.invalid")
    assert result.tcp_ok


def test_route_collection_failure_does_not_accuse_missing_gateway():
    base = snapshot()
    incomplete = Snapshot(adapters=base.adapters, default_routes=(),
                          warnings=("Windows could not provide default-route information.",),
                          routes_complete=False)
    report = diagnose(incomplete, (EndpointCheck("host1", True, True, "Connected"),))
    assert report.online_status == "reachable"
    assert not any(f.title == "No usable default route was found" for f in report.findings)
    assert any(f.title == "Partial Windows network information" for f in report.findings)


def test_reliably_empty_routes_still_warns():
    report = diagnose(snapshot(), ())
    assert any(f.title == "No usable default route was found" for f in report.findings)
