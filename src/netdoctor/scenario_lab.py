
"""Offline diagnostic validation scenarios for NetDoctor developers.

No network, hardware, router, registry, geolocation or disk operations are
performed by this module. The normal diagnostic functions receive injected
synthetic observations; their conclusions can be regression-tested before we
attempt disruptive real-world fault testing.

Run: python -m netdoctor.scenario_lab
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from netdoctor.checks import TEST_HOSTS
from netdoctor.desktop_support import explain
from netdoctor.diagnosis_insights import analyze_diagnosis
from netdoctor.dnsdiagnostics import DnsObservation, DnsReport
from netdoctor.doctor import run_doctor
from netdoctor.icmp import EchoResult
from netdoctor.latency import LatencyReport, _summarize
from netdoctor.models import Adapter, DefaultRoute, EndpointCheck, Snapshot
from netdoctor.network_intel import ProxySettings, collect_intelligence
from netdoctor.webdesktop import _wifi_adapter_fallback
from netdoctor.windows_wifi import WifiLink


@dataclass(frozen=True)
class Scenario:
    name: str
    explanation: str
    tcp: tuple[bool, bool] = (True, True)
    dns: Literal["answered", "timeout", "unavailable"] = "answered"
    gateway_replies: int = 4
    public_pings_reply: bool = True
    vpn: Literal["none", "overlay", "default"] = "none"
    wifi_signal: int | None = None
    proxy_configured: bool = False
    history: tuple[Literal["ok", "mixed", "failed"], ...] = ()
    download_mbps: float | None = None
    latency_ms: float = 25.0
    speed_age_minutes: int = 0
    download_delay_ms: float | None = None


SCENARIOS = (
    Scenario(
        "healthy",
        "Both public connections and basic DNS succeed.",
    ),
    Scenario(
        "partial_access",
        "Only one public TCP destination answers.",
        tcp=(True, False),
    ),
    Scenario(
        "access_unverified",
        "Neither public TCP destination answers.",
        tcp=(False, False),
    ),
    Scenario(
        "dns_direct_timeout",
        "Direct UDP DNS times out but public TCP works.",
        dns="timeout",
    ),
    Scenario(
        "dns_unavailable",
        "DNS probing cannot run but public TCP works.",
        dns="unavailable",
    ),
    Scenario(
        "ping_filtered",
        "ICMP replies are filtered while TCP works.",
        gateway_replies=0,
        public_pings_reply=False,
    ),
    Scenario(
        "overlay_present",
        "Tailscale-style interface is up but is not the internet route.",
        vpn="overlay",
    ),
    Scenario(
        "tunnel_default",
        "Default route uses a tunnel-style adapter.",
        vpn="default",
    ),
    Scenario(
        "wifi_private",
        "Windows hides wireless signal details.",
        wifi_signal=None,
    ),
    Scenario(
        "weak_wifi",
        "Actual weak Wi-Fi association was measured.",
        wifi_signal=24,
    ),
    Scenario(
        "proxy_present",
        "A Windows manual proxy setting is configured.",
        proxy_configured=True,
    ),
    Scenario(
        "recent_drops",
        "Some short connectivity rounds failed.",
        history=("ok", "failed", "ok", "mixed", "ok", "ok", "ok", "ok"),
    ),
    Scenario(
        "old_speed",
        "A low speed reading is more than two hours old.",
        download_mbps=0.3,
        latency_ms=400,
        speed_age_minutes=200,
    ),
    Scenario(
        "slow_download",
        "A recent test measured limited download bandwidth.",
        download_mbps=0.8,
    ),
    Scenario(
        "download_lag",
        "ICMP response time rose during a download.",
        download_delay_ms=70.0,
    ),
)


def _scenario_snapshot(case: Scenario) -> Snapshot:
    wifi = Adapter(
        6,
        "WiFi",
        "Intel(R) Wi-Fi 6E AX211 160MHz",
        "Up",
        "650 Mbps",
        "Wi-Fi (inferred)",
        ("192.168.1.20",),
        (),
        ("192.168.1.1",),
    )

    adapters = [wifi]
    internet_adapter = 6

    if case.vpn != "none":
        adapters.append(
            Adapter(
                8,
                "Tailscale",
                "Tailscale Tunnel",
                "Up",
                "100 Gbps",
                "Other",
                (),
                (),
                (),
            )
        )

        if case.vpn == "default":
            internet_adapter = 8

    return Snapshot(
        tuple(adapters),
        (
            DefaultRoute(
                "IPv4",
                internet_adapter,
                "192.168.1.1",
                0,
                20,
            ),
        ),
        (),
    )


def _simulated_dns(mode: str) -> DnsReport:
    answered = mode == "answered"

    return DnsReport(
        "WiFi",
        ("192.168.1.1",),
        (
            DnsObservation(
                "192.168.1.1",
                "example.com",
                "answered" if answered else "timeout",
                8.0 if answered else None,
                ("93.184.215.14",) if answered else (),
                0 if answered else None,
                "Injected test data",
            ),
        ),
        (),
    )


def _simulated_latency(case: Scenario) -> LatencyReport:
    def echoes(count: int, rtt: float):
        return tuple(
            EchoResult(
                "reply",
                rtt,
                "Injected reply",
            )
            if index < count
            else EchoResult(
                "timeout",
                None,
                "Injected timeout",
            )
            for index in range(4)
        )

    public = 4 if case.public_pings_reply else 0

    return LatencyReport(
        (
            _summarize(
                "Local gateway",
                "192.168.1.1",
                "gateway",
                echoes(case.gateway_replies, 3.0),
            ),
            _summarize(
                "Public destination A",
                "1.1.1.1",
                "public",
                echoes(public, 22.0),
            ),
            _summarize(
                "Public destination B",
                "8.8.8.8",
                "public",
                echoes(public, 28.0),
            ),
        ),
        (),
    )


def simulate(
    case: Scenario,
    *,
    now: datetime | None = None,
) -> dict:
    """Exercise the real diagnostic pipeline with injected evidence."""
    time = now or datetime.now(timezone.utc)

    if time.tzinfo is None:
        raise ValueError(
            "The scenario clock must be timezone-aware."
        )

    time = time.astimezone(timezone.utc)

    if not (0 <= case.gateway_replies <= 4):
        raise ValueError(
            "Gateway reply count must be 0..4."
        )

    if (
        case.wifi_signal is not None
        and not (0 <= case.wifi_signal <= 100)
    ):
        raise ValueError(
            "Wi-Fi signal percentage must be 0..100."
        )

    snapshot = _scenario_snapshot(case)

    success_by_host = dict(
        zip(TEST_HOSTS, case.tcp)
    )

    def endpoint(host, *, timeout):
        if host not in success_by_host:
            raise AssertionError(
                "Unexpected test destination"
            )

        succeeded = success_by_host[host]

        return EndpointCheck(
            host,
            True,
            succeeded,
            "Injected TCP result",
        )

    def dns(_snapshot, *, hostnames, timeout):
        if case.dns == "unavailable":
            from netdoctor.dnsdiagnostics import DnsDiagnosticError

            raise DnsDiagnosticError(
                "Simulated DNS probe unavailable"
            )

        return _simulated_dns(case.dns)

    def latency(_snapshot, *, count, timeout_ms, interval):
        return _simulated_latency(case)

    report = run_doctor(
        snapshot,
        endpoint_test=endpoint,
        dns_test=dns,
        latency_test=latency,
    )

    guide = explain(report)

    links = (
        ()
        if case.wifi_signal is None
        else (
            WifiLink(
                "Intel(R) Wi-Fi 6E AX211 160MHz",
                "Synthetic network",
                case.wifi_signal,
                650,
                650,
            ),
        )
    )

    network = collect_intelligence(
        snapshot,
        wifi_reader=lambda: links,
        proxy_reader=lambda: ProxySettings(
            manual=case.proxy_configured,
        ),
    ).to_dict()

    _wifi_adapter_fallback(
        snapshot,
        network,
    )

    overview = {
        "status": report.status,
        "network": network,
    }

    readings = None

    if case.download_mbps is not None:
        readings = {
            "tested_at": (
                time - timedelta(minutes=case.speed_age_minutes)
            ).isoformat(),
            "download_mbps": case.download_mbps,
            "latency_ms": case.latency_ms,
            "upload_mbps": 5.0,
        }

    history = [
        {
            "checked_at": (
                time - timedelta(seconds=10 * index)
            ).isoformat(),
            "state": state,
        }
        for index, state in enumerate(case.history)
    ]

    loaded = None

    if case.download_delay_ms is not None:
        loaded = {
            "tested_at": time.isoformat(),
            "status": "increase_observed",
            "change_ms": case.download_delay_ms,
        }

    interpretation = analyze_diagnosis(
        overview,
        reading=readings,
        samples=history,
        loaded=loaded,
        now=time,
    )

    return {
        "scenario": case.name,
        "description": case.explanation,
        "doctor_status": report.status,
        "doctor_headline": guide.headline,
        "diagnosis_headline": interpretation["headline"],
        "findings": interpretation["findings"],
        "notes": interpretation["notes"],
        "network": network,
        "doctor_steps": {
            step.name: step.status
            for step in report.steps
        },
    }


def main() -> int:
    print(
        "NETDOCTOR OFFLINE FAULT LAB - SYNTHETIC DATA ONLY"
    )
    print(
        "No live network check, data transfer or "
        "Windows configuration change.\n"
    )

    for case in SCENARIOS:
        result = simulate(case)

        labels = ", ".join(
            item["code"]
            for item in result["findings"]
        )

        print(
            f"{case.name:<21} "
            f"{result['doctor_status']:<11} "
            f"{labels}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
