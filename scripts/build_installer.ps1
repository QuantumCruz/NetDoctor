
# NetDoctor v0.2.0 installer build and verification.
# Run from the repository root.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$buildScript = Join-Path $root "scripts\build_windows.ps1"
$installerSpec = Join-Path $root "packaging\NetDoctor.iss"
$releaseDir = Join-Path $root "release"

$installer = Join-Path $releaseDir "NetDoctor-Setup-v0.2.0-x64.exe"

$requiredSource = @(
    "src\netdoctor\cloud_regions.py",
    "src\netdoctor\webdesktop.py",
    "ui\src\CloudRegionsPanel.jsx",
    "ui\src\cloud-regions.css",
    "tests\test_cloud_regions.py",
    "tests\test_cloud_region_bridge.py",
    "packaging\NetDoctor.iss"
)

Write-Host "`n=== VALIDATING SOURCE ===" -ForegroundColor Cyan

foreach ($file in $requiredSource) {
    $fullPath = Join-Path $root $file

    if (-not (Test-Path -LiteralPath $fullPath)) {
        throw "Required feature file is missing: $file"
    }
}

$projectConfig = Get-Content `
    -LiteralPath (Join-Path $root "pyproject.toml") -Raw

if ($projectConfig -notmatch '(?m)^version\s*=\s*"0\.2\.0"\s*$') {
    throw "pyproject.toml must declare version 0.2.0."
}

Write-Host "Source files and version verified." -ForegroundColor Green

Write-Host "`n=== REBUILDING NETDOCTOR ===" -ForegroundColor Cyan

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $buildScript

if ($LASTEXITCODE -ne 0) {
    throw "Windows application build failed."
}

Write-Host "`n=== CHECKING PACKAGED APPLICATION ===" -ForegroundColor Cyan

$exe = Join-Path $root "dist\NetDoctor\NetDoctor.exe"

$runtimeDll = Join-Path $root `
    "dist\NetDoctor\_internal\pythonnet\runtime\Python.Runtime.dll"

$dashboard = Join-Path $root `
    "dist\NetDoctor\_internal\ui\dist\index.html"

foreach ($file in @($exe, $runtimeDll, $dashboard)) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Required packaged component missing: $file"
    }
}

Write-Host "Executable, pythonnet DLL and React dashboard found." -ForegroundColor Green

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
        if (Test-Path -LiteralPath $candidate) {
            $compiler = $candidate
            break
        }
    }
}

if (-not $compiler) {
    throw "Inno Setup 6 not found. Install it before building the installer."
}

Write-Host "Compiler: $compiler"

Write-Host "`n=== COMPILING INSTALLER ===" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

& $compiler $installerSpec

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}

if (-not (Test-Path -LiteralPath $installer)) {
    throw "Installer executable was not generated."
}

Write-Host "`n=== GENERATING SHA256 CHECKSUM ===" -ForegroundColor Cyan

$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$checksumFile = "$installer.sha256"
$filename = Split-Path $installer -Leaf

"$hash  $filename" |
    Set-Content -LiteralPath $checksumFile -Encoding ascii

Write-Host "`n=== BUILD COMPLETE ===" -ForegroundColor Green

Write-Host "Installer: $installer"
Write-Host "Checksum: $checksumFile"
Write-Host "SHA256: $hash"

Write-Host "`nManual installation and GUI testing are required before publishing." -ForegroundColor Yellow
