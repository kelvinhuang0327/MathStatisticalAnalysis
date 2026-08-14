# DIVERSIFICATION_COVERAGE_T539_V1 — result

Status: SEALED — OUTPERFORMS_RANDOM_EXPECTED_COVERAGE ｜ 2026-08-14 ｜ Strategy Matrix Phase 2

Replication of `DIVERSIFICATION_COVERAGE_B649_V1` into DAILY_539's native
5/39 structure. Preregistration (locked before any winning-space
enumeration): `diversification-coverage-t539-v1-preregistration.md`.
Hash: `dd926b0ea045cb57be4e1cd10bc16e3d524e3b6acae5b34a805ed01f437e334e`
(execution script re-verified this before running). Full result:
`diversification-coverage-t539-v1-result.json`. Attempt ledger:
`diversification-coverage-t539-v1-attempt-ledger.json`.

## Identity

```text
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
MATRIX_VARIANT_ID:     DIVERSIFICATION_COVERAGE_T539_V1
LOTTERY:               DAILY_539
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
REPLICATES:             DIVERSIFICATION_COVERAGE_B649_V1
```

## Method

`CYCLIC_SIDON_SHIFT_T539_V1`: base set `{0,1,3,7,12}` in Z_39, verified
Sidon (all 20 pairwise differences distinct), cyclic shifts guaranteed
pairwise ticket overlap `<= 1` across all 39 possible shifts
(exhaustively checked, not asserted). Complete enumeration over all
`C(39,5) = 575,757` possible draws — confirmed in the result
(`total_draws_enumerated`). No real draw history, no simulation, no
Monte Carlo, exact `fractions.Fraction` arithmetic throughout — same
method as B649, no code changes needed to the shared
`exact_coverage_baseline` module beyond passing `(39, 5)` instead of
`(49, 6)`.

## Result

| k | Q_sidon (M3+) | Q_random_expected (M3+) | D_3(k) |
|---:|---:|---:|---:|
| 1 | 0.01004069 | 0.01004069 | +0.00000000 |
| 3 | 0.02993450 | 0.02982070 | +0.00011380 |
| 5 | 0.04957821 | 0.04920556 | +0.00037265 |
| 10 | 0.09771831 | 0.09599032 | +0.00172799 |
| 15 | 0.14498304 | 0.14047338 | +0.00450966 |
| 20 | 0.19206019 | 0.18276794 | **+0.00929225** |

`D_3(1) = 0` exactly, as the sanity check required. From there, `D_3(k)`
is positive and grows through the full tested ladder — the same
qualitative shape as B649's own result.

**`MARGINAL_GEOMETRY_DELTA` is increasing, not diminishing**, across the
tested range (`k=3`: `5.69e-5`; `k=20`: `9.57e-4` per additional ticket)
— `GEOMETRY_ADVANTAGE_ZERO_CROSSING: NONE`, matching B649's own finding
that the advantage widens rather than closes across `k in {1,...,20}`.

`Q_sidon(M4+)` was computed and is reported in the full result JSON as a
secondary descriptive value, confirmed correctly ordered
(`Q5 <= Q4 <= Q3` for every `k`) — did not, and by design could not,
affect the primary classification.

**`Q_sidon(M5+)` and `D_5(k)` are exactly zero for every `k`** — this is
expected, not a null result or a defect. For a 5-of-39 draw, `M5` (5 of
5 matches) is the degenerate exact-match case: only the single ticket
identical to the draw itself ever qualifies, so a portfolio of `k`
distinct tickets (fixed geometry or uniformly random) has exactly a
`k/575,757` chance of containing it either way. Geometry cannot help or
hurt an event where "matching" only ever means "is the literal winning
combination." B649's own M5 threshold (5-of-6) is not this degenerate
case, which is why B649's `D_5(k)` is small but nonzero.

## Independent post-execution verification (beyond the built-in sanity check)

1. `total_draws_enumerated == C(39,5) == 575,757` exactly.
2. `Q_sidon(1)` for `M3+` equals `1927/191919` exactly, which reduces
   from (and was independently cross-checked against) the closed-form
   `K(3)/N = 5781/575757` — the same fraction, confirmed by exact
   integer arithmetic, not floating-point proximity.
3. `Q_sidon(M3+)` monotonically non-decreasing in `k` (required — a
   nested portfolio can only ever gain coverage).
4. `Q_sidon(M5+) <= Q_sidon(M4+) <= Q_sidon(M3+)` for every `k` (required
   — a stricter hit threshold can never qualify more draws than a looser
   one).

All four are additionally covered by an executable regression test
(`tests/unit/test_diversification_coverage_t539_v1.py`), re-running the
locked experiment rather than trusting this file's numbers.

## Classification

```text
descriptive_classification:        OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
geometry_advantage_zero_crossing:  NONE
```

## What this does and does not claim

Does claim: at every tested exposure level, this one disclosed,
deterministic low-overlap ticket geometry (independently derived for
Z_39, independently verified Sidon there) covers strictly more of the
`M3_PLUS` winning-space than a matched-random portfolio of the same
size, under DAILY_539's structure. Does not claim: predictive advantage
on real draws, prize-value/cost efficiency, that this geometry is
optimal among all possible geometries, that this generalizes past
`k=20`, or that the base set's numeric coincidence with B649's prefix is
anything more than an observed fact about two independent searches (see
the preregistration's final pre-lock wording correction, §3).

## Cross-lottery replication status

```text
B649:                                OUTPERFORMS_RANDOM_EXPECTED_COVERAGE (sealed)
T539:                                OUTPERFORMS_RANDOM_EXPECTED_COVERAGE (this cell)
CROSS_LOTTERY_REPLICATION_STATUS:    SUPPORTED_IN_2_LOTTERIES
P638_NATIVE_DESIGN_CANDIDATE:        YES
```

B649 and T539 are independent lottery-native replication cells, not
pooled into a single numerical estimate here, and this is not read as
proof of a universal cross-lottery mechanism from two directions alone
-- only as grounds to treat a P638-native design as a worthwhile next
candidate, not to execute it automatically.

## Scope boundary

```text
PREDICTIVE_ADVANTAGE:                NOT_TESTED
PRIZE_VALUE_ADVANTAGE:                NOT_TESTED
ECONOMIC_OPTIMALITY:                  NOT_TESTED
P638:                                 NOT_RUN
PRODUCTION / COHORT / PROSPECTIVE:    NONE
```

## No-rescue statement

The locked base set, exposure ladder, event thresholds, and
classification rule were not changed after this result was seen.
