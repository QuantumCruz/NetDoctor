"""Bounded ICMP measurements and evidence-based human explanations."""

import ipaddress
import math
import socket
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Callable, Literal

from netdoctor.icmp import EchoResult, ping_ipv4
from netdoctor.models import Finding, Snapshot


class LatencyError(Exception):
    """The requested measurement could not be configured."""


@dataclass(frozen=True)
class TargetResult:
    name: str
    address: str
    role: Literal["gateway", "public", "custom"]
    samples: tuple[EchoResult, ...]
    replies: int
    timeouts: int
    unreachable: int
    errors: int
    loss_percent: float | None
    minimum_ms: float | None
    median_ms: float | None
    average_ms: float | None
    p95_ms: float | None
    maximum_ms: float | None
    variation_ms: float | None

    @property
    def sent(self) -> int:
        return len(self.samples)


@dataclass(frozen=True)
class LatencyReport:
    targets: tuple[TargetResult, ...]
    findings: tuple[Finding, ...]
    note: str = (
        "ICMP echo results may be affected by filtering or reply prioritization. "
        "RTT variation is the mean absolute change between adjacent successful replies; "
        "it is not application-specific jitter."
    )

    def to_dict(self) -> dict:
        return asdict(self)


def _resolve_ipv4(host: str) -> str:
    host = host.strip()

    if not host or len(host) > 253:
        raise LatencyError(
            "Specify a valid IPv4 address or hostname for --target."
        )

    try:
        return str(ipaddress.IPv4Address(host))
    except ipaddress.AddressValueError:
        pass

    try:
        records = socket.getaddrinfo(
            host,
            None,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise LatencyError(
            f"Could not resolve an IPv4 address for {host!r}."
        ) from exc

    if not records:
        raise LatencyError(
            f"No IPv4 address found for {host!r}."
        )

    return records[0][4][0]


def _summarize(
    name: str,
    address: str,
    role: str,
    samples: tuple[EchoResult, ...],
) -> TargetResult:
    replies = [
        sample.rtt_ms
        for sample in samples
        if sample.status == "reply" and sample.rtt_ms is not None
    ]

    timeouts = sum(sample.status == "timeout" for sample in samples)
    unreachable = sum(sample.status == "unreachable" for sample in samples)
    errors = sum(sample.status == "error" for sample in samples)

    # An entirely silent ICMP target may filter pings.
    # Network errors and unreachable indications also make a
    # packet-loss percentage misleading.
    loss = (
        round(100.0 * timeouts / len(samples), 1)
        if replies and not (unreachable or errors)
        else None
    )

    ordered = sorted(replies)

    changes = [
        abs(current.rtt_ms - previous.rtt_ms)
        for previous, current in zip(samples, samples[1:])
        if previous.status == "reply"
        and current.status == "reply"
        and previous.rtt_ms is not None
        and current.rtt_ms is not None
    ]

    return TargetResult(
        name=name,
        address=address,
        role=role,
        samples=samples,
        replies=len(replies),
        timeouts=timeouts,
        unreachable=unreachable,
        errors=errors,
        loss_percent=loss,
        minimum_ms=min(replies) if replies else None,
        median_ms=statistics.median(replies) if replies else None,
        average_ms=round(statistics.mean(replies), 2) if replies else None,
        p95_ms=(
            ordered[math.ceil(len(ordered) * 0.95) - 1]
            if replies else None
        ),
        maximum_ms=max(replies) if replies else None,
        variation_ms=(
            round(statistics.mean(changes), 2)
            if changes else None
        ),
    )


def _findings(
    results: tuple[TargetResult, ...],
) -> tuple[Finding, ...]:
    findings = []

    gateway = next(
        (result for result in results if result.role == "gateway"),
        None,
    )

    public = [
        result for result in results
        if result.role != "gateway"
    ]

    if gateway is None:
        findings.append(Finding(
            "info",
            "Gateway latency was not measured",
            "No usable IPv4 next-hop address was available for an ICMP echo test.",
            "Check the default route if you need to investigate your local network.",
        ))

    elif not gateway.replies:
        findings.append(Finding(
            "info",
            "Gateway ICMP replies were not confirmed",
            "Your gateway did not answer these echo requests. "
            "This may be caused by ICMP filtering or an actual connectivity problem.",
            "Do not assume your router is faulty based on this result alone.",
        ))

    elif (
        (gateway.loss_percent is not None and gateway.loss_percent > 0)
        or (
            gateway.p95_ms is not None
            and gateway.p95_ms >= 100
        )
    ):
        findings.append(Finding(
            "warning",
            "Gateway ICMP responsiveness needs attention",
            "Some gateway echo requests timed out or had high measured "
            "round-trip time. This can indicate a local issue, but routers "
            "may deprioritize ICMP.",
            "Repeat the test and compare Wi-Fi versus Ethernet if possible.",
        ))

    if any(result.errors or result.unreachable for result in results):
        findings.append(Finding(
            "warning",
            "Some ICMP probes returned errors",
            "At least one request returned an unreachable indication or an "
            "ICMP error. Those requests were not silently counted as packet loss.",
            "Check routing and try a different destination.",
        ))

    if public and not any(result.replies for result in public):
        findings.append(Finding(
            "info",
            "Public ICMP results are inconclusive",
            "None of the tested public destinations returned an ICMP echo reply. "
            "Some networks and endpoints block this traffic.",
            "Use the regular NetDoctor scan to check DNS and HTTPS connectivity.",
        ))

    elif public:
        lost = [
            result for result in public
            if result.loss_percent is not None
            and result.loss_percent > 0
        ]

        if lost:
            findings.append(Finding(
                "warning",
                "Some public echoes were unanswered",
                "One or more destinations answered some pings but not others. "
                "This is observed ICMP non-response, not proof of application packet loss.",
                "Repeat a longer measurement and compare multiple destinations.",
            ))

        varied = [
            result for result in public
            if result.variation_ms is not None
            and result.variation_ms >= 30
        ]

        if varied:
            findings.append(Finding(
                "info",
                "Round-trip times varied noticeably",
                "Some consecutive ICMP replies changed by 30 milliseconds or "
                "more on average. Short samples cannot establish a persistent problem.",
                "Repeat the test when your connection feels unstable.",
            ))

        findings.append(Finding(
            "info",
            "Latency measurements are available",
            "Results describe round-trip times to the tested destinations only. "
            "Distance, routing and ICMP handling affect the numbers.",
            "Compare the same destination over time before judging a specific activity.",
        ))

    return tuple(findings)


def measure_latency(
    snapshot: Snapshot,
    *,
    count: int = 6,
    timeout_ms: int = 1000,
    interval: float = 0.25,
    targets: tuple[str, ...] = (),
    probe: Callable[..., EchoResult] | None = None,
    sleep: Callable[[float], None] | None = None,
    on_target: Callable[[str, str], None] | None = None,
) -> LatencyReport:
    """Probe the gateway and two public endpoints (or chosen endpoints)."""
    if not 2 <= count <= 12:
        raise ValueError("count must be between 2 and 12")

    if not 100 <= timeout_ms <= 5000:
        raise ValueError("timeout_ms must be between 100 and 5000")

    if not 0 <= interval <= 2:
        raise ValueError("interval must be between 0 and 2")

    if len(targets) > 3:
        raise LatencyError("Specify at most three custom targets.")

    destinations: list[tuple[str, str, str]] = []
    route = snapshot.preferred_route("IPv4")

    if route is not None:
        try:
            next_hop = ipaddress.IPv4Address(route.next_hop)

            if not (
                next_hop.is_unspecified
                or next_hop.is_multicast
            ):
                destinations.append((
                    "Local gateway",
                    str(next_hop),
                    "gateway",
                ))
        except ipaddress.AddressValueError:
            pass

    configured = (
        [
            (target, _resolve_ipv4(target), "custom")
            for target in targets
        ]
        if targets
        else [
            ("Cloudflare DNS", "1.1.1.1", "public"),
            ("Google DNS", "8.8.8.8", "public"),
        ]
    )

    destinations.extend(configured)

    seen = set()
    unique = []

    for name, address, role in destinations:
        if address not in seen:
            seen.add(address)
            unique.append((name, address, role))

    send = probe or ping_ipv4
    pause = sleep or time.sleep
    measured = []

    for name, address, role in unique:
        if on_target is not None:
            on_target(name, address)

        samples = []

        for index in range(count):
            samples.append(
                send(address, timeout_ms=timeout_ms)
            )

            if index < count - 1 and interval:
                pause(interval)

        measured.append(_summarize(
            name,
            address,
            role,
            tuple(samples),
        ))

    results = tuple(measured)

    return LatencyReport(
        results,
        _findings(results),
    )