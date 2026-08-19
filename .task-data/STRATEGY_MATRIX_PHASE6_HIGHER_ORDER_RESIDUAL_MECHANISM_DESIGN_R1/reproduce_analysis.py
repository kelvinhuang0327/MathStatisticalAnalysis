#!/usr/bin/env python3
"""Phase 6 higher-order residual mechanism analysis.

Two independent parts:

1. Re-derives ``structure_comparison.csv`` and ``higher_order_decomposition.csv``
   from the sealed Phase-5 mechanism study
   (``STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1``), read
   read-only via ``git show`` at its pinned commit. That study lives only on
   ``origin/main`` -- local ``main`` diverged before PR #138 merged and does
   not contain these blobs in its working tree, even though the commit
   objects are present locally (already fetched). Nothing here checks out,
   merges, or writes to that commit; nothing in the sealed result is
   recomputed, only re-tabulated.

2. Runs a small bounded synthetic confirmation (toy pools, millisecond
   runtime, no lottery-scale enumeration) that isolates the exact
   combinatorial condition under which three tickets can jointly cover one
   winning combination, at the *real* B649/P638 Zone-1 ratio (draw_size=6,
   minimum_matches=3) and the real T539 ratio (draw_size=5,
   minimum_matches=3) -- not only the toy 3-number/2-match ratio the sealed
   test suite used. This is new computation, but it reuses the identical
   exact enumeration approach already sealed in
   ``src/lottolab/research/low_overlap_geometry_mechanism.py`` (function
   ``exact_hit_multiplicity_decomposition``), applied to synthetic tickets
   only -- no B649/T539/P638 constructor, portfolio, or winning space is
   invoked.
"""

from __future__ import annotations

import csv
import itertools
import json
import subprocess
from pathlib import Path

PINNED_COMMIT = "4d15e2f2d7690ff3be7a3fa0ff5676b8db398640"
RESULT_PATH = "docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json"
K_LADDER = ("3", "5", "10", "15", "20")
OUTPUT_DIR = Path(__file__).resolve().parent


def load_sealed_result() -> dict:
    """Read-only fetch of the sealed result JSON at its pinned origin/main commit."""
    blob = subprocess.run(
        ["git", "show", f"{PINNED_COMMIT}:{RESULT_PATH}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    ).stdout
    return json.loads(blob)


def write_structure_comparison(data: dict) -> None:
    rows = []
    for lottery, lot in data["per_lottery"].items():
        pool, draw = lot["pool_size"], lot["draw_size"]
        for k in K_LADDER:
            cell = lot["per_k"][k]
            for arm in ("ARM_B", "SIDON"):
                arm_data = cell["arms"][arm]
                geo = arm_data["geometry"]
                mult = arm_data["multiplicity_counts"]
                max_c_observed = max(int(c) for c, v in mult.items() if v > 0)
                histogram_str = ";".join(
                    f"r{r}:{c}"
                    for r, c in sorted(geo["ticket_pair_intersection_histogram"].items(), key=lambda kv: int(kv[0]))
                )
                rows.append(
                    [
                        lottery, pool, draw, k, arm,
                        geo["max_pairwise_overlap"],
                        histogram_str,
                        geo["unique_number_coverage"],
                        round(geo["reuse_dispersion_float"], 6),
                        geo["duplicate_count"],
                        arm_data["collision_moments"].get("2", 0),
                        arm_data["collision_moments"].get("3", 0),
                        arm_data["collision_moments"].get("4", 0),
                        max_c_observed,
                        arm_data["covered"],
                        arm_data["q"]["exact"],
                    ]
                )
    path = OUTPUT_DIR / "structure_comparison.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "lottery", "pool_size", "draw_size", "k", "arm", "max_pairwise_overlap",
                "pair_histogram", "unique_number_coverage", "reuse_dispersion",
                "duplicate_count", "S2", "S3", "S4", "max_multiplicity_observed",
                "covered", "q_exact",
            ]
        )
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def write_higher_order_decomposition(data: dict) -> None:
    rows = []
    for lottery, lot in data["per_lottery"].items():
        pool, draw = lot["pool_size"], lot["draw_size"]
        for k in K_LADDER:
            comp = lot["per_k"][k]["comparison"]
            hterms = comp["higher_order_signed_terms"]
            share = comp["pairwise_absolute_contribution_share"]
            share_str = share["exact"] if isinstance(share, dict) else share
            rows.append(
                [
                    lottery, pool, draw, k,
                    comp["delta_covered"],
                    comp["pairwise_component"],
                    hterms.get("3", 0),
                    hterms.get("4", 0),
                    comp["higher_order_residual"],
                    share_str,
                    comp["mechanism_descriptor"],
                ]
            )
    path = OUTPUT_DIR / "higher_order_decomposition.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "lottery", "pool_size", "draw_size", "k", "delta_covered",
                "pairwise_component_P", "T3", "T4", "higher_order_residual_H",
                "pairwise_contribution_share", "mechanism_descriptor",
            ]
        )
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Bounded synthetic confirmation: toy pools only, milliseconds, no lottery data.
# ---------------------------------------------------------------------------


def pairwise_overlaps(portfolio: list[tuple[int, ...]]) -> list[int]:
    return [len(set(a) & set(b)) for a, b in itertools.combinations(portfolio, 2)]


def exact_s3_and_covered(portfolio: list[tuple[int, ...]], pool_size: int, draw_size: int, m: int) -> tuple[int, int]:
    masks = [sum(1 << (n - 1) for n in t) for t in portfolio]
    s3 = covered = 0
    for w in itertools.combinations(range(1, pool_size + 1), draw_size):
        wm = sum(1 << (n - 1) for n in w)
        c = sum((wm & tm).bit_count() >= m for tm in masks)
        covered += c >= 1
        s3 += c >= 3
    return s3, covered


def run_synthetic_confirmation() -> list[list]:
    """Six k=3 toy portfolios: hub vs. triangle sharing pattern, at r=1 and r=2,
    at the real d=6 (B649/P638 Zone-1) and d=5 (T539) draw sizes, m=3 both times.

    Tests the necessary condition derived by hand from exact 3-set
    inclusion-exclusion on (ticket_i intersect w):

        r_ij + r_il + r_jl - |t_i & t_j & t_l| >= 3*m - d

    is required for any winning combination w to hit all three tickets at
    threshold m simultaneously (a nonzero S3 contribution from this triple).
    """
    cases = [
        ("D6M3_HUB_r1", 16, 6, 3, [(1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (1, 12, 13, 14, 15, 16)]),
        ("D6M3_TRIANGLE_r1", 15, 6, 3, [(1, 2, 4, 5, 6, 7), (1, 3, 8, 9, 10, 11), (2, 3, 12, 13, 14, 15)]),
        ("D5M3_HUB_r1", 13, 5, 3, [(1, 2, 3, 4, 5), (1, 6, 7, 8, 9), (1, 10, 11, 12, 13)]),
        ("D5M3_TRIANGLE_r1", 12, 5, 3, [(1, 2, 4, 5, 6), (1, 3, 7, 8, 9), (2, 3, 10, 11, 12)]),
        ("D5M3_HUB_r2", 11, 5, 3, [(1, 2, 3, 4, 5), (1, 2, 6, 7, 8), (1, 2, 9, 10, 11)]),
        ("D5M3_TRIANGLE_r2", 18, 5, 3, [(1, 2, 3, 7, 8), (1, 2, 4, 9, 10), (3, 4, 5, 11, 12)]),
    ]
    rows = []
    for label, pool, draw, m, portfolio in cases:
        portfolio = [tuple(sorted(t)) for t in portfolio]
        overlaps = pairwise_overlaps(portfolio)
        triple_intersection = len(set(portfolio[0]) & set(portfolio[1]) & set(portfolio[2]))
        deficit = sum(overlaps) - triple_intersection
        threshold = 3 * m - draw
        bound_met = deficit >= threshold
        s3, covered = exact_s3_and_covered(portfolio, pool, draw, m)
        assert bound_met == (s3 > 0), f"{label}: bound predicted {bound_met} but observed S3={s3}"
        rows.append([label, pool, draw, m, max(overlaps), overlaps, triple_intersection, deficit, threshold, bound_met, s3, covered])
        print(
            f"{label:20s} max_r={max(overlaps)} triple_int={triple_intersection} "
            f"deficit={deficit} threshold={threshold} bound_met={bound_met!s:5s} -> S3={s3} (covered={covered})"
        )
    return rows


def main() -> None:
    data = load_sealed_result()
    print(f"loaded sealed result: study_id={data['study_id']}  classifications={data['classifications']['mechanism_descriptor_counts']}")
    write_structure_comparison(data)
    write_higher_order_decomposition(data)
    print()
    print("=== bounded synthetic triple-collision-threshold confirmation ===")
    run_synthetic_confirmation()


if __name__ == "__main__":
    main()
