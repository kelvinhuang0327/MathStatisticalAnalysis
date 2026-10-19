# B649 Track D Historical Research Surface and Open Hypotheses R1

TASK_ID: B649_TRACK_D_HISTORICAL_RESEARCH_SURFACE_AND_OPEN_HYPOTHESES_R1

STATUS: PASS

CONTINUATION: RESUMED_FROM_QUOTA_EXHAUSTED_AGENT

MODE: READ_ONLY_RESEARCH_SYNTHESIS

RESEARCH_POLICY: WIDE_IN / STRICT_OUT

MAIN_HEAD: 2db4da27aee716805c393eb9c7dd41aff8e9527e

MAIN_TREE: cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c

ORIGIN_MAIN: 2db4da27aee716805c393eb9c7dd41aff8e9527e

INITIAL_BRANCH_AT_RESUME: main

CURRENT_BRANCH_AT_FINAL_VERIFICATION: codex/b649-horizon-minimax-target-native-migration-r1

CONCURRENT_BRANCH_DRIFT_OBSERVED: YES

FOREIGN_DIRTY_STATE: YES

ARTIFACT_ROOTS_READ: 18

AUTHORITIES_VERIFIED: PASS_WITH_SCOPED_UNKNOWNS

HISTORICAL_ANALYZABLE_COUNT: 133

CURRENT_EXECUTABLE_WITHIN_HISTORICAL_COUNT: 51

CURRENT_EXECUTABLE_COUNT: 51

FORWARD_EXECUTABLE_COUNT_WITHIN_HISTORICAL: 51

HISTORICAL_ONLY_RAW_ONLY_COUNT: 82

CANDIDATE_K_DIRECT_AVAILABLE_COUNT: 7

FROZEN_CANDIDATE_COUNT: 40

FROZEN_FORWARD_GENERATABLE_COUNT: 3

FROZEN_UNAVAILABLE_COUNT: 37

METHOD_FAMILY_COUNT: 30

DIRECTLY_TESTED_HYPOTHESIS_COUNT: 33

OPEN_HYPOTHESIS_COUNT: 28

OUTPUT_PATH: /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_RESEARCH_SURFACE_R1.md

BLOCKERS: NONE

## §1 Executive Summary

[實測] 133 個 historical analyzable identities 仍是 Track D 的歷史研究母體；其中 51 個也存在於目前 executable catalog，82 個為 historical-only / raw-only。這三個數字不得與 Candidate-K 的 7 個 direct matrix paths，或 frozen cohort 中可 forward-generate 的 3 個 candidates 混用。

[實測] 133-strategy robustness surface 共 17,024 個 strategy × ticket-count × window × criterion cells。正向 Bonferroni correction-surviving cells 為 0；負向 correction-surviving cells 為 731。這只否定該固定歷史 replay、native/projection contract、window、criterion 與 null 下的正向 edge，不等於否定整個方法家族或未測 interaction。

[實測] 40 個 frozen candidates 中只有 3 個 A candidates 能生成 forward prediction；17 個 A candidates unavailable，20 個 C candidates unavailable。這是 PROSPECTIVE_PIPELINE_GAP，不是 HISTORICAL_RESEARCH_INVALID。

[實測] A 與 C 的歷史 Combination Projection 已完成，且都不是 strategy internal ranking：

- A = CURRENT_PORTFOLIO_VOTE_PROXY。
- C = TRAILING_WINDOW_FREQUENCY_PROXY。

[實測] 既有歷史研究已直接觸及 33 個本文件定義的 hypothesis units；仍保留 28 個可被明確測試的 open hypothesis units。計數單位是「一個具可區分 contract 的 hypothesis family，或 authority 明確命名的 H1/H2」，不是每一個 strategy、pair、triple、window 或 parameter cell。若以 cells 或 combinations 為單位，數字會完全不同，因此不可把 33 解讀成所有曾跑過的參數組合總數。

[Inferred] Track B 最先值得做的實驗是 H01 CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR：在固定 5-ticket budget、strict-prior features、expanding-window blocked evaluation 下，動態選擇既有候選，而不是再造另一個 static strategy。它可直接重用 sealed 20-candidate causal regime portfolios、raw history、exact same-ticket random baseline，不需要 DB mutation，也不受 Cohort V1 的 37/40 availability gap 綁住。

核心研究邊界：

HISTORICAL_NEGATIVE_RESULT != FUTURE_RESEARCH_PROHIBITED

SIMILAR_METHOD_EXISTS != SAME_HYPOTHESIS_ALREADY_TESTED

EXTERNAL_UNVERIFIED != DO_NOT_TEST

## §2 Authority / Evidence Status

### 2.1 Evidence labels

- [實測]：本 task continuity 中有實際 command output、CSV/JSON recount、checksum result 或 Git observation。
- [宣告]：只由 sealed report / manifest 自述，未在本 synthesis 重算。
- [記憶]：只存在於交接敘述，未由本次可恢復 evidence 支撐。
- [Inferred]：由已實測數字作出的可檢查推論。
- [Unknown]：本次允許範圍內沒有足夠 evidence。

### 2.2 Repository authority

| Item | Result | Evidence status |
|---|---|---|
| Local HEAD | 2db4da27aee716805c393eb9c7dd41aff8e9527e | [實測] |
| origin/main | 2db4da27aee716805c393eb9c7dd41aff8e9527e | [實測] |
| Commit tree | cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c | [實測，continuation command evidence] |
| Branch at resume | main | [實測] |
| Branch at final verification | codex/b649-horizon-minimax-target-native-migration-r1 | [實測] |
| Concurrent branch metadata drift | YES; HEAD/tree remained unchanged | [實測] |
| Concurrent dirty state | YES | [實測] |
| Relevant committed authority movement | NO | [實測] |
| Applicable AGENTS.md | NONE | [實測，continuation preflight] |

Foreign/concurrent paths observed and preserved without content inspection by Track D:

- src/lottolab/strategies/catalog.py
- src/lottolab/strategies/adapters/biglotto_horizon_minimax.py
- tests/architecture/test_dependency_rules.py
- tests/unit/test_biglotto_batch15_adapters.py
- tests/unit/test_biglotto_horizon_minimax_adapter.py
- tests/unit/test_biglotto_wave1_adapters.py
- tests/unit/test_generate_live_zone_split_bets_use_case.py
- tests/unit/test_strategy_catalog.py

### 2.3 Artifact authorities recovered/read

The following roots were read directly by the prior Worker/subtasks in this same task continuity, and their command outputs were recovered before synthesis:

1. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2
2. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_HIT_DEPTH_PROJECTION_R1
3. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_FINAL_133_MULTI_TICKET_RANKING_REVIEW_R1
4. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1
5. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_STRATEGY_K_HISTORICAL_MATRIX_AUTHORITY_R1
6. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROJECTION_R1
7. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_CANDIDATE_FREEZE_R1
8. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_FORWARD_OBSERVER_R1
9. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_FORWARD_OBSERVER_R2
10. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_FORWARD_OBSERVER_R3
11. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_FORWARD_OBSERVER_R4
12. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_NEXT_GENERATION_STRATEGY_RESEARCH_R1
13. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OFFICIAL_CAUSAL_REGIME_ANALYSIS_R1
14. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_EWMA_SHORT_MEDIUM_DRIFT_CONFIRMATION_R2
15. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_EWMA_REGIME_EVENT_INFLUENCE_CONFIRMATION_R3
16. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_EWMA_PROSPECTIVE_SHADOW_PROTOCOL_R4
17. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_R2_OVERNIGHT_NEGATIVE_SIGNAL_STRUCTURE_AND_ANTI_BIAS_DESIGN_R1
18. /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_R2_FULL_UNIVERSE_PRIZE_AWARE_INFERENTIAL_VALIDATION_R1

[實測] SHA256SUMS validation was recovered as passing for the Raw Foundation R2, Hit Depth, Combination Projection, Candidate Freeze, and Forward Observer checksum-listed payloads. Full reproduction scripts and complete task-tree recomputation were NOT RUN in this continuation.

[Unknown] Forward Observer R4's own report remains FRESH_BOUNDED_PENDING. This Track D synthesis does not upgrade that status.

### 2.4 Current source boundary

- Network refresh: NOT RUN.
- GitHub/external-method search: NOT RUN by design.
- Any external method mentioned in prior material remains EXTERNAL_UNVERIFIED_CLAIM until LOCAL_EXPERIMENTAL_REPLICATION.
- Latest locally sealed outcome used by the named historical artifacts: [宣告] 115000075 / 2026-07-31.

## §3 133-Strategy Method-Family Surface

### 3.1 Reading rules

This is an overlapping method-surface map, not a partition. One strategy may appear in multiple semantic families; row counts and corrected-negative tallies are therefore not additive. The historical 133 population itself is unique and fixed.

For tested rows, raw/native strategy histories were evaluated through the historical authority and the standard FULL / 750 / 300 / 50 surfaces. Native ticket semantics remain the strategy's preserved ticket portfolio; the native range below is descriptive and must not be rewritten as a common ranking score.

The per-family current-forward join was not recomputed during continuation. Unless an explicit closed-unexecutable identity is named, FORWARD is therefore UNKNOWN_BY_FAMILY; the population-level 51/82 split remains authoritative.

In the outcome column, 0+/N− means zero positive and N negative Bonferroni-surviving cells on the recovered semantic surface. Because families overlap, N is not additive.

| # | Family | Representative strategy IDs | Historical availability / native tickets | Raw history | Forward | Historical outcome summary | Hypothesis status |
|---:|---|---|---|---|---|---|---|
| 1 | frequency | dynamic_frequency_predictor; edge_splicer_5bet | 19 analyzable; native 1..360 | YES | UNKNOWN_BY_FAMILY | 0+/122−; base frequency rules directly replayed | DIRECTLY_TESTED, but fusion/conditioning remains open |
| 2 | hot/cold | backtest_biglotto_coldpool_15; backtest_biglotto_hot_stop_rebound | 7 mapped; native 1..12 | YES | UNKNOWN_BY_FAMILY | 0+/27− on mapped surface | DIRECTLY_TESTED under existing selection rules |
| 3 | missing/gap | b649_new_discrete_gap_hazard_r1 | 0 inside the 133 map; one bounded Branch-B causal experiment | YES for new experiment inputs | NOT IN CURRENT CATALOG | Did not enter the one-item shortlist | PARTIALLY_TESTED; broader gap hazard remains open |
| 4 | EWMA / recency | backtest_biglotto_6bet_ewma | 1 mapped; native 17 tickets; specific 15/20-ticket regime H1/H2 also studied | YES | UNKNOWN_BY_FAMILY | Base surface 0 positive corrected; HIGH short-medium drift H1/H2 historically positive but threshold sensitivity mixed | PARTIALLY_TESTED; prospective confirmation open |
| 5 | Fourier / FFT / periodicity | power_fourier_rhythm | 1 direct semantic representative; native 2 | YES | UNKNOWN_BY_FAMILY | 0+/14− for the tested native rule | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 6 | Markov / transition | backtest_biglotto_markov_4bet; backtest_markov_repeat_exception | 4 mapped; native 2..27 | YES | UNKNOWN_BY_FAMILY | 0+/14−; one state-conditioned transition Branch-B experiment also run | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 7 | deviation / anomaly | optimize_deviation_extreme_generic; biglotto_2bet_optimizer | 8 mapped; native 1..7 | YES | UNKNOWN_BY_FAMILY | 0+/64− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 8 | regime | predict_evolutionary_gum; official 20-candidate regime analysis | 1 base-family strategy plus 20 candidates × 4 axes × 3 bands × 4 ticket counts | YES | UNKNOWN_BY_FAMILY | 71 high-sample cells positive vs random in both discovery/confirmation, but exploratory and multiplicity-exposed; many reversals | PARTIALLY_TESTED |
| 9 | structural constraints | backtest_structural_group; constraint_filter_predictor; backtest_sum_constraint | 3 mapped; native 2..39 | YES | UNKNOWN_BY_FAMILY | 0+/22−; overlap/concentration failure mechanics separately established | DIRECTLY_TESTED for named rules |
| 10 | sum/range | constraint_filter_predictor; backtest_sum_constraint | 2 mapped; native 2..39 | YES | UNKNOWN_BY_FAMILY | 0+/22− on overlapping surface | DIRECTLY_TESTED for named constraints |
| 11 | zone | zone_split; zone_split_optimizer | 9 mapped; native 1..54 | YES | UNKNOWN_BY_FAMILY | 0+/52− | DIRECTLY_TESTED for named zone rules |
| 12 | co-occurrence | cooccurrence_graph; hot_cooccurrence_analyzer | 2 mapped; native 1..4 | YES | UNKNOWN_BY_FAMILY | 0+/13− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 13 | graph | graph_predictor; backtest_graph_method; cooccurrence_graph | 3 mapped; native 1..4 | YES | UNKNOWN_BY_FAMILY | 0+/31− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 14 | Apriori / association | backtest_apriori; predict_biglotto_apriori | 2 mapped; native 2..13 | YES | UNKNOWN_BY_FAMILY | 0+/11− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 15 | Bayesian | advanced_bayesian_analyzer; bayesian_ensemble | 0 analyzable in 133; closed identities lacked a legal deterministic ticket contract or unified engine | NO analyzable raw contract | NO KNOWN PATH | No direct 133 test | NOT_TESTED |
| 16 | XGBoost | xgboost_model | 1 mapped; native 1 | YES | UNKNOWN_BY_FAMILY | 0+/11− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 17 | LSTM | perball_lstm; lstm_attention_predictor | 0 analyzable in 133; closed for unbound neural training randomness | NO analyzable raw contract | NO KNOWN PATH | No direct 133 test | NOT_TESTED |
| 18 | Transformer | transformer_model; attention_replay_predictor is not treated as transformer parity | 0 direct transformer in 133; one attention-replay strategy exists but does not establish transformer equivalence | Transformer raw contract absent | NO KNOWN TRANSFORMER PATH | No direct transformer hypothesis test | NOT_TESTED |
| 19 | ensemble | optimized_ensemble; biglotto_diversified_ensemble; predict_consensus_ensemble | 4 mapped; native 1..3 | YES | UNKNOWN_BY_FAMILY | 0+/38− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 20 | consensus | predict_consensus_ensemble | 1 mapped; native 2 | YES | UNKNOWN_BY_FAMILY | 0+/13− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 21 | anti-consensus | anti_consensus_strategy | 1 mapped; native 6 | YES | UNKNOWN_BY_FAMILY | 0+/5− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 22 | evolutionary | evolution_engine; predict_evolutionary_gum | 2 mapped; native 1..10 | YES | UNKNOWN_BY_FAMILY | 0+/19− | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 23 | covering | covering_strategy_research; test_cluster_cover | 2 mapped; native 3..40 | YES | UNKNOWN_BY_FAMILY | 0+/5− | PARTIALLY_TESTED; alternative objectives remain open |
| 24 | diversification | orthogonal_diversification_benchmark; research_true_orthogonal; diversified ensembles | 7 mapped; native 3..35 | YES | UNKNOWN_BY_FAMILY | 0+/28−; some conditional regime cells were descriptive positives | PARTIALLY_TESTED |
| 25 | cluster | backtest_cluster_pivot_biglotto; predict_biglotto_6bets_cluster; research_cluster_enhancements | 6 mapped; native 3..19 | YES, one overlay has partial coverage | UNKNOWN_BY_FAMILY | 0+/9−; low-sample apparent specialists often reversed | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 26 | portfolio optimization | portfolio_optimizer; backtest_biglotto_portfolio | 2 mapped; native 4..5 | YES | UNKNOWN_BY_FAMILY | 0+/3−; exact overlap penalty/anti-bias geometry also available | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN |
| 27 | random / smart-random baseline | compare_random_vs_smart; quantum_random_predictor | 2 mapped; native 5..8 | YES | UNKNOWN_BY_FAMILY | 0+/2− as strategies; exact random baselines are reusable comparators | DIRECTLY_TESTED as comparator and named strategies |
| 28 | special-number specific | biglotto_special_v4; analyze_biglotto_special | 0 legal full-ticket analyzable strategy; special-hit outcomes exist in projections | Partial metric evidence only | NO KNOWN FULL-TICKET PATH | Special-number ranking without main-number ticket construction was closed | PARTIALLY_TESTED at outcome level; joint model NOT_TESTED |
| 29 | candidate-only / exclusion-only | negative_selection_biglotto; backtest_must_hit; closed must-not-hit/negative-selector identities | 2 mapped; native 1..8, plus closed filter-only identities | YES for mapped ticket producers | UNKNOWN_BY_FAMILY | 0+/6−; filter-only contracts were not equivalent to a legal ticket producer | PARTIALLY_TESTED |
| 30 | other / unknown | core_satellite variants; predict_biglotto_echo_phase2; research_cluster_enhancements | 3 mapped; native 3..15 | YES / overlay | UNKNOWN_BY_FAMILY | 0+/15−; heterogeneous semantics | UNKNOWN |

### 3.2 Directly tested hypothesis register

DIRECTLY_TESTED_HYPOTHESIS_COUNT: 33

Counting rule: one distinct named producer-family contract or one separately declared hypothesis family/H1/H2. Individual strategies, combinations, cells and parameter settings are not counted separately unless the authority names them as a separate hypothesis.

| IDs | Directly tested hypothesis units |
|---|---|
| DT01–DT08 | base frequency; hot/cold; EWMA native rule; Fourier; Markov; deviation/anomaly; regime-family producer; structural constraints |
| DT09–DT16 | sum/range; zone; co-occurrence; graph; Apriori; XGBoost; attention replay; ensemble |
| DT17–DT24 | consensus; anti-consensus; evolutionary; covering; diversification; cluster; portfolio optimization; random/smart-random |
| DT25–DT28 | candidate/exclusion ticket producers; A combination projection; C combination projection; 20-candidate four-axis regime conditioning |
| DT29–DT31 | Branch-B horizon-minimax disagreement; discrete-gap hazard; state-conditioned transition |
| DT32–DT33 | EWMA HIGH SHORT_MEDIUM_DRIFT H1 at 15 tickets; H2 at 20 tickets |

The register establishes direct contact only. It does not claim that a family is exhausted.

## §4 Historical Negative Findings and Exact Scope

| Finding | HISTORICAL_FINDING | RESEARCH_SCOPE | What it does not prove |
|---|---|---|---|
| Full robustness surface | [實測] 0 positive and 731 negative Bonferroni-surviving cells across 17,024 cells | Fixed 133 identities, fixed projection/ticket/window/criterion contracts, exact named nulls | It does not forbid new interactions, conditional models, loss functions, regimes or meta-layers |
| Fourier | [實測] power_fourier_rhythm has 0 positive corrected and 14 negative corrected cells on its tested native rule | That producer, preserved history, tested windows and ticket semantics | It does not test Fourier × regime, residual Fourier, graph residual or conditional consensus |
| XGBoost | [實測] xgboost_model has 0 positive corrected and 11 negative corrected cells | That historical feature/producer/selection contract | It does not test XGBoost as a residual stacker, calibrated per-number model or meta-selector |
| Consensus / anti-consensus | [實測] tested static consensus and anti-consensus producers have no corrected positive cells | Their fixed static aggregation and native tickets | It does not test conditional consensus, minority signal by regime, or uncertainty-aware weighting |
| Next-generation bounded candidates | [實測] only horizon-minimax disagreement passed the result-blind shortlist gate; discrete-gap hazard and state-conditioned transition did not | Three exact causal producers, FULL/750/300/50, native 1- or 2-ticket baselines, sealed local history | It does not exhaust all gap or state-conditioned transition definitions |
| Regime exploration | [實測] many descriptive sign replications coexist with 419 out-of-sample reversals and 146 not-replicated rows; 71 high-sample cells were positive vs random in both splits | 20 provisional candidates, four fixed regime axes, 5/10/15/20 tickets, exploratory multiplicity | It does not establish a deployable regime edge; it justifies preregistered confirmation |
| EWMA drift confirmation | [實測] frozen q67 point estimates remain positive, but ±0.001 historical threshold bounds cross zero; latest audit has only 8 HIGH events | Exact EWMA strategy, SHORT_MEDIUM_DRIFT/HIGH, 15/20 tickets, named chronological blocks | It does not negate other thresholds, other drift features, or prospective H1/H2; threshold robustness remains unresolved |
| Portfolio overlap | [實測] overlap/concentration is associated with below-null portfolios in supported PREFIX_20 and BAND_21_50 strata; exact pairwise mechanics show overlap changes dependence | Structural portfolio geometry under exact prize/null contract, with small cluster-level samples | It is not a predictive-number edge; anti-bias can recover a handicap but cannot create evidence beyond random expectation |
| Cohort V1 availability | [實測] 37/40 candidates cannot currently produce forward predictions | Frozen producer/horizon engineering contract | It says nothing about the candidates' historical research value |
| Post-freeze accumulation | [實測] post-freeze-date prospective count is 0 | Existing six observations are pre-freeze unseen holdouts | It is not a negative prospective result because no calendar-gated prospective sample exists |

## §5 Historical vs Current Executable vs Candidate-K vs Frozen-Forward Map

| Population / capability | Count | Meaning |
|---|---:|---|
| HISTORICAL_ANALYZABLE | 133 | Historical research population with metric/raw evidence |
| CURRENT_EXECUTABLE_WITHIN_HISTORICAL | 51 | 7 MATRIX_AVAILABLE + 44 PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED; exact overlap with the 133 universe |
| HISTORICAL_ONLY_RAW_ONLY | 82 | Not in current executable catalog but remains valid historical evidence |
| COMPLETE_CURRENT_EXECUTABLE_B649_CATALOG | 68 | Different universe from the 51 historical overlap; do not substitute it for 51 |
| CANDIDATE_K_DIRECT_AVAILABLE | 7 | Exact Strategy × K matrix path exists now |
| CURRENT_PORTFOLIO_WITHOUT_CANONICAL_NUMBER_AGGREGATION | 44 | Current identity exists but canonical number-level aggregation contract is absent |
| FROZEN_CANDIDATES | 40 | Candidate Freeze R1; 10 per A/C × pair/triple bucket |
| FROZEN_CONTROLS | 10 | Matched controls |
| FROZEN_FORWARD_GENERATABLE | 3 | A_PAIR_R1_02, A_PAIR_R1_05, A_PAIR_R1_06 |
| FROZEN_UNAVAILABLE | 37 | 17 A + 20 C |
| POST_FREEZE_DATE_PROSPECTIVE | 0 | No calendar-gated post-freeze accumulation yet |

These are four separate axes:

HISTORICAL_ANALYZABLE != CURRENT_EXECUTABLE != CANDIDATE_K_AVAILABLE != FROZEN_FORWARD_GENERATABLE

## §6 37/40 Prospective Availability Gap

PROSPECTIVE_PIPELINE_GAP: [實測] YES

HISTORICAL_RESEARCH_INVALID: NO

### 6.1 Exact frozen distribution

| Bucket | Available | Unavailable | Primary reason |
|---|---:|---:|---|
| A pair/triple candidates | 3 | 17 | CURRENT_PORTFOLIO_MEMBER_PATH_UNAVAILABLE |
| C pair/triple candidates | 0 | 20 | C_PROXY_HORIZON_NOT_FROZEN |
| Controls | 0 | 10 | Matched candidate unavailable |

[實測] Underlying A member-detail occurrences include 35 NOT_IN_CURRENT_PRODUCTION_CATALOG and 2 CURRENT_EXECUTABLE_NOT_PORTFOLIO cases. C candidates fail first at the missing frozen horizon gate; [Unknown] binding a horizon alone does not prove all downstream member producer paths exist.

### 6.2 Why the gap occurred

[實測] Candidate Freeze eligibility used historical stable-positive status, SHORT support and LONG/MID evaluability, then selected the top ten per bucket. It did not include current catalog membership, transitive producer path, A portfolio compatibility, C horizon binding or forward executability as pre-freeze constraints.

### 6.3 Cohort V2 read-only recommendation

[Inferred] Cohort V2 can be created without modifying historical or V1 authority if it is separately versioned and:

1. freezes the repository/producer capability snapshot before selection;
2. requires every A member to provide the correct causal portfolio/exposure path;
3. freezes C's exact trailing horizon inside the candidate identity;
4. verifies transitive producer fingerprints before ranking;
5. does not force ten candidates into a bucket if fewer qualify;
6. creates new controls, cutoff/start boundary and fresh evidence streams;
7. creates a new correction family over the actual V2 membership.

The old terminal_holm_family_size = 40 cannot be carried over after membership changes. V1's selection metrics, bias disclosure, 40+10 membership, availability result and six pre-freeze holdout observations remain historical evidence, but cannot be relabeled as V2 prospective confirmation.

## §7 Open Hypothesis Inventory

OPEN_HYPOTHESIS_COUNT: 28

The status describes the exact hypothesis in this row, not whether a related family name appeared historically.

| ID | Open hypothesis | Prior contact | Status | Reuse / test path | Priority |
|---|---|---|---|---|---|
| H01 | Cross-strategy residual-gated meta-selector | Static strategies and regime screens exist; dynamic residual gating was not located | NOT_TESTED | 20-candidate causal portfolios, prior-only hit history, fixed 5-ticket evaluation | TIER_1_EXPLORE_NOW |
| H02 | Complementary-error graph across strategies | Pairwise method graph is not the same as error-complementarity graph | NOT_TESTED | Per-draw strategy outcome matrix; community/cover analysis | TIER_1_EXPLORE_NOW |
| H03 | Mixture-of-experts with out-of-fold gating | Regime-conditioned descriptive tables exist; no dynamic allocator | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Frozen regime features plus expanding-window gating | TIER_1_EXPLORE_NOW |
| H04 | 50/300/750 slope, acceleration and disagreement signal | Four windows were evaluated separately; their temporal derivatives were not | NOT_TESTED | Existing windows and strictly prior draw features | TIER_1_EXPLORE_NOW |
| H05 | Conditional consensus by regime/state | Static consensus tested | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Existing strategy outputs and frozen states | TIER_2_EXPLORE_AFTER |
| H06 | Conditional anti-consensus / minority signal | Static anti-consensus tested | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Disagreement and error-history features | TIER_2_EXPLORE_AFTER |
| H07 | Calibrated per-number probability model | No canonical number-level contract for 44 current portfolio identities | NOT_TESTED | Start with 7 Candidate-K paths or reconstructed causal number exposure | TIER_1_EXPLORE_NOW |
| H08 | Per-number ranking-loss model | Direct ticket producers are not a rank-loss model | NOT_TESTED | Same causal number-level matrix as H07 | TIER_2_EXPLORE_AFTER |
| H09 | Predictive uncertainty / ensemble dispersion | Static ensembles tested without calibrated uncertainty | NOT_TESTED | Cross-model dispersion and calibration curves | TIER_2_EXPLORE_AFTER |
| H10 | Direct ticket-level scorer with pair/triple residual terms | A/C projection uses proxies, not a learned ticket score | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Combination projection and causal ticket histories | TIER_1_EXPLORE_NOW |
| H11 | Pair/triple interaction residual after marginal number scores | Pair/triple combinations were projected, but residualized interaction was not | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | 392,084 historical combinations plus held-out scoring | TIER_2_EXPLORE_AFTER |
| H12 | Temporal hypergraph motifs / communities | Static graph/co-occurrence tested | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Pair/triple history, rolling hypergraph features | TIER_2_EXPLORE_AFTER |
| H13 | Temporal graph change rather than static graph score | Static graph family exists | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Rolling graph deltas and blocked validation | TIER_2_EXPLORE_AFTER |
| H14 | DPP/submodular portfolio selection under a calibrated score | Covering/diversification tested; DPP/submodular objective not located | NOT_TESTED | Existing ticket candidates and exact overlap geometry | TIER_1_EXPLORE_NOW |
| H15 | Multi-objective hit-depth / coverage / overlap / payout-proxy optimizer | Pieces exist separately | PARTIALLY_TESTED | Hit Depth, prize-aware validation, portfolio geometry | TIER_2_EXPLORE_AFTER |
| H16 | Joint main-number/special-number conditional model | Special outcomes exist, legal full-ticket predictor absent | NOT_TESTED | Main/special draw history and joint exact baseline | TIER_3_LONG_SHOT |
| H17 | Dynamic Bayesian state-space probability model | Bayesian identities closed without analyzable contract | NOT_TESTED | Causal counts and posterior predictive calibration | TIER_2_EXPLORE_AFTER |
| H18 | HMM latent-regime gating | Fixed empirical regime bands exist, HMM does not | NOT_TESTED | Regime feature table and expanding-window inference | TIER_2_EXPLORE_AFTER |
| H19 | Change-point-triggered strategy allocation | Drift axes exist, explicit change-point gating does not | NOT_TESTED | 50/300/750 distributions, frozen alarm rule | TIER_1_EXPLORE_NOW |
| H20 | Entropy/distribution-shift anomaly gating | Entropy/drift was descriptive, not a selector | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Existing four regime axes and strict-prior features | TIER_2_EXPLORE_AFTER |
| H21 | Negative-information candidate suppressor | Exclusion ticket producers exist; conditional suppression layer does not | PARTIALLY_TESTED | Historical false-positive patterns plus paired comparator | TIER_2_EXPLORE_AFTER |
| H22 | Conditional/nested exact null and paired counterfactual calibration | Exact nulls exist, but new conditional questions need new nulls | PARTIALLY_TESTED | Reuse exact combinatorics; implement paired/nested layer | TIER_2_EXPLORE_AFTER |
| H23 | LSTM as residual/meta-feature, not direct ticket generator | Closed LSTM identities are not this hypothesis | NOT_TESTED | Deterministic seeded training and out-of-fold embeddings | TIER_3_LONG_SHOT |
| H24 | Transformer as residual/meta-feature | Attention-replay producer is not transformer parity | NOT_TESTED | Deterministic causal sequence encoder | TIER_3_LONG_SHOT |
| H25 | XGBoost stacking strategy outputs and history | Direct XGBoost producer tested; residual stacking was not | FAMILY_TESTED_NEW_HYPOTHESIS_OPEN | Strategy-output matrix and blocked CV | TIER_2_EXPLORE_AFTER |
| H26 | Special-aware portfolio geometry | Special metric and portfolio geometry exist separately | NOT_TESTED | Joint baseline plus overlap-aware portfolio selection | TIER_3_LONG_SHOT |
| H27 | Preregistered confirmation of horizon-minimax disagreement | Bounded historical candidate shortlisted; no prospective confirmation | PARTIALLY_TESTED | Existing causal producer and exact 2-ticket baseline | TIER_1_EXPLORE_NOW |
| H28 | Prospective confirmation of frozen EWMA drift H1/H2 | Historical/event-influence confirmation exists; post-freeze evidence absent | PARTIALLY_TESTED | Frozen q67/H1/H2 protocol and shadow observer | TIER_1_EXPLORE_NOW |

ALREADY_DIRECTLY_TESTED is represented by DT01–DT33 in §3.2; it is not counted in OPEN_HYPOTHESIS_COUNT.

## §8 Research Gaps

1. PER_FAMILY_FORWARD_JOIN: [Unknown] not recomputed during continuation; only the authoritative population-level 51/82 split is claimed.
2. NUMBER_LEVEL_AGGREGATION: [實測] 44 current portfolio identities lack a canonical number-level aggregation contract.
3. C_HORIZON_BINDING: [實測] absent in Cohort V1 freeze.
4. TRANSITIVE_PRODUCER_CAPABILITY: [實測] freeze did not gate on it.
5. TRUE_CALENDAR_PROSPECTIVE_SAMPLE: [實測] count 0.
6. R4 FULL LIFECYCLE VERDICT: [Unknown] R4 reports FRESH_BOUNDED_PENDING.
7. EWMA THRESHOLD ROBUSTNESS: [Unknown] ±0.001 historical aggregate bounds cross zero; target-level success mapping is required.
8. EWMA NESTED 15/20 IDENTITY: [Unknown] aggregate monotonicity passes, target-level portfolio prefix identity is not proven by R1 aggregates.
9. SPECIAL-NUMBER LEGAL TICKET CONTRACT: [Unknown] outcome metrics exist but no analyzable full-ticket predictive contract was recovered.
10. BAYESIAN/LSTM/TRANSFORMER PARITY: [Unknown] closed identities do not establish faithful deterministic hypothesis tests.
11. STATISTICAL_BOOTSTRAP: [實測] absent in Forward Observer R1–R4. bootstrap_records / live_main_at_bootstrap are initialization terms, not resampling or bootstrap confidence intervals.
12. EXTERNAL METHODS: EXTERNAL_UNVERIFIED_CLAIM; no external search was required or run.

## §9 TOP_10_OPEN_RESEARCH_HYPOTHESES

### 1

HYPOTHESIS_ID: H01

TITLE: Cross-strategy residual-gated meta-selector

WHY_DIFFERENT_FROM_EXISTING_133: The 133 are fixed producers; H01 predicts which existing producer's error profile is favorable for the current state using only prior observations.

EXISTING_COMPONENTS_REUSABLE: 20-candidate causal portfolios, regime features, Hit Depth, exact same-ticket random baseline, blocked chronology.

NEW_COMPONENT_REQUIRED: Leakage-safe out-of-fold residual matrix and deterministic gating model.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES, as a separate shadow selector over forward-capable experts.

EXPECTED_COST: MEDIUM

NOVELTY: HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_1_EXPLORE_NOW

### 2

HYPOTHESIS_ID: H27

TITLE: Preregistered confirmation of horizon-minimax disagreement

WHY_DIFFERENT_FROM_EXISTING_133: It is a new causal two-ticket disagreement producer, not a relabeling of a legacy strategy; it was the only candidate passing the result-blind Branch-B shortlist.

EXISTING_COMPONENTS_REUSABLE: Sealed producer, four-window replay, exact two-ticket baseline, shortlist contract.

NEW_COMPONENT_REQUIRED: Frozen confirmation protocol and untouched validation/prospective blocks.

HISTORICAL_TEST_POSSIBLE: YES, on a separately reserved block if one exists.

FORWARD_TEST_POSSIBLE: YES, after a separately versioned executable adapter/shadow path.

EXPECTED_COST: LOW_TO_MEDIUM

NOVELTY: HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_1_EXPLORE_NOW

### 3

HYPOTHESIS_ID: H04

TITLE: Multi-window slope, acceleration and disagreement

WHY_DIFFERENT_FROM_EXISTING_133: Existing surfaces compare FULL/750/300/50 levels; H04 models their changes and disagreement as the signal.

EXISTING_COMPONENTS_REUSABLE: Four historical windows and strictly prior draw data.

NEW_COMPONENT_REQUIRED: Frozen derivative features and blocked calibration.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES

EXPECTED_COST: LOW

NOVELTY: MEDIUM_HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_1_EXPLORE_NOW

### 4

HYPOTHESIS_ID: H07

TITLE: Calibrated per-number probability model

WHY_DIFFERENT_FROM_EXISTING_133: Native ticket output is not a calibrated 49-number probability vector; the 44 missing aggregation contracts prove the distinction is operationally real.

EXISTING_COMPONENTS_REUSABLE: Seven direct Candidate-K paths, raw draw history, exact main-number outcome.

NEW_COMPONENT_REQUIRED: Causal number-level exposure contract, calibration loss and legality-preserving ticket constructor.

HISTORICAL_TEST_POSSIBLE: YES, initially on the seven direct paths.

FORWARD_TEST_POSSIBLE: YES for producers with stable number-level paths.

EXPECTED_COST: MEDIUM

NOVELTY: HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_1_EXPLORE_NOW

### 5

HYPOTHESIS_ID: H10

TITLE: Direct ticket-level residual scorer

WHY_DIFFERENT_FROM_EXISTING_133: A/C are exposure/frequency proxies, not learned combination-level scores; H10 estimates residual pair/triple contribution after marginal number effects.

EXISTING_COMPONENTS_REUSABLE: Combination Projection, ticket histories, exact prize/hit contracts.

NEW_COMPONENT_REQUIRED: Leakage-safe residual target, sparse interaction model and held-out selection.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES if inputs are frozen and executable.

EXPECTED_COST: HIGH

NOVELTY: HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_1_EXPLORE_NOW

### 6

HYPOTHESIS_ID: H14

TITLE: DPP/submodular portfolio selection under calibrated scores

WHY_DIFFERENT_FROM_EXISTING_133: Existing covering/diversification methods do not establish this objective or its calibration; H14 explicitly trades candidate score against overlap.

EXISTING_COMPONENTS_REUSABLE: Ticket candidates, exact overlap geometry, Hunter-Worsley bounds, anti-bias ceiling.

NEW_COMPONENT_REQUIRED: Frozen DPP/submodular objective and matched-score comparator.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES

EXPECTED_COST: MEDIUM

NOVELTY: MEDIUM_HIGH

ORTHOGONALITY: MEDIUM

TRACK_B_PRIORITY: TIER_1_EXPLORE_NOW

### 7

HYPOTHESIS_ID: H19

TITLE: Change-point-triggered strategy allocation

WHY_DIFFERENT_FROM_EXISTING_133: Existing empirical regime bands classify levels; H19 freezes an alarm and changes allocation only after a detected distribution shift.

EXISTING_COMPONENTS_REUSABLE: 50/300/750 distribution features, entropy/JS divergence, regime tables.

NEW_COMPONENT_REQUIRED: Sequential change detector, alarm freeze and gated comparator.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES

EXPECTED_COST: MEDIUM

NOVELTY: HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_1_EXPLORE_NOW

### 8

HYPOTHESIS_ID: H12

TITLE: Temporal hypergraph motif residual

WHY_DIFFERENT_FROM_EXISTING_133: Static graph/co-occurrence strategies do not model time-varying pair/triple motifs after marginal frequency is removed.

EXISTING_COMPONENTS_REUSABLE: Pair/triple histories and graph strategy evidence.

NEW_COMPONENT_REQUIRED: Rolling hypergraph features, residualization and sparse validation.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES, with bounded feature computation.

EXPECTED_COST: HIGH

NOVELTY: HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_2_EXPLORE_AFTER

### 9

HYPOTHESIS_ID: H21

TITLE: Conditional negative-information suppressor

WHY_DIFFERENT_FROM_EXISTING_133: Existing negative-selection/must-hit ticket producers are not a paired suppressor applied to an independent upstream probability model.

EXISTING_COMPONENTS_REUSABLE: Historical false-positive patterns, exclusion identities and paired ticket baselines.

NEW_COMPONENT_REQUIRED: Frozen upstream producer, suppression rule and paired counterfactual null.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES

EXPECTED_COST: MEDIUM

NOVELTY: MEDIUM_HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_2_EXPLORE_AFTER

### 10

HYPOTHESIS_ID: H17

TITLE: Dynamic Bayesian state-space number probabilities

WHY_DIFFERENT_FROM_EXISTING_133: Closed Bayesian identities lacked a legal deterministic contract; a calibrated causal state-space model is not the same tested hypothesis.

EXISTING_COMPONENTS_REUSABLE: Main-number history, exact baseline and blocked chronology.

NEW_COMPONENT_REQUIRED: State-space prior/transition, deterministic inference, calibration and legal ticket constructor.

HISTORICAL_TEST_POSSIBLE: YES

FORWARD_TEST_POSSIBLE: YES

EXPECTED_COST: HIGH

NOVELTY: HIGH

ORTHOGONALITY: HIGH

TRACK_B_PRIORITY: TIER_2_EXPLORE_AFTER

## §10 Track B Recommended First Experiment

TRACK_B_RECOMMENDED_FIRST_EXPERIMENT: H01 CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR

### 10.1 Observable question

At a fixed 5-ticket budget, can a deterministic selector using only strictly prior information choose among the 20 causally reconstructed provisional candidates and improve OFFICIAL_ANY_PRIZE and prespecified Hit Depth relative to:

1. exact same-ticket IID legal random;
2. one frozen static candidate chosen on discovery only;
3. static equal-weight/consensus allocation;
4. a result-blind simple regime-only selector?

### 10.2 Minimal experiment contract

1. Use the existing 20-candidate stored causal portfolios at 5 tickets; do not depend on Candidate Freeze V1.
2. Build per-target features only from earlier targets:
   - rolling strategy residuals versus matched baseline;
   - cross-strategy disagreement;
   - 50/300/750 performance slope;
   - the four already frozen regime features;
   - portfolio overlap/coverage diagnostics.
3. Freeze one primary outcome before evaluation: OFFICIAL_ANY_PRIZE at exactly five tickets.
4. Freeze one secondary family: M2+/M3+ hit-depth, with its own multiplicity rule.
5. Use expanding-window or nested blocked folds. A target's outcome may train only later targets.
6. Restrict the gate to a small, prespecified model class; compare against a simple regime-only gate to expose overfitting.
7. Keep candidate portfolios and target outcomes untouched; write results only to a new, versioned Branch-B research root.
8. If historical confirmation passes, create a separate shadow observer over only experts with verified forward paths.

### 10.3 Why first

- NOVELTY: It tests dynamic error complementarity, not another static heuristic.
- TESTABILITY: The required 20-candidate causal portfolio matrix already exists.
- REUSE: Regime, hit-depth, random-baseline and portfolio-geometry components are available.
- COST: Medium; no neural training or full 392,084-combination search is required.
- FORWARD_PATH: A shadow selector can operate over a small verified expert subset without reusing Cohort V1.
- ORTHOGONALITY: It can capture state-dependent differences even when every individual strategy lacks a global corrected edge.

STOP RULE: If the selector does not beat both the frozen static candidate and regime-only gate under the prespecified blocked test, record a scoped negative result and do not promote it.

## §11 Reusable Existing Capabilities

| Capability | Status | Reuse boundary |
|---|---|---|
| 133-strategy raw historical foundation | REUSE_AVAILABLE | Preserve original identity/native semantics and causal ordering |
| Hit Depth projection | REUSE_AVAILABLE | 133 strategies, four windows, hit-depth outcomes; do not treat as forward capability |
| Exact multiplicity-aware / ticket-count baselines | REUSE_AVAILABLE | Reuse only when the null and ticket semantics match |
| Binomial / Poisson-binomial exact retrospective tests | REUSE_AVAILABLE | New conditional or paired hypotheses may require a new null |
| Bonferroni 17,024-cell correction | REUSE_AVAILABLE_AS_HISTORICAL_REFERENCE | A changed family requires a new correction universe |
| BH-FDR exploratory mechanism | REUSE_AVAILABLE | Must freeze the new family and dependence interpretation |
| Predictable-Bernoulli mixture e-process | REUSE_AVAILABLE | Prospective only; new candidates need fresh states and correction family |
| A CURRENT_PORTFOLIO_VOTE_PROXY | REUSE_AVAILABLE | Not strategy internal ranking |
| C TRAILING_WINDOW_FREQUENCY_PROXY | REUSE_AVAILABLE | Exact horizon must be frozen |
| 20-candidate causal regime matrix | REUSE_AVAILABLE | Exploratory historical evidence, not deployment proof |
| Portfolio overlap / exact anti-bias geometry | REUSE_AVAILABLE | Removes structural handicap; does not create predictive edge |
| Candidate-K direct matrix | REUSE_AVAILABLE_FOR_7 | Does not cover the 44 aggregation-missing identities |

NEW_RESEARCH_LAYER_REQUIRED when a new hypothesis changes:

- null model;
- conditional or paired comparator;
- nested calibration;
- target-level outcome mapping;
- ticket budget;
- candidate family;
- forward producer/horizon identity.

## §12 Unknown / Needs Verification

1. [Unknown] Exact per-family membership among the 51 current-executable historical identities.
2. [Unknown] Which of the 44 portfolio identities can obtain a canonical number-level path without altering their semantics.
3. [Unknown] Downstream forward availability of the 20 C candidates after a horizon is frozen.
4. [Unknown] R4 full fresh-bounded Judge outcome.
5. [Unknown] Real-world outcomes after locally sealed draw 115000075; network validation was not authorized.
6. [Unknown] Statistical performance of any external GitHub method under this project's data/contract.
7. [Unknown] Whether Bayesian/LSTM/Transformer implementations can be made deterministic and contract-faithful; closed historical identities are not parity evidence.
8. [Unknown] EWMA threshold robustness beyond the exact frozen q67 point because the authorized aggregates cannot identify alternate-threshold successes.
9. [Unknown] A truly prospective edge for any candidate: post-freeze calendar count remains 0.

## §13 Concurrent Workspace Drift / No-Write Record

CONCURRENT_WORKTREE_DRIFT_OBSERVED: YES

CONCURRENT_BRANCH_DRIFT_OBSERVED: YES

INITIAL_BRANCH_AT_RESUME: main

CURRENT_BRANCH_AT_FINAL_VERIFICATION: codex/b649-horizon-minimax-target-native-migration-r1

FOREIGN_DIRTY_STATE_PRESENT: YES

TASK_CREATED_REPO_CHANGE: NO

TASK_CAUSED_REPO_MUTATION: NO

REPO_MUTATION_BY_TRACK_D: NONE

DB_MUTATION: NONE

SEALED_TASK_DATA_MUTATION: NONE

PROSPECTIVE_OBSERVATION_MUTATION: NONE

CANDIDATE_FREEZE_MUTATION: NONE

FOREIGN_CONCURRENT_REPO_CHANGES_PRESERVED: YES

SCRATCHPAD_OUTPUT_CREATED: /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_RESEARCH_SURFACE_R1.md

The scratchpad is outside the MathStatisticalAnalysis repository and outside every sealed .task-data/B649_* root.

No reset, restore, checkout, clean, stash, stage, commit, amend, revert, push, pull, fetch, re-freeze, prospective observation, database write or production operation was performed by Track D.

## Final Boundary

This document is a historical research map and experiment queue. It does not modify Candidate Freeze, certify Forward Observer R4, authorize Cohort V2, claim future predictive advantage, or act as R4 Judge.

END
