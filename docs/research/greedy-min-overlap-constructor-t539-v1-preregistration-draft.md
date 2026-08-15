# GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 — preregistration DRAFT

Status: DRAFT — NOT LOCKED, no winning-space enumeration has been (or
could yet be, per §2 of the design doc) performed against this arm ｜
2026-08-15 ｜ Strategy Matrix Phase 5, T539 native translation

This is a **draft**, produced by
`STRATEGY_MATRIX_PHASE5_T539_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1` (see
`strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md`
for the full design rationale this draft summarizes). It follows the same
format the locked preregistrations
`diversification-coverage-t539-v1-preregistration.md`,
`diversification-coverage-p638-zone1-v1-preregistration.md` (via that
cell's design doc), and
`diversification-constructor-frontier-b649-v1-preregistration.md` already
use, but is **not itself locked**: `PREREGISTRATION_LOCKED: NO`. A
separate, later Owner-authorized lock-and-execute task must (a) freeze
this file's content byte-for-byte (or explicitly revise and re-draft it),
(b) hash it via the same `tools/hash_preregistration_*.py` pattern the
other three cells use, and (c) have its execution script verify that hash
before touching the real `C(39,5)` winning space — none of which has
happened yet.

## 0. Identity

```text
MATRIX_VARIANT_ID:    GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:               DAILY_539
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
REPLICATES:             GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 (native
                        parameter substitution — see design doc §5)
```

## 1. Research question (frozen, identical claim in kind to the B649 cell)

At a fixed ticket count `k`, does DAILY_539's native instantiation of the
B649 Phase-5 non-Sidon low-overlap constructor increase exact `M3_PLUS`
winning-space coverage relative to `k` uniformly random distinct tickets'
*expected* coverage, and does it exceed T539's own already-sealed Sidon
reference's gain over random? `PREDICTIVE_ADVANTAGE: NOT_TESTED`.
`PRIZE_VALUE_ADVANTAGE: NOT_TESTED`. `ECONOMIC_OPTIMALITY: NOT_TESTED`.

## 2. Exposure ladder and events (frozen, unchanged from B649/T539)

```text
EXPOSURE_LADDER:              [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:                 M3_PLUS (main_hits >= 3, out of 5)
SECONDARY_DESCRIPTIVE_EVENTS:  M4_PLUS, M5 (degenerate exact-match case —
                                see the T539 Sidon cell's own disclosure)
PRIZE_VALUE_CLAIM:             NONE
```

## 3. Portfolio constructor — `GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1` (frozen definition, not yet executed)

`src/lottolab/research/greedy_min_overlap_constructor_t539.py`
(`greedy_min_overlap_portfolio_t539`), an unconditional delegation to the
shared, unmodified `greedy_min_overlap_portfolio(pool_size=39,
draw_size=5, ticket_count)`
(`src/lottolab/research/greedy_min_overlap_constructor.py`, frozen since
971b97b / PR132, not edited by this task). Ticket 0 is the
lexicographically first 5-subset of `1..39`. Ticket `i` (`i >= 1`) is the
lexicographically first not-yet-used 5-subset whose maximum pairwise
overlap with every already-chosen ticket is smallest — plain greedy
scan-and-keep-best, no backtracking, no revisiting an earlier ticket, no
Sidon/difference-set algebra, no random search, no post-result tuning.

`pool_size=39` and `draw_size=5` come directly from
`DAILY_539_RULE_CONTRACT` (`main_number_max=39`, `main_number_count=5`,
`src/lottolab/domain/lottery_rules.py`), not invented for this
preregistration.

```text
UNRESOLVED_B649_CONSTANTS: NONE (design doc §5)
DETERMINISTIC:              YES
OUTCOME_FREE:                YES
RANDOM_SEARCH:                NO
POST_RESULT_TUNING:           NO
DUPLICATE_TICKETS:            must be 0 (structural invariant of the
                              shared, already-tested constructor)
```

## 4. Primary estimand and computation method (frozen, structurally identical to B649/T539)

```text
Q_ARM_B_m(k)   = exact P(>= 1 ticket in the k-ticket arm-B portfolio has
                 hits >= m), single-pass enumeration over all
                 C(39,5) = 575,757 possible draws — NOT YET COMPUTED
Q_random_m(k)  = exact_random_portfolio_coverage(39, 5, m, k) (reused
                 verbatim, unmodified; independently re-verified in the
                 design task — design doc §9)

DELTA_RANDOM(k) = Q_ARM_B_3(k) - Q_random_3(k)
DELTA_SIDON(k)  = Q_ARM_B_3(k) - Q_sidon_3(k)   (Q_sidon already sealed,
                                                  diversification-coverage-t539-v1-result.json)
```

`K(3)` for T539 = `5,781` (out of `N = 575,757`, `1.004069%`), `K(4) =
171` (`0.029700%`), `K(5) = 1` (`0.000174%`) — all independently
recomputed in the design task via the reused `qualifying_ticket_count`
function (design doc §9), not re-derived by hand here.

## 5. Computational feasibility (estimated in the design task, not measured at real T539 scale — see design doc §6)

Toy-scale measurements (`draw_size=5`, `pool_size` in {16,18,20,22}, all
far below 39) fit a cost model cross-validated against B649's own real,
measured arm-B runtime (774.5s, within 12.6% of the model's prediction,
i.e. a 1.145x under-prediction ratio) before extrapolating: **~30-35s
estimated** for a single nested-prefix build to `ticket_count=20` (which
yields every ladder `k` as a free slice) at real `(pool_size=39,
draw_size=5)` scale. Not measured directly — `pool_size=39` was not
invoked anywhere in the design task (design doc §2). Coverage evaluation
on top of the built portfolio reuses the already-proven-feasible T539
winning-space method (`0.025s` bare enumeration, already exercised by the
sealed T539 Sidon cell).

```text
MONTE_CARLO:  NONE
REAL_DRAW_HISTORY: NOT_USED
NON_LOAD_BEARING_RUNTIME_ESTIMATE: TRUE -- the 1.145x correction and the
                                    ~30-35s figure it produces are
                                    engineering feasibility estimates
                                    only; not part of this preregistration's
                                    scientific contract (Sec 1-4, 6) and
                                    not consumed by LOCKED_PARAMETERS or
                                    any estimand/classification rule. The
                                    real execution task measures actual
                                    wall-clock time directly.
```

## 6. Classification (frozen rule, identical in kind to B649/T539/P638, not applied here)

```text
SANITY_CHECK: DELTA_RANDOM(1) must equal exactly 0 (pool symmetry at k=1 —
              does not require Q_random_3(1) itself to be 0; it is
              K(3)/N = 5781/575757, independently verified nonzero in the
              design task).

For k > 1, over the full ladder:
  DELTA_RANDOM(k) > 0 for every k  -> OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
  DELTA_RANDOM(k) == 0 for every k -> MATCHES_RANDOM_EXPECTED_COVERAGE
  DELTA_RANDOM(k) < 0 for every k  -> UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE
  otherwise                         -> MIXED_BY_EXPOSURE

DELTA_SIDON(k) > 0 for every k > 1 -> EXCEEDS_T539_SIDON_GAIN
otherwise                            -> DOES_NOT_EXCEED_T539_SIDON_GAIN (see
                                        design doc §10 for the full
                                        Q1/Q2/Q3 rule set, including the
                                        B649 direction-consistency check)
```

## 7. Scope boundary (frozen, unchanged in kind from B649/T539/P638)

```text
PREDICTIVE_ADVANTAGE:    NOT_TESTED
PRIZE_VALUE_ADVANTAGE:    NOT_TESTED
ECONOMIC_OPTIMALITY:      NOT_TESTED
P638:                     NOT_RUN
PRODUCTION / COHORT / PROSPECTIVE: NONE
B649 ARM C / BOUNDED OPTIMIZER:    OUT_OF_SCOPE, not translated by this cell
```

## 8. No-rescue commitment (pre-committed for the future lock, not yet binding)

If, once actually locked and executed, the classification is
`MATCHES_RANDOM_EXPECTED_COVERAGE` or
`UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE`, or
`DOES_NOT_EXCEED_T539_SIDON_GAIN`: record it and stop. No new constructor,
no offset, no different event threshold for this `matrix_variant_id` — a
different geometry would be a new variant, preregistered before touching
the winning-space enumeration.

## 9. Preregistration status

```text
PREREGISTRATION_LOCKED: NO
LOCK_BLOCKERS:            NONE identified — the constructor mapping has
                          no unresolved constant (design doc §5) and every
                          parameter above is already fully specified; the
                          only missing step before an Owner could lock
                          this file is the explicit lock+execute
                          authorization itself (design doc §18, §2's
                          frozen boundary)
HASH:                     NOT YET COMPUTED (no
                          tools/hash_preregistration_t539_arm_b.py exists
                          yet — would be written, mirroring
                          tools/hash_preregistration_t539.py, at lock time)
```
