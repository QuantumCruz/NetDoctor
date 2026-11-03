
"""Offline packaging checks and startup-error logging regression tests."""

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


def _mock_dashboard(monkeypatch, *, start=None, create=None):
    class DashboardAPI:
        def shutdown(self):
            pass

    module = ModuleType("netdoctor.webdesktop")
    module.DashboardAPI = DashboardAPI
    monkeypatch.setitem(sys.modules, "netdoctor.webdesktop", module)

    webview = ModuleType("webview")
    webview.create_window = create or (lambda *args, **kwargs: None)
    webview.start = start or (lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "webview", webview)


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


def test_renderer_failure_logs_real_exception(tmp_path, monkeypatch):
    root = frontend(tmp_path)
    messages = []

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        packaged_main,
        "frontend_directory",
        lambda: root,
    )
    monkeypatch.setattr(
        packaged_main,
        "_show_error",
        messages.append,
    )

    def fail_renderer(**kwargs):
        assert kwargs["gui"] == "edgechromium"
        raise RuntimeError("Renderer initialization failed")

    _mock_dashboard(monkeypatch, start=fail_renderer)

    assert packaged_main.launch() == 1

    log = tmp_path / "NetDoctor" / "logs" / "startup.log"
    assert log.is_file()

    content = log.read_text(encoding="utf-8")

    assert "Windows dashboard initialization" in content
    assert "RuntimeError: Renderer initialization failed" in content
    assert "fail_renderer" in content
    assert str(log) in messages[0]


def test_missing_frontend_logs_specific_problem(tmp_path, monkeypatch):
    messages = []

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        packaged_main,
        "frontend_directory",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        packaged_main,
        "_show_error",
        messages.append,
    )

    assert packaged_main.launch() == 2

    log = tmp_path / "NetDoctor" / "logs" / "startup.log"

    assert "Compiled index.html is missing." in log.read_text(
        encoding="utf-8"
    )
    assert "missing or incomplete" in messages[0]


def test_successful_dashboard_does_not_create_failure_log(
    tmp_path,
    monkeypatch,
):
    root = frontend(tmp_path)

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        packaged_main,
        "frontend_directory",
        lambda: root,
    )

    _mock_dashboard(monkeypatch)

    assert packaged_main.launch() == 0

    assert not (
        tmp_path / "NetDoctor" / "logs" / "startup.log"
    ).exists()


def test_log_write_failure_still_displays_error(
    tmp_path,
    monkeypatch,
):
    root = frontend(tmp_path)
    messages = []

    monkeypatch.setattr(
        packaged_main,
        "frontend_directory",
        lambda: root,
    )
    monkeypatch.setattr(
        packaged_main,
        "_show_error",
        messages.append,
    )
    monkeypatch.setattr(
        packaged_main,
        "_write_startup_error",
        lambda *args: None,
    )

    def fail_window(*args, **kwargs):
        raise RuntimeError("Window construction error")

    _mock_dashboard(monkeypatch, create=fail_window)

    assert packaged_main.launch() == 1
    assert "could not be saved" in messages[0]
