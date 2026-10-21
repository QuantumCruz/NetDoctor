import ctypes
from unittest.mock import patch

import pytest

from netdoctor.icmp import (
    EchoResult,
    ProbeError,
    _ReplyHeader,
    ping_ipv4,
)


def test_reply_header_first_fields_have_stable_layout():
    assert ctypes.sizeof(_ReplyHeader) == 12
    assert _ReplyHeader.status.offset == 4
    assert _ReplyHeader.round_trip_time.offset == 8


def test_rejects_ipv6_without_network_request():
    with pytest.raises(ProbeError, match="IPv4"):
        ping_ipv4("::1")


def test_native_success_decodes_rtt_and_closes_handle():
    closed = []

    def send(
        _handle,
        _address,
        _data,
        _size,
        _options,
        reply_ptr,
        _buffer_size,
        _timeout,
    ):
        header = ctypes.cast(
            reply_ptr,
            ctypes.POINTER(_ReplyHeader),
        ).contents

        header.status = 0
        header.round_trip_time = 27
        return 1

    with (
        patch(
            "netdoctor.icmp.platform.system",
            return_value="Windows",
        ),
        patch(
            "netdoctor.icmp._open_api",
            return_value=(lambda: 123, send, closed.append),
        ),
    ):
        result = ping_ipv4("1.1.1.1", timeout_ms=1000)

    assert result == EchoResult(
        "reply",
        27.0,
        "ICMP echo reply received.",
    )
    assert closed == [123]


def test_windows_timeout_is_not_api_failure():
    def send(*_args):
        return 0

    with (
        patch(
            "netdoctor.icmp.platform.system",
            return_value="Windows",
        ),
        patch(
            "netdoctor.icmp._open_api",
            return_value=(
                lambda: 123,
                send,
                lambda _handle: 1,
            ),
        ),
        patch(
            "netdoctor.icmp.ctypes.get_last_error",
            create=True,
            return_value=11010,
        ),
    ):
        result = ping_ipv4("8.8.8.8")

    assert result.status == "timeout"
    assert result.rtt_ms is None


def test_windows_unknown_error_is_not_counted_as_timeout():
    with (
        patch(
            "netdoctor.icmp.platform.system",
            return_value="Windows",
        ),
        patch(
            "netdoctor.icmp._open_api",
            return_value=(
                lambda: 123,
                lambda *_args: 0,
                lambda _handle: 1,
            ),
        ),
        patch(
            "netdoctor.icmp.ctypes.get_last_error",
            create=True,
            return_value=87,
        ),
    ):
        result = ping_ipv4("8.8.8.8")

    assert result.status == "error"