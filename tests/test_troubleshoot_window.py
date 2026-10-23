
"""Headless checks for guided desktop entry points (visual testing on Windows)."""

from netdoctor.desktop import NetDoctorDesktop
from netdoctor.troubleshoot_window import TroubleshootingWindow


def test_main_window_offers_guided_troubleshooting():
    assert callable(NetDoctorDesktop.open_help)
    assert callable(NetDoctorDesktop._clear_help)


def test_guided_window_exposes_all_three_workflows():
    assert callable(TroubleshootingWindow.start_slow)
    assert callable(TroubleshootingWindow.start_drops)
    assert callable(TroubleshootingWindow.start_website)
    assert callable(TroubleshootingWindow.close)
