# GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 — locked preregistration

Status: LOCKED before any real T539-scale constructor call or
winning-space enumeration against arm B ｜ 2026-08-15 ｜ Strategy Matrix
Phase 5, T539 native translation

`TASK_ID: STRATEGY_MATRIX_PHASE5_T539_NON_SIDON_LOW_OVERLAP_LOCK_EXECUTE_R1`,
Owner authorization
`AUTHORIZE_STRATEGY_MATRIX_PHASE5_T539_NON_SIDON_LOW_OVERLAP_LOCK_EXECUTE_R1`.
Locks and executes the design frozen in
`strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md`
(commit `94aa504`), the same two-step design-then-lock-and-execute pattern
`diversification-constructor-frontier-b649-v1-preregistration.md` and
`diversification-coverage-p638-zone1-v1-preregistration.md` already used.
T539 only. B649's own bounded-optimizer arm (arm C there) is out of scope
here, per the Owner packet -- this file locks exactly three arms.

## 0. Identity

```text
MATRIX_VARIANT_ID:    GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:               DAILY_539
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
REPLICATES:             GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 (native
                        parameter substitution, not a copy -- design doc S5)
BUILDS ON (immutable, not rerun): DIVERSIFICATION_COVERAGE_T539_V1 (sealed),
  DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 (sealed,
  SIDON_BELOW_FRONTIER_MARGIN), CYCLIC_SIDON_SHIFT_T539_V1 (existing)
```

## 1. Research question (frozen by the design doc, restated)

At a fixed ticket count `k`, does DAILY_539's native instantiation of the
B649 Phase-5 non-Sidon low-overlap constructor increase exact `M3_PLUS`
winning-space coverage relative to `k` uniformly random distinct tickets'
*expected* coverage, and does it exceed T539's own already-sealed Sidon
reference's gain over random? `PREDICTIVE_ADVANTAGE: NOT_TESTED`.
`PRIZE_VALUE_ADVANTAGE: NOT_TESTED`. `ECONOMIC_OPTIMALITY: NOT_TESTED`.

## 2. Frozen arms (identity only -- algorithms already frozen and toy-verified in 94aa504)

```text
A  SIDON_REFERENCE:        CYCLIC_SIDON_SHIFT_T539_V1              (immutable, no mutation)
B  NON_SIDON_LOW_OVERLAP:  GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1   (first real-scale run, this task)
C  RANDOM_EXPECTED_COVERAGE: exact_coverage_baseline.exact_random_portfolio_coverage (immutable, no mutation)
```

B649's arm C (`RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1`, a bounded
optimizer) is explicitly `OUT_OF_SCOPE` and has no T539 counterpart in
this task -- three arms only, matching the Owner packet's own `ARM_A` /
`ARM_B` / `ARM_C` lettering (not B649's four-arm A/B/C/D scheme). No
constructor family is added or changed by this task.

## 3. Contract (frozen)

```text
K:                     {1, 3, 5, 10, 15, 20}
PRIMARY_EVENT:          M3_PLUS  (>= 3 of 5 numbers match)
SECONDARY_EVENTS:       M4_PLUS, M5  (M5 is the degenerate exact-match
                        case, D(k) = k/575,757 geometry-independent --
                        design doc S3)
WINNING_SPACE:          exact C(39,5) = 575,757 (real enumeration, this task)
PORTFOLIO_MODE:         NESTED_PREFIX (arms A and B: portfolio(k) is
                        portfolio(k+1) minus its last ticket -- structurally
                        guaranteed for both, not just observed)
DUPLICATE_TICKETS:      must be exactly 0 for every arm at every k (frozen
                        invariant, asserted at runtime)
REAL_DRAW_HISTORY:      NONE
MONTE_CARLO:            NONE
```

## 4. Evaluation method (locked)

Coverage is computed by the same single-pass earliest-index enumeration
method `run_diversification_coverage_t539_v1.py` (the sealed
`DIVERSIFICATION_COVERAGE_T539_V1` cell) already used, not a new
evaluator: for each of the `C(39,5) = 575,757` possible draws, walk each
nested-prefix portfolio (arm A, arm B) in ticket order and record the
earliest ticket index at which each threshold `m` is first satisfied;
`Q_X_m(k)` is then the fraction of draws whose earliest index is `< k`.
No B649-specific fast evaluator (`exact_coverage_fast_evaluator.py`) is
needed or used -- the design doc's own feasibility estimate (S6) found
none necessary for arm B's construction cost, and this evaluation method
was already measured feasible at T539 scale (`0.025s` bare enumeration)
by the sealed Sidon cell. `NO_APPROXIMATION: YES`. `NO_MONTE_CARLO: YES`.

Arm A (Sidon) is recomputed fresh in this task's execution script (not
just re-quoted from the sealed JSON) and cross-checked for exact identity
against `diversification-coverage-t539-v1-result.json`'s own `q_sidon`
values -- an identity check, not a rerun that could produce a different
number, since arm A's constructor and the evaluation method are both
unchanged.

## 5. Estimands (frozen by the design doc S8, restated with the Owner
packet's own naming)

```text
Q_ARM_A(k)             exact M3_PLUS coverage, Sidon reference, k tickets
Q_ARM_B(k)             exact M3_PLUS coverage, greedy min-overlap, k tickets
Q_RANDOM_EXPECTED(k)    exact_random_portfolio_coverage(39, 5, 3, k)
DELTA_RANDOM_B(k)      = Q_ARM_B(k) - Q_RANDOM_EXPECTED(k)
DELTA_RANDOM_SIDON(k)   = Q_ARM_A(k) - Q_RANDOM_EXPECTED(k)
DELTA_SIDON(k)          = Q_ARM_B(k) - Q_ARM_A(k)

SANITY CHECK (required, exact):  DELTA_RANDOM_B(1) = 0  and  DELTA_SIDON(1) = 0
```

Both sanity checks follow from the same pool-symmetry argument the sealed
T539 Sidon cell already used: for a *single* fixed 5-number ticket, exact
`M3_PLUS` coverage against a uniformly random draw depends only on the
ticket's size, not its specific numbers, so `Q_ARM_A(1) = Q_ARM_B(1) =
Q_RANDOM_EXPECTED(1) = K(3)/N` exactly regardless of which ticket each
arm happens to pick at `k=1`. Both are asserted at runtime, not merely
observed -- a violation raises before any classification is computed.

## 6. Classification and replication rules (frozen by the design doc S10, applied here)

```text
Q1 (does arm B beat random at every k>1?):
  DELTA_RANDOM_B(k) > 0 for every k in {3,5,10,15,20}  -> T539_ARM_B_OUTPERFORMS_RANDOM
  DELTA_RANDOM_B(k) <= 0 for every k in {3,5,10,15,20} -> T539_ARM_B_DOES_NOT_OUTPERFORM_RANDOM
  otherwise                                             -> T539_ARM_B_MIXED_BY_EXPOSURE

Q2 (does arm B exceed T539 Sidon's own gain over random at every k>1?):
  DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}  -> T539_ARM_B_EXCEEDS_SIDON_GAIN
  DELTA_SIDON(k) <= 0 for every k in {3,5,10,15,20} -> T539_ARM_B_DOES_NOT_EXCEED_SIDON_GAIN
  otherwise                                          -> T539_ARM_B_MIXED_VS_SIDON

Q3 (direction consistent with B649 arm B's own sealed result?):
  B649's sealed DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 cell found
  DELTA_SIDON(k) > 0 for arm B at every tested k>1 (1.64x-6.08x capture
  ratio, never below 1x -- cited as given, not rerun here).
  T539 Q2 == T539_ARM_B_EXCEEDS_SIDON_GAIN -> CONSISTENT_WITH_B649
  otherwise                                 -> DIRECTION_INCONSISTENT_WITH_B649
                                                (disclosed, not a failure --
                                                cross-lottery divergence is a
                                                legitimate outcome)

T539_REPLICATION_SUPPORTED  iff  Q1 == T539_ARM_B_OUTPERFORMS_RANDOM
                             AND Q2 == T539_ARM_B_EXCEEDS_SIDON_GAIN
                             AND Q3 == CONSISTENT_WITH_B649
                             otherwise NOT_SUPPORTED, exact divergence
                             recorded, no rescue.

P638_NATIVE_REPLICATION_CANDIDATE: YES iff T539_REPLICATION_SUPPORTED, else NO.
P638 is not executed by this task either way.
```

## 7. Geometry outputs (frozen by the design doc S7, computed for arm B at every k)

`max_pairwise_overlap`, `mean_pairwise_overlap`, `overlap_profile`,
`number_use_counts` (1..39), `unique_number_coverage`, `reuse_dispersion`
(population stdev of `number_use_counts`), `duplicate_tickets` (asserted
`== 0`). No metric beyond this list is added post-hoc.

## 8. Boundaries (frozen)

```text
REAL_DRAW_HISTORY:             NONE
PREDICTIVE_ADVANTAGE:          NOT_TESTED
PRIZE_VALUE_ADVANTAGE:         NOT_TESTED
ECONOMIC_OPTIMALITY:           NOT_TESTED
P638:                          NOT_RUN
B649:                          NOT_RERUN (cited as given, S6 above)
A / C MUTATION:                NONE
PRODUCTION / COHORT / PROSPECTIVE: NONE
```

## 9. No-rescue commitment

Arms, contract, k ladder, endpoints, evaluation method, comparator, and
classification/replication rule are locked by this file and by 94aa504
before any real T539-scale value is computed against arm B. No new
constructor, no different event threshold, no k-ladder change, no
classification-rule change once results are visible. Any change required
after this point stops with `STOP_T539_POST_LOCK_CHANGE_REQUIRED` instead
of being made silently.

## 10. Preregistration hash

Computed over the LCJ-1 canonical JSON of every locked parameter above
(pool/draw size, exposure ladder, event thresholds, Sidon base set,
per-arm constructor identity, portfolio mode, duplicate-ticket invariant)
by `tools/hash_preregistration_t539_arm_b.py`, recorded in
`greedy-min-overlap-constructor-t539-v1-preregistration-hash.json`:

```text
preregistration_hash_sha256 = cb786aac3fc04ea2f1c302b37120831a2296869e94e7d397260d5745420ff8bd
```

`run_greedy_min_overlap_constructor_t539_v1.py` re-verifies this hash
before running and refuses to proceed on a mismatch.
