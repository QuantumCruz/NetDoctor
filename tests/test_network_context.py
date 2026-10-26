"""No Windows or external network needed for route-signature tests."""

from dataclasses import replace

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.network_context import (
    compare_network,
    network_signature,
)


def snapshot(
    *,
    gateway="192.168.1.1",
    local="192.168.1.20",
    link="650 Mbps",
    overlay=False,
    tunnel=False,
    route=True,
):
    wifi = Adapter(
        6,
        "WiFi",
        "Intel wireless",
        "Up",
        link,
        "Wi-Fi",
        (local,),
        (),
        (),
    )

    adapters = [wifi]
    index = 6

    if overlay or tunnel:
        adapters.append(
            Adapter(
                8,
                "Tailscale",
                "Tunnel",
                "Up",
                "100 Gbps",
                "Other",
                (),
                (),
                (),
            )
        )

        if tunnel:
            index = 8

    routes = (
        (
            DefaultRoute(
                "IPv4",
                index,
                gateway,
                0,
                20,
            ),
        )
        if route
        else ()
    )

    return Snapshot(
        tuple(adapters),
        routes,
        (),
    )


def test_signature_stable_across_adapter_order_and_link_rate_changes():
    first = snapshot(overlay=True)

    changed_link = snapshot(
        overlay=True,
        link="433 Mbps",
    )

    reordered = replace(
        first,
        adapters=tuple(reversed(first.adapters)),
    )

    assert network_signature(first) == network_signature(changed_link)
    assert network_signature(first) == network_signature(reordered)


def test_non_default_virtual_adapter_not_confused_with_vpn_route():
    assert network_signature(
        snapshot()
    ) == network_signature(
        snapshot(overlay=True)
    )

    assert network_signature(
        snapshot()
    ) != network_signature(
        snapshot(tunnel=True)
    )


def test_gateway_or_local_address_change_warns():
    before = network_signature(snapshot())

    assert before != network_signature(
        snapshot(gateway="192.168.42.1")
    )

    assert before != network_signature(
        snapshot(local="192.168.1.25")
    )


def test_missing_route_and_unusable_gateway_are_unverified():
    assert network_signature(
        snapshot(route=False)
    ) is None

    assert network_signature(
        snapshot(gateway="0.0.0.0")
    ) is None

    assert network_signature(
        snapshot(gateway="not-an-ip")
    ) is None

    assert network_signature(
        "not a snapshot"
    ) is None


def test_comparison_is_conservative():
    first = network_signature(snapshot())
    second = network_signature(
        snapshot(gateway="10.0.0.1")
    )

    assert compare_network(first, first).state == "matching"
    assert compare_network(first, second).state == "changed"

    assert (
        "Run a new speed test"
        in compare_network(first, second).message
    )

    assert compare_network(None, first).state == "unverified"
    assert compare_network(first, None).state == "unverified"


def test_does_not_depend_on_wifi_name_or_location():
    signed = network_signature(snapshot())

    assert signed.startswith("n1-")
    assert "WiFi" not in signed
    assert "192.168" not in signed
    assert len(signed) == 35