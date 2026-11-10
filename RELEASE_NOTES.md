# NetDoctor v0.3.0

NetDoctor v0.3.0 focuses on simpler troubleshooting, clearer diagnostic results, improved connection stability monitoring, and more reliable Windows packaging.

NetDoctor remains a local-first Windows network diagnostic application designed to explain network observations in straightforward language and suggest practical next steps.

## What's new

### 1. Unified network diagnosis

The Diagnosis page now provides a single guided troubleshooting workflow.

- One **Run diagnosis** button.
- One optional website field.
- Four diagnostic stages: local connection, DNS, external connectivity, and the selected website.
- A clear result summary and recommended next action.
- Technical evidence and measurements available under an expandable Details section.

The interface distinguishes successful observations, potential issues, inconclusive results, and tests that were not performed.

Checks begin only when requested.

### 2. Website diagnostics

Users can optionally include a public HTTPS website when running a diagnosis.

Available measurements may include:

- DNS lookup time
- TCP connection time
- TLS handshake time
- HTTP response timing and status

Unavailable measurements are identified instead of being reported as successful.

A successful website check does not guarantee that every page, download, or service on that website will work.

### 3. Improved stability monitoring

The Stability page includes a responsive timeline and clearer connection history.

- Monitoring sessions of 5, 10, or 30 minutes.
- Connectivity observations approximately every 10 seconds.
- Timeline visualization of recorded checks.
- Separate counts for fully successful, partially successful, and unsuccessful checks.
- Connection-aware history filtering where network identification is possible.
- Historical observations preserved locally.

Monitoring stops when the selected session ends, the application closes, or a relevant network configuration change is detected.

### 4. Clearer CGNAT guidance

The Overview page now explains how to locate a router's WAN IPv4 address.

Users can enter that address on the Network details page and request a comparison with their observed public IP.

Results distinguish between carrier-shared address space, private upstream addressing, matching public addresses, and inconclusive cases.

These observations provide clues about NAT behavior. They do not conclusively identify the ISP's network architecture or guarantee that inbound connections are possible.

### 5. Interface improvements

- Removed redundant diagnosis panels and duplicate website inputs.
- Removed unnecessary notifications when switching tabs.
- Improved sidebar label layout.
- Refined cloud-region empty-state alignment.
- Simplified Stability page styling without changing its functionality.
- Preserved the existing on-demand testing approach.

### 6. Maintenance and verification

- Removed obsolete legacy troubleshooting code.
- Removed the unused Tkinter desktop interface.
- Added Windows-based automated testing through GitHub Actions.
- Expanded packaged application checks to verify 14 desktop API methods.
- Added regression tests for the newer diagnostic bridge methods.
- Improved consistency across application and installer version metadata.

## Existing capabilities

NetDoctor continues to support:

- Windows connection overview and basic diagnostics.
- Optional download and upload speed tests.
- Latency and jitter measurements.
- Gaming, streaming, video-call, and browsing guidance.
- Loaded responsiveness checks.
- Windows adapter, gateway, Wi-Fi, VPN, and proxy information.
- Public-IP lookup and NAT assessment.
- AWS and Oracle Cloud region TCP connection-time comparisons.
- Locally stored diagnostic history.

Cloud-region measurements represent selected TCP connection attempts to specific endpoints, not guaranteed gameplay latency, ICMP ping, throughput, or complete regional availability.

## Windows installation

The planned v0.3.0 installer filename is:

`NetDoctor-Setup-v0.3.0-x64.exe`

A corresponding `.sha256` checksum file will accompany the installer.

Once v0.3.0 is published, download it from:

https://github.com/QuantumCruz/NetDoctor/releases

Run the installer and launch NetDoctor from the Windows Start menu.

The installed application includes its Python runtime and frontend assets. Users do not need separate Python or Node.js installations.

## System requirements

- 64-bit Windows 10 or Windows 11.
- Microsoft Edge WebView2 Runtime.
- Internet access for external diagnostic tests.

## Privacy and network usage

NetDoctor requires no account, subscription, or paid cloud service.

Diagnostic history is stored locally. External tests may contact third-party services that can observe the user's public exit IP.

Speed tests transfer network data. Cloud-region comparisons make short TCP connections. Optional website diagnostics contact the specified public HTTPS destination.

NetDoctor does not automatically change Windows network, firewall, DNS, or router settings.

## Known limitations

- Short checks can miss intermittent connectivity problems.
- Public services may restrict or reject diagnostic requests.
- ICMP, TCP, HTTPS response timing, and download throughput measure different things.
- VPNs and proxies can affect observed public-IP and routing information.
- Some Wi-Fi details may be unavailable because of Windows permissions or hardware capabilities.
- CGNAT findings may remain inconclusive.
- The installer is not currently code-signed and may trigger an unfamiliar-publisher warning.
- WebView2 availability and compatibility remain important.
- No automatic application updater is included.

Network diagnoses are evidence-based suggestions, not definitive identification of an ISP or hardware fault.

## Release verification

Before publication, the Windows installer must pass automated build checks and manual installation testing.

The v0.3.0 source preparation passed 491 Python tests and verified 14 desktop bridge methods locally.

The installer and installed graphical application require separate validation before publication.

## Feedback

Report issues through:

https://github.com/QuantumCruz/NetDoctor/issues

Include the NetDoctor version, Windows version, steps to reproduce the issue, and any relevant error messages.

Remove passwords, public IP addresses, and other sensitive network information from screenshots and logs before sharing them.

---

NetDoctor — Less guessing. Better networking.