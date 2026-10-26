"""Offline bundle validation; never opens WebView2 or makes a network request."""

import json
import sys
from types import ModuleType

from netdoctor import packaged_main


def frontend(
    tmp_path,
    *,
    js=True,
    css=True,
    script="./assets/app.js",
):
    root = tmp_path / "ui" / "dist"
    assets = root / "assets"
    assets.mkdir(parents=True)

    if js:
        (assets / "app.js").write_text(
            "console.log('test')",
            encoding="utf-8",
        )

    if css:
        (assets / "app.css").write_text(
            "body{}",
            encoding="utf-8",
        )

    (root / "index.html").write_text(
        f'<div id="root"></div>'
        f'<script type="module" src="{script}"></script>'
        '<link rel="stylesheet" href="./assets/app.css">',
        encoding="utf-8",
    )

    return root


def test_compiled_frontend_assets_are_checked(tmp_path):
    root = frontend(tmp_path)
    output = packaged_main.inspect_frontend(root)

    assert output["ok"]
    assert output["js_assets"] == 1
    assert output["css_assets"] == 1


def test_missing_javascript_is_reported(tmp_path):
    root = frontend(tmp_path, js=False)

    assert not packaged_main.inspect_frontend(root)["ok"]


def test_missing_stylesheet_is_reported(tmp_path):
    root = frontend(tmp_path, css=False)

    assert not packaged_main.inspect_frontend(root)["ok"]


def test_path_traversal_and_remote_assets_are_rejected(tmp_path):
    for source in (
        "../outside.js",
        "https://example.com/app.js",
        "/assets/app.js",
    ):
        folder = source.replace("/", "_").replace(":", "_")
        root = frontend(
            tmp_path / folder,
            script=source,
        )

        assert not packaged_main.inspect_frontend(root)["ok"]


def test_no_frontend_assets_reports_failure(tmp_path):
    assert not packaged_main.inspect_frontend(tmp_path)["ok"]


def test_frozen_lookup_uses_meipass(tmp_path, monkeypatch):
    monkeypatch.setattr(
        packaged_main.sys,
        "frozen",
        True,
        raising=False,
    )

    monkeypatch.setattr(
        packaged_main.sys,
        "_MEIPASS",
        str(tmp_path),
        raising=False,
    )

    assert packaged_main.frontend_directory() == (
        tmp_path / "ui" / "dist"
    )


def test_smoke_check_is_read_only_and_checks_bridge(
    tmp_path,
    monkeypatch,
):
    root = frontend(tmp_path)

    module = ModuleType("netdoctor.webdesktop")

    module.DashboardAPI = type(
        "DashboardAPI",
        (),
        {
            name: lambda self: None
            for name in packaged_main.REQUIRED_BRIDGE
        },
    )

    monkeypatch.setitem(
        sys.modules,
        "netdoctor.webdesktop",
        module,
    )

    webview = ModuleType("webview")
    webview.create_window = lambda *a, **k: None

    monkeypatch.setitem(
        sys.modules,
        "webview",
        webview,
    )

    output = packaged_main.smoke_check(root)

    assert output["ok"]
    assert "does not verify" in output["note"]


def test_smoke_report_is_written_without_gui(
    tmp_path,
    monkeypatch,
):
    root = frontend(tmp_path)

    monkeypatch.setattr(
        packaged_main,
        "frontend_directory",
        lambda: root,
    )

    module = ModuleType("netdoctor.webdesktop")

    module.DashboardAPI = type(
        "DashboardAPI",
        (),
        {
            name: lambda self: None
            for name in packaged_main.REQUIRED_BRIDGE
        },
    )

    monkeypatch.setitem(
        sys.modules,
        "netdoctor.webdesktop",
        module,
    )

    webview = ModuleType("webview")
    webview.create_window = lambda *a, **k: None

    monkeypatch.setitem(
        sys.modules,
        "webview",
        webview,
    )

    path = tmp_path / "out" / "smoke.json"

    assert packaged_main.main([
        "--smoke-report",
        str(path),
    ]) == 0

    result = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert result["ok"]


def test_invalid_arguments_do_not_launch_gui(monkeypatch):
    def unexpected_launch():
        raise AssertionError("GUI launched")

    monkeypatch.setattr(
        packaged_main,
        "launch",
        unexpected_launch,
    )

    monkeypatch.setattr(
        packaged_main,
        "_show_error",
        lambda *_: None,
    )

    assert packaged_main.main(["unexpected"]) == 2