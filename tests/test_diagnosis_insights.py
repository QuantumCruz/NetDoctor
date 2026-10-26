
"""Stage 18: separate real observations from possible contributors."""
from datetime import datetime, timedelta, timezone

import pytest

from netdoctor.diagnosis_insights import analyze_diagnosis

NOW = datetime(2026, 10, 26, 9, tzinfo=timezone.utc)


def overview(status="reachable", signal=None, wifi_status="Connected (details unavailable)",
             vpn="VPN-style adapter present", proxy="No manual proxy found"):
    return {"status": status, "network": {
        "wifi": {"status": wifi_status, "signal_percent": signal},
        "vpn": {"status": vpn}, "proxy": {"status": proxy},
    }}


def reading(age=0, down=35.7, latency=22):
    return {"tested_at": (NOW - timedelta(minutes=age)).isoformat(),
            "download_mbps": down, "upload_mbps": 20, "latency_ms": latency}


def samples(state="ok", count=8, age=0):
    return [{"state": state, "checked_at": (NOW - timedelta(minutes=age, seconds=i*10)).isoformat()}
            for i in range(count)]


def codes(result):
    return {item["code"] for item in result["findings"]}


def test_normal_speed_and_present_overlay_are_not_false_fault():
    result = analyze_diagnosis(overview(), reading=reading(), samples=samples(), now=NOW)
    assert codes(result) == {"needs_symptom"}
    assert "not preferred" in " ".join(result["notes"])


def test_location_restriction_does_not_mean_weak_wifi():
    result = analyze_diagnosis(overview(signal=None), now=NOW)
    assert "weak_wifi" not in codes(result)
    assert "no signal problem" in " ".join(result["notes"])


def test_genuinely_weak_wifi_is_possible_not_confirmed():
    result = analyze_diagnosis(overview(signal=25, wifi_status="Connected"), now=NOW)
    item = next(i for i in result["findings"] if i["code"] == "weak_wifi")
    assert item["kind"] == "possible"
    assert "Signal alone" in item["evidence"]


def test_stale_speed_not_used_as_present_cause():
    result = analyze_diagnosis(overview(), reading=reading(age=130, down=0.2, latency=900), now=NOW)
    assert "limited_bandwidth" not in codes(result)
    assert "test_latency" not in codes(result)
    assert result["speed_fresh"] is False


def test_current_low_bandwidth_and_latency_are_observations():
    result = analyze_diagnosis(overview(), reading=reading(down=0.8, latency=180), now=NOW)
    assert {"limited_bandwidth", "test_latency"} <= codes(result)
    assert all(i["kind"] == "observed" for i in result["findings"])


def test_recent_repeated_failures_not_isp_accusation():
    result = analyze_diagnosis(overview(), samples=samples("failed"), now=NOW)
    item = next(i for i in result["findings"] if i["code"] == "recent_instability")
    assert "not proof of an ISP outage" in item["evidence"]
    assert result["history_rounds"] == 8


def test_old_outage_history_not_used_as_current_evidence():
    result = analyze_diagnosis(overview(), samples=samples("failed", age=100), now=NOW)
    assert "recent_instability" not in codes(result)
    assert result["history_rounds"] == 0


def test_two_of_six_failures_detected():
    values = samples("ok", count=6)
    values[0]["state"] = "mixed"
    values[1]["state"] = "failed"
    result = analyze_diagnosis(overview(), samples=values, now=NOW)
    assert "recent_instability" in codes(result)


def test_loaded_increase_requires_fresh_and_measured_delta():
    loaded = {"tested_at": NOW.isoformat(), "status": "increase_observed", "change_ms": 65}
    result = analyze_diagnosis(overview(), loaded=loaded, now=NOW)
    assert "load_delay" in codes(result)
    loaded["tested_at"] = (NOW - timedelta(minutes=18)).isoformat()
    assert "load_delay" not in codes(analyze_diagnosis(overview(), loaded=loaded, now=NOW))


def test_inconclusive_loaded_test_is_not_classified_failure():
    loaded = {"tested_at": NOW.isoformat(), "status": "inconclusive"}
    result = analyze_diagnosis(overview(), loaded=loaded, now=NOW)
    assert "load_delay" not in codes(result)
    assert "inconclusive" in " ".join(result["notes"])


def test_vpn_and_proxy_are_possible_not_verified_causes():
    view = overview(vpn="Possible tunnel route", proxy="Configured")
    result = analyze_diagnosis(view, now=NOW)
    for item in result["findings"]:
        if item["code"] in {"tunnel_route", "proxy_configured"}:
            assert item["kind"] == "possible"
    assert {"tunnel_route", "proxy_configured"} <= codes(result)


def test_priority_and_no_network_or_location_requirement():
    result = analyze_diagnosis(overview(status="unverified", signal=30, wifi_status="Connected"), now=NOW)
    assert result["findings"][0]["code"] == "access_unverified"
    assert "No network settings" in result["limitation"]


def test_timezone_validation_and_malformed_input():
    with pytest.raises(ValueError):
        analyze_diagnosis(now=NOW.replace(tzinfo=None))
    result = analyze_diagnosis(None, reading={"tested_at": "garbage", "latency_ms": float("nan")}, now=NOW)
    assert result["speed_fresh"] is False
