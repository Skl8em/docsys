"""ULID minting.

The canonical identifier for records (the documentation system's ADR-028).

A ULID is 128 bits: a 48-bit timestamp (10 Crockford-base32 chars) + 80 bits of
randomness (16 chars), 26 chars total, lexicographically sortable by the leading
timestamp. Two minting modes (ADR-028):
  - chronological (ADRs, append-only): timestamp = real creation time;
  - ordinal (phases, re-orderable): timestamp = a controlled `order` sort-key.

Standard library only. A library (new_ulid, is_ulid, timestamp_of, at_to_ms); the
command line is `docsys id` (see cli.py).
"""

import datetime
import re
import secrets
import time
from typing import Final

CROCKFORD: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # excludes I L O U
_DECODE: Final = {c: i for i, c in enumerate(CROCKFORD)}
ULID_RE: Final = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
MAX_48: Final = (1 << 48) - 1


def _b32(value: int, length: int) -> str:
    out: list[str] = []
    for _ in range(length):
        out.append(CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def new_ulid(ts_ms: int | None = None, order: int | None = None, rand: int | None = None) -> str:
    """Mint a ULID. Pass `order` for the ordinal mode, `ts_ms` for a specific
    millisecond timestamp, or neither for `now`."""
    if order is not None:
        t = int(order)
    elif ts_ms is not None:
        t = int(ts_ms)
    else:
        t = int(time.time() * 1000)
    if not (0 <= t <= MAX_48):
        raise ValueError(f"timestamp/order {t} out of 48-bit range [0, {MAX_48}]")
    r = secrets.randbits(80) if rand is None else int(rand)
    return _b32(t, 10) + _b32(r, 16)


def is_ulid(s: str | None) -> bool:
    return bool(ULID_RE.match(s or ""))


def timestamp_of(ulid: str) -> int:
    """Return the 48-bit timestamp/order encoded in a ULID."""
    t = 0
    for c in ulid[:10]:
        t = (t << 5) | _DECODE[c]
    return t


def at_to_ms(text: str) -> int:
    """Milliseconds since the epoch of an ISO date or date-time, read as UTC."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(text, fmt).replace(tzinfo=datetime.UTC)
        except ValueError:
            continue
        return int(dt.timestamp() * 1000)
    raise ValueError(f"unparseable date: {text!r} (use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
