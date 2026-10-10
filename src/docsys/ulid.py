"""ULID minting.

The canonical identifier for records (the documentation system's ADR-028).

A ULID is 128 bits: a 48-bit timestamp (10 Crockford-base32 chars) + 80 bits of
randomness (16 chars), 26 chars total, lexicographically sortable by the leading
timestamp. Two minting modes (ADR-028):
  - chronological (ADRs, append-only): timestamp = real creation time;
  - ordinal (phases, re-orderable): timestamp = a controlled `order` sort-key.

Standard library only. A library (new_ulid, is_ulid, timestamp_of) and a CLI:

    python -m docsys.ulid                       # now
    python -m docsys.ulid --at 2026-08-01       # a given date (chronological)
    python -m docsys.ulid --order 8500000       # an ordinal key (phases)
    python -m docsys.ulid --slug gerund-naming  # prints <ulid>-<slug>
"""
import argparse
import datetime
import re
import secrets
import sys
import time

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # excludes I L O U
_DECODE = {c: i for i, c in enumerate(CROCKFORD)}
ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
MAX_48 = (1 << 48) - 1


def _b32(value, length):
    out = []
    for _ in range(length):
        out.append(CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def new_ulid(ts_ms=None, order=None, rand=None):
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


def is_ulid(s):
    return bool(ULID_RE.match(s or ""))


def timestamp_of(ulid):
    """Return the 48-bit timestamp/order encoded in a ULID."""
    t = 0
    for c in ulid[:10]:
        t = (t << 5) | _DECODE[c]
    return t


def _iso_to_ms(s):
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(s, fmt).replace(tzinfo=datetime.timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    raise SystemExit(f"unparseable --at date: {s!r} (use YYYY-MM-DD or ISO)")


def main():
    ap = argparse.ArgumentParser(description="Mint a ULID.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--at", help="chronological: ISO date/time for the timestamp")
    g.add_argument("--order", type=int, help="ordinal: a controlled sort-key (phases)")
    ap.add_argument("--slug", help="append -<slug> to print a filename stem")
    args = ap.parse_args()

    ts = _iso_to_ms(args.at) if args.at else None
    ulid = new_ulid(ts_ms=ts, order=args.order)
    sys.stdout.write(f"{ulid}-{args.slug}\n" if args.slug else f"{ulid}\n")


if __name__ == "__main__":
    main()
