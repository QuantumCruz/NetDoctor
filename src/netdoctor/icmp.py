"""Windows-native IPv4 ICMP echo requests. No administrator rights or shell parsing."""

import ctypes
import ipaddress
import platform
import sys
from dataclasses import dataclass
from typing import Literal


class ProbeError(Exception):
    """An ICMP request could not be executed or interpreted reliably."""


@dataclass(frozen=True)
class EchoResult:
    status: Literal["reply", "timeout", "unreachable", "error"]
    rtt_ms: float | None
    detail: str


class _ReplyHeader(ctypes.Structure):
    """First three fields shared by ICMP_ECHO_REPLY and ICMP_ECHO_REPLY32."""

    _fields_ = [
        ("address", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
        ("round_trip_time", ctypes.c_uint32),
    ]


_TIMEOUT = 11010  # IP_REQ_TIMED_OUT
_UNREACHABLE = {11002, 11003, 11004, 11005, 11012}
_PAYLOAD = b"NetDoctor IPv4 echo"


def _open_api():
    try:
        library = ctypes.WinDLL("iphlpapi.dll", use_last_error=True)
        create = library.IcmpCreateFile
        create.argtypes = []
        create.restype = ctypes.c_void_p
        send = library.IcmpSendEcho
        send.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint16,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        send.restype = ctypes.c_uint32
        close = library.IcmpCloseHandle
        close.argtypes = [ctypes.c_void_p]
        close.restype = ctypes.c_int
        return create, send, close
    except (OSError, AttributeError) as exc:
        raise ProbeError(
            "Windows ICMP support could not be loaded."
        ) from exc


def ping_ipv4(address: str, *, timeout_ms: int = 1000) -> EchoResult:
    """Send one echo; distinguish unanswered probes from API errors."""
    try:
        ip = ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError as exc:
        raise ProbeError(
            f"Not a valid IPv4 address: {address!r}."
        ) from exc

    if not 100 <= timeout_ms <= 5000:
        raise ValueError(
            "ICMP timeout must be between 100 and 5000 milliseconds."
        )

    if platform.system() != "Windows":
        raise ProbeError(
            "This ICMP implementation currently requires Windows."
        )

    create, send, close = _open_api()
    handle = create()

    if handle in (None, ctypes.c_void_p(-1).value):
        raise ProbeError(
            "Windows could not open an ICMP handle "
            f"(error {ctypes.get_last_error()})."
        )

    try:
        request = ctypes.create_string_buffer(_PAYLOAD)

        # Leave sufficient space for 32-bit and 64-bit reply layouts.
        reply = ctypes.create_string_buffer(128 + len(_PAYLOAD))
        ip_value = int.from_bytes(ip.packed, byteorder=sys.byteorder)

        returned = send(
            handle,
            ip_value,
            ctypes.byref(request),
            len(_PAYLOAD),
            None,
            ctypes.byref(reply),
            ctypes.sizeof(reply),
            timeout_ms,
        )

        if returned == 0:
            code = ctypes.get_last_error()

            if code == _TIMEOUT:
                return EchoResult(
                    "timeout", None,
                    "No ICMP echo reply before the timeout."
                )

            if code in _UNREACHABLE:
                return EchoResult(
                    "unreachable", None,
                    f"Network reported destination unreachable (code {code})."
                )

            return EchoResult(
                "error", None,
                f"Windows ICMP returned error {code}."
            )

        header = _ReplyHeader.from_buffer_copy(reply)

        if header.status == 0:
            return EchoResult(
                "reply",
                float(header.round_trip_time),
                "ICMP echo reply received.",
            )

        if header.status == _TIMEOUT:
            return EchoResult(
                "timeout", None,
                "No ICMP echo reply before the timeout.",
            )

        if header.status in _UNREACHABLE:
            return EchoResult(
                "unreachable", None,
                "Network reported destination unreachable "
                f"(code {header.status}).",
            )

        return EchoResult(
            "error", None,
            f"Windows ICMP returned status {header.status}.",
        )
    finally:
        close(handle)