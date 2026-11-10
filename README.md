
<div align="center">

<img src="assets/netdoctor-icon.png" alt="NetDoctor icon" width="112">

# NetDoctor

### Understand your connection. Find the likely problem. Know what to do next.

**Evidence-based network diagnostics for Windows.**

NetDoctor helps you investigate whether connectivity problems may originate from your computer, your local network or router, or your internet service provider.

[Download NetDoctor](https://github.com/QuantumCruz/NetDoctor/releases/latest) · [Report an Issue](https://github.com/QuantumCruz/NetDoctor/issues) · [Source Code](https://github.com/QuantumCruz/NetDoctor)

[![Tests](https://github.com/QuantumCruz/NetDoctor/actions/workflows/tests.yml/badge.svg)](https://github.com/QuantumCruz/NetDoctor/actions/workflows/tests.yml)

**Windows 10/11 · Python · React · Local-first · Free and open source**

</div>

---

## Overview

Internet problems are frustrating, especially when you cannot tell whether the issue is your device, your router, your ISP, or the destination you are trying to reach.

NetDoctor is a Windows desktop application designed to make network troubleshooting more understandable.

It combines connectivity checks, speed measurements, connection stability monitoring, Windows network information, cloud-region responsiveness testing, and NAT diagnostics to help you understand what is happening.

Developed with Nigerian networking conditions in mind, NetDoctor also provides guidance around private WAN addresses, upstream NAT, and possible carrier-grade NAT (CGNAT), which can affect services that require incoming connections.

### Evidence before conclusions

NetDoctor distinguishes between three categories:

- **Observed:** Information directly measured or reported by the system.
- **Possible:** An explanation consistent with the available evidence.
- **Unknown:** Information that cannot reliably be determined from the available measurements.

For example, an unreachable external endpoint does not automatically mean your ISP is experiencing an outage.

Likewise, a private WAN address may indicate upstream NAT, but it does not conclusively establish that your ISP uses CGNAT.

**NetDoctor is designed to reduce guesswork, not manufacture certainty.**

---

## Features

### 1. Connection overview

View useful information about your current network connection, including:

- Active network adapter
- Local network configuration
- Default gateway information
- Internet connectivity checks
- Available Windows network details

NetDoctor interprets the available results and explains what they may mean.

A failed individual probe is not automatically treated as a complete internet outage.

### 2. Internet speed testing

Run an optional Cloudflare-powered speed test.

Measurements include:

- Download speed
- Upload speed
- Response time (latency)
- Response-time variation (jitter)

NetDoctor uses a deliberately limited transfer sequence to reduce unnecessary data consumption.

Completed speed readings are saved locally.

**Important limitations:**

Speed results depend on the test destination, network routing, sampling method, and current connection conditions.

Latency to a Cloudflare endpoint does not represent latency to every website, game server, or application.

The dashboard does not independently verify the exact Cloudflare data-centre location used during a test.

### 3. Evidence-based diagnosis

NetDoctor combines available network measurements to explain:

1. What was observed
2. What might be causing the problem
3. What remains uncertain
4. What you can reasonably try next

The application aims to help users distinguish between possible problems involving their device, local network, internet connection, and external destinations.

It does not automatically blame an ISP based on one failed DNS lookup, ping, or external-service check.

### 4. Activity guidance

Get practical network-performance guidance for:

- Online gaming
- Video calls
- Video streaming
- General browsing

The assessments use available measurements rather than promising guaranteed application performance.

An optional loaded-response test compares connection latency before and during a short download to investigate responsiveness under load.

### 5. Connection stability monitoring

Investigate intermittent connectivity problems using optional monitoring sessions.

Available features include:

- 5-minute monitoring sessions
- 10-minute monitoring sessions
- 30-minute monitoring sessions
- Connectivity observations approximately every 10 seconds
- SQLite-based local history
- Up to 1,000 stored observations
- Network-context awareness where route information is available

Monitoring begins only when requested.

It stops when the selected session ends or the application closes.

Short monitoring sessions may not capture problems that occur infrequently.

### 6. Cloud-region responsiveness

Compare observed TCP connection setup times to public API endpoints associated with AWS and Oracle Cloud regions.

This feature was introduced in v0.2.0.

#### Supported AWS regions

| Region | Location |
|---|---|
| Africa (Cape Town) | South Africa |
| Middle East (Bahrain) | Bahrain |
| Europe (London) | United Kingdom |
| Europe (Frankfurt) | Germany |
| US East (N. Virginia) | United States |

#### Supported Oracle Cloud regions

| Region | Location |
|---|---|
| Johannesburg | South Africa |
| Dubai | United Arab Emirates |
| London | United Kingdom |
| Frankfurt | Germany |
| Ashburn | United States |

#### How the comparison works

NetDoctor performs three TCP connection attempts per endpoint using port 443.

The application reports:

- Median successful connection setup time
- Observed response-time variation
- Successful and unsuccessful attempts
- Partial and unavailable results
- Fastest eligible observed endpoint

You can compare AWS endpoints, Oracle endpoints, or both providers together.

**These are TCP connection setup measurements, not ICMP ping results.**

They do not measure:

- Guaranteed cloud virtual-machine latency
- Application response times
- Cloud server throughput
- Game-server latency
- Overall cloud-provider performance

A failed connection does not prove that an entire cloud region is unavailable.

No AWS or Oracle account is required, and the feature does not create or rent cloud infrastructure.

### 7. Windows network information

Inspect available Windows networking information, including:

- Network adapters and routing
- DNS configuration
- Wi-Fi connection details
- Possible VPN and virtual-network adapters
- Windows proxy settings
- Network link speeds

NetDoctor does not require Windows Location Services for its core diagnostic features.

However, Windows privacy restrictions may prevent access to certain Wi-Fi details, including network names and signal information.

### 8. Public IP and NAT diagnostics

NetDoctor can optionally retrieve your public exit IP address and information about its reported network operator.

If you provide the IPv4 WAN address displayed in your router settings, the application can identify clues suggesting:

- Private WAN addressing
- Upstream network address translation
- Possible carrier-grade NAT (CGNAT)

#### Why CGNAT matters

CGNAT allows an internet provider to share public IPv4 addresses among multiple customers.

Depending on the network configuration, this can complicate:

- Hosting services from home
- Direct inbound connections
- Port forwarding
- Certain peer-to-peer applications
- Some remote-access configurations

CGNAT does not automatically mean that your internet connection is slow or faulty.

A private WAN address alone cannot conclusively distinguish ISP-level CGNAT from another router performing NAT.

NetDoctor does not log into your router, modify its settings, or automatically configure port forwarding.

---

## Download and installation

### Download

Get the latest Windows release:

https://github.com/QuantumCruz/NetDoctor/releases/latest

For v0.2.0, the installer filename is:

`NetDoctor-Setup-v0.2.0-x64.exe`

### Installation

1. Download the installer from GitHub Releases.
2. Run the installer.
3. Follow the installation wizard.
4. Launch NetDoctor from the Windows Start menu.

The installer bundles the application's Python runtime and dashboard files.

You do not need to install Python, Node.js, or development dependencies to use the packaged application.

An uninstaller is included.

### System requirements

- 64-bit Windows 10 or Windows 11
- Microsoft Edge WebView2 Runtime
- Internet access for external network measurements

Normal application operation does not require administrator privileges.

WebView2 Runtime:

https://developer.microsoft.com/en-us/microsoft-edge/webview2/

### Windows security warnings

NetDoctor's installer is not currently code-signed.

Windows may display an unrecognized-publisher or reputation warning when launching a downloaded installer.

Download releases only from the official repository and inspect unexpected warnings.

Do not disable Windows security protections to install NetDoctor.

Earlier portable ZIP distributions could also encounter downloaded-file security restrictions affecting bundled .NET assemblies.

The installer replaces the earlier ZIP distribution approach, but testing across different Windows systems remains important.

### Startup troubleshooting

If the desktop dashboard fails to initialize, NetDoctor attempts to save diagnostic information at:

```text
%LOCALAPPDATA%\NetDoctor\logs\startup.log
```

This file may help identify missing components, Windows runtime problems, or startup failures.

Review logs for private or identifying information before sharing them publicly.

---

## Privacy and network usage

NetDoctor is designed as a local-first diagnostic application.

- No user account is required.
- No subscription is required.
- No paid cloud infrastructure is required.
- Diagnostic history is stored locally.
- Speed tests and cloud-region comparisons run on demand.
- Optional public IP lookups contact an external service.
- Cloud-region comparisons establish short TCP connections to external endpoints.
- External services may observe your public exit IP address.
- NetDoctor does not automatically change Windows, DNS, firewall, or router settings.

Application data is normally stored under:

```text
%LOCALAPPDATA%\NetDoctor\
```

This may include:

- Saved speed measurements
- Connection stability history
- Startup logs

Uninstalling NetDoctor does not automatically delete all saved diagnostic history.

---

## Understanding your results

### Download and upload speed

These measurements represent observed data-transfer performance during the selected test.

They are not guarantees of the speeds available to every application or destination.

### Latency

Latency measures response time to a particular destination using a particular test method.

A nearby endpoint may respond faster than one reached through an international network route.

There is no universal latency value for an entire internet connection.

### Jitter

Jitter describes variation in observed response times.

Measurement methods can differ between test providers and protocols.

### TCP connection timing

Cloud-region responsiveness tests measure the time required to establish TCP connections to selected endpoints.

These measurements are not interchangeable with ICMP ping, HTTP application response time, or download throughput.

### Unavailable results

An unavailable result can reflect:

- Network filtering
- Endpoint restrictions
- Routing problems
- Timeouts
- Temporary network conditions

Failure to reach one destination does not necessarily mean the internet connection is completely unavailable.

---

## Known limitations

NetDoctor is a diagnostic aid, not a replacement for professional packet analysis or ISP troubleshooting.

Current limitations include:

- Short tests may miss intermittent faults.
- ICMP and TCP measurements describe different aspects of connectivity.
- Some external endpoints restrict or ignore probes.
- Cloud API endpoints do not represent every server in their region.
- Adapter link speed is not equivalent to internet download speed.
- VPNs and proxies can change the observed network route.
- Windows may restrict access to certain Wi-Fi information.
- Saved measurements can become outdated after network changes.
- NAT and CGNAT assessments may remain inconclusive.
- Diagnostic recommendations depend on available evidence and are not guarantees.

---

## Development

### Technology stack

| Component | Technology |
|---|---|
| Core application | Python |
| Desktop interface | React |
| Frontend tooling | Vite |
| Windows desktop integration | pywebview |
| Local diagnostic history | SQLite |
| Automated testing | pytest |
| Windows packaging | PyInstaller |
| Installer | Inno Setup |

### Requirements

To develop from source:

- Python 3.12 or later
- Node.js compatible with the installed Vite version
- Windows for native desktop integration

### Clone the repository

```powershell
git clone https://github.com/QuantumCruz/NetDoctor.git
cd NetDoctor
```

### Create a Python environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,desktop]"
```

### Install and build the frontend

```powershell
cd ui
npm ci
npm run build
cd ..
```

### Launch the desktop application

```powershell
python -m netdoctor.webdesktop
```

### Run automated tests

```powershell
python -m pytest -q
```

### Run cloud-region diagnostics from the command line

```powershell
python -m netdoctor.cloud_regions
```

To test an individual provider:

```powershell
python -m netdoctor.cloud_regions --provider AWS
python -m netdoctor.cloud_regions --provider Oracle
```

---

## Building for Windows

### Build the application

Install PyInstaller:

```powershell
python -m pip install "pyinstaller>=6,<7"
```

Run the Windows build script:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_windows.ps1"
```

### Build the installer

Install Inno Setup 6:

https://jrsoftware.org/isdl.php

Then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_installer.ps1"
```

For v0.2.0, the expected installer output is:

```text
release\NetDoctor-Setup-v0.2.0-x64.exe
```

Automated tests and build checks do not replace manual installation, GUI, and fresh-download verification.

---

## Testing and continuous integration

The project uses pytest for automated testing.

Run the suite locally:

```powershell
python -m pytest -q
```

The GitHub Actions test workflow is configured to run the Python test suite on Windows when changes are pushed or pull requests are opened.

Workflow:

https://github.com/QuantumCruz/NetDoctor/actions/workflows/tests.yml

A successful CI run verifies the automated checks executed in that environment. It does not guarantee that the installer or GUI works on every Windows computer.

Manual testing remains necessary, particularly across different network environments and Windows installations.

---

## Reporting bugs

Bug reports and feature suggestions are welcome:

https://github.com/QuantumCruz/NetDoctor/issues

When reporting an issue, include:

- Windows version
- NetDoctor version
- Feature or action involved
- Observed behaviour
- Relevant error information

Do not publish passwords, router credentials, private tokens, or unredacted diagnostic logs.

---

## Release status

**Current documented version: v0.2.0**

This release introduces cloud-region responsiveness comparisons and a Windows installer.

Potential future improvements include:

- Additional cloud-region endpoints
- Application-specific network tests
- Clearer NAT and CGNAT explanations
- Privacy-filtered diagnostic report sharing
- Broader Windows installer compatibility testing
- Installer code signing

These are planned improvements, not guarantees of implementation.

---

## License

NetDoctor is distributed under the **MIT License**.

See [LICENSE](LICENSE) for the full license terms.

Copyright © 2026 QuantumCruz.

---

<div align="center">

### NetDoctor — Less guessing. Better networking.

Created and maintained by [QuantumCruz](https://github.com/QuantumCruz).

</div>
