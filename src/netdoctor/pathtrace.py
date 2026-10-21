
"""Bounded IPv4 route tracing using Windows ICMP TTL-limited echo requests."""

import ctypes
import ipaddress
import sys
from dataclasses import asdict, dataclass
from typing import Callable, Literal

from netdoctor.icmp import ProbeError, _open_api, _ReplyHeader
from netdoctor.latency import LatencyError, _resolve_ipv4
from netdoctor.models import Finding


class _IPOptions32(ctypes.Structure):
    """Eight-byte IP_OPTION_INFORMATION32 used by IcmpSendEcho."""

    _fields_ = [
        ("ttl", ctypes.c_ubyte),
        ("tos", ctypes.c_ubyte),
        ("flags", ctypes.c_ubyte),
        ("options_size", ctypes.c_ubyte),
        ("options_data", ctypes.c_uint32),
    ]


@dataclass(frozen=True)
class HopProbe:
    status: Literal["hop", "reached", "timeout", "unreachable", "error"]
    address: str | None
    rtt_ms: float | None
    detail: str


@dataclass(frozen=True)
class TraceHop:
    ttl: int
    probes: tuple[HopProbe, ...]


@dataclass(frozen=True)
class TraceTarget:
    name: str
    address: str
    hops: tuple[TraceHop, ...]
    reached: bool
    stop_reason: Literal["destination_reached", "hop_limit", "probe_error"]


@dataclass(frozen=True)
class TraceReport:
    targets: tuple[TraceTarget, ...]
    findings: tuple[Finding, ...]
    note: str = (
        "A silent intermediate router may filter or rate-limit ICMP. "
        "Hop round-trip times are to responding routers, not delays between routers. "
        "Different probes can take different paths; traces do not establish ISP fault."
    )

    def to_dict(self) -> dict:
        return asdict(self)


_TTL_EXPIRED = {11013, 11014}
_UNREACHABLE = {11002, 11003, 11004, 11005, 11012}
_TIMEOUT = 11010
_PAYLOAD = b"NetDoctor path trace"


def probe_hop_ipv4(address: str, *, ttl: int, timeout_ms: int = 800) -> HopProbe:
    """Send one Windows IPv4 echo with a limited TTL, without a subprocess."""
    try:
        ip = ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError as exc:
        raise ProbeError(f"Invalid IPv4 trace destination: {address!r}.") from exc

    if not 1 <= ttl <= 255:
        raise ValueError("TTL must be between 1 and 255.")
    if not 100 <= timeout_ms <= 3000:
        raise ValueError("Trace timeout must be between 100 and 3000 milliseconds.")

    create, send, close = _open_api()
    handle = create()
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ProbeError(
            f"Windows could not open an ICMP handle (error {ctypes.get_last_error()})."
        )

    try:
        options = _IPOptions32(ttl, 0, 0, 0, 0)
        payload = ctypes.create_string_buffer(_PAYLOAD)
        response = ctypes.create_string_buffer(128 + len(_PAYLOAD))
        numeric_address = int.from_bytes(ip.packed, sys.byteorder)
        count = send(
            handle,
            numeric_address,
            ctypes.byref(payload),
            len(_PAYLOAD),
            ctypes.byref(options),
            ctypes.byref(response),
            ctypes.sizeof(response),
            timeout_ms,
        )

        if count:
            header = _ReplyHeader.from_buffer_copy(response)
            status = header.status
            responder = str(ipaddress.IPv4Address(
                header.address.to_bytes(4, sys.byteorder)
            ))
            rtt = float(header.round_trip_time)
            if status == 0:
                if responder == address:
                    return HopProbe("reached", responder, rtt, "Destination answered echo.")
                return HopProbe(
                    "error", responder, None,
                    "Echo response address differed from the requested destination.",
                )
            if status in _TTL_EXPIRED:
                return HopProbe("hop", responder, rtt, "Router reported TTL expired.")
            if status == _TIMEOUT:
                return HopProbe("timeout", None, None, "No ICMP response.")
            if status in _UNREACHABLE:
                return HopProbe("unreachable", responder, None,
                                f"Network returned unreachable status {status}.")
            return HopProbe("error", None, None, f"ICMP returned status {status}.")

        code = ctypes.get_last_error()
        if code == _TIMEOUT:
            return HopProbe("timeout", None, None, "No ICMP response.")
        if code in _TTL_EXPIRED:
            return HopProbe("hop", None, None, "TTL expired; router address unavailable.")
        if code in _UNREACHABLE:
            return HopProbe("unreachable", None, None,
                            f"Network returned unreachable status {code}.")
        return HopProbe("error", None, None, f"Windows ICMP error {code}.")
    finally:
        close(handle)


def trace_paths(
    *,
    targets: tuple[str, ...] = (),
    max_hops: int = 12,
    probes_per_hop: int = 1,
    timeout_ms: int = 800,
    probe: Callable[..., HopProbe] | None = None,
    on_target: Callable[[str, str], None] | None = None,
) -> TraceReport:
    """Trace up to two selected IPv4 destinations, stopping on a real echo reply."""
    if not 1 <= max_hops <= 24:
        raise ValueError("Hop limit must be between 1 and 24.")
    if not 1 <= probes_per_hop <= 2:
        raise ValueError("Probes per hop must be 1 or 2.")
    if not 100 <= timeout_ms <= 3000:
        raise ValueError("Trace timeout must be between 100 and 3000 milliseconds.")
    if len(targets) > 2:
        raise LatencyError("Trace supports at most two destinations.")

    configured = (
        [(target, _resolve_ipv4(target)) for target in targets]
        if targets else [("Cloudflare DNS", "1.1.1.1"), ("Google DNS", "8.8.8.8")]
    )
    deduplicated = list(dict((address, (name, address)) for name, address in configured).values())
    do_probe = probe or probe_hop_ipv4
    traces: list[TraceTarget] = []
    findings: list[Finding] = []

    for name, address in deduplicated:
        if on_target:
            on_target(name, address)
        hops: list[TraceHop] = []
        stop_reason: Literal["destination_reached", "hop_limit", "probe_error"] = "hop_limit"
        for ttl in range(1, max_hops + 1):
            measurements: list[HopProbe] = []
            for _ in range(probes_per_hop):
                measurements.append(do_probe(address, ttl=ttl, timeout_ms=timeout_ms))
                if measurements[-1].status == "reached":
                    break
            hops.append(TraceHop(ttl, tuple(measurements)))
            if any(result.status == "reached" for result in measurements):
                stop_reason = "destination_reached"
                break
            if measurements and all(result.status == "error" for result in measurements):
                stop_reason = "probe_error"
                break
        trace = TraceTarget(name, address, tuple(hops),
                            stop_reason == "destination_reached", stop_reason)
        traces.append(trace)

        if trace.reached:
            findings.append(Finding(
                "info", f"ICMP path reached {name}",
                f"An ICMP echo from {address} was received with TTL {len(hops)}. "
                "This verifies echo reachability, not web-service performance.",
                "Compare this path with another run if the destination feels slow.",
            ))
        elif stop_reason == "probe_error":
            findings.append(Finding(
                "warning", f"Trace could not continue to {name}",
                "Windows returned a probe error. The trace does not establish a network outage.",
                "Check the per-hop error and retry the trace.",
            ))
        else:
            findings.append(Finding(
                "info", f"Path to {name} was not fully observed",
                f"No destination echo was received within {max_hops} hops. "
                "The destination may be farther away or ICMP responses may be filtered.",
                "Try more hops or compare with NetDoctor's TCP investigation.",
            ))

        if any(p.status == "unreachable" for h in hops for p in h.probes):
            findings.append(Finding(
                "warning", f"Network reported an unreachable response toward {name}",
                "A router reported an unreachable condition for at least one probe. "
                "That response alone does not identify the responsible network.",
                "Repeat the trace and compare ordinary TCP connectivity.",
            ))

    return TraceReport(tuple(traces), tuple(findings))
