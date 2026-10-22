
"""CLI regression checks specific to Stage 5 DNS integration."""

import json
from unittest.mock import patch

import pytest

from netdoctor.cli import main
from netdoctor.dnsdiagnostics import DnsDiagnosticError, DnsObservation, DnsReport
from netdoctor.models import Adapter, DefaultRoute, Snapshot


def _snapshot():
    return Snapshot(
        (Adapter(6, "WiFi", "Wireless", "Up", "100 Mbps", "Wi-Fi (inferred)",
                 ("192.168.1.100",), (), ("192.168.1.1",)),),
        (DefaultRoute("IPv4", 6, "192.168.1.1", 0, 35),), (),
    )


def _report():
    return DnsReport(
        "WiFi", ("192.168.1.1",),
        (DnsObservation("192.168.1.1", "example.com", "answered", 12.5,
                        ("93.184.215.14",), 0, "Resolved"),), (),
    )


def test_dns_json_dispatch_passes_expected_hosts(capsys):
    with (
        patch("netdoctor.cli.collect_snapshot", return_value=_snapshot()),
        patch("netdoctor.cli.diagnose_dns", return_value=_report()) as run,
    ):
        assert main(["dns", "--hostname", "example.com", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["observations"][0]["status"] == "answered"
    assert run.call_args.kwargs["hostnames"] == ("example.com",)


def test_dns_readable_explains_scope(capsys):
    with (
        patch("netdoctor.cli.collect_snapshot", return_value=_snapshot()),
        patch("netdoctor.cli.diagnose_dns", return_value=_report()),
    ):
        assert main(["dns"]) == 0
    output = capsys.readouterr().out
    assert "Configured DNS server checks" in output
    assert "direct" in output.lower()


def test_dns_invalid_hostname_returns_structured_error(capsys):
    with (
        patch("netdoctor.cli.collect_snapshot", return_value=_snapshot()),
        patch("netdoctor.cli.diagnose_dns", side_effect=DnsDiagnosticError("Invalid hostname")),
    ):
        assert main(["dns", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "ND-401"


@pytest.mark.parametrize("argv", [
    ["dns", "--offline"],
    ["dns", "--count", "2"],
    ["dns", "--hops", "4"],
    ["dns", "--target", "1.1.1.1"],
    ["scan", "--hostname", "example.com"],
    ["trace", "--hostname", "example.com"],
    ["dns", "--timeout", "4"],
    ["dns", "--hostname", "a.com", "--hostname", "b.com", "--hostname", "c.com", "--hostname", "d.com"],
])
def test_dns_argument_validation(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
