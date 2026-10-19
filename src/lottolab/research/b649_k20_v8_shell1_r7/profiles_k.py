"""Profile filter using F = 2800W + 11872*Tstar + (11872/3)(470 + 1.5K + 4Q - 0.5N1)."""

from __future__ import annotations

import json
import sys
from collections import Counter
from fractions import Fraction
from math import comb

from profiles import parts

# Packing numbers D(k): max triples in a linear 3-graph on k points.
def packing(k: int) -> int:
    r = k % 6
    if r in (1, 3):
        return k * (k - 1) // 6
    if r in (0, 2):
        return k * (k - 2) // 6
    if r == 4:
        return (k * (k - 2) - 2) // 6
    return (k * (k - 1) - 8) // 6

F_TARGET = {"P_A": 5_340_048 + 13_272 * 23, "P_C": 5_340_048 + 13_272 * 24}
TRIPLES = {"P_A": 23, "P_C": 20}


def kmax(deg: list[int], t: list[int], ntrip: int) -> int:
    order = sorted(range(20), key=lambda v: -deg[v])
    d = [deg[v] for v in order]
    tt = [t[v] for v in order]
    total, used, tsum = 0, 0, 0
    for r, v in enumerate(range(20)):
        tsum += tt[v]
        cap_cum = min(packing(r + 1), tsum // 3, ntrip)
        take = min(tt[v], r // 2, cap_cum - used, ntrip - used)
        take = max(take, 0)
        used += take
        total += take * (d[v] - 2)
    return total


def main() -> None:
    stats = Counter()
    surv = []
    for ts in range(6):
        for rest in parts(69 - ts, 19, 6):
            t = [ts] + list(rest)
            deg = [5 + ts] + [6 + x for x in rest]
            w = sum(comb(x, 2) for x in deg)
            k = kmax(deg, t, 23)
            f = 2800 * w + 11872 * 23 + Fraction(11872, 3) * (470 + Fraction(3, 2) * k)
            stats["P_A_ALL"] += 1
            if f > F_TARGET["P_A"]:
                stats["P_A_SURV"] += 1
                surv.append(("P_A", (ts,), rest, w, k, float(f - F_TARGET["P_A"])))
    for qsum in range(0, 21):
        for quad in parts(qsum, 4, 5):
            for rest in parts(60 - qsum, 16, 6):
                t = list(quad) + list(rest)
                deg = [8 + x for x in quad] + [6 + x for x in rest]
                w = sum(comb(x, 2) for x in deg)
                k = kmax(deg, t, 20)
                qmax = min(deg[:4]) - 3
                f = 2800 * w + 11872 * 24 + Fraction(11872, 3) * (470 + Fraction(3, 2) * k + 4 * qmax)
                stats["P_C_ALL"] += 1
                if f > F_TARGET["P_C"]:
                    stats["P_C_SURV"] += 1
                    surv.append(("P_C", quad, rest, w, k, float(f - F_TARGET["P_C"])))
    surv.sort(key=lambda r: -r[-1])
    print(dict(stats))
    for r in surv[:25]:
        print(r)
    json.dump(surv, open(sys.argv[1], "w"))


if __name__ == "__main__":
    main()
