
"""Guided troubleshooting tests; no internet traffic or real delay."""

import threading
from types import SimpleNamespace

import pytest

from netdoctor.checks import TEST_HOSTS
from netdoctor.icmp import EchoResult
from netdoctor.models import EndpointCheck
from netdoctor.troubleshoot import (
    GuidanceInputError,
    GuidedResult,
    GuidedWorker,
    _website_host,
    check_drops,
    check_slow,
    check_website,
)


def endpoint(
    host,
    *,
    timeout,
    success=True,
    dns=True,
):
    return EndpointCheck(
        host,
        dns,
        success,
        "simulated",
    )


def loaded_sample(status="no_clear_increase"):
    return SimpleNamespace(
        status=status,
        increase_ms=(
            60 if status == "increase_observed" else 4
        ),
        idle_median_ms=20.0,
        loaded_median_ms=(
            80.0 if status == "increase_observed" else 24.0
        ),
        download=SimpleNamespace(
            received_bytes=(
                4194304 if status != "inconclusive" else 0
            ),
            status=(
                "completed" if status != "inconclusive"
                else "timeout"
            ),
        ),
    )


def snapshot(route="192.168.1.1"):
    return SimpleNamespace(
        preferred_route=lambda family: (
            SimpleNamespace(next_hop=route)
            if route else None
        )
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("example.com", "example.com"),
        ("https://Example.COM/a?x=1", "example.com"),
        ("https://example.com:443/path", "example.com"),
        ("bücher.de", "xn--bcher-kva.de"),
    ],
)
def test_https_site_parsing_hides_url_paths(
    raw,
    expected,
):
    assert _website_host(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "http://example.com",
        "https://example.com:8080",
        "https://user:password@example.com",
        "https://localhost",
        "127.0.0.1",
        "example..com",
        "https://bad space.com",
    ],
)
def test_invalid_or_unsupported_website_is_rejected(raw):
    with pytest.raises(GuidanceInputError):
        _website_host(raw)


def test_site_connection_succeeds_but_page_load_not_claimed():
    called = []

    def check(host, *, timeout):
        called.append(host)
        return endpoint(
            host,
            timeout=timeout,
        )

    report = check_website(
        "https://example.com/sensitive-path",
        endpoint=check,
    )

    assert called == [
        "example.com",
        TEST_HOSTS[0],
    ]
    assert "accepted a connection" in report.headline
    assert "page or app might still fail" in report.explanation
    assert "did not download" in report.note
    assert not any(
        "sensitive" in item
        for item in report.evidence
    )


def test_site_dns_failure_and_working_comparison_is_qualified():
    def check(host, *, timeout):
        return endpoint(
            host,
            timeout=timeout,
            success=host != "missing.example",
            dns=host != "missing.example",
        )

    report = check_website(
        "missing.example",
        endpoint=check,
    )

    assert "couldn't find" in report.headline
    assert (
        "don't" not in report.explanation
        or "site-specific" in report.explanation
    )
    assert "Avoid changing" in report.next_step


def test_site_port_failure_with_working_comparison():
    report = check_website(
        "example.com",
        endpoint=lambda host, *, timeout: endpoint(
            host,
            timeout=timeout,
            success=host != "example.com",
        ),
    )

    assert "did not accept" in report.headline
    assert "which network" in report.next_step


def test_both_sites_fail_is_not_classified_as_certain_outage():
    report = check_website(
        "example.com",
        endpoint=lambda host, *, timeout: endpoint(
            host,
            timeout=timeout,
            success=False,
        ),
    )

    assert "either" in report.headline
    assert "enough evidence" in report.explanation


def test_slow_sends_one_four_mib_request_only():
    calls = []

    report = check_slow(
        loaded_test=lambda **kwargs: (
            calls.append(kwargs),
            loaded_sample(),
        )[1]
    )

    assert len(calls) == 1
    assert calls[0]["size_mib"] == 4
    assert calls[0]["timeout"] == 10.0
    assert "No clear" in report.headline
    assert "plan speed" in report.note


def test_slow_increase_not_attributed_to_isp():
    report = check_slow(
        loaded_test=lambda **_: loaded_sample(
            "increase_observed"
        )
    )

    assert "increased" in report.headline
    assert "60 ms" in report.explanation
    assert "doesn't establish why" in report.explanation


def test_inconclusive_download_has_no_speed_diagnosis():
    report = check_slow(
        loaded_test=lambda **_: loaded_sample(
            "inconclusive"
        )
    )

    assert "couldn't establish" in report.headline


def test_short_monitor_with_all_connections_working():
    calls = []

    def check(host, *, timeout):
        calls.append(host)
        return endpoint(
            host,
            timeout=timeout,
        )

    report = check_drops(
        collector=snapshot,
        endpoint=check,
        ping=lambda *args, **kwargs: EchoResult(
            "reply",
            4.0,
            "yes",
        ),
        rounds=3,
        interval=0,
    )

    assert len(calls) == 3 * len(TEST_HOSTS)
    assert "No disconnections observed" in report.headline
    assert "doesn't rule out" in report.explanation


def test_drop_watch_detects_a_full_round_without_connectivity():
    calls = [0]

    def check(host, *, timeout):
        round_number = calls[0] // len(TEST_HOSTS)
        calls[0] += 1

        return endpoint(
            host,
            timeout=timeout,
            success=round_number != 1,
        )

    report = check_drops(
        collector=snapshot,
        endpoint=check,
        rounds=3,
        interval=0,
        ping=lambda *a, **kw: EchoResult(
            "timeout",
            None,
            "ignored",
        ),
    )

    assert "interruptions were observed" in report.headline
    assert "does not identify" in report.explanation


def test_single_site_failures_not_called_a_network_wide_drop():
    report = check_drops(
        collector=snapshot,
        rounds=3,
        interval=0,
        endpoint=lambda host, *, timeout: endpoint(
            host,
            timeout=timeout,
            success=host == TEST_HOSTS[0],
        ),
    )

    assert "One public test destination" in report.headline
    assert "network-wide" in report.next_step


def test_all_failed_samples_not_declared_certain_internet_outage():
    report = check_drops(
        collector=snapshot,
        rounds=2,
        interval=0,
        endpoint=lambda host, *, timeout: endpoint(
            host,
            timeout=timeout,
            success=False,
        ),
    )

    assert "weren't confirmed" in report.headline
    assert "could" in report.explanation.lower()


def test_router_ping_failure_does_not_cancel_public_testing():
    def crash(*args, **kwargs):
        raise RuntimeError("wrong exception")

    # Known ICMP errors are ignorable.
    # Other exceptions fail the worker safely.
    report = check_drops(
        collector=lambda: snapshot(None),
        rounds=2,
        interval=0,
        endpoint=lambda host, *, timeout: endpoint(
            host,
            timeout=timeout,
        ),
        ping=crash,
    )

    assert "not available" in report.evidence[-1]


def test_cancelled_monitor_reports_partial_result():
    cancel = threading.Event()

    def check(host, *, timeout):
        cancel.set()
        return endpoint(
            host,
            timeout=timeout,
        )

    report = check_drops(
        collector=snapshot,
        endpoint=check,
        cancel=cancel,
        rounds=4,
        interval=0,
    )

    assert "stopped" in report.headline
    assert "partial" in report.explanation


def test_worker_validates_url_before_launching_thread():
    worker = GuidedWorker()

    with pytest.raises(GuidanceInputError):
        worker.start(
            "website",
            website="http://example.com",
        )

    assert not worker.running


def test_worker_progress_and_result_are_delivered_via_queue():
    messages = []

    def website(host, *, progress):
        messages.append(host)
        progress("testing")

        return GuidedResult(
            "website",
            "done",
            "body",
            "next",
            (),
            "note",
        )

    worker = GuidedWorker(
        website=website
    )

    assert worker.start(
        "website",
        website="example.com",
    )

    worker._thread.join(timeout=2)
    events = list(worker.events.queue)

    assert [
        event.kind for event in events
    ] == ["progress", "result"]

    assert messages == ["example.com"]


def test_worker_does_not_overlap_checks_and_supports_stopping():
    began = threading.Event()
    release = threading.Event()

    def drops(*, progress, cancel):
        began.set()
        release.wait(2)

        return GuidedResult(
            "drops",
            "done",
            "body",
            "next",
            (),
            "note",
        )

    worker = GuidedWorker(
        drops=drops
    )

    assert worker.start("drops")
    assert began.wait(2)
    assert worker.start("drops") is False

    worker.stop()
    assert worker._cancel.is_set()

    release.set()
    worker._thread.join(timeout=2)


def test_worker_error_does_not_expose_internal_exception():
    def crash(*, progress):
        raise RuntimeError(
            "secret from exception"
        )

    worker = GuidedWorker(
        slow=crash
    )
    worker.start("slow")
    worker._thread.join(timeout=2)

    failure = list(
        worker.events.queue
    )[-1]

    assert failure.kind == "error"
    assert "secret" not in failure.value
