
"""Offline regression tests for the desktop website-check bridge."""

import threading

import pytest

from netdoctor.webdesktop import DashboardAPI
from netdoctor.website_diagnostics import WebsiteTargetError


def test_check_calls_injected_diagnostic_once(tmp_path):
    received = []

    def checker(target):
        received.append(target)
        return {
            "status": "responded",
            "http_status": 200,
        }

    api = DashboardAPI(
        website_checker=checker,
        data_dir=tmp_path,
    )

    assert api.check_website("github.com") == {
        "ok": True,
        "report": {
            "status": "responded",
            "http_status": 200,
        },
    }

    assert received == ["github.com"]


@pytest.mark.parametrize(
    "target",
    [None, 123, "", " " * 4, "x" * 513],
)
def test_invalid_bridge_inputs_do_not_probe(
    tmp_path,
    target,
):
    api = DashboardAPI(
        website_checker=lambda *_: pytest.fail(
            "Unexpected probe"
        ),
        data_dir=tmp_path,
    )

    assert api.check_website(target)["ok"] is False


def test_validation_error_is_reported_without_network(
    tmp_path,
):
    def checker(_):
        raise WebsiteTargetError("HTTPS only.")

    api = DashboardAPI(
        website_checker=checker,
        data_dir=tmp_path,
    )

    response = api.check_website(
        "http://github.com"
    )

    assert response == {
        "ok": False,
        "error": "HTTPS only.",
    }


def test_unexpected_exception_is_sanitized(tmp_path):
    def checker(_):
        raise RuntimeError("secret text")

    api = DashboardAPI(
        website_checker=checker,
        data_dir=tmp_path,
    )

    response = api.check_website(
        "github.com"
    )

    assert response["ok"] is False
    assert "secret text" not in str(response)
    assert not api._website_lock.locked()


def test_parallel_checks_do_not_overlap(tmp_path):
    running = threading.Event()
    release = threading.Event()
    results = []

    def checker(_):
        running.set()
        assert release.wait(4)
        return {
            "status": "responded",
        }

    api = DashboardAPI(
        website_checker=checker,
        data_dir=tmp_path,
    )

    thread = threading.Thread(
        target=lambda: results.append(
            api.check_website("github.com")
        )
    )

    thread.start()

    try:
        assert running.wait(4)

        duplicate = api.check_website(
            "github.com"
        )

        assert duplicate["ok"] is False
        assert "already running" in duplicate["error"]

    finally:
        release.set()
        thread.join(timeout=4)

    assert not thread.is_alive()
    assert results[0]["ok"] is True


def test_invalid_checker_result_is_rejected(tmp_path):
    api = DashboardAPI(
        website_checker=lambda _: ["wrong"],
        data_dir=tmp_path,
    )

    assert api.check_website(
        "github.com"
    )["ok"] is False
