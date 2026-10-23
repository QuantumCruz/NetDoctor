
"""User-facing explanation, report export and background work for NetDoctor.

Keep technical measurements separate from conclusions. The main dashboard must
not label TCP port 443 as a complete HTTPS request or ICMP as internet speed.
"""

import json
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Literal

from netdoctor.doctor import DoctorReport, run_doctor
from netdoctor.windows import DiscoveryError, collect_snapshot


@dataclass(frozen=True)
class Evidence:
    name: str
    state: str
    detail: str
    tone: Literal["good", "warning", "neutral"]


@dataclass(frozen=True)
class DesktopView:
    headline: str
    summary: str
    interface: str
    gateway: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class PlainCheck:
    title: str
    result: str
    explanation: str
    tone: Literal["good", "warning", "neutral"]


@dataclass(frozen=True)
class Guidance:
    """The small set of conclusions a nontechnical user sees first."""

    headline: str
    explanation: str
    tone: Literal["good", "warning", "neutral"]
    observation_title: str
    observation: str
    observation_tone: Literal["good", "warning", "neutral"]
    next_step: str
    checks: tuple[PlainCheck, ...]
    limitation: str = (
        "This quick check does not measure your subscribed internet speed, "
        "Wi-Fi signal strength, or whether your connection drops over time."
    )


def present(report: DoctorReport) -> DesktopView:
    """Retain the established structured evidence API for reports and tests."""
    headlines = {
        "reachable": "Basic internet access confirmed",
        "attention": "Connection results need attention",
        "unverified": "Internet access not confirmed",
    }
    checks = report.connectivity.checks
    connected = sum(check.tcp_ok for check in checks)
    total = len(checks)

    if total and connected == total:
        internet = Evidence(
            "Internet access", "Connected",
            f"{connected}/{total} public connection checks succeeded.", "good",
        )
    elif connected:
        internet = Evidence(
            "Internet access", "Mixed results",
            f"{connected}/{total} public connection checks succeeded.", "warning",
        )
    else:
        internet = Evidence(
            "Internet access", "Not confirmed",
            f"{connected}/{total} public connection checks succeeded.", "neutral",
        )

    observations = report.dns.observations if report.dns is not None else ()
    dns_answers = sum(item.status == "answered" for item in observations)
    if observations and dns_answers == len(observations):
        dns = Evidence(
            "Name resolution", "Responded",
            f"{dns_answers}/{len(observations)} direct DNS queries returned IPv4 addresses.",
            "good",
        )
    elif observations:
        dns = Evidence(
            "Name resolution", "Needs context",
            f"{dns_answers}/{len(observations)} direct DNS queries returned IPv4 addresses.",
            "warning",
        )
    else:
        dns = Evidence(
            "Name resolution", "Not checked",
            "A direct DNS result was unavailable.", "neutral",
        )

    targets = report.latency.targets if report.latency is not None else ()
    replies = sum(item.replies for item in targets)
    attempts = sum(item.sent for item in targets)
    if attempts and replies:
        latency = Evidence(
            "Responsiveness", "Measured",
            f"{replies}/{attempts} ICMP echo requests received replies.", "good",
        )
    elif attempts:
        latency = Evidence(
            "Responsiveness", "Not confirmed",
            f"No ICMP replies from {attempts} attempts; filtering is possible.",
            "neutral",
        )
    else:
        latency = Evidence(
            "Responsiveness", "Not checked",
            "Latency sampling was unavailable.", "neutral",
        )

    return DesktopView(
        headline=headlines[report.status],
        summary=report.summary,
        interface=report.interface or "Not determined",
        gateway=report.gateway or "Not determined",
        evidence=(internet, dns, latency),
    )


def explain(report: DoctorReport) -> Guidance:
    """Generate honest conclusions from measurements, never a fake health score."""
    checks = report.connectivity.checks
    connected = sum(item.tcp_ok for item in checks)
    checked = len(checks)
    observations = report.dns.observations if report.dns else ()
    dns_answers = sum(item.status == "answered" for item in observations)
    targets = report.latency.targets if report.latency else ()
    echo_replies = sum(item.replies for item in targets)
    echo_sent = sum(item.sent for item in targets)

    if checked and connected == checked:
        headline = "Your basic internet connection is working"
        explanation = (
            "Your computer connected to both test destinations. "
            "That confirms basic connectivity, but it isn't a speed test."
        )
        tone: Literal["good", "warning", "neutral"] = "good"
        connection_card = PlainCheck(
            "Connecting to the internet", "Working",
            f"Connected to {connected} of {checked} public test destinations.", "good",
        )
    elif connected:
        headline = "Some internet connections may be having trouble"
        explanation = (
            f"Your computer connected to {connected} of {checked} test destinations. "
            "The problem might affect only some services."
        )
        tone = "warning"
        connection_card = PlainCheck(
            "Connecting to the internet", "Mixed results",
            f"Connected to {connected} of {checked} public test destinations.",
            "warning",
        )
    else:
        headline = "We couldn't confirm internet access"
        explanation = (
            "Neither public connection check succeeded. This doesn't yet tell us "
            "whether the cause is your Wi-Fi, router, DNS or another network."
            if checked else
            "Public connection checks were unavailable; we can't confirm access."
        )
        tone = "warning" if checked else "neutral"
        connection_card = PlainCheck(
            "Connecting to the internet", "Not confirmed",
            f"Connected to {connected} of {checked} public test destinations.",
            "neutral",
        )

    if observations and dns_answers == len(observations):
        dns_card = PlainCheck(
            "Finding website addresses", "Working in this test",
            f"{dns_answers} of {len(observations)} direct lookups returned addresses.",
            "good",
        )
    elif observations:
        dns_card = PlainCheck(
            "Finding website addresses", "Mixed or missing replies",
            f"{dns_answers} of {len(observations)} direct lookups returned addresses. "
            "Windows may resolve names differently.",
            "warning",
        )
    else:
        dns_card = PlainCheck(
            "Finding website addresses", "Not checked",
            "We couldn't test a configured DNS server directly.", "neutral",
        )

    if echo_sent:
        probe_card = PlainCheck(
            "Quick response checks",
            f"{echo_replies} of {echo_sent} replied",
            "These short ping checks don't measure download speed or Wi-Fi quality.",
            "good" if echo_replies == echo_sent else "neutral",
        )
    else:
        probe_card = PlainCheck(
            "Quick response checks", "Not checked",
            "We couldn't collect reliable ping measurements.", "neutral",
        )

    # Priority order: failed public access, uncertain configured DNS, then
    # destination-specific differences, then limited ICMP evidence.
    if not checked or connected < checked:
        observation_title = "The connection checks need another look"
        observation = (
            "Some destinations didn't accept a connection. This could be temporary "
            "or specific to those destinations; it isn't proof your internet is down."
        )
        next_step = (
            "Try opening a website you normally use. If it fails, check whether "
            "another site opens, then run this check again."
        )
        observation_tone: Literal["good", "warning", "neutral"] = "warning"
    elif observations and dns_answers < len(observations):
        observation_title = "Some direct website-name lookups didn't return addresses"
        observation = (
            "Your public connection checks succeeded, so these DNS responses alone "
            "don't prove websites are failing to load."
        )
        next_step = (
            "Try the website that worries you. If it loads normally, don't change "
            "DNS settings based on this short test."
        )
        observation_tone = "warning"
    else:
        public = [
            target for target in targets
            if target.role != "gateway" and target.replies >= 2
            and target.median_ms is not None
        ]
        distant = None
        close = None
        if len(public) >= 2:
            distant = max(public, key=lambda item: item.median_ms)
            close = min(public, key=lambda item: item.median_ms)

        if (distant is not None and close is not None
                and distant.median_ms - close.median_ms >= 80):
            observation_title = "One destination replied much more slowly than another"
            observation = (
                f"{distant.name} replied in about {distant.median_ms:.0f} ms, "
                f"versus {close.median_ms:.0f} ms for {close.name}. "
                "Routes and how destinations handle ping can explain this; "
                "it doesn't prove all websites are slow."
            )
            next_step = (
                "If a particular app or website feels slow, check that specific "
                "service. Repeat this diagnosis later to see if the difference persists."
            )
            observation_tone = "neutral"
        else:
            gateway = next((t for t in targets if t.role == "gateway"), None)
            if gateway is not None and gateway.sent > gateway.replies:
                observation_title = "Your router didn't answer every ping"
                observation = (
                    f"It answered {gateway.replies} of {gateway.sent} short requests. "
                    "Some routers limit ping replies even when normal traffic works."
                )
                next_step = (
                    "If the connection keeps dropping, repeat the check during a "
                    "drop. Don't restart or reconfigure the router based on pings alone."
                )
                observation_tone = "neutral"
            else:
                observation_title = "No obvious issue in these basic checks"
                observation = (
                    "The quick connection checks did not reveal a clear problem. "
                    "A slow or unstable connection can still pass these tests."
                )
                next_step = (
                    "If you're having trouble, note whether it's slow internet, "
                    "disconnections, or one specific website. A targeted check can help."
                )
                observation_tone = "good"

    return Guidance(
        headline=headline,
        explanation=explanation,
        tone=tone,
        observation_title=observation_title,
        observation=observation,
        observation_tone=observation_tone,
        next_step=next_step,
        checks=(connection_card, dns_card, probe_card),
    )


def text_report(report: DoctorReport, *, checked_at: str) -> str:
    """Readable evidence, with a practical explanation before technical findings."""
    view = present(report)
    guide = explain(report)
    lines = [
        "NetDoctor - Network check",
        f"Checked: {checked_at}",
        "",
        guide.headline,
        guide.explanation,
        "",
        "WHAT WE NOTICED",
        guide.observation_title,
        guide.observation,
        "",
        "WHAT TO DO NEXT",
        guide.next_step,
        "",
        "QUICK CHECKS",
    ]
    for card in guide.checks:
        lines.extend((f"{card.title}: {card.result}", f"  {card.explanation}"))
    lines.extend((
        "", f"Internet-facing interface: {view.interface}",
        f"Reported gateway: {view.gateway}", "",
        "DETAILED FINDINGS",
    ))
    if not report.findings:
        lines.append("No additional findings were recorded.")
    for finding in report.findings:
        lines.extend((
            f"{finding.severity.upper()}: {finding.title}",
            f"  {finding.explanation}",
            f"  Suggested next step: {finding.action}",
        ))
    lines.extend(("", "LIMITATIONS", guide.limitation, report.note, ""))
    return "\n".join(lines)


def export_content(
    report: DoctorReport, *, kind: Literal["txt", "json"], checked_at: str
) -> str:
    if kind == "txt":
        return text_report(report, checked_at=checked_at)
    if kind == "json":
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
    raise ValueError("Only txt and json report exports are supported.")


@dataclass(frozen=True)
class WorkerFailure:
    code: str
    message: str


@dataclass(frozen=True)
class WorkerEvent:
    kind: Literal["progress", "success", "failure"]
    value: str | DoctorReport | WorkerFailure


class DiagnosticWorker:
    """Run networking outside the UI thread, publishing immutable queue events."""

    def __init__(
        self,
        *,
        collector: Callable[[], object] = collect_snapshot,
        diagnosis: Callable[..., DoctorReport] = run_doctor,
    ) -> None:
        self.collector = collector
        self.diagnosis = diagnosis
        self.events: queue.Queue[WorkerEvent] = queue.Queue()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if self.running:
            return False
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break
        self._thread = threading.Thread(
            target=self._work, name="NetDoctorDesktopCheck", daemon=True
        )
        self._thread.start()
        return True

    def _work(self) -> None:
        def progress(message: str) -> None:
            self.events.put(WorkerEvent("progress", message))

        try:
            progress("Reading Windows network settings...")
            snapshot = self.collector()
            report = self.diagnosis(snapshot, on_step=progress)
        except DiscoveryError as exc:
            self.events.put(WorkerEvent("failure", WorkerFailure("ND-101", str(exc))))
        except Exception:
            self.events.put(WorkerEvent(
                "failure",
                WorkerFailure(
                    "ND-701",
                    "The network check encountered an unexpected error. "
                    "Try again; if it persists, use the command-line diagnostics.",
                ),
            ))
        else:
            self.events.put(WorkerEvent("success", report))
