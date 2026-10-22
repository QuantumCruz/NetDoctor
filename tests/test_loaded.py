
"""Loaded latency uses only data-transfer-overlapping echo replies."""

import json
import time

import pytest

from netdoctor.icmp import EchoResult, ProbeError
from netdoctor.loaded import LoadedError, LoadProbe, _interpret, measure_loaded
from netdoctor.throughput import DownloadReport


def _echo(ms=10):
    return EchoResult("reply", float(ms), "ok")


def _download(*, status="completed", quality="preliminary", first_byte=100, elapsed=1000):
    return DownloadReport(
        status, quality, "Cloudflare", 4194304,
        4194304 if status == "completed" else 0,
        elapsed, first_byte, 8.0, "observed", ()
    )


def _during(ms, *, overlap=True):
    return LoadProbe("reply", float(ms), overlap, "ok")


def test_observed_increase_uses_only_overlapping_replies():
    result = _interpret(
        "8.8.8.8",
        tuple(_echo(10) for _ in range(4)),
        (_during(900, overlap=False), _during(60), _during(62), _during(64)),
        _download(), 900
    )
    assert result.status == "increase_observed"
    assert result.loaded_median_ms == 62
    assert result.increase_ms == 52
    assert result.loaded_replies == 3
    assert "ICMP" in result.findings[0].title


def test_no_clear_increase_is_not_a_perfect_network_rating():
    result = _interpret(
        "8.8.8.8",
        tuple(_echo(10) for _ in range(4)),
        tuple(_during(14) for _ in range(4)),
        _download(), 900
    )
    assert result.status == "no_clear_increase"
    assert "does not rule out" in result.findings[0].explanation


def test_fast_transfer_is_inconclusive_even_if_icmp_samples_exist():
    result = _interpret(
        "8.8.8.8",
        tuple(_echo(10) for _ in range(4)),
        tuple(_during(60) for _ in range(4)),
        _download(elapsed=300), 200
    )
    assert result.status == "inconclusive"


def test_failed_download_is_inconclusive_even_with_high_latency():
    result = _interpret(
        "8.8.8.8",
        tuple(_echo(10) for _ in range(4)),
        tuple(_during(100) for _ in range(4)),
        _download(status="timeout"), 900
    )
    assert result.status == "inconclusive"
    assert "timeout" in result.findings[0].explanation


def test_packet_nonresponse_is_not_a_latency_value():
    result = _interpret(
        "8.8.8.8",
        tuple(_echo(10) for _ in range(4)),
        (
            LoadProbe("timeout", None, True, "blocked"),
            _during(99),
            LoadProbe("timeout", None, True, "blocked")
        ),
        _download(), 900
    )
    assert result.status == "inconclusive"
    assert result.loaded_replies == 1


def test_not_enough_baseline_replies_is_inconclusive():
    result = _interpret(
        "8.8.8.8",
        (_echo(1), EchoResult("timeout", None, "no")),
        tuple(_during(90) for _ in range(4)),
        _download(), 900
    )
    assert result.status == "inconclusive"


@pytest.mark.parametrize("target,size,timeout", [
    ("invalid", 4, 10),
    ("::1", 4, 10),
    ("224.0.0.1", 4, 10),
    ("8.8.8.8", 3, 10),
    ("8.8.8.8", 8, 11),
    ("8.8.8.8", 4, float("nan")),
])
def test_invalid_input_does_not_start_download(target, size, timeout):
    with pytest.raises(LoadedError):
        measure_loaded(
            target=target,
            size_mib=size,
            timeout=timeout,
            downloader=lambda **kw: (_ for _ in ()).throw(AssertionError("download called"))
        )


def test_threaded_probe_overlaps_real_fake_download_and_json_serializes():
    timeline = []

    def fake_transfer(*, size_mib, timeout):
        timeline.append("transfer")
        time.sleep(.9)
        return _download(elapsed=900, first_byte=100)

    def fake_probe(address, *, timeout_ms):
        time.sleep(.01)
        return _echo(15)

    report = measure_loaded(probe=fake_probe, downloader=fake_transfer)
    assert report.status == "no_clear_increase"
    assert report.loaded_replies >= 3
    assert timeline == ["transfer"]
    assert json.loads(json.dumps(report.to_dict()))["download"]["status"] == "completed"


def test_worker_failure_is_friendly_exception():
    def crash(**kwargs):
        raise RuntimeError("unavailable")

    with pytest.raises(LoadedError, match="worker"):
        measure_loaded(
            probe=lambda *_args, **_kwargs: _echo(),
            downloader=crash,
            sleep=lambda _: None
        )


def test_baseline_probe_error_prevents_download():
    def crash(*_args, **_kwargs):
        raise ProbeError("cannot ping")

    with pytest.raises(ProbeError):
        measure_loaded(
            probe=crash,
            downloader=lambda **_: (_ for _ in ()).throw(AssertionError())
        )
