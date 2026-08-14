# DIVERSIFICATION_COVERAGE_P638_ZONE1_V1 — locked preregistration

Status: LOCKED before any winning-space enumeration was performed ｜ 2026-08-14 ｜ Strategy Matrix Phase 3

Replication of `DIVERSIFICATION_COVERAGE_B649_V1` and
`DIVERSIFICATION_COVERAGE_T539_V1` (both sealed,
`OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`) into POWER_LOTTO Zone-1's native
6/38 structure. Same research claim, native reconstruction — nothing
copied from either prior base set by assumption; independently searched
and verified for `Z_38`. Finalizes, for exact lock metadata only, the
constructor and baseline math already derived and verified in
`docs/research/strategy-matrix-phase3-p638-diversification-native-design-r1.md`
(design task, commit `04ec484725eecac52ef7461a4f0c9606c1baf501`); no new
scientific or design choice is made in this document.

## 0. Identity

```text
MATRIX_VARIANT_ID:    DIVERSIFICATION_COVERAGE_P638_ZONE1_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:              POWER_LOTTO
GAME_COMPONENT:        ZONE_1 (6-of-38); ZONE_2 (1-of-8) OUT OF SCOPE
SOURCE_TYPE:           STRATEGY_MATRIX_NATIVE
REPLICATES:            DIVERSIFICATION_COVERAGE_B649_V1 and
                       DIVERSIFICATION_COVERAGE_T539_V1 (native
                       reconstruction, not a copy of either)
```

## 1. Research question (frozen, identical claim to the B649 and T539 cells)

At a fixed ticket count `k`, does a preregistered deterministic
portfolio-geometry rule increase exact `M3_PLUS` winning-space coverage
relative to `k` uniformly random distinct Zone-1 tickets' *expected*
coverage? `PREDICTIVE_ADVANTAGE: NOT_TESTED`. `PRIZE_VALUE_ADVANTAGE:
NOT_TESTED`. `ECONOMIC_OPTIMALITY: NOT_TESTED`. Zone-2 allocation is not
tested by this variant at all.

## 2. Exposure ladder and events (frozen, unchanged from B649/T539)

```text
EXPOSURE_LADDER:              [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:                 ZONE1_M3_PLUS (main_hits >= 3, out of 6)
SECONDARY_DESCRIPTIVE_EVENTS:  ZONE1_M4_PLUS, ZONE1_M5_PLUS, ZONE1_M6
PRIZE_VALUE_CLAIM:             NONE
```

`ZONE1_M6` (all 6 of 6) is a new secondary threshold not present for T539
(whose draw_size=5 caps its own ladder at M5) — included because P638
Zone-1's draw_size is 6, matching B649's own shape in this one respect.

## 3. Portfolio constructor — `CYCLIC_SIDON_SHIFT_P638_ZONE1_V1` (frozen, verified)

Base set in `Z_38` (0-indexed): `{0, 1, 3, 7, 17, 30}`.
`T_0` (1-based) = `{1, 2, 4, 8, 18, 31}`.

**Even-modulus obstruction, disclosed in full (derived and verified in the
prior design task, restated here for the locked record).** The plain
greedy search used verbatim for B649 (mod 49) and T539 (mod 39) — start
from `{0}`, add the smallest residue that introduces no duplicate pairwise
difference, stop at 6 elements — reproduces `{0,1,3,7,12}` and then
exhausts every remaining residue without finding a sixth element, run
independently for modulus 38. This is provable, not incidental: `19 =
38/2` is its own negation mod 38, so any base pair differing by exactly 19
yields the same signed difference from both orderings (where a genuine
Sidon set needs two distinct values), and independently forces a pairwise
cyclic-shift intersection of exactly 2 at shift-distance 19. Both 49 and
39 are odd, so this case never arose for either prior replication — it is
specific to POWER_LOTTO Zone-1's even pool size.

**Resolution**: the identical deterministic criterion, completed by
depth-first backtracking (same smallest-untried-residue order; the one
added rejection rule — no base pair may differ by exactly `pool_size/2` —
is itself required by the same criterion, not a weaker one) instead of
non-backtracking greedy. Reproduces B649's and T539's exact base sets
wherever plain greedy already succeeds (verified), so this is a
completion of the same pre-result contract, not a switch to a heuristic,
randomized, or outcome-tuned method — the search never inspected
winning-space coverage.

Verified in the design task
(`src/lottolab/research/cyclic_sidon_shift_p638.py`, 14 tests, mirroring
the B649/T539 modules' test structure):

1. Genuine Sidon set mod 38 — all `6*5=30` ordered pairwise differences
   distinct, and no base pair differs by exactly 19.
2. Pairwise ticket overlap `<= 1` across **all 38 possible shifts**
   (`C(38,2) = 703` pairs), exhaustively checked, not asserted. **Measured
   maximum: exactly 1.**
3. Strict nested-prefix portfolio property.
4. The search functions themselves (`greedy_sidon_base`,
   `derive_base_set_by_backtracking_search`) reproduce the exact committed
   B649 and T539 base sets, and re-derive this module's own constant —
   the base set was not hand-picked.

```text
INDEPENDENTLY_DERIVED_WITH_SAME_DETERMINISTIC_SEARCH: YES (completed by
                                                            backtracking;
                                                            see above)
COINCIDES_WITH_B649_T539_BASE_PREFIX:                 PARTIAL (shares
                                                        {0,1,3,7}; diverges
                                                        at the 5th element
                                                        — a real divergence
                                                        forced by
                                                        exhaustive search,
                                                        not preserved by
                                                        assumption)
SIDON_VALIDITY_IN_Z38:                                INDEPENDENTLY_VERIFIED
```

## 4. Primary estimand and computation method (frozen, structurally identical to B649/T539)

```text
Q_sidon_m(k)   = exact P(>= 1 ticket in P_k has hits >= m), single-pass
                 enumeration over all C(38,6) = 2,760,681 possible draws
Q_random_m(k)  = exact_random_portfolio_coverage(38, 6, m, k)  (reused
                 verbatim, unmodified, from src/lottolab/research/exact_coverage_baseline.py
                 -- confirmed in the design task to generalize correctly to
                 (pool=38, draw=6) with no code changes: Q_random_3(1)
                 recomputed via the closed form exactly equals K(3)/N,
                 verified by direct computation, not assumed)

D_m(k)                = Q_sidon_m(k) - Q_random_m(k)
MARGINAL_GEOMETRY_DELTA(k_j) = [D_3(k_j) - D_3(k_{j-1})] / (k_j - k_{j-1})
```

`K(3)` for P638 Zone-1 = `sum_{j=3}^{6} C(6,j) * C(32,6-j) = 106,833` (out
of `N = 2,760,681`, i.e. `3.869806%` of draws — computed and verified in
the design task via the reused `qualifying_ticket_count` function, not
re-derived by hand).

`MARGINAL_GEOMETRY_DELTA` is normalized per additional ticket (divided by
the ladder step size, since the ladder's steps are uneven), matching
B649/T539's convention exactly. Named `GEOMETRY_DELTA`, not `EFFICIENCY`:
no cost/utility authority exists, so nothing here may be read as an
economic quantity.

## 5. Computational feasibility (verified in the design task, before locking)

Bare enumeration of all `2,760,681` P638 Zone-1 draws: `0.1421s`
(measured, design task). This is `~5x` fewer draws than B649's
`13,983,816` and `~4.8x` more than T539's `575,757` — comfortably feasible
with the same method both prior replications used, no method change.

`MONTE_CARLO: NONE`. `REAL_DRAW_HISTORY: NOT_USED`.

## 6. Classification (frozen, identical rule to B649/T539)

```text
SANITY_CHECK: D_3(1) must equal exactly 0.

For k > 1, over the full ladder:
  D_3(k) > 0 for every k  -> OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
  D_3(k) == 0 for every k -> MATCHES_RANDOM_EXPECTED_COVERAGE
  D_3(k) < 0 for every k  -> UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE
  otherwise                -> MIXED_BY_EXPOSURE

GEOMETRY_ADVANTAGE_ZERO_CROSSING = smallest k_j (after the first ladder
    step) where MARGINAL_GEOMETRY_DELTA(k_j) <= 0, or NONE.
```

## 7. Scope boundary (frozen, unchanged in kind from B649/T539)

```text
PREDICTIVE_ADVANTAGE:    NOT_TESTED
PRIZE_VALUE_ADVANTAGE:    NOT_TESTED
ECONOMIC_OPTIMALITY:      NOT_TESTED
ZONE_2_ALLOCATION:        NOT_TESTED (a separate design dimension; not
                          predesigned or authorized here)
FULL_TICKET_DIVERSIFICATION: NOT_TESTED
PRODUCTION / COHORT / PROSPECTIVE: NONE
```

## 8. No-rescue commitment

If classification is `MATCHES_RANDOM_EXPECTED_COVERAGE` or
`UNDERPERFORMS_RANDOM_EXPECTED_COVERAGE`: record it and stop. No new base
set, no offset, no different Sidon construction, no different event
threshold for this `matrix_variant_id`. A different geometry is a new
variant, preregistered before touching the winning-space enumeration,
exactly as this document was.

## 9. Preregistration hash

Computed over the canonical JSON of every locked parameter above (pool
size, draw size, zone, the exact base set, the exposure ladder, and the
primary and secondary event thresholds) by `tools/hash_preregistration_p638.py`,
recorded in `diversification-coverage-p638-zone1-v1-preregistration-hash.json`.
The execution script re-verifies this hash before running and refuses to
proceed on a mismatch.
