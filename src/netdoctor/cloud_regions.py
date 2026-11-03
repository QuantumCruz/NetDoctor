
"""On-demand regional API endpoint responsiveness checks for NetDoctor.

Tests TCP connection establishment to documented HTTPS API endpoints. This is
not ICMP ping, VM latency, availability monitoring, or a provider speed rating.
No credentials, subscriptions, downloads or background probes are involved.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable


@dataclass(frozen=True)
class RegionEndpoint:
    provider: str
    region: str
    location: str
    hostname: str


# Documented regional HTTPS API endpoints.
# AWS: https://docs.aws.amazon.com/ec2/latest/devguide/ec2-endpoints.html
# Oracle: https://docs.oracle.com/en-us/iaas/api/
ENDPOINTS = (
    RegionEndpoint(
        "AWS",
        "af-south-1",
        "Cape Town, South Africa",
        "ec2.af-south-1.amazonaws.com",
    ),
    RegionEndpoint(
        "AWS",
        "me-south-1",
        "Bahrain",
        "ec2.me-south-1.amazonaws.com",
    ),
    RegionEndpoint(
        "AWS",
        "eu-west-2",
        "London, UK",
        "ec2.eu-west-2.amazonaws.com",
    ),
    RegionEndpoint(
        "AWS",
        "eu-central-1",
        "Frankfurt, Germany",
        "ec2.eu-central-1.amazonaws.com",
    ),
    RegionEndpoint(
        "AWS",
        "us-east-1",
        "Northern Virginia, USA",
        "ec2.us-east-1.amazonaws.com",
    ),
    RegionEndpoint(
        "Oracle",
        "af-johannesburg-1",
        "Johannesburg, South Africa",
        "iaas.af-johannesburg-1.oraclecloud.com",
    ),
    RegionEndpoint(
        "Oracle",
        "me-dubai-1",
        "Dubai, UAE",
        "iaas.me-dubai-1.oraclecloud.com",
    ),
    RegionEndpoint(
        "Oracle",
        "uk-london-1",
        "London, UK",
        "iaas.uk-london-1.oraclecloud.com",
    ),
    RegionEndpoint(
        "Oracle",
        "eu-frankfurt-1",
        "Frankfurt, Germany",
        "iaas.eu-frankfurt-1.oraclecloud.com",
    ),
    RegionEndpoint(
        "Oracle",
        "us-ashburn-1",
        "Ashburn, USA",
        "iaas.us-ashburn-1.oraclecloud.com",
    ),
)


@dataclass(frozen=True)
class RegionResult:
    provider: str
    region: str
    location: str
    hostname: str
    status: str
    attempts: int
    successful: int
    median_ms: float | None
    variation_ms: float | None
    samples_ms: tuple[float, ...]
    note: str


def _tcp_connect_ms(ipv4: str, port: int, timeout: float) -> float:
    """Measure only an IPv4 TCP handshake; exclude DNS lookup time."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        start = time.perf_counter()
        connection.connect((ipv4, port))
        return (time.perf_counter() - start) * 1000


def _validate_limits(attempts: int, timeout: float) -> None:
    if (
        isinstance(attempts, bool)
        or not isinstance(attempts, int)
        or not 1 <= attempts <= 5
    ):
        raise ValueError("Attempts must be between 1 and 5.")

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or not 0.2 <= timeout <= 5
    ):
        raise ValueError("Timeout must be between 0.2 and 5 seconds.")


def measure_region(
    endpoint: RegionEndpoint,
    *,
    attempts: int = 3,
    timeout: float = 1.5,
    resolver: Callable | None = None,
    connector: Callable | None = None,
) -> RegionResult:
    """Run bounded TCP attempts to one preset endpoint."""
    _validate_limits(attempts, timeout)
    resolver = resolver or socket.getaddrinfo
    connector = connector or _tcp_connect_ms

    common = dict(
        provider=endpoint.provider,
        region=endpoint.region,
        location=endpoint.location,
        hostname=endpoint.hostname,
        attempts=attempts,
    )

    try:
        answers = resolver(
            endpoint.hostname,
            443,
            socket.AF_INET,
            socket.SOCK_STREAM,
        )
        ipv4 = next(
            result[4][0]
            for result in answers
            if (
                result[0] == socket.AF_INET
                and result[4]
                and result[4][0]
            )
        )
    except (OSError, StopIteration, ValueError, TypeError, IndexError):
        return RegionResult(
            **common,
            status="unavailable",
            successful=0,
            median_ms=None,
            variation_ms=None,
            samples_ms=(),
            note="DNS lookup did not return a usable IPv4 address.",
        )

    measurements = []

    for _ in range(attempts):
        try:
            elapsed_ms = float(connector(ipv4, 443, timeout))

            if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
                raise ValueError("Invalid elapsed time")

            measurements.append(elapsed_ms)

        except (OSError, ValueError, TypeError, OverflowError):
            # A failed TCP connection is not evidence of an outage.
            continue

    if not measurements:
        return RegionResult(
            **common,
            status="unavailable",
            successful=0,
            median_ms=None,
            variation_ms=None,
            samples_ms=(),
            note=(
                "No TCP connection completed; filtering or timeout "
                "is possible."
            ),
        )

    median = statistics.median(measurements)
    deviation = statistics.median(
        abs(value - median) for value in measurements
    )
    successes = len(measurements)

    return RegionResult(
        **common,
        status="measured" if successes == attempts else "partial",
        successful=successes,
        median_ms=round(median, 2),
        variation_ms=(
            round(deviation, 2) if successes >= 2 else None
        ),
        samples_ms=tuple(round(value, 2) for value in measurements),
        note=(
            "All requested TCP handshakes completed."
            if successes == attempts
            else (
                "Some attempts did not connect; this is not a "
                "packet-loss measurement."
            )
        ),
    )


def compare_regions(
    *,
    provider: str = "all",
    attempts: int = 3,
    timeout: float = 1.5,
    endpoints: Iterable[RegionEndpoint] = ENDPOINTS,
    workers: int = 4,
    resolver: Callable | None = None,
    connector: Callable | None = None,
) -> dict:
    """Compare curated regions concurrently, only when requested."""
    _validate_limits(attempts, timeout)

    if provider not in ("all", "AWS", "Oracle"):
        raise ValueError("Provider must be all, AWS or Oracle.")

    if (
        isinstance(workers, bool)
        or not isinstance(workers, int)
        or not 1 <= workers <= 8
    ):
        raise ValueError("Workers must be between 1 and 8.")

    selected = tuple(
        endpoint
        for endpoint in endpoints
        if provider == "all" or endpoint.provider == provider
    )

    if not selected:
        raise ValueError("No endpoints were selected.")

    if len(selected) > 30:
        raise ValueError("Too many endpoints were selected.")

    results = []

    with ThreadPoolExecutor(
        max_workers=min(workers, len(selected))
    ) as pool:
        future_map = {
            pool.submit(
                measure_region,
                endpoint,
                attempts=attempts,
                timeout=timeout,
                resolver=resolver,
                connector=connector,
            ): endpoint
            for endpoint in selected
        }

        for future in as_completed(future_map):
            results.append(future.result())

    results.sort(
        key=lambda item: (
            item.median_ms is None,
            (
                float("inf")
                if item.median_ms is None
                else item.median_ms
            ),
            item.provider,
            item.region,
        )
    )

    # One successful handshake is insufficient for a recommendation.
    eligible = [
        item for item in results if item.successful >= 2
    ]
    best = eligible[0] if eligible else None

    return {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "IPv4 TCP connection setup to regional HTTPS API "
            "endpoints, port 443"
        ),
        "attempts_per_endpoint": attempts,
        "timeout_seconds": timeout,
        "provider_filter": provider,
        "best_observed_endpoint": (
            {
                "provider": best.provider,
                "region": best.region,
                "location": best.location,
                "median_ms": best.median_ms,
            }
            if best else None
        ),
        "results": [
            asdict(result) for result in results
        ],
        "disclaimer": (
            "These are short TCP handshake samples to API endpoints, "
            "not ICMP ping, cloud VM latency, throughput, packet loss "
            "or guaranteed game latency. An endpoint failure can "
            "reflect firewall restrictions or timeout. The fastest "
            "observed endpoint is not necessarily the best cloud provider."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare short TCP connection times to official "
            "cloud-region API endpoints."
        )
    )

    parser.add_argument(
        "--provider",
        choices=("all", "AWS", "Oracle"),
        default="all",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        choices=range(1, 6),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.5,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON.",
    )

    args = parser.parse_args(argv)

    try:
        report = compare_regions(
            provider=args.provider,
            attempts=args.attempts,
            timeout=args.timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            "NetDoctor | Cloud region responsiveness (TCP/443)\n"
        )

        for result in report["results"]:
            reading = (
                f'{result["median_ms"]:.2f} ms'
                if result["median_ms"] is not None
                else "Unavailable"
            )

            print(
                f'{result["provider"]:7} '
                f'{result["location"]:29} '
                f'{reading:>13}  '
                f'({result["successful"]}/{result["attempts"]} connected)'
            )

        winner = report["best_observed_endpoint"]

        if winner:
            print(
                f'\nFastest measured endpoint: '
                f'{winner["provider"]} '
                f'{winner["location"]} '
                f'({winner["median_ms"]:.2f} ms)'
            )
        else:
            print(
                "\nNo endpoint had enough successful samples "
                "to compare reliably."
            )

        print("\n" + report["disclaimer"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
