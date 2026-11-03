
"""Offline desktop bridge tests for opt-in cloud-region comparisons."""

import threading

import pytest

from netdoctor.webdesktop import DashboardAPI


def test_comparison_uses_fixed_limits_and_returns_report(tmp_path):
    calls = []

    def compare(**kwargs):
        calls.append(kwargs)
        return {
            "results": [
                {
                    "provider": "AWS",
                    "region": "af-south-1",
                    "median_ms": 80.0,
                }
            ],
            "best_observed_endpoint": None,
        }

    api = DashboardAPI(
        cloud_comparer=compare,
        data_dir=tmp_path,
    )

    result = api.check_cloud_regions("AWS")

    assert result["ok"]
    assert len(result["report"]["results"]) == 1
    assert calls == [
        {
            "provider": "AWS",
            "attempts": 3,
            "timeout": 1.5,
        }
    ]


@pytest.mark.parametrize(
    "provider",
    [
        "",
        "Azure",
        "AWS;example.com",
        None,
        123,
    ],
)
def test_invalid_provider_does_not_make_connections(
    tmp_path,
    provider,
):
    def never_called(**kwargs):
        pytest.fail("Unexpected network operation")

    api = DashboardAPI(
        cloud_comparer=never_called,
        data_dir=tmp_path,
    )

    result = api.check_cloud_regions(provider)

    assert not result["ok"]


def test_simultaneous_comparisons_are_rejected(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    output = []

    def compare(**kwargs):
        entered.set()
        assert release.wait(5)
        return {"results": [], "best_observed_endpoint": None}

    api = DashboardAPI(
        cloud_comparer=compare,
        data_dir=tmp_path,
    )

    worker = threading.Thread(
        target=lambda: output.append(api.check_cloud_regions())
    )

    worker.start()

    try:
        assert entered.wait(5)

        duplicate = api.check_cloud_regions()

        assert not duplicate["ok"]
        assert "already running" in duplicate["error"]

    finally:
        release.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert output[0]["ok"]


def test_unexpected_error_is_not_exposed(tmp_path):
    def broken(**kwargs):
        raise RuntimeError("internal secret detail")

    api = DashboardAPI(
        cloud_comparer=broken,
        data_dir=tmp_path,
    )

    result = api.check_cloud_regions()

    assert not result["ok"]
    assert "secret" not in result["error"]

    # The lock must be released even after a failure.
    assert not api._cloud_lock.locked()


def test_invalid_report_is_rejected(tmp_path):
    api = DashboardAPI(
        cloud_comparer=lambda **kwargs: {"unexpected": True},
        data_dir=tmp_path,
    )

    result = api.check_cloud_regions()

    assert not result["ok"]
    assert "invalid report" in result["error"]


def test_comparison_is_not_started_on_construction(tmp_path):
    calls = []

    api = DashboardAPI(
        cloud_comparer=lambda **kwargs: calls.append(kwargs),
        data_dir=tmp_path,
    )

    assert api is not None
    assert calls == []
