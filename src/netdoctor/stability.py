
"""User-controlled, low-traffic stability watch with bounded local SQLite history.

Only establishes two numeric-IP TCP connections and an optional gateway echo.
No bandwidth transfers, DNS lookups, cloud storage, or adapter changes.
"""

import ipaddress
import sqlite3
import threading
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from netdoctor.crosscheck import connect_tcp_ipv4
from netdoctor.icmp import ping_ipv4
from netdoctor.windows import collect_snapshot


TARGETS = ("1.1.1.1", "8.8.8.8")
INTERVAL_SECONDS = 10
MAX_ROWS = 1000
VIEW_ROWS = 120


@dataclass(frozen=True)
class StabilitySample:
    checked_at: str
    state: str
    first_ok: bool
    second_ok: bool
    gateway_reply: bool | None


def _gateway_address(snapshot) -> str | None:
    route = snapshot.preferred_route("IPv4")
    if route is None:
        return None

    try:
        address = ipaddress.IPv4Address(route.next_hop)
    except (ValueError, TypeError):
        return None

    if (
        address.is_unspecified
        or address.is_multicast
        or address.is_loopback
    ):
        return None

    return str(address)


def take_sample(
    gateway: str | None,
    *,
    tcp_probe: Callable = connect_tcp_ipv4,
    icmp_probe: Callable = ping_ipv4,
    now: Callable = lambda: datetime.now(timezone.utc),
) -> StabilitySample:
    """One check; a probe exception is an unavailable check, not an outage."""
    successes = []

    for address in TARGETS:
        try:
            result = tcp_probe(
                address,
                port=443,
                timeout=1.2,
            )
        except Exception as exc:
            raise RuntimeError(
                "A connection probe could not run."
            ) from exc

        successes.append(
            result.status == "connected"
        )

    echo = None

    if gateway is not None:
        try:
            response = icmp_probe(
                gateway,
                timeout_ms=700,
            )

            if response.status == "reply":
                echo = True

            elif response.status in (
                "timeout",
                "unreachable",
            ):
                echo = False

        except Exception:
            pass

    count = sum(successes)

    return StabilitySample(
        checked_at=now().astimezone(
            timezone.utc
        ).isoformat(),
        state=(
            "ok" if count == 2
            else "mixed" if count == 1
            else "failed"
        ),
        first_ok=successes[0],
        second_ok=successes[1],
        gateway_reply=echo,
    )


class StabilityHistory:
    """Small durable history; one SQLite connection per short transaction."""

    def __init__(
        self,
        path: Path,
        *,
        max_rows: int = MAX_ROWS,
    ):
        if (
            not isinstance(max_rows, int)
            or max_rows < 1
        ):
            raise ValueError(
                "max_rows must be positive"
            )

        self.path = Path(path)
        self.max_rows = max_rows
        self._lock = threading.Lock()

    def _connect(self):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = sqlite3.connect(
            self.path,
            timeout=3,
        )

        connection.execute(
            "PRAGMA busy_timeout=3000"
        )

        connection.execute(
            """CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY,
                checked_at TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('ok', 'mixed', 'failed')),
                first_ok INTEGER NOT NULL,
                second_ok INTEGER NOT NULL,
                gateway_reply INTEGER
            )"""
        )

        return connection

    def append(
        self,
        sample: StabilitySample,
    ):
        with self._lock, closing(
            self._connect()
        ) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO samples "
                    "(checked_at, state, first_ok, second_ok, gateway_reply) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        sample.checked_at,
                        sample.state,
                        int(sample.first_ok),
                        int(sample.second_ok),
                        (
                            None
                            if sample.gateway_reply is None
                            else int(sample.gateway_reply)
                        ),
                    ),
                )

                conn.execute(
                    """DELETE FROM samples WHERE id NOT IN (
                        SELECT id FROM samples
                        ORDER BY id DESC LIMIT ?
                    )""",
                    (self.max_rows,),
                )

    def recent(
        self,
        limit: int = VIEW_ROWS,
    ) -> list[dict]:
        if (
            not isinstance(limit, int)
            or limit < 1
            or limit > MAX_ROWS
        ):
            raise ValueError(
                "Invalid history limit"
            )

        with self._lock, closing(
            self._connect()
        ) as conn:
            rows = conn.execute(
                "SELECT checked_at, state, first_ok, second_ok, gateway_reply "
                "FROM samples ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            asdict(
                StabilitySample(
                    checked_at=row[0],
                    state=row[1],
                    first_ok=bool(row[2]),
                    second_ok=bool(row[3]),
                    gateway_reply=(
                        None
                        if row[4] is None
                        else bool(row[4])
                    ),
                )
            )
            for row in reversed(rows)
        ]


class StabilityMonitor:
    """Single stoppable monitor; max 30 minutes per user-started session."""

    def __init__(
        self,
        history: StabilityHistory,
        *,
        collector: Callable = collect_snapshot,
        sampler: Callable = take_sample,
        interval: float = INTERVAL_SECONDS,
    ):
        if interval <= 0:
            raise ValueError(
                "interval must be positive"
            )

        self.history = history
        self.collector = collector
        self.sampler = sampler
        self.interval = interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._active = False
        self._message = "Monitoring has not started."
        self._duration_minutes = None

    def start(
        self,
        minutes: int = 10,
    ) -> dict:
        if (
            minutes not in (5, 10, 30)
            or isinstance(minutes, bool)
        ):
            return {
                "ok": False,
                "message": "Choose 5, 10 or 30 minutes.",
            }

        with self._lock:
            if self._active:
                return {
                    "ok": False,
                    "message": "The stability watch is already running.",
                }

            try:
                self.history.recent(limit=1)
            except (OSError, sqlite3.Error):
                return {
                    "ok": False,
                    "message": "Local connection history could not be opened.",
                }

            self._stop.clear()
            self._active = True
            self._duration_minutes = minutes
            self._message = "Monitoring in progress."

            self._thread = threading.Thread(
                target=self._run,
                args=(minutes * 60,),
                daemon=True,
                name="NetDoctorStabilityWatch",
            )

            try:
                self._thread.start()
            except RuntimeError:
                self._active = False
                self._message = "Monitoring could not start."

                return {
                    "ok": False,
                    "message": self._message,
                }

        return {
            "ok": True,
            "message": "Stability watch started.",
        }

    def _run(
        self,
        duration_seconds: int,
    ):
        from time import monotonic

        deadline = monotonic() + duration_seconds
        gateway = None

        try:
            try:
                gateway = _gateway_address(
                    self.collector()
                )
            except Exception:
                pass

            while (
                not self._stop.is_set()
                and monotonic() < deadline
            ):
                started = monotonic()

                try:
                    sample = self.sampler(gateway)
                    self.history.append(sample)
                except Exception:
                    with self._lock:
                        self._message = (
                            "A check could not run; monitoring stopped "
                            "without recording a false outage."
                        )
                    break

                delay = max(
                    0,
                    self.interval - (
                        monotonic() - started
                    ),
                )

                self._stop.wait(
                    min(
                        delay,
                        max(
                            0,
                            deadline - monotonic(),
                        ),
                    )
                )

            else:
                with self._lock:
                    self._message = (
                        "Monitoring stopped."
                        if self._stop.is_set()
                        else "Monitoring session completed."
                    )

        finally:
            with self._lock:
                self._active = False

    def stop(self) -> dict:
        with self._lock:
            if not self._active:
                return {
                    "ok": True,
                    "message": "No monitor is running.",
                }

            self._stop.set()
            self._message = (
                "Stopping after the current connection check…"
            )

            return {
                "ok": True,
                "message": self._message,
            }

    def status(self) -> dict:
        with self._lock:
            running = self._active
            message = self._message
            duration = self._duration_minutes

        try:
            samples = self.history.recent()
        except (OSError, sqlite3.Error):
            return {
                "running": running,
                "message": "Local history is unavailable.",
                "samples": [],
                "counts": {
                    "ok": 0,
                    "mixed": 0,
                    "failed": 0,
                },
                "duration_minutes": duration,
            }

        counts = {
            name: sum(
                sample["state"] == name
                for sample in samples
            )
            for name in (
                "ok",
                "mixed",
                "failed",
            )
        }

        return {
            "running": running,
            "message": message,
            "duration_minutes": duration,
            "interval_seconds": self.interval,
            "samples": samples,
            "counts": counts,
        }
