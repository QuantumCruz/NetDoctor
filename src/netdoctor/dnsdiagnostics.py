
"""Bounded direct DNS-over-UDP IPv4 checks against an interface's configured resolvers.

Direct queries deliberately do not emulate the Windows DNS Client (NRPT, DoH,
search suffixes, global DNS configuration, or its cache).
"""

import ipaddress
import re
import secrets
import socket
import struct
import time
from dataclasses import asdict, dataclass
from typing import Callable, Literal

from netdoctor.models import Finding, Snapshot


class DnsDiagnosticError(Exception):
    """Invalid DNS diagnostic configuration or hostname."""


@dataclass(frozen=True)
class DnsObservation:
    resolver: str
    hostname: str
    status: Literal[
        "answered", "no_a_record", "nxdomain", "server_error", "truncated",
        "timeout", "invalid_response", "transport_error"
    ]
    elapsed_ms: float | None
    addresses: tuple[str, ...]
    response_code: int | None
    detail: str


@dataclass(frozen=True)
class DnsReport:
    interface: str | None
    resolvers: tuple[str, ...]
    observations: tuple[DnsObservation, ...]
    findings: tuple[Finding, ...]
    note: str = (
        "These are direct, uncached-by-NetDoctor IPv4 UDP port 53 A-record queries "
        "to servers listed on the default-route interface. Windows may use different "
        "DNS paths through policies, VPNs, encrypted DNS, or caches. A timeout alone "
        "does not prove the system's DNS is broken."
    )

    def to_dict(self) -> dict:
        return asdict(self)


_LABEL = re.compile(rb"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def _question_for(hostname: str) -> bytes:
    name = hostname.strip().rstrip(".")
    if not name:
        raise DnsDiagnosticError("Specify a nonempty hostname.")
    try:
        ascii_name = name.encode("idna").lower()
    except (UnicodeError, ValueError) as exc:
        raise DnsDiagnosticError(f"Invalid hostname: {hostname!r}.") from exc
    if len(ascii_name) > 253:
        raise DnsDiagnosticError("Hostname is too long for a DNS query.")
    labels = ascii_name.split(b".")
    if any(len(label) > 63 or not _LABEL.fullmatch(label) for label in labels):
        raise DnsDiagnosticError(f"Invalid hostname: {hostname!r}.")
    return b"".join(bytes((len(label),)) + label for label in labels) + b"\x00\x00\x01\x00\x01"


def _skip_name(data: bytes, offset: int) -> int:
    """Skip a wire-format name; do not dereference untrusted compression pointers."""
    while True:
        if offset >= len(data):
            raise ValueError("Truncated DNS name")
        length = data[offset]
        if length == 0:
            return offset + 1
        if (length & 0xC0) == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("Truncated DNS compression pointer")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if pointer >= len(data):
                raise ValueError("Invalid DNS compression pointer")
            return offset + 2
        if length & 0xC0 or length > 63 or offset + 1 + length > len(data):
            raise ValueError("Invalid DNS label")
        offset += 1 + length


def _read_response(
    packet: bytes, identifier: int, question: bytes
) -> tuple[str, tuple[str, ...], int | None, str]:
    try:
        if len(packet) < 12:
            raise ValueError("DNS response is too short")
        rx_id, flags, questions, answers, _, _ = struct.unpack_from("!HHHHHH", packet)
        if rx_id != identifier or not (flags & 0x8000) or (flags & 0x7800):
            raise ValueError("DNS response identifier or flags do not match")
        if questions != 1 or answers > 100:
            raise ValueError("Unexpected DNS question or answer count")
        offset = _skip_name(packet, 12)
        if offset + 4 > len(packet) or packet[12:offset + 4] != question:
            raise ValueError("DNS response question does not match the request")
        offset += 4
        rcode = flags & 0xF
        if flags & 0x0200:
            return "truncated", (), rcode, "UDP DNS response was truncated; TCP retry is not implemented."
        if rcode:
            if rcode == 3:
                return "nxdomain", (), rcode, "Server reported that this DNS name does not exist."
            return "server_error", (), rcode, f"DNS server returned response code {rcode}."
        addresses = []
        for _ in range(answers):
            offset = _skip_name(packet, offset)
            if offset + 10 > len(packet):
                raise ValueError("Truncated DNS answer header")
            rr_type, rr_class, _ttl, size = struct.unpack_from("!HHIH", packet, offset)
            offset += 10
            if offset + size > len(packet):
                raise ValueError("Truncated DNS record data")
            if rr_type == 1 and rr_class == 1 and size == 4:
                address = str(ipaddress.IPv4Address(packet[offset:offset + size]))
                if address not in addresses:
                    addresses.append(address)
            offset += size
        if addresses:
            return "answered", tuple(addresses), 0, "Resolver returned IPv4 A records."
        return "no_a_record", (), 0, "Resolver replied but no IPv4 A record was included."
    except (ValueError, struct.error, ipaddress.AddressValueError) as exc:
        return "invalid_response", (), None, f"DNS reply could not be validated: {exc}."


def _udp_exchange(resolver: str, query: bytes, timeout: float) -> bytes:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(timeout)
        connection.connect((resolver, 53))
        connection.sendall(query)
        return connection.recv(4096)


def query_dns(
    resolver: str,
    hostname: str,
    *,
    timeout: float = 1.5,
    exchange: Callable[[str, bytes, float], bytes] | None = None,
) -> DnsObservation:
    """Make one direct UDP DNS A-record query to a numeric IPv4 resolver."""
    try:
        ip = ipaddress.IPv4Address(resolver)
    except ipaddress.AddressValueError as exc:
        raise DnsDiagnosticError(f"Invalid IPv4 DNS server: {resolver!r}.") from exc
    if ip.is_multicast or ip.is_unspecified:
        raise DnsDiagnosticError("DNS resolver must be a usable IPv4 address.")
    if not 0.1 <= timeout <= 3.0:
        raise DnsDiagnosticError("DNS timeout must be between 0.1 and 3 seconds.")
    question = _question_for(hostname)
    identifier = secrets.randbelow(65536)
    packet = struct.pack("!HHHHHH", identifier, 0x0100, 1, 0, 0, 0) + question
    start = time.perf_counter()
    try:
        response = (exchange or _udp_exchange)(str(ip), packet, timeout)
    except (TimeoutError, socket.timeout):
        return DnsObservation(str(ip), hostname, "timeout", None, (), None,
                              "No direct UDP DNS response before the timeout.")
    except OSError as exc:
        code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        detail = f"Network socket error {code}." if code is not None else "DNS socket operation failed."
        return DnsObservation(str(ip), hostname, "transport_error", None, (), None, detail)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    if not isinstance(response, bytes):
        return DnsObservation(str(ip), hostname, "invalid_response", elapsed, (), None,
                              "DNS server returned unexpected response data.")
    status, addresses, rcode, detail = _read_response(response, identifier, question)
    return DnsObservation(str(ip), hostname, status, elapsed, addresses, rcode, detail)


def diagnose_dns(
    snapshot: Snapshot,
    *,
    hostnames: tuple[str, ...] = ("example.com", "www.microsoft.com"),
    timeout: float = 1.5,
    query: Callable[..., DnsObservation] | None = None,
) -> DnsReport:
    """Test DNS servers configured on the preferred IPv4 default-route interface."""
    if not 1 <= len(hostnames) <= 3:
        raise DnsDiagnosticError("Provide between one and three DNS hostnames.")
    for hostname in hostnames:
        _question_for(hostname)
    if not 0.1 <= timeout <= 3.0:
        raise DnsDiagnosticError("DNS timeout must be between 0.1 and 3 seconds.")

    route = snapshot.preferred_route("IPv4")
    adapter = next((item for item in snapshot.adapters
                    if route is not None and item.index == route.interface_index), None)
    if adapter is None:
        return DnsReport(None, (), (), (Finding(
            "info", "DNS servers could not be selected",
            "No usable IPv4 default-route interface was identified. This is not proof of a DNS fault.",
            "Check the network scan and routing information first.",
        ),))

    resolvers = []
    for candidate in adapter.dns:
        try:
            ip = ipaddress.IPv4Address(candidate)
        except ipaddress.AddressValueError:
            continue
        if not (ip.is_multicast or ip.is_unspecified) and str(ip) not in resolvers:
            resolvers.append(str(ip))
    resolvers = resolvers[:2]
    if not resolvers:
        return DnsReport(adapter.name, (), (), (Finding(
            "info", "No IPv4 DNS server listed on the selected interface",
            "Windows did not report an IPv4 DNS resolver on the interface used by the default route.",
            "Review DNS configuration. The Windows DNS client may use other resolver paths.",
        ),))

    perform = query or query_dns
    observations = tuple(
        perform(resolver, hostname, timeout=timeout)
        for resolver in resolvers for hostname in hostnames
    )
    findings = []
    good = sum(item.status == "answered" for item in observations)
    bad = [item for item in observations if item.status in
           {"timeout", "server_error", "invalid_response", "transport_error", "truncated"}]
    if good:
        findings.append(Finding(
            "good", "Direct DNS queries returned IPv4 addresses",
            f"{good} of {len(observations)} direct queries returned IPv4 A records.",
            "Compare results across resolvers and repeat if name resolution becomes unreliable.",
        ))
    if bad:
        findings.append(Finding(
            "warning" if good else "info", "Some direct DNS queries were inconclusive",
            f"{len(bad)} of {len(observations)} direct queries did not produce a validated response with IPv4 addresses. "
            "UDP filtering, DNS server policies, or network problems are possible.",
            "Check the individual results and compare with the regular scan before changing DNS settings.",
        ))
    if not good and not bad:
        findings.append(Finding(
            "info", "DNS replies did not include IPv4 addresses",
            "These hostnames received DNS responses such as NXDOMAIN or records other than IPv4 A records.",
            "Check the requested hostname and the individual DNS response codes.",
        ))
    return DnsReport(adapter.name, tuple(resolvers), observations, tuple(findings))
