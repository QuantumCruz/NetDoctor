"""User-started, low-traffic connection watch with network-scoped local history.

Two numeric-IP TCP checks and optionally one gateway echo per round.
No speed downloads, location access, account, or network modifications.
"""

import ipaddress
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from netdoctor.crosscheck import connect_tcp_ipv4
from netdoctor.icmp import ping_ipv4
from netdoctor.network_context import network_signature
from netdoctor.windows import collect_snapshot

TARGETS = ("1.1.1.1", "8.8.8.8")
INTERVAL_SECONDS = 10
MAX_ROWS = 1000
VIEW_ROWS = 120
CONTEXT_REFRESH_SECONDS = 10


@dataclass(frozen=True)
class StabilitySample:
    checked_at: str
    state: str
    first_ok: bool
    second_ok: bool
    gateway_reply: bool | None


def _gateway_address(snapshot) -> str | None:
    if snapshot is None:
        return None

    try:
        route = snapshot.preferred_route("IPv4")
    except (AttributeError, TypeError):
        return None

    if route is None:
        return None

    try:
        address = ipaddress.IPv4Address(route.next_hop)
    except (ValueError, TypeError):
        return None

    if address.is_unspecified or address.is_multicast or address.is_loopback:
        return None

    return str(address)


def take_sample(
    gateway: str | None,
    *,
    tcp_probe: Callable = connect_tcp_ipv4,
    icmp_probe: Callable = ping_ipv4,
    now: Callable = lambda: datetime.now(timezone.utc),
) -> StabilitySample:
    """A probe exception is not recorded as a network outage."""
    successes = []

    for address in TARGETS:
        try:
            result = tcp_probe(address, port=443, timeout=1.2)
        except Exception as exc:
            raise RuntimeError("A connection probe could not run.") from exc

        successes.append(result.status == "connected")

    echo = None

    if gateway is not None:
        try:
            response = icmp_probe(gateway, timeout_ms=700)

            if response.status == "reply":
                echo = True
            elif response.status in ("timeout", "unreachable"):
                echo = False
        except Exception:
            pass

    count = sum(successes)

    return StabilitySample(
        checked_at=now().astimezone(timezone.utc).isoformat(),
        state="ok" if count == 2 else "mixed" if count == 1 else "failed",
        first_ok=successes[0],
        second_ok=successes[1],
        gateway_reply=echo,
    )


class StabilityHistory:
    """Durable SQLite ring of samples, with legacy rows preserved unassigned."""

    def __init__(self, path: Path, *, max_rows: int = MAX_ROWS):
        if (
            isinstance(max_rows, bool)
            or not isinstance(max_rows, int)
            or max_rows < 1
        ):
            raise ValueError("max_rows must be positive")

        self.path = Path(path)
        self.max_rows = max_rows
        self._lock = threading.Lock()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.path, timeout=3)

        try:
            conn.execute("PRAGMA busy_timeout=3000")

            conn.execute(
                """CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY,
                    checked_at TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('ok','mixed','failed')),
                    first_ok INTEGER NOT NULL,
                    second_ok INTEGER NOT NULL,
                    gateway_reply INTEGER,
                    network_key TEXT
                )"""
            )

            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(samples)")
            }

            if "network_key" not in columns:
                conn.execute(
                    "ALTER TABLE samples ADD COLUMN network_key TEXT"
                )

            conn.commit()
            return conn

        except Exception:
            conn.close()
            raise

    def append(
        self,
        sample: StabilitySample,
        *,
        network_key: str | None = None,
    ):
        if network_key is not None and (
            not isinstance(network_key, str)
            or not network_key
            or len(network_key) > 100
        ):
            raise ValueError("Invalid network history key")

        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """INSERT INTO samples
                    (checked_at, state, first_ok, second_ok, gateway_reply, network_key)
                    VALUES (?, ?, ?, ?, ?, ?)""",
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
                        network_key,
                    ),
                )

                conn.execute(
                    """DELETE FROM samples WHERE id NOT IN
                    (SELECT id FROM samples ORDER BY id DESC LIMIT ?)""",
                    (self.max_rows,),
                )

    def recent(
        self,
        limit: int = VIEW_ROWS,
        *,
        network_key: str | None = None,
    ) -> list[dict]:
        """A key filters by network. Omitted key preserves legacy API behavior."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_ROWS
        ):
            raise ValueError("Invalid history limit")

        with self._lock, closing(self._connect()) as conn:
            if network_key is None:
                rows = conn.execute(
                    """SELECT checked_at, state, first_ok,
                    second_ok, gateway_reply
                    FROM samples ORDER BY id DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT checked_at, state, first_ok,
                    second_ok, gateway_reply
                    FROM samples WHERE network_key = ?
                    ORDER BY id DESC LIMIT ?""",
                    (network_key, limit),
                ).fetchall()

        return [
            asdict(
                StabilitySample(
                    checked_at=row[0],
                    state=row[1],
                    first_ok=bool(row[2]),
                    second_ok=bool(row[3]),
                    gateway_reply=(
                        None if row[4] is None else bool(row[4])
                    ),
                )
            )
            for row in reversed(rows)
        ]

    def other_count(self, network_key: str | None) -> int:
        """Count stored observations excluded from the selected view."""
        with self._lock, closing(self._connect()) as conn:
            if network_key is None:
                return int(
                    conn.execute(
                        "SELECT COUNT(*) FROM samples"
                    ).fetchone()[0]
                )

            return int(
                conn.execute(
                    """SELECT COUNT(*) FROM samples
                    WHERE network_key IS NULL OR network_key <> ?""",
                    (network_key,),
                ).fetchone()[0]
            )


class StabilityMonitor:
    """One explicit session; stop on a detected default-route configuration change."""

    def __init__(
        self,
        history: StabilityHistory,
        *,
        collector: Callable = collect_snapshot,
        sampler: Callable = take_sample,
        interval: float = INTERVAL_SECONDS,
    ):
        if (
            not isinstance(interval, (int, float))
            or interval <= 0
        ):
            raise ValueError("interval must be positive")

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

        self._session_key: str | None = None
        self._session_signature: str | None = None
        self._cached_key: str | None = None
        self._cache_time = float("-inf")

    def _snapshot(self):
        try:
            return self.collector()
        except Exception:
            return None

    def _current_signature(self) -> str | None:
        now = time.monotonic()

        with self._lock:
            if now - self._cache_time < CONTEXT_REFRESH_SECONDS:
                return self._cached_key

        snapshot = self._snapshot()
        key = network_signature(snapshot)

        with self._lock:
            self._cached_key = key
            self._cache_time = time.monotonic()

        return key

    def start(self, minutes: int = 10) -> dict:
        if isinstance(minutes, bool) or minutes not in (5, 10, 30):
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
            self._session_key = None
            self._session_signature = None
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

    def _run(self, duration_seconds: int):
        deadline = time.monotonic() + duration_seconds

        snapshot = self._snapshot()
        initial_signature = network_signature(snapshot)
        session_key = (
            initial_signature
            or f"unknown-session-{uuid.uuid4().hex}"
        )
        gateway = _gateway_address(snapshot)

        with self._lock:
            self._session_key = session_key
            self._session_signature = initial_signature
            self._cached_key = initial_signature
            self._cache_time = time.monotonic()

        try:
            while (
                not self._stop.is_set()
                and time.monotonic() < deadline
            ):
                started = time.monotonic()
                current = self._snapshot()
                current_signature = network_signature(current)

                if (
                    initial_signature is not None
                    and current_signature is not None
                    and current_signature != initial_signature
                ):
                    with self._lock:
                        self._cached_key = current_signature
                        self._cache_time = time.monotonic()
                        self._message = (
                            "Network configuration changed. This watch ended "
                            "to avoid mixing results from different connections."
                        )
                    break

                if self._stop.is_set():
                    break

                try:
                    sample = self.sampler(gateway)
                    self.history.append(
                        sample,
                        network_key=session_key,
                    )
                except Exception:
                    with self._lock:
                        self._message = (
                            "A check could not run; monitoring stopped "
                            "without recording a false outage."
                        )
                    break

                delay = max(
                    0,
                    self.interval - (time.monotonic() - started),
                )

                self._stop.wait(
                    min(
                        delay,
                        max(0, deadline - time.monotonic()),
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
                if (
                    self._stop.is_set()
                    and self._message.startswith("Stopping after")
                ):
                    self._message = "Monitoring stopped."

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
        current_key = self._current_signature()

        with self._lock:
            running = self._active
            message = self._message
            duration = self._duration_minutes
            session_key = self._session_key
            session_signature = self._session_signature

        if running and session_key and session_signature is None:
            visible_key = session_key
            scope = "session"
            notice = (
                "Windows route details were not available when this session began. "
                "Showing this session alone, without combining earlier history."
            )

        elif current_key is not None:
            visible_key = current_key
            scope = "current"
            notice = (
                "Showing only checks from the current route configuration. "
                "Older or other-network checks are kept separately. "
                "Matching route details do not prove the same physical Wi-Fi."
            )

        elif running and session_key:
            visible_key = session_key
            scope = "session"
            notice = (
                "Windows route details are unavailable. Showing only this "
                "monitoring session, not combined earlier history."
            )

        else:
            visible_key = None
            scope = "unverified"
            notice = (
                "Network configuration could not be identified. Previous "
                "history is preserved but excluded until the route is known."
            )

        try:
            samples = (
                self.history.recent(network_key=visible_key)
                if visible_key is not None
                else []
            )
            archived = self.history.other_count(visible_key)

        except (OSError, sqlite3.Error):
            samples = []
            archived = 0
            notice = "Local connection history is unavailable."

        counts = {
            key: sum(item["state"] == key for item in samples)
            for key in ("ok", "mixed", "failed")
        }

        return {
            "running": running,
            "message": message,
            "duration_minutes": duration,
            "interval_seconds": self.interval,
            "samples": samples,
            "counts": counts,
            "history_scope": scope,
            "history_notice": notice,
            "other_network_count": archived,
        }