# GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 — result

Status: SEALED — T539_REPLICATION_SUPPORTED ｜ 2026-08-15 ｜ Strategy Matrix
Phase 5, T539 lock+execute

`TASK_ID: STRATEGY_MATRIX_PHASE5_T539_NON_SIDON_LOW_OVERLAP_LOCK_EXECUTE_R1`.
Preregistration (locked before any real T539-scale constructor call or
winning-space enumeration):
`greedy-min-overlap-constructor-t539-v1-preregistration.md`. Hash:
`cb786aac3fc04ea2f1c302b37120831a2296869e94e7d397260d5745420ff8bd`
(execution script re-verified this before running). Full result:
`greedy-min-overlap-constructor-t539-v1-result.json`. Attempt ledger:
`greedy-min-overlap-constructor-t539-v1-attempt-ledger.json`.

## Identity

```text
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
MATRIX_VARIANT_ID:     GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1
LOTTERY:               DAILY_539
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:          EXACT_COMBINATORIAL
REPLICATES:             GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 (native
                        parameter substitution, not a copy)
```

## Method

Three arms, real T539 scale (`pool_size=39, draw_size=5`,
`C(39,5) = 575,757` possible draws), `K = {1,3,5,10,15,20}`, primary event
`M3_PLUS`, secondary `M4_PLUS, M5`:

- **A** `CYCLIC_SIDON_SHIFT_T539_V1` — immutable, unchanged.
- **B** `GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1` — deterministic greedy,
  no Sidon/difference-set algebra, invoked at real T539 scale for the
  first time.
- **C** `RANDOM_EXPECTED_COVERAGE` — immutable, closed-form.

B649's own bounded-optimizer arm has no T539 counterpart in this task —
three arms only, per the Owner packet. Coverage is computed by the same
single-pass earliest-index enumeration method
`run_diversification_coverage_t539_v1.py` already used (no
B649-specific fast evaluator — the design doc's own feasibility estimate
found none necessary for arm B's construction cost). Arm A was
recomputed fresh in this task's execution script (not re-quoted) and
cross-checked for **exact** identity against
`diversification-coverage-t539-v1-result.json`'s own `q_sidon` values —
confirmed identical at every `(m, k)` pair
(`arm_a_identity_check_vs_sealed_coverage_cell: true`). Every coverage
value is an exact `fractions.Fraction`. `MONTE_CARLO: NONE`.
`REAL_DRAW_HISTORY: NOT_USED`.

## Result — primary event (M3_PLUS)

| k | Q_sidon (A) | Q_greedy (B) | Q_random (C) | DELTA_RANDOM_B(k) | DELTA_SIDON(k) |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.01004069 | 0.01004069 | 0.01004069 | +0.00000000 | +0.00000000 |
| 3 | 0.02993450 | 0.03012208 | 0.02982070 | +0.00030138 | +0.00018758 |
| 5 | 0.04957821 | 0.05020347 | 0.04920556 | +0.00099792 | +0.00062526 |
| 10 | 0.09771831 | 0.09928147 | 0.09599032 | +0.00329115 | +0.00156316 |
| 15 | 0.14498304 | 0.14679630 | 0.14047338 | +0.00632293 | +0.00181326 |
| 20 | 0.19206019 | 0.19349830 | 0.18276794 | +0.01073036 | +0.00143811 |

`DELTA_RANDOM_B(1) = 0` and `DELTA_SIDON(1) = 0` exactly, both asserted
at runtime (not just observed) — required by the preregistration's pool-
symmetry argument. `DELTA_RANDOM_SIDON(k)` (arm A vs. arm C) is not
re-tabulated here; it is the already-sealed
`DIVERSIFICATION_COVERAGE_T539_V1` cell's own `D_3(k)`, reproduced
identically by this task's independent recomputation (see Method).

`descriptive_classification`: arm B `OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`
and exceeds arm A's own gain over random at **every** tested `k > 1`.
Unlike B649's own smoothly shrinking `arm_b_sidon_capture_ratio` (5.91x
at `k=3` down to 1.64x at `k=20`, monotonically decreasing), T539's
`DELTA_SIDON(k)` rises from `k=3` through `k=15` (`+0.00019` →
`+0.00181`) and then dips slightly at `k=20` (`+0.00144`) — still
strictly positive throughout the tested ladder, but not monotonic. This
non-monotonicity is disclosed as an observed fact, not smoothed over or
treated as a defect: Q2 requires positivity at every `k > 1`, not
monotonicity, and the preregistration's classification rule was frozen
before this shape was known.

## Geometry (arm B, every k; full detail in result.json)

| k | max overlap | mean overlap | unique numbers used | reuse dispersion | duplicate tickets |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0.000 | 5 / 39 | 0.334 | 0 |
| 3 | 0 | 0.000 | 15 / 39 | 0.487 | 0 |
| 5 | 0 | 0.000 | 25 / 39 | 0.480 | 0 |
| 10 | 1 | 0.400 | 35 / 39 | 0.749 | 0 |
| 15 | 1 | 0.581 | 39 / 39 | 1.163 | 0 |
| 20 | 1 | 0.616 | 39 / 39 | 1.410 | 0 |

`duplicate_tickets: 0` for arm B at every `k` (frozen invariant, asserted
at runtime, not just observed). `max_pairwise_overlap` never exceeds `1`
across the full tested ladder, mirroring B649's own arm-B geometry
finding. At `k <= 5`, `pool_size // draw_size = 39 // 5 = 7` fully
disjoint blocks are still available, so every pair is disjoint
(`max/mean overlap = 0`), exactly as the shared constructor's own
disclosed structural behavior predicts.

**Disclosed prediction (design doc §7), checked, not confirmed.** B649's
real arm-B portfolio never used its pool's highest number (49) at any
tested `k`. T539's arm B *does* use its highest number (39) — but only
starting at `k=15` (`number_use_counts["39"] = 0` at `k in {1,3,5,10}`,
`= 1` at `k in {15,20}`). The disclosed structural bias holds at smaller
`k` but does not hold across the full ladder; reported exactly as
observed, since this was pre-registered as a testable prediction, not
retroactively adjusted.

## Decision rules (frozen by the preregistration §6, applied here)

```text
Q1 (does arm B beat random at every k>1)?
  DELTA_RANDOM_B(k) > 0 for every k in {3,5,10,15,20}: TRUE
  -> T539_ARM_B_OUTPERFORMS_RANDOM

Q2 (does arm B exceed T539 Sidon's own gain over random at every k>1)?
  DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}: TRUE
  -> T539_ARM_B_EXCEEDS_SIDON_GAIN

Q3 (direction consistent with B649 arm B's own sealed result)?
  T539 Q2 == T539_ARM_B_EXCEEDS_SIDON_GAIN
  -> CONSISTENT_WITH_B649
```

```text
T539_REPLICATION_STATUS:            T539_REPLICATION_SUPPORTED
P638_NATIVE_REPLICATION_CANDIDATE:  YES
P638:                                NOT_RUN (this task does not execute it)
```

## What this does and does not claim

Does claim: at every tested exposure level `k > 1`, DAILY_539's native
instantiation of B649's non-Sidon, algebra-free greedy min-overlap
constructor covers strictly more of the `M3_PLUS` winning-space than both
a matched-random portfolio and T539's own already-sealed Sidon-shift
geometry, under DAILY_539's exact `C(39,5) = 575,757` winning space, via
full enumeration (not sampling). Does not claim: predictive advantage on
real draws, prize-value/cost efficiency, that arm B is optimal among all
possible low-overlap geometries, that this generalizes past `k=20`, or
any P638 outcome — P638 is not executed by this task.

## Runtime and resources

```text
arm_a_seconds:         ~0.00001  (fresh coverage query only; Sidon portfolio
                       generation is cheap, unlike its coverage evaluation)
arm_b_seconds:         30.01     (first-ever real-T539-scale constructor
                       call; design doc's pre-registered, non-load-bearing
                       estimate was ~30-35s -- within range)
enumeration_seconds:   2.98      (single-pass earliest-index coverage
                       evaluation, both arms, all three thresholds,
                       C(39,5) = 575,757 draws)
total_seconds:         33.0
peak_memory_bytes:     21,970,944  (~22.0 MB)
```

Two independent runs of this script (one before, one after a lint-only
edit with no logic change) reproduced identical `Q`, `DELTA`, geometry,
and classification values throughout -- only wall-clock timing and
`ru_maxrss` varied (34.11s/22,020,096 bytes vs. 33.0s/21,970,944 bytes),
as expected for repeated measurements on shared hardware. The numbers
above are from the run whose output is currently sealed in
`greedy-min-overlap-constructor-t539-v1-result.json` and
`-attempt-ledger.json`.

## Classification

```text
q1_classification:                  T539_ARM_B_OUTPERFORMS_RANDOM
q2_classification:                  T539_ARM_B_EXCEEDS_SIDON_GAIN
q3_classification:                  CONSISTENT_WITH_B649
t539_replication_status:             T539_REPLICATION_SUPPORTED
p638_native_replication_candidate:   YES
arm_a_identity_check_vs_sealed_coverage_cell: true
sanity_check_delta_random_b_at_k1_is_exactly_zero:    true
sanity_check_delta_sidon_at_k1_is_exactly_zero:        true
sanity_check_delta_random_sidon_at_k1_is_exactly_zero: true
```

## Scope boundary

```text
PREDICTIVE_ADVANTAGE / PRIZE_VALUE_ADVANTAGE / ECONOMIC_OPTIMALITY: NOT_TESTED
P638:                                NOT_RUN
B649:                                NOT_RERUN (cited as given)
PRODUCTION / COHORT / PROSPECTIVE:  NONE
```

## No-rescue statement

The locked arms, contract, k ladder, evaluation method, comparator, and
classification/replication rule were not changed after this result was
seen. No new constructor was added, no different event threshold was
tried, and the non-monotonic `DELTA_SIDON(k)` shape (rising through
`k=15`, dipping at `k=20`) was not smoothed, re-parametrized, or used to
justify a rerun once visible.
