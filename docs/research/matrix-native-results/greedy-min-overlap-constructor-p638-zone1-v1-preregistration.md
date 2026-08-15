# GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1 — locked preregistration

Status: LOCKED before any real P638 Zone-1-scale constructor call or
winning-space enumeration against arm B ｜ 2026-08-15 ｜ Strategy Matrix
Phase 5, P638 Zone-1 native translation

`TASK_ID: STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_LOCK_EXECUTE_R1`,
Owner authorization
`AUTHORIZE_STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_LOCK_EXECUTE_R1`.
Locks and executes the design frozen in
`strategy-matrix-phase5-p638-non-sidon-low-overlap-native-design-r1.md`
(commit `9b60007`), the same two-step design-then-lock-and-execute pattern
`diversification-constructor-frontier-b649-v1-preregistration.md`,
`diversification-coverage-p638-zone1-v1-preregistration.md`, and
`greedy-min-overlap-constructor-t539-v1-preregistration.md` already used.
P638 Zone-1 only; Zone-2 (1-of-8) is out of scope entirely. B649's own
bounded-optimizer arm (arm C there) is out of scope here, per the Owner
packet — this file locks exactly three arms. B649 and T539 are not rerun
by this task.

## 0. Identity

```text
MATRIX_VARIANT_ID:    GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:               POWER_LOTTO
GAME_COMPONENT:        ZONE_1 (6-of-38); ZONE_2 (1-of-8) OUT OF SCOPE
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
REPLICATES:             GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 and
                        GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 (native
                        parameter substitution, not a copy -- design doc S5)
BUILDS ON (immutable, not rerun): DIVERSIFICATION_COVERAGE_P638_ZONE1_V1
  (sealed), DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 (sealed,
  SIDON_BELOW_FRONTIER_MARGIN), GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1
  (sealed, T539_REPLICATION_SUPPORTED), CYCLIC_SIDON_SHIFT_P638_ZONE1_V1
  (existing, tracked, `src/lottolab/research/cyclic_sidon_shift_p638.py`)
```

`CYCLIC_SIDON_SHIFT_P638_ZONE1_V1` is the one and only P638 Zone-1 Sidon
module this file treats as sealed comparator A. A separate, uncommitted,
byte-different duplicate
(`src/lottolab/research/cyclic_sidon_shift_p638_zone1.py`) exists untracked
in the working tree, was flagged (not authored, not touched, not resolved)
by the design task (9b60007, S13 item 4), and is not read, imported, or
relied upon anywhere in this preregistration or its execution.

## 1. Research question (frozen by the design doc, restated)

At a fixed ticket count `k`, does POWER_LOTTO Zone-1's native instantiation
of the B649 Phase-5 non-Sidon low-overlap constructor increase exact
`ZONE1_M3_PLUS` winning-space coverage relative to `k` uniformly random
distinct Zone-1 tickets' *expected* coverage, and does it exceed P638
Zone-1's own already-sealed Sidon reference's gain over random?
`PREDICTIVE_ADVANTAGE: NOT_TESTED`. `PRIZE_VALUE_ADVANTAGE: NOT_TESTED`.
`ECONOMIC_OPTIMALITY: NOT_TESTED`. Zone-2 allocation is not tested by this
variant at all.

## 2. Frozen arms (identity only -- algorithms already frozen and toy-verified in 9b60007)

```text
A  SIDON_REFERENCE:        CYCLIC_SIDON_SHIFT_P638_ZONE1_V1            (immutable, no mutation)
B  NON_SIDON_LOW_OVERLAP:  GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1 (first real-scale run, this task)
C  RANDOM_EXPECTED_COVERAGE: exact_coverage_baseline.exact_random_portfolio_coverage (immutable, no mutation)
```

B649's arm C (`RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1`, a bounded
optimizer) is explicitly `OUT_OF_SCOPE` and has no P638 Zone-1 counterpart
in this task -- three arms only, matching the Owner packet's own `ARM_A` /
`ARM_B` / `ARM_C` lettering (not B649's four-arm A/B/C/D scheme). No
constructor family is added or changed by this task.

## 3. Contract (frozen)

```text
K:                     {1, 3, 5, 10, 15, 20}
PRIMARY_EVENT:          ZONE1_M3_PLUS  (>= 3 of 6 numbers match)
SECONDARY_EVENTS:       ZONE1_M4_PLUS, ZONE1_M5_PLUS, ZONE1_M6  (M6 is the
                        degenerate exact-match case, D(k) = k/2,760,681
                        geometry-independent -- design doc S3)
WINNING_SPACE:          exact C(38,6) = 2,760,681 (real enumeration, this task)
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
method the sealed `DIVERSIFICATION_COVERAGE_P638_ZONE1_V1` cell and
`run_greedy_min_overlap_constructor_t539_v1.py` already use, not a new
evaluator: for each of the `C(38,6) = 2,760,681` possible draws, walk each
nested-prefix portfolio (arm A, arm B) in ticket order and record the
earliest ticket index at which each threshold `m` is first satisfied;
`Q_X_m(k)` is then the fraction of draws whose earliest index is `< k`.
No B649-specific fast evaluator (`exact_coverage_fast_evaluator.py`) is
needed or used -- the design doc's own feasibility estimate (S6) found
none necessary for arm B's construction cost (non-load-bearing estimate,
~165s), and this evaluation method was already measured feasible at P638
Zone-1 scale (`0.1421s` bare enumeration) by the sealed Sidon cell.
`NO_APPROXIMATION: YES`. `NO_MONTE_CARLO: YES`.

Arm A (Sidon) is recomputed fresh in this task's execution script (not
just re-quoted from the sealed JSON) and cross-checked for exact identity
against `diversification-coverage-p638-zone1-v1-result.json`'s own
`q_sidon` values -- an identity check, not a rerun that could produce a
different number, since arm A's constructor and the evaluation method are
both unchanged.

## 5. Estimands (frozen by the design doc S8, restated with the Owner packet's own naming)

```text
Q_ARM_B(k)             exact ZONE1_M3_PLUS coverage, greedy min-overlap, k tickets
Q_SIDON(k)             exact ZONE1_M3_PLUS coverage, Sidon reference, k tickets
Q_RANDOM_EXPECTED(k)    exact_random_portfolio_coverage(38, 6, 3, k)
DELTA_RANDOM_B(k)      = Q_ARM_B(k) - Q_RANDOM_EXPECTED(k)
DELTA_RANDOM_SIDON(k)   = Q_SIDON(k) - Q_RANDOM_EXPECTED(k)
DELTA_SIDON(k)          = Q_ARM_B(k) - Q_SIDON(k)

SANITY CHECK (required, exact):  DELTA_RANDOM_B(1) = 0  and  DELTA_SIDON(1) = 0
```

Both sanity checks follow from the same pool-symmetry argument the sealed
P638 Zone-1 Sidon cell already used: for a *single* fixed 6-number ticket,
exact `ZONE1_M3_PLUS` coverage against a uniformly random draw depends only
on the ticket's size, not its specific numbers, so `Q_SIDON(1) =
Q_ARM_B(1) = Q_RANDOM_EXPECTED(1) = K(3)/N = 106833/2760681` exactly
regardless of which ticket each arm happens to pick at `k=1`. Both are
asserted at runtime, not merely observed -- a violation raises before any
classification is computed.

## 6. Classification and replication rules (frozen by the design doc S10, applied here)

```text
Q1 (does arm B beat random at every k>1?):
  DELTA_RANDOM_B(k) > 0 for every k in {3,5,10,15,20}  -> P638_ARM_B_OUTPERFORMS_RANDOM
  DELTA_RANDOM_B(k) <= 0 for every k in {3,5,10,15,20} -> P638_ARM_B_DOES_NOT_OUTPERFORM_RANDOM
  otherwise                                             -> P638_ARM_B_MIXED_BY_EXPOSURE

Q2 (does arm B exceed P638 Zone-1 Sidon's own gain over random at every k>1?):
  DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}  -> P638_ARM_B_EXCEEDS_SIDON_GAIN
  DELTA_SIDON(k) <= 0 for every k in {3,5,10,15,20} -> P638_ARM_B_DOES_NOT_EXCEED_SIDON_GAIN
  otherwise                                          -> P638_ARM_B_MIXED_VS_SIDON

Q3 (direction consistent with B649 AND T539 arm B's own sealed results?):
  B649's sealed DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1 cell found
  DELTA_SIDON(k) > 0 for arm B at every tested k>1 (1.64x-6.08x capture
  ratio, never below 1x). T539's sealed
  GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 cell found
  T539_REPLICATION_SUPPORTED (Q1/Q2/Q3 all PASS). Both cited as given, not
  rerun here.
  P638 Zone-1 Q2 == P638_ARM_B_EXCEEDS_SIDON_GAIN -> CONSISTENT_WITH_B649_AND_T539
  otherwise                                        -> DIRECTION_INCONSISTENT_WITH_B649_AND_T539
                                                       (disclosed, not a failure --
                                                       cross-lottery divergence is a
                                                       legitimate outcome)

P638_REPLICATION_SUPPORTED  iff  Q1 == P638_ARM_B_OUTPERFORMS_RANDOM
                             AND Q2 == P638_ARM_B_EXCEEDS_SIDON_GAIN
                             AND Q3 == CONSISTENT_WITH_B649_AND_T539
                             otherwise NOT_SUPPORTED, exact divergence
                             recorded, no rescue.

NON_SIDON_LOW_OVERLAP_CROSS_LOTTERY_STATUS: SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES
  iff P638_REPLICATION_SUPPORTED (P638 Zone-1 is the last of the three
  native lottery structures this repository currently supports for this
  arm-B translation chain -- design doc S10 replication-closure note;
  Zone-2 remains a separate, unaddressed dimension), otherwise not
  declared.
```

## 7. Geometry outputs (frozen by the design doc S7, computed for arm B at every k)

`max_pairwise_overlap`, `mean_pairwise_overlap`, `overlap_profile`,
`number_use_counts` (1..38), `unique_number_coverage`, `reuse_dispersion`
(population stdev of `number_use_counts`), `duplicate_tickets` (asserted
`== 0`). No metric beyond this list is added post-hoc.

## 8. Boundaries (frozen)

```text
REAL_DRAW_HISTORY:             NONE
PREDICTIVE_ADVANTAGE:          NOT_TESTED
PRIZE_VALUE_ADVANTAGE:         NOT_TESTED
ECONOMIC_OPTIMALITY:           NOT_TESTED
ZONE_2_ALLOCATION:              NOT_TESTED, NOT_DESIGNED
B649 / T539:                    NOT_RERUN (cited as given, S0/S6 above)
A / C MUTATION:                NONE
PRODUCTION / COHORT / PROSPECTIVE: NONE
```

## 9. No-rescue commitment

Arms, contract, k ladder, endpoints, evaluation method, comparator, and
classification/replication rule are locked by this file and by 9b60007
before any real P638 Zone-1-scale value is computed against arm B. No new
constructor, no different event threshold, no k-ladder change, no
classification-rule change once results are visible. Any change required
after this point stops with `STOP_P638_ARM_B_POST_LOCK_CHANGE_REQUIRED`
instead of being made silently.

## 10. Preregistration hash

Computed over the LCJ-1 canonical JSON of every locked parameter above
(pool/draw size, zone, exposure ladder, event thresholds, Sidon base set,
per-arm constructor identity, portfolio mode, duplicate-ticket invariant)
by `tools/hash_preregistration_p638_arm_b.py`, recorded in
`greedy-min-overlap-constructor-p638-zone1-v1-preregistration-hash.json`:

```text
preregistration_hash_sha256 = e535caa323c1bb5ef027e5d8c5efa8b12fa83f59f83312ad1d9250d1e039f58b
```

`run_greedy_min_overlap_constructor_p638_zone1_v1.py` re-verifies this
hash before running and refuses to proceed on a mismatch.
