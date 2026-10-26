
# NetDoctor Stage 23 - Windows standalone build and verification
# Run from the project root using:
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_windows.ps1"

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$results = Join-Path $env:USERPROFILE 'NetDoctorResults'

New-Item -ItemType Directory -Force -Path $results | Out-Null

$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$log = Join-Path $results "Stage23-build-$stamp.txt"
$sourceReport = Join-Path $results "Stage23-source-smoke-$stamp.json"
$bundleReport = Join-Path $results "Stage23-package-smoke-$stamp.json"

function Say {
    param([string]$Message)

    $Message | Tee-Object -FilePath $log -Append
}

function Quote-Argument {
    param([string]$Value)

    return '"' + $Value.Replace('"', '\"') + '"'
}

function Invoke-Logged {
    param(
        [string]$Label,
        [string]$Program,
        [string[]]$CommandArguments
    )

    Say ""
    Say "Running: $Label"

    $stdout = [System.IO.Path]::GetTempFileName()
    $stderr = [System.IO.Path]::GetTempFileName()

    try {
        $process = Start-Process `
            -FilePath $Program `
            -ArgumentList $CommandArguments `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr

        if ((Get-Item -LiteralPath $stdout).Length -gt 0) {
            Get-Content -LiteralPath $stdout |
                Tee-Object -FilePath $log -Append
        }

        if ((Get-Item -LiteralPath $stderr).Length -gt 0) {
            Get-Content -LiteralPath $stderr |
                Tee-Object -FilePath $log -Append
        }

        if ($process.ExitCode -ne 0) {
            throw "$Label failed with exit code $($process.ExitCode)."
        }

        Say "PASSED: $Label"
    }
    finally {
        Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
    }
}

if ($env:OS -ne 'Windows_NT') {
    throw 'This build must run on Windows.'
}

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Project virtual environment not found at .venv\Scripts\python.exe'
}

Push-Location $root

try {
    Say "========== NETDOCTOR STAGE 23 BUILD =========="
    Say "Project: $root"
    Say "Results: $results"

    # 1. Check required development dependencies
    Say ""
    Say "========== DEPENDENCY CHECK =========="

    Invoke-Logged `
        -Label 'PyInstaller availability' `
        -Program $python `
        -CommandArguments @(
            '-m',
            'PyInstaller',
            '--version'
        )

    Invoke-Logged `
        -Label 'pywebview availability' `
        -Program $python `
        -CommandArguments @(
            '-m',
            'pip',
            'show',
            'pywebview'
        )

    # 2. Run complete Python tests
    Say ""
    Say "========== FULL PYTHON REGRESSION =========="

    Invoke-Logged `
        -Label 'Complete Python test suite' `
        -Program $python `
        -CommandArguments @(
            '-m',
            'pytest',
            '-q'
        )

    # 3. Build React frontend
    Say ""
    Say "========== REACT PRODUCTION BUILD =========="

    Push-Location (Join-Path $root 'ui')

    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            Invoke-Logged `
                -Label 'Install frontend dependencies' `
                -Program 'cmd.exe' `
                -CommandArguments @(
                    '/d',
                    '/c',
                    'npm ci --no-audit --no-fund'
                )
        }

        Invoke-Logged `
            -Label 'React production build' `
            -Program 'cmd.exe' `
            -CommandArguments @(
                '/d',
                '/c',
                'npm run build'
            )
    }
    finally {
        Pop-Location
    }

    # 4. Check source dashboard assets
    Say ""
    Say "========== SOURCE SMOKE CHECK =========="

    Invoke-Logged `
        -Label 'Source assets and bridge' `
        -Program $python `
        -CommandArguments @(
            '-m',
            'netdoctor.packaged_main',
            '--smoke-report',
            (Quote-Argument $sourceReport)
        )

    if (-not (Test-Path -LiteralPath $sourceReport)) {
        throw 'Source smoke report was not produced.'
    }

    $sourceStatus = Get-Content -LiteralPath $sourceReport -Raw |
        ConvertFrom-Json

    if (-not $sourceStatus.ok) {
        throw 'Source smoke report contains errors.'
    }

    # 5. Build one-folder executable
    Say ""
    Say "========== PYINSTALLER BUILD =========="

    $spec = Join-Path $root 'packaging\NetDoctor.spec'
    $dist = Join-Path $root 'dist'
    $work = Join-Path $root 'build\pyinstaller'

    if (-not (Test-Path -LiteralPath $spec)) {
        throw 'Missing packaging\NetDoctor.spec'
    }

    Invoke-Logged `
        -Label 'Package NetDoctor.exe' `
        -Program $python `
        -CommandArguments @(
            '-m',
            'PyInstaller',
            '--clean',
            '--noconfirm',
            '--distpath',
            (Quote-Argument $dist),
            '--workpath',
            (Quote-Argument $work),
            (Quote-Argument $spec)
        )

    $exe = Join-Path $root 'dist\NetDoctor\NetDoctor.exe'

    if (-not (Test-Path -LiteralPath $exe)) {
        throw 'NetDoctor.exe was not produced.'
    }

    # 6. Validate executable without opening GUI
    Say ""
    Say "========== PACKAGED APPLICATION SMOKE CHECK =========="

    Invoke-Logged `
        -Label 'Packaged executable smoke check' `
        -Program $exe `
        -CommandArguments @(
            '--smoke-report',
            (Quote-Argument $bundleReport)
        )

    if (-not (Test-Path -LiteralPath $bundleReport)) {
        throw 'Packaged smoke report was not produced.'
    }

    $bundleStatus = Get-Content -LiteralPath $bundleReport -Raw |
        ConvertFrom-Json

    if (-not $bundleStatus.ok) {
        throw 'Packaged smoke check reported errors.'
    }

    if (-not $bundleStatus.frozen) {
        throw 'Smoke check did not run inside a frozen executable.'
    }

    # 7. Final summary
    Say ""
    Say "========== FINAL RESULTS =========="
    Say "JavaScript assets: $($bundleStatus.js_assets)"
    Say "CSS assets: $($bundleStatus.css_assets)"
    Say "Bridge methods checked: $($bundleStatus.bridge_methods_checked)"
    Say ""
    Say "ALL STAGE 23 BUILD CHECKS PASSED"
    Say "Executable: $exe"
    Say "Source smoke report: $sourceReport"
    Say "Package smoke report: $bundleReport"
    Say ""
    Say "The actual desktop window and buttons still require manual testing."

    Write-Host ""
    Write-Host "BUILD SUCCESSFUL" -ForegroundColor Green
    Write-Host "NetDoctor.exe is ready for manual testing." -ForegroundColor Green
}
catch {
    Say ""
    Say "========== BUILD FAILED =========="
    Say $_.Exception.Message

    Write-Host ""
    Write-Host "BUILD FAILED - SEE LOG" -ForegroundColor Red

    throw
}
finally {
    Pop-Location

    Write-Host ""
    Write-Host "Build log: $log"
}
