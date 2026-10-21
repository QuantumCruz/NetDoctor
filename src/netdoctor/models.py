
"""Data structures shared by collectors, checks and presentation."""

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class Adapter:
    index: int
    name: str
    description: str
    status: str
    link_speed: str
    medium: str
    ipv4: tuple[str, ...]
    ipv6: tuple[str, ...]
    dns: tuple[str, ...]

    @property
    def is_up(self) -> bool:
        return self.status.casefold() == "up"


@dataclass(frozen=True)
class DefaultRoute:
    family: Literal["IPv4", "IPv6"]
    interface_index: int
    next_hop: str
    route_metric: int
    interface_metric: int

    @property
    def total_metric(self) -> int:
        return self.route_metric + self.interface_metric


@dataclass(frozen=True)
class Snapshot:
    adapters: tuple[Adapter, ...]
    default_routes: tuple[DefaultRoute, ...]
    warnings: tuple[str, ...]
    routes_complete: bool = True

    def preferred_route(self, family: Literal["IPv4", "IPv6"]) -> DefaultRoute | None:
        up_indices = {adapter.index for adapter in self.adapters if adapter.is_up}
        routes = [route for route in self.default_routes
                  if route.family == family and route.interface_index in up_indices]
        return min(routes, key=lambda route: (route.total_metric, route.interface_index), default=None)


@dataclass(frozen=True)
class EndpointCheck:
    host: str
    dns_ok: bool
    tcp_ok: bool
    detail: str


@dataclass(frozen=True)
class Finding:
    severity: Literal["good", "warning", "critical", "info"]
    title: str
    explanation: str
    action: str


@dataclass(frozen=True)
class Report:
    snapshot: Snapshot
    checks: tuple[EndpointCheck, ...]
    findings: tuple[Finding, ...]
    online_status: Literal["reachable", "partial", "unverified", "not_tested"]

    def to_dict(self) -> dict:
        return asdict(self)
