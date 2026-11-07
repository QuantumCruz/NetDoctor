"""Interpret one user-started NetDoctor doctor run and optional website check.

This module does not make network requests. It preserves the distinction
between observations and possible explanations, especially for ICMP/DNS.
"""

from datetime import datetime, timezone


def _step(key, title, status, evidence, next_step):
    return {
        "key": key,
        "title": title,
        "status": status,
        "evidence": evidence,
        "next_step": next_step,
    }


def interpret_guided(snapshot, doctor, website=None) -> dict:
    """Turn existing independent checks into a cautious, actionable flow."""
    active = [item for item in snapshot.adapters if item.is_up]
    route = snapshot.preferred_route("IPv4") or snapshot.preferred_route("IPv6")
    steps = []

    gateway = None
    latency = getattr(doctor, "latency", None)
    if latency is not None:
        gateway = next(
            (item for item in latency.targets if item.role == "gateway"),
            None,
        )

    if not active:
        local = _step(
            "local", "No active adapter was reported", "attention",
            "Windows did not report an active network interface in this snapshot.",
            "Connect Wi-Fi or Ethernet and repeat the diagnosis.",
        )
    elif route is None:
        local = _step(
            "local", "Local route was not verified", "inconclusive",
            "Windows reported an active adapter but no usable default route. "
            "Routing information may be incomplete.",
            "Check the active connection and Windows gateway settings.",
        )
    else:
        evidence = (
            f"Windows reported an active adapter and a usable {route.family} "
            "default route. This does not by itself prove the router is reachable."
        )
        if gateway is not None:
            if gateway.replies > 0:
                evidence += (
                    f" The gateway replied to {gateway.replies}/{gateway.sent} "
                    "ICMP echo requests."
                )
            else:
                evidence += (
                    " The gateway did not answer the short ICMP sample; "
                    "some routers block or limit echo replies."
                )
        local = _step(
            "local", "Local routing information is present", "confirmed",
            evidence,
            "If problems persist, compare another device on this Wi-Fi or Ethernet network.",
        )
    steps.append(local)

    dns = getattr(doctor, "dns", None)
    observations = tuple(getattr(dns, "observations", ()) or ())
    successful_dns = sum(item.status == "answered" for item in observations)

    if successful_dns:
        dns_step = _step(
            "dns", "Direct DNS queries returned addresses", "confirmed",
            f"{successful_dns}/{len(observations)} direct UDP DNS A-record queries "
            "returned addresses. Windows applications may resolve names differently.",
            "If a single website fails, investigate that hostname rather than changing DNS immediately.",
        )
    elif observations:
        dns_step = _step(
            "dns", "Direct DNS check was inconclusive", "inconclusive",
            f"None of {len(observations)} direct UDP DNS queries returned an A record. "
            "Filtering, resolver policy or an actual lookup problem could explain this.",
            "Compare with browser access and the external connectivity results before changing DNS.",
        )
    else:
        dns_step = _step(
            "dns", "Direct DNS check was unavailable", "not_tested",
            "No validated direct IPv4 DNS query was available. This is not proof of DNS failure.",
            "Review DNS configuration if website names fail to resolve.",
        )
    steps.append(dns_step)

    checks = tuple(getattr(doctor.connectivity, "checks", ()) or ())
    connected = sum(bool(check.tcp_ok) for check in checks)

    if not checks:
        internet = _step(
            "internet", "External connectivity was not measured", "not_tested",
            "No public HTTPS TCP endpoint results were recorded.",
            "Repeat the quick connection check.",
        )
    elif connected == len(checks):
        internet = _step(
            "internet", "Basic public HTTPS transport succeeded", "confirmed",
            f"{connected}/{len(checks)} independent public endpoints accepted a "
            "TCP connection on port 443. This does not measure download speed.",
            "If one service is still slow, test that destination specifically.",
        )
    elif connected:
        internet = _step(
            "internet", "External connectivity varied by destination", "mixed",
            f"{connected}/{len(checks)} public endpoints accepted a TCP connection. "
            "The difference may be temporary or destination-specific.",
            "Repeat the test and compare from another network if it persists.",
        )
    else:
        internet = _step(
            "internet", "Public HTTPS connectivity was not confirmed", "inconclusive",
            f"0/{len(checks)} tested public endpoints accepted a TCP connection. "
            "DNS, routing, filtering and endpoint behavior remain possible explanations.",
            "Try an ordinary website and compare with another device or connection.",
        )
    steps.append(internet)

    if website is None:
        website_step = _step(
            "website", "Specific website not tested", "not_tested",
            "No website was selected; the guided diagnosis did not make a targeted HEAD request.",
            "Enter an HTTPS website above if only one service is slow or unreachable.",
        )
    elif website.get("status") == "responded":
        code = website.get("http_status")
        if isinstance(code, int) and 200 <= code < 400:
            status = "confirmed"
            headline = "Selected website responded over HTTPS"
        else:
            status = "mixed"
            headline = "Selected website replied but reported a restriction or error"

        website_step = _step(
            "website", headline, status,
            f"{website.get('headline', 'An HTTP service responded')}. "
            "A HEAD response does not measure file transfer speed or redirected asset hosts.",
            website.get("next_step", "Compare the same site in a browser."),
        )
    else:
        website_step = _step(
            "website", "Selected website check was inconclusive", "inconclusive",
            website.get("explanation", "The targeted HTTPS HEAD request did not finish."),
            website.get("next_step", "Repeat the site check using another connection."),
        )
    steps.append(website_step)

    if not active:
        headline = "Start with the local connection"
        summary = "No active adapter was reported. This snapshot cannot establish the internet fault."
        next_step = local["next_step"]
    elif internet["status"] == "confirmed" and website_step["status"] == "confirmed":
        headline = "General HTTPS and the selected website responded"
        summary = "The tested connections worked at this moment, but this does not rule out slow downloads or intermittent faults."
        next_step = "If the problem is download speed, compare a bounded download to the actual asset host."
    elif internet["status"] == "confirmed" and website_step["status"] in ("mixed", "inconclusive"):
        headline = "General connectivity works; the selected website needs investigation"
        summary = "Public HTTPS TCP checks succeeded, while the website response had a restriction, error or incomplete stage."
        next_step = website_step["next_step"]
    elif website_step["status"] == "confirmed":
        headline = "The selected website responded despite other uncertain checks"
        summary = "A successful website response shows this path worked; failures to other endpoints do not establish a universal outage."
        next_step = "Repeat the unsuccessful checks and compare with normal browsing."
    elif internet["status"] == "mixed":
        headline = "Connection behavior differs by destination"
        summary = "Only some public endpoints accepted TCP connections. One observation cannot identify the responsible network."
        next_step = internet["next_step"]
    elif internet["status"] == "inconclusive":
        headline = "Internet reachability remains unverified"
        summary = "The tested public TCP endpoints did not connect. This alone does not prove an ISP outage."
        next_step = internet["next_step"]
    else:
        headline = "No broad connection problem was confirmed"
        summary = "Review each stage below for observations, unavailable tests and suggested actions."
        next_step = internet["next_step"]

    return {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "headline": headline,
        "summary": summary,
        "next_step": next_step,
        "steps": steps,
        "website": website,
        "limitation": (
            "A short, user-triggered snapshot. ICMP nonresponses do not prove "
            "gateway failure; direct UDP DNS checks differ from Windows DNS policy. "
            "TCP success is not an internet speed measurement. Website HEAD "
            "requests do not download content or follow redirects."
        ),
    }