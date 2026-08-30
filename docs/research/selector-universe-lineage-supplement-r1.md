# Selector universe lineage supplement R1

Status: SEALED static deterministic supplement.

This artifact accounts for selector identities that are not exact joins to the production StrategyDescriptor catalog. It reads frozen selector JSON and exact source specifications with ASTs only; it does not run a selector, historical replay, database access, or strategy implementation.

## Frozen authority and census

- Selector commit/tree: `abc367bd6d8b59d01ecc4d79e56c787bbc03cd20` / `bf430efd66b7ce1ac38ee04fb0052e8c55cc972c`
- Selector result SHA-256: `04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157`
- Result bytes: `665339`
- Result SHA-256: `461afd3bd0b7eeca93546562330d03234ad57aa2aa4dff25d4432cc254795f37`
- P638 spec sources: `src/lottolab/strategies/adapters/powerlotto_wave1.py, src/lottolab/strategies/adapters/powerlotto_wave2.py, src/lottolab/strategies/adapters/powerlotto_wave3.py, src/lottolab/strategies/adapters/powerlotto_wave4.py, src/lottolab/strategies/adapters/powerlotto_wave5.py, src/lottolab/strategies/adapters/powerlotto_wave6.py`
- T539 replay-spec source: `tools/run_daily539_t539_wave1.py`
- T539 R2 portable spec source: `src/lottolab/strategies/adapters/daily539_biglotto_portable.py`

| Lottery | Qualified selected | Production exact joins | Supplement rows |
|---|---:|---:|---:|
| B649 | 15 | 15 | 0 |
| P638 | 65 | 9 | 56 |
| T539 | 55 | 1 | 54 |
| **Total** | **135** | **25** | **110** |

- Raw selector labels: **134**.
- The raw-label collision is `midfreq_fourier_2bet`; its P638 and T539 authority-qualified keys remain two separate identities.
- Safe production alias mapping: **NO**.
- Donor relation promoted to canonical identity: **NO**.

## T539 R2 source-pin correction

R2 portable definitions first appear at `c159da43ba79694d91c983f623d567560fe617a6`. `b2ce6a3daaef4925a8e3f15d93a883d173882714` (`b2ce6a3…`) is explicitly rejected as the T539 R2 implementation source. The canonical implementation tree is pinned to `0645f31a2bcaf494760d4bc1675bc1c3ed9a076d`.

## Supplement bindings

| Lottery | Strategy ID | Version | Implementation | Callable | Status |
|---|---|---|---|---|---|
| P638 | `cold_complement_2bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_cold_complement_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `fourier30_markov30_2bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_fourier30_markov30_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `fourier_rhythm_3bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_fourier_rhythm_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `lag_reversion_2bet` | `v0.1-p638-wave2` | `lottolab.strategies.adapters.powerlotto_wave2` | `lottolab.strategies.adapters.powerlotto_wave2:_lag_reversion_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `midfreq_fourier_2bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `midfreq_fourier_mk_3bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_mk_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_apriori_ext_4bet` | `v0.2-p638-wave2` | `lottolab.strategies.adapters.powerlotto_wave2` | `lottolab.strategies.adapters.powerlotto_wave2:_apriori_ext_4bet_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_asm_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_asm_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_attention_replay_1bet` | `v0.1-p638-wave3` | `lottolab.strategies.adapters.powerlotto_wave3` | `lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_auto_optimizer_alpha_25bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_auto_optimizer_25bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_backtest_10bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_backtest_10bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_cag_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_cag_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_cold_hunter_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_single_predictor` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_core_satellite_12bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_core_satellite_12bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_deviation_2bet` | `v0.1-p638-wave3` | `lottolab.strategies.adapters.powerlotto_wave3` | `lottolab.strategies.adapters.powerlotto_wave3:_deviation_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_diversified_ensemble_v6_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_diversified_ensemble_v6` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_dm_dms_2bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_dm_dms_predict` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_dms_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_dms_predict` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_dms_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_dms_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_dynamic_frequency_1bet` | `v0.1-p638-wave3` | `lottolab.strategies.adapters.powerlotto_wave3` | `lottolab.strategies.adapters.powerlotto_wave3:_dynamic_frequency_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_echo_2bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_echo_2bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_elite_7bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_elite_7bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_enhanced_dual_2bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_enhanced_dual_2bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_exhaustive_audit_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_exhaustive_audit_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_five_me_5bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_five_me_5bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_gap_pressure_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_single_predictor` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_gemini_phase2_7bet` | `v0.1-p638-wave3` | `lottolab.strategies.adapters.powerlotto_wave3` | `lottolab.strategies.adapters.powerlotto_wave3:_gemini_phase2_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_gemini_v1_2bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_gemini_v1_2bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_graph_predictor_1bet` | `v0.1-p638-wave3` | `lottolab.strategies.adapters.powerlotto_wave3` | `lottolab.strategies.adapters.powerlotto_wave3:_graph_predictor_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_moderate_rank_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_single_predictor` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_mwsc_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_mwsc_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_optimized_ensemble_1bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_optimized_ensemble` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_p0_echo_2bet` | `v0.1-p638-wave3` | `lottolab.strategies.adapters.powerlotto_wave3` | `lottolab.strategies.adapters.powerlotto_wave3:_p0_echo_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_pure_cold_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_single_predictor` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_random_core_satellite_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_random_core_satellite` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_random_zone_split_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_random_zone_split` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_rebound_aware_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_single_predictor` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_short_window_deviation_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_single_predictor` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_smart_2bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_smart_2bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_tme_3bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_tme_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_tme_optimizer_4bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_tme_optimizer` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_two_bet_elite_2bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_two_bet_elite` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_two_bet_final_2bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_two_bet_final` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_two_bet_optimizer_2bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_two_bet_optimizer_v2_2bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer_v2` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_variant_history_11bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_variant_history_11bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_zdp_3bet` | `v0.1-p638-wave5` | `lottolab.strategies.adapters.powerlotto_wave5` | `lottolab.strategies.adapters.powerlotto_wave5:_zdp_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_zone_balance_5bet` | `v0.1-p638-wave3` | `lottolab.strategies.adapters.powerlotto_wave3` | `lottolab.strategies.adapters.powerlotto_wave3:_zone_balance_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_zone_momentum_1bet` | `v0.1-p638-wave6` | `lottolab.strategies.adapters.powerlotto_wave6` | `lottolab.strategies.adapters.powerlotto_wave6:_single_predictor` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_biglotto_zone_split_3bet` | `v0.1-p638-wave4` | `lottolab.strategies.adapters.powerlotto_wave4` | `lottolab.strategies.adapters.powerlotto_wave4:_zone_split_3bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_fourier_gap_rebound_2bet` | `v0.1-p638-wave2` | `lottolab.strategies.adapters.powerlotto_wave2` | `lottolab.strategies.adapters.powerlotto_wave2:_fourier_gap_rebound_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_fourier_rhythm_2bet` | `v0.1-p638-all10` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_power_fourier_rhythm_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_momentum_2bet` | `v0.1-p638-wave2` | `lottolab.strategies.adapters.powerlotto_wave2` | `lottolab.strategies.adapters.powerlotto_wave2:_momentum_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_orthogonal_5bet` | `v0.1-p638-all10` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_power_orthogonal_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_precision_3bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_power_precision_tickets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `pp3_freqort_4bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_wave1` | `lottolab.strategies.adapters.powerlotto_wave1:_pp3_freqort_tickets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `539_3bet_orthogonal` | `v0.1-p36` | `lottolab.strategies.adapters.daily539_single_legacy` | `lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `acb_markov_midfreq` | `v0.1-p31a` | `lottolab.strategies.adapters.daily539_acb_markov_midfreq` | `lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `daily539_f4cold` | `v0.1` | `lottolab.strategies.adapters.daily539_portfolio_f4cold` | `lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `daily539_f4cold_3bet` | `v0.1` | `lottolab.strategies.adapters.daily539_portfolio_f4cold` | `lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `daily539_f4cold_5bet` | `v0.1` | `lottolab.strategies.adapters.daily539_portfolio_f4cold` | `lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `daily539_markov_cold` | `v0.1` | `lottolab.strategies.adapters.daily539_wave1` | `lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `midfreq_acb_2bet` | `v0.1` | `lottolab.strategies.adapters.daily539_portfolio_frequency` | `lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `midfreq_fourier_2bet` | `v0.1` | `lottolab.strategies.adapters.daily539_portfolio_frequency` | `lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `p0b_539_3bet_f_cold_fmid` | `v0.1-p36` | `lottolab.strategies.adapters.daily539_fourier4` | `lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_asm_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_attention_replay_1bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_auto_optimizer_alpha_25bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_backtest_10bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_cag_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_cold_hunter_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_core_satellite_12bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_deviation_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_diversified_ensemble_v6_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_dm_dms_2bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:Daily539BigLottoDmDmsAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_dms_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_dms_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_dynamic_frequency_1bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_echo_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_elite_7bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_enhanced_dual_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_exhaustive_audit_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_five_me_5bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_gap_pressure_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_gemini_phase2_7bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_gemini_v1_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_graph_predictor_1bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_high_prize_trend_7bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_hot_cooccurrence_1bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_moderate_rank_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_mwsc_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_optimized_ensemble_1bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_p0_echo_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_pure_cold_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_random_core_satellite_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_random_zone_split_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_rebound_aware_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_short_window_deviation_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_smart_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_tme_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_tme_optimizer_4bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_two_bet_elite_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_two_bet_final_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_two_bet_optimizer_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_two_bet_optimizer_v2_2bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_variant_history_11bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_zdp_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_zone_momentum_1bet` | `v0.1-t539-batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15` | `lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| T539 | `t539_biglotto_zone_split_3bet` | `v0.1-t539-cross-lottery-r2` | `lottolab.strategies.adapters.daily539_biglotto_portable` | `lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `zone_gap_3bet_539` | `v0.1-p36` | `lottolab.strategies.adapters.daily539_zone_gap` | `lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |

## Production exact joins

| Lottery | Strategy ID | Version | Implementation | Callable | Status |
|---|---|---|---|---|---|
| B649 | `legacy_biglotto__backtest_sum_constraint__acb3b118300d` | `v0.1` | `lottolab.strategies.adapters.biglotto_batch17` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave11` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave4` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave10` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__core_satellite__611284461323` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave11` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504` | `v0.1` | `lottolab.strategies.adapters.biglotto_batch17` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_asm__d39a233a4c75` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave13` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_cag__7ca5343dfedd` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave9` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_ces__78d17c530ab8` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave8` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_cluster_cover__5b43959e7c55` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave9` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_dcb__c3299c25ca59` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave13` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_dms__b63442289bd5` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave8` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_mwsc__ba37643d6a3b` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave8` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_tme__f3bb5106dfe3` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave6` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| B649 | `legacy_biglotto__test_zdp__e80cc7e95453` | `v0.1` | `lottolab.strategies.adapters.biglotto_wave9` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_apriori_2bet` | `v0.1-p638-wave2` | `lottolab.strategies.adapters.powerlotto_batch01` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_c01_recency_decay_1bet` | `v0.1-p638-p173` | `lottolab.strategies.adapters.cross_dataset_batch02_bridge` | `lottolab.strategies.adapters.base:BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_c03_pair_centrality_1bet` | `v0.1-p638-p176` | `lottolab.strategies.adapters.cross_dataset_batch02_bridge` | `lottolab.strategies.adapters.base:BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_c04_zone_balanced_1bet` | `v0.1-p638-p173` | `lottolab.strategies.adapters.cross_dataset_batch02_bridge` | `lottolab.strategies.adapters.base:BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_c05_dispersion_match_1bet` | `v0.1-p638-p176` | `lottolab.strategies.adapters.cross_dataset_batch02_bridge` | `lottolab.strategies.adapters.base:BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_c06_regime_cusum_1bet` | `v0.1-p638-p176` | `lottolab.strategies.adapters.cross_dataset_batch02_bridge` | `lottolab.strategies.adapters.base:BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_c07_borda_ensemble_1bet` | `v0.1-p638-p176` | `lottolab.strategies.adapters.cross_dataset_batch02_bridge` | `lottolab.strategies.adapters.base:BetAdapter.get_one_bet` | `RESOLVED_REPLAY_BINDING` |
| P638 | `power_lead_lag_2bet` | `v0.1-p638-wave2` | `lottolab.strategies.adapters.powerlotto_batch01` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| P638 | `zonal_entropy_2bet` | `v0.1-p638-wave1` | `lottolab.strategies.adapters.powerlotto_batch01` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |
| T539 | `acb_markov_midfreq_3bet` | `v0.1` | `lottolab.strategies.adapters.cross_dataset_batch02_bridge` | `lottolab.strategies.adapters.base:PortfolioBetAdapter.get_bets` | `RESOLVED_REPLAY_BINDING` |

## Explicit handoff facts

```text
QUALIFIED_SELECTOR_IDENTITIES = 135
RAW_SELECTOR_LABELS = 134
PRODUCTION_EXACT_JOINS = 25
SUPPLEMENT_ROWS = 110
P638_SUPPLEMENT_ROWS = 56
T539_SUPPLEMENT_ROWS = 54
SAFE_PRODUCTION_ALIAS_MAPPING = NO
SELECTOR_RERUN = NOT RUN
HISTORICAL_REPLAY = NOT RUN
DB_ACCESS = NO
PREDICTIVE_ADVANTAGE = NOT CLAIMED
```

Combined accounting is 135/135, and every supplement row is `RESOLVED_REPLAY_BINDING`.
