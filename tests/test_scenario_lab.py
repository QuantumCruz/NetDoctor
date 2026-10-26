
"""Offline fault scenarios; no real sockets, DNS, pings or downloads."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from netdoctor.scenario_lab import SCENARIOS, Scenario, simulate


NOW = datetime(
    2026, 10, 26, 12,
    tzinfo=timezone.utc,
)

CASES = {
    case.name: case
    for case in SCENARIOS
}


def run(name):
    return simulate(
        CASES[name],
        now=NOW,
    )


def codes(result):
    return {
        item["code"]
        for item in result["findings"]
    }


def test_every_scenario_finishes_without_external_requests():
    for case in SCENARIOS:
        result = simulate(
            case,
            now=NOW,
        )

        assert result["scenario"] == case.name

        assert result["doctor_status"] in {
            "reachable",
            "attention",
            "unverified",
        }

        assert result["findings"]

        assert (
            result["doctor_steps"]["internet"]
            == "completed"
        )


@pytest.mark.parametrize(
    "case, status, clue",
    [
        (
            "healthy",
            "reachable",
            "needs_symptom",
        ),
        (
            "partial_access",
            "attention",
            "partial_access",
        ),
        (
            "access_unverified",
            "unverified",
            "access_unverified",
        ),
    ],
)
def test_public_connection_failures_keep_uncertainty(
    case,
    status,
    clue,
):
    result = run(case)

    assert result["doctor_status"] == status
    assert clue in codes(result)

    assert not any(
        "ISP outage confirmed" in str(item)
        for item in result["findings"]
    )


def test_direct_dns_timeout_cannot_overturn_working_public_tcp():
    result = run("dns_direct_timeout")

    assert result["doctor_status"] == "reachable"
    assert result["doctor_steps"]["dns"] == "completed"

    assert "access_unverified" not in codes(result)


def test_unavailable_dns_does_not_mean_no_internet():
    result = run("dns_unavailable")

    assert result["doctor_status"] == "reachable"
    assert result["doctor_steps"]["dns"] == "unavailable"


def test_ping_filter_does_not_mean_router_or_internet_outage():
    result = run("ping_filtered")

    assert result["doctor_status"] == "reachable"

    assert (
        result["doctor_steps"]["responsiveness"]
        == "completed"
    )

    assert "access_unverified" not in codes(result)
    assert "weak_wifi" not in codes(result)


def test_installed_overlay_does_not_mean_vpn_internet_route():
    result = run("overlay_present")

    assert (
        result["network"]["vpn"]["status"]
        == "VPN-style adapter present"
    )

    assert "tunnel_route" not in codes(result)


def test_tunnel_default_is_only_possible_contributor():
    result = run("tunnel_default")

    assert (
        result["network"]["vpn"]["status"]
        == "Possible tunnel route"
    )

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "tunnel_route"
    )

    assert finding["kind"] == "possible"


def test_location_restricted_wifi_keeps_link_and_does_not_fake_weak_signal():
    result = run("wifi_private")
    wifi = result["network"]["wifi"]

    assert wifi["adapter_link_speed"] == "650 Mbps"
    assert wifi["signal_percent"] is None

    assert "weak_wifi" not in codes(result)


def test_measured_weak_signal_is_only_possible_contributor():
    result = run("weak_wifi")

    assert (
        result["network"]["wifi"]["signal_percent"]
        == 24
    )

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "weak_wifi"
    )

    assert finding["kind"] == "possible"


def test_proxy_config_is_not_proof_of_application_routing():
    result = run("proxy_present")

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "proxy_configured"
    )

    assert finding["kind"] == "possible"


def test_previous_short_failures_surface_without_isp_blame():
    result = run("recent_drops")

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "recent_instability"
    )

    assert finding["kind"] == "observed"

    assert (
        "not proof of an ISP outage"
        in finding["evidence"]
    )


def test_old_bad_speed_is_not_used_as_current_fault():
    result = run("old_speed")

    assert "limited_bandwidth" not in codes(result)
    assert "test_latency" not in codes(result)

    assert any(
        "old" in note.lower()
        for note in result["notes"]
    )


def test_fresh_low_download_speed_is_a_measurement_not_a_cause():
    result = run("slow_download")

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "limited_bandwidth"
    )

    assert finding["kind"] == "observed"

    assert (
        "does not identify the cause"
        in finding["evidence"]
    )


def test_during_download_delay_does_not_prove_bufferbloat():
    result = run("download_lag")

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "load_delay"
    )

    assert finding["kind"] == "observed"

    assert (
        "not proof of bufferbloat"
        in finding["evidence"]
    )


def test_invalid_simulation_config_is_rejected_locally():
    with pytest.raises(ValueError):
        simulate(
            replace(
                CASES["healthy"],
                gateway_replies=9,
            ),
            now=NOW,
        )

    with pytest.raises(ValueError):
        simulate(
            replace(
                CASES["healthy"],
                wifi_signal=200,
            ),
            now=NOW,
        )

    with pytest.raises(ValueError):
        simulate(
            CASES["healthy"],
            now=NOW.replace(tzinfo=None),
        )
