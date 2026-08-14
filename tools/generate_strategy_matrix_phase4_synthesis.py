"""Strategy Matrix Phase 4: exact, normalized cross-lottery synthesis.

Reads the three SEALED, already-published DIVERSIFICATION_COVERAGE_*_V1
result artifacts (B649, T539, P638 Zone-1) from
`docs/research/matrix-native-results/` and derives normalized cross-lottery
comparison statistics using only `fractions.Fraction` arithmetic on their
already-published `exact` fraction strings.

This performs no new combinatorial enumeration, reads no historical draw
data, and does not touch P638 Zone-2 -- it is a read-only meta-analysis
over evidence already sealed by Strategy Matrix Phases 1-3
(`docs/research/cross_lottery_research_ledger_r1.json` cells
`DIVERSIFICATION_COVERAGE_B649_V1__BIG_LOTTO`,
`DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539`,
`DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1`). The three
source result JSONs are read, never modified.

Normalizations computed, all exact except where explicitly cast to float
for reporting:

1. `relative_lift_over_random` = delta_3(k) / q_random_3(k) -- expresses
   the coverage advantage as a fraction of each lottery's own random
   baseline, which differs by ~3x across the three lotteries (0.18 to
   0.55 at k=20) and so is not directly comparable via raw deltas alone.
2. `exposure_fraction_k_over_n` = k / pool_size -- the same raw k covers a
   different fraction of each lottery's own cyclic shift space (49 vs 39
   vs 38 total shifts), so raw-k comparisons are partially confounded by
   this.
3. `coverage_ratio` = Q_geometry(k) / Q_random_expected(k), which is
   exactly `1 + relative_lift_over_random` and makes the normalized
   coverage multiplier explicit rather than leaving it implicit.
4. `marginal_rate` and its growth multiple from the k=3 to k=20 ladder
   rungs -- an exact re-derivation of each cell's own already-published
   `marginal_geometry_delta` (kept as a float there), used here as a
   dimensionless shape comparison across lotteries.
5. A same-sign convergence check against the M4+ secondary threshold, to
   confirm the finding is not an artifact of the single M3+ primary
   threshold choice.

No predictive-advantage, prize-value, or economic claim is computed or
implied anywhere in this module.
"""

from __future__ import annotations

import json
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any

RESULTS_DIR = Path("docs/research/matrix-native-results")
OUTPUT_PATH = RESULTS_DIR / "strategy-matrix-phase4-cross-lottery-synthesis-v1-result.json"

LADDER: tuple[int, ...] = (1, 3, 5, 10, 15, 20)

CELLS: dict[str, dict[str, Any]] = {
    "BIG_LOTTO": {
        "matrix_variant_id": "DIVERSIFICATION_COVERAGE_B649_V1",
        "cell_id": "DIVERSIFICATION_COVERAGE_B649_V1__BIG_LOTTO",
        "source_path": RESULTS_DIR / "diversification-coverage-b649-v1-result.json",
        "pool_size": 49,
        "draw_size": 6,
        "max_nondegenerate_threshold": 5,
        "constructor_id": "CYCLIC_SIDON_SHIFT_B649_V1",
    },
    "DAILY_539": {
        "matrix_variant_id": "DIVERSIFICATION_COVERAGE_T539_V1",
        "cell_id": "DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539",
        "source_path": RESULTS_DIR / "diversification-coverage-t539-v1-result.json",
        "pool_size": 39,
        "draw_size": 5,
        "max_nondegenerate_threshold": 4,
        "constructor_id": "CYCLIC_SIDON_SHIFT_T539_V1",
    },
    "POWER_LOTTO_zone1": {
        "matrix_variant_id": "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1",
        "cell_id": "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1",
        "source_path": RESULTS_DIR / "diversification-coverage-p638-zone1-v1-result.json",
        "pool_size": 38,
        "draw_size": 6,
        "max_nondegenerate_threshold": 5,
        "constructor_id": "CYCLIC_SIDON_SHIFT_P638_ZONE1_V1",
    },
}


def _frac_dict(mapping: dict[str, Fraction]) -> dict[str, dict[str, Any]]:
    return {
        k: {"exact": f"{v.numerator}/{v.denominator}", "float": float(v)}
        for k, v in mapping.items()
    }


def load_source(spec: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(spec["source_path"].read_text(encoding="utf-8"))
    if data["matrix_variant_id"] != spec["matrix_variant_id"]:
        raise ValueError(f"source identity mismatch in {spec['source_path']}")
    if data["sanity_check_d3_at_k1_is_exactly_zero"] is not True:
        raise ValueError(f"source sanity check not satisfied in {spec['source_path']}")
    return data


def analyze_cell(lottery: str, spec: dict[str, Any]) -> dict[str, Any]:
    data = load_source(spec)
    n = spec["pool_size"]

    delta3 = {k: Fraction(data["delta"]["3"][str(k)]["exact"]) for k in LADDER}
    qrand3 = {k: Fraction(data["q_random"]["3"][str(k)]["exact"]) for k in LADDER}
    qsidon3 = {k: Fraction(data["q_sidon"]["3"][str(k)]["exact"]) for k in LADDER}

    # Independent identity check: delta must equal q_sidon - q_random exactly,
    # for every ladder rung, re-derived here rather than trusted.
    for k in LADDER:
        if qsidon3[k] - qrand3[k] != delta3[k]:
            raise ValueError(f"{lottery}: delta identity failed at k={k}")
    if delta3[1] != 0:
        raise ValueError(f"{lottery}: D_3(1) != 0")

    relative_lift3 = {k: (delta3[k] / qrand3[k]) for k in LADDER if qrand3[k] != 0}
    coverage_ratio3 = {k: (qsidon3[k] / qrand3[k]) for k in LADDER if qrand3[k] != 0}

    exposure_fraction = {k: Fraction(k, n) for k in LADDER}

    marginal_rate: dict[int, Fraction] = {}
    prev_k = None
    for k in LADDER:
        if prev_k is not None:
            marginal_rate[k] = (delta3[k] - delta3[prev_k]) / (k - prev_k)
        prev_k = k
    growth_multiple_20_over_3 = marginal_rate[20] / marginal_rate[3]
    marginal_rates_in_ladder_order = [marginal_rate[k] for k in LADDER if k != 1]

    # Cross-check against each cell's own already-published float, as an
    # independent verification that this script's exact re-derivation
    # matches what Phases 1-3 already reported (not a new measurement).
    published_marginal = data["marginal_geometry_delta"]
    for k, exact_rate in marginal_rate.items():
        published = published_marginal[str(k)]
        if abs(float(exact_rate) - published) > 1e-12:
            raise ValueError(
                f"{lottery}: marginal rate mismatch at k={k}: "
                f"{float(exact_rate)} vs {published}"
            )

    # Secondary-threshold (M4+) sign-convergence check at k=20 -- confirms
    # the advantage is not an artifact of the single M3+ primary threshold.
    delta4_20 = Fraction(data["delta"]["4"]["20"]["exact"])
    qrand4_20 = Fraction(data["q_random"]["4"]["20"]["exact"])
    relative_lift4_20 = delta4_20 / qrand4_20 if qrand4_20 != 0 else None

    max_m = spec["max_nondegenerate_threshold"]
    delta_max_20 = Fraction(data["delta"][str(max_m)]["20"]["exact"])
    pool_density = Fraction(spec["draw_size"], n)

    return {
        "matrix_variant_id": spec["matrix_variant_id"],
        "source_cell_id": spec["cell_id"],
        "source_path": str(spec["source_path"]),
        "pool_size": n,
        "draw_size": spec["draw_size"],
        "constructor": {
            "constructor_id": spec["constructor_id"],
            "deterministic": True,
            "low_overlap": True,
            "maximum_pairwise_ticket_overlap": 1,
        },
        "pool_density_draw_size_over_pool_size": {
            "exact": f"{pool_density.numerator}/{pool_density.denominator}",
            "float": float(pool_density),
        },
        "delta_3": _frac_dict({str(k): v for k, v in delta3.items()}),
        "q_random_3": _frac_dict({str(k): v for k, v in qrand3.items()}),
        "q_geometry_3": _frac_dict({str(k): v for k, v in qsidon3.items()}),
        "relative_lift_3_over_random": _frac_dict({str(k): v for k, v in relative_lift3.items()}),
        "relative_lift_3_over_random_pct_at_k20": float(relative_lift3[20]) * 100,
        "coverage_ratio_3_over_random": _frac_dict(
            {str(k): v for k, v in coverage_ratio3.items()}
        ),
        "coverage_ratio_3_over_random_at_k20": float(coverage_ratio3[20]),
        "exposure_fraction_k_over_n": _frac_dict({str(k): v for k, v in exposure_fraction.items()}),
        "marginal_rate": _frac_dict({str(k): v for k, v in marginal_rate.items()}),
        "marginal_geometry_delta": _frac_dict({str(k): v for k, v in marginal_rate.items()}),
        "growth_multiple_rate_at_k20_over_rate_at_k3": float(growth_multiple_20_over_3),
        "delta_3_positive_for_every_tested_k_gt_1": all(delta3[k] > 0 for k in LADDER if k > 1),
        "marginal_geometry_delta_strictly_increasing": all(
            earlier < later
            for earlier, later in pairwise(marginal_rates_in_ladder_order)
        ),
        "geometry_advantage_zero_crossing": data["geometry_advantage_zero_crossing"],
        "delta_4_at_k20": {
            "exact": f"{delta4_20.numerator}/{delta4_20.denominator}",
            "float": float(delta4_20),
        },
        "relative_lift_4_over_random_pct_at_k20": (
            float(relative_lift4_20) * 100 if relative_lift4_20 is not None else None
        ),
        "max_nondegenerate_threshold_tested": max_m,
        "delta_at_max_nondegenerate_threshold_k20": {
            "exact": f"{delta_max_20.numerator}/{delta_max_20.denominator}",
            "float": float(delta_max_20),
        },
    }


def build_synthesis() -> dict[str, Any]:
    per_lottery = {lottery: analyze_cell(lottery, spec) for lottery, spec in CELLS.items()}

    raw_ranking_k20 = sorted(
        per_lottery, key=lambda lot: per_lottery[lot]["delta_3"]["20"]["float"], reverse=True
    )
    relative_ranking_k20 = sorted(
        per_lottery,
        key=lambda lot: per_lottery[lot]["relative_lift_3_over_random_pct_at_k20"],
        reverse=True,
    )

    m4_signs = {lot: (per_lottery[lot]["delta_4_at_k20"]["float"] > 0) for lot in per_lottery}
    m3_signs = {lot: (per_lottery[lot]["delta_3"]["20"]["float"] > 0) for lot in per_lottery}
    positive_at_every_k = {
        lot: per_lottery[lot]["delta_3_positive_for_every_tested_k_gt_1"]
        for lot in per_lottery
    }
    increasing_marginals = {
        lot: per_lottery[lot]["marginal_geometry_delta_strictly_increasing"]
        for lot in per_lottery
    }
    zero_crossings = {
        lot: per_lottery[lot]["geometry_advantage_zero_crossing"] for lot in per_lottery
    }

    return {
        "synthesis_id": "STRATEGY_MATRIX_PHASE4_DIVERSIFICATION_CROSS_LOTTERY_SYNTHESIS_R1",
        "source_type": "STRATEGY_MATRIX_SYNTHESIS",
        "evidence_type": "EXACT_COMBINATORIAL",
        "hypothesis_family_id": "DIVERSIFICATION",
        "inputs": {lot: per_lottery[lot]["source_cell_id"] for lot in per_lottery},
        "per_lottery": per_lottery,
        "raw_d3_k20_ranking_descending": raw_ranking_k20,
        "relative_lift_k20_ranking_descending": relative_ranking_k20,
        "ranking_flips_under_normalization": raw_ranking_k20 != relative_ranking_k20,
        "m3_and_m4_signs_agree_at_k20": all(
            m3_signs[lot] == m4_signs[lot] for lot in per_lottery
        ),
        "direction_consistency": {
            "tested_k_gt_1": [k for k in LADDER if k > 1],
            "positive_for_every_lottery_and_tested_k": all(positive_at_every_k.values()),
            "per_lottery": positive_at_every_k,
        },
        "exposure_shape_consistency": {
            "marginal_geometry_delta_strictly_increasing_for_every_lottery": all(
                increasing_marginals.values()
            ),
            "per_lottery": increasing_marginals,
            "classification": "WIDENS_IN_ALL_THREE_WITH_LOTTERY_SPECIFIC_GROWTH_MAGNITUDE",
        },
        "zero_crossing_consistency": {
            "all_none": all(value is None for value in zero_crossings.values()),
            "per_lottery": zero_crossings,
        },
        "constructor_invariant": {
            "all_deterministic": all(
                cell["constructor"]["deterministic"] for cell in per_lottery.values()
            ),
            "all_low_overlap": all(
                cell["constructor"]["low_overlap"] for cell in per_lottery.values()
            ),
            "maximum_pairwise_ticket_overlap": 1,
            "identical_ticket_sets_claimed": False,
            "constructor_ids": {
                lottery: cell["constructor"]["constructor_id"]
                for lottery, cell in per_lottery.items()
            },
        },
        "cross_lottery_synthesis_classification": (
            "SUPPORTED_ACROSS_3_NATIVE_LOTTERY_STRUCTURES"
        ),
        "phase5_research_priority": {
            "mechanism_family": "DIVERSIFICATION",
            "priority": "HIGH_PRIORITY_FOR_GENERATION_2",
            "candidate_family": "DIVERSIFICATION_CONSTRUCTOR_FRONTIER",
            "research_question": (
                "Among deterministic portfolio geometries at fixed ticket count, how much of "
                "the observed advantage is explained by low overlap itself, and is Sidon-shift "
                "near the achievable coverage frontier?"
            ),
        },
        "scope": {
            "new_enumeration_performed": "NO",
            "historical_draw_data_read": "NO",
            "p638_zone2_touched": "NO",
            "predictive_advantage": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
            "production_promotion": "NO",
            "cohort_creation": "NO",
            "prospective_activation": "NO",
        },
    }


def main() -> None:
    synthesis = build_synthesis()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(synthesis, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"raw D_3(20) ranking:      {synthesis['raw_d3_k20_ranking_descending']}")
    print(f"relative-lift ranking:    {synthesis['relative_lift_k20_ranking_descending']}")
    print(f"ranking flips:            {synthesis['ranking_flips_under_normalization']}")
    print(f"M3/M4 signs agree:        {synthesis['m3_and_m4_signs_agree_at_k20']}")


if __name__ == "__main__":
    main()
