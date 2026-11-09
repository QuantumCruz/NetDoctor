
"""Regression checks for the v0.3.0 packaged desktop API."""

import sys
from types import ModuleType

import pytest

from netdoctor import packaged_main
from netdoctor.webdesktop import DashboardAPI


NEW_BRIDGE_METHODS = (
    "check_cloud_regions",
    "check_website",
    "run_guided_troubleshooting",
)


def test_release_bridge_includes_new_diagnostic_methods():
    for name in NEW_BRIDGE_METHODS:
        assert name in packaged_main.REQUIRED_BRIDGE
        assert callable(getattr(DashboardAPI, name, None))


@pytest.mark.parametrize("missing_method", NEW_BRIDGE_METHODS)
def test_smoke_check_rejects_missing_diagnostic_method(
    tmp_path,
    monkeypatch,
    missing_method,
):
    frontend = tmp_path / "ui" / "dist"
    assets = frontend / "assets"
    assets.mkdir(parents=True)

    (assets / "app.js").write_text(
        "console.log('NetDoctor');",
        encoding="utf-8",
    )

    (assets / "app.css").write_text(
        "body { margin: 0; }",
        encoding="utf-8",
    )

    (frontend / "index.html").write_text(
        '<div id="root"></div>'
        '<script type="module" src="./assets/app.js"></script>'
        '<link rel="stylesheet" href="./assets/app.css">',
        encoding="utf-8",
    )

    available_methods = {
        name: lambda self: None
        for name in packaged_main.REQUIRED_BRIDGE
        if name != missing_method
    }

    dashboard_module = ModuleType("netdoctor.webdesktop")
    dashboard_module.DashboardAPI = type(
        "DashboardAPI",
        (),
        available_methods,
    )

    monkeypatch.setitem(
        sys.modules,
        "netdoctor.webdesktop",
        dashboard_module,
    )

    webview_module = ModuleType("webview")
    webview_module.create_window = (
        lambda *args, **kwargs: None
    )

    monkeypatch.setitem(
        sys.modules,
        "webview",
        webview_module,
    )

    result = packaged_main.smoke_check(frontend)

    assert not result["ok"]
    assert (
        "Required dashboard bridge methods are unavailable."
        in result["problems"]
    )

    assert result["bridge_methods_checked"] == len(
        packaged_main.REQUIRED_BRIDGE
    )
