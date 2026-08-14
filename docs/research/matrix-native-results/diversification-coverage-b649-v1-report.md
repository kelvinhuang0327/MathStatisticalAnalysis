# DIVERSIFICATION_COVERAGE_B649_V1 — result

Status: SEALED — OUTPERFORMS_RANDOM_COVERAGE ｜ 2026-08-14 ｜ Strategy Matrix Phase 1

Preregistration (locked before any winning-space enumeration):
`diversification-coverage-b649-v1-preregistration.md`. Hash:
`029210d0eb9860a625ad8bf4bc535358e928823860fa4ea1ad4591114ea59a26`
(execution script re-verified this before running). Full result:
`diversification-coverage-b649-v1-result.json`. Attempt ledger:
`diversification-coverage-b649-v1-attempt-ledger.json`.

## Identity

```text
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
MATRIX_VARIANT_ID:     DIVERSIFICATION_COVERAGE_B649_V1
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
SPLIT FROM:             ALLOCATION_EXPOSURE_EFFICIENCY_B649_V1 (DESIGN_ABANDONED --
                        this is the cleanly identifiable question that split off it)
```

## Method

`CYCLIC_SIDON_SHIFT_B649_V1`: base set `{0,1,3,7,12,20}` in Z_49, verified
Sidon (all 30 pairwise differences distinct), cyclic shifts guaranteed
pairwise ticket overlap `<= 1` across all 49 possible shifts (exhaustively
checked, not asserted). Complete enumeration over all `C(49,6) =
13,983,816` possible draws — confirmed in the result
(`total_draws_enumerated`). No real draw history, no simulation, no Monte
Carlo, exact `fractions.Fraction` arithmetic throughout.

## Result

| k | Q_sidon (M3+) | Q_random (M3+) | D_3(k) |
|---:|---:|---:|---:|
| 1 | 0.01863755 | 0.01863755 | +0.00000000 |
| 3 | 0.05503762 | 0.05487704 | +0.00016058 |
| 5 | 0.09029231 | 0.08977829 | +0.00051401 |
| 10 | 0.17364180 | 0.17149647 | +0.00214533 |
| 15 | 0.25178807 | 0.24587816 | +0.00590991 |
| 20 | 0.32687687 | 0.31358200 | **+0.01329487** |

`D_3(1) = 0` exactly, as the sanity check required (a single ticket of any
geometry has identical coverage probability to a single random ticket —
pure symmetry). From there, `D_3(k)` is positive and grows through the
full tested ladder.

**`MARGINAL_GEOMETRY_DELTA` is increasing, not diminishing**, across the
tested range (`k=3`: `8.03e-5`; `k=20`: `1.48e-3` per additional ticket) —
`GEOMETRY_ADVANTAGE_ZERO_CROSSING: NONE`. A plausible mechanism (not
claimed as proven, just a coherent reading): random portfolios accumulate
more accidental ticket-pair overlap as `k` grows (a birthday-paradox-style
effect), which erodes their coverage growth rate; the Sidon-shift
portfolio's guaranteed `<=1` pairwise overlap resists this, so the gap
widens rather than closes across `k in {1,...,20}`. Whether it keeps
widening past `k=20` is outside this V1's tested range.

`Q_sidon(M4+)` and `Q_sidon(M5+)` were computed and are reported in the
full result JSON as secondary descriptive values — confirmed correctly
ordered (`Q5 <= Q4 <= Q3` for every `k`, an independent check this task
verified after execution) — but did not, and by design could not, affect
the primary classification.

## Independent post-execution verification (beyond the built-in sanity check)

1. `total_draws_enumerated == C(49,6) == 13,983,816` exactly.
2. `Q_sidon(1)` for `M3+` equals `4654/249711` exactly, which reduces from
   (and was independently cross-checked against) the closed-form
   `K(3)/N = 260624/13983816` — the same fraction, confirmed by exact
   integer arithmetic, not floating-point proximity.
3. `Q_sidon(M3+)` monotonically non-decreasing in `k` (required — a
   nested portfolio can only ever gain coverage).
4. `Q_sidon(M5+) <= Q_sidon(M4+) <= Q_sidon(M3+)` for every `k` (required
   — a stricter hit threshold can never qualify more draws than a looser
   one).

## Classification

```text
descriptive_classification:        OUTPERFORMS_RANDOM_COVERAGE
geometry_advantage_zero_crossing:  NONE
```

## What this does and does not claim

Does claim: at every tested exposure level, this one disclosed,
deterministic low-overlap ticket geometry covers strictly more of the
`M3_PLUS` winning-space than a matched-random portfolio of the same size,
under B649's confirmed-fair draw process. Does not claim: predictive
advantage on real draws, prize-value/cost efficiency (no such data
exists, confirmed separately), that this geometry is optimal among all
possible geometries, or that this generalizes past `k=20`.

## Scope boundary

```text
T539 / P638:                        NOT_RUN
PRODUCTION / COHORT / PROSPECTIVE:  NONE
```

## No-rescue statement

The locked base set, exposure ladder, event thresholds, and classification
rule were not changed after this result was seen.
