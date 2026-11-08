
<div align="center">

<img src="assets/netdoctor-icon.png" alt="NetDoctor icon" width="112">

# NetDoctor

### Understand your connection. Diagnose problems. Know what to do next.

**A Windows network diagnostic application that turns technical measurements into understandable explanations.**

[Download](https://github.com/QuantumCruz/NetDoctor/releases/latest) · [Report an issue](https://github.com/QuantumCruz/NetDoctor/issues) · [Source code](https://github.com/QuantumCruz/NetDoctor)

**Windows 10/11 · Python · React · Local-first · No subscription**

</div>

---

## What is NetDoctor?

**Evidence-based network diagnosis for Windows.**

NetDoctor helps users investigate whether connectivity problems may originate from their device, local network or router, or internet service provider.

Built with Nigerian networking conditions in mind, it combines connectivity checks, speed measurements, stability monitoring, cloud-region TCP timing, and NAT/CGNAT indicators with understandable explanations.

NetDoctor distinguishes measured evidence from possible causes and unknowns. It does not claim to identify every network fault conclusively.

## Features

### Connection overview

Check basic internet connectivity, your active adapter, gateway information and available Windows network details.

NetDoctor explains the meaning of connection results rather than interpreting every failed probe as an internet outage.

### Internet speed

Run an optional Cloudflare-powered speed test to measure:

- Download speed
- Upload speed
- Response time (latency)
- Response-time variation (jitter)

The test uses a deliberately limited transfer sequence to reduce data consumption.

Speed measurements depend on the test destination, network routing and sampling method. In particular, latency to a Cloudflare test endpoint should not be interpreted as latency to every website, game server or application.

The current dashboard does not independently verify the exact Cloudflare data-centre location used for a test.

Completed speed readings are saved locally.

### Intelligent diagnosis

NetDoctor combines measured connection evidence to explain:

- What was observed
- What might be causing a problem
- What remains uncertain
- What action is worth trying next

An unavailable DNS, ping or external-service result does not automatically mean the internet connection is down.

### Activity guidance

Get practical network-performance guidance for:

- Gaming
- Video calls
- Streaming
- General browsing

These assessments use available measurements and are not guarantees of application performance.

An optional loaded-response test compares connection latency before and during a short download.

### Connection stability

Run an optional monitoring session to investigate intermittent problems.

- Five-, ten-, or thirty-minute sessions
- Short connectivity checks approximately every ten seconds
- SQLite-based local history
- Up to 1,000 stored observations
- Network-context awareness where route information is available

Monitoring runs only after being started and stops when its session ends or the application closes.

### Cloud-region responsiveness

**New in v0.2.0**

Compare real TCP connection setup times to ten public cloud API endpoints:

**Amazon Web Services**

- Cape Town, South Africa
- Bahrain
- London, United Kingdom
- Frankfurt, Germany
- Northern Virginia, United States

**Oracle Cloud**

- Johannesburg, South Africa
- Dubai, United Arab Emirates
- London, United Kingdom
- Frankfurt, Germany
- Ashburn, United States

Features include:

- AWS-only, Oracle-only and combined comparisons
- Three TCP attempts per endpoint
- Median successful connection setup time
- Observed response-time variation
- Clear unavailable and partial-result states
- Fastest eligible observed endpoint

These measurements use TCP port 443 and do not require cloud accounts or rented servers.

They are not ICMP ping measurements, guaranteed virtual-machine response times, cloud-provider speed rankings or game-server latency predictions.

An unavailable endpoint does not prove that a cloud region is offline.

### Windows network information

Inspect available information about:

- Network adapters and routing
- DNS configuration
- Wi-Fi connection details
- Possible VPN and virtual-network adapters
- Windows proxy settings
- Network link speeds

Windows Location Services are not required for NetDoctor's core features.

Some Wi-Fi information, including the network name or signal percentage, may be restricted by Windows privacy settings.

### Public IP and NAT information

Optionally check your public exit IP address and its reported network operator.

If you provide the IPv4 WAN address shown in your router settings, NetDoctor can identify clues suggesting private WAN addressing, upstream NAT or possible CGNAT.

These results cannot always distinguish provider-level NAT from another router in the network.

NetDoctor never logs into your router or changes its configuration.

---

## Download and install

Download the latest Windows installer:

https://github.com/QuantumCruz/NetDoctor/releases/latest

1. Download `NetDoctor-Setup-v0.2.0-x64.exe`.
2. Run the installer.
3. Follow the installation wizard.
4. Open NetDoctor from the Start menu.

The installer includes the application's Python runtime and dashboard files.

You do not need to install Python, Node.js or the project's development dependencies.

NetDoctor also includes an uninstaller.

### System requirements

- 64-bit Windows 10 or Windows 11
- Microsoft Edge WebView2 Runtime
- Internet access for external network measurements
- No administrator privileges for normal operation

Microsoft Edge WebView2 Runtime:

https://developer.microsoft.com/en-us/microsoft-edge/webview2/

### Windows security and unsigned releases

NetDoctor is not currently code-signed.

Windows may display security or reputation warnings for a downloaded executable. Download NetDoctor only from the official repository and inspect unexpected warnings rather than disabling Windows security features.

Earlier portable ZIP builds could encounter Windows downloaded-file security restrictions affecting bundled .NET assemblies.

The Windows installer replaces the ZIP distribution approach. It should still be tested on different Windows computers and download environments.

### Startup troubleshooting

If NetDoctor fails to initialize its Windows dashboard, it attempts to save technical details at:

`%LOCALAPPDATA%\NetDoctor\logs\startup.log`

This log can help identify missing components, Windows runtime issues or application startup failures.

Do not publish diagnostic logs without checking them for personally identifying information.

---

## Privacy and network usage

NetDoctor is local-first.

- No user account is required.
- No paid cloud infrastructure is required.
- Diagnostic history remains on your computer.
- Speed tests and cloud-region comparisons run on demand.
- Optional public IP lookups contact an external service.
- Cloud-region comparisons make short TCP connections to external endpoints.
- External services may observe your public exit IP address.
- NetDoctor does not automatically change router, DNS, firewall or Windows network settings.

Stored application data is normally located in:

`%LOCALAPPDATA%\NetDoctor\`

This may include saved speed measurements, stability history and startup logs.

Uninstalling NetDoctor does not automatically delete this history.

## Understanding the measurements

### Download and upload

These values measure observed data-transfer performance during the selected test.

Results can vary between providers, test locations, connection conditions and test durations.

### Latency

Latency is the measured response time to a particular test destination.

For example, a local Lagos test server may respond much faster than a service reached through an international route.

There is no single latency value that accurately describes every internet destination.

### Jitter

Jitter describes variation in observed response times.

The precise measurement method can differ between test providers.

### Cloud-region TCP timing

Cloud-region comparisons measure TCP connection establishment time to selected regional API endpoints.

They are not interchangeable with ICMP ping, application response time, download throughput or guaranteed VM latency.

### Unavailable results

A failed or timed-out connection can reflect filtering, endpoint restrictions, routing problems or temporary network conditions.

Failure to reach one destination does not automatically imply a complete connection outage.

---

## Limitations

NetDoctor is a diagnostic aid, not a replacement for professional packet analysis or ISP troubleshooting.

- Short tests may miss intermittent problems.
- ICMP and TCP tests measure different aspects of connectivity.
- Some endpoints ignore or restrict probing.
- Cloud API endpoints are not representative of every server in a cloud region.
- Adapter link speed is not internet download speed.
- VPNs and proxies can change the observed public route.
- Windows may restrict access to Wi-Fi details.
- Saved readings may become outdated when the network changes.
- Connection recommendations are based on available evidence rather than guarantees.

## Develop from source

Requirements:

- Python 3.12 or later
- Node.js compatible with the installed Vite version
- Windows for native desktop integration

Clone the repository:

```powershell
git clone https://github.com/QuantumCruz/NetDoctor.git
cd NetDoctor
```

Create a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,desktop]"
```

Install and build the frontend:

```powershell
cd ui
npm ci
npm run build
cd ..
```

Launch NetDoctor:

```powershell
python -m netdoctor.webdesktop
```

Run automated tests:

```powershell
python -m pytest -q
```

Run cloud-region diagnostics from the command line:

```powershell
python -m netdoctor.cloud_regions
```

To test one cloud provider:

```powershell
python -m netdoctor.cloud_regions --provider AWS
python -m netdoctor.cloud_regions --provider Oracle
```

### Build the Windows application

Install PyInstaller in the development environment:

```powershell
python -m pip install "pyinstaller>=6,<7"
```

Build the bundled application:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_windows.ps1"
```

### Build the Windows installer

Install Inno Setup 6:

https://jrsoftware.org/isdl.php

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_installer.ps1"
```

The installer will appear under:

`release\NetDoctor-Setup-v0.2.0-x64.exe`

Automated build and smoke tests do not replace manual GUI, installation and fresh-download verification.

---

## Reporting issues

Use GitHub Issues:

https://github.com/QuantumCruz/NetDoctor/issues

Useful information includes your Windows version, NetDoctor version, the action that failed and the observed error.

Never publish passwords, router credentials or unredacted private diagnostic information.

## Release status

**v0.2.0** introduces cloud-region responsiveness comparisons and a Windows installer.

Further planned improvements include additional cloud providers, application-specific endpoint tests, clearer NAT explanations and privacy-filtered diagnostic report sharing.

## Licensing

A repository license has not yet been selected. Check the repository for a `LICENSE` file before assuming permissions for redistribution or reuse.

---

<div align="center">

**NetDoctor — Less guessing. Better networking.**

Created by [QuantumCruz](https://github.com/QuantumCruz).

</div>
