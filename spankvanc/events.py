"""Normalized cue contract and serial message builder.

This is NOT a raw SCTE-104 decoder. The ANC adapter must validate and decode
the complete SCTE message before constructing these events.
"""
from dataclasses import dataclass
import time

from .engine import ConfigError, integer


@dataclass(frozen=True)
class Cue:
    source: str
    event_id: int
    action: str  # out, in, cancel
    pts90k: int | None
    duration90k: int | None = None

    def __post_init__(self):
        if not self.source or len(self.source) > 100:
            raise ConfigError("Cue needs a source identity")
        integer(self.event_id, 0, 0xffffffff, "Cue event id")
        if self.action not in ("out", "in", "cancel"):
            raise ConfigError("Unknown cue action")
        for label, value in (("PTS", self.pts90k), ("Duration", self.duration90k)):
            if value is not None:
                integer(value, 0, (1 << 33) - 1, label)


def serial_pulse(sequence: int, channel: int, milliseconds: int) -> bytes:
    integer(sequence, 1, 0xffffffff, "Serial sequence")
    integer(channel, 1, 4, "GPO channel")
    integer(milliseconds, 10, 10000, "GPO pulse")
    return f"PULSE {sequence} {channel} {milliseconds}\n".encode("ascii")


class Deduplicator:
    """Bounded, expiring duplicate suppression; in/out may share an event ID."""
    def __init__(self, ttl=120, capacity=4096, clock=time.monotonic):
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self.seen = {}

    def accept(self, cue: Cue) -> bool:
        now = self.clock()
        self.seen = {key: expiry for key, expiry in self.seen.items() if expiry > now}
        key = (cue.source, cue.event_id, cue.action)
        if key in self.seen:
            return False
        if len(self.seen) >= self.capacity:
            raise ConfigError("Cue deduplication capacity reached; refusing an untracked pulse")
        self.seen[key] = now + self.ttl
        return True


def pts_distance(target: int, current: int) -> int:
    """Signed shortest difference on the 33-bit MPEG clock, including wrap."""
    for value in (target, current):
        integer(value, 0, (1 << 33) - 1, "PTS")
    return ((target - current + (1 << 32)) % (1 << 33)) - (1 << 32)
