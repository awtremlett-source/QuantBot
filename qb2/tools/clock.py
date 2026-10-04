"""Is this laptop's clock right? Asked, not assumed, every time it matters.

The quote delay is measured as *our clock now* minus *the newest bar's
timestamp*. That subtraction is only as good as the first number. A laptop that
has been asleep, or that has drifted, reports a delay that is wrong by exactly as
much as the clock is wrong -- and nothing about the number looks suspicious. A
delay of "1.6 minutes" from a clock two minutes fast is really "minus 24
seconds", which is impossible, and we would have no way to know.

So the clock is checked against an internet time server (SNTP, UDP port 123) and
the offset is recorded with the reading. **No administrator rights are needed**:
this asks the time, it never sets it. Setting the system clock is the operator's
business and needs admin; being honest about the error does not.

**An unreachable server is never silently trusted.** If no server answers, the
sample is still recorded -- losing a reading would be worse -- but it is marked
unverified, and an unverified reading does not count towards the threshold at
which FACTS row o may be quoted.

The offset is computed the standard way, from four timestamps, so the network's
own round-trip does not get mistaken for clock error:

    offset = ((t2 - t1) + (t3 - t4)) / 2

where t1 is when we sent, t2 and t3 are the server receiving and replying, and t4
is when the reply reached us. A positive offset means **our clock is behind**.
"""

from __future__ import annotations

import socket
import struct
import time
from collections.abc import Sequence
from dataclasses import dataclass

# Seconds between the NTP epoch (1900-01-01) and the Unix epoch (1970-01-01).
NTP_EPOCH_OFFSET = 2_208_988_800

# Three independent operators, tried in order. STARTING FIGURES, tested first.
TIME_SERVERS: tuple[str, ...] = ("time.google.com", "pool.ntp.org",
                                 "time.cloudflare.com")
TIMEOUT_SECONDS = 3.0
# A reply that took longer than this round trip cannot pin the clock tightly
# enough to be worth trusting for a sub-minute measurement.
MAX_ROUND_TRIP_SECONDS = 1.0
# Past this, the clock is wrong enough to matter for a delay measured in minutes.
SUSPECT_OFFSET_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class ClockCheck:
    """What a time server said, or why it said nothing."""

    checked: bool
    offset_seconds: float = 0.0
    round_trip_seconds: float = 0.0
    server: str = ""
    error: str = ""

    @property
    def trustworthy(self) -> bool:
        return self.checked and self.round_trip_seconds <= MAX_ROUND_TRIP_SECONDS

    @property
    def suspect(self) -> bool:
        """The clock is far enough out to make a delay reading meaningless."""
        return self.checked and abs(self.offset_seconds) > SUSPECT_OFFSET_SECONDS

    def as_record(self) -> dict[str, object]:
        """The fields that travel with every sample."""
        return {
            "clock_checked": self.checked,
            "clock_offset_seconds": round(self.offset_seconds, 3),
            "clock_round_trip_seconds": round(self.round_trip_seconds, 3),
            "clock_server": self.server,
            "clock_error": self.error,
            "clock_suspect": self.suspect,
        }


def ask_one(server: str, timeout: float = TIMEOUT_SECONDS) -> ClockCheck:
    """Ask one server. Never raises: a failure is an answer about our knowledge."""
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        request = b"\x1b" + 47 * b"\0"          # LI 0, version 3, mode 3 (client)
        t1 = time.time()
        sock.sendto(request, (server, 123))
        data, _ = sock.recvfrom(48)
        t4 = time.time()
        if len(data) < 48:
            return ClockCheck(False, error=f"{server}: short reply ({len(data)}B)")
        t2 = _timestamp(data, 32)
        t3 = _timestamp(data, 40)
        return ClockCheck(
            checked=True,
            offset_seconds=((t2 - t1) + (t3 - t4)) / 2,
            round_trip_seconds=(t4 - t1) - (t3 - t2),
            server=server)
    except (OSError, struct.error) as exc:
        return ClockCheck(False, error=f"{server}: {type(exc).__name__}: {exc}")
    finally:
        if sock is not None:
            sock.close()


def _timestamp(data: bytes, at: int) -> float:
    seconds, fraction = struct.unpack("!II", data[at:at + 8])
    unix_time: float = seconds + fraction / 2 ** 32 - NTP_EPOCH_OFFSET
    return unix_time


def check(servers: Sequence[str] = TIME_SERVERS,
          timeout: float = TIMEOUT_SECONDS) -> ClockCheck:
    """The first server that answers usefully wins; otherwise say we do not know.

    Trying several is not belt-and-braces: a single unreachable host is common on
    a laptop behind a hotel or office network, and one silent failure would turn
    every reading that day into an unverified one.
    """
    best = ClockCheck(False, error="no servers were tried")
    reasons: list[str] = []
    for server in servers:
        answer = ask_one(server, timeout)
        if answer.trustworthy:
            return answer
        if answer.checked:
            best = answer                 # answered, but too slow to pin tightly
        elif answer.error:
            reasons.append(answer.error)
    if best.checked:
        return best
    return ClockCheck(
        False, error="; ".join(reasons) or "no time server could be reached")
