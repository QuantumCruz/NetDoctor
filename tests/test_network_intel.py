
"""Stage 13 status tests that cannot mislabel VPN, hotspot or link speed."""

import ctypes

from netdoctor.models import (
    Adapter,
    DefaultRoute,
    Snapshot,
)
from netdoctor.network_intel import (
    ProxySettings,
    collect_intelligence,
)
from netdoctor.windows_wifi import (
    WifiLink,
    _Association,
    _Connection,
    _InterfaceInfo,
    _decode_link,
)


def snapshot(*, internet=6, extra=()):
    adapters = (
        Adapter(
            6,
            "WiFi",
            "Intel(R) Wireless AX",
            "Up",
            "1201 Mbps",
            "Wi-Fi (inferred)",
            ("192.168.1.10",),
            (),
            ("192.168.1.1",),
        ),
    ) + tuple(extra)

    return Snapshot(
        adapters,
        (
            DefaultRoute(
                "IPv4", internet,
                "192.168.1.1", 0, 35,
            ),
        ),
        (),
    )


def wifi(quality=75):
    return (
        WifiLink(
            "Intel(R) Wireless AX",
            "Home WiFi",
            quality,
            866.7,
            433.3,
        ),
    )


def inspect(
    snap=None,
    *,
    quality=75,
    proxy=ProxySettings(),
):
    return collect_intelligence(
        snap or snapshot(),
        wifi_reader=lambda: wifi(quality),
        proxy_reader=lambda: proxy,
    )


def test_good_wifi_is_signal_not_speed():
    info = inspect()

    assert info.wifi.signal_percent == 75
    assert info.wifi.signal_label == "Strong"
    assert info.wifi.receive_link_mbps == 866.7
    assert "do not measure internet speed" in info.wifi.detail
    assert info.wifi.ssid == "Home WiFi"


def test_weak_signal_suggests_recheck_not_certain_cause():
    info = inspect(quality=29)

    assert info.wifi.signal_label == "Weak"
    assert "cannot establish the cause" in info.observation


def test_wifi_on_tunnel_route_does_not_claim_it_is_internet_route():
    vpn = Adapter(
        9,
        "WireGuard Tunnel",
        "Wintun Tunnel",
        "Up",
        "1 Gbps",
        "Other",
        (),
        (),
        (),
    )

    info = inspect(
        snapshot(
            internet=9,
            extra=(vpn,),
        )
    )

    assert info.vpn.status == "Possible tunnel route"
    assert "another interface" in info.wifi.detail
    assert "not confirmed for every app" in info.observation


def test_active_tailscale_without_default_route_is_not_active_internet_vpn():
    overlay = Adapter(
        8,
        "Tailscale",
        "Tailscale Tunnel",
        "Up",
        "100 Mbps",
        "Other",
        (),
        (),
        (),
    )

    info = inspect(
        snapshot(extra=(overlay,))
    )

    assert info.vpn.status == "VPN-style adapter present"
    assert "not the preferred" in info.vpn.detail


def test_no_matching_adapter_is_not_proof_vpn_absence():
    info = inspect()

    assert info.vpn.status == "No tunnel route identified"
    assert "Some VPNs" in info.vpn.detail


def test_manual_proxy_is_configured_not_proven_in_use():
    info = inspect(
        proxy=ProxySettings(manual=True)
    )

    assert info.proxy.status == "Configured"
    assert "may ignore" in info.proxy.detail
    assert "may influence" in info.observation


def test_auto_proxy_is_not_claimed_as_active():
    info = inspect(
        proxy=ProxySettings(auto_detect=True)
    )

    assert info.proxy.status == "Auto-detection enabled"
    assert (
        "No active proxy usage was verified"
        in info.proxy.detail
    )


def test_hotspot_isp_and_cgnat_remain_unknown():
    info = inspect().to_dict()

    assert info["hotspot"] == "Not determined"
    assert info["isp"] == "Not checked"
    assert info["cgnat"] == "Not checked"


def test_reader_failure_does_not_break_diagnosis():
    def boom():
        raise RuntimeError("unavailable")

    info = collect_intelligence(
        snapshot(),
        wifi_reader=boom,
        proxy_reader=boom,
    )

    assert info.wifi.status == "Not available"
    assert info.proxy.status == "Not verified"


def test_only_one_of_two_wifi_links_not_arbitrarily_selected():
    links = wifi() + (
        WifiLink(
            "Another adapter",
            "Other",
            30,
            None,
            None,
        ),
    )

    mismatched = snapshot(
        extra=(
            Adapter(
                7,
                "Ethernet",
                "Card",
                "Up",
                "",
                "Other",
                (),
                (),
                (),
            ),
        )
    )

    mismatched = Snapshot(
        mismatched.adapters,
        (
            DefaultRoute(
                "IPv4", 7, "", 0, 1,
            ),
        ),
        (),
    )

    info = collect_intelligence(
        mismatched,
        wifi_reader=lambda: links,
        proxy_reader=ProxySettings,
    )

    assert info.wifi.status == "Ambiguous"


def test_ctypes_wifi_layout_and_decode_are_consistent():
    assert ctypes.sizeof(_Association) == 68
    assert _Connection.association.offset == 520

    row = _InterfaceInfo()

    name = "Intel(R) Wireless AX".encode("utf-16-le")

    ctypes.memmove(
        ctypes.addressof(row.description),
        name,
        len(name),
    )

    connection = _Connection()
    connection.state = 1
    connection.association.ssid.length = 4
    connection.association.ssid.bytes[:4] = b"Home"
    connection.association.signal_quality = 81
    connection.association.rx_kbps = 866700
    connection.association.tx_kbps = 433300

    result = _decode_link(row, connection)

    assert result.ssid == "Home"
    assert result.receive_link_mbps == 866.7
    assert result.signal_percent == 81


def test_unavailable_proxy_settings_return_not_verified():
    info = inspect(
        proxy=ProxySettings(available=False)
    )

    assert info.proxy.status == "Not verified"
