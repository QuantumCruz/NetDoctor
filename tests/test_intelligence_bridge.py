
"""Stage 13 dashboard bridge tests for optional network intelligence."""

from types import SimpleNamespace

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.network_intel import ProxySettings, collect_intelligence
from netdoctor.webdesktop import DashboardAPI
from netdoctor.windows_wifi import WifiLink


def snapshot():
    return Snapshot(
        (
            Adapter(
                6,
                "WiFi",
                "Intel Wireless",
                "Up",
                "866 Mbps",
                "Wi-Fi (inferred)",
                ("192.168.0.10",),
                (),
                ("192.168.0.1",),
            ),
        ),
        (
            DefaultRoute("IPv4", 6, "192.168.0.1", 0, 20),
        ),
        (),
    )


def make_api(*, intelligence=None):
    return DashboardAPI(
        collector=snapshot,
        diagnose=lambda snap: SimpleNamespace(
            status="reachable",
            interface="WiFi",
            gateway="192.168.0.1",
        ),
        presenter=lambda result: SimpleNamespace(
            headline="Basic connection works",
            explanation="Two connections responded.",
            observation="No clear fault.",
            next_step="Run the speed test if you choose.",
        ),
        intelligence=intelligence or (
            lambda snap: collect_intelligence(
                snap,
                wifi_reader=lambda: (
                    WifiLink(
                        "Intel Wireless",
                        "Home",
                        74,
                        866.7,
                        433.3,
                    ),
                ),
                proxy_reader=lambda: ProxySettings(),
            )
        ),
    )


def test_bridge_exposes_wifi_and_vpn_information():
    result = make_api().get_overview()

    assert result["status"] == "reachable"
    assert result["network"]["wifi"]["signal_percent"] == 74
    assert result["network"]["wifi"]["signal_label"] == "Strong"
    assert result["vpn"] == "No tunnel route identified"
    assert result["proxy"] == "No manual proxy found"
    assert result["cgnat"] == "Not checked"


def test_intelligence_failure_preserves_main_diagnosis():
    def fail(snapshot):
        raise RuntimeError("Internal information")

    result = make_api(intelligence=fail).get_overview()

    assert result["status"] == "reachable"
    assert result["vpn"] == "Not checked"
    assert result["network"] is None


def test_discovery_failure_returns_safe_error():
    bridge = DashboardAPI(
        collector=lambda: (
            _ for _ in ()
        ).throw(RuntimeError("secret"))
    )

    result = bridge.get_overview()

    assert result["status"] == "unverified"
    assert "secret" not in str(result)
