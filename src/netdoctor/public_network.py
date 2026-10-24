
"""Opt-in public exit-IP lookup and conservative IPv4 NAT/CGN interpretation.

No router access, port scans, UPnP requests, or automatic lookups on startup.
The external service observes the caller's exit IP, which can be a VPN/proxy.
"""

import ipaddress
import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable

from netdoctor.models import Snapshot


class PublicLookupError(Exception):
    """The optional external address lookup could not be completed."""


_SHARED = ipaddress.IPv4Network("100.64.0.0/10")
_PRIVATE = tuple(ipaddress.IPv4Network(cidr) for cidr in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))
_URL = "https://api.ip.sb/geoip"


@dataclass(frozen=True)
class PublicNetworkReport:
    public_ip: str
    ip_family: str
    exit_network: str | None
    asn: int | None
    local_ipv4: str | None
    router_wan_ipv4: str | None
    nat_status: str
    nat_explanation: str
    provider_explanation: str = (
        "This identifies the network operating the address visible to the "
        "lookup service. A VPN, proxy, carrier or shared network can make it "
        "different from your subscription provider."
    )
    source: str = "IP.SB HTTPS lookup (requested by user)"

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_wan(text: str | None) -> ipaddress.IPv4Address | None:
    if text is None or not text.strip():
        return None
    if len(text) > 45:
        raise ValueError("Enter one IPv4 address from your router's WAN page.")
    try:
        address = ipaddress.IPv4Address(text.strip())
    except ipaddress.AddressValueError as exc:
        raise ValueError("Router WAN address must be a numeric IPv4 address.") from exc
    if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local:
        raise ValueError("That is not a usable router WAN IPv4 address.")
    return address


def _fetch_profile(timeout: float = 4.0) -> dict:
    """One HTTPS GET, bounded body and timeout, without browser geolocation."""
    request = urllib.request.Request(
        _URL,
        headers={"User-Agent": "NetDoctor/0.1 (local network diagnostic)",
                 "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if getattr(response, "status", 200) != 200:
                raise PublicLookupError("The external lookup service was unavailable.")
            body = response.read(8193)
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        raise PublicLookupError("Could not reach the public address lookup service.") from exc
    if len(body) > 8192:
        raise PublicLookupError("The public lookup returned an unexpectedly large response.")
    try:
        profile = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PublicLookupError("The public lookup returned invalid data.") from exc
    if not isinstance(profile, dict):
        raise PublicLookupError("The public lookup returned invalid data.")
    return profile


def _clean_label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split())
    if not clean or any(ord(c) < 32 for c in clean):
        return None
    return clean[:100]


def _local_ipv4(snapshot: Snapshot) -> str | None:
    route = snapshot.preferred_route("IPv4")
    adapter = next((a for a in snapshot.adapters if route and a.index == route.interface_index), None)
    if adapter is None:
        return None
    for raw in adapter.ipv4:
        try:
            address = ipaddress.IPv4Address(raw)
        except ipaddress.AddressValueError:
            continue
        if not (address.is_link_local or address.is_loopback or address.is_unspecified):
            return str(address)
    return None


def _nat_assessment(
    public: ipaddress.IPv4Address | ipaddress.IPv6Address,
    wan: ipaddress.IPv4Address | None,
    local: str | None,
) -> tuple[str, str]:
    if wan is None:
        if local:
            return (
                "CGNAT not determined",
                "A computer's local IP and gateway cannot establish whether your provider "
                "uses CGNAT. For a better clue, compare the WAN IPv4 shown in your router "
                "with the public IPv4 observed externally.",
            )
        return (
            "CGNAT not determined",
            "No router WAN address was supplied; no reliable CGNAT conclusion is possible.",
        )
    if wan in _SHARED:
        return (
            "Carrier-shared WAN address detected",
            "The supplied router WAN address is in 100.64.0.0/10, reserved for "
            "shared carrier address space. This strongly suggests upstream address "
            "sharing, but it does not identify the equipment or prove port reachability.",
        )
    if any(wan in subnet for subnet in _PRIVATE):
        return (
            "Upstream NAT indicated",
            "The supplied router WAN address is private. Another NAT layer is likely "
            "upstream, but it could be another household router or provider CGNAT.",
        )
    if not wan.is_global:
        return (
            "CGNAT not determined",
            "The router WAN address is not globally routable; its role is unclear.",
        )
    if isinstance(public, ipaddress.IPv6Address):
        return (
            "IPv4 comparison unavailable",
            "The external lookup observed IPv6, so it cannot be directly compared "
            "with the router's IPv4 WAN address.",
        )
    if str(wan) == str(public):
        return (
            "No upstream IPv4 NAT indicated",
            "The router WAN IPv4 matches the observed public IPv4. This does not "
            "guarantee inbound connections or open ports.",
        )
    return (
        "Addresses differ — cause unverified",
        "The router WAN address and externally observed IPv4 differ. Possible "
        "explanations include VPN/proxy routing, multiple WAN paths or upstream NAT. "
        "A mismatch alone cannot diagnose CGNAT.",
    )


def inspect_public_network(
    snapshot: Snapshot,
    *,
    router_wan_ipv4: str = "",
    fetch: Callable[[], dict] = _fetch_profile,
) -> PublicNetworkReport:
    """An explicit lookup; WAN address never leaves this Python process as input."""
    wan = _parse_wan(router_wan_ipv4)
    profile = fetch()
    if not isinstance(profile, dict):
        raise PublicLookupError("The lookup returned an invalid response.")
    try:
        public = ipaddress.ip_address(profile.get("ip", ""))
    except ValueError as exc:
        raise PublicLookupError("The lookup did not return a valid public address.") from exc
    if not public.is_global:
        raise PublicLookupError("The lookup did not return a globally routable address.")
    provider = _clean_label(profile.get("isp")) or _clean_label(profile.get("asn_organization"))
    asn = profile.get("asn")
    if isinstance(asn, str) and asn.isdecimal():
        asn = int(asn)
    if isinstance(asn, bool) or not isinstance(asn, int) or not 0 < asn <= 4294967295:
        asn = None
    local = _local_ipv4(snapshot)
    status, explanation = _nat_assessment(public, wan, local)
    return PublicNetworkReport(
        public_ip=str(public),
        ip_family="IPv4" if isinstance(public, ipaddress.IPv4Address) else "IPv6",
        exit_network=provider,
        asn=asn,
        local_ipv4=local,
        router_wan_ipv4=str(wan) if wan else None,
        nat_status=status,
        nat_explanation=explanation,
    )
