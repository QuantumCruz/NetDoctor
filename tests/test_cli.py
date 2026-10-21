import json
from unittest.mock import patch

import pytest

from netdoctor.cli import main
from netdoctor.crosscheck import (
    CrosscheckReport,
    TcpAttempt,
    _summarize_tcp,
)
from netdoctor.icmp import EchoResult, ProbeError
from netdoctor.latency import LatencyReport, _summarize
from netdoctor.models import Adapter, Snapshot
from netdoctor.windows import DiscoveryError


def _snapshot():
    return Snapshot(
        (
            Adapter(
                1,
                "Ethernet",
                "Ethernet adapter",
                "Up",
                "1 Gbps",
                "Ethernet (inferred)",
                ("192.168.0.2",),
                (),
                (),
            ),
        ),
        (),
        (),
    )


def test_json_offline_does_not_contact_internet(capsys):
    with (
        patch(
            "netdoctor.cli.collect_snapshot",
            return_value=_snapshot(),
        ),
        patch(
            "netdoctor.cli.check_endpoint",
            side_effect=AssertionError("Unexpected internet access"),
        ),
    ):
        assert main(["scan", "--offline", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)

    assert report["online_status"] == "not_tested"
    assert report["snapshot"]["adapters"][0]["name"] == "Ethernet"


def test_cli_reports_discovery_failure_without_traceback(capsys):
    with patch(
        "netdoctor.cli.collect_snapshot",
        side_effect=DiscoveryError("Unavailable"),
    ):
        assert main(["--json"]) == 2

    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "ND-101"


def test_json_reports_incomplete_routes_instead_of_false_missing_route(capsys):
    snapshot = Snapshot(
        _snapshot().adapters,
        (),
        ("Windows could not provide default-route information.",),
        False,
    )

    with patch(
        "netdoctor.cli.collect_snapshot",
        return_value=snapshot,
    ):
        assert main(["scan", "--offline", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)

    assert report["snapshot"]["routes_complete"] is False

    assert not any(
        finding["title"] == "No usable default route was found"
        for finding in report["findings"]
    )


def test_readable_report_says_unknown_when_routes_failed(capsys):
    snapshot = Snapshot(
        _snapshot().adapters,
        (),
        ("Windows could not provide default-route information.",),
        False,
    )

    with patch(
        "netdoctor.cli.collect_snapshot",
        return_value=snapshot,
    ):
        assert main(["scan", "--offline"]) == 0

    output = capsys.readouterr().out

    assert "Cannot determine" in output
    assert "Not found on an active adapter" not in output


def test_latency_json_report_integrates(capsys):
    result = _summarize(
        "Target",
        "1.1.1.1",
        "public",
        (
            EchoResult("reply", 25.0, "OK"),
            EchoResult("reply", 26.0, "OK"),
        ),
    )

    with (
        patch(
            "netdoctor.cli.collect_snapshot",
            return_value=_snapshot(),
        ),
        patch(
            "netdoctor.cli.measure_latency",
            return_value=LatencyReport((result,), ()),
        ),
    ):
        assert main(["latency", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["targets"][0]["median_ms"] == 25.5


def test_latency_native_error_is_readable(capsys):
    with (
        patch(
            "netdoctor.cli.collect_snapshot",
            return_value=_snapshot(),
        ),
        patch(
            "netdoctor.cli.measure_latency",
            side_effect=ProbeError("Windows ICMP unavailable"),
        ),
    ):
        assert main(["latency", "--json"]) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "ND-201"


def test_latency_rejects_offline_mode():
    with pytest.raises(SystemExit) as result:
        main(["latency", "--offline"])

    assert result.value.code == 2


def test_scan_refuses_latency_flags():
    with pytest.raises(SystemExit) as result:
        main(["scan", "--count", "10"])

    assert result.value.code == 2


def test_investigate_json_uses_crosscheck_engine(capsys):
    icmp = _summarize(
        "Target",
        "1.1.1.1",
        "public",
        (
            EchoResult("reply", 25.0, "OK"),
            EchoResult("reply", 26.0, "OK"),
        ),
    )

    tcp = _summarize_tcp(
        "Target",
        "1.1.1.1",
        (
            TcpAttempt("connected", 35.0, "connected"),
            TcpAttempt("connected", 37.0, "connected"),
        ),
    )

    response = CrosscheckReport(
        LatencyReport((icmp,), ()),
        (tcp,),
        (),
    )

    with (
        patch(
            "netdoctor.cli.collect_snapshot",
            return_value=_snapshot(),
        ),
        patch(
            "netdoctor.cli.run_crosscheck",
            return_value=response,
        ) as call,
    ):
        assert main([
            "investigate",
            "--count",
            "2",
            "--json",
        ]) == 0

    result = json.loads(capsys.readouterr().out)

    assert result["tcp"][0]["median_ms"] == 36
    assert result["latency"]["targets"][0]["median_ms"] == 25.5
    assert call.call_args.kwargs["count"] == 2


def test_investigate_text_output_explains_protocols(capsys):
    icmp = _summarize(
        "Target",
        "1.1.1.1",
        "public",
        (
            EchoResult("reply", 25.0, "OK"),
            EchoResult("reply", 26.0, "OK"),
        ),
    )

    tcp = _summarize_tcp(
        "Target",
        "1.1.1.1",
        (
            TcpAttempt("connected", 35.0, "connected"),
        ),
    )

    response = CrosscheckReport(
        LatencyReport((icmp,), ()),
        (tcp,),
        (),
    )

    with (
        patch(
            "netdoctor.cli.collect_snapshot",
            return_value=_snapshot(),
        ),
        patch(
            "netdoctor.cli.run_crosscheck",
            return_value=response,
        ),
    ):
        assert main(["investigate"]) == 0

    output = capsys.readouterr().out

    assert "TCP connects" in output
    assert "ICMP replies" in output
    assert "not TLS, HTTP, or speed" in output


def test_investigate_does_not_accept_offline():
    with pytest.raises(SystemExit) as exc:
        main(["investigate", "--offline"])

    assert exc.value.code == 2


def test_investigate_native_error_is_structured(capsys):
    with (
        patch(
            "netdoctor.cli.collect_snapshot",
            return_value=_snapshot(),
        ),
        patch(
            "netdoctor.cli.run_crosscheck",
            side_effect=ProbeError("ICMP unavailable"),
        ),
    ):
        assert main(["investigate", "--json"]) == 2

    assert (
        json.loads(capsys.readouterr().out)["error"]["code"]
        == "ND-201"
    )