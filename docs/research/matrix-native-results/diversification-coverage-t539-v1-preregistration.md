# DIVERSIFICATION_COVERAGE_T539_V1 — locked preregistration

Status: LOCKED before any winning-space enumeration was performed ｜ 2026-08-14 ｜ Strategy Matrix Phase 2

Replication of `DIVERSIFICATION_COVERAGE_B649_V1`
(`OUTPERFORMS_RANDOM_EXPECTED_COVERAGE`, sealed) into DAILY_539's native
5/39 structure. Same research claim, native reconstruction — nothing
copied from the B649 base set by assumption; independently searched and
verified for Z_39.

## 0. Identity

```text
MATRIX_VARIANT_ID:    DIVERSIFICATION_COVERAGE_T539_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:              DAILY_539
SOURCE_TYPE:           STRATEGY_MATRIX_NATIVE
REPLICATES:            DIVERSIFICATION_COVERAGE_B649_V1 (native reconstruction, not a copy)
```

## 1. Research question (frozen, identical claim to the B649 cell)

At a fixed ticket count `k`, does a preregistered deterministic
portfolio-geometry rule increase exact `M3_PLUS` winning-space coverage
relative to `k` uniformly random distinct tickets' *expected* coverage?
`PREDICTIVE_ADVANTAGE: NOT_TESTED`. `PRIZE_VALUE_ADVANTAGE: NOT_TESTED`.
`ECONOMIC_OPTIMALITY: NOT_TESTED`.

## 2. Exposure ladder and events (frozen, unchanged from B649)

```text
EXPOSURE_LADDER:            [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:               M3_PLUS   (main_hits >= 3, out of 5 -- T539's own
                              draw size, not reused from B649's 6)
SECONDARY_DESCRIPTIVE_EVENTS: M4_PLUS, M5_PLUS
PRIZE_VALUE_CLAIM:            NONE
```

`M3_PLUS` here means "at least 3 of a ticket's 5 numbers match" — a
different fraction of the ticket (3/5 vs B649's 3/6) than the B649 cell,
disclosed explicitly so the two results are not misread as the same
threshold in relative terms. Kept as `M3_PLUS` for continuity with the
B649 identity and because it is DAILY_539's own most natural low-tier
main-hit threshold, not because the fraction matches.

## 3. Portfolio constructor — `CYCLIC_SIDON_SHIFT_T539_V1` (frozen, verified)

Base set in `Z_39` (0-indexed): `{0, 1, 3, 7, 12}`, found by the identical
deterministic greedy search as the B649 base set (start from `{0}`, add
the smallest residue that introduces no duplicate pairwise difference,
stop at 5 elements) — **independently run for modulus 39**, not assumed
from B649. `T_0` (1-based) = `{1, 2, 4, 8, 13}`.

Verified in this task before locking
(`src/lottolab/research/cyclic_sidon_shift_t539.py`, 10 tests, mirroring
the B649 module's test structure):

1. Genuine Sidon set mod 39 — all `5*4=20` ordered pairwise differences
   distinct.
2. Pairwise ticket overlap `<= 1` across **all 39 possible shifts**
   (`C(39,2) = 741` pairs), exhaustively checked, not asserted.
3. Strict nested-prefix portfolio property.

**Final pre-lock wording correction.** The base set's five elements are
identical to the first five elements of the B649 base set
(`{0,1,3,7,12,20}`). This is disclosed, not hidden — but the equality is
**not** claimed to be mathematically forced. "A subset of a Sidon set is
itself a Sidon set" is true, and is exactly why this set's Sidon-in-Z_39
property was worth independently checking (and was — see
`test_base_set_is_a_sidon_set_mod_39`); it does **not**, by itself, imply
that two independent greedy searches over *different* moduli (39 vs. 49)
must produce the same prefix, since Sidon-ness mod 39 and mod 49 are
different conditions on different difference sets. The two searches
agreeing here is consistent with both starting from `{0}` and never yet
needing to wrap around within the first five elements (every pairwise
difference involved is well under the smaller modulus, 39), not a
theorem that guarantees agreement in general.

```text
INDEPENDENTLY_DERIVED_WITH_SAME_DETERMINISTIC_SEARCH: YES
COINCIDES_WITH_B649_BASE_PREFIX:                      YES
SIDON_VALIDITY_IN_Z39:                                INDEPENDENTLY_VERIFIED
```

## 4. Primary estimand and computation method (frozen, structurally identical to B649)

```text
Q_sidon_m(k)   = exact P(>= 1 ticket in P_k has hits >= m), single-pass
                 enumeration over all C(39,5) = 575,757 possible draws
Q_random_m(k)  = exact_random_portfolio_coverage(39, 5, m, k)  (reused
                 verbatim, unmodified, from src/lottolab/research/exact_coverage_baseline.py
                 -- confirmed in this task to generalize correctly to
                 (pool=39, draw=5) with no code changes: Q_random_3(1)
                 recomputed via the closed form exactly equals K(3)/N,
                 verified by direct computation in this task, not assumed)

D_m(k)                = Q_sidon_m(k) - Q_random_m(k)
MARGINAL_GEOMETRY_DELTA(k_j) = [D_3(k_j) - D_3(k_{j-1})] / (k_j - k_{j-1})
```

`K(3)` for T539 = `sum_{j=3}^{5} C(5,j) * C(34,5-j) = 5,781` (out of
`N = 575,757`, i.e. `1.0041%` of draws — computed and verified in this
task via the reused `qualifying_ticket_count` function, not re-derived by
hand).

`MARGINAL_GEOMETRY_DELTA` is normalized per additional ticket (divided by
the ladder step size, since the ladder's steps are uneven), matching
B649's convention exactly. Named `GEOMETRY_DELTA`, not `EFFICIENCY`: no
cost/utility authority exists, so nothing here may be read as an
economic quantity.

## 5. Computational feasibility (verified in this task, before locking)

Bare enumeration of all `575,757` T539 draws: `0.025s` (measured, prior
design session). This is `~24x` fewer draws than B649's `13,983,816`, so
the full per-draw, up-to-20-ticket evaluation this experiment needs is
comfortably feasible with the same method B649 used — no method change.

`MONTE_CARLO: NONE`. `REAL_DRAW_HISTORY: NOT_USED`.

## 6. Classification (frozen, identical rule to B649, corrected terminology from the start)

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

Unlike the B649 cell (whose original sealed artifact says
`OUTPERFORMS_RANDOM_COVERAGE` and was clarified only afterward at the
ledger layer), this document locks the corrected `_EXPECTED_` terminology
from the start, and the execution script below emits it directly — there
is no earlier label to reconcile.

## 7. Scope boundary (frozen, unchanged in kind from B649)

```text
PREDICTIVE_ADVANTAGE:    NOT_TESTED
PRIZE_VALUE_ADVANTAGE:    NOT_TESTED
ECONOMIC_OPTIMALITY:      NOT_TESTED
P638:                     NOT_RUN (waits for this T539 result; P638's
                          dual-zone structure needs its own separate
                          native design, not a same-wave copy)
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
size, draw size, the exact base set, the exposure ladder, the primary and
secondary event thresholds) by `tools/hash_preregistration_t539.py`,
recorded in `diversification-coverage-t539-v1-preregistration-hash.json`.
The execution script re-verifies this hash before running and refuses to
proceed on a mismatch.
