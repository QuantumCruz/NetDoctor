
"""Loaded CLI routing, opt-in traffic, and JSON compatibility."""

import json
from unittest.mock import patch

import pytest

from netdoctor.cli import main
from netdoctor.icmp import EchoResult
from netdoctor.loaded import LoadedError, LoadProbe, _interpret
from netdoctor.throughput import DownloadReport


def _report():
    download = DownloadReport(
        "completed", "preliminary", "Cloudflare", 4194304,
        4194304, 1400., 300., 24., "okay", ()
    )
    return _interpret(
        "8.8.8.8",
        tuple(EchoResult("reply", 10., "ok") for _ in range(4)),
        tuple(LoadProbe("reply", 12., True, "ok") for _ in range(4)),
        download, 1100.
    )


def test_loaded_json_dispatch_does_not_collect_windows_snapshot(capsys):
    with (
        patch("netdoctor.cli.collect_snapshot", side_effect=AssertionError("snapshot not needed")),
        patch("netdoctor.cli.measure_loaded", return_value=_report()) as called,
    ):
        assert main(["loaded", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "no_clear_increase"
    assert result["loaded_replies"] == 4
    assert called.call_args.kwargs["size_mib"] == 4
    assert called.call_args.kwargs["timeout"] == 10.
    assert called.call_args.kwargs["target"] == "8.8.8.8"


def test_loaded_can_select_one_ipv4_target(capsys):
    with patch("netdoctor.cli.measure_loaded", return_value=_report()) as called:
        assert main([
            "loaded", "--target", "1.1.1.1",
            "--size-mib", "1", "--json"
        ]) == 0

    assert called.call_args.kwargs["target"] == "1.1.1.1"
    assert called.call_args.kwargs["size_mib"] == 1


def test_loaded_readable_includes_uncertainty(capsys):
    with patch("netdoctor.cli.measure_loaded", return_value=_report()):
        assert main(["loaded"]) == 0

    output = capsys.readouterr().out
    assert "Loaded Latency" in output
    assert "During-transfer replies" in output
    assert "cannot prove" in output


def test_loaded_engine_error_returns_structured_nd601(capsys):
    with patch("netdoctor.cli.measure_loaded", side_effect=LoadedError("Unable to probe")):
        assert main(["loaded", "--json"]) == 2

    assert json.loads(capsys.readouterr().out)["error"]["code"] == "ND-601"


@pytest.mark.parametrize("args", [
    ["loaded", "--size-mib", "3"],
    ["loaded", "--offline"],
    ["loaded", "--count", "4"],
    ["loaded", "--interval", "0.2"],
    ["loaded", "--hops", "5"],
    ["loaded", "--hostname", "example.com"],
    ["loaded", "--target", "1.1.1.1", "--target", "8.8.8.8"],
    ["loaded", "--timeout", "11"],
    ["scan", "--size-mib", "4"],
])
def test_loaded_arguments_reject_unrelated_options(args):
    with pytest.raises(SystemExit) as error:
        main(args)

    assert error.value.code == 2


def test_existing_download_defaults_unchanged(capsys):
    with patch("netdoctor.cli.measure_download", return_value=_report().download) as called:
        assert main(["download", "--json"]) == 0

    assert called.call_args.kwargs == {"size_mib": 2, "timeout": 5.0}
