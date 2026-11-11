<div align="center">

<img src="assets/netdoctor-icon.png" alt="NetDoctor icon" width="112">

# NetDoctor

### Understand your connection. Find the likely problem. Know what to do next.

**Evidence-based network diagnostics for Windows.**

[Download NetDoctor](https://github.com/QuantumCruz/NetDoctor/releases/latest) · [Report an Issue](https://github.com/QuantumCruz/NetDoctor/issues) · [Source Code](https://github.com/QuantumCruz/NetDoctor)

[![NetDoctor CI](https://github.com/QuantumCruz/NetDoctor/actions/workflows/tests.yml/badge.svg)](https://github.com/QuantumCruz/NetDoctor/actions/workflows/tests.yml)

**Windows 10/11 · Python · React · Local-first · Free and open source**

</div>

---

## Overview

Internet problems are frustrating, particularly when you cannot tell whether the issue comes from your computer, router, internet service provider (ISP), or the service you're trying to access.

**NetDoctor is a Windows desktop application designed to make network troubleshooting understandable.**

Instead of requiring users to understand networking commands, NetDoctor provides guided questions, performs relevant diagnostic checks, and explains the results in plain language.

Developed with practical networking problems in mind, including those commonly encountered on Nigerian networks, NetDoctor combines:

- Windows network diagnostics
- Internet speed and responsiveness measurements
- Connection stability monitoring
- Website connectivity checks
- NAT and CGNAT guidance
- VPN exit-IP comparisons
- Cloud-region latency comparisons
- Practical troubleshooting recommendations

### Evidence before conclusions

NetDoctor distinguishes between:

- **Observed:** What a measurement or Windows network report actually established.
- **Possible:** An explanation consistent with the available results.
- **Unknown:** What cannot reliably be determined.

A failed ping does not automatically mean the router is faulty.

A failed DNS query does not automatically mean the ISP is down.

A successful internet connectivity check does not guarantee every website or application will work.

**NetDoctor aims to reduce guesswork without manufacturing certainty.**

---

## Ask NetDoctor

The main interface includes seven practical troubleshooting questions.

### 1. What's wrong with my internet?

NetDoctor performs a guided diagnosis using:

- Active Windows network adapter information
- Default-route and gateway information
- Gateway ICMP response observations
- Direct DNS queries
- External HTTPS TCP connectivity checks

The application then explains which part of the connection deserves further investigation.

Users can optionally report whether another device works on the same network and whether their PC works on another connection.

These comparisons help narrow potential causes, but they are user-reported rather than independently measured by NetDoctor.

**A single-PC diagnostic snapshot cannot always distinguish a faulty router from an ISP outage.**

### 2. Why is my port forwarding not working?

NetDoctor helps investigate common obstacles to inbound IPv4 connections.

It identifies private and carrier-shared WAN address ranges and explains possible upstream NAT or CGNAT configurations.

Where appropriate, it suggests:

- Checking an upstream router
- Contacting the ISP about public IPv4 availability
- Using Tailscale or ZeroTier for private connectivity between authorized devices
- Investigating an appropriate public tunnel or relay for public hosting

NetDoctor does not automatically configure routers or verify that a particular inbound port is open.

A private WAN address alone does not conclusively establish ISP-level CGNAT.

### 3. Why is my internet slow?

Investigate slow internet performance using available connection information and optional speed measurements.

Users can compare observed speed against their advertised plan and, where appropriate, compare results between connections.

NetDoctor distinguishes measured throughput from Wi-Fi link speed and does not treat one slow result as definitive proof of ISP underperformance.

### 4. Why does my internet keep disconnecting?

Investigate intermittent connectivity problems using connection observations and optional stability monitoring.

NetDoctor separates observed failures from periods when no measurement was taken.

Short monitoring sessions may not capture infrequent problems.

### 5. Why won't a website open?

Run targeted HTTPS connectivity checks and investigate the available DNS, connection, TLS and HTTP response information.

NetDoctor distinguishes an actual HTTP response from a failure to establish a connection.

A website returning an HTTP error does not automatically mean the user's internet connection has failed.

### 6. Which VPS location has the lowest latency?

Compare TCP connection setup times to selected AWS and Oracle Cloud regional endpoints.

Supported regions include locations in South Africa, Europe, the Middle East and the United States.

The application ranks eligible endpoints using completed measurements.

**These are regional API endpoint measurements, not tests of actual VPS instances.**

Results do not guarantee virtual-machine latency, gaming performance or application throughput.

No AWS or Oracle account is required.

### 7. Is my VPN working?

With the user's approval, NetDoctor compares public-IP lookup results before and after connecting a VPN.

It can identify:

- Changes in the observed public IP address
- Changes in the reported IP-based country
- The externally observed exit network

This is not a complete VPN security audit.

It does not prove encryption strength or guarantee protection against DNS, IPv6 or WebRTC leaks.

---

## Explore Tools

NetDoctor also provides direct access to its diagnostic utilities.

### Overview

View current connection information and run an optional Cloudflare-powered internet speed test.

The configured test sequence transfers approximately 22.4 MB plus overhead across downloads and uploads.

Measurements may include:

- Download speed
- Upload speed
- Latency
- Jitter

Completed speed readings are stored locally.

### Diagnosis

Review evidence-based connection findings and perform guided diagnostics.

An optional website address can be included for targeted HTTPS testing.

### Activities

Receive practical network-performance guidance for:

- Online gaming
- Video calls
- Video streaming
- Web browsing

An optional loaded-response test measures latency before and during a short download.

These assessments do not guarantee performance for individual applications or servers.

### Stability

Monitor connection behavior using optional sessions lasting:

- 5 minutes
- 10 minutes
- 30 minutes

Measurements are collected approximately every 10 seconds.

Monitoring history is stored locally using SQLite, with bounded storage.

Monitoring stops when the session ends, the user stops it, or the application closes.

### Cloud Regions

Compare TCP connection setup measurements to selected AWS and Oracle Cloud regional endpoints.

Results include successful attempts, unavailable measurements and observed response-time variation.

A failed regional endpoint does not prove an entire cloud region is unavailable.

### Network Details

Inspect Windows networking information, including:

- Network adapters
- IPv4 and IPv6 configuration
- Default gateways and routes
- DNS information
- Wi-Fi information where available
- VPN and virtual adapters
- Proxy information
- Public-IP and NAT clues

Windows permissions and driver limitations may restrict some available measurements.

---

## Privacy and Network Usage

NetDoctor is designed as a **local-first application**.

- No user account is required.
- No subscription is required.
- No paid cloud infrastructure is required.
- External network measurements are user-initiated.
- In-app confirmation dialogs explain network tests before they run.
- Remote endpoints may observe the user's public exit IP address.
- Local diagnostic history is stored on the computer.
- NetDoctor does not automatically modify Windows networking, DNS, firewall or router settings.

Optional public-IP information is retrieved from IP.SB.

The application normally stores local data under:

`%LOCALAPPDATA%\NetDoctor\`

This may include speed measurements, stability history and startup logs.

Uninstalling NetDoctor does not necessarily remove all saved diagnostic history.

---

## Download and Installation

Download the latest published Windows release:

https://github.com/QuantumCruz/NetDoctor/releases/latest

### v1.0.0 Release Candidate

The planned installer filename is:

`NetDoctor-Setup-v1.0.0-x64.exe`

This release remains subject to packaged application testing and publication.

### System Requirements

- 64-bit Windows 10 or Windows 11
- Microsoft Edge WebView2 Runtime
- Internet access for external network measurements

WebView2 Runtime:

https://developer.microsoft.com/en-us/microsoft-edge/webview2/

The installer bundles the Python runtime and compiled application frontend.

Users do not need to install Python or Node.js separately.

Normal application operation does not require administrator privileges.

### Windows Security Notice

NetDoctor's installer is currently unsigned.

Windows may show an unrecognized-publisher or application-reputation warning.

Download the application only from the official GitHub repository.

Do not disable Windows security protections to install NetDoctor.

### Startup Troubleshooting

Startup failures may be recorded in:

`%LOCALAPPDATA%\NetDoctor\logs\startup.log`

Review logs for sensitive information before sharing them publicly.

---

## Known Limitations

NetDoctor is a diagnostic aid, not a replacement for professional network analysis or ISP support.

Current limitations include:

- Short tests may miss intermittent faults.
- A single computer cannot conclusively identify every router or ISP problem.
- ICMP replies may be blocked or rate-limited.
- Direct DNS checks may differ from Windows or browser name resolution.
- Successful TCP connections do not establish download speed.
- Some external endpoints restrict or ignore probes.
- VPNs and proxies may change observed network paths.
- IP-based geolocation is approximate.
- Wi-Fi link speed does not represent actual internet throughput.
- Cloud-region TCP measurements are not VPS performance benchmarks.
- NAT and CGNAT assessments may remain inconclusive.
- Third-party diagnostic services may change behavior or availability.

Diagnostic recommendations are based on available evidence, not guaranteed root-cause identification.

---

## Development

### Technology Stack

| Component | Technology |
|---|---|
| Diagnostic backend | Python |
| Desktop interface | React |
| Frontend build | Vite |
| Windows integration | pywebview / WebView2 |
| Local storage | SQLite |
| Automated testing | pytest / Node.js test runner |
| Executable packaging | PyInstaller |
| Windows installer | Inno Setup |

### Clone the Repository

```powershell
git clone https://github.com/QuantumCruz/NetDoctor.git
cd NetDoctor
```

### Create a Python Environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,desktop]"
```

### Build the Frontend

```powershell
cd ui
npm ci
npm run build
cd ..
```

### Launch NetDoctor

```powershell
python -m netdoctor.webdesktop
```

### Run Python Tests

```powershell
python -m pytest -q
```

### Run JavaScript Tests

```powershell
$tests = @(
    Get-ChildItem -Path "ui/src" -Recurse -File -Filter "*.test.mjs" |
    ForEach-Object { $_.FullName }
)

node --test $tests
```

### Continuous Integration

GitHub Actions checks:

- Python tests
- JavaScript diagnostic logic tests
- React production build
- Python dependency consistency
- Desktop source-bundle smoke checks
- Remaining native browser confirmation calls

Workflow:

https://github.com/QuantumCruz/NetDoctor/actions/workflows/tests.yml

Automated tests do not replace real Windows installation and network testing.

---

## Windows Packaging

### Build the Windows Application

Install PyInstaller:

```powershell
python -m pip install "pyinstaller>=6,<7"
```

Run the application build:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_windows.ps1"
```

### Build the Installer

Install Inno Setup 6:

https://jrsoftware.org/isdl.php

Build the release candidate:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_installer.ps1"
```

Expected output:

- `release\NetDoctor-Setup-v1.0.0-x64.exe`
- `release\NetDoctor-Setup-v1.0.0-x64.exe.sha256`

The installer must pass installation, startup, diagnostic, restart and uninstall testing before publication.

---

## Reporting Bugs

Report issues here:

https://github.com/QuantumCruz/NetDoctor/issues

Useful reports should include:

- Windows version
- NetDoctor version
- Feature being used
- Expected behavior
- Actual behavior
- Relevant error messages

Avoid publishing passwords, router credentials, tokens or unredacted diagnostic logs.

---

## Release Status

**Development target: NetDoctor v1.0.0**

The release candidate is being prepared for final Windows installation and acceptance testing.

Release notes are maintained in `docs/releases/v1.0.0.md`.

The latest publicly available release can be found on GitHub Releases.

---

## License

NetDoctor is distributed under the **MIT License**.

See [LICENSE](LICENSE) for the complete license terms.

Copyright © 2026 QuantumCruz.

---

<div align="center">

### NetDoctor — Less guessing. Better networking.

Created and maintained by [QuantumCruz](https://github.com/QuantumCruz).

</div>