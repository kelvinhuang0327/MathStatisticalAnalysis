# DIVERSIFICATION_COVERAGE_B649_V1 — locked preregistration

Status: LOCKED before any winning-space enumeration was performed ｜ 2026-08-14 ｜ Strategy Matrix Phase 1

Supersedes the R1 draft's `CYCLIC_MINIMUM_REUSE` constructor, which had an
unresolved wraparound ambiguity past `k=8` (documented in that draft's §6,
item 1). Replaced with `CYCLIC_SIDON_SHIFT_B649_V1`, verified in this task
before locking (§3).

## 0. Identity

```text
MATRIX_VARIANT_ID:   DIVERSIFICATION_COVERAGE_B649_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
LOTTERY:              BIG_LOTTO
SOURCE_TYPE:           STRATEGY_MATRIX_NATIVE
RELATED:               ALLOCATION_EXPOSURE_EFFICIENCY_B649_V1 (DESIGN_ABANDONED --
                        this cell is the question that split cleanly off it)
```

## 1. Research question (frozen, unchanged from the R1 draft)

At a fixed ticket count `k`, does the `CYCLIC_SIDON_SHIFT_B649_V1`
portfolio geometry increase exact `M3_PLUS` winning-space coverage
relative to `k` uniformly random distinct tickets? `PREDICTIVE_ADVANTAGE:
NOT_TESTED`. `PRIZE_VALUE_EFFICIENCY: NOT_TESTED`.

## 2. Exposure ladder and events (frozen)

```text
EXPOSURE_LADDER:            [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:               M3_PLUS       (main_hits >= 3)
SECONDARY_DESCRIPTIVE_EVENTS: M4_PLUS, M5_PLUS  (computed, never override the primary classification)
PRIZE_VALUE_CLAIM:            NONE
```

## 3. Portfolio constructor — `CYCLIC_SIDON_SHIFT_B649_V1` (frozen, verified)

Base set in `Z_49` (0-indexed): `{0, 1, 3, 7, 12, 20}`. Ticket `i`
(0-indexed) is `{(x + i) mod 49 : x in base}`, reported 1-based and
ascending. `T_0` (1-based) = `{1, 2, 4, 8, 13, 21}`.
`P_k = {T_0, ..., T_{k-1}}` — a strict nested prefix, `P_k subset P_{k+1}`
by construction, no reordering, no historical data, no strategy output.

Verified in this task before locking
(`src/lottolab/research/cyclic_sidon_shift.py`, 10 tests):

1. The base set is a genuine Sidon set mod 49 -- all 30 ordered pairwise
   differences distinct.
2. Consequently, **every pair of the 49 possible shifts (not just the ones
   the exposure ladder uses) has pairwise ticket overlap `<= 1`** --
   checked exhaustively over all `C(49,2) = 1176` shift pairs, not
   asserted from the Sidon property alone. This is what removes the
   `CYCLIC_MINIMUM_REUSE` draft's ambiguity: the same bound holds
   uniformly across the whole shift space, so there is no `k=8`-style
   boundary and no offset-tuning decision to make.
3. `sidon_shift_ticket(0) == sidon_shift_ticket(49)` (period exactly 49,
   as it must be) and the portfolio is a verified strict nested prefix.

No optimality claim is made — this names one specific, disclosed,
low-overlap geometry, not a proof of the best possible one.

## 4. Primary estimand (frozen)

```text
PRIMARY_ESTIMAND: EXACT_BASELINE_RELATIVE_COVERAGE_DELTA

Q_sidon_m(k)  = exact P(>= 1 ticket in P_k has main_hits >= m),
                via one single-pass enumeration over all C(49,6) = 13,983,816
                possible draws (fixed, disclosed portfolio -- cheap; see §5)

Q_random_m(k) = exact_random_portfolio_coverage(49, 6, m, k)
                (src/lottolab/research/exact_coverage_baseline.py -- reused
                verbatim from the withdrawn allocation-exposure draft,
                already independently brute-force verified, not re-derived)

D_m(k)                = Q_sidon_m(k) - Q_random_m(k)
MARGINAL_GEOMETRY_DELTA(k_j) = [D_3(k_j) - D_3(k_{j-1})] / (k_j - k_{j-1})
```

`MARGINAL_GEOMETRY_DELTA` is normalized per additional ticket (divided by
the ladder step size, since the ladder's steps are uneven: 1->3 is +2,
5->10 is +5, etc.) so values are comparable across ladder segments. Named
`GEOMETRY_DELTA`, not `EFFICIENCY`: no cost/utility authority exists
(confirmed, allocation-exposure draft §2), so nothing here may be read as
an economic quantity.

## 5. Computation method (frozen, feasibility-verified)

One pass over all 13,983,816 possible draws. For each draw and each
`m in {3,4,5}`, find the smallest ticket index `i in 0..19` (if any) at
which `main_hits(T_i, draw) >= m` -- since `P_k` is a strict prefix, "draw
is covered by `P_k`" is exactly "that smallest index `< k`" for every `k`
in the ladder simultaneously, so all six `Q_sidon_m(k)` values (for a
given `m`) come from one pass, not six. This is the same order of
magnitude as the CUSUM experiment's enumeration (confirmed fast, `<1s`
bare iteration) plus a 20-ticket hit-count check per draw -- unrelated to,
and far cheaper than, the withdrawn `GREEDY_EXACT_M3_COVERAGE` idea's
per-step re-evaluation of up to `N` candidates (that was the infeasible
part, not enumeration itself).

`MONTE_CARLO: NONE`. `REAL_DRAW_HISTORY: NOT_USED`.

## 6. Classification (frozen, deterministic, no statistical test)

Every value here is exact (rational), so classification is a plain sign
rule, not a significance test.

```text
SANITY_CHECK: D_3(1) must equal exactly 0 (a single ticket, of any
              geometry, has identical exact coverage probability to a
              single random ticket -- pure symmetry, not specific to
              Sidon sets). Computed and checked, not assumed.

For k > 1, over the full ladder:
  D_3(k) > 0 for every k  -> OUTPERFORMS_RANDOM_COVERAGE
  D_3(k) == 0 for every k -> MATCHES_RANDOM_COVERAGE
  D_3(k) < 0 for every k  -> UNDERPERFORMS_RANDOM_COVERAGE
  otherwise                -> MIXED_BY_EXPOSURE

GEOMETRY_ADVANTAGE_ZERO_CROSSING = smallest k_j (after the first ladder
    step) where MARGINAL_GEOMETRY_DELTA(k_j) <= 0, or NONE.
```

`GEOMETRY_ADVANTAGE_ZERO_CROSSING` is a mathematical description only --
never called an "optimum" or given any economic reading.

## 7. Scope boundary (frozen)

```text
PREDICTIVE_ADVANTAGE:  NOT_TESTED
PRIZE_VALUE_EFFICIENCY: NOT_TESTED
COST / ECONOMIC_EFFICIENCY CLAIMS: NONE
T539 / P638:            NOT_RUN
PRODUCTION / COHORT / PROSPECTIVE: NONE
```

## 8. No-rescue commitment

If classification is `MATCHES_RANDOM_COVERAGE` or `UNDERPERFORMS_RANDOM_COVERAGE`:
record it and stop. No new base set, no offset, no different Sidon
construction, no different event threshold for this `matrix_variant_id`. A
different geometry is a new variant, preregistered before touching the
winning-space enumeration, exactly as this document was.

## 9. Preregistration hash

Computed over the canonical JSON of every locked parameter above (pool
size, draw size, the exact base set, the exposure ladder, the primary and
secondary event thresholds) by `tools/hash_preregistration.py`, recorded
in `diversification-coverage-b649-v1-preregistration-hash.json`. The
execution script re-verifies this hash before running and refuses to
proceed on a mismatch.
