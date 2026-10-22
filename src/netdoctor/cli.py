
"""NetDoctor's human-readable and JSON command-line interface."""

import argparse
import json
import logging
import math
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from netdoctor import __version__
from netdoctor.checks import TEST_HOSTS, check_endpoint, diagnose
from netdoctor.crosscheck import CrosscheckReport, run_crosscheck
from netdoctor.dnsdiagnostics import DnsDiagnosticError, DnsReport, diagnose_dns
from netdoctor.icmp import ProbeError
from netdoctor.latency import LatencyError, LatencyReport, measure_latency
from netdoctor.models import Report
from netdoctor.pathtrace import TraceReport, trace_paths
from netdoctor.windows import DiscoveryError, collect_snapshot

LOG = logging.getLogger("netdoctor")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netdoctor", description="Understand your Windows network connection.",
    )
    parser.add_argument(
        "command", nargs="?", choices=["scan", "latency", "investigate", "trace", "dns"],
        default="scan", help="scan (default), latency, investigate, trace, or dns",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Inspect local settings without public network checks (scan only)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output JSON")
    parser.add_argument(
        "--timeout", type=float, default=None, metavar="SECONDS",
        help="Per-probe timeout (trace: 0.8 s; dns: 1.5 s; others: 2 s)",
    )
    parser.add_argument("--verbose", action="store_true", help="Show diagnostic progress")
    parser.add_argument(
        "--count", type=int, default=None, metavar="N",
        help="Attempts per destination (trace: probes per hop)",
    )
    parser.add_argument(
        "--interval", type=float, default=None, metavar="SECONDS",
        help="Pause between latency/investigate probes (0–2, default: 0.25)",
    )
    parser.add_argument(
        "--target", action="append", default=[], metavar="HOST",
        help="IPv4 or hostname (trace: max 2; latency/investigate: max 3)",
    )
    parser.add_argument(
        "--hops", type=int, default=None, metavar="N",
        help="Maximum IPv4 hops to trace (1–24, default: 12; trace only)",
    )
    parser.add_argument(
        "--hostname", action="append", default=[], metavar="NAME",
        help="DNS name to query directly (up to 3, dns only)",
    )
    parser.add_argument(
        "--version", action="version", version=f"NetDoctor {__version__}",
    )
    return parser


def _print_findings(findings, console: Console) -> None:
    colors = {"good": "green", "warning": "yellow", "critical": "red", "info": "cyan"}
    for finding in findings:
        color = colors[finding.severity]
        console.print(f"[{color}]{finding.title}[/{color}]")
        console.print(f"  {finding.explanation}")
        console.print(f"  [bold]Next step:[/bold] {finding.action}")


def _format_ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} ms"


def _print_report(report: Report, console: Console) -> None:
    console.print(Panel.fit(
        f"NetDoctor v{__version__}  |  Connection: "
        f"[bold]{report.online_status.replace('_', ' ').title()}[/bold]",
        title="Network Report",
    ))
    route = report.snapshot.preferred_route("IPv4")
    if route:
        console.print(
            f"[bold]Lowest-metric IPv4 default route:[/bold] "
            f"interface #{route.interface_index}, "
            f"next hop {route.next_hop or 'Not reported'} "
            f"(metric {route.total_metric})"
        )
    elif not report.snapshot.routes_complete:
        console.print(
            "[bold]IPv4 default route:[/bold] "
            "Cannot determine (route data incomplete)"
        )
    else:
        console.print(
            "[bold]IPv4 default route:[/bold] "
            "Not found on an active adapter"
        )

    table = Table(title="Windows Network Interfaces", show_lines=False)
    for label in ("Interface", "State", "Type*", "IPv4", "IPv6", "DNS"):
        table.add_column(label, overflow="fold")
    for adapter in report.snapshot.adapters:
        table.add_row(
            f"{adapter.name} (#{adapter.index})", adapter.status,
            adapter.medium, ", ".join(adapter.ipv4) or "—",
            ", ".join(adapter.ipv6) or "—", ", ".join(adapter.dns) or "—",
        )
    console.print(table)
    console.print(
        "[dim]* Connection type is inferred from the adapter's name/description.[/dim]"
    )
    if report.checks:
        checks_table = Table(title="Public Connectivity Checks")
        for label in ("Host", "DNS", "TCP 443", "Explanation"):
            checks_table.add_column(label)
        for check in report.checks:
            checks_table.add_row(
                check.host, "OK" if check.dns_ok else "Failed",
                "OK" if check.tcp_ok else "Failed", check.detail,
            )
        console.print(checks_table)
    console.print("\n[bold]What NetDoctor found[/bold]")
    _print_findings(report.findings, console)
    console.print(
        "\n[dim]No speed, ping, VPN, hotspot or CGNAT claims "
        "are made by this initial scan.[/dim]"
    )


def _print_latency(report: LatencyReport, console: Console) -> None:
    console.print(Panel.fit(
        f"NetDoctor v{__version__} | IPv4 ICMP responsiveness",
        title="Latency Report",
    ))
    table = Table(title="Round-trip Time and Echo Replies")
    for label in (
        "Destination", "Replies", "Median", "P95", "RTT change", "Timeouts",
    ):
        table.add_column(label, overflow="fold")
    for result in report.targets:
        table.add_row(
            f"{result.name} ({result.address})", f"{result.replies}/{result.sent}",
            _format_ms(result.median_ms), _format_ms(result.p95_ms),
            _format_ms(result.variation_ms), str(result.timeouts),
        )
    console.print(table)
    for result in report.targets:
        if result.loss_percent is not None and result.loss_percent > 0:
            console.print(
                f"[yellow]{result.name}:[/yellow] "
                f"{result.loss_percent:.1f}% apparent ICMP echo loss in this short sample."
            )
        if result.unreachable or result.errors:
            console.print(
                f"[yellow]{result.name}:[/yellow] "
                f"{result.unreachable} unreachable, {result.errors} ICMP errors."
            )
    console.print("\n[bold]What NetDoctor found[/bold]")
    _print_findings(report.findings, console)
    console.print(f"\n[dim]{report.note}[/dim]")


def _print_crosscheck(report: CrosscheckReport, console: Console) -> None:
    console.print(Panel.fit(
        f"NetDoctor v{__version__} | ICMP versus TCP port 443",
        title="Network Investigation",
    ))
    tcp_by_ip = {target.address: target for target in report.tcp}
    table = Table(title="Measurements to the Same IPv4 Addresses")
    for label in (
        "Destination", "ICMP replies", "ICMP median", "TCP connects", "TCP median",
    ):
        table.add_column(label, overflow="fold")
    for target in report.latency.targets:
        tcp = tcp_by_ip.get(target.address)
        table.add_row(
            f"{target.name} ({target.address})",
            f"{target.replies}/{target.sent}", _format_ms(target.median_ms),
            f"{tcp.connected}/{tcp.sent}" if tcp is not None else "Not tested",
            _format_ms(tcp.median_ms) if tcp is not None else "—",
        )
    console.print(table)
    console.print("\n[bold]What NetDoctor found[/bold]")
    _print_findings(report.findings, console)
    console.print(f"\n[dim]{report.note}[/dim]")


def _print_trace(report: TraceReport, console: Console) -> None:
    console.print(Panel.fit(
        f"NetDoctor v{__version__} | IPv4 path tracing",
        title="Network Path Investigation",
    ))
    for trace in report.targets:
        table = Table(title=f"{trace.name} ({trace.address})")
        table.add_column("TTL", justify="right")
        table.add_column("Responding router / destination", overflow="fold")
        table.add_column("Response", overflow="fold")
        for hop in trace.hops:
            for probe in hop.probes:
                table.add_row(
                    str(hop.ttl), probe.address or "—",
                    f"{probe.status}: {_format_ms(probe.rtt_ms)}",
                )
        console.print(table)
        if trace.reached:
            console.print(f"[green]Destination answered at hop {len(trace.hops)}.[/green]")
        elif trace.stop_reason == "probe_error":
            console.print("[yellow]Trace stopped because an ICMP probe failed.[/yellow]")
        else:
            console.print("[cyan]Destination was not observed within the hop limit.[/cyan]")
    console.print("\n[bold]What NetDoctor found[/bold]")
    _print_findings(report.findings, console)
    console.print(f"\n[dim]{report.note}[/dim]")


def _print_dns(report: DnsReport, console: Console) -> None:
    console.print(Panel.fit(
        f"NetDoctor v{__version__} | Configured DNS server checks",
        title="DNS Diagnostics",
    ))
    console.print(f"[bold]Default-route interface:[/bold] {report.interface or 'Not determined'}")
    console.print(f"[bold]Configured IPv4 DNS servers:[/bold] {', '.join(report.resolvers) or 'None found'}")
    if report.observations:
        table = Table(title="Direct UDP DNS A-record Queries")
        for label in ("Resolver", "Hostname", "Status", "Response time", "IPv4 answers"):
            table.add_column(label, overflow="fold")
        for result in report.observations:
            table.add_row(
                result.resolver, result.hostname, result.status.replace("_", " "),
                _format_ms(result.elapsed_ms), ", ".join(result.addresses) or "—",
            )
        console.print(table)
    console.print("\n[bold]What NetDoctor found[/bold]")
    _print_findings(report.findings, console)
    console.print(f"\n[dim]{report.note}[/dim]")


def _error(code: str, message: str, as_json: bool, console: Console) -> int:
    if as_json:
        print(json.dumps({"error": {"code": code, "message": message}}))
    else:
        console.print(f"[red]{code}: {message}[/red]")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    is_measurement = args.command in ("latency", "investigate", "trace")
    is_trace = args.command == "trace"
    is_dns = args.command == "dns"

    if args.timeout is None:
        args.timeout = 0.8 if is_trace else (1.5 if is_dns else 2.0)
    timeout_max = 3 if is_trace or is_dns else (5 if is_measurement else 10)
    if not math.isfinite(args.timeout) or not 0.1 <= args.timeout <= timeout_max:
        parser.error(f"--timeout must be between 0.1 and {timeout_max} seconds")

    if is_dns:
        if args.offline:
            parser.error("--offline is only available with scan; dns sends queries")
        if args.target or args.count is not None or args.interval is not None or args.hops is not None:
            parser.error("dns supports --hostname and --timeout, not measurement or trace flags")
        if len(args.hostname) > 3:
            parser.error("Specify at most three --hostname values")
    elif args.hostname:
        parser.error("--hostname is only available with dns")

    if is_measurement:
        if args.offline:
            parser.error("--offline is only available with scan")
        args.count = (1 if is_trace else 6) if args.count is None else args.count
        if is_trace:
            args.hops = 12 if args.hops is None else args.hops
            if not 1 <= args.hops <= 24:
                parser.error("--hops must be between 1 and 24")
            if not 1 <= args.count <= 2:
                parser.error("--count for trace must be 1 or 2 probes per hop")
            if args.interval is not None:
                parser.error("--interval is not supported for trace")
            if len(args.target) > 2:
                parser.error("Specify at most two --target values for trace")
        else:
            if args.hops is not None:
                parser.error("--hops is only available with trace")
            args.interval = 0.25 if args.interval is None else args.interval
            if not 2 <= args.count <= 12:
                parser.error("--count must be between 2 and 12")
            if not math.isfinite(args.interval) or not 0 <= args.interval <= 2:
                parser.error("--interval must be between 0 and 2 seconds")
            if len(args.target) > 3:
                parser.error("Specify at most three --target values")
    elif not is_dns and (args.target or args.count is not None or args.interval is not None or args.hops is not None):
        parser.error("--target, --count, --interval and --hops require a measurement command")

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s", stream=sys.stderr,
    )
    console = Console(stderr=True)

    if is_trace:
        try:
            report = trace_paths(
                targets=tuple(args.target), max_hops=args.hops,
                probes_per_hop=args.count, timeout_ms=round(args.timeout * 1000),
                on_target=lambda name, address: LOG.info("Tracing %s (%s)...", name, address),
            )
        except (LatencyError, ProbeError) as exc:
            return _error("ND-301", str(exc), args.as_json, console)
        if args.as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            _print_trace(report, Console())
        return 0

    try:
        LOG.info("Reading Windows network adapters, IP configuration and default routes...")
        snapshot = collect_snapshot()

        if is_dns:
            report = diagnose_dns(
                snapshot,
                hostnames=tuple(args.hostname) or ("example.com", "www.microsoft.com"),
                timeout=args.timeout,
            )
            if args.as_json:
                print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            else:
                _print_dns(report, Console())
            return 0

        if args.command == "latency":
            report = measure_latency(
                snapshot, count=args.count, timeout_ms=round(args.timeout * 1000),
                interval=args.interval, targets=tuple(args.target),
                on_target=lambda name, address: LOG.info("Measuring %s (%s)...", name, address),
            )
            if args.as_json:
                print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            else:
                _print_latency(report, Console())
            return 0

        if args.command == "investigate":
            report = run_crosscheck(
                snapshot, count=args.count, timeout_ms=round(args.timeout * 1000),
                interval=args.interval, targets=tuple(args.target),
                on_icmp=lambda name, address: LOG.info("ICMP to %s (%s)...", name, address),
                on_tcp=lambda name, address: LOG.info("TCP port 443 to %s (%s)...", name, address),
            )
            if args.as_json:
                print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            else:
                _print_crosscheck(report, Console())
            return 0

        checks = ()
        if not args.offline:
            results = []
            for host in TEST_HOSTS:
                LOG.info("Checking DNS and TCP port 443 for %s...", host)
                results.append(check_endpoint(host, timeout=args.timeout))
            checks = tuple(results)
        report = diagnose(snapshot, checks)

    except DiscoveryError as exc:
        return _error("ND-101", str(exc), args.as_json, console)
    except DnsDiagnosticError as exc:
        return _error("ND-401", str(exc), args.as_json, console)
    except (LatencyError, ProbeError) as exc:
        return _error("ND-201", str(exc), args.as_json, console)

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        _print_report(report, Console())
    return 0
