
"""Conservative activity insights from an existing speed test.

No internet requests, hidden speed tests, or synthetic quality scores.

Streaming reference: https://help.netflix.com/en/node/306
Video-call reference:
https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0066166
"""

from datetime import datetime, timedelta, timezone
import math


def _measurement(reading, key):
    value = reading.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def _item(key, title, status, tone, detail):
    return {
        "key": key,
        "title": title,
        "status": status,
        "tone": tone,
        "detail": detail,
    }


def evaluate_activities(reading=None, *, samples=(), now=None):
    """Interpret existing measurements without certifying application quality.

    Stability samples are independent TCP observations and may belong to
    a different network or monitoring session.
    """
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reading = reading if isinstance(reading, dict) else {}

    downloaded = _measurement(reading, "download_mbps")
    uploaded = _measurement(reading, "upload_mbps")
    latency = _measurement(reading, "latency_ms")
    jitter = _measurement(reading, "jitter_ms")

    observed_at = _time(reading.get("tested_at"))
    age = (current - observed_at).total_seconds() if observed_at else None
    stale = age is None or age > 2 * 3600 or age < -300

    if downloaded is None:
        streaming = _item(
            "streaming", "Video streaming", "Speed test needed", "neutral",
            "Run a speed test to compare download bandwidth with common "
            "streaming guidance.",
        )
    elif downloaded >= 15:
        streaming = _item(
            "streaming", "Video streaming", "4K bandwidth reference met",
            "positive",
            "Measured download meets Netflix's 15 Mbps 4K recommendation "
            "for one stream. Buffering and other services were not tested.",
        )
    elif downloaded >= 5:
        streaming = _item(
            "streaming", "Video streaming", "Full HD reference met",
            "positive",
            "Measured download meets Netflix's 5 Mbps Full HD reference, "
            "but not its 15 Mbps 4K recommendation.",
        )
    elif downloaded >= 3:
        streaming = _item(
            "streaming", "Video streaming", "HD reference met", "neutral",
            "Measured download meets Netflix's 3 Mbps HD reference, "
            "but not its 5 Mbps Full HD reference.",
        )
    else:
        streaming = _item(
            "streaming", "Video streaming", "HD may struggle", "caution",
            "Measured download is below Netflix's 3 Mbps HD reference. "
            "Lower resolution may help.",
        )

    if downloaded is None or uploaded is None:
        calls = _item(
            "calls", "Video calls", "Upload and download needed", "neutral",
            "An upload and download test is needed to compare with "
            "HD video-call bandwidth references.",
        )
    elif uploaded >= 3.8 and downloaded >= 3.0:
        calls = _item(
            "calls", "Video calls", "1080p bandwidth reference met",
            "positive",
            "Upload and download meet Zoom's 1080p reference "
            "(3.8 up, 3.0 down Mbps). Call stability and the meeting "
            "service were not tested.",
        )
    elif uploaded >= 2.6 and downloaded >= 1.8:
        calls = _item(
            "calls", "Video calls", "Group HD reference met", "positive",
            "Upload and download meet Zoom's 720p group-call reference "
            "(2.6 up, 1.8 down Mbps). Stability still matters.",
        )
    elif uploaded >= 1.2 and downloaded >= 1.2:
        calls = _item(
            "calls", "Video calls", "One-to-one HD reference met", "neutral",
            "Bandwidth meets Zoom's 1:1 720p reference of 1.2 Mbps "
            "in each direction; group HD may need more.",
        )
    else:
        calls = _item(
            "calls", "Video calls", "HD calls may struggle", "caution",
            "One or both measured directions fall below Zoom's 1:1 "
            "720p reference. Try lower video quality.",
        )

    if latency is None:
        gaming = _item(
            "gaming", "Online gaming", "Game latency not measured", "neutral",
            "A speed test with latency is needed. Game-server ping "
            "and packet loss remain untested.",
        )
    elif latency > 100:
        gaming = _item(
            "gaming", "Online gaming", "Delay could be noticeable", "caution",
            f"Idle latency was {latency:.0f} ms to the speed-test network. "
            "Your game's server may have very different latency; "
            "no game-server test was performed.",
        )
    else:
        gaming = _item(
            "gaming", "Online gaming", "Game-server test still needed",
            "neutral",
            f"Idle latency was {latency:.0f} ms to the speed-test network. "
            "This cannot predict game-server ping, loaded latency "
            "or packet loss.",
        )

    if downloaded is None:
        browsing = _item(
            "browsing", "Web browsing", "Speed test needed", "neutral",
            "Bandwidth has not been measured. The basic connection check "
            "is separate from page-load speed.",
        )
    elif downloaded < 1:
        browsing = _item(
            "browsing", "Web browsing", "Limited bandwidth measured",
            "caution",
            "Download measured under 1 Mbps. Pages with large content "
            "may be slow; actual websites were not timed.",
        )
    else:
        browsing = _item(
            "browsing", "Web browsing", "Page loads not tested", "neutral",
            "Download bandwidth was measured, but NetDoctor has not "
            "timed actual websites or application requests.",
        )

    recent = []
    for sample in samples or ():
        if (
            not isinstance(sample, dict)
            or sample.get("state") not in {"ok", "mixed", "failed"}
        ):
            continue

        when = _time(sample.get("checked_at"))
        if when and timedelta(0) <= current - when <= timedelta(hours=1):
            recent.append(sample)

    recent = recent[-120:]
    interruptions = sum(s["state"] != "ok" for s in recent)

    if len(recent) >= 6:
        stability = {
            "status": (
                f"{len(recent) - interruptions} of {len(recent)} recent "
                "connection rounds succeeded at both destinations"
            ),
            "detail": (
                (
                    "Some recent TCP checks were mixed or failed; "
                    "this does not prove a general outage. "
                    if interruptions else
                    "No unsuccessful TCP rounds were recorded "
                    "in this recent sample. "
                )
                + "These checks may be from a different network or session, "
                "and do not measure game or call stability."
            ),
            "observed": len(recent),
            "mixed_or_failed": interruptions,
        }
    else:
        stability = {
            "status": "Not enough recent checks",
            "detail": (
                "Use the Stability tab for a longer observation. "
                "Previous connection history may belong to a different network."
            ),
            "observed": len(recent),
            "mixed_or_failed": interruptions,
        }

    freshness = (
        "No completed speed-test timestamp is available."
        if age is None else
        "This reading appears to be in the future; check the computer clock."
        if age < -300 else
        "This speed reading is over two hours old and may describe "
        "a different network."
        if age > 2 * 3600 else
        "These are short measurements to a test network, "
        "not guarantees for individual apps."
    )

    if jitter is not None and jitter > 30:
        freshness += (
            " Measured idle jitter was elevated; "
            "consider retesting during a call or game."
        )

    return {
        "tested_at": observed_at.isoformat() if observed_at else None,
        "stale": stale,
        "note": freshness,
        "activities": [streaming, calls, gaming, browsing],
        "stability": stability,
        "source_urls": [
            "https://help.netflix.com/en/node/306",
            "https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0066166",
        ],
    }
