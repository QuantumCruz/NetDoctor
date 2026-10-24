
"""Cautious interpretation of Windows Wi-Fi, VPN-style routes and proxy settings.

Read-only and local: an active tunnel-looking adapter is not proof an app uses
it; a Windows proxy configuration is not proof any given app obeys it.
"""

import os
import platform
import re
from dataclasses import asdict, dataclass
from typing import Callable

from netdoctor.models import Adapter, Snapshot
from netdoctor.windows_wifi import WifiLink, read_wifi_links


@dataclass(frozen=True)
class WifiStatus:
    status: str
    ssid: str | None
    signal_percent: int | None
    signal_label: str
    receive_link_mbps: float | None
    transmit_link_mbps: float | None
    detail: str


@dataclass(frozen=True)
class TunnelStatus:
    status: str
    detail: str


@dataclass(frozen=True)
class ProxySettings:
    manual: bool = False
    pac: bool = False
    auto_detect: bool = False
    environment: bool = False
    available: bool = True


@dataclass(frozen=True)
class ProxyStatus:
    status: str
    detail: str


@dataclass(frozen=True)
class NetworkIntelligence:
    wifi: WifiStatus
    vpn: TunnelStatus
    proxy: ProxyStatus
    hotspot: str
    isp: str
    cgnat: str
    observation: str | None

    def to_dict(self) -> dict:
        return asdict(self)


_VPN_LABELS = re.compile(
    r"wireguard|openvpn|wintun|nordlynx|protonvpn|mullvad|surfshark|"
    r"expressvpn|anyconnect|globalprotect|fortinet|forticlient|"
    r"tunnelbear|zerotier|tailscale|tap-windows|\bvpn\b",
    re.IGNORECASE,
)


def _looks_like_tunnel(adapter: Adapter) -> bool:
    return bool(
        _VPN_LABELS.search(
            f"{adapter.name} {adapter.description}"
        )
    )


def read_proxy_settings() -> ProxySettings:
    """Read current-user WinINet settings and proxy env variable presence.

    No proxy addresses or PAC URLs are returned to the dashboard; those
    values could contain sensitive endpoint or credential information.
    """
    env = any(
        os.environ.get(key)
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        )
    )

    if platform.system() != "Windows":
        return ProxySettings(
            environment=env,
            available=False,
        )

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:

            def get(name, default=None):
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    return default

            return ProxySettings(
                manual=(
                    bool(get("ProxyEnable", 0))
                    and bool(get("ProxyServer", ""))
                ),
                pac=bool(get("AutoConfigURL", "")),
                auto_detect=bool(get("AutoDetect", 0)),
                environment=env,
            )

    except OSError:
        return ProxySettings(
            environment=env,
            available=False,
        )


def _wifi_status(
    snapshot: Snapshot,
    links: tuple[WifiLink, ...],
) -> WifiStatus:
    if not links:
        return WifiStatus(
            "Not available",
            None,
            None,
            "Unknown",
            None,
            None,
            "Windows did not provide an active Wi-Fi association.",
        )

    selected_route = (
        snapshot.preferred_route("IPv4")
        or snapshot.preferred_route("IPv6")
    )

    selected = next(
        (
            adapter for adapter in snapshot.adapters
            if selected_route
            and adapter.index == selected_route.interface_index
        ),
        None,
    )

    matched = next(
        (
            link for link in links
            if selected
            and link.description.casefold().strip()
            == selected.description.casefold().strip()
        ),
        None,
    )

    # A VPN can be the default route above one physical Wi-Fi connection.
    if matched is None and len(links) == 1:
        matched = links[0]

    if matched is None:
        return WifiStatus(
            "Ambiguous",
            None,
            None,
            "Unknown",
            None,
            None,
            "More than one wireless association was reported; "
            "the active one is unclear.",
        )

    signal = matched.signal_percent
    quality = (
        "Strong" if signal >= 70
        else "Fair" if signal >= 40
        else "Weak"
    )

    detail = (
        "Windows reported the current Wi-Fi association. "
        "Signal percentage and negotiated link rates "
        "do not measure internet speed."
    )

    if (
        selected
        and matched.description.casefold().strip()
        != selected.description.casefold().strip()
    ):
        detail += (
            " The preferred internet route uses another interface "
            "(possibly a tunnel)."
        )

    return WifiStatus(
        "Connected",
        matched.ssid,
        signal,
        quality,
        matched.receive_link_mbps,
        matched.transmit_link_mbps,
        detail,
    )


def _vpn_status(snapshot: Snapshot) -> TunnelStatus:
    selected = (
        snapshot.preferred_route("IPv4")
        or snapshot.preferred_route("IPv6")
    )

    active = [
        adapter
        for adapter in snapshot.adapters
        if adapter.is_up and _looks_like_tunnel(adapter)
    ]

    if selected and any(
        adapter.index == selected.interface_index
        for adapter in active
    ):
        return TunnelStatus(
            "Possible tunnel route",
            "The preferred default route uses a VPN-style adapter. "
            "This does not prove every app's traffic passes through a VPN.",
        )

    if active:
        return TunnelStatus(
            "VPN-style adapter present",
            "A VPN or virtual-network adapter is active, "
            "but it is not the preferred default internet route. "
            "It may serve only private networks.",
        )

    return TunnelStatus(
        "No tunnel route identified",
        "No recognized VPN-style adapter was found on the preferred "
        "internet route. Some VPNs and per-app tunnels are not "
        "identifiable this way.",
    )


def _proxy_status(settings: ProxySettings) -> ProxyStatus:
    if (
        settings.manual
        or settings.pac
        or settings.environment
    ):
        sources = []

        if settings.manual:
            sources.append("Windows manual proxy")
        if settings.pac:
            sources.append("automatic configuration script")
        if settings.environment:
            sources.append("proxy environment variable")

        return ProxyStatus(
            "Configured",
            "Detected "
            + ", ".join(sources)
            + ". Some applications may ignore these settings.",
        )

    if settings.auto_detect:
        return ProxyStatus(
            "Auto-detection enabled",
            "Windows may discover a proxy automatically. "
            "No active proxy usage was verified.",
        )

    if not settings.available:
        return ProxyStatus(
            "Not verified",
            "Windows proxy settings could not be read.",
        )

    return ProxyStatus(
        "No manual proxy found",
        "No manual or script proxy setting was found for this user. "
        "This does not rule out other proxy mechanisms.",
    )


def collect_intelligence(
    snapshot: Snapshot,
    *,
    wifi_reader: Callable[
        [], tuple[WifiLink, ...]
    ] = read_wifi_links,
    proxy_reader: Callable[
        [], ProxySettings
    ] = read_proxy_settings,
) -> NetworkIntelligence:
    """Summarize local configuration, isolating optional reader failures."""
    try:
        wifi_links = wifi_reader()
    except Exception:
        wifi_links = ()

    try:
        proxy_settings = proxy_reader()
    except Exception:
        proxy_settings = ProxySettings(
            available=False
        )

    wifi = _wifi_status(snapshot, wifi_links)
    vpn = _vpn_status(snapshot)
    proxy = _proxy_status(proxy_settings)

    notice = None

    if (
        wifi.status == "Connected"
        and wifi.signal_label == "Weak"
    ):
        notice = (
            "Wi-Fi signal looks weak. Try moving closer to the "
            "access point and retest. Signal alone cannot "
            "establish the cause of slow internet."
        )

    elif vpn.status == "Possible tunnel route":
        notice = (
            "Your preferred internet route appears to use a "
            "VPN-style adapter. A tunnel may affect latency "
            "or routing; usage is not confirmed for every app."
        )

    elif proxy.status == "Configured":
        notice = (
            "A proxy is configured. It may influence certain "
            "applications, but NetDoctor has not verified "
            "that their traffic uses it."
        )

    return NetworkIntelligence(
        wifi=wifi,
        vpn=vpn,
        proxy=proxy,
        hotspot="Not determined",
        isp="Not checked",
        cgnat="Not checked",
        observation=notice,
    )
