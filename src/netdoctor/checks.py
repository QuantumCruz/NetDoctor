
"""Lightweight public-endpoint checks and conservative interpretation."""

import socket

from netdoctor.models import EndpointCheck, Finding, Report, Snapshot

# These are HTTPS ports on independent public networks. No data is uploaded.
TEST_HOSTS = ("www.cloudflare.com", "www.microsoft.com")


def check_endpoint(host: str, *, timeout: float = 2.0) -> EndpointCheck:
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return EndpointCheck(host, False, False, "Name lookup failed.")

    # Try one OS-selected candidate per address family. An IPv6 failure alone
    # must not cause a working IPv4 connection to be reported as unreachable.
    candidates = []
    seen_families = set()
    for family, kind, protocol, _, address in addresses:
        if family in (socket.AF_INET, socket.AF_INET6) and family not in seen_families:
            candidates.append((family, kind, protocol, address))
            seen_families.add(family)
    if not candidates:
        return EndpointCheck(host, False, False, "No usable IP addresses were returned.")

    for family, kind, protocol, address in candidates:
        try:
            with socket.socket(family, kind, protocol) as connection:
                connection.settimeout(timeout)
                connection.connect(address)
            return EndpointCheck(host, True, True, "TCP port 443 accepted a connection.")
        except OSError:
            continue
    return EndpointCheck(host, True, False,
                         "Name lookup worked, but TCP port 443 could not be reached.")


def diagnose(snapshot: Snapshot, checks: tuple[EndpointCheck, ...]) -> Report:
    findings: list[Finding] = []
    active = [adapter for adapter in snapshot.adapters if adapter.is_up]
    reachable = sum(check.tcp_ok for check in checks)
    route = snapshot.preferred_route("IPv4") or snapshot.preferred_route("IPv6")

    if not snapshot.adapters:
        findings.append(Finding("warning", "No network adapters were discovered",
            "Windows did not return any network interfaces.",
            "Check that your network adapter is installed and enabled."))
    elif not active:
        findings.append(Finding("critical", "No active network connection detected",
            "Windows reports that all discovered network interfaces are down.",
            "Connect to Wi-Fi or plug in an Ethernet cable, then run the test again."))
    elif route is None and snapshot.routes_complete:
        findings.append(Finding("warning", "No usable default route was found",
            "Windows did not report a default route on an active interface. "
            "Connections to outside networks may fail.",
            "Check your router connection and IP configuration. "
            "If a VPN is active, verify its network routes."))

    if checks:
        if reachable == len(checks):
            status = "reachable"
            findings.append(Finding("good", "Basic internet transport is reachable",
                "The tested public hosts accepted TCP connections on port 443. "
                "This does not yet verify browser performance or internet speed.",
                "Continue with latency and speed diagnostics when available."))
        elif reachable:
            status = "partial"
            findings.append(Finding("warning", "Connectivity differs by destination",
                "At least one public test host accepted a TCP connection, but another did not.",
                "Repeat the test. If this persists, investigate the failing destination."))
        elif not any(check.dns_ok for check in checks):
            status = "unverified"
            findings.append(Finding("warning", "Public hostnames could not be resolved",
                "All test name lookups failed. This can happen with a DNS problem "
                "or a wider connectivity problem; the cause is not yet confirmed.",
                "Check your configured DNS servers and try the test again."))
        else:
            status = "unverified"
            findings.append(Finding("warning", "External TCP access could not be confirmed",
                "At least one hostname resolved, but neither tested host accepted "
                "a TCP connection on port 443. Filtering, routing, or the remote "
                "destination could explain this.",
                "Retry the test and check whether normal HTTPS websites open."))
    else:
        status = "not_tested"
        findings.append(Finding("info", "External connectivity was not tested",
            "Only local Windows network settings were collected.",
            "Run NetDoctor without --offline to check public TCP reachability."))

    for warning in snapshot.warnings:
        findings.append(Finding("warning", "Partial Windows network information",
                                warning, "Retry the scan. Some details may be unavailable."))

    return Report(snapshot=snapshot, checks=checks, findings=tuple(findings),
                  online_status=status)
