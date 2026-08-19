# B649_TRACK_B_LAGGED_PHYSICAL_DRAW_ORDER_LEVEL1_R1

TASK_ID: `B649_TRACK_B_LAGGED_PHYSICAL_DRAW_ORDER_LEVEL1_R1`  
STATUS: **COMPLETE — NO_SIGNAL / DO_NOT_ADVANCE**  
TARGET_COUNT: **300**  
DEVELOPMENT_WINDOWS: **DEV_W1–DEV_W4**, chronological; common benchmark `113000006`–`115000069`  
COMMON_DEVELOPMENT_BENCHMARK: **YES**  
CLEAN_HELD_OUT_CONFIRMATION: **NO**

## Final fields

PHYSICAL_ORDER_SOURCE: `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result`, verified Track A `drawNumberAppear` source fixture  
SOURCE_DRAW_COUNT: **2161**  
JOINED_DRAW_COUNT: **2160/2161 exact period join; 2160/2160 date-aligned join** (reused Track A read-only local-snapshot evidence)  
ANALYSIS_SOURCE_ROWS_CONSUMED: **2161/2161**  
BASELINE_METHOD: **HORIZON_MINIMAX_2**, two fixed tickets from canonical set-only history  
BASELINE_M2_PLUS: **79/300 (0.2633)**  
REAL_ORDER_M2_PLUS: **91/300 (0.3033)**  
DELTA_VS_BASELINE: **0.0400**  
ORDER_SHUFFLED_PLACEBO_M2_PLUS: **98/300 (0.3267)**  
REAL_MINUS_ORDER_SHUFFLED: **-0.0233**  
STALE_ORDER_PLACEBO_M2_PLUS: **92/300 (0.3067)**  
REAL_MINUS_STALE: **-0.0033**  
SET_ONLY_CONTROL_M2_PLUS: **92/300 (0.3067)**  
ORDER_INCREMENTAL_DELTA: **-0.0033**  
M3_PLUS_RESULTS: **baseline 11/300 (0.0367); real 9/300 (0.0300); shuffled 12/300 (0.0400); stale 9/300 (0.0300)**  
POSITIVE_CHRONOLOGICAL_BLOCKS: **4/4**  
SEARCH_CONFIG_COUNT: **1**  
SEARCH_OVERFIT_RISK: **MODERATE CAVEAT — the final decision uses one initial locked configuration; a post-result threshold sensitivity was run and explicitly invalidated under the no-rescue rule**  
SIGNAL_CLASSIFICATION: **NO_SIGNAL**  
DECISION: **DO_NOT_ADVANCE**  
KEY_LESSONS: **Real order improves over the fixed baseline but loses to the
order-shuffled placebo and the set-only control; the observed lift is not
incremental physical-order information.**  
NEXT: **Close the physical-order line and return to D fallback EH27.**  
REPO_MUTATION: **task data only**  
DB_MUTATION: **NONE**

## Authority and source coverage

Track A's verified semantic authority classifies `drawNumberAppear` as
`PHYSICAL_DRAW_ORDER`, with a permutation invariant and no malformed or
duplicate rows. The retained official source fixture has `2161`
rows, six pages, `totalSize=2161` on each page, and zero missing order fields.
Its pagination method is the official `month`/`endMonth` query, not the
provider-shaped `startMonth` broad request.

PHYSICAL_ORDER_SEMANTIC_AUTHORITY: **PASS**  
HISTORICAL_SOURCE_COVERAGE: **PASS**  
PAGINATION_METHOD: **MONTH_ENDMONTH**  
SOURCE_ROWS_SHA256: `bb0141f88b9db71aa32e64b53a1bc0b77dd9d9b0018dde4f85c4b36bd5783fcd`

## Model and controls

All candidate tickets are created from `drawNumberSize[:6]`, sorted as
canonical number sets. `SET_ONLY_CONTROL` is a low-cardinality selector keyed
by the overlap of the two latest historical number sets. The primary real
model adds two locked order-derived buckets: the recent share of low numbers
in physical positions 1–3 (`POSITIONAL_RECENCY`) and the recent rate of
consecutive-number adjacency in physical neighbor positions
(`POSITIONAL_PAIR_ADJACENCY`). The selector is fit only on strictly earlier
records and falls back to the baseline until a key has `24`
earlier observations.

`ORDER_SHUFFLED_PLACEBO` deterministically permutes only the six main physical
positions within each historical draw. The exact six-number set and the
two-ticket exposure remain unchanged. `STALE_ORDER_PLACEBO` uses the same
order features after removing the latest `8` eligible historical
draws. Neither placebo changes the candidate generation or target scoring.

| Condition | M2+ | M2+ rate | M3+ | M3+ rate | Avg matched | Δ vs baseline |
|---|---:|---:|---:|---:|---:|---:|
| BASELINE_ONLY | 79/300 | 0.2633 | 11/300 | 0.0367 | 0.7100 | 0.0000 |
| SET_ONLY_CONTROL | 92/300 | 0.3067 | 8/300 | 0.0267 | 0.7183 | 0.0433 |
| BASELINE_PLUS_REAL_ORDER | 91/300 | 0.3033 | 9/300 | 0.0300 | 0.7200 | 0.0400 |
| ORDER_SHUFFLED_PLACEBO | 98/300 | 0.3267 | 12/300 | 0.0400 | 0.7467 | 0.0633 |
| STALE_ORDER_PLACEBO | 92/300 | 0.3067 | 9/300 | 0.0300 | 0.7267 | 0.0433 |

## Chronological blocks

| Block | Targets | Baseline | Set-only | Real order | Shuffled order | Stale order |
|---|---:|---:|---:|---:|---:|---:|
| DEV_W1 | 75 | 0.3200 | 0.3467 | 0.3467 | 0.3867 | 0.3467 |
| DEV_W2 | 75 | 0.2267 | 0.2400 | 0.2667 | 0.2667 | 0.2933 |
| DEV_W3 | 75 | 0.2267 | 0.2533 | 0.2400 | 0.2533 | 0.2533 |
| DEV_W4 | 75 | 0.2800 | 0.3867 | 0.3600 | 0.4000 | 0.3333 |

Real order was positive in `4` blocks and non-negative in
`4` blocks. This is descriptive evidence
inside the exposed development benchmark, not prospective confirmation.

## Causal and reproducibility gates

NO_FUTURE_LEAKAGE: **PASS** — order and set keys read only rows strictly before
each target; target outcomes are read only after candidate prediction for
scoring.  
CURRENT_TARGET_ORDER_USED: **NO**  
SAME_NUMBER_SET_CONTROL: **PASS** — canonical candidate history and shuffled
placebo retain identical six-number sets.  
ORDER_SHUFFLED_PLACEBO: **PASS** — deterministic within-draw six-position
permutation completed for all `2161` source rows.  
EQUAL_EXPOSURE: **PASS** — every condition scores exactly two tickets for each
of `300` targets.  
REPRODUCTION: **PASS** — the script reads the task-owned source copy and
regenerates all CSV/Markdown artifacts offline.  

Selector diagnostics:

- `SET_ONLY_CONTROL`: fallbacks `96`, selected `{'HORIZON_MINIMAX_2': 1103, 'ZONE_SPLIT_2_OF_3': 800, 'DEVIATION_2': 48}`
- `BASELINE_PLUS_REAL_ORDER`: fallbacks `254`, selected `{'HORIZON_MINIMAX_2': 1071, 'ZONE_SPLIT_2_OF_3': 536, 'DEVIATION_2': 344}`
- `ORDER_SHUFFLED_PLACEBO`: fallbacks `255`, selected `{'HORIZON_MINIMAX_2': 1006, 'ZONE_SPLIT_2_OF_3': 852, 'DEVIATION_2': 93}`
- `STALE_ORDER_PLACEBO`: fallbacks `255`, selected `{'HORIZON_MINIMAX_2': 1033, 'ZONE_SPLIT_2_OF_3': 667, 'DEVIATION_2': 251}`

## Attempt ledger

- **Attempt 1 — initial locked configuration:** completed offline; baseline
  79 M2+, real order 91, shuffled placebo 98, stale placebo 92, set-only 92;
  result `NO_SIGNAL / DO_NOT_ADVANCE`.
- **Attempt 2 — identical reproduction:** completed offline with byte-identical
  artifacts.
- **Attempt 3 — superseded sensitivity:** changing the fixed adjacency bucket
  cutoffs from `<0.16/>0.24` to `<0.03/>0.06` after observing Attempt 1
  produced baseline 79, real order 103, shuffled 84, stale 94, and set-only
  92. This branch is **invalidated and not used** because the packet forbids
  rescuing a failed result by retuning on the exposed benchmark.
- **Attempt 4 — restored final configuration:** the initial `<0.16/>0.24`
  thresholds were restored and the final artifacts were regenerated; the
  final decision remains `NO_SIGNAL / DO_NOT_ADVANCE`.

No production database, schema, ingestion path, production strategy
registration, or Strategy Matrix was changed. The prescribed next step is
`D fallback EH27` because this is **DO_NOT_ADVANCE**.

## Artifacts

- `report.md`
- `results.csv`
- `config_ledger.csv`
- `placebo_results.csv`
- `order_feature_summary.csv`
- `source_snapshot.json`
- `reproduce_analysis.py`
