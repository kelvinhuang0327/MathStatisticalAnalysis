"""Run one pre-outcome K10 outside-native single-crossover augmentation study.

Reuses the frozen causal full-union loader, the frozen MIN_OVERLAP K10 /
prior-20 archive, the unchanged local-refinement selector, and the unchanged
exact OFFICIAL_ANY_PRIZE scorer from the sibling full-union local-refinement
study. Only candidate-pool construction changes: each target's search pool is
the native full union augmented with deterministic single-number crossover
children between the frozen K10 baseline and the tickets outside the prior
20-ticket pool.
"""

# pyright: reportPrivateUsage=false
# Deliberately imports the sibling study's private loader/evaluator helpers
# unchanged rather than reimplementing frozen machinery (same precedent as
# tests/unit/test_b649_min_overlap_full_union_local_refinement.py).

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import cast

from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths
from lottolab.research.b649_arm_d_vs_sealed_exact_probability import (
    TOTAL_OUTCOME_SPACE,
    load_frozen_arm_d_archive,
    verify_evaluator_content_sha256,
    verify_sealed_input_file,
)
from lottolab.research.b649_min_overlap_full_union_local_refinement import (
    ITERATION_CAP,
    SELECTION_DRAW_COUNT,
    SELECTION_SEED,
    K,
    Portfolio,
    RefinementResult,
    Ticket,
    refine_min_overlap_k10,
)
from lottolab.research.b649_official_win_marginal_coverage_selector import (
    generate_selection_draw_sample,
)
from lottolab.research.b649_outside_native_single_crossover_augmentation import (
    AUGMENTATION_ID,
    generate_single_crossover_children,
)
from tools.run_b649_min_overlap_full_union_local_refinement_r1 import (
    BASELINE_RESULT_LOCATOR,
    BRANCH2_RESULT_BLOB,
    BRANCH2_RESULT_SHA256,
    _build_full_union,
    _evaluate_exact_cohort,
    _hash_portfolio_archive,
    _load_baseline_mean,
    _load_history_before,
    _mean_probability,
    _project_branch2_predraw_rows,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_LOCATOR = "docs/research/b649-outside-native-single-crossover-augmentation-r1-result.json"
REPORT_LOCATOR = "docs/research/b649-outside-native-single-crossover-augmentation-r1-report.md"
MATERIAL_RELATIVE_GAIN_THRESHOLD = Fraction(1, 100)


@dataclass(frozen=True, slots=True)
class IntStats:
    """Min / median / mean / max over one integer-valued per-target diagnostic."""

    minimum: int
    median: Fraction
    mean: Fraction
    maximum: int

    def as_json(self) -> dict[str, object]:
        return {
            "min": self.minimum,
            "median": str(self.median),
            "mean": str(self.mean),
            "max": self.maximum,
        }


def _int_stats(values: Sequence[int]) -> IntStats:
    if not values:
        raise ValueError("values must be non-empty")
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    median = (
        Fraction(ordered[middle])
        if count % 2 == 1
        else Fraction(ordered[middle - 1] + ordered[middle], 2)
    )
    return IntStats(
        minimum=ordered[0],
        median=median,
        mean=Fraction(sum(ordered), count),
        maximum=ordered[-1],
    )


def render_report(payload: dict[str, object]) -> str:
    native = cast(dict[str, object], payload["native_full_union"])
    augmentation = cast(dict[str, object], payload["augmentation"])
    search = cast(dict[str, object], payload["search"])
    evaluation = cast(dict[str, object], payload["evaluation"])
    control = cast(dict[str, object], evaluation["control_subset_o_zero"])
    outside = cast(dict[str, object], evaluation["outside_subset_o_gt_zero"])
    pool_stats = cast(dict[str, object], augmentation["augmented_pool_size"])
    child_stats = cast(dict[str, object], augmentation["generated_child_count"])
    mean_swaps = Fraction(str(search["mean_swap_count"]))
    baseline = Fraction(str(evaluation["min_overlap_mean_probability"]))
    candidate = Fraction(str(evaluation["candidate_mean_probability"]))
    delta = Fraction(str(evaluation["absolute_delta"]))
    relative = Fraction(str(evaluation["relative_delta"]))
    return "\n".join(
        [
            "# B649 Outside-Native Single-Crossover K10 Augmentation R1",
            "",
            "## Frozen pre-outcome contract",
            "",
            (
                f"- Cohort: {payload['target_count']} targets from the sealed "
                "MIN_OVERLAP K10/K20 archive."
            ),
            (
                "- Candidate pool per target: native PRE_DRAW full union (U) augmented with "
                "deterministic single-number crossover children between the frozen K10 "
                "baseline (P10) and native tickets outside the prior 20-ticket pool "
                "(O = U minus P20)."
            ),
            (
                f"- Augmentation `{AUGMENTATION_ID}` starts from frozen K10 MIN_OVERLAP "
                f"tickets; K remains {K}."
            ),
            (
                f"- Selection sample: {SELECTION_DRAW_COUNT:,} seeded main draws, "
                f"seed `{SELECTION_SEED}`; special balls integrated analytically."
            ),
            (
                "- Search: unchanged local-refinement selector, all one-for-one swaps, "
                "strict sample improvement, tie-break (remove position, add pool position), "
                f"maximum {ITERATION_CAP} swaps."
            ),
            (
                "- Final values use the unchanged exhaustive OFFICIAL_ANY_PRIZE "
                "evaluator over all 601,304,088 fair-draw outcomes."
            ),
            "- No target outcome was decoded or used at any stage.",
            "",
            "## Native full-union and augmentation diagnostics",
            "",
            f"- Native full-union sizes: `{native['size_distribution']}`.",
            (
                f"- Outside-native counts (|O|): `{native['outside_native_count_distribution']}`; "
                f"total {native['outside_native_total']}."
            ),
            (
                f"- Augmented pool size: min {pool_stats['min']}, median {pool_stats['median']}, "
                f"mean {pool_stats['mean']} ({float(Fraction(str(pool_stats['mean']))):.2f}), "
                f"max {pool_stats['max']}."
            ),
            (
                f"- Generated child count: min {child_stats['min']}, "
                f"median {child_stats['median']}, "
                f"mean {child_stats['mean']} ({float(Fraction(str(child_stats['mean']))):.2f}), "
                f"max {child_stats['max']}."
            ),
            (
                "- Targets with generated children: "
                f"{augmentation['targets_with_generated_children']}."
            ),
            "",
            "## Search diagnostics",
            "",
            f"- Targets with any swap: {search['targets_with_any_swap']}.",
            (
                "- Targets with final portfolio change: "
                f"{search['targets_with_final_portfolio_change']}."
            ),
            f"- Mean swap count: {mean_swaps} ({float(mean_swaps):.4f}).",
            "",
            "## Exact K10 comparison on all targets",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| MIN_OVERLAP mean probability | {baseline} ({float(baseline):.8f}) |",
            f"| Candidate mean probability | {candidate} ({float(candidate):.8f}) |",
            f"| Absolute delta | {delta} ({float(delta):+.8f}) |",
            f"| Relative delta | {relative} ({float(relative):+.4%}) |",
            f"| Required relative lift | {MATERIAL_RELATIVE_GAIN_THRESHOLD} (+1.0%) |",
            f"| READY_FOR_BRANCH2_OOS | **{evaluation['ready_for_branch2_oos']}** |",
            "",
            "The sampled selection score is separate from these exact final probabilities.",
            "",
            "## Control subset (|O| = 0, no augmentation possible)",
            "",
            f"- Targets: {control['target_count']}.",
            f"- MIN_OVERLAP mean: {control['min_overlap_mean_probability']}.",
            f"- Candidate mean: {control['candidate_mean_probability']}.",
            f"- Absolute delta: {control['absolute_delta']}.",
            "",
            "## Outside subset (|O| > 0, augmentation possible)",
            "",
            f"- Targets: {outside['target_count']}.",
            f"- MIN_OVERLAP mean: {outside['min_overlap_mean_probability']}.",
            f"- Candidate mean: {outside['candidate_mean_probability']}.",
            f"- Absolute delta: {outside['absolute_delta']}.",
            "- Both subsets are diagnostic; the all-target mean is the sole primary gate.",
            "",
            (
                "K20 selector optimization and Branch2 OOS were not run. "
                "No target outcome value was decoded or used, and no database write, "
                "production action, push, or PR occurred."
            ),
            "This fair-draw model result makes no predictive, payout, profit, or ROI claim.",
            "",
        ]
    )


def run() -> dict[str, object]:
    verify_sealed_input_file()
    verify_evaluator_content_sha256()
    target_ids, archive = load_frozen_arm_d_archive()
    baseline = archive[K]
    prior20 = archive[20]
    predraw = _project_branch2_predraw_rows()
    if tuple(row.target_draw for row in predraw) != target_ids:
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: target order")
    if len(baseline) != len(prior20) or len(baseline) != len(target_ids):
        raise ValueError("frozen archive cohort mismatch")
    frozen_mean, baseline_result_sha = _load_baseline_mean()
    sample = generate_selection_draw_sample(sample_count=SELECTION_DRAW_COUNT, seed=SELECTION_SEED)

    database = resolve_local_data_paths().database
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro&immutable=1", uri=True)
    connection.execute("PRAGMA query_only = ON")
    unions: list[Portfolio] = []
    outside_lists: list[tuple[Ticket, ...]] = []
    child_lists: list[tuple[Ticket, ...]] = []
    augmented_pools: list[tuple[Ticket, ...]] = []
    selections: list[RefinementResult] = []
    try:
        for index, (row, base, twenty) in enumerate(
            zip(predraw, baseline, prior20, strict=True), start=1
        ):
            history = _load_history_before(connection, row)
            full_union, pool_sha = _build_full_union(history)
            if (
                pool_sha != row.pool_sha256
                or len(full_union) != row.candidate_count
                or len(twenty) != 20
                or not set(base).issubset(full_union)
                or not set(twenty).issubset(full_union)
            ):
                raise ValueError(
                    f"FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: target {row.target_draw}"
                )
            unions.append(full_union)
            twenty_set = set(twenty)
            outside = tuple(ticket for ticket in full_union if ticket not in twenty_set)
            if len(outside) != len(full_union) - 20:
                raise AssertionError(
                    f"outside-native cardinality mismatch for target {row.target_draw}"
                )
            outside_lists.append(outside)
            children = generate_single_crossover_children(base, outside)
            child_lists.append(children)
            augmented = tuple(dict.fromkeys((*full_union, *children)))
            if not outside and augmented != full_union:
                raise AssertionError(
                    "empty outside-native set must leave the pool unaugmented "
                    f"for {row.target_draw}"
                )
            augmented_pools.append(augmented)
            selections.append(refine_min_overlap_k10(augmented, base, selection_draws=sample))
            if index % 100 == 0 or index == len(predraw):
                print(f"PRE_DRAW targets complete: {index}/{len(predraw)}", flush=True)
    finally:
        connection.close()

    candidate = tuple(selection.portfolio for selection in selections)
    baseline_counts, candidate_counts = _evaluate_exact_cohort(baseline, candidate)
    baseline_mean = _mean_probability(baseline_counts)
    if baseline_mean != frozen_mean:
        raise ValueError("unchanged exact evaluator did not reproduce frozen MIN_OVERLAP mean")
    candidate_mean = _mean_probability(candidate_counts)
    delta = candidate_mean - baseline_mean
    relative = delta / baseline_mean
    changed = sum(
        set(base) != set(selected) for base, selected in zip(baseline, candidate, strict=True)
    )
    any_swap = sum(selection.swap_count > 0 for selection in selections)
    if any_swap != changed:
        raise AssertionError("strict-ascent swaps did not bind final portfolio changes")
    ready = relative >= MATERIAL_RELATIVE_GAIN_THRESHOLD and changed > 0

    outside_counts = tuple(len(outside) for outside in outside_lists)
    child_counts = tuple(len(children) for children in child_lists)
    augmented_sizes = tuple(len(pool) for pool in augmented_pools)
    control_indices = tuple(index for index, count in enumerate(outside_counts) if count == 0)
    outside_indices = tuple(index for index, count in enumerate(outside_counts) if count > 0)
    if len(control_indices) + len(outside_indices) != len(target_ids):
        raise AssertionError("control/outside subset partition did not cover every target")

    def subset_summary(indices: Sequence[int]) -> dict[str, object]:
        subset_baseline_mean = _mean_probability([baseline_counts[index] for index in indices])
        subset_candidate_mean = _mean_probability([candidate_counts[index] for index in indices])
        return {
            "target_count": len(indices),
            "min_overlap_mean_probability": str(subset_baseline_mean),
            "candidate_mean_probability": str(subset_candidate_mean),
            "absolute_delta": str(subset_candidate_mean - subset_baseline_mean),
        }

    pool_stats = _int_stats(augmented_sizes)
    child_stats = _int_stats(child_counts)

    payload: dict[str, object] = {
        "schema_id": "lottolab.research.b649_outside_native_single_crossover_augmentation",
        "schema_version": "1.0.0",
        "selector_id": AUGMENTATION_ID,
        "target_count": len(target_ids),
        "authorities": {
            "branch2_result_blob": BRANCH2_RESULT_BLOB,
            "branch2_result_sha256": BRANCH2_RESULT_SHA256,
            "baseline_result_locator": BASELINE_RESULT_LOCATOR,
            "baseline_result_sha256": baseline_result_sha,
            "upstream_candidate_locator": (
                "docs/research/b649-min-overlap-full-union-local-refinement-r1-result.json"
            ),
            "upstream_head": "6844ee6fd49616b99d53972d54399a12090e6139",
            "full_union_archive_sha256": _hash_portfolio_archive(unions),
            "min_overlap_k10_archive_sha256": _hash_portfolio_archive(baseline),
            "augmented_pool_archive_sha256": _hash_portfolio_archive(augmented_pools),
            "candidate_k10_archive_sha256": _hash_portfolio_archive(candidate),
        },
        "native_full_union": {
            "size_distribution": dict(sorted(Counter(map(len, unions)).items())),
            "outside_native_count_distribution": dict(sorted(Counter(outside_counts).items())),
            "outside_native_total": sum(outside_counts),
        },
        "augmentation": {
            "augmented_pool_size": pool_stats.as_json(),
            "generated_child_count": child_stats.as_json(),
            "targets_with_generated_children": sum(1 for count in child_counts if count > 0),
        },
        "search": {
            "k": K,
            "seed": SELECTION_SEED,
            "sample_main_draw_count": SELECTION_DRAW_COUNT,
            "iteration_cap": ITERATION_CAP,
            "move": "ONE_FOR_ONE_SWAP",
            "tie_break": "REMOVE_PORTFOLIO_POSITION_THEN_ADD_FULL_UNION_POSITION",
            "acceptance": "STRICT_SAMPLE_OFFICIAL_ANY_PRIZE_IMPROVEMENT",
            "targets_with_any_swap": any_swap,
            "targets_with_final_portfolio_change": changed,
            "mean_swap_count": str(
                Fraction(sum(item.swap_count for item in selections), len(selections))
            ),
            "swap_count_distribution": dict(
                sorted(Counter(item.swap_count for item in selections).items())
            ),
        },
        "evaluation": {
            "model_identity": "BIG_LOTTO_UNIFORM_FAIR_DRAW",
            "event_definition": "OFFICIAL_ANY_PRIZE",
            "exact_outcome_space_count": TOTAL_OUTCOME_SPACE,
            "min_overlap_mean_probability": str(baseline_mean),
            "candidate_mean_probability": str(candidate_mean),
            "absolute_delta": str(delta),
            "relative_delta": str(relative),
            "material_relative_gain_threshold": str(MATERIAL_RELATIVE_GAIN_THRESHOLD),
            "ready_for_branch2_oos": "YES" if ready else "NO",
            "control_subset_o_zero": subset_summary(control_indices),
            "outside_subset_o_gt_zero": subset_summary(outside_indices),
        },
        "claim_boundary": {
            "target_outcomes_inspected": False,
            "k_changed": False,
            "min_overlap_changed": False,
            "branch2_oos_run": False,
            "database_mutated": False,
            "production_action": False,
        },
    }
    result_path = REPO_ROOT / RESULT_LOCATOR
    report_path = REPO_ROOT / REPORT_LOCATOR
    if result_path.exists() or report_path.exists():
        raise FileExistsError("refusing to overwrite an existing study artifact")
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
