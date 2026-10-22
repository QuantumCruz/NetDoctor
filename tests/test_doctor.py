
"""Unified diagnosis must not turn optional-test gaps into internet outages."""

import json

import pytest

from netdoctor.dnsdiagnostics import DnsDiagnosticError, DnsObservation, DnsReport
from netdoctor.doctor import run_doctor
from netdoctor.icmp import EchoResult, ProbeError
from netdoctor.latency import LatencyReport, _summarize
from netdoctor.models import Adapter, DefaultRoute, EndpointCheck, Snapshot


def _snapshot(*, route=True, active=True, warnings=()):
    adapter = Adapter(
        6, "WiFi", "Wireless", "Up" if active else "Disconnected", "866 Mbps",
        "Wi-Fi (inferred)", ("192.168.1.10",), (), ("192.168.1.1",),
    )
    paths = (DefaultRoute("IPv4", 6, "192.168.1.1", 10, 25),) if route else ()
    return Snapshot((adapter,), paths, tuple(warnings))


def _endpoint(host, *, timeout, success=True):
    return EndpointCheck(host, True, success, "TCP connected" if success else "TCP failed")


def _dns(snapshot, *, hostnames, timeout, status="answered"):
    return DnsReport(
        "WiFi", ("192.168.1.1",),
        (DnsObservation("192.168.1.1", hostnames[0], status,
                        8.0 if status == "answered" else None,
                        ("93.184.215.14",) if status == "answered" else (),
                        0 if status == "answered" else None, "observed"),),
        (),
    )


def _latency(snapshot, *, count, timeout_ms, interval, gateway_replies=4, different=False):
    assert count == 4
    assert 100 <= timeout_ms <= 1000
    samples = tuple(
        EchoResult("reply", 4.0, "ok") if i < gateway_replies
        else EchoResult("timeout", None, "no reply")
        for i in range(count)
    )
    return LatencyReport((
        _summarize("Local gateway", "192.168.1.1", "gateway", samples),
        _summarize("Cloudflare DNS", "1.1.1.1", "public",
                   tuple(EchoResult("reply", 190.0 if different else 30.0, "ok")
                         for _ in range(count))),
        _summarize("Google DNS", "8.8.8.8", "public",
                   tuple(EchoResult("reply", 30.0, "ok") for _ in range(count))),
    ), ())


def _run(snapshot=None, *, endpoint=None, dns=None, latency=None, **kwargs):
    return run_doctor(
        snapshot or _snapshot(),
        endpoint_test=endpoint or _endpoint,
        dns_test=dns or _dns,
        latency_test=latency or _latency,
        **kwargs,
    )


def test_healthy_tcp_dns_and_gateway_produce_reachable_summary():
    report = _run()
    assert report.status == "reachable"
    assert report.interface == "WiFi"
    assert report.gateway == "192.168.1.1"
    assert len(report.connectivity.checks) == 2
    assert [step.status for step in report.steps] == ["completed"] * 3
    assert any("Gateway answered" in f.title for f in report.findings)


def test_partial_https_is_attention_not_total_outage():
    report = _run(endpoint=lambda host, *, timeout: _endpoint(
        host, timeout=timeout, success="cloudflare" in host
    ))
    assert report.status == "attention"
    assert "one destination" in report.summary.lower()
    assert not any("internet is down" in f.explanation.lower() for f in report.findings)


def test_both_https_checks_fail_reports_unverified_not_proven_offline():
    report = _run(endpoint=lambda host, *, timeout: _endpoint(
        host, timeout=timeout, success=False
    ))
    assert report.status == "unverified"
    assert "could not be confirmed" in report.summary


def test_dns_timeout_does_not_cancel_successful_https():
    report = _run(dns=lambda snap, *, hostnames, timeout: _dns(
        snap, hostnames=hostnames, timeout=timeout, status="timeout"
    ))
    assert report.status == "reachable"
    assert report.steps[1].status == "completed"
    assert any("need context" in f.title.lower() for f in report.findings)


def test_dns_exception_keeps_other_results():
    def fail_dns(*args, **kwargs):
        raise DnsDiagnosticError("DNS collection unavailable")
    report = _run(dns=fail_dns)
    assert report.status == "reachable"
    assert report.steps[1].status == "unavailable"
    assert report.steps[2].status == "completed"


def test_native_ping_failure_does_not_reverse_tcp_success():
    def fail_latency(*args, **kwargs):
        raise ProbeError("ICMP blocked")
    report = _run(latency=fail_latency)
    assert report.status == "reachable"
    assert report.steps[2].status == "unavailable"
    assert report.latency is None


def test_no_ipv4_route_skips_dns_without_guessing_server():
    def unexpected(*args, **kwargs):
        raise AssertionError("DNS should not run")
    report = _run(_snapshot(route=False), dns=unexpected)
    assert report.steps[1].status == "skipped"
    assert report.dns is None
    assert report.status == "reachable"


def test_disconnected_adapter_skips_latency():
    def unexpected(*args, **kwargs):
        raise AssertionError("Latency should not run")
    report = _run(_snapshot(active=False), latency=unexpected)
    assert report.steps[2].status == "skipped"


def test_partial_gateway_echo_is_not_claimed_router_failure():
    report = _run(latency=lambda snap, **kw: _latency(
        snap, gateway_replies=2, **kw
    ))
    assert report.status == "reachable"
    assert any("Gateway ICMP evidence is limited" in f.title for f in report.findings)


def test_large_external_latency_difference_is_target_specific():
    report = _run(latency=lambda snap, **kw: _latency(snap, different=True, **kw))
    assert any("varies by destination" in f.title for f in report.findings)
    assert not any("ISP" in f.explanation for f in report.findings)


def test_local_collection_warning_is_explained_not_hidden():
    report = _run(_snapshot(warnings=("Partial route data",)))
    assert any("incomplete" in f.title for f in report.findings)
    assert report.status == "reachable"


def test_progress_and_json_are_structured():
    names = []
    report = _run(on_step=names.append)
    assert names == [
        "Checking basic internet connections",
        "Checking configured DNS server",
        "Sampling gateway and public responsiveness",
    ]
    result = json.loads(json.dumps(report.to_dict()))
    assert result["status"] == "reachable"
    assert result["dns"]["observations"][0]["status"] == "answered"
    assert result["latency"]["targets"][0]["median_ms"] == 4.0


@pytest.mark.parametrize("timeout", [0, -1, 3.1, float("nan"), float("inf")])
def test_invalid_timeout_rejected(timeout):
    with pytest.raises(ValueError):
        _run(timeout=timeout)
