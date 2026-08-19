# B649_TRACK_B_PREDRAW_JACKPOT_ROLLOVER_PREDICTION_LEVEL1_R1

TASK_ID: `B649_TRACK_B_PREDRAW_JACKPOT_ROLLOVER_PREDICTION_LEVEL1_R1`  
STATUS: **WEAK_SIGNAL**  
ACTION: **DO_NOT_ADVANCE**  
TARGET_COUNT: **300**  
DEVELOPMENT_WINDOWS: `DEV_W1`–`DEV_W4`, chronological; common benchmark `113000006`–`115000069`  
COMMON_DEVELOPMENT_BENCHMARK: **YES**  
CLEAN_HELD_OUT_CONFIRMATION: **NO**

## Question and authority

This Level-1 falsification asks whether jackpot/rollover information known
before a target draw provides repeatable incremental B649 prediction
information. The official source is the Taiwan Lottery `Lotto649Result`
endpoint already used by the repository's `TaiwanLotteryDrawProvider`:
`https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result`.

The offline raw snapshot contains `2161` official rows,
spanning `2007-01-02`–`2026-08-14`, with
reported `totalSize=2161` and row digest
`d0e0a0374052fdadac15267fa5a31ac92f94db12779a4c7fbdc5bb3088577b39`. The benchmark contains `300` targets
(`113000006`–`115000069`) across years
`{2024: 113, 2025: 118, 2026: 69}`.

`derive_pre_draw_jackpot_rollover(...)` reads only the immediately prior row.
When that prior draw has `winnerCount=0`, the source-semantic components used
for the entering amount are `prior.lastPrize + prior.prize`; after a prior
jackpot winner the amount is left missing and the state is
`NO_ROLLOVER_RESET`, not zero-filled. A validation-only cross-row diagnostic
matched `1738/1739` prior no-winner transitions; the
remaining exception(s) are retained in `config_ledger.csv` and were not
repaired with target-t fields. The saved `target_features.csv` retains the
prior winner/reset state, amount, and prior jackpot pool components.

Chain diagnostic exceptions: `114000067->114000068 expected=299539966 actual=302539966`

## Baseline and bounded model

`BASELINE_ONLY` is the existing operational
`HORIZON_MINIMAX_2` producer: Horizon Minimax Disagreement, exactly two
tickets per target. The rollover model selects among the same-budget,
already-landed candidate portfolios `HORIZON_MINIMAX_2, DEVIATION_2, ZONE_SPLIT_2_OF_3` using a
small causal regime lookup trained on prior-target M2+ outcomes. The primary
key is a causal state+amount bucket (`ROLLOVER`, `ROLLOVER_LOW`,
`ROLLOVER_HIGH`, or `NO_ROLLOVER_RESET`), with a minimum of
`24` earlier observations per regime. The state-only
version is a sensitivity check. This is six evaluated conditions and remains
well below the Level-1 configuration cap of 24.

Placebos use the identical candidate set, selector, metric, exposure, and
chronological fit path:

- `STALE_PLACEBO`: the state+amount pair from `8` eligible
  draws earlier;
- `SHUFFLED_PLACEBO`: a deterministic pair permutation preserving the exact
  feature marginal distribution;
- `ERA_CONTROL`: calendar-year regime only, testing whether a slow era label
  explains the result.

## Overall metrics

| Condition | M2+ | M2+ rate | M3+ | M3+ rate | Average matched numbers | Δ M2+ vs baseline |
|---|---:|---:|---:|---:|---:|---:|
| BASELINE_ONLY | 79/300 | 0.2633 | 11/300 | 0.0367 | 0.7100 | 0.0000 |
| BASELINE_PLUS_ROLLOVER | 94/300 | 0.3133 | 8/300 | 0.0267 | 0.7167 | 0.0500 |
| STATE_ONLY_SENSITIVITY | 98/300 | 0.3267 | 7/300 | 0.0233 | 0.7567 | 0.0633 |
| STALE_PLACEBO | 92/300 | 0.3067 | 9/300 | 0.0300 | 0.7400 | 0.0433 |
| SHUFFLED_PLACEBO | 92/300 | 0.3067 | 8/300 | 0.0267 | 0.7683 | 0.0433 |
| ERA_CONTROL | 104/300 | 0.3467 | 11/300 | 0.0367 | 0.7967 | 0.0833 |

All rows use `2` tickets per target and the same
`300` targets. Selected portfolio counts are retained in
`results.csv`; the primary selector counts were:

- `BASELINE_PLUS_ROLLOVER`: `{'ZONE_SPLIT_2_OF_3': 123, 'DEVIATION_2': 126, 'HORIZON_MINIMAX_2': 51}`
- `STATE_ONLY_SENSITIVITY`: `{'ZONE_SPLIT_2_OF_3': 55, 'HORIZON_MINIMAX_2': 68, 'DEVIATION_2': 177}`
- `STALE_PLACEBO`: `{'HORIZON_MINIMAX_2': 126, 'DEVIATION_2': 57, 'ZONE_SPLIT_2_OF_3': 117}`
- `SHUFFLED_PLACEBO`: `{'ZONE_SPLIT_2_OF_3': 63, 'HORIZON_MINIMAX_2': 22, 'DEVIATION_2': 215}`
- `ERA_CONTROL`: `{'HORIZON_MINIMAX_2': 67, 'DEVIATION_2': 232, 'ZONE_SPLIT_2_OF_3': 1}`

## Chronological consistency

| Window | Targets | Baseline M2+ rate | Real rollover M2+ rate | Δ |
|---|---:|---:|---:|---:|
| DEV_W1 | 75 | 0.3200 | 0.3867 | 0.0667 |
| DEV_W2 | 75 | 0.2267 | 0.3067 | 0.0800 |
| DEV_W3 | 75 | 0.2267 | 0.2533 | 0.0267 |
| DEV_W4 | 75 | 0.2800 | 0.3067 | 0.0267 |

The causal model had `4` positive and
`4` non-negative development
windows. This is descriptive chronological consistency inside the shared
development benchmark, not prospective confirmation.

## Decision

- Real rollover Δ M2+: `0.0500`;
  meaningful threshold required at least `3`
  additional M2+ targets and one percentage point.
- Beats stale placebo: **True**.
- Beats shuffled placebo: **True**.
- Survives the calendar-year era control: **False**.
- Chronological stability gate: **True**.

The Level-1 decision is **WEAK_SIGNAL**. The prescribed action
is **DO_NOT_ADVANCE**; no additional tuning is used to rescue this
benchmark.

## Causal and filesystem checks

NO_FUTURE_LEAKAGE: **PASS** — feature derivation reads only row `t-1` or
earlier, and selector fitting uses records strictly before the current target.  
CURRENT_TARGET_POSTDRAW_FIELDS_USED: **NO** — target jackpot/sales/winner and
prize fields are never read as predictor inputs; target numbers are used only
after prediction for scoring.  
TARGET_OUTCOME_USED_AS_INPUT: **NO**.  
EQUAL_EXPOSURE: **PASS** — every condition emits/scored exactly two tickets per
target.  
PLACEBO_TESTS: **PASS** — stale, shuffled, and era-control paths completed.  
REPRODUCTION: **PASS** — the analysis is offline after the saved snapshot and
is regenerated by this script.

No database, strategy matrix, or production strategy registration was changed.

Artifacts: `report.md`, `results.csv`, `placebo_results.csv`,
`config_ledger.csv`, `target_features.csv`, `official_metadata.json`, and
`reproduce_analysis.py`.
