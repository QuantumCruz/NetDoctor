
"""One-command, evidence-first diagnosis using existing read-only checks.

The doctor reports what was measured, what could not be measured, and what
remains uncertain. It does not claim to identify a particular ISP fault.
"""

from dataclasses import asdict, dataclass
from typing import Callable, Literal

from netdoctor.checks import TEST_HOSTS, check_endpoint, diagnose
from netdoctor.dnsdiagnostics import DnsDiagnosticError, DnsReport, diagnose_dns
from netdoctor.icmp import ProbeError
from netdoctor.latency import LatencyError, LatencyReport, measure_latency
from netdoctor.models import EndpointCheck, Finding, Report, Snapshot


@dataclass(frozen=True)
class DoctorStep:
    name: Literal["internet", "dns", "responsiveness"]
    status: Literal["completed", "skipped", "unavailable"]
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    status: Literal["reachable", "attention", "unverified"]
    summary: str
    interface: str | None
    gateway: str | None
    connectivity: Report
    dns: DnsReport | None
    latency: LatencyReport | None
    steps: tuple[DoctorStep, ...]
    findings: tuple[Finding, ...]
    note: str = (
        "This is a short, read-only snapshot. Successful TCP connections do not "
        "measure browsing speed; ICMP reply gaps do not prove application packet "
        "loss; direct UDP DNS checks do not reproduce all Windows DNS policies."
    )

    def to_dict(self) -> dict:
        return asdict(self)


def run_doctor(
    snapshot: Snapshot,
    *,
    timeout: float = 1.5,
    endpoint_test: Callable[..., EndpointCheck] | None = None,
    dns_test: Callable[..., DnsReport] | None = None,
    latency_test: Callable[..., LatencyReport] | None = None,
    on_step: Callable[[str], None] | None = None,
) -> DoctorReport:
    """Run bounded independent tests; optional-test failure is not internet failure."""
    if not 0.1 <= timeout <= 3.0:
        raise ValueError("Doctor timeout must be between 0.1 and 3 seconds.")

    endpoint = endpoint_test or check_endpoint
    query_dns = dns_test or diagnose_dns
    check_latency = latency_test or measure_latency
    emit = on_step or (lambda _name: None)
    steps: list[DoctorStep] = []
    findings: list[Finding] = []

    route = snapshot.preferred_route("IPv4") or snapshot.preferred_route("IPv6")
    adapter = next(
        (item for item in snapshot.adapters if route and item.index == route.interface_index),
        None,
    )
    gateway = route.next_hop if route else None

    emit("Checking basic internet connections")
    checks = tuple(endpoint(host, timeout=timeout) for host in TEST_HOSTS)
    connectivity = diagnose(snapshot, checks)
    reachable = sum(item.tcp_ok for item in checks)
    steps.append(DoctorStep(
        "internet", "completed", f"{reachable}/{len(checks)} HTTPS TCP destinations responded."
    ))

    if reachable == len(checks):
        overall: Literal["reachable", "attention", "unverified"] = "reachable"
        summary = "Basic internet connectivity was confirmed to both test hosts."
        findings.append(Finding(
            "good", "Public HTTPS connections succeeded",
            "Both independent test hosts accepted a TCP connection on port 443. "
            "This does not establish speed or uninterrupted availability.",
            "No connectivity repair is indicated by these specific checks.",
        ))
    elif reachable:
        overall = "attention"
        summary = "One destination responded, while another did not."
        findings.append(Finding(
            "warning", "Internet connectivity varied by destination",
            "One public host accepted a TCP connection while another did not. "
            "A destination-specific issue or transient filtering is possible.",
            "Retry the test and use 'netdoctor investigate' if the difference persists.",
        ))
    else:
        overall = "unverified"
        summary = "Internet reachability could not be confirmed by these checks."
        findings.append(Finding(
            "warning", "Web connection checks were unsuccessful",
            "Neither test host accepted a TCP connection. The results alone cannot "
            "distinguish DNS, routing, filtering, or remote problems.",
            "Check whether a normal HTTPS website opens; use 'netdoctor scan' for details.",
        ))

    if snapshot.warnings:
        findings.append(Finding(
            "info", "Some local network data was incomplete",
            "; ".join(dict.fromkeys(snapshot.warnings)),
            "Review the detailed scan before making configuration changes.",
        ))

    dns_report: DnsReport | None = None
    if snapshot.preferred_route("IPv4") is None:
        steps.append(DoctorStep(
            "dns", "skipped", "No usable IPv4 default route for selecting a DNS server."
        ))
    else:
        emit("Checking configured DNS server")
        try:
            dns_report = query_dns(
                snapshot, hostnames=("example.com",), timeout=min(timeout, 1.5)
            )
        except (DnsDiagnosticError, OSError) as exc:
            steps.append(DoctorStep("dns", "unavailable", str(exc)))
        else:
            observations = dns_report.observations
            if not observations:
                steps.append(DoctorStep(
                    "dns", "skipped", "No direct IPv4 DNS query could be made."
                ))
            else:
                answers = sum(item.status == "answered" for item in observations)
                steps.append(DoctorStep(
                    "dns", "completed", f"{answers}/{len(observations)} direct DNS queries returned A records."
                ))
                if answers == len(observations):
                    findings.append(Finding(
                        "good", "Configured DNS responded to direct queries",
                        "The tested resolver or resolvers returned an IPv4 address for example.com.",
                        "No DNS configuration change is indicated by these results.",
                    ))
                else:
                    findings.append(Finding(
                        "info", "Direct DNS results need context",
                        "Some direct UDP port 53 queries did not return IPv4 addresses. "
                        "Windows may still resolve names through caching, VPN rules, or encrypted DNS.",
                        "Compare this with real website access before changing DNS settings.",
                    ))

    latency_report: LatencyReport | None = None
    if not any(item.is_up for item in snapshot.adapters):
        steps.append(DoctorStep(
            "responsiveness", "skipped", "No active adapter was reported by Windows."
        ))
    else:
        emit("Sampling gateway and public responsiveness")
        try:
            latency_report = check_latency(
                snapshot,
                count=4,
                timeout_ms=round(min(timeout, 1.0) * 1000),
                interval=0.15,
            )
        except (LatencyError, ProbeError, OSError) as exc:
            steps.append(DoctorStep("responsiveness", "unavailable", str(exc)))
        else:
            steps.append(DoctorStep(
                "responsiveness", "completed",
                f"Sampled {len(latency_report.targets)} ICMP destinations (4 attempts each)."
            ))
            local = next(
                (item for item in latency_report.targets if item.role == "gateway"),
                None,
            )
            if local and local.replies == local.sent and local.sent > 0:
                findings.append(Finding(
                    "good", "Gateway answered each echo request",
                    f"The selected gateway answered {local.replies}/{local.sent} short ICMP "
                    f"probes (median {local.median_ms:.1f} ms). This is not a Wi-Fi quality test.",
                    "Repeat while experiencing a problem if you suspect local instability.",
                ))
            elif local:
                findings.append(Finding(
                    "info", "Gateway ICMP evidence is limited",
                    f"The selected gateway answered {local.replies}/{local.sent} echo requests. "
                    "Routers may limit ICMP replies without affecting normal traffic.",
                    "Compare with normal internet access before suspecting the router.",
                ))

            public = [
                item for item in latency_report.targets
                if item.role != "gateway" and item.replies >= 2 and item.median_ms is not None
            ]
            if len(public) >= 2:
                shortest = min(public, key=lambda item: item.median_ms)
                longest = max(public, key=lambda item: item.median_ms)
                if longest.median_ms - shortest.median_ms >= 80:
                    findings.append(Finding(
                        "info", "Response time varies by destination",
                        f"Median ICMP time to {longest.name} was {longest.median_ms:.1f} ms, "
                        f"compared with {shortest.median_ms:.1f} ms to {shortest.name}. "
                        "Different routes and reply policies may explain this.",
                        "Use 'netdoctor investigate' or 'netdoctor trace' to compare destinations.",
                    ))

    return DoctorReport(
        status=overall,
        summary=summary,
        interface=adapter.name if adapter else None,
        gateway=gateway,
        connectivity=connectivity,
        dns=dns_report,
        latency=latency_report,
        steps=tuple(steps),
        findings=tuple(findings),
    )
