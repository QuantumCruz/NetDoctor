"""Privacy-conscious signatures for the route currently used for internet access.

This is not Wi-Fi identification: unchanged settings can occur on different
networks, and a DHCP renewal or route change can change a signature. The
signature is a local warning heuristic, never a network identity certificate.
"""

import hashlib
import ipaddress
import json
from dataclasses import dataclass

from netdoctor.models import Snapshot


@dataclass(frozen=True)
class NetworkContext:
    state: str
    message: str

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "message": self.message,
        }


def network_signature(snapshot: Snapshot) -> str | None:
    """Hash selected route and adapter context; no SSID, MAC or location APIs."""
    if not isinstance(snapshot, Snapshot):
        return None

    route = (
        snapshot.preferred_route("IPv4")
        or snapshot.preferred_route("IPv6")
    )

    if route is None:
        return None

    adapter = next(
        (
            candidate
            for candidate in snapshot.adapters
            if candidate.is_up
            and candidate.index == route.interface_index
        ),
        None,
    )

    if adapter is None:
        return None

    try:
        hop = ipaddress.ip_address(route.next_hop)
    except (ValueError, TypeError):
        return None

    if (
        hop.is_unspecified
        or hop.is_multicast
        or hop.is_loopback
    ):
        return None

    local_v4 = []

    for value in adapter.ipv4:
        try:
            address = ipaddress.IPv4Address(value)
        except (ValueError, TypeError):
            continue

        if not (
            address.is_loopback
            or address.is_unspecified
        ):
            local_v4.append(str(address))

    data = {
        "version": 1,
        "family": route.family,
        "adapter_index": adapter.index,
        "adapter_name": adapter.name.casefold().strip(),
        "adapter_description": adapter.description.casefold().strip(),
        "gateway": str(hop),
        "local_ipv4": sorted(set(local_v4)),
    }

    serialized = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    )

    return (
        "n1-"
        + hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()[:32]
    )


def compare_network(
    saved: str | None,
    current: str | None,
) -> NetworkContext:
    """Different signatures warrant caution; equal does not prove same LAN."""
    if not saved:
        return NetworkContext(
            "unverified",
            "This previous speed result was saved before network tracking "
            "was available. It may be from another connection.",
        )

    if not current:
        return NetworkContext(
            "unverified",
            "Windows could not provide enough route information to compare "
            "this reading with the current connection.",
        )

    if saved != current:
        return NetworkContext(
            "changed",
            "The active network configuration differs from the "
            "configuration recorded with this speed result. "
            "Run a new speed test before using it to judge "
            "your current connection.",
        )

    return NetworkContext(
        "matching",
        "The recorded and current network configurations match. "
        "This does not guarantee the same Wi-Fi network "
        "or unchanged internet performance.",
    )