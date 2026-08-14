# REGIME_CHANGE_POINT_CUSUM_B649_V1 — result

Status: SEALED — NO_EVIDENCE_OF_REGIME_CHANGE ｜ 2026-08-14 ｜ Strategy Matrix Phase 1

Preregistration (locked before any data was loaded):
`docs/research/regime-changepoint-cusum-b649-v1-preregistration.md`.
Preregistration hash: `6cf305db6fe5ae37743d8ddf5b2018f533005f1b7d18dc9d0e45ebd07e6d7d26`
(recorded in `regime-changepoint-cusum-b649-v1-preregistration-hash.json`;
the execution script re-verifies this hash before running and refuses to
proceed if it doesn't match). Full machine-readable result:
`regime-changepoint-cusum-b649-v1-result.json`. Attempt ledger:
`regime-changepoint-cusum-b649-v1-attempt-ledger.json`.

## Identity

```text
HYPOTHESIS_FAMILY_ID:      REGIME_CHANGE_POINT
MATRIX_VARIANT_ID:         REGIME_CHANGE_POINT_CUSUM_B649_V1
SOURCE_TYPE:                STRATEGY_MATRIX_NATIVE
RELATED_LEGACY_EVIDENCE:   H07_H19_CHANGE_POINT__BIG_LOTTO (REPORTED_UNVERIFIED, untouched by this result)
```

## Data provenance

Same Phase -1-verified BIG_LOTTO baseline: 2,138 contamination-excluded
draws (150 `DATE_LIKE` rows excluded, reused verbatim, not recomputed),
2007-03-09 to 2026-07-31. Read-only throughout.

## Primary result

| | |
|---|---|
| Statistic | global trimmed max-\|CUSUM\| of per-draw sum-of-six |
| Observed value | 964.0 |
| Argmax split point | draw #386 (chronological index) |
| Null distribution (100 sims) | min 689.0, median 1685.0, max 4886.0 |
| Percentile | **0.10** (real value below 90% of null replicates) |
| Classification | `NO_EVIDENCE_OF_REGIME_CHANGE` |

The observed statistic falls *below* the null median, not above it — the
opposite of what a regime break would produce (a break makes the CUSUM
path swing further from zero, i.e. a *larger* statistic and a *high*
percentile; this experiment's own preregistration §5 said so explicitly,
before any data existed, precisely to keep this direction from being
picked after the fact). B649's sum-of-six sequence is, if anything, more
stable than a typical draw from its own exact-null model — not less.

## Secondary: per-number CUSUM family (diagnostic, not primary)

49 tests, Holm-corrected. Holm-min adjusted p = **0.485**. Two individual
numbers (6 and 8) had raw empirical p-values at the simulation floor
(0.0099 — the smallest value 100 null replicates can produce), which might
look striking in isolation, but 49 independent tests are *expected* to
throw up roughly 49 × 0.0099 ≈ 0.49 such extreme values by chance alone —
matching the reported Holm-min almost exactly. This is Holm correction
doing its job: catching a would-be "the raw number looks extreme" reading
that the multiple-comparison structure of the test already predicts.

## Chronological stability (descriptive)

4 equal contiguous blocks, Holm-corrected. Every block's mean sum-of-six
is close to the exact null (149.1 to 150.8 against an expected 150.0),
Holm-min p = 1.0 (fully non-significant). No sign of any change concentrated
in one part of the history.

## Causality / leakage audit

This is a retrospective stationarity test over the full fixed historical
sequence, not a forward-prediction claim — there is no held-out future to
leak into. The actual methodological risk this design controls is
post-hoc statistic/threshold selection; that risk is closed by the
preregistration hash above, verified by the execution script before it
loaded a single draw.

## Classification and next step

```text
descriptive_classification: NO_EVIDENCE_OF_REGIME_CHANGE
decision_state:              DO_NOT_ADVANCE
replication_candidate:       NO
```

Per the Owner's scope: T539 not run, P638 not run, cross-lottery
replication not run, no production/cohort/prospective action taken. This
result seals `REGIME_CHANGE_POINT_CUSUM_B649_V1` and returns to Matrix
selection — it does not, by itself, change `REGIME_CHANGE_POINT`'s status
in any other lottery, and it does not touch legacy `H07_H19`'s own
(separately unverified) grade.

## No-rescue statement

The locked statistic (global trimmed max-\|CUSUM\|), trim fraction (15%),
simulation count (100), and classification thresholds (95th/75th
percentile) were not changed after this result was seen. The one
resolution made before data was touched — separating this experiment's
identity from legacy H07/H19, and fixing the primary/secondary endpoint
precedence — is disclosed in the preregistration document itself, not
here after the fact.
