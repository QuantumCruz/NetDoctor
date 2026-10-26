
<div align="center">

<img src="assets/netdoctor-icon.png" alt="NetDoctor icon" width="112">

# NetDoctor

### Understand your connection. Diagnose problems. Know what to do next.

**A Windows network diagnostic application that turns technical measurements into understandable explanations.**

[Releases](https://github.com/QuantumCruz/NetDoctor/releases) · [Report an issue](https://github.com/QuantumCruz/NetDoctor/issues) · [Source code](https://github.com/QuantumCruz/NetDoctor)

**Windows 10/11 · Python · React · Local-first · No subscription**

</div>

---

## What is NetDoctor?

NetDoctor helps you investigate internet and local-network problems without needing to understand networking terminology.

It checks different parts of your connection, explains what the measurements mean, and suggests useful next steps.

It is designed to distinguish three things:

- **Observed:** something NetDoctor actually measured.
- **Possible:** an explanation consistent with the available evidence.
- **Unknown:** something the available tests cannot reliably establish.

The goal is not to display a misleading "network health score" or blame an ISP without evidence.

## Features

### Connection overview

See basic internet reachability, your active network adapter, gateway information, and straightforward explanations of potential problems.

NetDoctor uses short connectivity checks to help establish whether selected destinations can be reached.

### Internet speed

Run an optional speed test for:

- Download speed
- Upload speed
- Network response time
- Response-time variation

Speed testing uses Cloudflare's speed-test service and transfers data only when you request a test.

Results are saved locally.

### Intelligent diagnosis

NetDoctor combines available connection evidence to explain what it noticed, what it cannot confirm, and what you can try next.

An unavailable DNS or ping result does not automatically mean your internet connection is down.

### Activity guidance

Get practical connection insights for:

- Gaming
- Video calls
- Streaming
- General browsing

These are guidance estimates based on available measurements, not guarantees that a particular game or application will perform perfectly.

An optional loaded-response test can help reveal increased delay during a short download.

### Connection stability

Start a user-controlled monitoring session to look for intermittent connection problems.

- Five-, ten-, or thirty-minute sessions
- Small connection checks approximately every ten seconds
- Local history stored in SQLite
- Up to 1,000 stored observations
- Network-specific history where route information is available

Monitoring stops when the session finishes or when the application closes. It can also stop when a network configuration change is detected.

### Network information

Inspect available Windows network information, including:

- Network adapters and connection routes
- Configured DNS information
- Wi-Fi details when Windows allows access
- Possible VPN or virtual-network adapters
- Proxy configuration clues

NetDoctor does not require Windows Location Services to perform its core diagnostics.

Some Wi-Fi information, especially the SSID and signal percentage, may be unavailable when Windows restricts access.

### Public IP and NAT information

Optionally check the public IP address seen by an external lookup service.

NetDoctor can show the reported network operator and autonomous system number (ASN).

If you enter your router's WAN IPv4 address, NetDoctor can provide additional evidence about private WAN addressing and upstream NAT.

For example, a router WAN address in the private `10.0.0.0/8` range indicates that the router does not itself have a publicly routable WAN IPv4 address.

This can suggest upstream NAT or carrier-grade NAT (CGNAT), but cannot always distinguish provider NAT from another local router.

NetDoctor does not log into your router or change port-forwarding settings.

## Download and run

Visit the [GitHub Releases page](https://github.com/QuantumCruz/NetDoctor/releases).

Download the Windows portable ZIP from the latest beta or stable release.

1. Extract the ZIP completely.
2. Open the extracted `NetDoctor` folder.
3. Double-click `NetDoctor.exe`.
4. Use the dashboard to check your connection.

**Keep the entire extracted folder together.** The executable depends on bundled files in its accompanying `_internal` directory.

You do not need to install Python, Node.js, or the project's source dependencies.

### System requirements

- 64-bit Windows 10 or Windows 11
- Microsoft Edge WebView2 Runtime
- Internet access for external connectivity tests and optional online lookups
- No administrator privileges for ordinary operation

WebView2 is available from [Microsoft](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).

Early unsigned builds may trigger a Windows SmartScreen reputation warning. Download releases only from the official repository and do not disable security software.

## Privacy and network usage

NetDoctor is local-first.

- No user account is required.
- No paid cloud infrastructure is required.
- Local measurements and connection history remain on your computer.
- Basic diagnostics make small external connection or DNS checks.
- Speed tests transfer data only after you choose to run one.
- Public IP lookup contacts IP.SB only after you request it.
- Stability monitoring runs only for a session you explicitly start.
- NetDoctor does not automatically change your router, DNS configuration, firewall, or Windows network settings.

Local data is normally stored in:

`%LOCALAPPDATA%\NetDoctor\`

This includes the last saved speed reading and connection-stability history.

Deleting this directory removes the associated local results.

The public IP lookup sends a request to an external service. That service necessarily sees the IP address from which the request exits.

## Understanding the results

**"Reachable"** means the tested connection checks succeeded. It does not prove that every website works or that the connection is fast.

**"Unverified"** means the particular tests could not establish connectivity. It is not a definitive diagnosis of an outage.

**"Possible VPN route"** means a VPN-style adapter may be involved in routing. It does not prove that all traffic uses a VPN.

**"CGNAT not determined"** means there is insufficient information to establish whether provider-level address translation exists.

**"Upstream NAT indicated"** means an additional private-addressing or translation layer is suggested by the supplied router WAN address. The precise network arrangement may still be unknown.

## Limitations

NetDoctor is a diagnostic aid, not a replacement for ISP support, professional packet analysis, or application-specific testing.

- Ping and TCP connections measure different properties.
- Some routers and public endpoints ignore or deprioritize ICMP echo requests.
- TCP connection setup time is not equivalent to application response time.
- Short tests may miss intermittent problems.
- Adapter link speed is not internet download speed.
- Windows may restrict Wi-Fi association details.
- Shared addresses and VPNs can complicate NAT and provider identification.
- Matching network-route details do not prove that two physical networks are the same.

NetDoctor reports these limitations rather than presenting uncertain conclusions as facts.

## Planned improvements

- Cloud-region responsiveness comparisons for AWS, Oracle Cloud, and other providers
- User-selected game or application endpoint tests
- Clearer CGNAT and port-forwarding explanations
- Privacy-filtered diagnostic report sharing
- Wider real-world testing across different Windows computers and networks

Cloud-provider comparisons will measure connections to specified public endpoints. They will not be presented as guaranteed latency to every virtual machine, game server, or service in a region.

## Develop from source

Requirements:

- Python 3.12 or later
- Node.js compatible with the installed Vite version
- Windows for native network discovery and desktop integration

Clone the repository:

```powershell
git clone https://github.com/QuantumCruz/NetDoctor.git
cd NetDoctor
```

Create a Python environment and install development dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,desktop]"
```

Install and build the React frontend:

```powershell
cd ui
npm ci
npm run build
cd ..
```

Launch the development desktop:

```powershell
python -m netdoctor.webdesktop
```

Run automated tests:

```powershell
python -m pytest -q
```

For command-line diagnostic options:

```powershell
netdoctor --help
```

### Build the Windows executable

Install the packaging tool:

```powershell
python -m pip install "pyinstaller>=6,<7"
```

Run the Windows build script:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build_windows.ps1"
```

The portable build will appear under:

`dist\NetDoctor\NetDoctor.exe`

The build script also runs Python tests, creates production React assets, and performs packaged-application smoke checks.

A successful smoke check does not replace manual GUI testing.

## Reporting issues

Use [GitHub Issues](https://github.com/QuantumCruz/NetDoctor/issues).

Please include:

- Your Windows version
- Your NetDoctor release version
- Which action you performed
- What you expected to happen
- What actually happened

Do not publish your public IP, private network addresses, router credentials, or other sensitive information in a public issue.

## Release status

NetDoctor is in active development. Beta releases are intended for early testing and feedback.

The first Windows release uses a portable one-folder application. A traditional installer, signing, and automatic updates are not yet provided.

## Licensing

A repository license has not yet been selected. Check the repository for a `LICENSE` file before assuming the source is licensed for reuse or redistribution.

---

<div align="center">

**NetDoctor — Less guessing. Better networking.**

Created by [QuantumCruz](https://github.com/QuantumCruz).

</div>
