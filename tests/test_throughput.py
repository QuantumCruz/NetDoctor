
"""Bounded opt-in download checks without any external traffic."""
import json
import socket
import urllib.error

import pytest

from netdoctor.throughput import DownloadConfigError, measure_download

MIB = 1_048_576


class Stream:
    def __init__(self, length=MIB, *, declared=True, status=200, encoding="identity", error=None):
        self.remaining = length
        self.status = status
        self.headers = {"Content-Encoding": encoding}
        if declared:
            self.headers["Content-Length"] = str(length)
        self.error = error
        self.closed = False
        self.read_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, count):
        self.read_calls += 1
        if self.error is not None:
            raise self.error
        size = min(count, self.remaining)
        self.remaining -= size
        return b"z" * size


def clock(step=0.025):
    value = [-step]
    def tick():
        value[0] += step
        return value[0]
    return tick


def test_complete_download_reports_exact_bytes_and_rate():
    stream = Stream()
    calls = []
    def open_stream(url, timeout):
        calls.append((url, timeout))
        return stream
    report = measure_download(size_mib=1, opener=open_stream, clock=clock())
    assert report.status == "completed"
    assert report.received_bytes == report.requested_bytes == MIB
    assert report.average_mbps > 0
    assert report.first_byte_ms is not None
    assert stream.closed
    assert calls == [(f"https://speed.cloudflare.com/__down?bytes={MIB}", 5.0)]
    assert json.loads(json.dumps(report.to_dict()))["status"] == "completed"


def test_short_sample_is_qualified_not_false_connection_rating():
    report = measure_download(size_mib=1, opener=lambda *_: Stream(), clock=clock(0.0001))
    assert report.quality == "short_sample"
    assert "too quickly" in report.findings[0].title


def test_short_body_is_incomplete_and_has_no_rate():
    report = measure_download(size_mib=1, opener=lambda *_: Stream(length=100, declared=False), clock=clock())
    assert report.status == "incomplete"
    assert report.received_bytes == 100
    assert report.average_mbps is None


def test_wrong_content_length_does_not_download():
    stream = Stream(length=2*MIB)
    report = measure_download(size_mib=1, opener=lambda *_: stream, clock=clock())
    assert report.status == "unavailable"
    assert stream.read_calls == 0


def test_response_compression_not_accepted():
    stream = Stream(encoding="gzip")
    report = measure_download(size_mib=1, opener=lambda *_: stream, clock=clock())
    assert report.status == "unavailable"
    assert stream.read_calls == 0


def test_http_error_does_not_crash():
    def open_stream(url, timeout):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
    report = measure_download(size_mib=1, opener=open_stream, clock=clock())
    assert report.status == "unavailable"
    assert "403" in report.explanation


def test_urllib_error_does_not_crash():
    def open_stream(url, timeout):
        raise urllib.error.URLError("network down")
    report = measure_download(size_mib=1, opener=open_stream, clock=clock())
    assert report.status == "unavailable"


def test_timeout_preserves_partial_bytes():
    stream = Stream(error=socket.timeout("no bytes"))
    report = measure_download(size_mib=1, opener=lambda *_: stream, clock=clock())
    assert report.status == "timeout"
    assert report.average_mbps is None


def test_streaming_budget_is_enforced():
    stream = Stream()
    report = measure_download(size_mib=1, opener=lambda *_: stream, clock=clock(1.0))
    assert report.status == "incomplete"
    assert report.received_bytes < MIB
    assert "15-second" in report.explanation


@pytest.mark.parametrize("size", [0, 3, 9, -1, 1.0, True])
def test_reject_unsupported_download_size(size):
    with pytest.raises(DownloadConfigError):
        measure_download(size_mib=size, opener=lambda *_: (_ for _ in ()).throw(AssertionError()))


@pytest.mark.parametrize("timeout", [0, 11, float("nan"), float("inf"), -1])
def test_reject_bad_timeouts(timeout):
    with pytest.raises(DownloadConfigError):
        measure_download(timeout=timeout, opener=lambda *_: (_ for _ in ()).throw(AssertionError()))
