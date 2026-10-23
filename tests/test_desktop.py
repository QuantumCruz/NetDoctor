"""GUI launch safety checks that do not require a visible desktop session."""

from unittest.mock import patch

from netdoctor import desktop


def test_graphical_launcher_is_present():
    assert callable(desktop.main)
    assert hasattr(desktop, "NetDoctorDesktop")


def test_unavailable_display_returns_exit_code_instead_of_traceback():
    with patch(
        "netdoctor.desktop.tk.Tk",
        side_effect=desktop.tk.TclError("no display"),
    ):
        assert desktop.main() == 1