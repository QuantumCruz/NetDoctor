
"""Stage 7 CLI accepts only intentional, bounded external data use."""
import json
from unittest.mock import patch

import pytest

from netdoctor.cli import main
from netdoctor.throughput import DownloadConfigError, _result


def sample_report():
    return _result("completed", 2 * 1_048_576, 2 * 1_048_576,
                   0.55, 0.09, "test completed")


def test_download_json_dispatch_skips_adapter_collection(capsys):
    with (
        patch("netdoctor.cli.collect_snapshot", side_effect=AssertionError("not needed")),
        patch("netdoctor.cli.measure_download", return_value=sample_report()) as measured,
    ):
        assert main(["download", "--size-mib", "2", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "completed"
    assert data["requested_bytes"] == 2 * 1_048_576
    assert measured.call_args.kwargs == {"size_mib": 2, "timeout": 5.0}


def test_download_readable_includes_caution_and_units(capsys):
    with patch("netdoctor.cli.measure_download", return_value=sample_report()):
        assert main(["download"]) == 0
    printed = capsys.readouterr().out
    assert "Download Diagnostics" in printed
    assert "Mbit/s" in printed
    assert "not your plan speed" in printed


def test_download_unavailable_still_returns_diagnostic_json(capsys):
    report = _result("unavailable", 1_048_576, 0, 0.2, None, "HTTP error")
    with patch("netdoctor.cli.measure_download", return_value=report):
        assert main(["download", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unavailable"


def test_download_configuration_failure_is_structured(capsys):
    with patch("netdoctor.cli.measure_download", side_effect=DownloadConfigError("Bad config")):
        assert main(["download", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "ND-501"


@pytest.mark.parametrize("argv", [
    ["download", "--size-mib", "0"],
    ["download", "--size-mib", "16"],
    ["download", "--count", "2"],
    ["download", "--interval", "0.2"],
    ["download", "--hops", "5"],
    ["download", "--target", "1.1.1.1"],
    ["download", "--hostname", "example.com"],
    ["download", "--offline"],
    ["download", "--timeout", "20"],
    ["doctor", "--size-mib", "2"],
    ["scan", "--size-mib", "2"],
])
def test_download_args_are_strict(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
