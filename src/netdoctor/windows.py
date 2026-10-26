"""Read-only Windows network discovery through supported PowerShell cmdlets.

Child PowerShell processes must not create visible terminal windows.
This is essential when NetDoctor runs as a windowed PyInstaller executable.
"""

import base64
import json
import platform
import re
import subprocess

from netdoctor.models import Adapter, DefaultRoute, Snapshot


class DiscoveryError(Exception):
    """A diagnostic collection step could not finish reliably."""


# CREATE_NO_WINDOW is supported by Windows CreateProcess.
# Use the numeric Windows value as a fallback so mock-based tests can
# exercise this behavior on non-Windows development environments.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


# Query the routing table without filtering for a route that might not exist.
# Windows may raise a "no matching objects" error for an absent IPv6 default.
_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$warnings = @()
$adapters = @(Get-NetAdapter -IncludeHidden -ErrorAction Stop)
$configs = @()
try {
    $configs = @(Get-NetIPConfiguration -All -ErrorAction Stop)
} catch {
    $warnings += 'Windows could not provide IP/DNS configuration.'
}
$routes = @()
$routesComplete = $true
try {
    $routes = @(Get-NetRoute -ErrorAction Stop |
        Where-Object {
            $_.DestinationPrefix -eq '0.0.0.0/0' -or $_.DestinationPrefix -eq '::/0'
        } |
        Where-Object { $_.State -eq 'Alive' } |
        ForEach-Object {
            [pscustomobject]@{
                InterfaceIndex = $_.InterfaceIndex
                DestinationPrefix = [string]$_.DestinationPrefix
                NextHop = [string]$_.NextHop
                RouteMetric = $_.RouteMetric
                InterfaceMetric = $_.InterfaceMetric
            }
        })
} catch {
    $routesComplete = $false
    $warnings += 'Windows could not provide default-route information.'
}
$items = @($adapters | ForEach-Object {
    $adapter = $_
    $config = $configs | Where-Object { $_.InterfaceIndex -eq $adapter.ifIndex } | Select-Object -First 1
    [pscustomobject]@{
        InterfaceIndex = $adapter.ifIndex
        Name = [string]$adapter.Name
        Description = [string]$adapter.InterfaceDescription
        Status = [string]$adapter.Status
        LinkSpeed = [string]$adapter.LinkSpeed
        IPv4 = @($config.IPv4Address | ForEach-Object { $_.IPAddress })
        IPv6 = @($config.IPv6Address | ForEach-Object { $_.IPAddress })
        DNS = @($config.DNSServer.ServerAddresses)
    }
})
ConvertTo-Json -InputObject ([pscustomobject]@{
    Adapters = $items
    Routes = $routes
    RoutesComplete = $routesComplete
    Warnings = $warnings
}) -Depth 5 -Compress
"""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        value = [] if value is None else [value]
    return tuple(
        result
        for item in value
        if (result := _text(item))
    )


def _records(value: object) -> list[dict]:
    if isinstance(value, dict):
        return [value]

    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    return []


def _medium(name: str, description: str) -> str:
    label = f"{name} {description}"

    if re.search(
        r"wi[ -]?fi|wireless|wlan|802\.11",
        label,
        re.IGNORECASE,
    ):
        return "Wi-Fi (inferred)"

    if re.search(
        r"ethernet|gigabit|\blan\b",
        label,
        re.IGNORECASE,
    ):
        return "Ethernet (inferred)"

    return "Other / virtual / unknown"


def parse_snapshot(data: object) -> Snapshot:
    """Validate returned shape and keep collection failures separate from absence."""
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("Adapters"), list)
    ):
        raise DiscoveryError(
            "Windows returned an unexpected adapter data format."
        )

    routes_complete = data.get("RoutesComplete", True)

    if not isinstance(routes_complete, bool):
        raise DiscoveryError(
            "Windows returned an invalid routing collection status."
        )

    warnings = list(_strings(data.get("Warnings")))
    adapters = []

    for raw in _records(data["Adapters"]):
        try:
            index = int(raw["InterfaceIndex"])

            if index < 0:
                raise ValueError("negative index")

            name = _text(raw["Name"])

            if not name:
                raise ValueError("empty adapter name")

            description = _text(raw.get("Description"))

            adapters.append(
                Adapter(
                    index=index,
                    name=name,
                    description=description,
                    status=_text(raw.get("Status")) or "Unknown",
                    link_speed=_text(raw.get("LinkSpeed")),
                    medium=_medium(name, description),
                    ipv4=_strings(raw.get("IPv4")),
                    ipv6=_strings(raw.get("IPv6")),
                    dns=_strings(raw.get("DNS")),
                )
            )

        except (KeyError, ValueError, TypeError):
            warnings.append(
                "Windows returned an invalid adapter entry; it was skipped."
            )

    raw_routes = data.get("Routes")

    if not isinstance(raw_routes, list):
        raw_routes = []
        routes_complete = False
        warnings.append(
            "Windows returned an unexpected default-route data format."
        )

    routes = []

    for raw in raw_routes:
        try:
            if not isinstance(raw, dict):
                raise ValueError("invalid route record")

            prefix = _text(raw["DestinationPrefix"])

            if prefix not in ("0.0.0.0/0", "::/0"):
                continue

            index = int(raw["InterfaceIndex"])
            route_metric = int(raw["RouteMetric"])
            interface_metric = int(raw["InterfaceMetric"])

            if min(index, route_metric, interface_metric) < 0:
                raise ValueError("negative routing value")

            routes.append(
                DefaultRoute(
                    family=(
                        "IPv4"
                        if prefix == "0.0.0.0/0"
                        else "IPv6"
                    ),
                    interface_index=index,
                    next_hop=_text(raw.get("NextHop")),
                    route_metric=route_metric,
                    interface_metric=interface_metric,
                )
            )

        except (KeyError, ValueError, TypeError):
            routes_complete = False
            warnings.append(
                "Windows returned an invalid default route; it was skipped."
            )

    return Snapshot(
        adapters=tuple(
            sorted(adapters, key=lambda adapter: adapter.index)
        ),
        default_routes=tuple(routes),
        warnings=tuple(warnings),
        routes_complete=routes_complete,
    )


def collect_snapshot(*, timeout: float = 15.0) -> Snapshot:
    """Collect Windows network information without creating console windows."""
    if platform.system() != "Windows":
        raise DiscoveryError(
            "This first NetDoctor release currently supports Windows only."
        )

    encoded = base64.b64encode(
        _SCRIPT.encode("utf-16-le")
    ).decode("ascii")

    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-EncodedCommand",
        encoded,
    ]

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
            creationflags=_CREATE_NO_WINDOW,
        )

    except subprocess.TimeoutExpired as exc:
        raise DiscoveryError(
            "Windows network discovery timed out. Try again shortly."
        ) from exc

    except OSError as exc:
        raise DiscoveryError(
            "Could not start Windows PowerShell for network discovery."
        ) from exc

    if process.returncode != 0:
        raise DiscoveryError(
            "Windows could not read network adapters. Confirm the NetAdapter "
            "and NetTCPIP PowerShell modules are available, then try again."
        )

    try:
        payload = json.loads(
            process.stdout.lstrip("\ufeff")
        )

    except (ValueError, TypeError) as exc:
        raise DiscoveryError(
            "Windows returned unreadable network information."
        ) from exc

    return parse_snapshot(payload)