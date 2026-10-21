"""Compare ICMP echo and TCP connection observations without guessing causes."""

import ipaddress
import math
import socket
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Callable, Literal

from netdoctor.icmp import EchoResult
from netdoctor.latency import LatencyReport, measure_latency
from netdoctor.models import Finding, Snapshot


@dataclass(frozen=True)
class TcpAttempt:
    status: Literal["connected", "timeout", "refused", "error"]
    connect_ms: float | None
    detail: str


@dataclass(frozen=True)
class TcpTarget:
    name: str
    address: str
    port: int
    attempts: tuple[TcpAttempt, ...]
    connected: int
    timed_out: int
    refused: int
    errors: int
    median_ms: float | None

    @property
    def sent(self) -> int:
        return len(self.attempts)


@dataclass(frozen=True)
class CrosscheckReport:
    latency: LatencyReport
    tcp: tuple[TcpTarget, ...]
    findings: tuple[Finding, ...]
    note: str = (
        "ICMP and TCP tests run sequentially; their times are not directly equivalent. "
        "TCP timing measures connection establishment only, not TLS, HTTP, or speed. "
        "A filtered ICMP request or closed TCP port does not prove internet failure."
    )

    def to_dict(self) -> dict:
        return asdict(self)


def connect_tcp_ipv4(
    address: str, *, port: int = 443, timeout: float = 2.0
) -> TcpAttempt:
    """Time one TCP connection to a numeric IPv4 destination without DNS."""
    ip = ipaddress.IPv4Address(address)

    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("TCP port must be between 1 and 65535.")

    if not math.isfinite(timeout) or not 0.1 <= timeout <= 5:
        raise ValueError("TCP timeout must be between 0.1 and 5 seconds.")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            start = time.perf_counter()
            connection.connect((str(ip), port))
            duration_ms = (time.perf_counter() - start) * 1000

        return TcpAttempt(
            "connected", round(duration_ms, 2), "TCP connection established."
        )

    except ConnectionRefusedError:
        return TcpAttempt(
            "refused", None,
            "The destination refused TCP connections on this port."
        )

    except (TimeoutError, socket.timeout):
        return TcpAttempt(
            "timeout", None,
            "No TCP connection established before the timeout."
        )

    except OSError as exc:
        code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        detail = (
            f"Socket error {code}."
            if code is not None else "Socket operation failed."
        )
        return TcpAttempt("error", None, detail)


def _summarize_tcp(
    name: str, address: str, samples: tuple[TcpAttempt, ...]
) -> TcpTarget:
    connected = [
        sample.connect_ms
        for sample in samples
        if sample.status == "connected" and sample.connect_ms is not None
    ]

    return TcpTarget(
        name=name,
        address=address,
        port=443,
        attempts=samples,
        connected=len(connected),
        timed_out=sum(s.status == "timeout" for s in samples),
        refused=sum(s.status == "refused" for s in samples),
        errors=sum(s.status == "error" for s in samples),
        median_ms=(
            round(statistics.median(connected), 2)
            if connected else None
        ),
    )


def _interpret(
    icmp: LatencyReport, tcp: tuple[TcpTarget, ...]
) -> tuple[Finding, ...]:
    findings = list(icmp.findings)

    remote = [
        target for target in icmp.targets
        if target.role != "gateway"
    ]

    replied = [
        target for target in remote
        if target.median_ms is not None
    ]

    if len(replied) >= 2:
        fastest = min(replied, key=lambda target: target.median_ms)
        slowest = max(replied, key=lambda target: target.median_ms)

        if slowest.median_ms - fastest.median_ms >= 80:
            findings.append(Finding(
                "info",
                "Responsiveness differs by destination",
                f"ICMP median to {slowest.name} was "
                f"{slowest.median_ms:.1f} ms, "
                f"compared with {fastest.median_ms:.1f} ms "
                f"to {fastest.name}. "
                "These destinations may take different paths or "
                "handle echo requests differently.",
                "Repeat both measurements at another time. "
                "Do not assume your entire internet link is equally slow.",
            ))

    by_ip = {
        target.address: target
        for target in remote
    }

    for result in tcp:
        matching = by_ip[result.address]

        if result.connected and matching.replies == 0:
            findings.append(Finding(
                "info",
                f"TCP works although ICMP did not reply: {result.name}",
                f"TCP port 443 accepted connections at {result.address}, "
                "but the same IP did not respond to ICMP echo requests.",
                "Do not classify this destination as offline "
                "based on ping alone.",
            ))

        elif (
            result.median_ms is not None
            and matching.median_ms is not None
            and matching.median_ms >= 120
            and matching.median_ms - result.median_ms >= 80
        ):
            findings.append(Finding(
                "info",
                f"ICMP and TCP timings differ: {result.name}",
                f"ICMP median was {matching.median_ms:.1f} ms "
                f"while TCP connection median was "
                f"{result.median_ms:.1f} ms. "
                "These are different protocols and were tested "
                "at different moments.",
                "Repeat the comparison before attributing "
                "the difference to an ISP or a router.",
            ))

    connected_targets = [
        target for target in tcp
        if target.connected
    ]

    unavailable_targets = [
        target for target in tcp
        if not target.connected
    ]

    if unavailable_targets:
        names = ", ".join(
            target.name for target in unavailable_targets
        )

        findings.append(Finding(
            "warning" if connected_targets else "info",
            "TCP port 443 was not confirmed on every target",
            f"No TCP connection succeeded to: {names}. "
            "A filtered or unsupported port can produce this result "
            "even when the internet is working.",
            "Compare with the standard scan, then retry "
            "the affected destination.",
        ))

    return tuple(findings)


def run_crosscheck(
    snapshot: Snapshot,
    *,
    count: int = 6,
    timeout_ms: int = 1000,
    interval: float = 0.25,
    targets: tuple[str, ...] = (),
    icmp_probe: Callable[..., EchoResult] | None = None,
    tcp_probe: Callable[..., TcpAttempt] | None = None,
    sleep: Callable[[float], None] | None = None,
    on_icmp: Callable[[str, str], None] | None = None,
    on_tcp: Callable[[str, str], None] | None = None,
) -> CrosscheckReport:
    """Measure ICMP first, then TCP to exactly the same non-gateway IPs."""
    latency = measure_latency(
        snapshot,
        count=count,
        timeout_ms=timeout_ms,
        interval=interval,
        targets=targets,
        probe=icmp_probe,
        sleep=sleep,
        on_target=on_icmp,
    )

    probe = tcp_probe or connect_tcp_ipv4
    pause = sleep or time.sleep
    tcp_results = []

    for target in latency.targets:
        if target.role == "gateway":
            continue

        if on_tcp is not None:
            on_tcp(target.name, target.address)

        samples = []

        for index in range(count):
            samples.append(
                probe(
                    target.address,
                    port=443,
                    timeout=timeout_ms / 1000,
                )
            )

            if interval and index < count - 1:
                pause(interval)

        tcp_results.append(
            _summarize_tcp(
                target.name,
                target.address,
                tuple(samples),
            )
        )

    results = tuple(tcp_results)

    return CrosscheckReport(
        latency,
        results,
        _interpret(latency, results),
    )