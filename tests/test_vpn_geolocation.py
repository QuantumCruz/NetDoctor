
"""Offline regression coverage for optional public-IP geolocation fields."""

from netdoctor.models import Adapter, DefaultRoute, Snapshot
from netdoctor.public_network import inspect_public_network


def snapshot():
    return Snapshot(
        (
            Adapter(
                6,
                "WiFi",
                "Wireless",
                "Up",
                "650 Mbps",
                "Wi-Fi",
                ("192.168.0.12",),
                (),
                (),
            ),
        ),
        (
            DefaultRoute(
                "IPv4",
                6,
                "192.168.0.1",
                0,
                10,
            ),
        ),
        (),
    )


def test_location_fields_are_extracted_without_extra_network_calls():
    calls = []

    def fetch():
        calls.append(True)

        return {
            "ip": "8.8.8.8",
            "country": "United States",
            "country_code": "us",
            "city": "Mountain View",
            "isp": "Example network",
        }

    result = inspect_public_network(
        snapshot(),
        fetch=fetch,
    ).to_dict()

    assert calls == [True]
    assert result["country"] == "United States"
    assert result["country_code"] == "US"
    assert result["city"] == "Mountain View"
    assert result["public_ip"] == "8.8.8.8"
    assert result["nat_status"] == "CGNAT not determined"


def test_absent_or_invalid_location_is_not_invented():
    result = inspect_public_network(
        snapshot(),
        fetch=lambda: {
            "ip": "8.8.8.8",
            "country_code": "NOT_A_CODE",
        },
    ).to_dict()

    assert result["country"] is None
    assert result["country_code"] is None
    assert result["city"] is None
