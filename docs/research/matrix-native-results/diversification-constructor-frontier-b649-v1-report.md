# DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 — result

Status: SEALED — `SIDON_BELOW_FRONTIER_MARGIN` ｜ 2026-08-15 ｜ Strategy Matrix
Phase 5, Generation 2

Preregistration (locked before any real B649-scale constructor or optimizer
call): `diversification-constructor-frontier-b649-v1-preregistration.md`.
Hash: `02b3bc90256b94864eb35e1caf940bec79f83f0315671281a49b3c0cb05b9e71`
(execution script re-verified this before running). Full result:
`diversification-constructor-frontier-b649-v1-result.json`. Attempt
ledger: `diversification-constructor-frontier-b649-v1-attempt-ledger.json`.

## Identity

```text
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
MATRIX_VARIANT_ID:     DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:          EXACT_COMBINATORIAL_BOUNDED_SEARCH
GENERATION:             2 (builds on sealed Generation-1 DIVERSIFICATION_COVERAGE_B649_V1)
```

## Method

Four arms, real B649 scale (`pool_size=49, draw_size=6`, `C(49,6) =
13,983,816` possible draws), `K = {1,3,5,10,15,20}`, primary event
`M3_PLUS`, secondary `M4_PLUS, M5_PLUS, M6`:

- **A** `CYCLIC_SIDON_SHIFT_B649_V1` — immutable, unchanged.
- **B** `GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1` — deterministic greedy,
  no Sidon/difference-set algebra, invoked at real B649 scale for the
  first time.
- **C** `RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1` — seed `20260815`,
  `restart_count=5, candidate_sample_size=60, max_swap_passes=3`,
  `INDEPENDENT_PER_K`, invoked at real B649 scale for the first time, via
  the fast-evaluator-backed `bounded_coverage_optimizer_fast` module
  (exact parity with the frozen slow search, verified at toy scale).
- **D** `RANDOM_EXPECTED_BASELINE` — immutable, closed-form.

Every coverage value is an exact `fractions.Fraction`. `MONTE_CARLO:
NONE`. `REAL_DRAW_HISTORY: NOT_USED`.

## Result — primary event (M3_PLUS)

| k | Q_sidon (A) | Q_greedy (B) | Q_bounded (C) | Q_random (D) | best-found | gap vs Sidon |
|---:|---:|---:|---:|---:|:---:|---:|
| 1 | 0.01863755 | 0.01863755 | 0.01863755 | 0.01863755 | A (tie) | +0.00000000 |
| 3 | 0.05503762 | 0.05582682 | 0.05582682 | 0.05487704 | B (tie w/ C) | +0.00078920 |
| 5 | 0.09029231 | 0.09290168 | 0.09290168 | 0.08977829 | B (tie w/ C) | +0.00260937 |
| 10 | 0.17364180 | 0.18167144 | 0.18218232 | 0.17149647 | **C** | +0.00854052 |
| 15 | 0.25178807 | 0.26065632 | 0.26529203 | 0.24587816 | **C** | +0.01350397 |
| 20 | 0.32687687 | 0.33536361 | 0.34244823 | 0.31358200 | **C** | +0.01557136 |

`D_3(1) = 0` exactly for every arm (A, B, and C alike — verified, not just
assumed: at `k=1` no fixed ticket has an advantage over any other by pool
symmetry, so this is a valid cross-arm sanity check, not only an A-vs-D
one). `descriptive_classification`: **A, B, and C all
`OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`** across the full ladder.

`arm_c_primary_coverage_monotonic_in_k: true` — observed, not asserted
(§6.1 of the design doc: arm C is `INDEPENDENT_PER_K`, no nested-prefix
guarantee, so this was not structurally forced).

## Frontier estimands (primary event)

| k | `SIDON_FRONTIER_GAP` | `FRONTIER_CAPTURE_RATIO` |
|---:|---:|---:|
| 1 | 0 | NOT_APPLICABLE_K1 |
| 3 | 0.00078920 | 0.16908 |
| 5 | 0.00260937 | 0.16457 |
| 10 | 0.00854052 | 0.20076 |
| 15 | 0.01350397 | 0.30442 |
| 20 | 0.01557136 | 0.46057 |

`FRONTIER_CAPTURE_RATIO(k) < 0.90` at **every** `k > 1` →
`NEAR_FRONTIER = FALSE` → **`SIDON_FRONTIER_CLASSIFICATION:
SIDON_BELOW_FRONTIER_MARGIN`**. Sidon-shift captures only 16–46% of the
improvement over random that this one bounded search actually found — a
materially different picture from the toy-scale numbers in the design
doc's own (explicitly discarded, non-scientific) mechanics check. The
capture ratio rises with `k` (16.9% → 46.1%) even as the absolute gap also
grows — Sidon becomes relatively more competitive at larger `k` within
this tested range, without closing the gap. `GLOBAL_OPTIMUM_STATUS:
UNKNOWN` — the search is bounded, not exhaustive, and no arm here is
called globally optimal.

## Required Questions

**Q1 — Does arm B reproduce most of Sidon's gain?**
`LOW_OVERLAP_MECHANISM_RESULT: REPRODUCES_MOST_OF_SIDON_GAIN` — arm B not
only reproduces but *exceeds* Sidon's own improvement over random at
**every** tested `k`, by `arm_b_sidon_capture_ratio_primary_event` of
5.91x (`k=3`), 6.08x (`k=5`), 4.74x (`k=10`), 2.50x (`k=15`), 1.64x
(`k=20`) — shrinking toward, but never below, 1x. A purely
lexicographic-greedy, algebra-free min-overlap rule out-performs the
Sidon/difference-set construction here, not merely approaches it.

**Q2 — Does arm C materially improve over Sidon?**
Yes. `classification.c: OUTPERFORMS_RANDOM_EXPECTED_COVERAGE` and
`DELTA_SIDON(k) > 0` for arm C at every `k > 1` (0.00079 → 0.01557,
`k=3..20`), growing in absolute terms across the ladder. Arm C is also the
single best-found constructor at `k=10, 15, 20` (arm B ties it at `k=3,5`
exactly — see below).

**Q3 — `SIDON_FRONTIER_GAP(k)` across k?**
See the table above: 0, 0.00079, 0.00261, 0.00854, 0.01350, 0.01557 for
`k = 1,3,5,10,15,20`. Monotonically non-decreasing across the tested
ladder (not asserted, observed).

**Q4 — Is reduced overlap associated with increased coverage?**
Descriptive only (`n=3` real constructors per `k`, far too small for
inference, per the design doc's own caveat). At `k=20`: mean pairwise
overlap A=0.858, B=0.663, C=0.505, paired with `Q_3(20)` A=0.32688,
B=0.33536, C=0.34245 — lower mean overlap lines up with higher coverage
at every arm, at every `k` tested (e.g. at `k=3`: A mean=1.0 / Q=0.05504
vs B=C mean=0.0 / Q=0.05583). Consistent with, not proof of, an
overlap-driven mechanism. A related, purely structural observation: arm
B's lexicographic tie-break means it never uses number 49 in any tested
portfolio (`unique_number_coverage=48` at `k=20`, `20` unique numbers used
at most other k), while arm C's randomized sampling shows no such bias
(`unique_number_coverage=49`, all numbers used, at `k>=10`).

**Q5 — Should the best-found constructor proceed to T539/P638 replication?**
Both challenger arms are `ELIGIBLE_FOR_T539_P638_REPLICATION` (971b97b
§11's three conditions all hold for both B and C: `OUTPERFORMS_RANDOM`
across the full ladder, `DELTA_SIDON(k) > 0` for at least one `k`, and
both modules are generically parametrized by `(pool_size, draw_size)` with
no B649-tuned constant). Arm C is the stronger of the two at `k >= 10` and
never worse than B at any tested `k`; arm B is the structurally simpler
mechanism (no bounded search, no seed, no evaluation budget) and already
captures most of arm C's advantage at small-to-medium `k`. This report
does not choose between them — that choice, and any actual T539/P638
execution, is left to a separate Owner-authorized task (`T539: NOT_RUN`,
`P638: NOT_RUN`, per this task's frozen boundary).

## Optimizer diagnostics (arm C)

```text
evaluations_used_total_ladder: 56730 / 65610 ceiling (86.5%)
```

| k | evaluations used | ceiling | restarts converged (of 5) | swap passes run |
|---:|---:|---:|---:|---:|
| 1 | 605 | 1215 | 5 | all 1 |
| 3 | 1805 | 3645 | 5 | all 1 |
| 5 | 3605 | 6075 | 5 | 1–2 |
| 10 | 11405 | 12150 | 5 | 2–3 |
| 15 | 15305 | 18225 | 2 | 1–3 |
| 20 | 24005 | 24300 | 2 | all 3 |

At `k=15` and `k=20`, most restarts hit `max_swap_passes=3` without
reaching a no-improving-swap pass (`converged=False`) — the pass limit was
a real, binding constraint there, not just a formality. This is disclosed
as a limitation: a richer `max_swap_passes` budget might find an even
larger gap at high `k`, but that is a different, unauthorized budget per
this task's lock (§9 no-rescue) — not run here.

## Runtime and resources

```text
total_seconds:      6904.6  (~115.1 minutes)
arm_a_seconds:      ~0 (fresh coverage query only, portfolio reused from cheap generation)
arm_b_seconds:      774.5   (~12.9 minutes, first-ever real-scale run)
arm_c_seconds_by_k: k=1: 45.0s, k=3: 145.9s, k=5: 305.5s, k=10: 1100.4s,
                     k=15: 1613.9s, k=20: 2902.4s (largest single component,
                     ~48.4 minutes)
arm_d_seconds:      ~0 (closed form)
peak_memory_bytes:  3,054,829,568 (~3.05 GB) — consistent with the
                     ~1.96-2.03 GB single-restart benchmarks this task ran
                     before locking, scaled up modestly for restart_count=5
                     and the larger k rungs; no runaway growth observed,
                     consistent with the per-slot/per-step cache-clearing
                     policy (bounded_coverage_optimizer_fast.py) actually
                     holding at real scale, not just in benchmarks.
```

## Geometry (selected, `k=20`, full detail in result.json)

| arm | max overlap | mean overlap | unique numbers used | reuse dispersion |
|---|---:|---:|---:|---:|
| A (Sidon) | 1 | 0.858 | 40 / 49 | 1.762 |
| B (greedy) | 1 | 0.663 | 48 / 49 | 1.263 |
| C (bounded) | 1 | 0.505 | 49 / 49 | 0.608 |

`duplicate_tickets: 0` for every arm at every `k` (frozen invariant,
asserted at runtime, not just observed).

## Classification

```text
descriptive_classification.a:      OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
descriptive_classification.b:      OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
descriptive_classification.c:      OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
sidon_frontier_classification:     SIDON_BELOW_FRONTIER_MARGIN
near_frontier:                     FALSE
low_overlap_mechanism_result:      REPRODUCES_MOST_OF_SIDON_GAIN
replication_eligibility.b:         ELIGIBLE_FOR_T539_P638_REPLICATION
replication_eligibility.c:         ELIGIBLE_FOR_T539_P638_REPLICATION
global_optimum_status:             UNKNOWN
```

## What this does and does not claim

Does claim: at every tested exposure level, a bounded, seeded, exact
coverage search — and even a much simpler deterministic low-overlap greedy
rule with no Sidon algebra at all — cover strictly more of the `M3_PLUS`
winning-space than the previously-canonical Sidon-shift geometry, under
B649's confirmed-fair draw process, within one fixed, disclosed,
non-exhaustive search budget. Does not claim: predictive advantage on real
draws, prize-value/cost efficiency, that arm C (or B) is globally optimal
— `C(49,6) = 13,983,816` candidate tickets exist per slot and this search
sampled a tiny, disclosed fraction of that space — or that either
challenger's advantage generalizes to T539/P638 without native
replication (not run here).

## Scope boundary

```text
PREDICTIVE_ADVANTAGE / PRIZE_VALUE_ADVANTAGE / ECONOMIC_OPTIMALITY: NOT_TESTED
T539 / P638:                        NOT_RUN
PRODUCTION / COHORT / PROSPECTIVE:  NONE
```

## No-rescue statement

The locked arms, budget, seed, k ladder, endpoint, optimizer mode,
classification rule, and frontier rule were not changed after this result
was seen. No new constructor was added, no extra optimizer restart was run
after seeing the outcome, and the budget was not adjusted once results
were visible.
