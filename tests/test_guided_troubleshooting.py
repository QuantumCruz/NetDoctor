"""Offline tests for evidence-based guided diagnosis summaries."""

from types import SimpleNamespace as NS

import pytest

from netdoctor.guided_troubleshooting import interpret_guided


def setup_case(
    *,
    active=True,
    route=True,
    tcp=(True, True),
    dns=("answered",),
    gateway_replies=2,
):
    default_route = NS(family="IPv4") if route else None

    snapshot = NS(
        adapters=(NS(is_up=active),),
        preferred_route=lambda family: (
            default_route if family == "IPv4" else None
        ),
    )

    latency = NS(
        targets=(
            NS(
                role="gateway",
                replies=gateway_replies,
                sent=4,
            ),
        ),
    )

    doctor = NS(
        latency=latency,
        dns=(
            NS(
                observations=tuple(
                    NS(status=s) for s in dns
                )
            )
            if dns is not None
            else None
        ),
        connectivity=NS(
            checks=tuple(
                NS(tcp_ok=flag) for flag in tcp
            )
        ),
    )

    return snapshot, doctor


def stage(report, key):
    return next(
        x for x in report["steps"] if x["key"] == key
    )


def test_healthy_no_website_is_not_called():
    snapshot, doctor = setup_case()
    report = interpret_guided(snapshot, doctor)

    assert stage(report, "local")["status"] == "confirmed"
    assert stage(report, "dns")["status"] == "confirmed"
    assert stage(report, "internet")["status"] == "confirmed"
    assert stage(report, "website")["status"] == "not_tested"
    assert "speed" in report["limitation"].lower()


def test_gateway_icmp_no_reply_is_not_called_outage():
    snapshot, doctor = setup_case(gateway_replies=0)
    report = interpret_guided(snapshot, doctor)

    assert stage(report, "local")["status"] == "confirmed"
    assert "block" in stage(
        report, "local"
    )["evidence"].lower()


def test_dns_failures_cannot_override_successful_tcp():
    snapshot, doctor = setup_case(
        dns=("timeout", "invalid_response")
    )

    report = interpret_guided(snapshot, doctor)

    assert stage(report, "dns")["status"] == "inconclusive"
    assert stage(report, "internet")["status"] == "confirmed"


def test_selected_website_may_respond_even_if_standard_targets_do_not():
    snapshot, doctor = setup_case(tcp=(False, False))

    report = interpret_guided(
        snapshot,
        doctor,
        website={
            "status": "responded",
            "http_status": 200,
            "headline": "HTTPS response",
            "next_step": "No action needed.",
        },
    )

    assert stage(report, "website")["status"] == "confirmed"
    assert "despite" in report["headline"].lower()


@pytest.mark.parametrize(
    "http_status",
    [403, 405, 429, 500],
)
def test_http_errors_prove_response_not_broad_outage(
    http_status,
):
    snapshot, doctor = setup_case()

    report = interpret_guided(
        snapshot,
        doctor,
        website={
            "status": "responded",
            "http_status": http_status,
            "headline": "HTTP error",
            "next_step": "Check browser",
        },
    )

    assert stage(report, "website")["status"] == "mixed"
    assert (
        "general connectivity works"
        in report["headline"].lower()
    )


def test_no_active_adapter_has_local_first_next_step():
    snapshot, doctor = setup_case(
        active=False,
        route=False,
        tcp=(False, False),
    )

    report = interpret_guided(snapshot, doctor)

    assert stage(report, "local")["status"] == "attention"
    assert "local connection" in report["headline"].lower()


def test_missing_route_never_declares_router_down():
    snapshot, doctor = setup_case(route=False)
    report = interpret_guided(snapshot, doctor)

    assert stage(report, "local")["status"] == "inconclusive"
    assert "router is unreachable" not in str(report)


def test_inconclusive_website_not_claimed_unreachable():
    snapshot, doctor = setup_case()

    report = interpret_guided(
        snapshot,
        doctor,
        website={
            "status": "inconclusive",
            "explanation": "HEAD unsupported",
            "next_step": "Try browser",
        },
    )

    assert stage(report, "website")["status"] == "inconclusive"
    assert report["next_step"] == "Try browser"


def test_mixed_internet_not_isp_blame():
    snapshot, doctor = setup_case(tcp=(True, False))
    report = interpret_guided(snapshot, doctor)

    assert stage(report, "internet")["status"] == "mixed"
    assert "isp outage" not in report["summary"].lower()