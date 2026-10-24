
"""Stage 14 React bridge: local fallback and opt-in public lookups."""

from types import SimpleNamespace

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.webdesktop import DashboardAPI


def snapshot():
    return Snapshot((
        Adapter(6, "WiFi", "Intel(R) Wi-Fi 6E AX211", "Up", "650 Mbps", "Wi-Fi (inferred)",
                ("192.168.1.55",), (), ()),
        Adapter(8, "Tailscale", "Tailscale Tunnel", "Up", "100 Gbps", "Other", (), (), ()),
    ), (DefaultRoute("IPv4", 6, "192.168.1.1", 0, 20),), ())


def intelligence(_):
    return SimpleNamespace(to_dict=lambda: {
        "wifi": {
            "status": "Not available",
            "signal_percent": None,
            "signal_label": "Unknown",
        },
        "vpn": {
            "status": "VPN-style adapter present",
            "detail": "Not preferred route",
        },
        "proxy": {
            "status": "No manual proxy found",
            "detail": "None",
        },
        "hotspot": "Not determined",
        "isp": "Not checked",
        "cgnat": "Not checked",
        "observation": None,
    })


def bridge(*, public=None):
    return DashboardAPI(
        collector=snapshot,
        diagnose=lambda _: SimpleNamespace(
            status="reachable", interface="WiFi", gateway="192.168.1.1"
        ),
        presenter=lambda _: SimpleNamespace(
            headline="Basic connection works",
            explanation="OK",
            observation="Nothing unusual",
            next_step="None",
        ),
        intelligence=intelligence,
        public_lookup=public or (
            lambda snap, *, router_wan_ipv4: SimpleNamespace(
                to_dict=lambda: {
                    "public_ip": "8.8.8.8",
                    "nat_status": "CGNAT not determined",
                    "router_wan_ipv4": router_wan_ipv4,
                }
            )
        ),
    )


def test_overview_uses_adapter_without_location_access():
    view = bridge().get_overview()
    wifi = view["network"]["wifi"]
    assert wifi["adapter_link_speed"] == "650 Mbps"
    assert wifi["signal_percent"] is None
    assert wifi["status"] == "Connected (details unavailable)"
    assert "privacy" in wifi["detail"]
    assert view["vpn"] == "VPN-style adapter present"
    assert view["isp"] == "Not checked"


def test_overview_never_calls_external_public_lookup():
    def crash(*args, **kwargs):
        raise AssertionError("Public lookup must be opt-in")

    assert bridge(public=crash).get_overview()["status"] == "reachable"


def test_explicit_public_lookup_transfers_wan_only_to_python_function():
    called = []

    def lookup(snap, *, router_wan_ipv4):
        called.append(router_wan_ipv4)
        return SimpleNamespace(to_dict=lambda: {"public_ip": "8.8.8.8"})

    result = bridge(public=lookup).check_public_connection("100.64.1.2")

    assert result == {"ok": True, "report": {"public_ip": "8.8.8.8"}}
    assert called == ["100.64.1.2"]


def test_lookup_failure_is_safe_and_does_not_leak_error_details():
    def fail(*args, **kwargs):
        raise RuntimeError("secret cookie")

    result = bridge(public=fail).check_public_connection()
    assert not result["ok"]
    assert "secret cookie" not in result["error"]


def test_wrong_wan_type_is_rejected_without_lookup():
    assert bridge().check_public_connection(42)["ok"] is False
