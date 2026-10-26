"""Ensure Windows network discovery never opens a visible console.

These tests mock PowerShell, so they do not launch a real process.
"""

import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from netdoctor.windows import (
    DiscoveryError,
    _CREATE_NO_WINDOW,
    collect_snapshot,
)


def fake_response():
    return SimpleNamespace(
        returncode=0,
        stdout=json.dumps({
            "Adapters": [],
            "Routes": [],
            "RoutesComplete": True,
            "Warnings": [],
        }),
        stderr="",
    )


def test_windows_discovery_uses_create_no_window():
    with (
        patch(
            "netdoctor.windows.platform.system",
            return_value="Windows",
        ),
        patch(
            "netdoctor.windows.subprocess.run",
            return_value=fake_response(),
        ) as run,
    ):
        collect_snapshot()

    assert run.call_count == 1

    args, kwargs = run.call_args

    assert args[0][0] == "powershell.exe"

    assert kwargs["creationflags"] & 0x08000000
    assert kwargs["creationflags"] == _CREATE_NO_WINDOW
    assert kwargs["shell"] is False
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] == 15.0


def test_powershell_is_noninteractive_and_encoded():
    with (
        patch(
            "netdoctor.windows.platform.system",
            return_value="Windows",
        ),
        patch(
            "netdoctor.windows.subprocess.run",
            return_value=fake_response(),
        ) as run,
    ):
        collect_snapshot(timeout=4.0)

    command = run.call_args.args[0]
    options = run.call_args.kwargs

    assert "-NoProfile" in command
    assert "-NonInteractive" in command
    assert "-EncodedCommand" in command
    assert options["timeout"] == 4.0

    position = command.index("-EncodedCommand")
    encoded = command[position + 1]

    script = base64.b64decode(encoded).decode("utf-16-le")

    assert "Get-NetAdapter" in script
    assert "Get-NetRoute" in script


def test_non_windows_does_not_spawn_powershell():
    with (
        patch(
            "netdoctor.windows.platform.system",
            return_value="Linux",
        ),
        patch(
            "netdoctor.windows.subprocess.run",
        ) as run,
    ):
        with pytest.raises(
            DiscoveryError,
            match="Windows only",
        ):
            collect_snapshot()

    run.assert_not_called()