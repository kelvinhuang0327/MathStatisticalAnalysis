"""Execute the locked DIVERSIFICATION_COVERAGE_T539_V1 experiment.

Reads locked parameters from
`docs/research/matrix-native-results/diversification-coverage-t539-v1-preregistration-hash.json`
and re-verifies that file's hash before using anything in it. No draw
history is read; this experiment is pure exact combinatorics over the
complete C(39,5) winning-space enumeration and the already-verified
`exact_coverage_baseline` closed-form random portfolio baseline, reused
unmodified from the B649 cell. Mirrors
`run_diversification_coverage_sidon_v1.py` (B649) exactly, except
classification labels use the `_EXPECTED_COVERAGE` terminology directly
(T539's preregistration locks that terminology from the start, unlike
B649's original script -- see the ledger's classification-label
clarification note for that historical cell).
"""

from __future__ import annotations

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json
from lottolab.research.cyclic_sidon_shift_t539 import sidon_shift_portfolio
from lottolab.research.exact_coverage_baseline import exact_random_portfolio_coverage

PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-t539-v1-preregistration-hash.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/diversification-coverage-t539-v1-result.json"
)

_CLASSIFICATION_BY_SIGNS: dict[frozenset[int], str] = {
    frozenset({1}): "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE",
    frozenset({0}): "MATCHES_RANDOM_EXPECTED_COVERAGE",
    frozenset({-1}): "UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE",
}


def load_locked_parameters() -> dict[str, Any]:
    record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    locked = record["locked_parameters"]
    recomputed = canonical_json.sha256_hex(canonical_json.canonical_bytes(locked))
    if recomputed != record["preregistration_hash_sha256"]:
        raise ValueError(
            "preregistration hash mismatch -- the locked parameters file was "
            "modified after locking; refusing to execute against tampered parameters"
        )
    return locked


def _ticket_bitmask(ticket: tuple[int, ...]) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def run(locked: dict[str, Any]) -> dict[str, Any]:
    pool_size: int = locked["pool_size"]
    draw_size: int = locked["draw_size"]
    ladder: list[int] = locked["exposure_ladder"]
    max_k: int = max(ladder)
    thresholds: list[int] = [
        locked["primary_event_minimum_matches"],
        *locked["secondary_event_minimum_matches"],
    ]

    portfolio = sidon_shift_portfolio(max_k)
    ticket_masks = [_ticket_bitmask(ticket) for ticket in portfolio]

    total_draws = math.comb(pool_size, draw_size)
    earliest_index_counts: dict[int, list[int]] = {m: [0] * (max_k + 1) for m in thresholds}

    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_mask = _ticket_bitmask(draw)
        earliest_for_threshold = dict.fromkeys(thresholds, max_k)
        remaining = set(thresholds)
        for index, ticket_mask in enumerate(ticket_masks):
            if not remaining:
                break
            hits = (draw_mask & ticket_mask).bit_count()
            satisfied_now = [m for m in remaining if hits >= m]
            for m in satisfied_now:
                earliest_for_threshold[m] = index
                remaining.discard(m)
        for m in thresholds:
            earliest_index_counts[m][earliest_for_threshold[m]] += 1

    q_sidon: dict[int, dict[int, Fraction]] = {m: {} for m in thresholds}
    for m in thresholds:
        cumulative = 0
        prefix_counts: dict[int, int] = {}
        for i in range(max_k):
            cumulative += earliest_index_counts[m][i]
            prefix_counts[i + 1] = cumulative
        for k in ladder:
            q_sidon[m][k] = Fraction(prefix_counts[k], total_draws)

    q_random: dict[int, dict[int, Fraction]] = {m: {} for m in thresholds}
    for m in thresholds:
        for k in ladder:
            q_random[m][k] = exact_random_portfolio_coverage(pool_size, draw_size, m, k)

    delta: dict[int, dict[int, Fraction]] = {
        m: {k: q_sidon[m][k] - q_random[m][k] for k in ladder} for m in thresholds
    }

    primary_m = locked["primary_event_minimum_matches"]
    sanity_check_d3_at_1 = delta[primary_m][1]
    if sanity_check_d3_at_1 != 0:
        raise ValueError(
            f"sanity check failed: D_{primary_m}(1) = {sanity_check_d3_at_1}, expected exactly 0"
        )

    primary_deltas = [delta[primary_m][k] for k in ladder]
    signs = {(1 if d > 0 else (-1 if d < 0 else 0)) for d in primary_deltas[1:]}  # exclude k=1
    classification = _CLASSIFICATION_BY_SIGNS.get(frozenset(signs), "MIXED_BY_EXPOSURE")

    marginal_geometry_delta: dict[int, float] = {}
    zero_crossing: int | None = None
    for previous_k, current_k in itertools.pairwise(ladder):
        step = current_k - previous_k
        raw = delta[primary_m][current_k] - delta[primary_m][previous_k]
        marginal = raw / step
        marginal_geometry_delta[current_k] = float(marginal)
        if zero_crossing is None and marginal <= 0:
            zero_crossing = current_k

    def _fraction_dict(mapping: dict[int, Fraction]) -> dict[str, dict[str, Any]]:
        return {
            str(k): {"exact": f"{v.numerator}/{v.denominator}", "float": float(v)}
            for k, v in mapping.items()
        }

    return {
        "matrix_variant_id": locked["matrix_variant_id"],
        "hypothesis_family_id": locked["hypothesis_family_id"],
        "lottery_type": locked["lottery_type"],
        "replicates": "DIVERSIFICATION_COVERAGE_B649_V1",
        "preregistration_hash_sha256": canonical_json.sha256_hex(
            canonical_json.canonical_bytes(locked)
        ),
        "total_draws_enumerated": total_draws,
        "sanity_check_d3_at_k1_is_exactly_zero": True,
        "primary_event_minimum_matches": primary_m,
        "q_sidon": {str(m): _fraction_dict(q_sidon[m]) for m in thresholds},
        "q_random": {str(m): _fraction_dict(q_random[m]) for m in thresholds},
        "delta": {str(m): _fraction_dict(delta[m]) for m in thresholds},
        "marginal_geometry_delta": {str(k): v for k, v in marginal_geometry_delta.items()},
        "geometry_advantage_zero_crossing": zero_crossing,
        "descriptive_classification": classification,
        "scope": {
            "predictive_advantage": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
            "p638": "NOT_RUN",
            "production_promotion": "NO",
            "cohort_creation": "NO",
            "prospective_activation": "NO",
        },
    }


def main() -> None:
    locked = load_locked_parameters()
    result = run(locked)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"classification: {result['descriptive_classification']}")
    print(f"geometry_advantage_zero_crossing: {result['geometry_advantage_zero_crossing']}")


if __name__ == "__main__":
    main()
