# B649_ARM_D_VS_SEALED_OUTCOME_FREE_EXACT_PROBABILITY_R1 — Report

**Status**: COMPLETE — NO_MEAN_GEOMETRY_SUPERIORITY_ON_FROZEN_ARCHIVE | 2026-09-21

## 0. Executive Summary

This study evaluates the exact, outcome-free geometry probability of winning
`OFFICIAL_ANY_PRIZE` under the uniform fair-draw model
(`BIG_LOTTO_UNIFORM_FAIR_DRAW`, 601,304,088 finite outcomes) for:
- Frozen Branch2 ARM_D (MIN_OVERLAP) archive: 1,761 historical target portfolios;
- Sealed production portfolios (`B649_SEALED_GEOMETRY_PORTFOLIO` 1.0.0,
  commit `2560407`).

**Primary Metric (K10)**:
- Result Label: `NO_MEAN_GEOMETRY_SUPERIORITY_ON_FROZEN_ARCHIVE`
- Mean ARM_D Exact Probability: `40898896109/151270928424` (0.27036851)
- Sealed Production Exact Probability: `1095245/3734808` (0.29325336)
- Exact Delta (ARM_D - Sealed): `-1730906063/75635464212` (-2.28848475e-02)

**Secondary Descriptive Metric (K20)**:
- Result Description: `NO_MEAN_GEOMETRY_SUPERIORITY_AT_K20`
- Mean ARM_D Exact Probability: `74090350/190998647` (0.38791034)
- Sealed Production Exact Probability: `44615213/85900584` (0.51938195)
- Exact Delta (ARM_D - Sealed): `-6629277631/50423642808` (-1.31471613e-01)

**Note**: Per the frozen protocol, K20 is descriptive only and does not rescue K10.

## 1. Identity and Provenance

```text
TASK_ID:                         B649_ARM_D_VS_SEALED_OUTCOME_FREE_EXACT_PROBABILITY_R1
METHOD_VERSION:                  1.0.0
MODEL_IDENTITY:                  BIG_LOTTO_UNIFORM_FAIR_DRAW
TOTAL_OUTCOME_SPACE:             601,304,088
EVENT_DEFINITION:                OFFICIAL_ANY_PRIZE
EVALUATION_METHOD:               MAIN_DRAW_COLLAPSED_EXACT_SPECIAL_UNION
BRANCH2_UPSTREAM_COMMIT:         d7665ee5d00fac09fdc593908e81e54ae080f2ba
BRANCH2_UPSTREAM_TREE:           5a9cbff94817c82163c32f1274f7c73d19bc8426
BRANCH2_UPSTREAM_SHA256:         af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3
PRODUCTION_AUTHORITY_COMMIT:     2560407ec6267e0fcf3b7cfb5627c1a4f1158baf
EVALUATOR_CONTENT_SHA256:        92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66
```

## 2. Methodology & Scientific Safeguards

1. **Exact Finite-Outcome Enumeration**: Every probability is an exact integer fraction
   over the full outcome space (`C(49, 6) * 43 = 601,304,088`). Special ball union is
   collapsed analytically (`MAIN_DRAW_COLLAPSED_EXACT_SPECIAL_UNION`).
2. **Outcome-Free Boundary**: Zero historical winning numbers, hit scores, or payout
   amounts were provided to or consumed by the evaluator.
3. **Weighting Discipline**: All 1,761 historical rows receive equal weight (1/1761).
   Repeated portfolios and forced-selection draws are fully preserved.
4. **Production Oracle Reproduction**: The exact evaluator independently reproduced the
   production sealed baseline probabilities for K10 (`1095245/3734808`) and
   K20 (`44615213/85900584`).

## 3. Detailed Results

| Metric | K10 (Primary) | K20 (Secondary) |
|---|---|---|
| Archive Row Count | 1761 | 1761 |
| Unique Portfolios | 1761 | 1761 |
| Evaluation Cache Hits | 0 | 0 |
| Sum Successful Outcomes | 286,292,272,763 | 410,756,900,400 |
| Mean ARM_D Probability | 40898896109/151270928424 | 74090350/190998647 |
| Sealed Production Probability | 1095245/3734808 | 44615213/85900584 |
| Exact Delta (ARM_D - Sealed) | -1730906063/75635464212 | -6629277631/50423642808 |
| Decimal Delta | -2.28848475e-02 | -1.31471613e-01 |
| Row Outcomes SHA-256 | `16e86e4e70c1a7ed...` | `c5377683e70bc332...` |

## 4. Decision Gate Adjudication

- `Delta_10 > 0`: **False**
- Primary Gate Result: `NO_MEAN_GEOMETRY_SUPERIORITY_ON_FROZEN_ARCHIVE`
- `Delta_20 > 0`: **False**
- Secondary Description: `NO_MEAN_GEOMETRY_SUPERIORITY_AT_K20`

## 5. Claim Boundary & Non-Claims

**Permitted Statement**:
- The exact average OFFICIAL_ANY_PRIZE geometry probability of the 1,761 frozen ARM_D
  portfolios is compared to the current sealed production portfolio under
  BIG_LOTTO_UNIFORM_FAIR_DRAW.

**Strictly Forbidden & Unclaimed**:
- `CONFIRMATORY_OOS_SUCCESS`: Not claimed.
- `PREDICTIVE_EDGE`: Not claimed.
- `FUTURE_SUCCESS_RATE_IMPROVEMENT`: Not claimed.
- `EXPECTED_PAYOUT_ADVANTAGE`: Not claimed.
- `PROFIT`: Not claimed.
- `ROI`: Not claimed.
- `PRODUCTION_PROMOTION`: Not claimed.
- `PRODUCTION_ADOPTION`: Not claimed.

## 6. Verification and Reproducibility

To independently reproduce the evaluation:
```bash
PYTHONPATH=src python -m lottolab.research.b649_arm_d_vs_sealed_exact_probability
```
