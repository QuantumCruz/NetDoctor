# NetDoctor v1.0.0 installer build and verification.
# Run from the repository root.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$releaseVersion = "1.0.0"

$python = Join-Path $root ".venv\Scripts\python.exe"
$buildScript = Join-Path $root "scripts\build_windows.ps1"
$installerSpec = Join-Path $root "packaging\NetDoctor.iss"
$releaseDir = Join-Path $root "release"

$installer = Join-Path $releaseDir "NetDoctor-Setup-v1.0.0-x64.exe"

$requiredSource = @(
    "src\netdoctor\cloud_regions.py",
    "src\netdoctor\webdesktop.py",
    "src\netdoctor\guided_troubleshooting.py",
    "src\netdoctor\public_network.py",
    "ui\src\GuidedHome.jsx",
    "ui\src\CloudRegionsPanel.jsx",
    "ui\src\confirmInPage.mjs",
    "ui\src\confirmInPage.css",
    "ui\src\features\internet-fault\InternetFaultFlow.jsx",
    "ui\src\features\port-forwarding\PortForwardingFlow.jsx",
    "ui\src\features\slow-internet\SlowInternetFlow.jsx",
    "ui\src\features\disconnections\DisconnectFlow.jsx",
    "ui\src\features\website\WebsiteFlow.jsx",
    "ui\src\features\vps-finder\VpsFinderFlow.jsx",
    "ui\src\features\vpn-check\VpnCheckFlow.jsx",
    "tests\test_cloud_regions.py",
    "tests\test_cloud_region_bridge.py",
    "tests\test_vpn_geolocation.py",
    "packaging\NetDoctor.spec",
    "packaging\NetDoctor.iss",
    "README.md",
    "docs\releases\v1.0.0.md",
    "LICENSE"
)

Write-Host "`n=== VALIDATING SOURCE ===" -ForegroundColor Cyan

foreach ($file in $requiredSource) {
    $fullPath = Join-Path $root $file

    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Required source file is missing: $file"
    }
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python environment not found."
}

$versionCheck = @'
import json
import sys
import tomllib
from pathlib import Path

root = Path(sys.argv[1])
expected = sys.argv[2]

with (root / "pyproject.toml").open("rb") as file:
    project = tomllib.load(file)

with (root / "ui" / "package.json").open("r", encoding="utf-8") as file:
    manifest = json.load(file)

with (root / "ui" / "package-lock.json").open("r", encoding="utf-8") as file:
    lock = json.load(file)

versions = {
    "Python package": project["project"]["version"],
    "React package": manifest["version"],
    "npm lockfile": lock["version"],
    "npm lockfile root": lock["packages"][""]["version"],
}

for component, version in versions.items():
    if version != expected:
        raise SystemExit(
            f"{component} version is {version}, expected {expected}"
        )

print(f"PASS: All package versions match {expected}")
'@

& $python -c $versionCheck $root $releaseVersion

if ($LASTEXITCODE -ne 0) {
    throw "Release package versions are inconsistent."
}

$innoConfig = Get-Content -LiteralPath $installerSpec -Raw

if (
    $innoConfig -notmatch '(?m)^#define AppVersion "1\.0\.0"\s*$' -or
    $innoConfig -notmatch '(?m)^OutputBaseFilename=NetDoctor-Setup-v1\.0\.0-x64\s*$' -or
    $innoConfig -notmatch '(?m)^VersionInfoVersion=1\.0\.0\.0\s*$'
) {
    throw "Inno Setup version metadata does not match v1.0.0."
}

Write-Host "Source and version validation passed." -ForegroundColor Green

Write-Host "`n=== REBUILDING NETDOCTOR ===" -ForegroundColor Cyan

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $buildScript

if ($LASTEXITCODE -ne 0) {
    throw "Windows application build failed."
}

Write-Host "`n=== CHECKING PACKAGED APPLICATION ===" -ForegroundColor Cyan

$exe = Join-Path $root "dist\NetDoctor\NetDoctor.exe"

$runtimeDll = Join-Path $root (
    "dist\NetDoctor\_internal\pythonnet\runtime\Python.Runtime.dll"
)

$dashboard = Join-Path $root (
    "dist\NetDoctor\_internal\ui\dist\index.html"
)

foreach ($file in @($exe, $runtimeDll, $dashboard)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Required packaged component missing: $file"
    }
}

Write-Host "Packaged executable and dashboard verified." -ForegroundColor Green

Write-Host "`n=== FINDING INNO SETUP ===" -ForegroundColor Cyan

$compiler = $null
$command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue

if ($command) {
    $compiler = $command.Source
}

if (-not $compiler) {
    $locations = @(
        (Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Inno Setup 6\ISCC.exe"),
        (Join-Path ([Environment]::GetFolderPath("ProgramFiles")) "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )

    foreach ($candidate in $locations) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $compiler = $candidate
            break
        }
    }
}

if (-not $compiler) {
    throw "Inno Setup 6 not found."
}

Write-Host "Compiler: $compiler"

Write-Host "`n=== COMPILING INSTALLER ===" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

& $compiler $installerSpec

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}

if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Installer executable was not generated."
}

Write-Host "`n=== GENERATING SHA256 CHECKSUM ===" -ForegroundColor Cyan

$hash = (
    Get-FileHash -LiteralPath $installer -Algorithm SHA256
).Hash.ToLowerInvariant()

$checksumFile = "$installer.sha256"
$filename = Split-Path $installer -Leaf

"$hash  $filename" |
    Set-Content -LiteralPath $checksumFile -Encoding ascii

Write-Host "`n=== BUILD COMPLETE ===" -ForegroundColor Green

Write-Host "Installer: $installer"
Write-Host "Checksum: $checksumFile"
Write-Host "SHA256: $hash"

Write-Host "`nManual installation and GUI testing are required before publishing." -ForegroundColor Yellow