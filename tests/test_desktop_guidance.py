
"""Stage 10: plain-English guidance must follow evidence, not invented scores."""

from dataclasses import replace

import pytest

from netdoctor.desktop_support import explain, export_content, present
from netdoctor.doctor import DoctorReport
from netdoctor.dnsdiagnostics import DnsObservation, DnsReport
from netdoctor.icmp import EchoResult
from netdoctor.latency import LatencyReport, _summarize
from netdoctor.models import Adapter, DefaultRoute, EndpointCheck, Report, Snapshot


def sample_report(*, connected=2, dns_status="answered",
                  google_ms=25, cloudflare_ms=25, gateway_replies=4,
                  latency_present=True, dns_present=True):
    snapshot = Snapshot(
        (Adapter(6, "WiFi", "Wireless", "Up", "100 Mbps", "Wi-Fi (inferred)",
                 ("192.168.1.10",), (), ("192.168.1.1",)),),
        (DefaultRoute("IPv4", 6, "192.168.1.1", 0, 35),), (),
    )
    checks = tuple(EndpointCheck(
        f"test{i}.example", True, i < connected, "observed"
    ) for i in range(2))
    status = "reachable" if connected == 2 else "partial" if connected else "unverified"
    internet = Report(snapshot, checks, (), status)
    dns = DnsReport("WiFi", ("192.168.1.1",), (
        DnsObservation(
            "192.168.1.1", "example.com", dns_status,
            5 if dns_status == "answered" else None,
            ("93.184.215.14",) if dns_status == "answered" else (),
            0 if dns_status == "answered" else None, "observed",
        ),
    ), ()) if dns_present else None
    gateway = tuple(
        EchoResult("reply", 4., "ok") if i < gateway_replies
        else EchoResult("timeout", None, "no reply")
        for i in range(4)
    )
    latency = LatencyReport((
        _summarize("Gateway", "192.168.1.1", "gateway", gateway),
        _summarize("Cloudflare DNS", "1.1.1.1", "public",
                   tuple(EchoResult("reply", float(cloudflare_ms), "ok") for _ in range(4))),
        _summarize("Google DNS", "8.8.8.8", "public",
                   tuple(EchoResult("reply", float(google_ms), "ok") for _ in range(4))),
    ), ()) if latency_present else None
    return DoctorReport(
        "reachable" if connected == 2 else "attention" if connected else "unverified",
        "A short connection test.", "WiFi", "192.168.1.1",
        internet, dns, latency, (), (),
    )


def test_healthy_summary_says_basic_connectivity_not_full_internet_rating():
    guide = explain(sample_report())
    assert guide.headline == "Your basic internet connection is working"
    assert "speed test" in guide.explanation
    assert guide.observation_title == "No obvious issue in these basic checks"
    assert "Wi-Fi signal" in guide.limitation


def test_public_rtt_difference_is_not_mislabeled_as_overall_slowness():
    guide = explain(sample_report(google_ms=20.5, cloudflare_ms=167.5))
    assert "much more slowly" in guide.observation_title
    assert "Cloudflare DNS" in guide.observation
    assert "Google DNS" in guide.observation
    assert "168" in guide.observation
    assert "20" in guide.observation
    assert "doesn't prove all websites are slow" in guide.observation
    assert guide.observation_tone == "neutral"


@pytest.mark.parametrize("connected", [0, 1])
def test_partial_or_failed_tcp_takes_priority_over_ping_differences(connected):
    guide = explain(sample_report(connected=connected, cloudflare_ms=200))
    assert "connection checks need another look" in guide.observation_title
    assert guide.checks[0].tone != "good"
    assert "website" in guide.next_step


def test_zero_success_does_not_claim_the_network_is_down():
    guide = explain(sample_report(connected=0))
    assert "couldn't confirm" in guide.headline
    assert "your internet is down" not in guide.explanation.lower()


def test_dns_timeout_without_tcp_outage_is_not_a_dns_failure_diagnosis():
    guide = explain(sample_report(dns_status="timeout", cloudflare_ms=210))
    assert "lookups" in guide.observation_title
    assert "alone" in guide.observation
    assert "don't change DNS settings" in guide.next_step
    assert guide.headline == "Your basic internet connection is working"


def test_unavailable_dns_is_neutral_not_good():
    guide = explain(sample_report(dns_present=False))
    assert guide.checks[1].result == "Not checked"
    assert guide.checks[1].tone == "neutral"


def test_missing_latency_is_not_displayed_as_good_response_time():
    guide = explain(sample_report(latency_present=False))
    assert guide.checks[2].result == "Not checked"
    assert guide.checks[2].tone == "neutral"


def test_gateway_one_missed_echo_does_not_trigger_router_repair():
    guide = explain(sample_report(gateway_replies=3))
    assert "didn't answer every ping" in guide.observation_title
    assert "Some routers limit ping replies" in guide.observation
    assert "Don't restart" in guide.next_step


def test_missing_ping_replies_are_not_automatically_packet_loss():
    guide = explain(sample_report(gateway_replies=0))
    assert "router" in guide.observation_title.lower()
    assert "packet loss" not in guide.observation.lower()


def test_text_export_starts_with_conclusions_and_is_useful_to_share():
    report = sample_report(google_ms=22, cloudflare_ms=190)
    contents = export_content(report, kind="txt", checked_at="today")
    assert contents.index("WHAT WE NOTICED") < contents.index("DETAILED FINDINGS")
    assert "WHAT TO DO NEXT" in contents
    assert "QUICK CHECKS" in contents
    assert "LIMITATIONS" in contents


def test_json_preserves_existing_doctor_schema_unchanged():
    import json
    report = sample_report()
    exported = json.loads(export_content(report, kind="json", checked_at="today"))
    assert exported == json.loads(json.dumps(report.to_dict()))


def test_legacy_evidence_api_remains_available_for_regressions():
    view = present(sample_report())
    assert view.headline == "Basic internet access confirmed"
    assert view.evidence[0].state == "Connected"
    assert view.evidence[1].state == "Responded"


def test_no_connection_checks_are_not_invented():
    report = sample_report()
    empty = replace(report, connectivity=replace(report.connectivity, checks=()))
    guide = explain(empty)
    assert guide.checks[0].result == "Not confirmed"
    assert guide.tone == "neutral"
