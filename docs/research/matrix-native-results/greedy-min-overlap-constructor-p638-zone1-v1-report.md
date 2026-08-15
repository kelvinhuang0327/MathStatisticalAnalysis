# GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1 — result

Status: SEALED — P638_REPLICATION_SUPPORTED ｜ 2026-08-15 ｜ Strategy Matrix
Phase 5, P638 Zone-1 lock+execute

`TASK_ID: STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_LOCK_EXECUTE_R1`.
Preregistration (locked before any real P638 Zone-1-scale constructor call
or winning-space enumeration):
`greedy-min-overlap-constructor-p638-zone1-v1-preregistration.md`. Hash:
`e535caa323c1bb5ef027e5d8c5efa8b12fa83f59f83312ad1d9250d1e039f58b`
(execution script re-verified this before running). Full result:
`greedy-min-overlap-constructor-p638-zone1-v1-result.json`. Attempt
ledger: `greedy-min-overlap-constructor-p638-zone1-v1-attempt-ledger.json`.

## Identity

```text
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
MATRIX_VARIANT_ID:     GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1
LOTTERY:               POWER_LOTTO (Zone-1, 6-of-38; Zone-2 out of scope)
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:          EXACT_COMBINATORIAL
REPLICATES:             GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1 and
                        GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 (native
                        parameter substitution, not a copy)
```

## Method

Three arms, real P638 Zone-1 scale (`pool_size=38, draw_size=6`,
`C(38,6) = 2,760,681` possible draws), `K = {1,3,5,10,15,20}`, primary
event `ZONE1_M3_PLUS`, secondary `ZONE1_M4_PLUS, ZONE1_M5_PLUS, ZONE1_M6`:

- **A** `CYCLIC_SIDON_SHIFT_P638_ZONE1_V1` — immutable, unchanged
  (`src/lottolab/research/cyclic_sidon_shift_p638.py`, the one and only
  tracked, sealed P638 Zone-1 Sidon comparator; the separate untracked
  `cyclic_sidon_shift_p638_zone1.py` duplicate flagged in the design task
  was not read, imported, or relied upon anywhere in this execution).
- **B** `GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1` — deterministic
  greedy, no Sidon/difference-set algebra, invoked at real P638 Zone-1
  scale for the first time.
- **C** `RANDOM_EXPECTED_COVERAGE` — immutable, closed-form.

B649's own bounded-optimizer arm has no P638 Zone-1 counterpart in this
task — three arms only, per the Owner packet. Coverage is computed by the
same single-pass earliest-index enumeration method the sealed
`DIVERSIFICATION_COVERAGE_P638_ZONE1_V1` cell and
`run_greedy_min_overlap_constructor_t539_v1.py` already use (no
B649-specific fast evaluator — the design doc's own feasibility estimate
found none necessary for arm B's construction cost). Arm A was recomputed
fresh in this task's execution script (not re-quoted) and cross-checked
for **exact** identity against
`diversification-coverage-p638-zone1-v1-result.json`'s own `q_sidon`
values — confirmed identical at every `(m, k)` pair
(`arm_a_identity_check_vs_sealed_coverage_cell: true`). Every coverage
value is an exact `fractions.Fraction`. `MONTE_CARLO: NONE`.
`REAL_DRAW_HISTORY: NOT_USED`. B649 and T539 are not rerun by this task.

## Result — primary event (ZONE1_M3_PLUS)

| k | Q_sidon (A) | Q_greedy (B) | Q_random (C) | DELTA_RANDOM_B(k) | DELTA_SIDON(k) |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.03869806 | 0.03869806 | 0.03869806 | +0.00000000 | +0.00000000 |
| 3 | 0.11285730 | 0.11565951 | 0.11165955 | +0.00399995 | +0.00280221 |
| 5 | 0.18280852 | 0.19204138 | 0.17908342 | +0.01295797 | +0.00923287 |
| 10 | 0.34421978 | 0.35290206 | 0.32609621 | +0.02680585 | +0.00868228 |
| 15 | 0.48421748 | 0.48961289 | 0.44678160 | +0.04283129 | +0.00539541 |
| 20 | 0.60548430 | 0.61074351 | 0.54585434 | +0.06488917 | +0.00525921 |

`DELTA_RANDOM_B(1) = 0` and `DELTA_SIDON(1) = 0` exactly, both asserted at
runtime (not just observed) — required by the preregistration's
pool-symmetry argument. `DELTA_RANDOM_SIDON(k)` (arm A vs. arm C) is not
re-tabulated here; it is the already-sealed
`DIVERSIFICATION_COVERAGE_P638_ZONE1_V1` cell's own `D_3(k)`, reproduced
identically by this task's independent recomputation (see Method).

`descriptive_classification`: arm B `OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`
and exceeds arm A's own gain over random at **every** tested `k > 1`.
`DELTA_SIDON(k)` rises from `k=3` to a peak at `k=5` (`+0.00280` →
`+0.00923`), then declines through `k=20` (`+0.00868` → `+0.00540` →
`+0.00526`) — still strictly positive throughout the tested ladder, but
not monotonic, similar in kind to T539's own non-monotonic `DELTA_SIDON(k)`
shape (a different shape in detail: T539 rose through `k=15` before
dipping once at `k=20`; P638 Zone-1 peaks earlier, at `k=5`, and declines
thereafter). Disclosed as an observed fact, not smoothed over: Q2 requires
positivity at every `k > 1`, not monotonicity, and the preregistration's
classification rule was frozen before this shape was known.

## Result — secondary events (ZONE1_M4_PLUS, ZONE1_M5_PLUS, ZONE1_M6)

**Disclosed structural finding, verified not assumed:** at every tested
`k`, `Q_greedy(m,k)` is **exactly identical** to `Q_sidon(m,k)` for
`m in {4, 5, 6}` (`delta_sidon["4"|"5"|"6"][k] = 0/1` at every `k`,
full detail in `result.json`). This is not a coincidence and not a defect
— it is a provable consequence of two independently-established facts:
(1) both arms' `max_pairwise_overlap` never exceeds `1` anywhere in the
tested ladder (arm A by the Sidon module's own cyclic-shift guarantee;
arm B measured `0` at `k<=5` and `1` at `k in {10,15,20}`, see Geometry
below), and (2) for `draw_size=6` and `m>=4`, `2m-1 >= 7 > 6` means no
single 6-number draw can ever achieve `>=m` hits against two tickets that
overlap by at most `1` number — so the "`>=m` hits" events for different
tickets in either portfolio are mutually exclusive, making
`Q_X_m(k) = k * K(m)/N` exactly for *any* portfolio of `k` tickets with
pairwise overlap `<=1`, regardless of which specific tickets they are.
Spot-checked exactly: `Q_greedy(4,20) = 8980/162393 = 20 * (449/162393) =
20 * K(4)/N`. `DELTA_RANDOM_B(m,k)` and `DELTA_RANDOM_SIDON(m,k)` are
therefore also identical to each other for `m in {4,5,6}` (both arms beat
the random-expected baseline by the same margin) — visible directly in
`result.json`, not re-tabulated here since Q1/Q2/Q3 are defined only on
the primary event (`m=3`, preregistration S6).

## Geometry (arm B, every k; full detail in result.json)

| k | max overlap | mean overlap | unique numbers used | reuse dispersion | duplicate tickets |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0.000 | 6 / 38 | 0.365 | 0 |
| 3 | 0 | 0.000 | 18 / 38 | 0.499 | 0 |
| 5 | 0 | 0.000 | 30 / 38 | 0.408 | 0 |
| 10 | 1 | 0.667 | 36 / 38 | 0.815 | 0 |
| 15 | 1 | 0.810 | 37 / 38 | 1.110 | 0 |
| 20 | 1 | 0.826 | 38 / 38 | 1.204 | 0 |

`duplicate_tickets: 0` for arm B at every `k` (frozen invariant, asserted
at runtime, not just observed). `max_pairwise_overlap` never exceeds `1`
across the full tested ladder, mirroring both B649's and T539's own arm-B
geometry finding (and, per the secondary-event finding above, doing the
real combinatorial work behind that identical-to-Sidon result). At
`k <= 5`, `pool_size // draw_size = 38 // 6 = 6` fully disjoint blocks are
still available, so every pair among the first 5 tickets is disjoint
(`max/mean overlap = 0`), exactly as the shared constructor's own
disclosed structural behavior predicts.

**Disclosed prediction (design doc §7), checked, not confirmed.** B649's
real arm-B portfolio never used its pool's highest number (49) at any
tested `k`; T539's used its highest number (39) starting at `k=15`. P638
Zone-1's arm B uses its highest number (38) only starting at `k=20`
(`number_use_counts["38"] = 0` at `k in {1,3,5,10,15}`, `= 2` at `k=20`) —
later than T539, closer to B649's own bias but not absolute. Reported
exactly as observed, since this was pre-registered as a testable
prediction, not retroactively adjusted.

## Decision rules (frozen by the preregistration §6, applied here)

```text
Q1 (does arm B beat random at every k>1)?
  DELTA_RANDOM_B(k) > 0 for every k in {3,5,10,15,20}: TRUE
  -> P638_ARM_B_OUTPERFORMS_RANDOM

Q2 (does arm B exceed P638 Zone-1 Sidon's own gain over random at every k>1)?
  DELTA_SIDON(k) > 0 for every k in {3,5,10,15,20}: TRUE
  -> P638_ARM_B_EXCEEDS_SIDON_GAIN

Q3 (direction consistent with B649 and T539 arm B's own sealed results)?
  P638 Zone-1 Q2 == P638_ARM_B_EXCEEDS_SIDON_GAIN
  -> CONSISTENT_WITH_B649_AND_T539
```

```text
P638_REPLICATION_STATUS:                            P638_REPLICATION_SUPPORTED
NON_SIDON_LOW_OVERLAP_CROSS_LOTTERY_STATUS:         SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES
```

## What this does and does not claim

Does claim: at every tested exposure level `k > 1`, POWER_LOTTO Zone-1's
native instantiation of B649's non-Sidon, algebra-free greedy min-overlap
constructor covers strictly more of the `ZONE1_M3_PLUS` winning-space than
both a matched-random portfolio and P638 Zone-1's own already-sealed
Sidon-shift geometry, under POWER_LOTTO Zone-1's exact
`C(38,6) = 2,760,681` winning space, via full enumeration (not sampling) —
the same finding B649 and T539 already established, now replicated
natively in the third and last of this repository's three supported
lottery structures for this arm-B translation chain. Does not claim:
predictive advantage on real draws, prize-value/cost efficiency, that arm
B is optimal among all possible low-overlap geometries, that this
generalizes past `k=20`, Zone-2 (1-of-8) allocation behavior, or full-ticket
(Zone-1 + Zone-2 combined) behavior — none of these are tested by this
task.

## Runtime and resources

```text
arm_a_seconds:         0.0000123  (fresh coverage query only; Sidon portfolio
                       generation is cheap, unlike its coverage evaluation)
arm_b_seconds:         159.01     (first-ever real-P638-Zone-1-scale
                       constructor call; design doc's pre-registered,
                       non-load-bearing estimate was ~165s -- within ~4%)
enumeration_seconds:   16.69      (single-pass earliest-index coverage
                       evaluation, both arms, all four thresholds,
                       C(38,6) = 2,760,681 draws)
total_seconds:         175.70
peak_memory_bytes:     22,003,712  (~22.0 MB)
```

The design doc's `~165.17s` estimate for `arm_b_seconds` was explicitly
marked `NON_LOAD_BEARING_RUNTIME_ESTIMATE` (an engineering feasibility
projection only, not part of the scientific contract) — the measured
`159.01s` lands close to it, confirming the projection was reasonable
without the estimate itself ever gating any estimand, classification, or
locked parameter.

## Classification

```text
q1_classification:                            P638_ARM_B_OUTPERFORMS_RANDOM
q2_classification:                            P638_ARM_B_EXCEEDS_SIDON_GAIN
q3_classification:                            CONSISTENT_WITH_B649_AND_T539
p638_replication_status:                      P638_REPLICATION_SUPPORTED
non_sidon_low_overlap_cross_lottery_status:   SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES
arm_a_identity_check_vs_sealed_coverage_cell: true
sanity_check_delta_random_b_at_k1_is_exactly_zero:        true
sanity_check_delta_sidon_at_k1_is_exactly_zero:            true
sanity_check_delta_random_sidon_at_k1_is_exactly_zero:     true
```

## Scope boundary

```text
PREDICTIVE_ADVANTAGE / PRIZE_VALUE_ADVANTAGE / ECONOMIC_OPTIMALITY: NOT_TESTED
ZONE_2_ALLOCATION:                    NOT_TESTED, NOT_DESIGNED
B649 / T539:                          NOT_RERUN (cited as given for Q3)
PRODUCTION / COHORT / PROSPECTIVE:    NONE
```

## No-rescue statement

The locked arms, contract, k ladder, evaluation method, comparator, and
classification/replication rule were not changed after this result was
seen. No new constructor was added, no different event threshold was
tried, and the non-monotonic `DELTA_SIDON(k)` shape (peaking at `k=5`,
declining thereafter) was not smoothed, re-parametrized, or used to
justify a rerun once visible.

## Replication-closure note

Per the design doc's (9b60007, S10) replication-closure note: POWER_LOTTO
Zone-1 is the last of the three native lottery structures this repository
currently supports (BIG_LOTTO, DAILY_539, POWER_LOTTO) for this specific
arm-B (`GREEDY_MIN_OVERLAP_CONSTRUCTOR`) translation chain. With
`P638_REPLICATION_SUPPORTED`, this closes the three-lottery replication
chain for the non-Sidon low-overlap constructor mechanism rather than
opening a new replication target — matching the same closure precedent set
by `DIVERSIFICATION_COVERAGE_P638_ZONE1_V1`'s own
`SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES` finding for the Sidon-coverage
mechanism. Zone-2 (1-of-8) remains a wholly separate, unaddressed design
dimension, not tested or designed by this task or any of its predecessors.
