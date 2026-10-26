
"""Presentation tests: no synthetic quality scores and no network requests."""

from datetime import datetime, timezone

import pytest

from netdoctor.icmp import EchoResult
from netdoctor.loaded import LoadProbe, LoadedReport, _interpret
from netdoctor.load_insights import summarize_loaded
from netdoctor.throughput import DownloadReport

NOW = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)


def report(idle=10, loaded=70, *, window=1200, download_status="completed"):
    download = DownloadReport(
        download_status, "preliminary", "test provider", 4 * 1048576,
        4 * 1048576 if download_status == "completed" else 0,
        window + 120, 120, 30.0, "sample", (),
    )
    return _interpret(
        "8.8.8.8", tuple(EchoResult("reply", idle, "ok") for _ in range(4)),
        tuple(LoadProbe("reply", loaded, True, "ok") for _ in range(5)),
        download, window,
    )


def test_observed_increase_is_caution_not_isp_accusation():
    result = summarize_loaded(report(), now=NOW)
    assert result["tone"] == "caution"
    assert result["status"] == "increase_observed"
    assert result["change_ms"] == 60
    assert "does not identify" in result["explanation"]
    assert result["received_mib"] == 4


def test_no_increase_is_neutral_not_guarantee():
    result = summarize_loaded(report(10, 13), now=NOW)
    assert result["status"] == "no_clear_increase"
    assert result["tone"] == "neutral"
    assert "upload-heavy" in result["explanation"]


def test_inconclusive_never_shown_as_failure():
    result = summarize_loaded(report(window=300), now=NOW)
    assert result["status"] == "inconclusive"
    assert result["tone"] == "neutral"
    assert "not a failed internet test" in result["explanation"]


def test_failed_download_shows_zero_and_inconclusive():
    result = summarize_loaded(report(download_status="timeout"), now=NOW)
    assert result["status"] == "inconclusive"
    assert result["received_mib"] == 0
    assert result["download_status"] == "timeout"


def test_timestamp_is_tz_aware():
    assert summarize_loaded(report(), now=NOW)["tested_at"].endswith("+00:00")
    with pytest.raises(ValueError):
        summarize_loaded(report(), now=NOW.replace(tzinfo=None))


def test_unsupported_status_rejected():
    import dataclasses
    with pytest.raises(ValueError):
        summarize_loaded(dataclasses.replace(report(), status="fake"), now=NOW)
