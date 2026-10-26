
"""Stage 16: bandwidth references are not application quality scores."""

from datetime import datetime, timedelta, timezone

from netdoctor.activity_quality import evaluate_activities


NOW = datetime(2026, 10, 24, 11, tzinfo=timezone.utc)


def report(download=35.7, upload=21.7, latency=135, jitter=5, when=None):
    return {
        "tested_at": (when or NOW).isoformat(),
        "download_mbps": download,
        "upload_mbps": upload,
        "latency_ms": latency,
        "jitter_ms": jitter,
    }


def insight(result, key):
    return next(
        item for item in result["activities"] if item["key"] == key
    )


def test_realistic_reading_streaming_meets_example_but_gaming_has_caveat():
    result = evaluate_activities(report(), now=NOW)

    assert "4K" in insight(result, "streaming")["status"]
    assert insight(result, "gaming")["tone"] == "caution"
    assert "game's server" in insight(result, "gaming")["detail"]


def test_720p_group_call_reference_up_and_down():
    result = evaluate_activities(
        report(download=1.9, upload=2.7),
        now=NOW,
    )

    assert insight(result, "calls")["status"] == "Group HD reference met"


def test_low_upload_prevents_hd_call_claim():
    result = evaluate_activities(
        report(download=100, upload=0.3),
        now=NOW,
    )

    assert insight(result, "calls")["tone"] == "caution"


def test_1080p_reference_requires_correct_directions():
    good = evaluate_activities(
        report(download=3.2, upload=3.9),
        now=NOW,
    )
    insufficient = evaluate_activities(
        report(download=3.9, upload=3.2),
        now=NOW,
    )

    assert "1080p" in insight(good, "calls")["status"]
    assert "1080p" not in insight(insufficient, "calls")["status"]


def test_missing_speed_is_not_synthetic_green():
    result = evaluate_activities(None, now=NOW)

    assert all(
        item["tone"] == "neutral"
        for item in result["activities"]
    )
    assert result["stale"]


def test_outdated_reading_disclosed():
    result = evaluate_activities(
        report(when=NOW - timedelta(days=1)),
        now=NOW,
    )

    assert result["stale"]
    assert "over two hours" in result["note"]


def test_future_clock_disclosed():
    result = evaluate_activities(
        report(when=NOW + timedelta(hours=2)),
        now=NOW,
    )

    assert result["stale"]
    assert "future" in result["note"]


def test_older_history_not_mixed_with_current_sample():
    sample = {
        "checked_at": (NOW - timedelta(days=1)).isoformat(),
        "state": "failed",
    }

    result = evaluate_activities(
        report(),
        samples=[sample],
        now=NOW,
    )

    assert result["stability"]["observed"] == 0


def test_recent_tcp_history_reassurance_is_qualified():
    samples = [
        {
            "checked_at": (
                NOW - timedelta(seconds=i * 10)
            ).isoformat(),
            "state": "ok",
        }
        for i in range(6)
    ]

    result = evaluate_activities(
        report(),
        samples=samples,
        now=NOW,
    )

    assert "6 of 6" in result["stability"]["status"]
    assert "different network" in result["stability"]["detail"]


def test_recent_mixed_checks_are_not_isp_diagnosis():
    samples = [
        {
            "checked_at": NOW.isoformat(),
            "state": "mixed",
        }
    ] * 6

    result = evaluate_activities(
        report(),
        samples=samples,
        now=NOW,
    )

    assert result["stability"]["mixed_or_failed"] == 6
    assert "does not prove" in result["stability"]["detail"]


def test_invalid_numeric_and_timestamps_do_not_crash():
    result = evaluate_activities(
        {
            "download_mbps": float("nan"),
            "upload_mbps": True,
            "latency_ms": -1,
            "tested_at": "invalid",
        },
        now=NOW,
    )

    assert insight(result, "streaming")["status"] == "Speed test needed"
    assert insight(result, "gaming")["tone"] == "neutral"
