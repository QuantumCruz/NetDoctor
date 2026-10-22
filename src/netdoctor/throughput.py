
"""Opt-in, data-capped HTTPS download sample; never a definitive speed test.

The endpoint is the download API documented by Cloudflare's speedtest client.
Only a single request is made, capped by requested bytes and wall time.
"""

import math
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Literal

from netdoctor.models import Finding


class DownloadConfigError(Exception):
    """Download test arguments were invalid."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class DownloadReport:
    status: Literal["completed", "incomplete", "timeout", "unavailable"]
    quality: Literal["preliminary", "short_sample", "not_measured"]
    destination: str
    requested_bytes: int
    received_bytes: int
    elapsed_ms: float | None
    first_byte_ms: float | None
    average_mbps: float | None
    explanation: str
    findings: tuple[Finding, ...]
    note: str = (
        "An opt-in, single-stream HTTPS download sample to Cloudflare; it includes "
        "DNS, TCP/TLS setup and server processing. It is not your plan speed, "
        "maximum throughput, loaded latency, upload speed, or a Wi-Fi quality score. "
        "Your connection may incur metered data charges."
    )

    def to_dict(self) -> dict:
        return asdict(self)


_DESTINATION = "https://speed.cloudflare.com/__down"
_MIB = 1_048_576
_MAX_SECONDS = 15.0


def _open_download(url: str, timeout: float):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NetDoctor/0.1", "Accept-Encoding": "identity"},
        method="GET",
    )
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)


def _result(
    status: str,
    expected: int,
    received: int,
    elapsed: float | None,
    first_byte: float | None,
    explanation: str,
) -> DownloadReport:
    completed = status == "completed" and received == expected and elapsed is not None
    short = bool(completed and elapsed < 0.15)
    rate = round(received * 8 / (elapsed * 1_000_000), 2) if completed and elapsed > 0 else None
    quality = "short_sample" if short else "preliminary" if completed else "not_measured"
    findings = []
    if status == "completed":
        if short:
            findings.append(Finding(
                "info", "Download sample finished too quickly for a stable estimate",
                "The requested data arrived in less than 150 ms. Startup and timing noise "
                "can dominate such a short test.",
                "Try a larger capped sample and compare multiple runs.",
            ))
        else:
            findings.append(Finding(
                "info", "Short HTTPS download completed",
                "The requested bytes were received from the test endpoint. The measured "
                "average includes connection setup, so it is not a maximum bandwidth result.",
                "Repeat under similar conditions before drawing conclusions about speed.",
            ))
    else:
        findings.append(Finding(
            "warning", "Download measurement could not be completed",
            explanation,
            "Retry later or use 'netdoctor doctor' to check basic connectivity. "
            "Do not conclude the entire internet connection is down.",
        ))
    return DownloadReport(
        status=status,
        quality=quality,
        destination="Cloudflare speed test",
        requested_bytes=expected,
        received_bytes=received,
        elapsed_ms=round(elapsed * 1000, 2) if elapsed is not None else None,
        first_byte_ms=round(first_byte * 1000, 2) if first_byte is not None else None,
        average_mbps=rate,
        explanation=explanation,
        findings=tuple(findings),
    )


def measure_download(
    *,
    size_mib: int = 2,
    timeout: float = 5.0,
    opener: Callable[[str, float], object] | None = None,
    clock: Callable[[], float] | None = None,
) -> DownloadReport:
    """Download at most 8 MiB; stop early on malformed responses or time limits.

    A per-socket timeout complements the 15-second overall read-loop budget.
    An in-progress read may use up to its socket timeout after that deadline.
    """
    if type(size_mib) is not int or size_mib not in (1, 2, 4, 8):
        raise DownloadConfigError("--size-mib must be one of 1, 2, 4, or 8.")
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0.1 <= timeout <= 10:
        raise DownloadConfigError("Timeout must be between 0.1 and 10 seconds.")

    expected = size_mib * _MIB
    endpoint = f"{_DESTINATION}?bytes={expected}"
    open_stream = opener or _open_download
    now = clock or time.perf_counter
    start = now()
    received = 0
    first_byte = None
    status = "incomplete"
    message = "The server ended the response before all requested bytes were received."

    try:
        with open_stream(endpoint, float(timeout)) as stream:
            response_status = getattr(stream, "status", None)
            if response_status is not None and response_status != 200:
                return _result("unavailable", expected, 0, now() - start, None,
                               f"Download endpoint returned HTTP {response_status}.")
            headers = getattr(stream, "headers", {})
            encoding = headers.get("Content-Encoding", "identity") if headers is not None else "identity"
            if str(encoding).lower() != "identity":
                return _result("unavailable", expected, 0, now() - start, None,
                               "The endpoint returned encoded content, not a plain byte stream.")
            length = headers.get("Content-Length") if headers is not None else None
            if length is not None:
                try:
                    declared = int(length)
                except (TypeError, ValueError):
                    return _result("unavailable", expected, 0, now() - start, None,
                                   "The endpoint supplied an invalid response length.")
                if declared != expected:
                    return _result("unavailable", expected, 0, now() - start, None,
                                   "The endpoint response size does not match the requested cap.")

            while received < expected:
                if now() - start >= _MAX_SECONDS:
                    message = "The 15-second test budget elapsed before completion."
                    break
                requested = min(65536, expected - received)
                if first_byte is None:
                    requested = 1
                chunk = stream.read(requested)
                if not chunk:
                    break
                if not isinstance(chunk, bytes) or len(chunk) > requested:
                    return _result("unavailable", expected, received, now() - start,
                                   first_byte, "Endpoint produced unexpected response bytes.")
                if first_byte is None:
                    first_byte = now() - start
                received += len(chunk)

            elapsed = now() - start
            if received == expected:
                status = "completed"
                message = "Received the requested byte count from the HTTPS endpoint."
            return _result(status, expected, received, elapsed, first_byte, message)

    except (TimeoutError, socket.timeout):
        return _result("timeout", expected, received, now() - start, first_byte,
                       "The HTTPS download exceeded its socket timeout.")
    except urllib.error.HTTPError as exc:
        return _result("unavailable", expected, received, now() - start, first_byte,
                       f"The HTTPS endpoint returned HTTP {exc.code}.")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return _result("timeout", expected, received, now() - start, first_byte,
                           "The HTTPS request timed out.")
        return _result("unavailable", expected, received, now() - start, first_byte,
                       "The HTTPS download could not connect or complete TLS verification.")
    except OSError:
        return _result("unavailable", expected, received, now() - start, first_byte,
                       "The HTTPS connection failed during download.")
