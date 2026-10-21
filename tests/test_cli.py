
import json
from unittest.mock import patch

from netdoctor.cli import main
from netdoctor.models import Adapter, Snapshot
from netdoctor.windows import DiscoveryError


def test_json_offline_does_not_contact_internet(capsys):
    snapshot = Snapshot((Adapter(1, "Ethernet", "Ethernet adapter", "Up", "1 Gbps",
                                 "Ethernet (inferred)", ("192.168.0.2",), (), ()),), (), ())
    with patch("netdoctor.cli.collect_snapshot", return_value=snapshot), patch(
        "netdoctor.cli.check_endpoint", side_effect=AssertionError("Unexpected internet access")
    ):
        assert main(["scan", "--offline", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["online_status"] == "not_tested"
    assert report["snapshot"]["adapters"][0]["name"] == "Ethernet"


def test_cli_reports_discovery_failure_without_traceback(capsys):
    with patch("netdoctor.cli.collect_snapshot", side_effect=DiscoveryError("Unavailable")):
        assert main(["--json"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "ND-101"


def test_json_reports_incomplete_routes_instead_of_false_missing_route(capsys):
    snapshot = Snapshot((Adapter(1, "WiFi", "Wireless adapter", "Up", "100 Mbps",
                                 "Wi-Fi (inferred)", ("172.31.119.195",), (), ()),), (),
                        ("Windows could not provide default-route information.",), False)
    with patch("netdoctor.cli.collect_snapshot", return_value=snapshot):
        assert main(["scan", "--offline", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["snapshot"]["routes_complete"] is False
    assert not any(f["title"] == "No usable default route was found" for f in report["findings"])


def test_readable_report_says_unknown_when_routes_failed(capsys):
    snapshot = Snapshot((Adapter(1, "WiFi", "Wireless adapter", "Up", "100 Mbps",
                                 "Wi-Fi (inferred)", ("172.31.119.195",), (), ()),), (),
                        ("Windows could not provide default-route information.",), False)
    with patch("netdoctor.cli.collect_snapshot", return_value=snapshot):
        assert main(["scan", "--offline"]) == 0
    output = capsys.readouterr().out
    assert "Cannot determine" in output
    assert "Not found on an active adapter" not in output
