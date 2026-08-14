# DIVERSIFICATION_COVERAGE_P638_ZONE1_V1 — result

Status: SEALED — OUTPERFORMS_RANDOM_EXPECTED_COVERAGE ｜ 2026-08-14 ｜ Strategy Matrix Phase 3

Replication of `DIVERSIFICATION_COVERAGE_B649_V1` and
`DIVERSIFICATION_COVERAGE_T539_V1` into POWER_LOTTO Zone-1's native 6/38
structure. Preregistration (locked before any winning-space enumeration):
`diversification-coverage-p638-zone1-v1-preregistration.md`. Hash:
`53e18558d07821460772a49f8358da3f2290b888dbde21c4497a0525c73cc992`
(execution script re-verified this before running). Full result:
`diversification-coverage-p638-zone1-v1-result.json`. Attempt ledger:
`diversification-coverage-p638-zone1-v1-attempt-ledger.json`.

## Identity

```text
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
MATRIX_VARIANT_ID:     DIVERSIFICATION_COVERAGE_P638_ZONE1_V1
LOTTERY:               POWER_LOTTO
ZONE:                  zone1 (Zone-2 1-of-8 out of scope)
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
REPLICATES:             DIVERSIFICATION_COVERAGE_B649_V1, DIVERSIFICATION_COVERAGE_T539_V1
```

## Method

`CYCLIC_SIDON_SHIFT_P638_ZONE1_V1`: base set `{0,1,3,7,17,30}` in `Z_38`,
verified Sidon (all 30 pairwise differences distinct, no pair differing by
the self-paired half-modulus distance 19), cyclic shifts guaranteed
pairwise ticket overlap `<= 1` across all 38 possible shifts (exhaustively
checked, not asserted — measured maximum: exactly 1). Complete enumeration
over all `C(38,6) = 2,760,681` possible draws — confirmed in the result
(`total_draws_enumerated`). No real draw history, no simulation, no Monte
Carlo, exact `fractions.Fraction` arithmetic throughout — same method as
B649/T539, no code changes to the shared `exact_coverage_baseline` module
beyond passing `(38, 6)` instead of `(49, 6)` or `(39, 5)`.

Unlike B649 (mod 49) and T539 (mod 39), POWER_LOTTO Zone-1's pool size (38)
is even, and the plain greedy constructor search that both prior
replications used unmodified provably cannot resolve it (`19 = 38/2` is
self-inverse). The base set above was found by a backtracking completion
of the identical criterion, not a different or weaker one — see the
preregistration §3 and the design task's own module docstring for the full
argument, independently re-verified by the search functions themselves.

## Result

| k | Q_sidon (M3+) | Q_random_expected (M3+) | D_3(k) |
|---:|---:|---:|---:|
| 1 | 0.03869806 | 0.03869806 | +0.00000000 |
| 3 | 0.11285730 | 0.11165955 | +0.00119775 |
| 5 | 0.18280852 | 0.17908342 | +0.00372510 |
| 10 | 0.34421978 | 0.32609621 | +0.01812357 |
| 15 | 0.48421748 | 0.44678160 | +0.03743588 |
| 20 | 0.60548430 | 0.54585434 | **+0.05962996** |

`D_3(1) = 0` exactly, as the sanity check required. From there, `D_3(k)`
is positive and grows through the full tested ladder — the same
qualitative shape as B649's and T539's own results, and **the largest
`D_3(20)` of the three sealed native cells** (B649: `+0.01329487`; T539:
`+0.00929225`; P638 Zone-1: `+0.05962996`) — disclosed as a descriptive
observation about this one exposure ladder, not a claim that P638's
geometry is "better" in any general or economic sense; the three lotteries
have different pool/draw shapes and are not pooled into one estimate.

**`MARGINAL_GEOMETRY_DELTA` is increasing, not diminishing**, across the
tested range (`k=3`: `5.99e-4`; `k=20`: `4.44e-3` per additional ticket) —
`GEOMETRY_ADVANTAGE_ZERO_CROSSING: NONE`, matching B649's and T539's own
finding that the advantage widens rather than closes across `k in
{1,...,20}`.

`Q_sidon(M4+)` and `Q_sidon(M5+)` were computed and are reported in the
full result JSON as secondary descriptive values, confirmed correctly
ordered (`Q6 <= Q5 <= Q4 <= Q3` for every `k`) — did not, and by design
could not, affect the primary classification.

**`Q_sidon(M6)` and `D_6(k)` are exactly zero for every `k`** — this is
expected, not a null result or a defect, and is the same phenomenon T539
already documented for its own M5. For a 6-of-38 draw, `M6` (6 of 6
matches) is the degenerate exact-match case: only the single ticket
identical to the draw itself ever qualifies, so a portfolio of `k`
distinct tickets (fixed geometry or uniformly random) has exactly a
`k/2,760,681` chance of containing it either way. Geometry cannot help or
hurt an event where "matching" only ever means "is the literal winning
combination."

## Independent post-execution verification (beyond the built-in sanity check)

1. `total_draws_enumerated == C(38,6) == 2,760,681` exactly.
2. `Q_sidon(1)` for `M3+` equals `35611/920227` exactly, which reduces from
   (and was independently cross-checked against) the closed-form `K(3)/N =
   106833/2760681` — the same fraction, confirmed by exact integer
   arithmetic, not floating-point proximity.
3. `Q_sidon(M3+)` monotonically non-decreasing in `k` (required — a nested
   portfolio can only ever gain coverage).
4. `Q_sidon(M6+) <= Q_sidon(M5+) <= Q_sidon(M4+) <= Q_sidon(M3+)` for every
   `k` (required — a stricter hit threshold can never qualify more draws
   than a looser one).

All four are additionally covered by an executable regression test
(`tests/unit/test_diversification_coverage_p638_zone1_v1.py`), re-running
the locked experiment rather than trusting this file's numbers.

## Classification

```text
descriptive_classification:        OUTPERFORMS_RANDOM_EXPECTED_COVERAGE
geometry_advantage_zero_crossing:  NONE
```

## What this does and does not claim

Does claim: at every tested exposure level, this one disclosed,
deterministic low-overlap ticket geometry (independently derived for
`Z_38` via a backtracking completion of the same criterion used for B649
and T539, independently verified Sidon there) covers strictly more of the
`M3_PLUS` winning-space than a matched-random portfolio of the same size,
under POWER_LOTTO Zone-1's structure. Does not claim: predictive advantage
on real draws, prize-value/cost efficiency, that this geometry is optimal
among all possible geometries, that this generalizes past `k=20`, that
Zone-2 allocation behaves the same way, or that the larger `D_3(20)`
relative to B649/T539 means P638 is a "better" lottery to play in any
economic sense.

## Cross-lottery replication status

```text
B649:                                OUTPERFORMS_RANDOM_EXPECTED_COVERAGE (sealed)
T539:                                OUTPERFORMS_RANDOM_EXPECTED_COVERAGE (sealed)
P638 (Zone-1):                       OUTPERFORMS_RANDOM_EXPECTED_COVERAGE (this cell)
CROSS_LOTTERY_REPLICATION_STATUS:    SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES
```

All three are independent lottery-native replication cells, not pooled
into a single numerical estimate here. This repository has exactly three
lottery types (`BIG_LOTTO`, `DAILY_539`, `POWER_LOTTO`); this
single-zone/single-mechanism diversification claim has now been natively
tested, positively, in all three available structures. This is still not
read as proof of a universal predictive mechanism: the evidence type
remains `EXACT_COMBINATORIAL` portfolio-geometry coverage, not forecasting,
and Zone-2 allocation / full-ticket structure (a materially different
mechanism) remains completely untested.

## Scope boundary

```text
PREDICTIVE_ADVANTAGE:                NOT_TESTED
PRIZE_VALUE_ADVANTAGE:                NOT_TESTED
ECONOMIC_OPTIMALITY:                  NOT_TESTED
ZONE_2_ALLOCATION:                    NOT_TESTED
FULL_TICKET_DIVERSIFICATION:          NOT_TESTED
PRODUCTION / COHORT / PROSPECTIVE:    NONE
```

## No-rescue statement

The locked base set, exposure ladder, event thresholds, and classification
rule were not changed after this result was seen.
