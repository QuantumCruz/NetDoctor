"""Stage 9 presentation, export and background-worker tests (no Tk display needed)."""

import json
import threading

import pytest

from netdoctor.desktop_support import (
    DiagnosticWorker,
    WorkerFailure,
    export_content,
    present,
    text_report,
)
from netdoctor.doctor import DoctorReport, DoctorStep
from netdoctor.dnsdiagnostics import DnsObservation, DnsReport
from netdoctor.icmp import EchoResult
from netdoctor.latency import LatencyReport, _summarize
from netdoctor.models import (
    Adapter,
    DefaultRoute,
    EndpointCheck,
    Finding,
    Report,
    Snapshot,
)
from netdoctor.windows import DiscoveryError


def _report(
    *,
    status="reachable",
    connected=2,
    dns_answers=1,
    icmp_replies=4,
):
    snapshot = Snapshot(
        (
            Adapter(
                6,
                "WiFi",
                "Wireless",
                "Up",
                "100 Mbps",
                "Wi-Fi (inferred)",
                ("192.168.1.10",),
                (),
                ("192.168.1.1",),
            ),
        ),
        (
            DefaultRoute(
                "IPv4", 6, "192.168.1.1", 0, 35
            ),
        ),
        (),
    )

    checks = tuple(
        EndpointCheck(
            f"site{i}.example",
            True,
            i < connected,
            "test",
        )
        for i in range(2)
    )

    connectivity = Report(
        snapshot,
        checks,
        (),
        "reachable" if connected == 2 else "partial",
    )

    observations = (
        DnsObservation(
            "192.168.1.1",
            "example.com",
            "answered" if dns_answers else "timeout",
            20 if dns_answers else None,
            ("93.184.215.14",) if dns_answers else (),
            0 if dns_answers else None,
            "test",
        ),
    )

    dns = DnsReport(
        "WiFi",
        ("192.168.1.1",),
        observations,
        (),
    )

    samples = tuple(
        EchoResult("reply", 4.0, "ok")
        if i < icmp_replies
        else EchoResult("timeout", None, "no")
        for i in range(4)
    )

    latency = LatencyReport(
        (
            _summarize(
                "Gateway",
                "192.168.1.1",
                "gateway",
                samples,
            ),
        ),
        (),
    )

    finding = Finding(
        "info",
        "Sample finding",
        "A measured observation.",
        "Try the test again.",
    )

    return DoctorReport(
        status,
        "Basic checks completed.",
        "WiFi",
        "192.168.1.1",
        connectivity,
        dns,
        latency,
        (
            DoctorStep(
                "internet", "completed", "done"
            ),
        ),
        (finding,),
    )


def test_present_basic_connection_does_not_claim_ideal_speed():
    view = present(_report())

    assert view.headline == "Basic internet access confirmed"
    assert view.interface == "WiFi"
    assert view.evidence[0].state == "Connected"
    assert "speed" not in view.headline.lower()


def test_partial_connection_is_not_displayed_as_confirmed():
    view = present(
        _report(status="attention", connected=1)
    )

    assert view.evidence[0].state == "Mixed results"
    assert view.evidence[0].tone == "warning"


def test_unconfirmed_connection_has_uncertain_heading():
    view = present(
        _report(status="unverified", connected=0)
    )

    assert view.headline == "Internet access not confirmed"
    assert view.evidence[0].state == "Not confirmed"


def test_partial_dns_does_not_get_green_success():
    view = present(
        _report(dns_answers=0)
    )

    assert view.evidence[1].state == "Needs context"
    assert view.evidence[1].tone == "warning"


def test_missing_dns_and_latency_are_not_assumed_healthy():
    from dataclasses import replace

    report = _report()
    view = present(
        replace(report, dns=None, latency=None)
    )

    assert view.evidence[1].state == "Not checked"
    assert view.evidence[2].state == "Not checked"


def test_no_icmp_replies_is_not_classified_as_healthy():
    view = present(
        _report(icmp_replies=0)
    )

    assert view.evidence[2].state == "Not confirmed"
    assert view.evidence[2].tone == "neutral"


def test_report_text_contains_findings_actions_and_limitations():
    output = text_report(
        _report(),
        checked_at="2026-10-22 14:00 WAT",
    )

    assert "2026-10-22 14:00 WAT" in output
    assert "Sample finding" in output
    assert "Suggested next step: Try the test again." in output
    assert "LIMITATIONS" in output


def test_export_json_preserves_diagnostic_fields():
    output = export_content(
        _report(),
        kind="json",
        checked_at="example",
    )

    data = json.loads(output)

    assert (
        data["connectivity"]["checks"][0]["host"]
        == "site0.example"
    )
    assert (
        data["latency"]["targets"][0]["replies"]
        == 4
    )


def test_export_txt_matches_presented_report():
    report = _report()

    assert export_content(
        report,
        kind="txt",
        checked_at="now",
    ) == text_report(
        report,
        checked_at="now",
    )


def test_export_unknown_extension_is_rejected():
    with pytest.raises(
        ValueError,
        match="Only txt and json",
    ):
        export_content(
            _report(),
            kind="html",
            checked_at="now",
        )


def test_worker_does_not_do_networking_before_start():
    called = []

    worker = DiagnosticWorker(
        collector=lambda: called.append("scan"),
        diagnosis=lambda *a, **kw: _report(),
    )

    assert called == []
    assert worker.start() is True

    worker._thread.join(timeout=2)

    assert called == ["scan"]
    assert worker.events.get_nowait().kind == "progress"
    assert worker.events.get_nowait().kind == "success"


def test_worker_does_not_allow_overlapping_runs():
    entered = threading.Event()
    release = threading.Event()

    def collect():
        entered.set()
        assert release.wait(2)
        return object()

    worker = DiagnosticWorker(
        collector=collect,
        diagnosis=lambda *a, **kw: _report(),
    )

    assert worker.start()
    assert entered.wait(2)
    assert worker.start() is False

    release.set()
    worker._thread.join(timeout=2)

    assert not worker.running


def test_worker_emits_progress_and_success_without_tk_calls():
    def run(_snapshot, *, on_step):
        on_step("Checking DNS")
        return _report()

    worker = DiagnosticWorker(
        collector=lambda: object(),
        diagnosis=run,
    )

    worker.start()
    worker._thread.join(timeout=2)

    events = list(worker.events.queue)

    assert [
        event.kind for event in events
    ] == ["progress", "progress", "success"]

    assert events[1].value == "Checking DNS"


def test_worker_classifies_windows_discovery_error():
    def fail():
        raise DiscoveryError(
            "Windows network scan failed"
        )

    worker = DiagnosticWorker(
        collector=fail
    )

    worker.start()
    worker._thread.join(timeout=2)

    events = list(worker.events.queue)

    assert events[-1].kind == "failure"
    assert isinstance(
        events[-1].value,
        WorkerFailure,
    )
    assert events[-1].value.code == "ND-101"


def test_worker_does_not_expose_unexpected_exception_details():
    def fail():
        raise RuntimeError(
            "internal secret error"
        )

    worker = DiagnosticWorker(
        collector=fail
    )

    worker.start()
    worker._thread.join(timeout=2)

    failure = list(worker.events.queue)[-1].value

    assert failure.code == "ND-701"
    assert "internal secret" not in failure.message


def test_worker_can_restart_and_old_events_are_discarded():
    worker = DiagnosticWorker(
        collector=lambda: object(),
        diagnosis=lambda *a, **kw: _report(),
    )

    worker.start()
    worker._thread.join(timeout=2)

    worker.start()
    worker._thread.join(timeout=2)

    assert [
        event.kind
        for event in list(worker.events.queue)
    ] == ["progress", "success"]