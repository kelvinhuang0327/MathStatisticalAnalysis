# DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 — locked preregistration

Status: LOCKED before any real B649-scale constructor or optimizer call ｜
2026-08-15 ｜ Strategy Matrix Phase 5, Generation 2

`TASK_ID: STRATEGY_MATRIX_PHASE5_B649_CONSTRUCTOR_FRONTIER_LOCK_EXECUTE_R1`,
Owner authorization
`AUTHORIZE_STRATEGY_MATRIX_PHASE5_B649_CONSTRUCTOR_FRONTIER_LOCK_EXECUTE_R1`.
Locks and executes the design frozen in
`strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md`
(commit `971b97b`) using the fast exact evaluator added in commit
`c7e3b4a`, exactly the two-step design-then-lock-and-execute pattern
`strategy-matrix-phase3-p638-diversification-native-design-r1.md` /
`diversification-coverage-p638-zone1-v1-preregistration.md` already used.

## 0. Identity

```text
MATRIX_VARIANT_ID:    DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:               BIG_LOTTO
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
BUILDS ON (immutable, not rerun): DIVERSIFICATION_COVERAGE_B649_V1 (sealed),
  the Phase-5 design doc's arm B/C definitions and frontier rules (971b97b)
```

## 1. Research question (frozen by the design doc, restated)

At fixed ticket count `k`, how close is `CYCLIC_SIDON_SHIFT_B649_V1` to the
best exact `M3_PLUS` coverage found under one fixed, bounded constructor
search, and how much of its advantage over random is reproduced by a
non-Sidon low-overlap constructor? `PREDICTIVE_ADVANTAGE: NOT_TESTED`.
`PRIZE_VALUE_ADVANTAGE: NOT_TESTED`. `GLOBAL_OPTIMUM_STATUS: UNKNOWN`,
always — no arm here is ever called globally optimal.

## 2. Frozen arms (identity only — algorithms already frozen and toy-verified in 971b97b)

```text
A  SIDON_REFERENCE:        CYCLIC_SIDON_SHIFT_B649_V1        (immutable, no mutation)
B  NON_SIDON_LOW_OVERLAP:  GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1  (first real-scale run, this task)
C  BOUNDED_COVERAGE_OPTIMIZER: RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1 (first real-scale run, this task)
D  RANDOM_EXPECTED_BASELINE: exact_coverage_baseline.exact_random_portfolio_coverage (immutable, no mutation)
```

No constructor family is added or changed by this task.

## 3. Contract (frozen)

```text
K:                     {1, 3, 5, 10, 15, 20}
PRIMARY_EVENT:          M3_PLUS
SECONDARY_EVENTS:       M4_PLUS, M5_PLUS, M6
SIDON_MODE:             NESTED_PREFIX  (arms A and B: portfolio(k) is portfolio(k+1) minus its last ticket)
OPTIMIZER_MODE:         INDEPENDENT_PER_K  (arm C: one independent search per ladder rung, no carried portfolio — 971b97b §6.1)
DUPLICATE_TICKETS:      must be exactly 0 for every arm at every k (frozen invariant, asserted at runtime)
```

## 4. Optimizer budget (locked, not to change after results are visible)

```text
SEED:                        20260815
RESTART_COUNT:                5
CANDIDATE_SAMPLE_SIZE:        60
MAX_SWAP_PASSES:               3
MAX_CANDIDATE_EVALUATIONS:    65610   (sum over K of restart_count*(k*candidate_sample_size +
                                        max_swap_passes*k*(candidate_sample_size+1)) = 1215*54 = 65610,
                                        independently reverified at runtime, not just trusted)
BUDGET_CLASS:                  MODERATE
```

## 5. Fast evaluator (locked)

Arm C's search calls `exact_coverage_fast_evaluator.fast_exact_portfolio_coverage`
/ `coverage_with_base` (commit `c7e3b4a`, parity-verified against
`bounded_coverage_optimizer.exact_portfolio_coverage`), via a new module,
`src/lottolab/research/bounded_coverage_optimizer_fast.py`, rather than an
edit to the frozen, toy-tested `bounded_coverage_optimizer.py`. This is the
same algorithm (§6 of 971b97b), not a redefinition — see that module's own
docstring for the parity argument (identical RNG call sequence, coverage
values proven exact-equal, so the two searches can only diverge if control
flow itself diverges, which is directly tested at toy scale). Arm A and
arm D's fresh-at-runtime coverage queries (all four `m` thresholds, since
the sealed `DIVERSIFICATION_COVERAGE_B649_V1` cell only ever locked
`m in {3,4,5}`, never `m=6`) also go through the fast evaluator.
`NO_APPROXIMATION: YES`. `NO_MONTE_CARLO: YES`.

**Cache policy** (locked: clear between swap slots, clear between
restarts, no result-dependent policy — plus one disclosed, results-neutral
addition): this task's benchmark measured ~1.96 GB peak RSS for a single
`k=1` restart with per-slot/per-construction-step clearing (60 cached
tickets' worth of qualifying-draws sets at ~26–67 MB each); leaving an
entire `ticket_count`-step construction phase uncleared before the first
"between restarts" boundary would scale that toward tens of GB for the
richer ladder rungs (`k=20`, `ticket_count=20` construction steps). This
module therefore also clears once per construction step, not only once per
swap slot — a strict superset of the two locked points, verified
results-neutral (`test_clear_cache_does_not_change_results`,
`exact_coverage_fast_evaluator.py`), not a change to the locked policy's
outcome.

## 6. Estimands (frozen by 971b97b §10-11, restated for this execution)

```text
Q_X(k)                        exact M3_PLUS coverage, arm X, k tickets
DELTA_RANDOM_X(k)             Q_X(k) - Q_random_expected(k)
DELTA_SIDON_X(k)               Q_X(k) - Q_sidon(k)
RELATIVE_LIFT_VS_RANDOM(k)     DELTA_RANDOM_X(k) / Q_random_expected(k)
BEST_FOUND_Q(k)                max(Q_sidon(k), Q_B(k), Q_C(k))
SIDON_FRONTIER_GAP(k)          BEST_FOUND_Q(k) - Q_sidon(k)
FRONTIER_CAPTURE_RATIO(k)      [Q_sidon(k)-Q_random(k)] / [BEST_FOUND_Q(k)-Q_random(k)],
                                NOT_APPLICABLE if the denominator <= 0, for k > 1 only
```

Classification (deterministic sign rule over `DELTA_RANDOM_X(k)` for
`k > 1`, reused verbatim from the sealed A/B649, T539, P638 Zone-1
convention) and the frontier-nearness / replication-eligibility rules are
already frozen by 971b97b §11 and applied here exactly, not renegotiated.
`FRONTIER_NEARNESS_MARGIN = 0.90`; `NEAR_FRONTIER = FALSE` if any
`DELTA_SIDON_TO_RANDOM(k) < 0` for `k > 1`. No averaging across `k`.

## 7. Geometry outputs (frozen by 971b97b §8, computed per arm per k here)

For each of arms A, B, C, at every ladder `k`: `max_pairwise_overlap`,
`mean_pairwise_overlap`, `overlap_profile`, `number_use_counts`,
`unique_number_coverage`, `reuse_dispersion` (population stdev of
`number_use_counts`), `duplicate_tickets` (asserted `== 0`). No metric
beyond this list is added post-hoc.

## 8. Boundaries (frozen)

```text
REAL_DRAW_HISTORY:            NONE
PREDICTIVE_ADVANTAGE:          NOT_TESTED
PRIZE_VALUE_ADVANTAGE:         NOT_TESTED
T539 / P638:                   NOT_RUN
A / D MUTATION:                NONE
GLOBAL_OPTIMUM_STATUS:         UNKNOWN (search is bounded, not exhaustive; never claimed proven)
```

## 9. No-rescue commitment

Arms, budget, seed, k ladder, endpoint, optimizer mode, classification,
and frontier rule are locked by this file and by 971b97b before any real
B649-scale value is computed. No new constructor, no extra optimizer
restart, no budget change once results are visible. Any change required
after this point stops with `STOP_PHASE5_POST_LOCK_CHANGE_REQUIRED`
instead of being made silently.

## 10. Preregistration hash

Computed over the LCJ-1 canonical JSON of every locked parameter above
(pool/draw size, exposure ladder, event thresholds, Sidon base set, arm
identifiers, optimizer seed/restart/candidate/swap-pass/evaluation-ceiling
budget, evaluator identity, cache policy) by
`tools/hash_preregistration_b649_constructor_frontier.py`, recorded in
`diversification-constructor-frontier-b649-v1-preregistration-hash.json`:

```text
preregistration_hash_sha256 = 02b3bc90256b94864eb35e1caf940bec79f83f0315671281a49b3c0cb05b9e71
```

`run_diversification_constructor_frontier_b649_v1.py` re-verifies this hash
before running and refuses to proceed on a mismatch.
