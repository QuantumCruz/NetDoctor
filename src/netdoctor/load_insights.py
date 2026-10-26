
"""Plain-language presentation of NetDoctor's existing loaded-latency test.

This module makes no network requests. A result is always a short ICMP
comparison during one bounded download, not an app-quality or bufferbloat score.
"""

from datetime import datetime, timezone

from netdoctor.loaded import LoadedReport


def summarize_loaded(report: LoadedReport, *, now=None) -> dict:
    """Summarize measured evidence; preserve inconclusive results as such."""
    if not isinstance(report, LoadedReport):
        raise ValueError("The loaded latency engine returned an invalid result.")

    if report.status == "increase_observed":
        heading = "Response time increased during the download"
        tone = "caution"
        explanation = (
            "Replies to the test destination became slower while a small "
            "download was in progress. This can make interactive use feel "
            "less responsive, but does not identify the router, ISP or cause."
        )
        next_step = (
            "Repeat when you notice lag. Compare with and without other "
            "downloads, and try Ethernet instead of Wi-Fi if available."
        )
    elif report.status == "no_clear_increase":
        heading = "No large response-time increase was observed"
        tone = "neutral"
        explanation = (
            "This short download did not produce a clear latency increase "
            "to the test destination. Longer or upload-heavy traffic may "
            "behave differently."
        )
        next_step = (
            "If games or calls still lag, test during the problem. "
            "A real game server or call can use a different route."
        )
    elif report.status == "inconclusive":
        heading = "Not enough evidence for a loaded-latency result"
        tone = "neutral"
        explanation = (
            "The download or overlapping ping replies did not provide "
            "enough reliable measurements. This is not a failed internet test."
        )
        next_step = (
            "Try again on the same connection later. A very fast download "
            "or blocked ping replies can make this test inconclusive."
        )
    else:
        raise ValueError("The loaded latency engine returned an unknown status.")

    checked = now or datetime.now(timezone.utc)
    if checked.tzinfo is None:
        raise ValueError("The result timestamp must have a timezone.")

    return {
        "tested_at": checked.astimezone(timezone.utc).isoformat(),
        "status": report.status,
        "tone": tone,
        "headline": heading,
        "explanation": explanation,
        "next_step": next_step,
        "idle_ms": report.idle_median_ms,
        "during_download_ms": report.loaded_median_ms,
        "change_ms": report.increase_ms,
        "loaded_replies": report.loaded_replies,
        "received_mib": round(report.download.received_bytes / 1_048_576, 2),
        "download_status": report.download.status,
        "limitation": (
            "Only a 4 MiB download and ICMP replies were compared. "
            "This did not measure upload-loaded latency, game-server ping, "
            "application packet loss or bufferbloat conclusively."
        ),
    }
