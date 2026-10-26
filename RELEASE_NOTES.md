
# NetDoctor v0.1.0 Beta 1

The first portable Windows beta of NetDoctor.

NetDoctor helps you understand connection problems through real measurements, readable explanations, and practical next steps.

## Highlights

- Native Windows desktop application with a React dashboard
- New NetDoctor pulse-and-shield application icon
- Connection overview and basic internet diagnostics
- Optional download and upload speed tests
- Responsiveness and latency insights
- Guidance for gaming, calls, streaming, and browsing
- User-controlled connection stability monitoring
- Network-specific history where routing information is available
- Windows network, Wi-Fi, VPN-style adapter, and proxy information
- Optional public-IP lookup and CGNAT/NAT clues
- Intelligent diagnosis that distinguishes observed facts from possible explanations
- Action feedback, loading indicators, and human-readable status messages

## Installation

1. Download `NetDoctor-Windows-v0.1.0-beta.1.zip`.
2. Extract the ZIP completely.
3. Open the `NetDoctor` folder.
4. Run `NetDoctor.exe`.

Keep the entire folder together, including `_internal`.

Python and Node.js are not required on the user's computer.

## Requirements

- 64-bit Windows 10 or 11
- Microsoft Edge WebView2 Runtime
- Internet access for external network checks

## Privacy

No account, subscription, or cloud database is required.

Results are stored locally. The public-IP lookup and speed test are optional and require user action.

NetDoctor does not change router or Windows network settings.

## Known beta limitations

- This is an early test release, not a fully validated stable release.
- The executable is not code-signed, so Windows may show an unfamiliar-app warning.
- WebView2 must be available on the computer.
- Some Wi-Fi data may be restricted by Windows privacy settings.
- Network diagnostics are evidence-based, not definitive proof of ISP problems.
- The cloud-region comparison feature is planned but is not included in this release.
- No automatic updater or traditional installer is included yet.

## Feedback

Please report issues at:
https://github.com/QuantumCruz/NetDoctor/issues

When reporting a problem, describe what you clicked, what happened, and your Windows version.

Please remove public IP addresses, credentials, and other private network information from screenshots and logs.

Thank you for helping test NetDoctor!
