
# -*- mode: python ; coding: utf-8 -*-
"""NetDoctor Windows one-folder build. Run via scripts/build_windows.ps1."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPEC).resolve().parent.parent
FRONTEND = ROOT / "ui" / "dist"
ICON = ROOT / "assets" / "netdoctor.ico"

if not (FRONTEND / "index.html").is_file():
    raise SystemExit(
        "Build the React dashboard first: cd ui; npm run build"
    )

if not ICON.is_file():
    raise SystemExit(
        "Missing assets/netdoctor.ico. "
        "Save the NetDoctor Windows icon before building."
    )

webview_datas, webview_binaries, webview_hidden = collect_all("webview")

analysis = Analysis(
    [str(ROOT / "src" / "netdoctor" / "packaged_main.py")],
    pathex=[str(ROOT / "src")],
    binaries=webview_binaries,
    datas=webview_datas + [
        (str(FRONTEND), "ui/dist"),
    ],
    hiddenimports=sorted(set(webview_hidden + [
        "clr",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ])),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "cefpython3",
    ],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="NetDoctor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON),
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="NetDoctor",
)
