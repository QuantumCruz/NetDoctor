
"""Console entry point. UI and diagnostics do not depend on one another."""

import argparse
import json
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from netdoctor import __version__
from netdoctor.checks import TEST_HOSTS, check_endpoint, diagnose
from netdoctor.models import Report
from netdoctor.windows import DiscoveryError, collect_snapshot

LOG = logging.getLogger("netdoctor")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netdoctor", description="Understand your Windows network connection.")
    parser.add_argument("command", nargs="?", choices=["scan"], default="scan",
                        help="Scan local network settings and connectivity (default: scan)")
    parser.add_argument("--offline", action="store_true",
                        help="Inspect this PC without contacting public hosts")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Output the complete report as JSON")
    parser.add_argument("--timeout", type=float, default=2.0, metavar="SECONDS",
                        help="Per-address TCP connection timeout (default: 2)")
    parser.add_argument("--verbose", action="store_true", help="Show diagnostic progress")
    parser.add_argument("--version", action="version", version=f"NetDoctor {__version__}")
    return parser


def _print_report(report: Report, console: Console) -> None:
    console.print(Panel.fit(f"NetDoctor v{__version__}  |  Connection: "
                            f"[bold]{report.online_status.replace('_', ' ').title()}[/bold]",
                            title="Network Report"))
    route = report.snapshot.preferred_route("IPv4")
    if route:
        console.print(f"[bold]Lowest-metric IPv4 default route:[/bold] "
                      f"interface #{route.interface_index}, "
                      f"next hop {route.next_hop or 'Not reported'} "
                      f"(metric {route.total_metric})")
    elif not report.snapshot.routes_complete:
        console.print("[bold]IPv4 default route:[/bold] Cannot determine (route data incomplete)")
    else:
        console.print("[bold]IPv4 default route:[/bold] Not found on an active adapter")

    table = Table(title="Windows Network Interfaces", show_lines=False)
    for label in ("Interface", "State", "Type*", "IPv4", "IPv6", "DNS"):
        table.add_column(label, overflow="fold")
    for adapter in report.snapshot.adapters:
        table.add_row(f"{adapter.name} (#{adapter.index})", adapter.status,
                      adapter.medium, ", ".join(adapter.ipv4) or "—",
                      ", ".join(adapter.ipv6) or "—", ", ".join(adapter.dns) or "—")
    console.print(table)
    console.print("[dim]* Connection type is inferred from the adapter's name/description.[/dim]")

    if report.checks:
        checks_table = Table(title="Public Connectivity Checks")
        checks_table.add_column("Host")
        checks_table.add_column("DNS")
        checks_table.add_column("TCP 443")
        checks_table.add_column("Explanation")
        for check in report.checks:
            checks_table.add_row(check.host, "OK" if check.dns_ok else "Failed",
                                 "OK" if check.tcp_ok else "Failed", check.detail)
        console.print(checks_table)

    console.print("\n[bold]What NetDoctor found[/bold]")
    colors = {"good": "green", "warning": "yellow", "critical": "red", "info": "cyan"}
    for finding in report.findings:
        color = colors[finding.severity]
        console.print(f"[{color}]{finding.title}[/{color}]")
        console.print(f"  {finding.explanation}")
        console.print(f"  [bold]Next step:[/bold] {finding.action}")
    console.print("\n[dim]No speed, ping, VPN, hotspot or CGNAT claims are made by this initial scan.[/dim]")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not 0.1 <= args.timeout <= 10.0 or args.timeout != args.timeout:
        parser.error("--timeout must be between 0.1 and 10 seconds")

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s: %(message)s", stream=sys.stderr)
    console = Console(stderr=True)
    try:
        LOG.info("Reading Windows network adapters, IP configuration and default routes...")
        snapshot = collect_snapshot()
        checks = ()
        if not args.offline:
            results = []
            for host in TEST_HOSTS:
                LOG.info("Checking DNS and TCP port 443 for %s...", host)
                results.append(check_endpoint(host, timeout=args.timeout))
            checks = tuple(results)
        report = diagnose(snapshot, checks)
    except DiscoveryError as exc:
        if args.as_json:
            print(json.dumps({"error": {"code": "ND-101", "message": str(exc)}}))
        else:
            console.print(f"[red]ND-101: {exc}[/red]")
        return 2

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        _print_report(report, Console())
    return 0
