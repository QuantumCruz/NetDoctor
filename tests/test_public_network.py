
"""Stage 14 public IP and NAT evidence, no real outbound traffic."""

import json
from unittest.mock import patch

import pytest

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.public_network import (
    PublicLookupError, _fetch_profile, inspect_public_network,
)


def snapshot(local="192.168.1.55"):
    return Snapshot(
        (Adapter(6, "WiFi", "Intel Wireless", "Up", "650 Mbps", "Wi-Fi (inferred)",
                 (local,), (), ("192.168.1.1",)),),
        (DefaultRoute("IPv4", 6, "192.168.1.1", 0, 25),), (),
    )


def profile(ip="41.12.34.56", **fields):
    return {"ip": ip, "isp": "Example Fiber", "asn": 64500, **fields}


def measure(*, wan="", ip="41.12.34.56", **fields):
    return inspect_public_network(snapshot(), router_wan_ipv4=wan,
                                  fetch=lambda: profile(ip, **fields))


def test_public_profile_is_exit_network_not_subscription_claim():
    result = measure()
    assert result.public_ip == "41.12.34.56"
    assert result.exit_network == "Example Fiber"
    assert result.asn == 64500
    assert result.local_ipv4 == "192.168.1.55"
    assert result.nat_status == "CGNAT not determined"
    assert "VPN" in result.provider_explanation
    assert result.to_dict()["ip_family"] == "IPv4"


def test_shared_router_wan_is_strong_cgn_clue():
    result = measure(wan="100.100.0.3")
    assert result.nat_status == "Carrier-shared WAN address detected"
    assert "strongly suggests" in result.nat_explanation
    assert "prove port" in result.nat_explanation


def test_private_wan_is_not_automatically_cgnat():
    result = measure(wan="10.1.2.3")
    assert result.nat_status == "Upstream NAT indicated"
    assert "could be another household router" in result.nat_explanation


def test_matching_public_wan_is_not_proof_ports_open():
    result = measure(wan="41.12.34.56")
    assert result.nat_status == "No upstream IPv4 NAT indicated"
    assert "does not guarantee inbound" in result.nat_explanation


def test_mismatch_cannot_establish_cgnat():
    result = measure(wan="41.12.34.57")
    assert result.nat_status == "Addresses differ — cause unverified"
    assert "cannot diagnose CGNAT" in result.nat_explanation


def test_ipv6_observed_does_not_compare_with_router_ipv4():
    result = measure(wan="41.12.34.56", ip="2001:4860:4860::8888")
    assert result.ip_family == "IPv6"
    assert result.nat_status == "IPv4 comparison unavailable"


@pytest.mark.parametrize(
    "bad",
    ["localhost", "1.2.3.999", "127.0.0.1", "169.254.1.1", "2001:db8::1"],
)
def test_invalid_wan_is_rejected_before_external_request(bad):
    with pytest.raises(ValueError):
        inspect_public_network(
            snapshot(),
            router_wan_ipv4=bad,
            fetch=lambda: (_ for _ in ()).throw(AssertionError("network used")),
        )


@pytest.mark.parametrize(
    "bad",
    ["127.0.0.1", "192.168.1.1", "100.64.1.2", "malformed"],
)
def test_invalid_public_ip_is_rejected(bad):
    with pytest.raises(PublicLookupError):
        measure(ip=bad)


def test_optional_fields_are_safe():
    result = inspect_public_network(
        snapshot(),
        fetch=lambda: {"ip": "8.8.8.8", "asn": "15169", "isp": ""},
    )
    assert result.exit_network is None
    assert result.asn == 15169


def test_public_lookup_response_is_bounded():
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            assert n == 8193
            return b"X" * 8193

    with patch("netdoctor.public_network.urllib.request.urlopen", return_value=Response()):
        with pytest.raises(PublicLookupError, match="large"):
            _fetch_profile()


def test_public_lookup_uses_https_and_custom_user_agent():
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            return json.dumps(profile()).encode()

    with patch("netdoctor.public_network.urllib.request.urlopen", return_value=Response()) as opened:
        result = _fetch_profile()

    assert result["ip"] == "41.12.34.56"
    request = opened.call_args.args[0]
    assert request.full_url == "https://api.ip.sb/geoip"
    assert "NetDoctor" in request.headers["User-agent"]
    assert opened.call_args.kwargs["timeout"] == 4.0
