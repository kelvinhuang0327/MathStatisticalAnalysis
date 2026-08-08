# BIGLOTTO68 → T539/P638 cross-lottery closure R1

This document records the target-native closure for the nine Batch-15
identities added when the frozen BIG_LOTTO catalog grew from 59 to 68 rows.
The donor implementations remain BIG_LOTTO-specific; only their pure
number-selection control flow is generalized.

## Target contracts

| Target | First-zone contract | Second zone |
|---|---|---|
| DAILY_539 | 1..39, five unique numbers | none |
| POWER_LOTTO | 1..38, six unique numbers | composed only by the existing P638 second-zone SSOT |

Both adapter families require causal, oldest-first history and have
`min_history = 1`. They do not read a database, filesystem, clock, network,
or shared application/infrastructure layer while producing a ticket.

## Closed identities

| Donor identity | T539 identity | P638 identity | Native tickets |
|---|---|---|---:|
| `legacy_biglotto__cold_hunter_predict__9e89f2b41add` | `t539_biglotto_cold_hunter_1bet` | `power_biglotto_cold_hunter_1bet` | 1 |
| `legacy_biglotto__short_window_deviation_predict__9e89f2b41add` | `t539_biglotto_short_window_deviation_1bet` | `power_biglotto_short_window_deviation_1bet` | 1 |
| `legacy_biglotto__rebound_aware_predict__9e89f2b41add` | `t539_biglotto_rebound_aware_1bet` | `power_biglotto_rebound_aware_1bet` | 1 |
| `legacy_biglotto__zone_momentum_predict__9e89f2b41add` | `t539_biglotto_zone_momentum_1bet` | `power_biglotto_zone_momentum_1bet` | 1 |
| `legacy_biglotto__pure_cold_predict__9e89f2b41add` | `t539_biglotto_pure_cold_1bet` | `power_biglotto_pure_cold_1bet` | 1 |
| `legacy_biglotto__moderate_rank_predict__9e89f2b41add` | `t539_biglotto_moderate_rank_1bet` | `power_biglotto_moderate_rank_1bet` | 1 |
| `legacy_biglotto__gap_pressure_scorer__5e862ef27ee6` | `t539_biglotto_gap_pressure_1bet` | `power_biglotto_gap_pressure_1bet` | 1 |
| `legacy_biglotto__test_dm_dms_biglotto__bad71858012d` | `t539_biglotto_dm_dms_2bet` | `power_biglotto_dm_dms_2bet` | 2 |
| `legacy_biglotto__test_dms_biglotto__10e39919c3a1` | `t539_biglotto_dms_1bet` | `power_biglotto_dms_1bet` | 1 |

The cumulative T539 run is registered as
`BIGLOTTO68_TO_T539_CROSS_LOTTERY_CLOSURE_R1` under
`biglotto68-to-t539-cross-lottery`; it appends these nine specs to the 15
previous T539 identities. The P638 current-universe registry appends Wave 6
to Waves 1–5, producing 70 executable strategy specs.

## Closure policy

The donor's short native outputs remain explicit. P638 Wave 6 permits a
zero-ticket zone-momentum closure and zero- or one-ticket DM-DMS closure via
`P638StrategySpec.source_native_closure_ticket_counts`; no padding is added.
The T539 adapters raise `SourceNativePortfolioClosure` when a producer cannot
emit its advertised native count, so the task runner records a typed failure
instead of converting it into an invented ticket.

The shared core is parity-tested against the frozen BIG_LOTTO Batch-15
producers at their native 1..49/6 contract, then exercised under both target
GameSpecs. P638 second-zone assertions use the existing `second_zone_predict`
implementation and no second-zone logic is duplicated in Wave 6.

## Verification boundary

The implementation is local and deterministic. It does not fetch official
draw data or write a production database. The resumable T539 runner and the
P638 current-ranking integration are wired and covered by focused fixture
tests; an official-source backtest remains a separate, explicitly invoked
runtime operation.
