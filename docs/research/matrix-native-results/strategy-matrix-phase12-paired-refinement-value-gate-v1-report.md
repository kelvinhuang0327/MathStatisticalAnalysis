# Strategy Matrix Phase 12 paired refinement-value gate

## Result

`INCONCLUSIVE` under the existing repository contract.

The canonical strategy-success evaluator is descriptive and contains no
paired refinement-value decision rule. This report therefore applies no new
threshold. Observed effects are mixed: three cells are unchanged because the
seed and terminal portfolios are identical, three cells have a positive
full-history delta, and three have a negative full-history delta.

The machine-readable authority is
`strategy-matrix-phase12-paired-refinement-value-gate-v1-result.json`
(143,827 bytes; SHA-256
`30bdb799a22b600bbbcab3f33a0d7ecdc3458183ff1b9b8255ca0ac3c6e3db1d`).

## Frozen inputs and method

- Phase 10 B649 authority: SHA-256
  `099ca254ff9143c00953bde62329b2b8ae298a1f8e2bcfb757ca1c263119aa2c`.
- Phase 11 T539/P638 Zone-1 authority: SHA-256
  `c7904f716a61fb6b43df2091664ef55a1972b9212cac3490133d0accd4ae7290`.
- Dataset: `/Users/kelvin/Library/Application Support/LottoLab/lottolab.db`,
  schema v3, read-only, SHA-256
  `4c3fc2959201fbdfc2cd3a1535758196f95ba67fb546f41e6dd3fab227c57f13`
  before and after both executions.
- Partitions: B649 2,164 draws (`9f3143c6…6f51`), T539 202 draws
  (`e8f59eee…89de`), and P638 67 draws (`c177d2f7…15a9`).
- Replay: canonical `ReplayHistoricalPortfolioPredictions` composed with
  `BuildCausalHistory`; maximum history 1, minimum history 1; source order is
  draw date then numeric draw number. Each lottery's first draw is preserved
  as one typed `INSUFFICIENT_HISTORY` closure per portfolio member. Every
  other cutoff strictly precedes its target.
- Metric: existing `LEGAL_TICKET_PRIZE` diagnostic M3+ coverage. P638 uses
  `PowerLottoSuccessCriterion(minimum_zone1_hits=3,
  zone2_requirement=NOT_USED)`; Zone-2 was not scored.
- Windows: unchanged `STRATEGY_SUCCESS_WINDOWS_V1` full/750/300/50 nested
  windows. T539 and P638 do not have enough eligible draws for the 750- or
  300-draw windows, so those deltas remain unavailable.

## Paired results

Each cell is `baseline successes/eligible → refined successes/eligible
(exact refined-minus-baseline rate)`. `INSUFFICIENT` is the canonical window
status, not an omitted result.

| Structure | k | Full history | 750 | 300 | 50 |
|---|---:|---|---|---|---|
| B649 | 10 | 398/2163 → 398/2163 (0/1) | 141/750 → 141/750 (0/1) | 57/300 → 57/300 (0/1) | 12/50 → 12/50 (0/1) |
| B649 | 15 | 579/2163 → 577/2163 (-2/2163) | 204/750 → 182/750 (-11/375) | 84/300 → 78/300 (-1/50) | 20/50 → 16/50 (-2/25) |
| B649 | 20 | 766/2163 → 774/2163 (+8/2163) | 267/750 → 261/750 (-1/125) | 112/300 → 109/300 (-1/100) | 23/50 → 22/50 (-1/50) |
| T539 | 10 | 23/201 → 23/201 (0/1) | INSUFFICIENT | INSUFFICIENT | 4/50 → 4/50 (0/1) |
| T539 | 15 | 30/201 → 33/201 (+1/67) | INSUFFICIENT | INSUFFICIENT | 6/50 → 8/50 (+1/25) |
| T539 | 20 | 37/201 → 37/201 (0/1) | INSUFFICIENT | INSUFFICIENT | 7/50 → 7/50 (0/1) |
| P638 Zone-1 | 10 | 22/66 → 24/66 (+1/33) | INSUFFICIENT | INSUFFICIENT | 17/50 → 19/50 (+1/25) |
| P638 Zone-1 | 15 | 33/66 → 32/66 (-1/66) | INSUFFICIENT | INSUFFICIENT | 26/50 → 25/50 (-1/50) |
| P638 Zone-1 | 20 | 42/66 → 34/66 (-4/33) | INSUFFICIENT | INSUFFICIENT | 33/50 → 29/50 (-2/25) |

The result artifact preserves all nine full baseline/refined SHA-256 identities,
all typed closures, exact target-set hashes, canonical summary objects, and
exact paired deltas.

## Determinism and boundary

Two fresh single-worker executions against the same frozen database produced
byte-identical normalized JSON: 143,827 bytes and SHA-256
`30bdb799a22b600bbbcab3f33a0d7ecdc3458183ff1b9b8255ca0ac3c6e3db1d`
both times. No timestamp or performance field is in the hashed payload.

Exactly one recommended next action: **STOP further refinement expansion**.
This is a bounded research recommendation, not a repository decision-rule
classification.

`REFERENCE_PROMOTION = NOT AUTHORIZED`

`RUNTIME_PROMOTION = NOT AUTHORIZED`

`DEPLOYMENT = NOT RUN`
