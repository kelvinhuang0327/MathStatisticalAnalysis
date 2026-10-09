"""Enumerate Shell-1 per-ticket profiles and apply analytic triangle caps (scratch)."""

from __future__ import annotations

import json
import sys
from collections import Counter
from math import comb

THRESH = 5_340_048
TSTAR = {"P_A": 23, "P_C": 24}


def parts(total: int, n: int, hi: int, lo: int = 0):
    """Non-increasing tuples of length n, entries in [lo, hi], summing to total."""
    if n == 0:
        if total == 0:
            yield ()
        return
    for first in range(min(hi, total), lo - 1, -1):
        if first * n < total:
            break
        for rest in parts(total - first, n - 1, first, lo):
            yield (first,) + rest


def profiles():
    # P_A: singleton ticket with t_s in 0..5, 19 others in 0..6, sum t = 69.
    for ts in range(6):
        for rest in parts(69 - ts, 19, 6):
            yield "P_A", (ts,), rest
    # P_C: 4 quad tickets in 0..5, 16 others in 0..6, sum t = 60.
    for qsum in range(0, 21):
        for quad in parts(qsum, 4, 5):
            for rest in parts(60 - qsum, 16, 6):
                yield "P_C", quad, rest


def degrees(kind, special, rest):
    if kind == "P_A":
        return [5 + special[0]] + [6 + t for t in rest]
    return [8 + t for t in special] + [6 + t for t in rest]


def edge_min_cap(deg):
    d = sorted(deg, reverse=True)
    total = sum(x * min(x, i) for i, x in enumerate(d))
    edges = sum(deg) // 2
    return (total - edges) // 3


def s3(kind, w, t3):
    return 2800 * w + 11872 * t3 - 13272 * TSTAR[kind]


def main() -> None:
    stats = Counter()
    survivors = []
    for kind, special, rest in profiles():
        deg = degrees(kind, special, rest)
        assert sum(deg) == 188
        w = sum(comb(x, 2) for x in deg)
        cap_w = w // 3
        cap_e = edge_min_cap(deg)
        cap = min(cap_w, cap_e)
        stats[kind, "ALL"] += 1
        if s3(kind, w, cap_w) > THRESH:
            stats[kind, "SURVIVE_W3"] += 1
        if s3(kind, w, cap) > THRESH:
            stats[kind, "SURVIVE_W3_EDGE"] += 1
            need = (THRESH + 13272 * TSTAR[kind] - 2800 * w) // 11872  # max allowed T3
            survivors.append(
                {"KIND": kind, "SPECIAL": special, "REST": rest, "W": w, "CAP": cap, "ALLOWED_T3": need,
                 "COARSE_S3": s3(kind, w, cap)}
            )
    survivors.sort(key=lambda r: -r["COARSE_S3"])
    print(json.dumps({str(k): v for k, v in stats.items()}, indent=1))
    print("max W by kind:", {k: max(r["W"] for r in survivors if r["KIND"] == k) for k in ("P_A", "P_C") if any(r["KIND"] == k for r in survivors)})
    for r in survivors[:15]:
        print(r)
    json.dump(survivors, open(sys.argv[1], "w"))


if __name__ == "__main__":
    main()
