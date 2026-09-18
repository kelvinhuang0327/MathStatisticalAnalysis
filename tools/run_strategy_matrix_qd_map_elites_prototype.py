"""One reproducible, bounded BIG_LOTTO K5 run of the native MAP-Elites / QD
prototype (`STRATEGY_MATRIX_NATIVE_MAP_ELITES_QD_PROTOTYPE_R1`).

Every input below was frozen BEFORE this script was ever executed, by
reading only already-sealed canonical sources -- no new baseline study was
launched:

SEED_1 (`CYCLIC_SIDON_SHIFT_OFFSET0_V1`, raw, pre-ascent) and SEED_2 (the
`STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1` BIG_LOTTO k=5 winning
terminal, from `CYCLIC_SIDON_SHIFT_OFFSET1_V1`) are both read verbatim from
`docs/research/matrix-native-results/strategy-matrix-k235-multistart-baseline-v1-result.json`
(`structures.BIG_LOTTO.per_k["5"]`, `STARTS[0].SEED_PORTFOLIO` and
`BEST_TERMINAL_PORTFOLIO` respectively; that file's own report records
`RESULT_SHA256_RUN1/RUN2 = d1e04f50d33fbb5bdd01180ab2fefb0afd99fae7e6f1bf07dee8cfe84000a297`,
`FRESH_PROCESS_BYTE_IDENTITY: PASS`). Their descriptor cells were computed
once during this task's bounded resolution and confirmed materially
different: SEED_1 -> (max_pairwise_overlap=1, union_size=22); SEED_2 ->
(max_pairwise_overlap=0, union_size=30).

STRONG_BASELINE_ID: STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1, BIG_LOTTO,
k=5 cell (BEST_EXACT_Q=54130/582659, LOCAL_OPTIMUM_STATUS=
EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM, all 4 independent frozen cyclic-Sidon
starts converged to this same exact Q; the sealed result's top-level
`gate.MULTISTART_EXECUTION_GATE` is PASS).
STRONG_BASELINE_SELECTION_RULE (frozen before running this script): select
the maximum BEST_EXACT_Q among every sealed, gate-PASS, multistart-verified
canonical BIG_LOTTO K=5 exact-coverage study at the M3_PLUS objective in
`docs/research/matrix-native-results/`. This is currently the only such
study in the bounded resolution; the sealed
`strategy-matrix-phase7-reference-designation-v1-report.md` additionally
confirms Method E (`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`) only
*ties*, never beats, Reference R at k in {1, 3, 5} -- so no sealed K=5
result is known to exceed this baseline. SEED_2 equals this baseline by
construction: it is deliberately included as a seed so QD's one-exchange
wave also probes the immediate neighborhood of the strongest already-known
K5 result, not only a weaker starting point.

MINIMUM_MATCHES = 3 (M3_PLUS) -- matches the baseline's own primary_event,
so quality is directly comparable without re-deriving it under a different
objective.

FIXED_EVALUATION_BUDGET = 2580 -- exactly SEED_1's 1290 legal one-exchange
neighbors plus SEED_2's 1290 (6 * 43 * 5 tickets each, zero collisions with
either seed's own tickets, confirmed by direct enumeration before this
script was written). This is a hard cap covering precisely one full
emission wave from each frozen seed and nothing more: no frontier queue, no
second generation, no automatic escalation.

COMPETITIVE_THRESHOLD (frozen before running): a non-seed discovery counts
as "retaining competitive exact uniform-draw coverage" only if its exact
coverage is >= 90% of BEST_STRONG_BASELINE_EXACT_COVERAGE. This threshold
was chosen before this script was ever run and is not adjusted afterward.

FINAL_VERDICT rule (corrected at R1 local closure):
  NEW_DESCRIPTOR_CELL_COUNT > 0 and BEST_QD_EXACT_COVERAGE (best among
    NON-SEED archive entries only -- what QD itself actually discovered,
    not the seeds it was merely handed) >= COMPETITIVE_THRESHOLD
    and BEST_QD_EXACT_COVERAGE >= BEST_STRONG_BASELINE_EXACT_COVERAGE
    -> QD_VALUE_SIGNAL_FOUND
  NEW_DESCRIPTOR_CELL_COUNT == 0, or a non-empty archive whose best non-seed
    discovery falls below COMPETITIVE_THRESHOLD or the fixed strong baseline
    -> QD_MORPHOLOGY_ONLY_NO_VALUE_SIGNAL
  Any exception, invariant violation (e.g. evaluated_candidate_count !=
    2580), or non-deterministic re-run mismatch -> QD_BOUNDED_PROTOTYPE_FAILED

The pre-run classification checked only novelty and the 90% competitive
bar. R1 closure adds only the guard that a negative exact-coverage delta
cannot be a value signal; the competitive threshold remains unchanged.
This does not establish a new positive-improvement threshold.

QD_CANDIDATE_SELECTION_RULE (frozen before running): among non-seed archive
entries, maximize exact coverage; exact ties resolve by canonical
lexicographic portfolio order, then descriptor cell order.
"""

from __future__ import annotations

import json
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    fast_exact_portfolio_coverage,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import canonicalize_portfolio
from lottolab.research.strategy_matrix_qd_map_elites import (
    DescriptorCell,
    EliteEntry,
    MapElitesResult,
    Portfolio,
    portfolio_descriptor_cell,
    run_map_elites,
)

RESULT_PATH = Path(
    "docs/research/matrix-native-results/strategy-matrix-k235-multistart-baseline-v1-result.json"
)
MINIMUM_MATCHES = 3
FIXED_EVALUATION_BUDGET = 2580
COMPETITIVE_THRESHOLD_RATIO = Fraction(90, 100)
BASELINE_SELECTION_RULE = (
    "max BEST_EXACT_Q among sealed, gate-PASS, multistart-verified "
    "canonical BIG_LOTTO K5 M3_PLUS exact-coverage studies"
)
QD_CANDIDATE_SELECTION_RULE = (
    "max exact coverage among non-seed archive entries; ties by canonical "
    "lexicographic portfolio, then descriptor cell"
)


def _canonical_portfolio(raw: object) -> Portfolio:
    if not isinstance(raw, list):
        raise ValueError("portfolio JSON value must be a list")
    raw_tickets = cast(list[object], raw)
    tickets: list[tuple[int, ...]] = []
    for raw_ticket in raw_tickets:
        if not isinstance(raw_ticket, list):
            raise ValueError("ticket JSON value must be a list")
        raw_numbers = cast(list[object], raw_ticket)
        numbers: list[int] = []
        for raw_number in raw_numbers:
            if type(raw_number) is not int:
                raise ValueError("ticket numbers must be integers")
            numbers.append(raw_number)
        tickets.append(tuple(numbers))
    return canonicalize_portfolio(tickets)


def _load_frozen_seeds_and_baseline() -> tuple[Portfolio, Portfolio, Fraction]:
    with RESULT_PATH.open() as handle:
        data: dict[str, Any] = json.load(handle)
    k5: dict[str, Any] = data["structures"]["BIG_LOTTO"]["per_k"]["5"]
    starts: list[dict[str, Any]] = k5["STARTS"]
    starts_by_id = {start["START_ID"]: start for start in starts}

    seed_1 = _canonical_portfolio(
        starts_by_id["CYCLIC_SIDON_SHIFT_OFFSET0_V1"]["SEED_PORTFOLIO"]
    )
    seed_2 = _canonical_portfolio(k5["BEST_TERMINAL_PORTFOLIO"])
    best_exact_q: dict[str, Any] = k5["BEST_EXACT_Q"]
    baseline_q = Fraction(best_exact_q["numerator"], best_exact_q["denominator"])
    gate: dict[str, Any] = data["gate"]
    if gate["MULTISTART_EXECUTION_GATE"] != "PASS":
        raise ValueError("sealed baseline gate is not PASS")
    if k5["LOCAL_OPTIMUM_STATUS"] != "EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM":
        raise ValueError("sealed K5 baseline is not locally certified")
    return seed_1, seed_2, baseline_q


def _best_non_seed_entry(
    result: MapElitesResult,
) -> tuple[DescriptorCell, EliteEntry] | None:
    candidates = [(cell, entry) for cell, entry in result.archive.items() if not entry.is_seed]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (-item[1].quality, item[1].portfolio, item[0]),
    )


def classify_final_verdict(
    *,
    evaluated_candidate_count: int,
    new_descriptor_cell_count: int,
    best_qd_exact_coverage: Fraction | None,
    strong_baseline_q: Fraction,
) -> str:
    """Classify frozen metrics without executing the expensive prototype."""
    competitive_bar = strong_baseline_q * COMPETITIVE_THRESHOLD_RATIO
    if evaluated_candidate_count != FIXED_EVALUATION_BUDGET:
        return "QD_BOUNDED_PROTOTYPE_FAILED"
    if new_descriptor_cell_count > 0 and best_qd_exact_coverage is not None and (
        best_qd_exact_coverage >= competitive_bar
        and best_qd_exact_coverage >= strong_baseline_q
    ):
        return "QD_VALUE_SIGNAL_FOUND"
    return "QD_MORPHOLOGY_ONLY_NO_VALUE_SIGNAL"


def main() -> int:
    seed_1, seed_2, strong_baseline_q = _load_frozen_seeds_and_baseline()
    seeds = (seed_1, seed_2)
    seed_descriptor_cells = frozenset(
        portfolio_descriptor_cell(seed, BIG_LOTTO_RULE_CONTRACT) for seed in seeds
    )

    print("SEED_IDENTITIES: CYCLIC_SIDON_SHIFT_OFFSET0_V1 (raw), "
          "STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1 BIG_LOTTO k=5 BEST_TERMINAL_PORTFOLIO")
    print("STRONG_BASELINE_ID: STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1 (BIG_LOTTO, k=5)")
    print(f"STRONG_BASELINE_SELECTION_RULE: {BASELINE_SELECTION_RULE}")
    print(f"QD_CANDIDATE_SELECTION_RULE: {QD_CANDIDATE_SELECTION_RULE}")
    print(f"STRONG_BASELINE_EXACT_Q: {strong_baseline_q}")
    print(f"MINIMUM_MATCHES: {MINIMUM_MATCHES}")
    print(f"FIXED_EVALUATION_BUDGET: {FIXED_EVALUATION_BUDGET}")
    print(f"SEED_DESCRIPTOR_CELLS: {sorted(seed_descriptor_cells)}")

    start_time = time.monotonic()
    result = run_map_elites(
        seeds,
        BIG_LOTTO_RULE_CONTRACT,
        minimum_matches=MINIMUM_MATCHES,
        evaluation_budget=FIXED_EVALUATION_BUDGET,
    )
    elapsed = time.monotonic() - start_time
    if result.seed_descriptor_cells != seed_descriptor_cells:
        raise RuntimeError("seed descriptor snapshot changed before exploration")

    # A seed's own quality must be reported even if a neighbor later
    # replaced it in the archive, so it is recomputed directly rather than
    # read back from `result.archive`.
    direct_seed_qualities: list[Fraction] = []
    for seed in seeds:
        q = fast_exact_portfolio_coverage(49, 6, MINIMUM_MATCHES, seed)
        clear_cache()
        direct_seed_qualities.append(q)
    best_seed_exact_coverage = max(direct_seed_qualities)

    best_qd_entry = _best_non_seed_entry(result)
    best_qd_exact_coverage = best_qd_entry[1].quality if best_qd_entry is not None else None

    print()
    print(f"SEED_COUNT: {result.seed_count}")
    print(f"SEED_DESCRIPTOR_CELLS_CONFIRMED: {sorted(result.seed_descriptor_cells)}")
    print(f"EVALUATED_CANDIDATE_COUNT: {result.evaluated_candidate_count}")
    print(f"FINAL_OCCUPIED_CELLS: {sorted(result.final_descriptor_cells)}")
    print(f"NEW_DESCRIPTOR_CELL_COUNT: {result.new_descriptor_cell_count}")
    print(f"NON_SEED_ELITE_COUNT: {result.non_seed_elite_count}")
    print()
    print(f"BEST_SEED_EXACT_COVERAGE: {best_seed_exact_coverage}")
    print(f"BEST_STRONG_BASELINE_EXACT_COVERAGE: {strong_baseline_q}")
    print(f"BEST_QD_EXACT_COVERAGE (best non-seed discovery): {best_qd_exact_coverage}")
    if best_qd_exact_coverage is not None:
        print(f"DELTA_QD_VS_SEED: {best_qd_exact_coverage - best_seed_exact_coverage}")
        print(f"DELTA_QD_VS_STRONG_BASELINE: {best_qd_exact_coverage - strong_baseline_q}")
    if best_qd_entry is not None:
        cell, entry = best_qd_entry
        print(f"QD_CANDIDATE_DESCRIPTOR_CELL: {cell}")
        print(f"QD_CANDIDATE_PORTFOLIO: {entry.portfolio}")
        print(f"QD_CANDIDATE_EXACT_COVERAGE: {entry.quality}")
    print(f"ELAPSED_TIME: {elapsed:.2f}s")
    print(f"BUDGET_EXHAUSTED: {result.budget_exhausted}")

    competitive_bar = strong_baseline_q * COMPETITIVE_THRESHOLD_RATIO
    print(f"COMPETITIVE_THRESHOLD (90% of strong baseline): {competitive_bar}")

    verdict = classify_final_verdict(
        evaluated_candidate_count=result.evaluated_candidate_count,
        new_descriptor_cell_count=result.new_descriptor_cell_count,
        best_qd_exact_coverage=best_qd_exact_coverage,
        strong_baseline_q=strong_baseline_q,
    )

    print()
    print(f"FINAL_VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAILURE: {type(exc).__name__}: {exc}")
        print("FINAL_VERDICT: QD_BOUNDED_PROTOTYPE_FAILED")
        raise SystemExit(1) from exc
