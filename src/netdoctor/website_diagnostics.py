
"""User-triggered, low-data HTTPS website response diagnostics.

One public endpoint, one DNS lookup, one TCP/TLS connection and one HEAD
request. Redirects are not followed and response bodies are not downloaded.
This is not a throughput, browser, or CDN-route benchmark.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote, urlsplit


class WebsiteTargetError(ValueError):
    """Invalid or unsafe website input; no connection should be attempted."""


_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_STATUS = re.compile(rb"^HTTP/1\.[01] ([1-5][0-9]{2})(?:[ \t]|$)")
_DISCLAIMER = (
    "One direct HTTPS HEAD request, with no body download or redirect follow. "
    "Times measure this particular destination, not sustained download speed, "
    "ISP responsibility, browser/proxy behavior, or other CDN servers."
)


def _target(value: str) -> tuple[str, str, str]:
    if not isinstance(value, str):
        raise WebsiteTargetError("Enter a website address.")

    raw = value.strip()
    if not raw or len(raw) > 512 or any(ch.isspace() for ch in raw):
        raise WebsiteTargetError(
            "Enter a website address (maximum 512 characters)."
        )

    if "://" not in raw:
        raw = "https://" + raw

    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise WebsiteTargetError(
            "Enter a valid HTTPS website address."
        ) from exc

    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise WebsiteTargetError(
            "Use HTTPS on port 443, without login details, query or fragment."
        )

    try:
        host = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise WebsiteTargetError(
            "Website hostname is not valid."
        ) from exc

    if len(host) > 253:
        raise WebsiteTargetError("Website hostname is too long.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        parts = host.split(".")
        if len(parts) < 2 or any(
            not _LABEL.fullmatch(p) for p in parts
        ):
            raise WebsiteTargetError(
                "Enter a valid public website hostname."
            )
    else:
        if not ip.is_global:
            raise WebsiteTargetError(
                "Private and non-public IP addresses are not supported."
            )

    path = parsed.path or "/"
    if (
        len(path) > 512
        or "\\" in path
        or any(ord(c) < 32 for c in path)
    ):
        raise WebsiteTargetError("Website path is not valid.")

    path = quote(path, safe="/!$&'()*+,;=:@%-._~")
    authority = f"[{host}]" if ":" in host else host

    return host, path, f"https://{authority}{path}"


def _result(
    *,
    url: str,
    host: str,
    stage: str,
    status: str,
    headline: str,
    explanation: str,
    next_step: str,
    timings: dict,
    http_status: int | None = None,
    address_family: str | None = None,
) -> dict:
    return {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "target": url,
        "hostname": host,
        "status": status,
        "stage": stage,
        "headline": headline,
        "explanation": explanation,
        "next_step": next_step,
        "dns_ms": timings["dns_ms"],
        "tcp_ms": timings["tcp_ms"],
        "tls_ms": timings["tls_ms"],
        "response_ms": timings["response_ms"],
        "http_status": http_status,
        "address_family": address_family,
        "limitation": _DISCLAIMER,
    }


def diagnose_website(
    target: str,
    *,
    timeout: float = 3.0,
    resolver: Callable = socket.getaddrinfo,
    socket_factory: Callable = socket.socket,
    tls_context_factory: Callable = ssl.create_default_context,
    clock: Callable = time.perf_counter,
) -> dict:
    """Measure DNS, TCP, TLS, and HEAD status without fetching a body."""
    host, path, display_url = _target(target)

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0.5 <= timeout <= 5.0
    ):
        raise WebsiteTargetError(
            "Timeout must be between 0.5 and 5 seconds."
        )

    timings = {
        "dns_ms": None,
        "tcp_ms": None,
        "tls_ms": None,
        "response_ms": None,
    }

    def measured(t0: float) -> float:
        return round(max(0.0, (clock() - t0) * 1000.0), 2)

    def failed(
        stage: str,
        headline: str,
        explanation: str,
        next_step: str,
    ) -> dict:
        return _result(
            url=display_url,
            host=host,
            stage=stage,
            status="inconclusive",
            headline=headline,
            explanation=explanation,
            next_step=next_step,
            timings=timings,
        )

    start = clock()
    try:
        addresses = resolver(
            host,
            443,
            type=socket.SOCK_STREAM,
        )
    except (OSError, ValueError, UnicodeError):
        timings["dns_ms"] = measured(start)
        return failed(
            "dns",
            "Website address could not be resolved",
            "The system's name lookup did not return an address.",
            "Check the website spelling and try another known website.",
        )

    timings["dns_ms"] = measured(start)
    chosen = None

    for family, socktype, proto, _, sockaddr in addresses:
        if (
            family not in (socket.AF_INET, socket.AF_INET6)
            or socktype != socket.SOCK_STREAM
        ):
            continue

        try:
            address = ipaddress.ip_address(sockaddr[0])
        except (ValueError, TypeError, IndexError):
            continue

        if address.is_global and address.version == (
            4 if family == socket.AF_INET else 6
        ):
            chosen = (family, proto, str(address))
            break

    if chosen is None:
        return failed(
            "dns",
            "No public address available",
            "The website did not resolve to a usable public IP address. "
            "Private and reserved destinations are intentionally excluded.",
            "Try a public website. Local network addresses require "
            "other diagnostic tools.",
        )

    family, proto, address = chosen
    family_label = (
        "IPv4" if family == socket.AF_INET else "IPv6"
    )
    sockaddr = (
        (address, 443)
        if family == socket.AF_INET
        else (address, 443, 0, 0)
    )

    try:
        with socket_factory(
            family, socket.SOCK_STREAM, proto
        ) as tcp:
            tcp.settimeout(timeout)

            start = clock()
            try:
                tcp.connect(sockaddr)
            except (OSError, TimeoutError):
                return failed(
                    "tcp",
                    "TCP connection did not complete",
                    "The website's public IP did not accept this "
                    "TCP connection within the test limit.",
                    "Try again later or compare the same site "
                    "on another connection.",
                )

            timings["tcp_ms"] = measured(start)

            context = tls_context_factory()
            if hasattr(context, "set_alpn_protocols"):
                context.set_alpn_protocols(["http/1.1"])

            start = clock()
            try:
                secure = context.wrap_socket(
                    tcp,
                    server_hostname=host,
                )
            except ssl.SSLCertVerificationError:
                return failed(
                    "tls",
                    "Website certificate could not be verified",
                    "The secure connection failed certificate "
                    "validation; this is not a speed measurement.",
                    "Check the system clock and whether a VPN or "
                    "security product intercepts HTTPS.",
                )
            except (ssl.SSLError, OSError, TimeoutError):
                return failed(
                    "tls",
                    "Secure connection could not be established",
                    "TCP connected but the TLS handshake did "
                    "not finish successfully.",
                    "Retry the website and compare with your "
                    "browser or another connection.",
                )

            timings["tls_ms"] = measured(start)

            with secure:
                secure.settimeout(timeout)

                request = (
                    f"HEAD {path} HTTP/1.1\r\n"
                    f"Host: {host}\r\n"
                    "User-Agent: NetDoctor/0.3\r\n"
                    "Accept: */*\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")

                try:
                    secure.sendall(request)

                    start = clock()
                    response = b""
                    first_byte = None
                    deadline = clock() + timeout

                    while (
                        b"\n" not in response
                        and len(response) < 4096
                    ):
                        remaining = deadline - clock()

                        if remaining <= 0:
                            raise TimeoutError(
                                "HTTP status line deadline elapsed"
                            )

                        secure.settimeout(remaining)
                        chunk = secure.recv(
                            min(512, 4096 - len(response))
                        )

                        if not chunk:
                            break

                        if first_byte is None:
                            first_byte = measured(start)

                        response += chunk

                except (OSError, TimeoutError):
                    return failed(
                        "http",
                        "No HTTP response received",
                        "The secure connection was established, but "
                        "the HEAD request did not return a usable response.",
                        "Try the website in a browser; some services "
                        "reject diagnostic HEAD requests.",
                    )

                timings["response_ms"] = first_byte

                line = response.split(
                    b"\n", 1
                )[0].rstrip(b"\r")

                match = _STATUS.match(line)

                if match is None:
                    return failed(
                        "http",
                        "HTTP response could not be interpreted",
                        "The server returned no valid HTTP/1.x "
                        "status line for this HEAD request.",
                        "Try another website or repeat this test later.",
                    )

                code = int(match.group(1))

                if code < 200:
                    status = "inconclusive"
                    headline = "Website returned an interim HTTP status"
                    description = (
                        f"HTTP {code} is not a final response "
                        "to the HEAD request."
                    )
                    next_step = (
                        "Repeat the check or open the website "
                        "in your browser."
                    )

                elif code in (405, 501):
                    status = "inconclusive"
                    headline = (
                        "Website does not support this HEAD request"
                    )
                    description = (
                        "The server responded but did not accept "
                        "the metadata-only request."
                    )
                    next_step = (
                        "Open the site normally; this test cannot "
                        "measure its page or download speed."
                    )

                elif code >= 500:
                    status = "responded"
                    headline = "Website server reported an error"
                    description = (
                        f"The server returned HTTP {code}; the network "
                        "route reached an HTTP service."
                    )
                    next_step = (
                        "Retry the page later; this does not establish "
                        "which system caused the server error."
                    )

                elif code >= 400:
                    status = "responded"
                    headline = (
                        "Website responded with an access or request status"
                    )
                    description = (
                        f"The server returned HTTP {code}; the endpoint "
                        "was reached, but the request was not accepted "
                        "as normal content."
                    )
                    next_step = (
                        "Check the website in your browser. Permissions, "
                        "protection rules, or the path may differ."
                    )

                elif code >= 300:
                    status = "responded"
                    headline = "Website responded with a redirect"
                    description = (
                        f"HTTP {code} was returned. "
                        "Redirects are intentionally not followed."
                    )
                    next_step = (
                        "Open the destination in a browser if you "
                        "need to check the redirected page."
                    )

                else:
                    status = "responded"
                    headline = "Website responded over HTTPS"
                    description = (
                        f"The endpoint returned HTTP {code} "
                        "to a metadata-only request."
                    )
                    next_step = (
                        "For a slow download, compare the actual asset "
                        "host and a second network; this test does not "
                        "measure transfer speed."
                    )

                return _result(
                    url=display_url,
                    host=host,
                    stage="complete",
                    status=status,
                    headline=headline,
                    explanation=description,
                    next_step=next_step,
                    timings=timings,
                    http_status=code,
                    address_family=family_label,
                )

    except (OSError, ssl.SSLError):
        return failed(
            "tcp",
            "Website connection could not start",
            "A local socket or secure transport error "
            "prevented the website test.",
            "Check the current connection and retry.",
        )
