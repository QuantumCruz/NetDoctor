
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from netdoctor.windows import DiscoveryError, _SCRIPT, collect_snapshot, parse_snapshot


@pytest.fixture
def windows_response():
    return {
        "Adapters": [
            {"InterfaceIndex": 12, "Name": "Wi-Fi", "Description": "Wireless Adapter",
             "Status": "Up", "LinkSpeed": "144 Mbps", "IPv4": ["192.168.1.10"],
             "IPv6": [], "DNS": ["192.168.1.1"]},
            {"InterfaceIndex": 4, "Name": "Ethernet", "Description": "Ethernet Adapter",
             "Status": "Disconnected", "LinkSpeed": "0 bps", "IPv4": [],
             "IPv6": [], "DNS": []},
        ],
        "Routes": [
            {"InterfaceIndex": 12, "DestinationPrefix": "0.0.0.0/0",
             "NextHop": "192.168.1.1", "RouteMetric": 10, "InterfaceMetric": 35},
            {"InterfaceIndex": 4, "DestinationPrefix": "0.0.0.0/0",
             "NextHop": "192.168.1.2", "RouteMetric": 0, "InterfaceMetric": 10},
        ],
        "RoutesComplete": True,
        "Warnings": [],
    }


def test_discovers_adapters_and_ignores_down_route(windows_response):
    snapshot = parse_snapshot(windows_response)
    assert len(snapshot.adapters) == 2
    assert snapshot.preferred_route("IPv4").next_hop == "192.168.1.1"
    assert snapshot.adapters[1].medium == "Wi-Fi (inferred)"
    assert snapshot.routes_complete


def test_invalid_adapter_does_not_crash_entire_snapshot(windows_response):
    windows_response["Adapters"].append({"Name": "Malformed"})
    snapshot = parse_snapshot(windows_response)
    assert len(snapshot.adapters) == 2
    assert any("invalid adapter" in warning for warning in snapshot.warnings)


def test_rejects_unexpected_result():
    with pytest.raises(DiscoveryError, match="unexpected"):
        parse_snapshot({"Adapters": None})


def test_powershell_nonzero_exit_is_actionable():
    with patch("netdoctor.windows.platform.system", return_value="Windows"), patch(
        "netdoctor.windows.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="error")
    ):
        with pytest.raises(DiscoveryError, match="NetAdapter"):
            collect_snapshot()


def test_powershell_timeout_is_actionable():
    with patch("netdoctor.windows.platform.system", return_value="Windows"), patch(
        "netdoctor.windows.subprocess.run", side_effect=subprocess.TimeoutExpired("powershell.exe", 15)
    ):
        with pytest.raises(DiscoveryError, match="timed out"):
            collect_snapshot()


def test_powershell_valid_json(windows_response):
    with patch("netdoctor.windows.platform.system", return_value="Windows"), patch(
        "netdoctor.windows.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps(windows_response), stderr="")
    ):
        snapshot = collect_snapshot()
    assert snapshot.adapters[1].name == "Wi-Fi"


def test_missing_ipv6_default_does_not_require_specific_route_query():
    assert "Get-NetRoute -ErrorAction Stop" in _SCRIPT
    assert "Get-NetRoute -DestinationPrefix" not in _SCRIPT


def test_failed_route_collection_is_not_a_confirmed_missing_route(windows_response):
    windows_response["Routes"] = []
    windows_response["RoutesComplete"] = False
    windows_response["Warnings"] = ["Windows could not provide default-route information."]
    snapshot = parse_snapshot(windows_response)
    assert not snapshot.routes_complete
    assert snapshot.preferred_route("IPv4") is None


def test_invalid_route_makes_route_data_incomplete(windows_response):
    windows_response["Routes"] = [{"DestinationPrefix": "0.0.0.0/0", "InterfaceIndex": 12}]
    snapshot = parse_snapshot(windows_response)
    assert not snapshot.routes_complete
    assert any("invalid default route" in warning for warning in snapshot.warnings)


def test_missing_route_array_is_not_treated_as_empty_routing_table(windows_response):
    del windows_response["Routes"]
    snapshot = parse_snapshot(windows_response)
    assert not snapshot.routes_complete
