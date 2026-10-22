
"""Stage 6 CLI dispatch, JSON, and argument validation tests."""

import json
from unittest.mock import patch

import pytest

from netdoctor.cli import main
from netdoctor.doctor import DoctorReport, DoctorStep
from netdoctor.models import Adapter, DefaultRoute, EndpointCheck, Snapshot
from netdoctor.checks import diagnose
from netdoctor.windows import DiscoveryError


def _snapshot():
    return Snapshot(
        (Adapter(6, "WiFi", "Wireless", "Up", "100 Mbps", "Wi-Fi (inferred)",
                 ("192.168.1.10",), (), ("192.168.1.1",)),),
        (DefaultRoute("IPv4", 6, "192.168.1.1", 0, 35),), (),
    )


def _report():
    snapshot = _snapshot()
    checks = (EndpointCheck("www.cloudflare.com", True, True, "ok"),)
    connectivity = diagnose(snapshot, checks)
    return DoctorReport(
        "reachable", "Basic connectivity confirmed", "WiFi", "192.168.1.1",
        connectivity, None, None,
        (DoctorStep("internet", "completed", "1/1 connected"),), (),
    )


def test_doctor_json_dispatch_does_not_duplicate_snapshot_collection(capsys):
    with (
        patch("netdoctor.cli.collect_snapshot", return_value=_snapshot()) as collected,
        patch("netdoctor.cli.run_doctor", return_value=_report()) as called,
    ):
        assert main(["doctor", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "reachable"
    assert data["interface"] == "WiFi"
    assert called.call_args.kwargs["timeout"] == 1.5
    assert called.call_args.args[0] == _snapshot()
    collected.assert_called_once_with()


def test_doctor_readable_summary_and_evidence(capsys):
    with (
        patch("netdoctor.cli.collect_snapshot", return_value=_snapshot()),
        patch("netdoctor.cli.run_doctor", return_value=_report()),
    ):
        assert main(["doctor"]) == 0
    display = capsys.readouterr().out
    assert "Network Doctor" in display
    assert "Basic connectivity confirmed" in display
    assert "Checks performed" in display
    assert "netdoctor scan" in display


def test_doctor_discovery_errors_use_existing_error_contract(capsys):
    with patch("netdoctor.cli.collect_snapshot", side_effect=DiscoveryError("Unavailable")):
        assert main(["doctor", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "ND-101"


@pytest.mark.parametrize("args", [
    ["doctor", "--offline"],
    ["doctor", "--count", "6"],
    ["doctor", "--interval", "0.3"],
    ["doctor", "--target", "1.1.1.1"],
    ["doctor", "--hostname", "example.com"],
    ["doctor", "--hops", "5"],
    ["doctor", "--timeout", "4"],
])
def test_doctor_rejects_unrelated_or_unbounded_options(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
