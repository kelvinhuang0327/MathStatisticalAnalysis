"""First-principles constants for the K20 Shell-1 off-fiber bound (scratch check)."""

from __future__ import annotations

import json
from itertools import combinations
from math import comb

POOL, DRAW, OUT = 49, 6, 3


def co_win(tickets: list[frozenset[int]]) -> int:
    """#(main draw D, special s notin D) where every ticket wins OFFICIAL_ANY_PRIZE.

    Official rule: |t & D| >= 3, or |t & D| == 2 and s in t. Direct DP over
    incidence-mask classes; no 7-set reformulation is assumed.
    """
    k = len(tickets)
    counts = [0] * (1 << k)
    for label in range(1, POOL + 1):
        mask = sum(1 << i for i, t in enumerate(tickets) if label in t)
        counts[mask] += 1
    total = 0
    for smask, mult in enumerate(counts):
        if not mult:
            continue
        need = [OUT - (1 if smask >> i & 1 else 0) for i in range(k)]
        avail = counts[:]
        avail[smask] -= 1
        states = {(0,) + (0,) * k: 1}
        for mask, n in enumerate(avail):
            if not n:
                continue
            nxt: dict[tuple[int, ...], int] = {}
            for st, ways in states.items():
                for take in range(min(n, DRAW - st[0]) + 1):
                    hits = tuple(
                        min(need[i], st[1 + i] + (take if mask >> i & 1 else 0)) for i in range(k)
                    )
                    key = (st[0] + take,) + hits
                    nxt[key] = nxt.get(key, 0) + ways * comb(n, take)
            states = nxt
        total += mult * states.get((DRAW,) + tuple(need), 0)
    return total


def main() -> None:
    out: dict[str, object] = {}
    universe = comb(POOL, DRAW) * (POOL - DRAW)
    out["OUTCOME_UNIVERSE"] = universe
    assert universe == 601_304_088 == 7 * comb(POOL, 7)
    t0 = frozenset(range(1, 7))
    s1 = co_win([t0])
    out["SINGLE_TICKET"] = s1
    closed = 7 * sum(comb(6, j) * comb(43, 7 - j) for j in range(3, 7))
    assert s1 == closed == 18_611_432
    q = [co_win([t0, frozenset(list(range(1, 1 + m)) + list(range(7, 13 - m)))]) for m in range(6)]
    out["PAIR_Q"] = q
    assert q == [107_800, 574_000, 1_695_988, 3_469_942, 6_224_512, 10_776_332]
    # Triple types with pairwise overlap <= 1 (labels: shared ones first).
    A = frozenset({1, 2, 3, 4, 5, 6})
    triple_types = {
        "DISJOINT": [A, frozenset(range(7, 13)), frozenset(range(13, 19))],
        "SINGLE_EDGE": [A, frozenset([1] + list(range(7, 12))), frozenset(range(13, 19))],
        "PATH": [A, frozenset([1, 7, 8, 9, 10, 11]), frozenset([7, 13, 14, 15, 16, 17])],
        "STAR": [A, frozenset([1, 7, 8, 9, 10, 11]), frozenset([1, 13, 14, 15, 16, 17])],
        "TRIANGLE": [A, frozenset([1, 7, 8, 9, 10, 11]), frozenset([2, 7, 13, 14, 15, 16])],
    }
    tw = {name: co_win(ts) for name, ts in triple_types.items()}
    out["TRIPLE_WEIGHTS"] = tw
    assert tw == {"DISJOINT": 0, "SINGLE_EDGE": 0, "PATH": 2_800, "STAR": 7_000, "TRIANGLE": 20_272}
    # S3 = 2800 W + 11872 T3 - 13272 Tstar (W wedges, T3 graph triangles).
    assert 3 * tw["PATH"] + (tw["TRIANGLE"] - 3 * tw["PATH"]) == tw["TRIANGLE"]
    assert tw["TRIANGLE"] - 3 * tw["PATH"] == 11_872
    assert tw["STAR"] - tw["TRIANGLE"] == -13_272
    # Histograms: 49 labels, sum d = 120, sum C(d,2) in {93, 94}.
    def hists(target: int) -> list[dict[int, int]]:
        found = []
        def rec(d: int, left_labels: int, left_inc: int, left_pairs: int, acc: dict[int, int]):
            if d < 0:
                if left_labels == left_inc == left_pairs == 0:
                    found.append({k: v for k, v in acc.items() if v})
                return
            for n in range(left_labels + 1):
                if n * d > left_inc or n * comb(d, 2) > left_pairs:
                    break
                acc[d] = n
                rec(d - 1, left_labels - n, left_inc - n * d, left_pairs - n * comb(d, 2), acc)
            acc[d] = 0
        rec(20, 49, 120, target, {})
        return found
    h93, h94 = hists(93), hists(94)
    out["HIST_93"] = h93
    out["HIST_94"] = h94
    assert h93 == [{3: 22, 2: 27}]
    assert sorted(map(lambda h: sorted(h.items()), h94)) == sorted(
        [sorted({3: 23, 2: 25, 1: 1}.items()), sorted({4: 1, 3: 20, 2: 28}.items())]
    )
    K = 20
    S1 = K * s1
    pairs = comb(K, 2)
    s2_fiber = pairs * q[0] + 93 * (q[1] - q[0])
    s2_shell1 = pairs * q[0] + 94 * (q[1] - q[0])
    out.update(
        S1=S1, S2_FIBER=s2_fiber, S2_SHELL1=s2_shell1,
        S1_MINUS_S2_FIBER=S1 - s2_fiber, S1_MINUS_S2_SHELL1=S1 - s2_shell1,
        OVERLAP2_EXCESS_OVER_FIBER=(q[2] - q[0]) - 2 * (q[1] - q[0]),
        SHELL2_EXCESS_OVER_FIBER=2 * (q[1] - q[0]),
    )
    assert S1 == 372_228_640 and s2_fiber == 63_838_600 and s2_shell1 == 64_304_800
    assert S1 - s2_shell1 == 307_923_840
    incumbent = 313_263_888
    out["INCUMBENT"] = incumbent
    out["S3_THRESHOLD_SHELL1"] = incumbent - (S1 - s2_shell1)
    assert out["S3_THRESHOLD_SHELL1"] == 5_340_048
    out["T_STAR"] = {"P_A": 23 * comb(3, 3), "P_C": 20 + comb(4, 3)}
    # 4-label quartet (P_C): co-win of the four tickets sharing the 4-label.
    quad4 = [frozenset([1] + list(range(2 + 5 * i, 7 + 5 * i))) for i in range(4)]
    out["QUAD_STAR_4_COWIN"] = co_win(quad4)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
