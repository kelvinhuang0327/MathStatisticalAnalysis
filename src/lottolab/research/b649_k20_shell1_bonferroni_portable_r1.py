#!/usr/bin/env python3
"""Exact, stdlib-only verification of Shell-1 Bonferroni event constants."""

from __future__ import annotations

import argparse
import hashlib
import json
from math import comb
from pathlib import Path


POOL = 49
DRAW_SIZE = 6
SPECIALS_OUTSIDE_DRAW = POOL - DRAW_SIZE
TICKET_SIZE = 6
TICKET_COUNT = 20
SHELL1_OVERLAP_ONE_PAIRS = 94
CANONICAL_K20_COUNT = 313_263_888
CANONICAL_K20_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"

REFERENCE = {
    "OUTCOME_UNIVERSE": 601_304_088,
    "SINGLE_TICKET_WINNING_OUTCOMES": 18_611_432,
    "S1": 372_228_640,
    "PAIR_Q0": 107_800,
    "PAIR_Q1": 574_000,
    "S2": 64_304_800,
    "S1_MINUS_S2": 307_923_840,
    "TRIPLE_PATH": 2_800,
    "TRIPLE_STAR": 7_000,
    "TRIPLE_TRIANGLE": 20_272,
}

# A, B, C are bits 0, 1, 2. Region keys are the ticket-membership masks.
# Mask 0 is the part of the 49-label pool outside all three tickets.
MOTIFS = {
    "TRIPLE_PATH": {
        "definition": "A-B and B-C overlap in distinct labels; A and C are disjoint",
        "regions": {0: 33, 1: 5, 2: 4, 3: 1, 4: 5, 6: 1},
    },
    "TRIPLE_STAR": {
        "definition": "all three tickets contain the same one label; no other overlaps",
        "regions": {0: 33, 1: 5, 2: 5, 4: 5, 7: 1},
    },
    "TRIPLE_TRIANGLE": {
        "definition": "each ticket pair overlaps once, on three distinct labels",
        "regions": {0: 34, 1: 4, 2: 4, 3: 1, 4: 4, 5: 1, 6: 1},
    },
}


def count_seven_sets(region_sizes: dict[int, int], ticket_count: int) -> int:
    """Count 7-subsets meeting every ticket in at least 3 labels.

    This is a bounded Venn-region dynamic count. It enumerates at most the
    ways to distribute seven selected labels among eight membership classes,
    never the full 7-subset universe.
    """
    sizes = {mask: region_sizes.get(mask, 0) for mask in range(1 << ticket_count)}
    if any(size < 0 for size in sizes.values()) or sum(sizes.values()) != POOL:
        raise ValueError("region sizes must be nonnegative and sum to 49")
    for ticket in range(ticket_count):
        contained = sum(size for mask, size in sizes.items() if mask & (1 << ticket))
        if contained != TICKET_SIZE:
            raise ValueError(f"ticket {ticket} has {contained} labels, expected 6")

    regions = tuple(sorted(sizes.items()))
    suffix_pool = [0] * (len(regions) + 1)
    suffix_hits = [[0] * ticket_count for _ in range(len(regions) + 1)]
    for index in range(len(regions) - 1, -1, -1):
        mask, size = regions[index]
        suffix_pool[index] = suffix_pool[index + 1] + size
        for ticket in range(ticket_count):
            suffix_hits[index][ticket] = suffix_hits[index + 1][ticket] + (
                size if mask & (1 << ticket) else 0
            )

    hits = [0] * ticket_count
    total = 0

    def visit(index: int, remaining: int, ways: int) -> None:
        nonlocal total
        if remaining < 0 or remaining > suffix_pool[index]:
            return
        if any(hits[t] + suffix_hits[index][t] < 3 for t in range(ticket_count)):
            return
        if index == len(regions):
            if remaining == 0:
                total += ways
            return

        mask, size = regions[index]
        for take in range(min(size, remaining) + 1):
            choices = comb(size, take)
            if not choices:
                continue
            for ticket in range(ticket_count):
                if mask & (1 << ticket):
                    hits[ticket] += take
            visit(index + 1, remaining - take, ways * choices)
            for ticket in range(ticket_count):
                if mask & (1 << ticket):
                    hits[ticket] -= take

    visit(0, 7, 1)
    return total


def pair_overlap_outcomes(overlap: int) -> int:
    if overlap not in (0, 1):
        raise ValueError("Shell-1 pair overlap must be 0 or 1")
    regions = {
        0: POOL - (2 * TICKET_SIZE - overlap),
        1: TICKET_SIZE - overlap,
        2: TICKET_SIZE - overlap,
        3: overlap,
    }
    return 7 * count_seven_sets(regions, ticket_count=2)


def check_event_equivalence() -> None:
    """Check the official rule against its seven-set form for valid hit states."""
    for main_hits in range(DRAW_SIZE + 1):
        for special_hit in (0, 1):
            if main_hits + special_hit > TICKET_SIZE:
                continue
            official = main_hits >= 3 or (main_hits == 2 and special_hit == 1)
            seven_set = main_hits + special_hit >= 3
            if official != seven_set:
                raise AssertionError(
                    f"event mismatch: main_hits={main_hits}, special_hit={special_hit}"
                )


def check_bonferroni_direction() -> int:
    """Verify the per-outcome third Bonferroni partial-sum inequality for K=20."""
    checked = 0
    for multiplicity in range(TICKET_COUNT + 1):
        partial = multiplicity - comb(multiplicity, 2) + comb(multiplicity, 3)
        union_indicator = int(multiplicity > 0)
        if partial < union_indicator:
            raise AssertionError(f"Bonferroni upper-bound failure at m={multiplicity}")
        if multiplicity == 0:
            if partial != 0:
                raise AssertionError("zero-hit Bonferroni term must equal zero")
        elif partial != 1 + comb(multiplicity - 1, 3):
            raise AssertionError(f"Bonferroni identity failure at m={multiplicity}")
        checked += 1
    return checked


def verify() -> dict[str, object]:
    check_event_equivalence()

    outcome_universe = comb(POOL, DRAW_SIZE) * SPECIALS_OUTSIDE_DRAW
    seven_set_universe = 7 * comb(POOL, 7)
    if outcome_universe != seven_set_universe:
        raise AssertionError("draw/special universe and seven-set universe disagree")

    single = 7 * sum(
        comb(TICKET_SIZE, hits) * comb(POOL - TICKET_SIZE, 7 - hits)
        for hits in range(3, TICKET_SIZE + 1)
    )
    pair_q0 = pair_overlap_outcomes(0)
    pair_q1 = pair_overlap_outcomes(1)
    pair_total = comb(TICKET_COUNT, 2)
    overlap_zero_pairs = pair_total - SHELL1_OVERLAP_ONE_PAIRS
    s1 = TICKET_COUNT * single
    s2 = overlap_zero_pairs * pair_q0 + SHELL1_OVERLAP_ONE_PAIRS * pair_q1
    s1_minus_s2 = s1 - s2

    motif_weights = {
        name: 7 * count_seven_sets(spec["regions"], ticket_count=3)
        for name, spec in MOTIFS.items()
    }
    constants = {
        "OUTCOME_UNIVERSE": outcome_universe,
        "SINGLE_TICKET_WINNING_OUTCOMES": single,
        "S1": s1,
        "PAIR_Q0": pair_q0,
        "PAIR_Q1": pair_q1,
        "S2": s2,
        "S1_MINUS_S2": s1_minus_s2,
        **motif_weights,
    }
    for name, expected in REFERENCE.items():
        actual = constants[name]
        if actual != expected:
            raise AssertionError(f"MISMATCH {name}: expected {expected}, got {actual}")

    checked_multiplicities = check_bonferroni_direction()
    verifier_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "TASK_ID": "B649_K20_SHELL1_BONFERRONI_PORTABLE_VERIFIER_R1",
        "STATUS": "PASS",
        "COUNTING_METHOD": "7set_venn_region_exact_integer_dp_v1",
        "METHOD_PROPERTIES": {
            "stdlib_only": True,
            "imports_original_co_win": False,
            "enumerates_full_outcome_universe": False,
            "event_definition": "|T&D| >= 3 or (|T&D| == 2 and special in T)",
            "seven_set_map": "R = D union {special}; ticket event is |T&R| >= 3",
            "outcome_fiber_size_per_seven_set": 7,
        },
        "SHELL1_PAIR_CLASS_COUNTS": {
            "ticket_count": TICKET_COUNT,
            "total_pairs": pair_total,
            "overlap_one_pairs": SHELL1_OVERLAP_ONE_PAIRS,
            "overlap_zero_pairs": overlap_zero_pairs,
        },
        "MOTIF_DEFINITIONS": {
            name: {
                "definition": spec["definition"],
                "venn_region_sizes_by_ticket_mask": {
                    str(mask): spec["regions"].get(mask, 0)
                    for mask in range(8)
                },
            }
            for name, spec in MOTIFS.items()
        },
        "CONSTANTS": constants,
        "BONFERRONI": {
            "BOUND_DIRECTION": "UNION_COUNT <= S1 - S2 + S3",
            "PER_OUTCOME_IDENTITY": "m-C(m,2)+C(m,3)=0 if m=0; else 1+C(m-1,3)",
            "multiplicities_checked": checked_multiplicities,
        },
        "SHA256": {
            "canonical_k20": CANONICAL_K20_SHA256,
            "verifier": verifier_sha256,
        },
        "CANONICAL_K20_COUNT": CANONICAL_K20_COUNT,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="also write the deterministic JSON result to this existing directory",
    )
    args = parser.parse_args()
    result_text = json.dumps(verify(), sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        if not args.output.parent.is_dir():
            parser.error(f"output directory does not exist: {args.output.parent}")
        args.output.write_text(result_text, encoding="utf-8")
    print(result_text, end="")


if __name__ == "__main__":
    main()
