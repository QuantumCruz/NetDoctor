
"""Combine existing NetDoctor observations into cautious troubleshooting advice.

Read-only and deterministic. No probes, network requests, or synthetic scores.
Old speed tests, previous-network history and VPN adapter names are not proof
of a present fault or of its cause.
"""

from datetime import datetime, timedelta, timezone
import math


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return date.astimezone(timezone.utc) if date.tzinfo else None


def _recent(value, now, minutes):
    when = _timestamp(value)
    return when is not None and timedelta(0) <= now - when <= timedelta(minutes=minutes)


def _number(source, key):
    if not isinstance(source, dict):
        return None
    n = source.get(key)
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        return None
    return float(n) if math.isfinite(n) and n >= 0 else None


def _finding(code, title, kind, evidence, step):
    return {"code": code, "title": title, "kind": kind,
            "evidence": evidence, "next_step": step}


def analyze_diagnosis(overview=None, *, reading=None, samples=(), loaded=None, now=None):
    """Return observed issues first, then plausible contributors, not a diagnosis of ISP.

    The baseline overview was collected separately by the desktop. History has no
    connection fingerprint, so it is always treated as possibly from another LAN.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Current time must include a timezone.")
    current = current.astimezone(timezone.utc)
    info = overview if isinstance(overview, dict) else {}
    network = info.get("network") if isinstance(info.get("network"), dict) else {}
    wifi = network.get("wifi") if isinstance(network.get("wifi"), dict) else {}
    vpn = network.get("vpn") if isinstance(network.get("vpn"), dict) else {}
    proxy = network.get("proxy") if isinstance(network.get("proxy"), dict) else {}

    findings = []
    facts = []
    status = info.get("status")
    if status == "reachable":
        facts.append("Basic connections succeeded at the time of the last quick check.")
    elif status == "attention":
        findings.append(_finding(
            "partial_access", "Some destinations did not connect", "observed",
            "The quick check reported mixed results across its test destinations.",
            "Retry the quick check. If only one website or app fails, investigate that service specifically."))
    elif status == "unverified":
        findings.append(_finding(
            "access_unverified", "Basic internet access was not confirmed", "observed",
            "The quick check could not confirm public connections. This does not identify where the failure occurred.",
            "Check whether a normal website opens, then check Wi-Fi or Ethernet and retry."))
    else:
        facts.append("A recent basic-connectivity result is not available.")

    signal = _number(wifi, "signal_percent")
    if signal is not None and signal < 40 and wifi.get("status") == "Connected":
        findings.append(_finding(
            "weak_wifi", "Weak wireless signal may contribute", "possible",
            f"Windows reported {signal:.0f}% wireless signal. Signal alone does not prove the cause of slow internet.",
            "Try moving closer to the router or comparing with an Ethernet connection."))
    elif signal is None and wifi.get("status") == "Connected (details unavailable)":
        facts.append("Wi-Fi signal is unavailable under Windows settings; no signal problem is assumed.")

    recent = []
    for item in samples if isinstance(samples, (tuple, list)) else ():
        if not isinstance(item, dict) or item.get("state") not in ("ok", "mixed", "failed"):
            continue
        if _recent(item.get("checked_at"), current, 60):
            recent.append(item)
    recent = recent[-120:]
    misses = sum(item["state"] != "ok" for item in recent)
    if len(recent) >= 6 and misses >= 2:
        findings.append(_finding(
            "recent_instability", "Some recent connection checks were inconsistent", "observed",
            f"{misses} of {len(recent)} recent checks had one or both public destinations fail. "
            "Saved history may be from a different network; this is not proof of an ISP outage.",
            "Run Stability while the problem occurs. Compare the time of failures with Wi-Fi and VPN changes."))
    elif len(recent) >= 6:
        facts.append(f"Both public destinations connected in {len(recent) - misses} of {len(recent)} recent history checks.")
    else:
        facts.append("There are fewer than six recent stability checks for correlation.")

    fresh_speed = isinstance(reading, dict) and _recent(reading.get("tested_at"), current, 120)
    if not fresh_speed:
        facts.append("Saved speed readings are missing or over two hours old; they are not used to identify a current issue.")
    else:
        download = _number(reading, "download_mbps")
        latency = _number(reading, "latency_ms")
        if download is not None and download < 3:
            findings.append(_finding(
                "limited_bandwidth", "Recent download bandwidth was limited", "observed",
                f"A short speed test measured {download:.1f} Mbps. This is below a typical single HD-stream reference, "
                "but does not identify the cause.",
                "Repeat the speed test once when other downloads are idle. Compare Wi-Fi and Ethernet if available."))
        if latency is not None and latency > 100:
            findings.append(_finding(
                "test_latency", "Delay to the speed-test network was elevated", "observed",
                f"The speed test measured {latency:.0f} ms idle response time to its test network, not to your game or call server.",
                "Compare response times at different times, and test the affected application directly."))

    fresh_load = isinstance(loaded, dict) and _recent(loaded.get("tested_at"), current, 15)
    if fresh_load and loaded.get("status") == "increase_observed":
        change = _number(loaded, "change_ms")
        if change is not None and change >= 40:
            findings.append(_finding(
                "load_delay", "Replies slowed during a download", "observed",
                f"The optional test observed a +{change:.0f} ms ICMP response-time increase while receiving data. "
                "This is not proof of bufferbloat or ISP congestion.",
                "Try the test again with other downloads stopped and compare Ethernet with Wi-Fi."))
    elif fresh_load and loaded.get("status") == "inconclusive":
        facts.append("The last under-download response check was inconclusive, not a failed-connection result.")

    if vpn.get("status") == "Possible tunnel route":
        findings.append(_finding(
            "tunnel_route", "Internet routing might use a tunnel", "possible",
            "The preferred route uses a VPN-style adapter. This does not prove all apps use a VPN.",
            "If an app is slow, compare its behavior with the VPN on and off, where safe and permitted."))
    elif vpn.get("status") == "VPN-style adapter present":
        facts.append("A virtual-network adapter is present, but not preferred for ordinary internet traffic.")

    if proxy.get("status") == "Configured":
        findings.append(_finding(
            "proxy_configured", "A proxy setting could affect some applications", "possible",
            "A proxy was configured; the check did not establish whether an affected application uses it.",
            "Check the application's proxy configuration if only certain services are affected."))

    if findings:
        headline = "Here's what stands out"
        summary = "These are measured clues and possible contributors—not a confirmed fault location."
    else:
        headline = "No clear cause identified yet"
        summary = "Basic checks may work even when a particular app or an intermittent connection has trouble."
        findings = [_finding(
            "needs_symptom", "Check during the problem", "next_check",
            "Current evidence does not isolate a fault in Wi-Fi, the router or the provider.",
            "Run Stability while symptoms occur, or run the optional response-under-load test for lag during downloads.")]

    order = {"observed": 0, "possible": 1, "next_check": 2}
    findings.sort(key=lambda x: (order[x["kind"]],
                                ["access_unverified", "partial_access", "recent_instability", "weak_wifi", "load_delay", "limited_bandwidth", "test_latency"].index(x["code"])
                                if x["code"] in ["access_unverified", "partial_access", "recent_instability", "weak_wifi", "load_delay", "limited_bandwidth", "test_latency"] else 99))
    return {
        "headline": headline, "summary": summary, "findings": findings[:4],
        "notes": facts[:5], "next_step": findings[0]["next_step"],
        "speed_fresh": bool(fresh_speed),
        "load_fresh": bool(fresh_load),
        "history_rounds": len(recent),
        "limitation": ("This is evidence-based guidance, not a definitive root-cause analysis. "
                       "Historical stability checks might refer to another connection. "
                       "No network settings were changed or new probes run."),
    }
