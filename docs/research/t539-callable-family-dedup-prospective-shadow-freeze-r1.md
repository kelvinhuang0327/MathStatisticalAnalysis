# T539 callable-family-dedup prospective shadow freeze R1

> Preregistration/freeze only. This artifact evaluates no post-freeze outcome and establishes neither predictive advantage nor profitability.

## Frozen source and boundary

- Pilot commit: `0a4355cfcd13b26451e6d6c74bc873ca2b12fcdd`
- Pilot tree: `34c1896bb2a3797ffb57b2bff44f9ddd8bff628e`
- Pilot result SHA-256: `1a4fbd067f3d9b4735a4a1143b3694222f38f05eb3ec91e4e8b782e0e90c5c86`
- Pilot result bytes: `532005`
- Freeze boundary: `115000186`
- Future admissibility: `target_identity > 115000186`
- Immutable rule fingerprint: `eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446`
- JSON artifact SHA-256: `f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8` (78949 bytes)

The pilot JSON's embedded `source_authorities` manifest is the sole supporting research locator. The boundary is the maximum non-null historical `last_target` actually evaluated by that sealed pilot.

## Frozen experiment surface

- Lottery: `T539`
- Native ticket counts: `1`, `2`, `3`, `4`, `5`, `7`, `10`, `11`, `12`, `25`
- Windows: `W50`, `W300`, `W750` (no preferred or weighted window)
- Original candidates across cells: `62`
- Callable representatives across cells: `26`
- Removed sibling identities across cells: `36`

| Cell | K | Original | Callable | Removed | Windows |
|---|---:|---:|---:|---:|---|
| `T539:K1` | 1 | 25 | 12 | 13 | W50, W300, W750 |
| `T539:K2` | 2 | 13 | 3 | 10 | W50, W300, W750 |
| `T539:K3` | 3 | 13 | 3 | 10 | W50, W300, W750 |
| `T539:K4` | 4 | 1 | 1 | 0 | W50, W300, W750 |
| `T539:K5` | 5 | 3 | 2 | 1 | W50, W300, W750 |
| `T539:K7` | 7 | 3 | 1 | 2 | W50, W300, W750 |
| `T539:K10` | 10 | 1 | 1 | 0 | W50, W300, W750 |
| `T539:K11` | 11 | 1 | 1 | 0 | W50, W300, W750 |
| `T539:K12` | 12 | 1 | 1 | 0 | W50, W300, W750 |
| `T539:K25` | 25 | 1 | 1 | 0 | W50, W300, W750 |

## Frozen selector and comparators

The selector uses exactly the immediately preceding window targets, all strictly before the target. The frozen tie-break is:

1. `OFFICIAL_ANY_PRIZE_TARGET_RATE_DESC`
1. `OFFICIAL_PRIZE_TIER_COUNT_VECTOR_DESC`
1. `OFFICIAL_WINNING_TICKET_RATE_DESC`
1. `STRATEGY_ID_ASC`

The future contract contains exactly three arms:

1. `ORIGINAL_ROLLING` — causal rolling selection over each cell's complete original candidate universe.
2. `CALLABLE_FAMILY_DEDUP_ROLLING` — the same selector over the frozen callable representatives.
3. `CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE` — the exact per-cell/window baseline identity sealed below.

Both dedup arms reference the identical per-cell `callable_reduced_universe_sha256`.

### Fixed dedup baseline identities

| Cell | Window | Complete identity |
|---|---|---|
| `T539:K1` | `W50` | `T539_HISTORICAL_SQLITE / T539 / 539_3bet_orthogonal / v0.1-p36` |
| `T539:K1` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_attention_replay_1bet / v0.1-t539-cross-lottery-r2` |
| `T539:K1` | `W750` | `T539_HISTORICAL_SQLITE / T539 / 539_3bet_orthogonal / v0.1-p36` |
| `T539:K2` | `W50` | `T539_HISTORICAL_SQLITE / T539 / midfreq_acb_2bet / v0.1` |
| `T539:K2` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_deviation_2bet / v0.1-t539-cross-lottery-r2` |
| `T539:K2` | `W750` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_deviation_2bet / v0.1-t539-cross-lottery-r2` |
| `T539:K3` | `W50` | `T539_HISTORICAL_SQLITE / T539 / acb_markov_midfreq_3bet / v0.1` |
| `T539:K3` | `W300` | `T539_HISTORICAL_SQLITE / T539 / daily539_f4cold_3bet / v0.1` |
| `T539:K3` | `W750` | `T539_HISTORICAL_SQLITE / T539 / daily539_f4cold_3bet / v0.1` |
| `T539:K4` | `W50` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_tme_optimizer_4bet / v0.1-t539-cross-lottery-r2` |
| `T539:K4` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_tme_optimizer_4bet / v0.1-t539-cross-lottery-r2` |
| `T539:K4` | `W750` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_tme_optimizer_4bet / v0.1-t539-cross-lottery-r2` |
| `T539:K5` | `W50` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_five_me_5bet / v0.1-t539-cross-lottery-r2` |
| `T539:K5` | `W300` | `T539_HISTORICAL_SQLITE / T539 / daily539_f4cold_5bet / v0.1` |
| `T539:K5` | `W750` | `T539_HISTORICAL_SQLITE / T539 / daily539_f4cold_5bet / v0.1` |
| `T539:K7` | `W50` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_elite_7bet / v0.1-t539-cross-lottery-r2` |
| `T539:K7` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_elite_7bet / v0.1-t539-cross-lottery-r2` |
| `T539:K7` | `W750` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_elite_7bet / v0.1-t539-cross-lottery-r2` |
| `T539:K10` | `W50` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_backtest_10bet / v0.1-t539-cross-lottery-r2` |
| `T539:K10` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_backtest_10bet / v0.1-t539-cross-lottery-r2` |
| `T539:K10` | `W750` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_backtest_10bet / v0.1-t539-cross-lottery-r2` |
| `T539:K11` | `W50` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_variant_history_11bet / v0.1-t539-cross-lottery-r2` |
| `T539:K11` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_variant_history_11bet / v0.1-t539-cross-lottery-r2` |
| `T539:K11` | `W750` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_variant_history_11bet / v0.1-t539-cross-lottery-r2` |
| `T539:K12` | `W50` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_core_satellite_12bet / v0.1-t539-cross-lottery-r2` |
| `T539:K12` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_core_satellite_12bet / v0.1-t539-cross-lottery-r2` |
| `T539:K12` | `W750` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_core_satellite_12bet / v0.1-t539-cross-lottery-r2` |
| `T539:K25` | `W50` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_auto_optimizer_alpha_25bet / v0.1-t539-cross-lottery-r2` |
| `T539:K25` | `W300` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_auto_optimizer_alpha_25bet / v0.1-t539-cross-lottery-r2` |
| `T539:K25` | `W750` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_auto_optimizer_alpha_25bet / v0.1-t539-cross-lottery-r2` |

## Frozen callable representatives

Each representative is the lexicographically smallest complete identity ordered by `(source_authority_id, lottery_id, strategy_id, strategy_version)`. Historical performance is not an input to representative selection.

| Cell | Callable identity | Representative | Removed siblings |
|---|---|---|---|
| `T539:K1` | `callable-sha256:c6c6d25c5671a19d0b5f2b20e842db571af2340b46a9268291fe409590d50944` | `T539_HISTORICAL_SQLITE / T539 / acb_single_539 / v0.1-p36` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / acb_markov_midfreq / v0.1-p31a` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_cold_hunter_1bet / v0.1-t539-batch15` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_dms_1bet / v0.1-t539-batch15; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_gap_pressure_1bet / v0.1-t539-batch15; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_moderate_rank_1bet / v0.1-t539-batch15; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_pure_cold_1bet / v0.1-t539-batch15; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_rebound_aware_1bet / v0.1-t539-batch15; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_short_window_deviation_1bet / v0.1-t539-batch15; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_zone_momentum_1bet / v0.1-t539-batch15` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_attention_replay_1bet / v0.1-t539-cross-lottery-r2` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_dynamic_frequency_1bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_graph_predictor_1bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_hot_cooccurrence_1bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_hpsb_1bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_must_hit_top6_1bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_optimized_ensemble_1bet / v0.1-t539-cross-lottery-r2` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / p0b_539_3bet_f_cold_fmid / v0.1-p36` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0cFourierColdX2Adapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / p0c_539_3bet_f_cold_x2 / v0.1-p36` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / daily539_f4cold / v0.1` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Acb1BetAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / acb_1bet / v0.1-p31a` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Markov1BetAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / markov_1bet_539 / v0.1-p36` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / 539_3bet_orthogonal / v0.1-p36` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / daily539_markov_cold / v0.1` | `NONE` |
| `T539:K1` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet` | `T539_HISTORICAL_SQLITE / T539 / zone_gap_3bet_539 / v0.1-p36` | `NONE` |
| `T539:K2` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:Daily539BigLottoDmDmsAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_dm_dms_2bet / v0.1-t539-batch15` | `NONE` |
| `T539:K2` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_deviation_2bet / v0.1-t539-cross-lottery-r2` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_echo_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_enhanced_dual_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_gemini_v1_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_p0_echo_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_smart_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_two_bet_elite_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_two_bet_final_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_two_bet_optimizer_2bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_two_bet_optimizer_v2_2bet / v0.1-t539-cross-lottery-r2` |
| `T539:K2` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / midfreq_acb_2bet / v0.1` | `T539_HISTORICAL_SQLITE / T539 / midfreq_fourier_2bet / v0.1` |
| `T539:K3` | `callable-sha256:8d315f03ca35764733727ebad1d644ab144ed27061722c5b97d33038895351ad` | `T539_HISTORICAL_SQLITE / T539 / acb_markov_midfreq_3bet / v0.1` | `NONE` |
| `T539:K3` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_asm_3bet / v0.1-t539-cross-lottery-r2` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_cag_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_diversified_ensemble_v6_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_dms_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_exhaustive_audit_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_mwsc_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_random_core_satellite_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_random_zone_split_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_tme_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_zdp_3bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_zone_split_3bet / v0.1-t539-cross-lottery-r2` |
| `T539:K3` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / daily539_f4cold_3bet / v0.1` | `NONE` |
| `T539:K4` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_tme_optimizer_4bet / v0.1-t539-cross-lottery-r2` | `NONE` |
| `T539:K5` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_five_me_5bet / v0.1-t539-cross-lottery-r2` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_zone_balance_5bet / v0.1-t539-cross-lottery-r2` |
| `T539:K5` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / daily539_f4cold_5bet / v0.1` | `NONE` |
| `T539:K7` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_elite_7bet / v0.1-t539-cross-lottery-r2` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_gemini_phase2_7bet / v0.1-t539-cross-lottery-r2; T539_HISTORICAL_SQLITE / T539 / t539_biglotto_high_prize_trend_7bet / v0.1-t539-cross-lottery-r2` |
| `T539:K10` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_backtest_10bet / v0.1-t539-cross-lottery-r2` | `NONE` |
| `T539:K11` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_variant_history_11bet / v0.1-t539-cross-lottery-r2` | `NONE` |
| `T539:K12` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_core_satellite_12bet / v0.1-t539-cross-lottery-r2` | `NONE` |
| `T539:K25` | `selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `T539_HISTORICAL_SQLITE / T539 / t539_biglotto_auto_optimizer_alpha_25bet / v0.1-t539-cross-lottery-r2` | `NONE` |

## Prospective boundary and status contract

A target is eligible only when `target_identity > FREEZE_BOUNDARY`, where `FREEZE_BOUNDARY = 115000186`. A target at or before the boundary is ineligible. Prediction input must report outcome presence as `ABSENT`, and its causal history must end strictly before the target.

The existing observer vocabulary is reused: prediction entries are `AVAILABLE` or `UNAVAILABLE`; score entries are `SCORED` or `UNAVAILABLE_PREDICTION`; score sync can also return `OUTCOME_UNAVAILABLE`. No shared prospective runtime change is required.

## Freeze integrity

```text
FUTURE_OUTCOME_ACCESS = NO
PROSPECTIVE_OBSERVATIONS = 0
HISTORICAL_REPLAY = NOT RUN
STRATEGY_RERUN = NOT RUN
DB_ACCESS = NO
PREDICTIVE_ADVANTAGE = NOT ESTABLISHED
PROFITABILITY = NOT ESTABLISHED
```
