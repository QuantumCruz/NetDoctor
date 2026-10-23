
"""Guided, read-only network checks for everyday symptoms.

No repair commands, uploads, background monitoring, or automatic downloads.
The slow-connection check needs explicit user consent in the desktop UI.
"""

import ipaddress
import queue
import re
import threading
from dataclasses import dataclass
from typing import Callable, Literal
from urllib.parse import urlsplit

from netdoctor.checks import TEST_HOSTS, check_endpoint
from netdoctor.icmp import ProbeError, ping_ipv4
from netdoctor.loaded import LoadedReport, measure_loaded
from netdoctor.models import EndpointCheck
from netdoctor.windows import collect_snapshot


Problem = Literal["slow", "drops", "website"]


class GuidanceInputError(ValueError):
    """A guided check was requested with an unsupported or unsafe input."""


@dataclass(frozen=True)
class GuidedResult:
    problem: Problem
    headline: str
    explanation: str
    next_step: str
    evidence: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class GuidedEvent:
    kind: Literal["progress", "result", "error"]
    value: str | GuidedResult


def _website_host(user_text: str) -> str:
    raw = user_text.strip()
    if not raw or len(raw) > 2048:
        raise GuidanceInputError(
            "Enter the address of an HTTPS website."
        )

    if "://" not in raw:
        raw = "https://" + raw

    try:
        url = urlsplit(raw)
        host = url.hostname
        port = url.port
    except ValueError as exc:
        raise GuidanceInputError(
            "That website address does not look valid."
        ) from exc

    if (
        url.scheme.lower() != "https"
        or not host
        or url.username
        or url.password
    ):
        raise GuidanceInputError(
            "Enter an HTTPS address, such as https://example.com."
        )

    if port not in (None, 443):
        raise GuidanceInputError(
            "This check supports standard HTTPS websites (port 443)."
        )

    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise GuidanceInputError(
            "That website name could not be understood."
        ) from exc

    if len(ascii_host) > 253:
        raise GuidanceInputError(
            "That website name is too long."
        )

    try:
        ip = ipaddress.ip_address(ascii_host)
    except ValueError:
        labels = ascii_host.split(".")
        if len(labels) < 2 or any(
            not re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
                label,
            )
            for label in labels
        ):
            raise GuidanceInputError(
                "Enter a complete website address, like example.com."
            )
    else:
        if ip.is_loopback or ip.is_multicast or ip.is_unspecified:
            raise GuidanceInputError(
                "Enter a normal website address, not a local-only address."
            )

    return ascii_host


def check_website(
    address: str,
    *,
    endpoint: Callable[..., EndpointCheck] = check_endpoint,
    progress: Callable[[str], None] | None = None,
) -> GuidedResult:
    """Compare port-443 reachability without downloading pages or sending URLs."""
    host = _website_host(address)
    send = progress or (lambda _message: None)

    send("Checking the website's address and connection...")
    selected = endpoint(host, timeout=2.0)

    comparison_host = next(
        (name for name in TEST_HOSTS if name != host),
        TEST_HOSTS[0],
    )

    send(
        "Checking whether another public website accepts connections..."
    )
    comparison = endpoint(comparison_host, timeout=2.0)

    evidence = (
        f"{host}: address "
        f"{'found' if selected.dns_ok else 'not found'}, "
        f"connection "
        f"{'accepted' if selected.tcp_ok else 'not confirmed'}.",
        f"Comparison website: connection "
        f"{'accepted' if comparison.tcp_ok else 'not confirmed'}.",
    )

    note = (
        "Only name lookup and TCP port 443 were tested. "
        "NetDoctor did not download the page, complete an HTTPS "
        "request, or inspect its content or path."
    )

    if selected.tcp_ok:
        return GuidedResult(
            "website",
            "The website's server accepted a connection",
            "Your computer found the website and established a "
            "basic connection. The page or app might still fail "
            "at a later step.",
            "Try opening the page in your browser. If it still "
            "fails, check its error message or try another browser.",
            evidence,
            note,
        )

    if not selected.dns_ok and comparison.tcp_ok:
        return GuidedResult(
            "website",
            "Your computer couldn't find this website's address",
            "The comparison website accepted a connection, "
            "but the entered website's name lookup failed. "
            "This may be site-specific or temporary.",
            "Check the spelling, then retry. Avoid changing "
            "your computer's DNS settings from this one result alone.",
            evidence,
            note,
        )

    if selected.dns_ok and comparison.tcp_ok:
        return GuidedResult(
            "website",
            "This website did not accept a connection",
            "The website name was found and the comparison site "
            "accepted a connection, but this website's port 443 "
            "did not respond to the check.",
            "Try again later or check whether the website reports "
            "an outage. This doesn't establish which network is responsible.",
            evidence,
            note,
        )

    return GuidedResult(
        "website",
        "We couldn't confirm access to either website",
        "The entered website and comparison website did not "
        "establish TCP connections in this short check. "
        "There isn't enough evidence to identify the cause.",
        "Check your Wi-Fi or Ethernet connection and run "
        "the main NetDoctor check again.",
        evidence,
        note,
    )


def check_slow(
    *,
    loaded_test: Callable[..., LoadedReport] = measure_loaded,
    progress: Callable[[str], None] | None = None,
) -> GuidedResult:
    """One opt-in 4 MiB load comparison; no repeat downloads or speed claims."""
    send = progress or (lambda _message: None)

    send(
        "Checking responsiveness during a capped 4 MiB download..."
    )

    sample = loaded_test(
        size_mib=4,
        timeout=10.0,
        on_phase=send,
    )

    downloaded = sample.download

    evidence = (
        f"Download: "
        f"{downloaded.received_bytes / 1048576:.2f} MiB "
        f"received ({downloaded.status}).",
        (
            f"Idle response: {sample.idle_median_ms:.1f} ms."
            if sample.idle_median_ms is not None
            else "Idle response: not measured."
        ),
        (
            f"During-download response: "
            f"{sample.loaded_median_ms:.1f} ms."
            if sample.loaded_median_ms is not None
            else "During-download response: not measured."
        ),
    )

    note = (
        "This was one small, single-stream download and an ICMP "
        "comparison. It doesn't establish your plan speed, sustained "
        "connection quality, or the cause of any slowdown. "
        "Metered-data charges may apply."
    )

    if sample.status == "increase_observed":
        return GuidedResult(
            "slow",
            "Response time increased while downloading",
            f"In this brief sample, the response time increased "
            f"by about {sample.increase_ms:.0f} ms during download "
            "traffic. That can affect calls or games, but one run "
            "doesn't establish why.",
            "Repeat later. If you notice delays mainly during "
            "downloads, try pausing heavy transfers and comparing "
            "the experience.",
            evidence,
            note,
        )

    if sample.status == "no_clear_increase":
        return GuidedResult(
            "slow",
            "No clear slowdown during this small download",
            "Response times did not increase substantially during "
            "the sampled transfer. Your connection can still be slow "
            "for other destinations or under heavier use.",
            "If a specific website or app is slow, use the website "
            "check. Repeat the test at another time if the problem "
            "comes and goes.",
            evidence,
            note,
        )

    return GuidedResult(
        "slow",
        "The short test couldn't establish a result",
        "The download or the overlapping response measurements "
        "weren't sufficient for a reliable before-and-during comparison.",
        "Try again later. If the download itself timed out, first "
        "check whether ordinary websites open normally.",
        evidence,
        note,
    )


def check_drops(
    *,
    collector: Callable[[], object] = collect_snapshot,
    endpoint: Callable[..., EndpointCheck] = check_endpoint,
    ping: Callable[..., object] = ping_ipv4,
    rounds: int = 6,
    interval: float = 4.0,
    cancel: threading.Event | None = None,
    progress: Callable[[str], None] | None = None,
) -> GuidedResult:
    """Brief, stoppable connectivity sampling. Not persistent background monitoring."""
    if not 2 <= rounds <= 12 or not 0 <= interval <= 10:
        raise GuidanceInputError(
            "Invalid monitoring duration."
        )

    stop = cancel or threading.Event()
    send = progress or (lambda _message: None)

    send("Identifying your active network...")
    snapshot = collector()
    route = snapshot.preferred_route("IPv4")

    gateway = None
    if route:
        try:
            gateway_ip = ipaddress.IPv4Address(route.next_hop)
            if (
                not gateway_ip.is_unspecified
                and not gateway_ip.is_multicast
            ):
                gateway = str(gateway_ip)
        except ValueError:
            pass

    outcomes: list[tuple[int, int]] = []
    gateway_replies = 0
    gateway_attempts = 0

    for index in range(rounds):
        if stop.is_set():
            break

        send(
            f"Checking for connection interruptions "
            f"({index + 1} of {rounds})..."
        )

        connected = sum(
            int(endpoint(host, timeout=1.5).tcp_ok)
            for host in TEST_HOSTS
        )

        outcomes.append(
            (connected, len(TEST_HOSTS))
        )

        if gateway:
            try:
                echo = ping(
                    gateway,
                    timeout_ms=800,
                )
            except (ProbeError, OSError):
                pass
            else:
                if echo.status != "error":
                    gateway_attempts += 1
                    gateway_replies += int(
                        echo.status == "reply"
                    )

        if index < rounds - 1 and stop.wait(interval):
            break

    done = len(outcomes)

    fully_working = sum(
        succeeded == total
        for succeeded, total in outcomes
    )
    no_connections = sum(
        succeeded == 0
        for succeeded, _ in outcomes
    )

    evidence = (
        f"Checks completed: {done} of {rounds}.",
        f"Both public destinations responded in "
        f"{fully_working} of {done} checks.",
        f"Neither public destination responded in "
        f"{no_connections} of {done} checks.",
        (
            f"Router replied in {gateway_replies} "
            f"of {gateway_attempts} tested pings."
            if gateway_attempts
            else "Router ping replies were not available."
        ),
    )

    note = (
        "Only a short series of TCP connection attempts and "
        "optional router pings. It does not continuously monitor "
        "your connection or prove which device or ISP caused "
        "an interruption."
    )

    if done < rounds:
        return GuidedResult(
            "drops",
            "Connection watch was stopped",
            "The check ended early, so these observations are "
            "only a partial sample.",
            "Run the watch again when the connection is "
            "behaving unexpectedly.",
            evidence,
            note,
        )

    if no_connections and no_connections < rounds:
        return GuidedResult(
            "drops",
            "Brief connection interruptions were observed",
            f"In {no_connections} of {rounds} checks, neither "
            "test destination accepted a connection. This "
            "does not identify where the interruption occurred.",
            "Run this check while the problem is happening "
            "and note the time. If it repeats, compare the "
            "connection on another device.",
            evidence,
            note,
        )

    if no_connections == rounds:
        return GuidedResult(
            "drops",
            "Public connections weren't confirmed during this watch",
            "Neither test destination responded in these samples. "
            "That could involve your connection, filtering, or "
            "the test destinations.",
            "Try another website and the main NetDoctor check "
            "to narrow down the problem.",
            evidence,
            note,
        )

    if fully_working < rounds:
        return GuidedResult(
            "drops",
            "One public test destination responded inconsistently",
            "At least one connection failed in some checks, "
            "but there was no round where both destinations "
            "failed together.",
            "Repeat during a disconnection. One test site's "
            "failure isn't enough to diagnose a network-wide dropout.",
            evidence,
            note,
        )

    return GuidedResult(
        "drops",
        "No disconnections observed in this short watch",
        f"Both public test destinations accepted connections "
        f"in all {rounds} checks. That doesn't rule out a problem "
        "occurring later.",
        "Try this again while the connection is dropping. "
        "Longer-term history monitoring is planned for a later milestone.",
        evidence,
        note,
    )


class GuidedWorker:
    """Dispatch user-selected checks in a background thread, never touching Tk."""

    def __init__(
        self,
        *,
        slow: Callable[..., GuidedResult] = check_slow,
        drops: Callable[..., GuidedResult] = check_drops,
        website: Callable[..., GuidedResult] = check_website,
    ) -> None:
        self.slow = slow
        self.drops = drops
        self.website = website
        self.events: queue.Queue[GuidedEvent] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    @property
    def running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    def start(
        self,
        problem: Problem,
        *,
        website: str = "",
    ) -> bool:
        if self.running:
            return False

        if problem not in ("slow", "drops", "website"):
            raise GuidanceInputError(
                "Select a supported network problem."
            )

        if problem == "website":
            _website_host(website)

        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break

        self._cancel = threading.Event()
        self._thread = threading.Thread(
            target=self._work,
            args=(problem, website),
            name="NetDoctorGuidedCheck",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop the connection watch. A capped download finishes itself."""
        self._cancel.set()

    def _work(
        self,
        problem: Problem,
        website: str,
    ) -> None:
        def progress(message: str) -> None:
            self.events.put(
                GuidedEvent("progress", message)
            )

        try:
            if problem == "slow":
                report = self.slow(
                    progress=progress
                )
            elif problem == "drops":
                report = self.drops(
                    progress=progress,
                    cancel=self._cancel,
                )
            else:
                report = self.website(
                    website,
                    progress=progress,
                )
        except Exception:
            self.events.put(
                GuidedEvent(
                    "error",
                    "That check couldn't finish. No settings were "
                    "changed. Try again or use the basic connection check.",
                )
            )
        else:
            self.events.put(
                GuidedEvent("result", report)
            )
