# B649 Official-Win Marginal-Coverage Selector R1

## Frozen comparison contract

- Selector: `B649_OFFICIAL_WIN_MARGINAL_COVERAGE_V1`; event: `OFFICIAL_ANY_PRIZE`; model: `BIG_LOTTO_UNIFORM_FAIR_DRAW`.
- Candidate input: `docs/research/b649-arm-d-vs-sealed-outcome-free-exact-probability-r1-input.json`.
- Candidate input SHA-256: `ef089c1cdbe4f856a57885206bcf496023140e4047eec661d3e7896da46a286e`.
- Each row's fixed K10 pool is its frozen K20 `MIN_OVERLAP` portfolio.
  The K10 baseline is nested in every pool.
- Candidate-pool archive SHA-256: `f03c68d64e9cdf46bf332f278d203a3e597eef27b810560f6acb16343b92c151`.
- K10 baseline archive SHA-256: `ac83b2559a05502926e7eaebaa5ce84aa8062017992be8c05d89ce925b004f82`.
- K10 selected archive SHA-256: `9bc8c75921430e0b116b90603d0a2eb6fcffa26493f119b816b1d795e451187b`.
- Rows 1761; pools 1761; N=20.
- Selection evidence: 65,536 uniform main-draw samples, seed `20260923`.
  The special ball is integrated analytically for each sampled main draw.
- Final evaluation: exhaustive exact enumeration of 13,983,816 main draws and 43 legal special balls per draw.
  This uses the existing official-prize evaluator.
- Selector Monte Carlo scores are not used as final probability estimates; final values are
  recomputed by exhaustive enumeration of the full model outcome space.

## K10 pre-outcome model comparison

| Metric | MIN_OVERLAP | Marginal coverage | Delta |
|---|---:|---:|---:|
| Mean OFFICIAL_ANY_PRIZE probability | 40898896109/151270928424 (0.27036851) | 3406755505/12605910702 (0.27025065) | -17830049/151270928424 (-0.00011787) |
| Relative change vs MIN_OVERLAP | — | — | -17830049/40898896109 (-0.0436%) |
| Material hurdle | — | — | at least 1/100 |
| READY_FOR_BRANCH2_OOS | — | — | **NO** |

The materiality rule was fixed before exact comparison: mean official-win probability must improve by at least 1% relative to the frozen K10 `MIN_OVERLAP` baseline.
This model result makes no claim about future wins, payout, profit, or edge.

## K20 disposition

`SKIPPED_FORCED_SELECTION`: each K20 pool contains exactly 20 tickets.
Selecting K20 forces all pool members, leaving no selection decision.

## Outcome and scope boundary

- No target numbers, scores, prizes, payouts, or outcomes were read.
- No outcome replay or OOS run occurred.
- No candidate-pool change, K increase, or `MIN_OVERLAP` modification occurred.
- No database or production mutation, push, PR, or governance expansion occurred.

Study ID: `B649_OFFICIAL_WIN_MARGINAL_COVERAGE_PREOUTCOME_R1`.
Baseline exact-result SHA-256: `4cb38b0257b917d9dcd330049848e6406cf73f9c2a5c2702b439a0c08fea4c21`.
Official evaluator SHA-256: `92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66`.
Branch2 authority commit: `d7665ee5d00fac09fdc593908e81e54ae080f2ba`.
Branch2 authority tree: `5a9cbff94817c82163c32f1274f7c73d19bc8426`.
