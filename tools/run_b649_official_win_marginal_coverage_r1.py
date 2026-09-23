"""Run the frozen, outcome-free B649 K10 marginal-coverage comparison."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from pathlib import Path
from typing import cast

from lottolab.research.b649_arm_d_vs_sealed_exact_probability import (
    BRANCH2_UPSTREAM_COMMIT,
    BRANCH2_UPSTREAM_TREE,
    DRAW_SIZE,
    EVALUATOR_CONTENT_SHA256,
    EXPECTED_ARCHIVE_ROW_COUNT,
    POOL_SIZE,
    SEALED_INPUT_LOCATOR,
    SEALED_INPUT_SHA256,
    TOTAL_MAIN_DRAWS,
    TOTAL_OUTCOME_SPACE,
    load_frozen_arm_d_archive,
    verify_evaluator_content_sha256,
    verify_sealed_input_file,
)
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.research.b649_official_win_marginal_coverage_selector import (
    EVENT_ID,
    FROZEN_K10_SPEC,
    MODEL_ID,
    PRIMARY_K,
    SECONDARY_K,
    SELECTOR_ID,
    SelectionResult,
    generate_selection_draw_sample,
    select_official_win_marginal_coverage,
)

BASELINE_RESULT_LOCATOR = (
    "docs/research/b649-arm-d-vs-sealed-outcome-free-exact-probability-r1-result.json"
)
BASELINE_RESULT_SHA256 = "4cb38b0257b917d9dcd330049848e6406cf73f9c2a5c2702b439a0c08fea4c21"
MATERIAL_RELATIVE_GAIN_THRESHOLD = Fraction(1, 100)
EXACT_EVALUATION_WORKERS = 2
RESULT_LOCATOR = "docs/research/b649-official-win-marginal-coverage-r1-result.json"
REPORT_LOCATOR = "docs/research/b649-official-win-marginal-coverage-r1-report.md"
STUDY_ID = "B649_OFFICIAL_WIN_MARGINAL_COVERAGE_PREOUTCOME_R1"
REPO_ROOT = Path(__file__).resolve().parents[1]

_exact_draws: DrawMasks | None = None


def _hash_portfolio_archive(
    portfolios: Sequence[Sequence[Sequence[int]]],
) -> str:
    canonical_json = json.dumps(
        [[list(ticket) for ticket in portfolio] for portfolio in portfolios],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_json.encode("ascii")).hexdigest()


def _load_baseline_exact_mean(path: Path) -> tuple[Fraction, str]:
    raw_bytes = path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != BASELINE_RESULT_SHA256:
        raise ValueError("frozen outcome-free baseline result SHA-256 mismatch")
    result = cast(dict[str, object], json.loads(raw_bytes))
    authorities = cast(dict[str, object], result["authorities"])
    model = cast(dict[str, object], result["model"])
    baseline_k10 = cast(dict[str, object], result["k10"])
    claim_boundary = cast(dict[str, object], result["claim_boundary"])

    if authorities.get("sealed_input_sha256") != SEALED_INPUT_SHA256:
        raise ValueError("baseline result does not match the frozen candidate input")
    if authorities.get("evaluator_content_sha256") != EVALUATOR_CONTENT_SHA256:
        raise ValueError("baseline result does not match the frozen exact evaluator")
    if model.get("model_identity") != MODEL_ID or model.get("event_definition") != EVENT_ID:
        raise ValueError("baseline result model or event definition mismatch")
    if baseline_k10.get("row_count") != EXPECTED_ARCHIVE_ROW_COUNT:
        raise ValueError("baseline K10 row count mismatch")
    if claim_boundary.get("outcome_fields_used") is not False:
        raise ValueError("baseline artifact does not certify its outcome-free boundary")
    if claim_boundary.get("historical_oos_rerun") is not False:
        raise ValueError("baseline artifact reports a historical OOS rerun")

    exact_mean = Fraction(str(baseline_k10["exact_mean_arm_d_probability"]))
    return exact_mean, digest


def _initialize_exact_evaluator() -> None:
    global _exact_draws
    _exact_draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)


def _evaluate_exact_probability_count(portfolio: tuple[tuple[int, ...], ...]) -> int:
    if _exact_draws is None:
        raise RuntimeError("exact evaluator worker was not initialized")
    result = evaluate_portfolio(portfolio, draws=_exact_draws)
    return result.official_any_prize_outcome_count


def _evaluate_new_portfolios_exact(
    portfolios: Sequence[tuple[tuple[int, ...], ...]],
) -> tuple[int, ...]:
    unique_portfolios = tuple(dict.fromkeys(portfolios))
    unique_counts: list[int] = []
    with ProcessPoolExecutor(
        max_workers=EXACT_EVALUATION_WORKERS,
        initializer=_initialize_exact_evaluator,
    ) as executor:
        for index, count in enumerate(
            executor.map(_evaluate_exact_probability_count, unique_portfolios, chunksize=1),
            start=1,
        ):
            unique_counts.append(count)
            if index % 100 == 0 or index == len(unique_portfolios):
                print(f"Exact portfolios complete: {index}/{len(unique_portfolios)}", flush=True)

    count_by_portfolio = dict(zip(unique_portfolios, unique_counts, strict=True))
    return tuple(count_by_portfolio[portfolio] for portfolio in portfolios)


def _select_k10_portfolios(
    candidate_pools: Sequence[tuple[tuple[int, ...], ...]],
) -> tuple[SelectionResult, ...]:
    selection_draws = generate_selection_draw_sample()
    selections: list[SelectionResult] = []
    for index, candidate_pool in enumerate(candidate_pools, start=1):
        selection = select_official_win_marginal_coverage(
            candidate_pool,
            PRIMARY_K,
            selection_draws=selection_draws,
        )
        selections.append(selection)
        if index % 100 == 0 or index == len(candidate_pools):
            print(f"Selection pools complete: {index}/{len(candidate_pools)}", flush=True)
    return tuple(selections)


def _write_new_artifact(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        raise FileExistsError(f"refusing to overwrite a different frozen artifact: {path}")
    path.write_text(content, encoding="utf-8")


def render_report(payload: dict[str, object]) -> str:
    k10 = cast(dict[str, object], payload["k10"])
    k20 = cast(dict[str, object], payload["k20"])
    authority = cast(dict[str, object], payload["authorities"])
    delta = Fraction(str(k10["exact_delta"]))
    baseline = Fraction(str(k10["baseline_exact_mean_probability"]))
    selected = Fraction(str(k10["selector_exact_mean_probability"]))
    relative = delta / baseline if baseline else Fraction(0)
    ready = str(k10["ready_for_branch2_oos"])

    return "\n".join(
        [
            "# B649 Official-Win Marginal-Coverage Selector R1",
            "",
            "## Frozen comparison contract",
            "",
            f"- Selector: `{SELECTOR_ID}`; event: `{EVENT_ID}`; model: `{MODEL_ID}`.",
            f"- Candidate input: `{authority['sealed_input_locator']}`.",
            f"- Candidate input SHA-256: `{authority['sealed_input_sha256']}`.",
            "- Each row's fixed K10 pool is its frozen K20 `MIN_OVERLAP` portfolio.",
            "  The K10 baseline is nested in every pool.",
            f"- Candidate-pool archive SHA-256: `{authority['candidate_pool_archive_sha256']}`.",
            f"- K10 baseline archive SHA-256: `{authority['min_overlap_k10_archive_sha256']}`.",
            f"- K10 selected archive SHA-256: `{authority['selector_k10_archive_sha256']}`.",
            f"- Rows {k10['row_count']}; pools {k10['unique_candidate_pool_count']}; N=20.",
            (
                f"- Selection evidence: {FROZEN_K10_SPEC.selection_draw_count:,} uniform main-draw "
                f"samples, seed `{FROZEN_K10_SPEC.selection_seed}`."
            ),
            "  The special ball is integrated analytically for each sampled main draw.",
            (
                f"- Final evaluation: exhaustive exact enumeration of {TOTAL_MAIN_DRAWS:,} main "
                f"draws and {POOL_SIZE - DRAW_SIZE} legal special balls per draw."
            ),
            "  This uses the existing official-prize evaluator.",
            (
                "- Selector Monte Carlo scores are not used as final probability "
                "estimates; final values are"
            ),
            "  recomputed by exhaustive enumeration of the full model outcome space.",
            "",
            "## K10 pre-outcome model comparison",
            "",
            "| Metric | MIN_OVERLAP | Marginal coverage | Delta |",
            "|---|---:|---:|---:|",
            (
                f"| Mean OFFICIAL_ANY_PRIZE probability | {baseline} ({float(baseline):.8f}) "
                f"| {selected} ({float(selected):.8f}) | {delta} ({float(delta):+.8f}) |"
            ),
            f"| Relative change vs MIN_OVERLAP | — | — | {relative} ({float(relative):+.4%}) |",
            f"| Material hurdle | — | — | at least {k10['material_relative_gain_threshold']} |",
            f"| READY_FOR_BRANCH2_OOS | — | — | **{ready}** |",
            "",
            "The materiality rule was fixed before exact comparison: mean official-win probability "
            "must improve by at least 1% relative to the frozen K10 `MIN_OVERLAP` baseline.",
            "This model result makes no claim about future wins, payout, profit, or edge.",
            "",
            "## K20 disposition",
            "",
            f"`{k20['status']}`: each K20 pool contains exactly 20 tickets.",
            "Selecting K20 forces all pool members, leaving no selection decision.",
            "",
            "## Outcome and scope boundary",
            "",
            "- No target numbers, scores, prizes, payouts, or outcomes were read.",
            "- No outcome replay or OOS run occurred.",
            "- No candidate-pool change, K increase, or `MIN_OVERLAP` modification occurred.",
            "- No database or production mutation, push, PR, or governance expansion occurred.",
            "",
            f"Study ID: `{STUDY_ID}`.",
            f"Baseline exact-result SHA-256: `{authority['baseline_result_sha256']}`.",
            f"Official evaluator SHA-256: `{authority['evaluator_content_sha256']}`.",
            f"Branch2 authority commit: `{authority['branch2_upstream_commit']}`.",
            f"Branch2 authority tree: `{authority['branch2_upstream_tree']}`.",
            "",
        ]
    )


def run() -> dict[str, object]:
    verify_sealed_input_file()
    verify_evaluator_content_sha256()
    target_ids, archive = load_frozen_arm_d_archive()
    k10_baseline = archive[PRIMARY_K]
    k20_candidate_pools = archive[SECONDARY_K]

    if len(target_ids) != EXPECTED_ARCHIVE_ROW_COUNT:
        raise ValueError("outcome-free archive row count mismatch")
    if len(k10_baseline) != len(k20_candidate_pools):
        raise ValueError("K10 baseline and K20 candidate-pool row counts differ")

    pool_sizes = {len(pool) for pool in k20_candidate_pools}
    if pool_sizes != {SECONDARY_K}:
        raise ValueError("K20 baseline pools do not have the frozen candidate-pool size")
    nested = all(
        set(baseline).issubset(set(candidate_pool))
        for baseline, candidate_pool in zip(k10_baseline, k20_candidate_pools, strict=True)
    )
    if not nested:
        raise ValueError("a frozen K10 MIN_OVERLAP baseline is outside its K20 candidate pool")

    baseline_result_path = REPO_ROOT / BASELINE_RESULT_LOCATOR
    baseline_probability, baseline_result_sha256 = _load_baseline_exact_mean(baseline_result_path)
    selections = _select_k10_portfolios(k20_candidate_pools)
    selector_portfolios = tuple(selection.portfolio for selection in selections)
    exact_counts = _evaluate_new_portfolios_exact(selector_portfolios)
    selector_probability = Fraction(
        sum(exact_counts), len(selector_portfolios) * TOTAL_OUTCOME_SPACE
    )
    delta = selector_probability - baseline_probability
    relative_delta = delta / baseline_probability
    relative_threshold = MATERIAL_RELATIVE_GAIN_THRESHOLD
    ready = relative_delta >= relative_threshold

    candidate_pool_archive_sha256 = _hash_portfolio_archive(k20_candidate_pools)
    baseline_archive_sha256 = _hash_portfolio_archive(k10_baseline)
    selector_archive_sha256 = _hash_portfolio_archive(selector_portfolios)
    payload: dict[str, object] = {
        "schema_id": "lottolab.research.b649_official_win_marginal_coverage",
        "schema_version": "1.0.0",
        "study_id": STUDY_ID,
        "selector": {
            "selector_id": SELECTOR_ID,
            "primary_k": PRIMARY_K,
            "selection_draw_count": FROZEN_K10_SPEC.selection_draw_count,
            "selection_seed": FROZEN_K10_SPEC.selection_seed,
            "tie_break": FROZEN_K10_SPEC.tie_break,
            "special_ball_handling": FROZEN_K10_SPEC.special_ball_handling,
        },
        "authorities": {
            "sealed_input_locator": SEALED_INPUT_LOCATOR,
            "sealed_input_sha256": SEALED_INPUT_SHA256,
            "baseline_result_locator": BASELINE_RESULT_LOCATOR,
            "baseline_result_sha256": baseline_result_sha256,
            "evaluator_content_sha256": EVALUATOR_CONTENT_SHA256,
            "branch2_upstream_commit": BRANCH2_UPSTREAM_COMMIT,
            "branch2_upstream_tree": BRANCH2_UPSTREAM_TREE,
            "candidate_pool_archive_sha256": candidate_pool_archive_sha256,
            "min_overlap_k10_archive_sha256": baseline_archive_sha256,
            "selector_k10_archive_sha256": selector_archive_sha256,
        },
        "model": {
            "model_identity": MODEL_ID,
            "event_definition": EVENT_ID,
            "exactness": "EXHAUSTIVE_COMBINATORIAL_OFFICIAL_PRIZE_PROBABILITY",
            "main_draw_count": TOTAL_MAIN_DRAWS,
            "special_ball_count_per_main_draw": POOL_SIZE - DRAW_SIZE,
            "outcome_space_count": TOTAL_OUTCOME_SPACE,
        },
        "k10": {
            "row_count": len(selector_portfolios),
            "unique_candidate_pool_count": len(set(k20_candidate_pools)),
            "candidate_pool_size_per_row": SECONDARY_K,
            "baseline_nested_rows": len(k10_baseline),
            "baseline_exact_mean_probability": str(baseline_probability),
            "selector_exact_mean_probability": str(selector_probability),
            "exact_delta": str(delta),
            "relative_delta": str(relative_delta),
            "material_relative_gain_threshold": str(relative_threshold),
            "selection_sample_official_any_prize_mean": str(
                sum(
                    (item.sample_official_any_prize_probability for item in selections),
                    start=Fraction(0),
                )
                / len(selections)
            ),
            "exact_probability_evaluated_portfolio_count": len(set(selector_portfolios)),
            "exact_evaluation_workers": EXACT_EVALUATION_WORKERS,
            "ready_for_branch2_oos": "YES" if ready else "NO",
        },
        "k20": {
            "status": "SKIPPED_FORCED_SELECTION",
            "candidate_pool_size_per_row": SECONDARY_K,
            "requested_k": SECONDARY_K,
        },
        "claim_boundary": {
            "target_outcomes_used": False,
            "outcome_replay": False,
            "branch2_oos_run": False,
            "candidate_pool_changed": False,
            "k_increased": False,
            "min_overlap_modified": False,
            "database_mutated": False,
            "production_action": False,
            "historical_win_rate_tuning": False,
        },
    }

    result_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _write_new_artifact(REPO_ROOT / RESULT_LOCATOR, result_text)
    report = render_report(payload)
    _write_new_artifact(REPO_ROOT / REPORT_LOCATOR, report)
    return payload


if __name__ == "__main__":
    run()
