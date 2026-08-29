# B649 K2 fixed-universe failure taxonomy R1

## Outcome

B649 K2 has zero complete fixed-universe targets because `legacy_biglotto__quick_ml_predict__8b7ba0b52e2d` fails all 750 targets. A second strategy, `legacy_biglotto__backtest_radical_strategy__e54cc0812bc6`, fails intermittently on 29 of those same targets.

This is failure attribution only. No strategy was repaired or excluded, no replay was regenerated, and no database was accessed.

## Source identity and data quality

- Rolling-selector source: `abc367bd6d8b59d01ecc4d79e56c787bbc03cd20` / `bf430efd66b7ce1ac38ee04fb0052e8c55cc972c`
- Sealed replay source: `85d2b4578d437b66bd015c60dd1f9bdc8404e755` / `c6341c36ca210e02b08bac66ff98b7c8be1fc95a`
- Target evidence SHA-256: `f4ee7bcd2900c6c066b6aa0255031c97c1ca1a248c605ce68a46f62bfe7820f0`
- Authority directory: `/Users/kelvin/Library/Application Support/LottoLab/authorities/big_lotto/exact_native_k2_k3`
- Hash stability before/after load: `True`
- Rows: 28500 total; 14250 K2
- K2 universe: 19 strategies x 750 targets
- Duplicate strategy-target rows: 0
- Sealed ranking RECENT_750 cross-check: `PASS`

## Per-strategy failure matrix

| Strategy ID | Family | Evaluated | Complete | EXECUTION_FAILURE | Pattern | First failure | Last failure | Blockage share | Exclusive targets | Reason/category |
|---|---:|---:|---:|---:|---|---|---|---:|---:|---|
| `b649_new_horizon_minimax_disagreement_r1` | `biglotto_horizon_minimax` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__backtest_radical_strategy__e54cc0812bc6` | `biglotto_radical_gap` | 750 | 721 | 29 | INTERMITTENT | 111000108 | 115000065 | 29/750 | 0 | InvalidOutput: legacy_biglotto__backtest_radical_strategy__e54cc0812bc6: frozen donor emitted fewer than six legal candidates x 29 |
| `legacy_biglotto__backtest_strategy_1__41ed79a6de62` | `biglotto_wave10` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__biglotto_2bet_final__7eaedb330a07` | `biglotto_wave3` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__biglotto_2bet_hedging__07a3aa455074` | `biglotto_2bet_hedging` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876` | `biglotto_wave3` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3` | `biglotto_wave3` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__concentrated_pool_predictor__a03b90705749` | `biglotto_concentrated_pool` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__constraint_filter_predictor__3a85b3995002` | `biglotto_constraint_filter` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01` | `biglotto_wave10` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4` | `biglotto_minimal_dual_bet` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4` | `biglotto_orthogonal_2bet` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__power_fourier_rhythm__cb75e72e4c94` | `biglotto_power_fourier_rhythm` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a` | `biglotto_wave7` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511` | `biglotto_wave4` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa` | `biglotto_wave5` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__quick_ml_predict__8b7ba0b52e2d` | `biglotto_wave12` | 750 | 0 | 750 | PERSISTENT | 109000024 | 115000081 | 750/750 | 721 | Wave12FrozenSourceError: FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR x 750 |
| `legacy_biglotto__test_dm_dms_biglotto__bad71858012d` | `biglotto_batch15` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |
| `legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776` | `biglotto_wave6` | 750 | 750 | 0 | NO_FAILURE | — | — | 0/750 | 0 | — |

## Target-level blockage

- Union of failure targets: **750/750**
- Complete fixed-universe targets: **0**
- Targets with one failing strategy: **721**
- Targets with two failing strategies: **29**
- Exact per-target failing-strategy rows and the full 750-target union are in the JSON artifact.

### Dual-failure targets

`111000108`, `112000116`, `113000024`, `113000025`, `113000027`, `113000028`, `113000046`, `113000068`, `113000088`, `113000102`, `113000103`, `113000109`, `113000110`, `113000114`, `114000006`, `114000050`, `114000054`, `114000058`, `114000059`, `114000060`, `114000065`, `114000077`, `114000078`, `114000096`, `114000108`, `115000019`, `115000039`, `115000062`, `115000065`

## Intersection, isolation, and cover diagnostics

- `quick_ml_predict` failure set: 750 targets (persistent, one contiguous run).
- `backtest_radical_strategy` failure set: 29 targets (intermittent).
- Pairwise intersection: 29 targets; the radical failure set is a strict subset of the QuickML failure set.
- Minimum diagnostic failure cover cardinality: **1**.
- Minimum cover set(s): `[["legacy_biglotto__quick_ml_predict__8b7ba0b52e2d"]]`.
- A cover set is descriptive only and does not authorize strategy removal.

## Implementation-family concentration

The primary blockage is concentrated in `biglotto_wave12`: its QuickML strategy fails all 750 targets with `Wave12FrozenSourceError: FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR`. The separate `biglotto_radical_gap` family adds 29 overlapping `InvalidOutput` failures and no exclusive blocked targets.

## Wave26 authority lineage

- `legacy_biglotto__test_ces__78d17c530ab8`
- `legacy_biglotto__test_dms__b63442289bd5`
- `legacy_biglotto__test_greedy_optimizer__82df7f878ece`
- `legacy_biglotto__test_mwsc__ba37643d6a3b`

All four are K3-only in the sealed manifest. Their intersection with the K2 universe and K2 failure set is empty.

## Required questions

1. **YES_ONE_PERSISTENT_PRIMARY** — legacy_biglotto__quick_ml_predict__8b7ba0b52e2d fails all 750 targets.
2. **NO_NOT_PRIMARY_CAUSE** — 2 strategies fail at least once; 1 persistent strategy covers the full blockage.
3. **YES_PRIMARY_BLOCKAGE_CONCENTRATED** — biglotto_wave12 covers 750/750 blocked targets.
4. **NO** — The four sealed-manifest wave26 provenance IDs are K3-only; their K2 and K2-failure intersections are empty.
5. **YES** — RCA of legacy_biglotto__quick_ml_predict__8b7ba0b52e2d could restore 721/750 complete-universe targets if that failure alone were resolved.
6. **MULTIPLE_STRATEGY_CHANGES_REQUIRED_FOR_ALL_750** — All 2 failing strategy implementations must have their distinct failure rows resolved for full coverage.

## Recommended bounded next task

Run implementation RCA only for `legacy_biglotto__quick_ml_predict__8b7ba0b52e2d` in `biglotto_wave12`, focused on `Wave12FrozenSourceError: FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR`. If that persistent failure were resolved, 721/750 targets would become complete-universe comparable; full 750-target restoration would still require a separate RCA/remediation decision for the 29 radical-gap failures.

No repair is authorized or performed by this task.

## Explicit boundaries

B649_K2_REPAIR = NOT RUN

DB_ACCESS = NO

NEW_HISTORICAL_REPLAY = NOT RUN

CANONICAL_STRATEGY_EXCLUSION = NOT AUTHORIZED
