# GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1 — preregistration DRAFT

Status: DRAFT — NOT LOCKED, no winning-space enumeration has been (or
could yet be, per §2 of the design doc) performed against this arm ｜
2026-08-15 ｜ Strategy Matrix Phase 5, P638 Zone-1 native translation

This is a **draft**, produced by
`STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1` (see
`strategy-matrix-phase5-p638-non-sidon-low-overlap-native-design-r1.md`
for the full design rationale this draft summarizes). It follows the same
format the locked preregistrations
`diversification-coverage-p638-zone1-v1-preregistration.md` and
`diversification-constructor-frontier-b649-v1-preregistration.md`, and the
still-draft `greedy-min-overlap-constructor-t539-v1-preregistration-draft.md`,
already use, but is **not itself locked**: `PREREGISTRATION_LOCKED: NO`. A
separate, later Owner-authorized lock-and-execute task must (a) freeze
this file's content byte-for-byte (or explicitly revise and re-draft it),
(b) hash it via the same `tools/hash_preregistration_*.py` pattern the
other locked cells use, and (c) have its execution script verify that
hash before touching the real `C(38,6)` winning space — none of which has
happened yet.

## 0. Identity

```text
MATRIX_VARIANT_ID:    GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:               POWER_LOTTO
GAME_COMPONENT:        ZONE_1 (6-of-38); ZONE_2 (1-of-8) OUT OF SCOPE
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
REPLICATES:             GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 and
                        GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 (native
                        parameter substitution — see design doc §5)
```

## 1. Research question (frozen, identical claim in kind to the B649 and T539 cells)

At a fixed ticket count `k`, does POWER_LOTTO Zone-1's native
instantiation of the B649 Phase-5 non-Sidon low-overlap constructor
increase exact `ZONE1_M3_PLUS` winning-space coverage relative to `k`
uniformly random distinct Zone-1 tickets' *expected* coverage, and does
it exceed P638 Zone-1's own already-sealed Sidon reference's gain over
random? `PREDICTIVE_ADVANTAGE: NOT_TESTED`. `PRIZE_VALUE_ADVANTAGE:
NOT_TESTED`. `ECONOMIC_OPTIMALITY: NOT_TESTED`. Zone-2 allocation is not
tested by this variant at all.

## 2. Exposure ladder and events (frozen, unchanged from B649/T539/P638)

```text
EXPOSURE_LADDER:              [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:                 ZONE1_M3_PLUS (main_hits >= 3, out of 6)
SECONDARY_DESCRIPTIVE_EVENTS:  ZONE1_M4_PLUS, ZONE1_M5_PLUS, ZONE1_M6
                                (degenerate exact-match case — see the
                                P638 Zone-1 Sidon cell's own disclosure)
PRIZE_VALUE_CLAIM:             NONE
```

## 3. Portfolio constructor — `GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1` (frozen definition, not yet executed)

`src/lottolab/research/greedy_min_overlap_constructor_p638_zone1.py`
(`greedy_min_overlap_portfolio_p638_zone1`), an unconditional delegation
to the shared, unmodified `greedy_min_overlap_portfolio(pool_size=38,
draw_size=6, ticket_count)`
(`src/lottolab/research/greedy_min_overlap_constructor.py`, frozen since
`971b97b`, not edited by this task). Ticket 0 is the lexicographically
first 6-subset of `1..38`. Ticket `i` (`i >= 1`) is the lexicographically
first not-yet-used 6-subset whose maximum pairwise overlap with every
already-chosen ticket is smallest — plain greedy scan-and-keep-best, no
backtracking, no revisiting an earlier ticket, no Sidon/difference-set
algebra, no random search, no post-result tuning.

`pool_size=38` and `draw_size=6` come directly from
`POWER_LOTTO_RULE_CONTRACT` (`main_number_max=38`, `main_number_count=6`,
`src/lottolab/domain/lottery_rules.py`), not invented for this
preregistration. Zone-2's `special_number_*` fields on the same rule
contract are never read.

```text
UNRESOLVED_B649/T539_CONSTANTS: NONE (design doc §5)
EVEN_MODULUS_OBSTRUCTION:        DOES NOT APPLY to this constructor
                                  (design doc §5.1 — no modular/cyclic
                                  structure exists for it to attach to)
DETERMINISTIC:                   YES
OUTCOME_FREE:                    YES
RANDOM_SEARCH:                   NO
POST_RESULT_TUNING:              NO
DUPLICATE_TICKETS:               must be 0 (structural invariant of the
                                 shared, already-tested constructor)
```

## 4. Primary estimand and computation method (frozen, structurally identical to B649/T539)

```text
Q_ARM_B_m(k)   = exact P(>= 1 ticket in the k-ticket arm-B portfolio has
                 hits >= m), single-pass enumeration over all
                 C(38,6) = 2,760,681 possible draws — NOT YET COMPUTED
Q_random_m(k)  = exact_random_portfolio_coverage(38, 6, m, k) (reused
                 verbatim, unmodified; independently re-verified in the
                 design task — design doc §9)

DELTA_RANDOM(k) = Q_ARM_B_3(k) - Q_random_3(k)
DELTA_SIDON(k)  = Q_ARM_B_3(k) - Q_sidon_3(k)   (Q_sidon already sealed,
                                                  diversification-coverage-p638-zone1-v1-result.json)
```

`K(3)` for P638 Zone-1 = `106,833` (out of `N = 2,760,681`, `3.869806%`),
`K(4) = 7,633` (`0.276490%`), `K(5) = 193` (`0.006991%`), `K(6) = 1`
(`0.000036%` — the degenerate exact-match case) — all independently
recomputed in the design task via the reused `qualifying_ticket_count`
function (design doc §9), not re-derived by hand here.

## 5. Computational feasibility (estimated in the design task, not measured at real P638 Zone-1 scale — see design doc §6)

Toy-scale measurements (`draw_size=6`, `pool_size` in {14,16,18,20,22},
all far below 38) fit a cost model cross-validated against B649's own
real, measured arm-B runtime (774.5s, same `draw_size=6`, no cross-size
adjustment needed — a 1.1635x under-prediction ratio) before
extrapolating: **~165s estimated** (~2.75 minutes) for a single
nested-prefix build to `ticket_count=20` (which yields every ladder `k`
as a free slice) at real `(pool_size=38, draw_size=6)` scale. Not
measured directly — `pool_size=38` was not invoked anywhere in the design
task (design doc §2). Coverage evaluation on top of the built portfolio
reuses the already-proven-feasible P638 Zone-1 winning-space method
(`0.1421s` bare enumeration, already exercised by the sealed P638 Zone-1
Sidon cell).

```text
MONTE_CARLO:  NONE
REAL_DRAW_HISTORY: NOT_USED
NON_LOAD_BEARING_RUNTIME_ESTIMATE: TRUE -- the 1.1635x correction and the
                                    ~165s figure it produces are
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
              K(3)/N = 106833/2760681, independently verified nonzero in
              the design task).

For k > 1, over the full ladder:
  DELTA_RANDOM(k) > 0 for every k  -> OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
  DELTA_RANDOM(k) == 0 for every k -> MATCHES_RANDOM_EXPECTED_COVERAGE
  DELTA_RANDOM(k) < 0 for every k  -> UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE
  otherwise                         -> MIXED_BY_EXPOSURE

DELTA_SIDON(k) > 0 for every k > 1 -> EXCEEDS_P638_ZONE1_SIDON_GAIN
otherwise                            -> DOES_NOT_EXCEED_P638_ZONE1_SIDON_GAIN
                                        (see design doc §10 for the full
                                        Q1/Q2/Q3 rule set, including the
                                        B649/T539 direction-consistency check)
```

## 7. Scope boundary (frozen, unchanged in kind from B649/T539/P638)

```text
PREDICTIVE_ADVANTAGE:    NOT_TESTED
PRIZE_VALUE_ADVANTAGE:    NOT_TESTED
ECONOMIC_OPTIMALITY:      NOT_TESTED
ZONE_2_ALLOCATION:         NOT_TESTED, NOT_DESIGNED
PRODUCTION / COHORT / PROSPECTIVE: NONE
B649 ARM C / BOUNDED OPTIMIZER:    OUT_OF_SCOPE, not translated by this cell
```

## 8. No-rescue commitment (pre-committed for the future lock, not yet binding)

If, once actually locked and executed, the classification is
`MATCHES_RANDOM_EXPECTED_COVERAGE` or
`UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE`, or
`DOES_NOT_EXCEED_P638_ZONE1_SIDON_GAIN`: record it and stop. No new
constructor, no offset, no different event threshold for this
`matrix_variant_id` — a different geometry would be a new variant,
preregistered before touching the winning-space enumeration.

## 9. Preregistration status

```text
PREREGISTRATION_LOCKED: NO
LOCK_BLOCKERS:            NONE identified — the constructor mapping has
                          no unresolved constant (design doc §5), the
                          even-modulus obstruction that affected P638
                          Zone-1's own Sidon reference does not apply to
                          this constructor (design doc §5.1), and every
                          parameter above is already fully specified; the
                          only missing step before an Owner could lock
                          this file is the explicit lock+execute
                          authorization itself (design doc §18, §2's
                          frozen boundary)
HASH:                     NOT YET COMPUTED (no
                          tools/hash_preregistration_p638_arm_b.py exists
                          yet — would be written, mirroring
                          tools/hash_preregistration_t539_arm_b.py, at
                          lock time)
```
