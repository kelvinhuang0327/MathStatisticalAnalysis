"""Run one pre-outcome K10 local refinement over the frozen Branch2 cohort."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import cast

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    build_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths
from lottolab.research.b649_arm_d_vs_sealed_exact_probability import (
    EVALUATOR_CONTENT_SHA256,
    EXPECTED_ARCHIVE_ROW_COUNT,
    SEALED_INPUT_LOCATOR,
    SEALED_INPUT_SHA256,
    TOTAL_OUTCOME_SPACE,
    load_frozen_arm_d_archive,
    verify_evaluator_content_sha256,
    verify_sealed_input_file,
)
from lottolab.research.b649_min_overlap_full_union_local_refinement import (
    ITERATION_CAP,
    SELECTION_DRAW_COUNT,
    SELECTION_SEED,
    SELECTOR_ID,
    K,
    Portfolio,
    RefinementResult,
    Ticket,
    refine_min_overlap_k10,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.research.b649_official_win_marginal_coverage_selector import (
    generate_selection_draw_sample,
)
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from tools.b649_operational_prediction_loop import STRATEGY_STREAMS, StrategyStream

REPO_ROOT = Path(__file__).resolve().parents[1]
BRANCH2_RESULT_BLOB = "feb5b2c715cd107e6dc18ed6566c0cacb96277d9"
BRANCH2_RESULT_SHA256 = "af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3"
BASELINE_RESULT_LOCATOR = (
    "docs/research/b649-arm-d-vs-sealed-outcome-free-exact-probability-r1-result.json"
)
BASELINE_RESULT_SHA256 = "4cb38b0257b917d9dcd330049848e6406cf73f9c2a5c2702b439a0c08fea4c21"
RESULT_LOCATOR = "docs/research/b649-min-overlap-full-union-local-refinement-r1-result.json"
REPORT_LOCATOR = "docs/research/b649-min-overlap-full-union-local-refinement-r1-report.md"
MATERIAL_RELATIVE_GAIN_THRESHOLD = Fraction(1, 100)
EXACT_EVALUATION_WORKERS = 2

_exact_draws: DrawMasks | None = None


@dataclass(frozen=True, slots=True)
class PredrawRow:
    """Only the causal identities projected from the pinned Branch2 result."""

    target_draw: str
    target_date: str
    cutoff_draw: str
    cutoff_date: str
    history_count: int
    history_sha256: str
    pool_sha256: str
    candidate_count: int


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def _hash_portfolio_archive(portfolios: Sequence[Portfolio]) -> str:
    return hashlib.sha256(
        json.dumps(
            [[list(ticket) for ticket in portfolio] for portfolio in portfolios],
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()


def _project_branch2_predraw_rows() -> tuple[PredrawRow, ...]:
    """Extract only pre-draw fields; never decode or expose paired outcome scores."""

    raw = subprocess.run(
        ["git", "cat-file", "blob", BRANCH2_RESULT_BLOB],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    if hashlib.sha256(raw).hexdigest() != BRANCH2_RESULT_SHA256:
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: Branch2 digest")
    if b'"by_k":{"10":' not in raw:
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: K10 layout")
    blocks = [match.end() for match in re.finditer(rb'"paired_draws":\[', raw)]
    if len(blocks) != 3:
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: paired layout")
    k10_bytes = raw[blocks[0] : blocks[1]]

    def field(name: str, value_pattern: bytes) -> list[str]:
        pattern = rb'"' + name.encode() + rb'":' + value_pattern
        return [value.decode("ascii") for value in re.findall(pattern, k10_bytes)]

    columns = {
        "target_draw": field("target_draw", rb'"([^\"]+)"'),
        "target_date": field("target_date", rb'"([^\"]+)"'),
        "cutoff_draw": field("cutoff_draw", rb'"([^\"]+)"'),
        "cutoff_date": field("cutoff_date", rb'"([^\"]+)"'),
        "history_count": field("history_count", rb"(\d+)"),
        "history_sha256": field("history_sha256", rb'"([0-9a-f]{64})"'),
        "pool_sha256": field("pool_sha256", rb'"([0-9a-f]{64})"'),
        "candidate_count": field("candidate_count", rb"(\d+)"),
    }
    if any(len(values) != EXPECTED_ARCHIVE_ROW_COUNT for values in columns.values()):
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: pre-draw field count")
    rows = tuple(
        PredrawRow(
            target_draw=columns["target_draw"][index],
            target_date=columns["target_date"][index],
            cutoff_draw=columns["cutoff_draw"][index],
            cutoff_date=columns["cutoff_date"][index],
            history_count=int(columns["history_count"][index]),
            history_sha256=columns["history_sha256"][index],
            pool_sha256=columns["pool_sha256"][index],
            candidate_count=int(columns["candidate_count"][index]),
        )
        for index in range(EXPECTED_ARCHIVE_ROW_COUNT)
    )
    if len({row.target_draw for row in rows}) != len(rows):
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: duplicate target")
    return rows


def _load_history_before(
    connection: sqlite3.Connection, row: PredrawRow
) -> tuple[CausalDrawRow, ...]:
    """Read only strict-prefix main draws, never the target's main or special ball."""

    dates = connection.execute(
        "SELECT draw_date FROM draws WHERE lottery_type = ? AND draw_number = ?",
        (LotteryType.BIG_LOTTO.value, row.target_draw),
    ).fetchall()
    if dates != [(row.target_date,)]:
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: target date")
    source_rows = connection.execute(
        "SELECT draw_number, draw_date, main_numbers_json FROM draws "
        "WHERE lottery_type = ? AND "
        "(draw_date < ? OR (draw_date = ? AND CAST(draw_number AS INTEGER) < ?)) "
        "ORDER BY draw_date, CAST(draw_number AS INTEGER)",
        (
            LotteryType.BIG_LOTTO.value,
            row.target_date,
            row.target_date,
            int(row.target_draw),
        ),
    ).fetchall()
    history = tuple(
        CausalDrawRow(str(number), str(day), tuple(json.loads(str(numbers))))
        for number, day, numbers in source_rows
    )
    if (
        len(history) != row.history_count
        or not history
        or (history[-1].draw, history[-1].date) != (row.cutoff_draw, row.cutoff_date)
        or hashlib.sha256(_canonical_bytes([asdict(item) for item in history])).hexdigest()
        != row.history_sha256
    ):
        raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: causal history")
    return history


def _build_full_union(
    history: tuple[CausalDrawRow, ...], streams: Sequence[StrategyStream] = STRATEGY_STREAMS
) -> tuple[tuple[Ticket, ...], str]:
    """Rebuild the pinned eleven-stream pool before any K20 pruning."""

    pool: list[StrategyCandidate] = []
    for stream in streams:
        if not stream.enabled:
            continue
        adapter = stream.adapter_factory()
        if (adapter.strategy_id, adapter.strategy_version) != (
            stream.strategy_id,
            stream.strategy_version,
        ):
            raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: stream identity")
        if isinstance(adapter, PortfolioBetAdapter):
            tickets = adapter.get_bets(history, LotteryType.BIG_LOTTO)
        else:
            ticket, _ = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
            tickets = (ticket,)
        if len(tickets) != stream.native_ticket_count:
            raise ValueError("FULL_PRE_DRAW_UNION_AUTHORITY_UNRESOLVED: stream cardinality")
        pool.append(StrategyCandidate(stream.strategy_id, tickets))
    pool_sha256 = hashlib.sha256(
        _canonical_bytes([(candidate.strategy_id, candidate.tickets) for candidate in pool])
    ).hexdigest()
    distinct_count = len(
        {tuple(sorted(ticket)) for candidate in pool for ticket in candidate.tickets}
    )
    union = tuple(build_portfolio(pool, {}, bucket_sizes=(distinct_count,))[distinct_count])
    return union, pool_sha256


def _load_baseline_mean() -> tuple[Fraction, str]:
    raw = (REPO_ROOT / BASELINE_RESULT_LOCATOR).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != BASELINE_RESULT_SHA256:
        raise ValueError("frozen baseline result SHA-256 mismatch")
    result = cast(dict[str, object], json.loads(raw))
    authorities = cast(dict[str, object], result["authorities"])
    model = cast(dict[str, object], result["model"])
    k10 = cast(dict[str, object], result["k10"])
    claim = cast(dict[str, object], result["claim_boundary"])
    if (
        authorities.get("sealed_input_sha256") != SEALED_INPUT_SHA256
        or authorities.get("evaluator_content_sha256") != EVALUATOR_CONTENT_SHA256
        or model.get("model_identity") != "BIG_LOTTO_UNIFORM_FAIR_DRAW"
        or model.get("event_definition") != "OFFICIAL_ANY_PRIZE"
        or k10.get("row_count") != EXPECTED_ARCHIVE_ROW_COUNT
        or claim.get("outcome_fields_used") is not False
    ):
        raise ValueError("frozen baseline result authority mismatch")
    return Fraction(str(k10["exact_mean_arm_d_probability"])), digest


def _initialize_exact_evaluator() -> None:
    global _exact_draws
    _exact_draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)


def _evaluate_exact_probability_count(portfolio: Portfolio) -> int:
    if _exact_draws is None:
        raise RuntimeError("exact evaluator worker was not initialized")
    return evaluate_portfolio(portfolio, draws=_exact_draws).official_any_prize_outcome_count


def _evaluate_exact_cohort(
    baseline: Sequence[Portfolio], candidate: Sequence[Portfolio]
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    unique = tuple(dict.fromkeys((*baseline, *candidate)))
    counts: list[int] = []
    with ProcessPoolExecutor(
        max_workers=EXACT_EVALUATION_WORKERS,
        initializer=_initialize_exact_evaluator,
    ) as executor:
        for index, count in enumerate(
            executor.map(_evaluate_exact_probability_count, unique, chunksize=4), start=1
        ):
            counts.append(count)
            if index % 100 == 0 or index == len(unique):
                print(f"Exact portfolios complete: {index}/{len(unique)}", flush=True)
    by_portfolio = dict(zip(unique, counts, strict=True))
    return (
        tuple(by_portfolio[portfolio] for portfolio in baseline),
        tuple(by_portfolio[portfolio] for portfolio in candidate),
    )


def _mean_probability(counts: Sequence[int]) -> Fraction:
    return Fraction(sum(counts), len(counts) * TOTAL_OUTCOME_SPACE)


def render_report(payload: dict[str, object]) -> str:
    union = cast(dict[str, object], payload["full_union"])
    search = cast(dict[str, object], payload["search"])
    evaluation = cast(dict[str, object], payload["evaluation"])
    subset = cast(dict[str, object], evaluation["outside_prior20_subset"])
    mean_swaps = Fraction(str(search["mean_swap_count"]))
    baseline = Fraction(str(evaluation["min_overlap_mean_probability"]))
    candidate = Fraction(str(evaluation["candidate_mean_probability"]))
    delta = Fraction(str(evaluation["absolute_delta"]))
    relative = Fraction(str(evaluation["relative_delta"]))
    return "\n".join(
        [
            "# B649 MIN_OVERLAP Full-Union K10 Local Refinement R1",
            "",
            "## Frozen pre-outcome contract",
            "",
            (
                f"- Cohort: {payload['target_count']} targets from the sealed "
                "MIN_OVERLAP K10/K20 archive."
            ),
            (
                "- Full union: eleven same-target strategy streams; "
                f"Branch2 result SHA-256 `{BRANCH2_RESULT_SHA256}`."
            ),
            (
                "- Each target's strict history count, cutoff, history SHA-256, "
                "pool SHA-256, and distinct count matched the pinned replay."
            ),
            (
                "- The Branch2 result supplied only projected pre-draw fields; "
                "paired outcome scores were not decoded or passed to selection."
            ),
            (
                "- Target main and special numbers were excluded from selection "
                "queries; only strict prior history entered the adapters."
            ),
            (
                f"- Selector `{SELECTOR_ID}` starts from frozen K10 MIN_OVERLAP "
                f"tickets; K remains {K}."
            ),
            (
                f"- Selection sample: {SELECTION_DRAW_COUNT:,} seeded main draws, "
                f"seed `{SELECTION_SEED}`; special balls integrated analytically."
            ),
            (
                "- Search: all one-for-one swaps, strict sample improvement, "
                "tie-break (remove position, add pool position), "
                f"maximum {ITERATION_CAP} swaps."
            ),
            (
                "- Final values use the unchanged exhaustive OFFICIAL_ANY_PRIZE "
                "evaluator over all 601,304,088 fair-draw outcomes."
            ),
            "",
            "## Full-union and search diagnostics",
            "",
            f"- Full-union sizes: `{union['size_distribution']}`.",
            (
                f"- Outside-prior-20 counts: `{union['outside_prior20_distribution']}`; "
                f"total {union['outside_prior20_total']}."
            ),
            f"- Targets with outside tickets: {union['targets_with_outside_tickets']}.",
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
            "## Subset with tickets outside the prior 20",
            "",
            f"- Targets: {subset['target_count']}.",
            f"- MIN_OVERLAP mean: {subset['min_overlap_mean_probability']}.",
            f"- Candidate mean: {subset['candidate_mean_probability']}.",
            (
                f"- Absolute delta: {subset['absolute_delta']}; "
                f"relative delta: {subset['relative_delta']}."
            ),
            "- This subset is diagnostic; the all-target mean is the sole primary gate.",
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
    if len(baseline) != len(prior20) or len(baseline) != EXPECTED_ARCHIVE_ROW_COUNT:
        raise ValueError("frozen archive cohort mismatch")
    frozen_mean, baseline_result_sha = _load_baseline_mean()
    sample = generate_selection_draw_sample(sample_count=SELECTION_DRAW_COUNT, seed=SELECTION_SEED)

    database = resolve_local_data_paths().database
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro&immutable=1", uri=True)
    connection.execute("PRAGMA query_only = ON")
    selections: list[RefinementResult] = []
    unions: list[tuple[Ticket, ...]] = []
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
            selections.append(refine_min_overlap_k10(full_union, base, selection_draws=sample))
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
    outside_counts = tuple(len(union) - 20 for union in unions)
    subset_indices = tuple(index for index, count in enumerate(outside_counts) if count > 0)
    subset_baseline_mean = _mean_probability([baseline_counts[index] for index in subset_indices])
    subset_candidate_mean = _mean_probability([candidate_counts[index] for index in subset_indices])
    subset_delta = subset_candidate_mean - subset_baseline_mean
    ready = relative >= MATERIAL_RELATIVE_GAIN_THRESHOLD and changed > 0

    payload: dict[str, object] = {
        "schema_id": "lottolab.research.b649_min_overlap_full_union_local_refinement",
        "schema_version": "1.0.0",
        "selector_id": SELECTOR_ID,
        "target_count": len(target_ids),
        "authorities": {
            "sealed_input_locator": SEALED_INPUT_LOCATOR,
            "sealed_input_sha256": SEALED_INPUT_SHA256,
            "branch2_result_blob": BRANCH2_RESULT_BLOB,
            "branch2_result_sha256": BRANCH2_RESULT_SHA256,
            "baseline_result_locator": BASELINE_RESULT_LOCATOR,
            "baseline_result_sha256": baseline_result_sha,
            "evaluator_content_sha256": EVALUATOR_CONTENT_SHA256,
            "full_union_archive_sha256": _hash_portfolio_archive(unions),
            "min_overlap_k10_archive_sha256": _hash_portfolio_archive(baseline),
            "candidate_k10_archive_sha256": _hash_portfolio_archive(candidate),
        },
        "full_union": {
            "size_distribution": dict(sorted(Counter(map(len, unions)).items())),
            "outside_prior20_distribution": dict(sorted(Counter(outside_counts).items())),
            "outside_prior20_total": sum(outside_counts),
            "targets_with_outside_tickets": len(subset_indices),
            "all_baselines_subset_of_full_union": True,
            "all_pools_match_pinned_predraw_hashes": True,
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
            "selection_sample_baseline_mean": str(
                Fraction(
                    sum(item.initial_sample_outcome_count for item in selections),
                    len(selections)
                    * SELECTION_DRAW_COUNT
                    * (BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE),
                )
            ),
            "selection_sample_candidate_mean": str(
                Fraction(
                    sum(item.final_sample_outcome_count for item in selections),
                    len(selections)
                    * SELECTION_DRAW_COUNT
                    * (BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE),
                )
            ),
        },
        "evaluation": {
            "model_identity": "BIG_LOTTO_UNIFORM_FAIR_DRAW",
            "event_definition": "OFFICIAL_ANY_PRIZE",
            "exact_outcome_space_count": TOTAL_OUTCOME_SPACE,
            "exact_evaluation_workers": EXACT_EVALUATION_WORKERS,
            "min_overlap_mean_probability": str(baseline_mean),
            "candidate_mean_probability": str(candidate_mean),
            "absolute_delta": str(delta),
            "relative_delta": str(relative),
            "material_relative_gain_threshold": str(MATERIAL_RELATIVE_GAIN_THRESHOLD),
            "ready_for_branch2_oos": "YES" if ready else "NO",
            "outside_prior20_subset": {
                "target_count": len(subset_indices),
                "min_overlap_mean_probability": str(subset_baseline_mean),
                "candidate_mean_probability": str(subset_candidate_mean),
                "absolute_delta": str(subset_delta),
                "relative_delta": str(subset_delta / subset_baseline_mean),
            },
        },
        "claim_boundary": {
            "target_outcomes_inspected": False,
            "k_changed": False,
            "frozen_min_overlap_changed": False,
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
