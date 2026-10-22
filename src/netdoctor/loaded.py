
"""Opt-in, bounded comparison of idle and during-download IPv4 ICMP latency.

A probe is counted as loaded only if its entire measurement took place
between the download's first received byte and the end of its response.
This avoids misclassifying DNS, TCP and TLS setup time as network load.
"""

import ipaddress
import math
import statistics
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable, Literal

from netdoctor.icmp import EchoResult, ProbeError, ping_ipv4
from netdoctor.models import Finding
from netdoctor.throughput import DownloadReport, measure_download


class LoadedError(Exception):
    """The concurrent latency diagnostic could not run reliably."""


@dataclass(frozen=True)
class LoadProbe:
    status: Literal["reply", "timeout", "unreachable", "error"]
    rtt_ms: float | None
    during_transfer: bool
    detail: str


@dataclass(frozen=True)
class LoadedReport:
    status: Literal["increase_observed", "no_clear_increase", "inconclusive"]
    target: str
    idle: tuple[EchoResult, ...]
    during: tuple[LoadProbe, ...]
    idle_median_ms: float | None
    loaded_median_ms: float | None
    increase_ms: float | None
    loaded_replies: int
    transfer_window_ms: float | None
    download: DownloadReport
    findings: tuple[Finding, ...]
    note: str = (
        "An opt-in, single-stream HTTPS download with ICMP echo sampling. "
        "Only probes fully overlapping received download data count as loaded. "
        "ICMP and HTTPS may follow different routes. A single test cannot prove "
        "bufferbloat, congestion, packet loss, or a problem with your ISP."
    )

    def to_dict(self) -> dict:
        return asdict(self)


def _median(values: tuple[float, ...]) -> float | None:
    return round(statistics.median(values), 2) if values else None


def _interpret(
    target: str,
    idle: tuple[EchoResult, ...],
    during: tuple[LoadProbe, ...],
    download: DownloadReport,
    transfer_window_ms: float | None,
) -> LoadedReport:
    idle_values = tuple(
        sample.rtt_ms for sample in idle
        if sample.status == "reply" and sample.rtt_ms is not None
    )
    loaded_values = tuple(
        sample.rtt_ms for sample in during
        if sample.during_transfer
        and sample.status == "reply" and sample.rtt_ms is not None
    )
    before = _median(idle_values)
    after = _median(loaded_values)
    delta = round(after - before, 2) if before is not None and after is not None else None

    enough = (
        download.status == "completed"
        and transfer_window_ms is not None
        and transfer_window_ms >= 700
        and len(idle_values) >= 3
        and len(loaded_values) >= 3
        and download.quality != "short_sample"
    )
    findings: list[Finding] = []

    if not enough:
        status: Literal["increase_observed", "no_clear_increase", "inconclusive"] = "inconclusive"
        if download.status != "completed":
            reason = (
                f"The bounded download ended as '{download.status}' "
                f"({download.received_bytes} of {download.requested_bytes} bytes received)."
            )
        elif transfer_window_ms is None or transfer_window_ms < 700:
            reason = "The actual data-transfer period was shorter than 700 ms."
        else:
            reason = (
                "Not enough ICMP replies were observed both before and during "
                "the actual transfer (at least three in each period are required)."
            )
        findings.append(Finding(
            "info", "Loaded latency is inconclusive", reason,
            "Retry at a different time or explicitly select a larger capped sample. "
            "Do not treat missing ping replies as proof of application packet loss.",
        ))
    elif delta is not None and delta >= 40:
        status = "increase_observed"
        findings.append(Finding(
            "warning", "ICMP response time increased during the download",
            f"Median echo time to {target} increased from {before:.1f} ms while "
            f"idle to {after:.1f} ms during data transfer (+{delta:.1f} ms). "
            "The sample suggests a load-related responsiveness change, but does "
            "not establish its cause.",
            "Repeat the measurement. Compare Ethernet and Wi-Fi when possible, "
            "and avoid identifying a specific router or ISP from this sample alone.",
        ))
    else:
        status = "no_clear_increase"
        findings.append(Finding(
            "info", "No large latency increase observed in this short test",
            f"Median ICMP time was {before:.1f} ms idle and {after:.1f} ms "
            f"during the download ({delta:+.1f} ms difference). "
            "This does not rule out congestion during heavier or longer traffic.",
            "Repeat under similar conditions if interactive applications feel slow.",
        ))

    return LoadedReport(
        status=status,
        target=target,
        idle=idle,
        during=during,
        idle_median_ms=before,
        loaded_median_ms=after,
        increase_ms=delta,
        loaded_replies=len(loaded_values),
        transfer_window_ms=transfer_window_ms,
        download=download,
        findings=tuple(findings),
    )


def measure_loaded(
    *,
    target: str = "8.8.8.8",
    size_mib: int = 4,
    timeout: float = 10.0,
    probe: Callable[..., EchoResult] | None = None,
    downloader: Callable[..., DownloadReport] | None = None,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
    on_phase: Callable[[str], None] | None = None,
) -> LoadedReport:
    """Compare four idle echoes with echoes overlapping one capped HTTPS download.

    Data use is controlled by the existing throughput module (1/2/4/8 MiB).
    Only the download runs in a worker thread; the main thread performs ICMP.
    """
    try:
        address = str(ipaddress.IPv4Address(target))
    except ipaddress.AddressValueError as exc:
        raise LoadedError("--target must be a numeric IPv4 address.") from exc

    if ipaddress.IPv4Address(address).is_multicast or ipaddress.IPv4Address(address).is_unspecified:
        raise LoadedError("Choose a usable IPv4 probe destination.")
    if type(size_mib) is not int or size_mib not in (1, 2, 4, 8):
        raise LoadedError("--size-mib must be one of 1, 2, 4, or 8.")
    if (not isinstance(timeout, (int, float)) or not math.isfinite(timeout)
            or not 0.1 <= timeout <= 10):
        raise LoadedError("--timeout must be between 0.1 and 10 seconds.")

    send = probe or ping_ipv4
    transfer = downloader or measure_download
    now = clock or time.perf_counter
    pause = sleep or time.sleep
    announce = on_phase or (lambda _phase: None)

    announce("Measuring idle responsiveness")
    idle_samples: list[EchoResult] = []
    for index in range(4):
        idle_samples.append(send(address, timeout_ms=800))
        if index < 3:
            pause(0.15)

    shared: dict[str, object] = {}
    started = threading.Event()
    finished = threading.Event()

    def download_worker() -> None:
        shared["started_at"] = now()
        started.set()
        try:
            shared["report"] = transfer(size_mib=size_mib, timeout=float(timeout))
        except Exception as exc:
            shared["error"] = exc
        finally:
            finished.set()

    announce("Downloading the capped sample and measuring responsiveness")
    worker = threading.Thread(target=download_worker, name="NetDoctorDownload", daemon=True)
    worker.start()
    started.wait()
    measurements: list[tuple[float, float, EchoResult]] = []

    # The download module also limits its own read-loop duration.
    for _ in range(64):
        if finished.is_set():
            break
        begin = now()
        try:
            result = send(address, timeout_ms=800)
        except ProbeError:
            result = EchoResult("error", None, "Windows ICMP became unavailable.")
        end = now()
        measurements.append((begin, end, result))
        if finished.wait(0.15):
            break

    worker.join()
    if "error" in shared:
        raise LoadedError("The HTTPS download worker could not finish reliably.") from shared["error"]
    report = shared.get("report")
    if not isinstance(report, DownloadReport):
        raise LoadedError("The download engine returned an unexpected report.")

    started_at = shared["started_at"]
    transfer_window_ms = None
    loaded_start = loaded_end = None
    if report.first_byte_ms is not None and report.elapsed_ms is not None:
        transfer_window_ms = max(0.0, report.elapsed_ms - report.first_byte_ms)
        loaded_start = started_at + report.first_byte_ms / 1000
        loaded_end = started_at + report.elapsed_ms / 1000

    during = tuple(
        LoadProbe(
            status=result.status,
            rtt_ms=result.rtt_ms,
            during_transfer=(
                loaded_start is not None
                and loaded_end is not None
                and begin >= loaded_start
                and end <= loaded_end
            ),
            detail=result.detail,
        )
        for begin, end, result in measurements
    )
    return _interpret(address, tuple(idle_samples), during, report, transfer_window_ms)
