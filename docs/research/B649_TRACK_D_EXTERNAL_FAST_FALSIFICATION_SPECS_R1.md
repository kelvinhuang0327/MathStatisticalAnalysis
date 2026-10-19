# B649 Track D External Fast-Falsification Specifications R1

Task: `B649_TRACK_D_EXTERNAL_RESEARCH_FRONTIER_EXPANSION_R1`

Status: specification only. No strategy was implemented, no model was trained, and no historical or prospective test was run. Every external efficacy statement remains `EXTERNAL_UNVERIFIED_CLAIM`; `LOCAL_VALIDATION_STATUS: NOT_RUN`.

## Shared causal protocol

- Use the current B649 historical authority only after a later Track B execution packet authorizes it. The present task does not read unsealed concurrent results.
- For prediction origin `t`, every feature, label-derived residual, calibration score, threshold, representation, hyperparameter, and strategy choice must be based on information available through `t-1`.
- Use nested expanding-window or rolling-origin evaluation. Any representation learning, feature scaling, rank selection, subgroup selection, multiplicity correction, and fallback threshold belongs inside the training fold.
- Compare against a frozen legal-ticket baseline and the closest existing hypothesis controls. Preserve raw per-origin outputs so paired loss differences can be audited.
- Treat abstention as a strategy-allocation signal. If the product must emit tickets, the abstaining candidate maps to a prespecified fallback rather than peeking at the outcome.
- A positive signal is exploratory until it survives the later Track B historical gate and separate prospective policy. A null or unstable result falsifies the proposed mechanism at the tested scale; it does not prove universal absence.

## EH01 — Matrix-profile motif/discord regime allocator

- `HYPOTHESIS_ID`: EH01
- `TITLE`: MATRIX_PROFILE_MOTIF_DISCORD_REGIME_ALLOCATOR
- `SOURCE_INSPIRATION`: S01; S02
- `WHY_NEW`: Existing H19/H20 can detect change or anomaly, but do not retrieve causal subsequence analogues or use analogue support as an allocation rule.
- `CLOSEST_EXISTING_HYPOTHESIS`: H19; H20
- `CLOSEST_EXISTING_STRATEGIES`: `predict_evolutionary_gum`; `dynamic_frequency_predictor`; `feature_discovery_and_retrospective`; `optimize_deviation_extreme_generic`; `advanced_methods_benchmark`
- `MINIMUM_DATA`: Ordered draw summaries plus out-of-fold residual streams for at least two frozen strategy families; enough origins for non-overlapping windows at three prespecified lengths.
- `DERIVED_FEATURES`: Z-normalized causal subsequences; matrix-profile distance; motif support count; discord score; boundary score.
- `TARGET`: Next-origin strategy loss difference or fixed abstention/fallback choice.
- `COMPARATOR`: H19-style single changepoint statistic; H20-style scalar anomaly gate; ungated best frozen strategy.
- `TEMPORAL_DESIGN`: Inner folds select one window length and thresholds; outer expanding walk-forward emits one action per origin.
- `LEAKAGE_GUARD`: Exclude the query subsequence and all future-overlapping subsequences from nearest-neighbor search; fit normalization inside each fold.
- `EXPECTED_COST`: LOW to MEDIUM; deterministic CPU transform with no training beyond threshold selection.
- `SUCCESS_SIGNAL`: Supported motifs show a directionally consistent paired-loss improvement versus all three controls and discords correctly favor the prespecified fallback without coverage collapse.
- `FAILURE_SIGNAL`: Analogue states are unstable; support is sparse; or outer-fold loss is no better than the simplest H19/H20 control.
- `IF_POSITIVE_NEXT`: Freeze one window and one allocation map for a full Track B historical test before any prospective use.

## EH02 — Transfer-entropy directed lag graph

- `HYPOTHESIS_ID`: EH02
- `TITLE`: TRANSFER_ENTROPY_DIRECTED_LAG_GRAPH
- `SOURCE_INSPIRATION`: S03; S04
- `WHY_NEW`: H11–H13 model association or structural change, not conditional directed information flow from one past stream to another.
- `CLOSEST_EXISTING_HYPOTHESIS`: H11; H12; H13
- `CLOSEST_EXISTING_STRATEGIES`: `cooccurrence_graph`; `graph_predictor`; `backtest_graph_method`; `hot_cooccurrence_analyzer`; `verify_markov_vs_triple_2bet`
- `MINIMUM_DATA`: Ordered binary number indicators and/or frozen-strategy residual signs with adequate samples per prespecified lag.
- `DERIVED_FEATURES`: Conditional transfer entropy; directionality asymmetry; surrogate-null adjusted edge strength; edge stability across inner folds.
- `TARGET`: Per-number residual rank or strategy-family loss difference.
- `COMPARATOR`: Lagged mutual information; co-occurrence graph score; fixed-order Markov feature.
- `TEMPORAL_DESIGN`: Estimate edges only in training history; apply the frozen stable-edge set to the next outer segment.
- `LEAKAGE_GUARD`: Surrogates are generated within training folds; embeddings and discretization never use outer outcomes.
- `EXPECTED_COST`: MEDIUM; estimator and surrogate computation dominate.
- `SUCCESS_SIGNAL`: A small stable directed edge set improves the prespecified rank/loss target beyond undirected and Markov controls across at least two outer periods.
- `FAILURE_SIGNAL`: Edges disappear under surrogate adjustment or fail to transfer across adjacent outer periods.
- `IF_POSITIVE_NEXT`: Test a sparse frozen edge graph with multiplicity control and no estimator search.

## EH03 — Recurrence-quantification state gate

- `HYPOTHESIS_ID`: EH03
- `TITLE`: RECURRENCE_QUANTIFICATION_STATE_GATE
- `SOURCE_INSPIRATION`: S27
- `WHY_NEW`: Recurrence geometry over embedded states is distinct from H18 latent-state labels and H20 scalar entropy/distribution-shift alarms.
- `CLOSEST_EXISTING_HYPOTHESIS`: H18; H20
- `CLOSEST_EXISTING_STRATEGIES`: `predict_evolutionary_gum`; `optimize_deviation_extreme_generic`; `attention_replay_predictor`; `feature_discovery_and_retrospective`; `dynamic_frequency_predictor`
- `MINIMUM_DATA`: Ordered multivariate draw/residual summaries long enough for a bounded delay embedding and multiple outer folds.
- `DERIVED_FEATURES`: Recurrence rate; determinism; laminarity; trapping time; diagonal-length summaries.
- `TARGET`: Conditional strategy loss or abstention benefit.
- `COMPARATOR`: Raw lag-vector nearest neighbors; H20 entropy gate; constant allocation.
- `TEMPORAL_DESIGN`: Choose one embedding and radius policy in inner folds; compute each origin from the trailing window only.
- `LEAKAGE_GUARD`: No full-series distance normalization or recurrence threshold; overlapping target windows are blocked in resampling.
- `EXPECTED_COST`: LOW to MEDIUM.
- `SUCCESS_SIGNAL`: One predeclared recurrence state replicates a conditional strategy-loss difference with adequate support and beats raw-distance controls.
- `FAILURE_SIGNAL`: Conditional effects vanish after minimum-support and multiplicity rules or depend on a single radius.
- `IF_POSITIVE_NEXT`: Freeze the smallest stable descriptor set and test it as a gate only.

## EH04 — Context-tree-weighted symbolic residual forecaster

- `HYPOTHESIS_ID`: EH04
- `TITLE`: CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER
- `SOURCE_INSPIRATION`: S28
- `WHY_NEW`: CTW averages variable-depth contexts through a compression objective; fixed-order Markov and existing state-space hypotheses do not implement that mechanism.
- `CLOSEST_EXISTING_HYPOTHESIS`: H07; H17
- `CLOSEST_EXISTING_STRATEGIES`: `backtest_biglotto_markov_4bet`; `backtest_markov_repeat_exception`; `verify_markov_vs_triple_2bet`; `biglotto_2bet_final`; `attention_replay_predictor`
- `MINIMUM_DATA`: Ordered symbol streams from binary appearances, gap bins, rank bins, or residual signs; one alphabet fixed before evaluation.
- `DERIVED_FEATURES`: CTW posterior predictive probability; excess code length versus IID; selected-context posterior mass.
- `TARGET`: Per-number log loss or frozen-strategy residual sign.
- `COMPARATOR`: IID/uniform; fixed-order Markov depths 1–3; trailing-frequency probability.
- `TEMPORAL_DESIGN`: Prequential update; maximum depth and alphabet chosen inside training folds.
- `LEAKAGE_GUARD`: Symbol bin edges and depth are fit on prior data only; no full-history compression dictionary.
- `EXPECTED_COST`: LOW.
- `SUCCESS_SIGNAL`: CTW reduces outer prequential log loss and retains improvement after probability calibration relative to every fixed-order control.
- `FAILURE_SIGNAL`: Code length and predictive loss match IID or the best fixed-order Markov control.
- `IF_POSITIVE_NEXT`: Carry only the winning alphabet and depth cap into a Track B residual-ranking test.

## EH05 — Density-ratio importance-weighted recalibration

- `HYPOTHESIS_ID`: EH05
- `TITLE`: DENSITY_RATIO_IMPORTANCE_WEIGHTED_RECALIBRATION
- `SOURCE_INSPIRATION`: S05; S30
- `WHY_NEW`: Existing calibration and shift hypotheses do not reweight historical calibration examples by an estimated recent/reference covariate ratio with an effective-sample-size fallback.
- `CLOSEST_EXISTING_HYPOTHESIS`: H07; H20
- `CLOSEST_EXISTING_STRATEGIES`: `dynamic_frequency_predictor`; `backtest_biglotto_6bet_ewma`; `feature_discovery_and_retrospective`; `exhaustive_feature_sweep_v2`; `predict_evolutionary_gum`
- `MINIMUM_DATA`: Out-of-fold per-number scores; causal state covariates; recent and reference calibration windows.
- `DERIVED_FEATURES`: Direct density-ratio weights; clipping indicator; effective sample size; balance residuals.
- `TARGET`: Per-number Brier/log loss and downstream M1+/M2+ ticket objective.
- `COMPARATOR`: Unweighted calibration; fixed EWMA weights; recent-window-only calibration.
- `TEMPORAL_DESIGN`: Re-estimate weights at each outer origin from covariates through `t-1`; tune clipping only in inner folds.
- `LEAKAGE_GUARD`: Density-ratio labels identify windows, never outcomes; calibration residuals are strictly out of fold.
- `EXPECTED_COST`: LOW to MEDIUM.
- `SUCCESS_SIGNAL`: Weighted calibration improves proper scoring and downstream target while ESS and balance remain within prespecified safety bounds.
- `FAILURE_SIGNAL`: Weights collapse ESS; balance fails; or improvements vanish against EWMA/recent-window controls.
- `IF_POSITIVE_NEXT`: Freeze covariates and clipping rule; test whether gains survive ticket construction.

## EH06 — Hawkes excitation/inhibition residual scorer

- `HYPOTHESIS_ID`: EH06
- `TITLE`: HAWKES_EXCITATION_INHIBITION_RESIDUAL_SCORER
- `SOURCE_INSPIRATION`: S18; S19
- `WHY_NEW`: The 28 contain lagged pair/triple and state-space hypotheses but no marked event-intensity mechanism with excitation or inhibition kernels.
- `CLOSEST_EXISTING_HYPOTHESIS`: H11; H12; H17
- `CLOSEST_EXISTING_STRATEGIES`: `cooccurrence_graph`; `backtest_biglotto_markov_4bet`; `graph_predictor`; `hot_cooccurrence_analyzer`; `verify_markov_vs_triple_2bet`
- `MINIMUM_DATA`: Ordered event times for appearances or frozen-strategy errors; restrict to a small prespecified number/group set.
- `DERIVED_FEATURES`: Baseline intensity; self/cross excitation; inhibition proxy; compensator residuals.
- `TARGET`: Next-draw residual rank or strategy error risk.
- `COMPARATOR`: Memoryless Bernoulli/Poisson event model; fixed-order Markov; co-occurrence score.
- `TEMPORAL_DESIGN`: Fit regularized kernels on expanding training history and score only the next outer block.
- `LEAKAGE_GUARD`: Fixed event definition and kernel family; stability/branching constraints checked before scoring outer data.
- `EXPECTED_COST`: MEDIUM to HIGH.
- `SUCCESS_SIGNAL`: Stable sparse kernels yield calibrated intensity residuals and repeat a directional rank/loss gain beyond all simpler event controls.
- `FAILURE_SIGNAL`: Instability; non-identifiability; null-simulation false alarms; or no outer gain.
- `IF_POSITIVE_NEXT`: Reduce to the smallest stable marked process and rerun with a locked penalty.

## EH07 — NVAR/reservoir causal residual meta-feature

- `HYPOTHESIS_ID`: EH07
- `TITLE`: NVAR_RESERVOIR_CAUSAL_RESIDUAL_META_FEATURE
- `SOURCE_INSPIRATION`: S20; S21
- `WHY_NEW`: This uses a low-capacity dynamical representation for residuals rather than another direct LSTM/Transformer or static stacking model.
- `CLOSEST_EXISTING_HYPOTHESIS`: H17; H23; H25
- `CLOSEST_EXISTING_STRATEGIES`: `attention_replay_predictor`; `benchmark_ai`; `quick_ml_predict`; `evolution_engine`; `xgboost_model`
- `MINIMUM_DATA`: Causal lag vectors and frozen-strategy residual targets; enough folds for regularization selection.
- `DERIVED_FEATURES`: Polynomial NVAR terms or fixed reservoir states; ridge-fitted residual prediction.
- `TARGET`: Strategy loss difference or per-number residual.
- `COMPARATOR`: Linear autoregression; XGBoost stacking; small LSTM residual model if later authorized.
- `TEMPORAL_DESIGN`: Architecture seed and feature order fixed inside training; outer predictions use only past reservoir states.
- `LEAKAGE_GUARD`: No bidirectional states; scaling and ridge penalties refit per fold; retain seed ledger.
- `EXPECTED_COST`: MEDIUM.
- `SUCCESS_SIGNAL`: A small NVAR/reservoir consistently beats linear AR and static nonlinear controls without sensitivity to seed or feature order.
- `FAILURE_SIGNAL`: Gain disappears under seed replication or equals a linear lag model.
- `IF_POSITIVE_NEXT`: Freeze one deterministic NVAR basis before any larger reservoir search.

## EH08 — Persistent-homology rolling structure gate

- `HYPOTHESIS_ID`: EH08
- `TITLE`: PERSISTENT_HOMOLOGY_ROLLING_STRUCTURE_GATE
- `SOURCE_INSPIRATION`: S22; S23
- `WHY_NEW`: Persistent topological summaries of rolling state clouds or graphs are absent from H12/H13/H20.
- `CLOSEST_EXISTING_HYPOTHESIS`: H12; H13; H20
- `CLOSEST_EXISTING_STRATEGIES`: `cooccurrence_graph`; `graph_predictor`; `backtest_graph_method`; `predict_evolutionary_gum`; `feature_discovery_and_retrospective`
- `MINIMUM_DATA`: Causal delay embeddings or weighted structural graphs across multiple non-overlapping windows.
- `DERIVED_FEATURES`: Persistence diagrams; total persistence; landscape norms; Betti-curve summaries.
- `TARGET`: Conditional strategy loss or anomaly/fallback action.
- `COMPARATOR`: Graph density; connected components; PCA variance; H20 scalar anomaly.
- `TEMPORAL_DESIGN`: Fix filtration and scale policy in inner folds; compute rolling summaries through `t-1` only.
- `LEAKAGE_GUARD`: No global distance scaling; topology feature selection remains inside training; small fixed descriptor set.
- `EXPECTED_COST`: HIGH relative to other fast falsifications.
- `SUCCESS_SIGNAL`: Topological descriptors add stable outer information beyond simple graph and PCA summaries.
- `FAILURE_SIGNAL`: Effect is scale-sensitive; support-poor; or fully explained by simple graph density.
- `IF_POSITIVE_NEXT`: Retain one descriptor and one filtration for a locked replication.

## EH09 — Strategy×draw×metric tensor-factor residual gate

- `HYPOTHESIS_ID`: EH09
- `TITLE`: STRATEGY_DRAW_METRIC_TENSOR_FACTOR_RESIDUAL_GATE
- `SOURCE_INSPIRATION`: S24; S25
- `WHY_NEW`: H03 stacks flat predictions; this hypothesis models explicit strategy-by-time-by-metric interactions with low-rank factors.
- `CLOSEST_EXISTING_HYPOTHESIS`: H03; H11; H12
- `CLOSEST_EXISTING_STRATEGIES`: `advanced_methods_benchmark`; `optimized_ensemble`; `dynamic_ensemble_predictor`; `feature_discovery_and_retrospective`; `xgboost_model`
- `MINIMUM_DATA`: Aligned out-of-fold residuals for several frozen strategies and at least two prespecified metrics or number groups.
- `DERIVED_FEATURES`: Regularized CP/Tucker factors; reconstruction residual; factor stability.
- `TARGET`: Next-origin strategy loss or allocation.
- `COMPARATOR`: Flat ridge stacking; per-strategy EWMA; matrix factorization with the metric mode collapsed.
- `TEMPORAL_DESIGN`: Fit rank and factors on training tensor only; score the next outer time slab.
- `LEAKAGE_GUARD`: Missing future cells remain missing; rank selection and component alignment occur per inner fold.
- `EXPECTED_COST`: MEDIUM.
- `SUCCESS_SIGNAL`: Multiway factors improve outer allocation beyond both flat and collapsed controls with stable component alignment.
- `FAILURE_SIGNAL`: Rank is unstable or any gain is reproduced by simple strategy EWMA.
- `IF_POSITIVE_NEXT`: Freeze tensor axes and smallest sufficient rank.

## EH10 — Permutation-entropy ordinal state gate

- `HYPOTHESIS_ID`: EH10
- `TITLE`: PERMUTATION_ENTROPY_ORDINAL_STATE_GATE
- `SOURCE_INSPIRATION`: S26; S40
- `WHY_NEW`: It is a specific ordinal-complexity extension of H20, not a generic claim that entropy predicts lottery outcomes.
- `CLOSEST_EXISTING_HYPOTHESIS`: H20
- `CLOSEST_EXISTING_STRATEGIES`: `predict_evolutionary_gum`; `feature_discovery_and_retrospective`; `optimize_deviation_extreme_generic`; `dynamic_frequency_predictor`; `attention_replay_predictor`
- `MINIMUM_DATA`: Ordered scalar or low-dimensional draw/residual summaries with enough patterns for fixed orders 3–5.
- `DERIVED_FEATURES`: Permutation entropy; ordinal-pattern occupancy; missing-pattern count.
- `TARGET`: Conditional strategy loss or abstention benefit.
- `COMPARATOR`: Shannon entropy; sample entropy; raw variance; constant gate.
- `TEMPORAL_DESIGN`: Window/order fixed in inner folds; each value uses data through `t-1`.
- `LEAKAGE_GUARD`: No full-history normalization or post hoc choice among many summaries.
- `EXPECTED_COST`: LOW.
- `SUCCESS_SIGNAL`: One ordinal descriptor improves a predeclared conditional allocation target beyond Shannon and variance controls.
- `FAILURE_SIGNAL`: No replicated conditional effect or the signal is identical to variance/window length.
- `IF_POSITIVE_NEXT`: Freeze the single order/window and test alongside H20.

## EH11 — MMD joint-distribution shift allocator

- `HYPOTHESIS_ID`: EH11
- `TITLE`: MMD_JOINT_DISTRIBUTION_SHIFT_ALLOCATOR
- `SOURCE_INSPIRATION`: S10; S11; S12
- `WHY_NEW`: H20 is broader; MMD supplies a concrete multivariate two-sample transformation and fixed allocation action.
- `CLOSEST_EXISTING_HYPOTHESIS`: H20
- `CLOSEST_EXISTING_STRATEGIES`: `predict_evolutionary_gum`; `optimize_deviation_extreme_generic`; `feature_discovery_and_retrospective`; `dynamic_frequency_predictor`; `backtest_biglotto_6bet_ewma`
- `MINIMUM_DATA`: Recent/reference causal multivariate feature windows and frozen-strategy residual outcomes.
- `DERIVED_FEATURES`: MMD statistic; calibrated alarm; kernel-bandwidth diagnostics.
- `TARGET`: Post-alarm strategy loss difference or fallback value.
- `COMPARATOR`: Marginal KS/energy summaries; scalar entropy gate; no alarm.
- `TEMPORAL_DESIGN`: Thresholds calibrated on earlier windows; alarm at `t` affects actions from `t+1`.
- `LEAKAGE_GUARD`: Kernel and threshold chosen in training; no reuse of post-alarm outcomes to label the alarm.
- `EXPECTED_COST`: LOW to MEDIUM.
- `SUCCESS_SIGNAL`: MMD alarms identify a supported interval where the fixed action improves paired loss beyond scalar controls.
- `FAILURE_SIGNAL`: Alarm rate is unstable; effect starts before the alarm; or scalar controls explain it.
- `IF_POSITIVE_NEXT`: Freeze one feature set and bandwidth rule for historical replication.

## EH12 — Wasserstein-window shift allocator

- `HYPOTHESIS_ID`: EH12
- `TITLE`: WASSERSTEIN_WINDOW_SHIFT_ALLOCATOR
- `SOURCE_INSPIRATION`: S31
- `WHY_NEW`: It adds distribution geometry to H19/H20 rather than merely renaming a changepoint detector.
- `CLOSEST_EXISTING_HYPOTHESIS`: H19; H20
- `CLOSEST_EXISTING_STRATEGIES`: `predict_evolutionary_gum`; `optimize_deviation_extreme_generic`; `dynamic_frequency_predictor`; `backtest_biglotto_6bet_ewma`; `feature_discovery_and_retrospective`
- `MINIMUM_DATA`: Ordered recent/reference empirical feature distributions.
- `DERIVED_FEATURES`: Sliced-Wasserstein or low-dimensional Wasserstein distance; alarm persistence.
- `TARGET`: Fixed post-shift strategy allocation or abstention.
- `COMPARATOR`: MMD; energy distance; scalar mean/variance shift.
- `TEMPORAL_DESIGN`: Backward-only windows; threshold calibrated in training; action delayed one origin.
- `LEAKAGE_GUARD`: Scaling and projection directions fit before the outer block; no outcome-conditioned projections.
- `EXPECTED_COST`: LOW to MEDIUM.
- `SUCCESS_SIGNAL`: Transport alarms support an allocation effect not captured by MMD or marginal shifts.
- `FAILURE_SIGNAL`: Distances are dimension/scale artifacts or do not precede the conditional effect.
- `IF_POSITIVE_NEXT`: Lock the cheapest stable transport approximation.

## EH13 — Conformal set-size/coverage abstention

- `HYPOTHESIS_ID`: EH13
- `TITLE`: CONFORMAL_SET_SIZE_COVERAGE_ABSTENTION
- `SOURCE_INSPIRATION`: S13; S14; S15
- `WHY_NEW`: H07/H09 estimate probabilities or uncertainty; this combination turns calibrated set size and coverage into a reject/allocation action.
- `CLOSEST_EXISTING_HYPOTHESIS`: H07; H09
- `CLOSEST_EXISTING_STRATEGIES`: `predict_6expert`; `optimized_ensemble`; `predict_consensus_ensemble`; `biglotto_diversified_ensemble_v6`; `hybrid_integration_benchmark`
- `MINIMUM_DATA`: Strictly out-of-fold per-number scores; rolling calibration residuals; fixed fallback strategy.
- `DERIVED_FEATURES`: Conformal candidate-set size; empirical coverage error; risk-control upper bound.
- `TARGET`: Loss conditional on acting; coverage; action rate; fallback-adjusted overall loss.
- `COMPARATOR`: Raw probability threshold; entropy/disagreement gate; always-act policy.
- `TEMPORAL_DESIGN`: Rolling calibration precedes each outer prediction; thresholds fixed per training fold.
- `LEAKAGE_GUARD`: Calibration examples never share labels with model training predictions; report selective and overall risk together.
- `EXPECTED_COST`: LOW to MEDIUM.
- `SUCCESS_SIGNAL`: A prespecified set-size/coverage rule improves fallback-adjusted loss while meeting coverage and minimum-action constraints.
- `FAILURE_SIGNAL`: Apparent selective gain is entirely due to tiny action rate or coverage fails.
- `IF_POSITIVE_NEXT`: Freeze one risk level and fallback mapping for Track B.

## EH14 — Context-conditioned MMD drift gate

- `HYPOTHESIS_ID`: EH14
- `TITLE`: CONTEXT_CONDITIONED_MMD_DRIFT_GATE
- `SOURCE_INSPIRATION`: S10; S11; S12
- `WHY_NEW`: It tests whether a global null masks context-specific joint shift, combining H18/H20 with prespecified conditional analysis.
- `CLOSEST_EXISTING_HYPOTHESIS`: H18; H20
- `CLOSEST_EXISTING_STRATEGIES`: `predict_evolutionary_gum`; `biglotto_diversified_ensemble_v6`; `predict_6expert`; `feature_discovery_and_retrospective`; `optimize_deviation_extreme_generic`
- `MINIMUM_DATA`: Predeclared context labels with adequate counts and multivariate residual features.
- `DERIVED_FEATURES`: Within-context MMD; context support; multiplicity-adjusted alarm.
- `TARGET`: Context-conditional strategy loss difference.
- `COMPARATOR`: Global MMD; context-only gate; no-shift allocation.
- `TEMPORAL_DESIGN`: Context definition and alpha allocation fixed before outer evaluation; alarm affects later actions.
- `LEAKAGE_GUARD`: No post hoc context mining; minimum support; inner-only kernel selection.
- `EXPECTED_COST`: MEDIUM.
- `SUCCESS_SIGNAL`: A prespecified context produces replicated adjusted drift and a later allocation effect beyond both component controls.
- `FAILURE_SIGNAL`: Result fails multiplicity/support rules or is explained by global drift alone.
- `IF_POSITIVE_NEXT`: Test the single replicated context with a locked action.

## EH15 — Changepoint-triggered meta-selection

- `HYPOTHESIS_ID`: EH15
- `TITLE`: CHANGEPOINT_TRIGGERED_META_SELECTION
- `SOURCE_INSPIRATION`: S05; S06; S07
- `WHY_NEW`: The components H19 and H01/H03 exist separately; the hypothesis specifies how an alarm changes selector horizon or eligibility.
- `CLOSEST_EXISTING_HYPOTHESIS`: H01; H03; H19
- `CLOSEST_EXISTING_STRATEGIES`: `advanced_methods_benchmark`; `biglotto_diversified_ensemble_v6`; `predict_6expert`; `optimized_ensemble`; `predict_evolutionary_gum`
- `MINIMUM_DATA`: Frozen-strategy out-of-fold residual streams and at least one causal state feature.
- `DERIVED_FEATURES`: One prespecified ADWIN or Page-Hinkley alarm; time since alarm; local competence after alarm.
- `TARGET`: Strategy-selection loss versus fixed global selector.
- `COMPARATOR`: Alarm-only reset; selector-only; global best strategy.
- `TEMPORAL_DESIGN`: Minimal 2×2 component ablation in nested walk-forward; selection begins after alarm.
- `LEAKAGE_GUARD`: Detector sees residuals only after outcomes arrive; no retroactive segment labels; fixed minimum post-alarm sample.
- `EXPECTED_COST`: LOW.
- `SUCCESS_SIGNAL`: The combination beats both components and the global selector on paired outer losses with sufficient post-alarm coverage.
- `FAILURE_SIGNAL`: No interaction benefit or alarms leave too little data for competence estimation.
- `IF_POSITIVE_NEXT`: Freeze one detector and one horizon-switch rule.

## EH16 — Calibrated-probability × DPP portfolio

- `HYPOTHESIS_ID`: EH16
- `TITLE`: CALIBRATED_PROBABILITY_DPP_PORTFOLIO
- `SOURCE_INSPIRATION`: S13; S15; S16
- `WHY_NEW`: DPP alone exactly matches H14, but the quality kernel built from causally calibrated per-number probabilities is a testable H07×H14 combination.
- `CLOSEST_EXISTING_HYPOTHESIS`: H07; H14
- `CLOSEST_EXISTING_STRATEGIES`: `portfolio_optimizer`; `backtest_biglotto_portfolio`; `covering_strategy_research`; `biglotto_diversified_ensemble`; `orthogonal_diversification_benchmark`
- `MINIMUM_DATA`: Out-of-fold calibrated per-number scores; legal candidate tickets; fixed ticket count.
- `DERIVED_FEATURES`: Ticket log-quality; pairwise overlap kernel; DPP determinant or MAP objective.
- `TARGET`: Predeclared M1+/M2+/M3+ and coverage objective at fixed cost.
- `COMPARATOR`: Quality-only top tickets; diversity-only DPP; existing H14-style portfolio; random legal portfolio.
- `TEMPORAL_DESIGN`: Calibrate and tune kernel weights inside training; build tickets only after origin-specific probabilities are frozen.
- `LEAKAGE_GUARD`: Candidate generation and calibration are nested; no outcome-informed ticket pruning.
- `EXPECTED_COST`: MEDIUM.
- `SUCCESS_SIGNAL`: The combined kernel improves a predeclared portfolio target beyond both component ablations at identical ticket count.
- `FAILURE_SIGNAL`: Any gain is reproduced by quality-only ranking or diversity reduces calibrated value.
- `IF_POSITIVE_NEXT`: Lock quality transform; similarity kernel; and ticket count for Track B.

## EH17 — State-space posterior × multiwindow disagreement

- `HYPOTHESIS_ID`: EH17
- `TITLE`: STATE_SPACE_POSTERIOR_MULTIWINDOW_DISAGREEMENT
- `SOURCE_INSPIRATION`: S09; S21
- `WHY_NEW`: The mechanism combines H17 posterior state uncertainty with H04 short/medium/long-window disagreement.
- `CLOSEST_EXISTING_HYPOTHESIS`: H04; H17
- `CLOSEST_EXISTING_STRATEGIES`: `dynamic_frequency_predictor`; `backtest_biglotto_6bet_ewma`; `feature_discovery_and_retrospective`; `attention_replay_predictor`; `predict_evolutionary_gum`
- `MINIMUM_DATA`: Causal state summaries and three frozen window predictors with out-of-fold residuals.
- `DERIVED_FEATURES`: Posterior state probability; posterior entropy; pairwise window disagreement; slope sign pattern.
- `TARGET`: Strategy loss or abstention benefit.
- `COMPARATOR`: State-only gate; disagreement-only gate; best single window.
- `TEMPORAL_DESIGN`: State model and thresholds refit per training fold; one-step-delayed action.
- `LEAKAGE_GUARD`: Filtering not smoothing; no future state estimates; windows all end at `t-1`.
- `EXPECTED_COST`: MEDIUM.
- `SUCCESS_SIGNAL`: A prespecified posterior×disagreement interaction beats both component gates across outer folds.
- `FAILURE_SIGNAL`: No interaction or filtered state is too uncertain to support allocation.
- `IF_POSITIVE_NEXT`: Freeze one state model and one disagreement category.

## EH18 — E-process anytime-valid promotion/abstention gate

- `HYPOTHESIS_ID`: EH18
- `TITLE`: E_PROCESS_ANYTIME_VALID_PROMOTION_ABSTENTION_GATE
- `SOURCE_INSPIRATION`: S29
- `WHY_NEW`: H22/H28 cover nested nulls and prospective confirmation, but not an explicitly optional-stopping-safe promotion/suspension action.
- `CLOSEST_EXISTING_HYPOTHESIS`: H22; H28
- `CLOSEST_EXISTING_STRATEGIES`: `scientific_baseline_report`; `rgf_walkforward_validator`; `advanced_methods_benchmark`; `historical_audit_rigorous`; `exhaustive_feature_sweep_v2`
- `MINIMUM_DATA`: Sequential bounded or otherwise e-process-compatible paired loss differences for one frozen candidate and baseline.
- `DERIVED_FEATURES`: E-value; running e-process; threshold-crossing time; drawdown.
- `TARGET`: Research promotion; continuation; demotion; or fallback action rather than number prediction.
- `COMPARATOR`: Fixed-horizon test; unadjusted repeated monitoring; H28 EWMA confirmation.
- `TEMPORAL_DESIGN`: Prespecify betting function and thresholds; update once per realized outer outcome.
- `LEAKAGE_GUARD`: Candidate and loss are frozen before monitoring; no tuning from the same e-process path.
- `EXPECTED_COST`: LOW.
- `SUCCESS_SIGNAL`: Simulated-null calibration is valid and a genuine synthetic/known control crosses as designed; later real evidence is interpretable under optional stopping.
- `FAILURE_SIGNAL`: Null calibration fails or bounded-loss assumptions cannot be met.
- `IF_POSITIVE_NEXT`: Adopt only as a Track B research-governance gate after owner approval.

## EH25 — TS2Vec causal residual embedding

- `HYPOTHESIS_ID`: EH25
- `TITLE`: TS2VEC_CAUSAL_RESIDUAL_EMBEDDING
- `SOURCE_INSPIRATION`: S33; S34
- `WHY_NEW`: H23–H25 are supervised residual models; this uses a self-supervised temporal representation and a frozen simple head.
- `CLOSEST_EXISTING_HYPOTHESIS`: H23; H24; H25
- `CLOSEST_EXISTING_STRATEGIES`: `attention_replay_predictor`; `benchmark_ai`; `evolution_engine`; `quick_ml_predict`; `xgboost_model`
- `MINIMUM_DATA`: Multichannel causal sequences with enough training windows for contrastive batches; strict compute budget.
- `DERIVED_FEATURES`: Causal hierarchical contrastive embeddings; embedding stability; nearest-neighbor support.
- `TARGET`: Frozen-strategy residual or allocation with a linear head.
- `COMPARATOR`: Raw lags plus ridge; PCA lags; supervised LSTM/Transformer residual controls.
- `TEMPORAL_DESIGN`: Train the encoder separately inside each outer training fold; causal sliding inference only.
- `LEAKAGE_GUARD`: No full-series pretraining; augmentations cannot cross the prediction origin; seeds and checkpoints logged.
- `EXPECTED_COST`: HIGH.
- `SUCCESS_SIGNAL`: Embeddings improve outer residual loss over raw/PCA features and remain stable across seeds without a complex head.
- `FAILURE_SIGNAL`: Gain needs future context; disappears across seeds; or is matched by ridge on raw lags.
- `IF_POSITIVE_NEXT`: Freeze one encoder size and augmentation set before any broader neural search.

## EH26 — Stationary vine-copula residual dependence

- `HYPOTHESIS_ID`: EH26
- `TITLE`: STATIONARY_VINE_COPULA_RESIDUAL_DEPENDENCE
- `SOURCE_INSPIRATION`: S35; S36
- `WHY_NEW`: H07 calibrates marginals and H11 studies pairs/triples; a vine explicitly separates calibrated marginals from conditional higher-order and tail dependence.
- `CLOSEST_EXISTING_HYPOTHESIS`: H07; H11
- `CLOSEST_EXISTING_STRATEGIES`: `cooccurrence_graph`; `backtest_apriori`; `hot_cooccurrence_analyzer`; `graph_predictor`; `verify_markov_vs_triple_2bet`
- `MINIMUM_DATA`: Continuous or randomized calibrated residuals for a small prespecified set of numbers/strategies.
- `DERIVED_FEATURES`: Pair-copula family; conditional tail probability; vine edge stability; joint surprise.
- `TARGET`: Joint error risk; portfolio overlap risk; or conditional allocation.
- `COMPARATOR`: Independence copula; Gaussian copula; pairwise correlation/co-occurrence.
- `TEMPORAL_DESIGN`: Fit marginals and vine structure inside training; outer joint scores use frozen parameters.
- `LEAKAGE_GUARD`: Dimension and variable set prespecified; structure selection nested; randomized transforms seeded.
- `EXPECTED_COST`: MEDIUM to HIGH.
- `SUCCESS_SIGNAL`: A sparse stable vine improves outer joint log score and an allocation target beyond Gaussian/pairwise controls.
- `FAILURE_SIGNAL`: Structure is unstable or joint-score gain does not translate to the target.
- `IF_POSITIVE_NEXT`: Lock the smallest variable set and pair-copula families.

## EH27 — Sparse subset-scan conditional edge gate

- `HYPOTHESIS_ID`: EH27
- `TITLE`: SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE
- `SOURCE_INSPIRATION`: S32
- `WHY_NEW`: It asks whether a small coordinated subset carries a temporary residual edge hidden by global averages; H10/H20/H22 do not define that cross-sectional scan target.
- `CLOSEST_EXISTING_HYPOTHESIS`: H10; H20; H22
- `CLOSEST_EXISTING_STRATEGIES`: `optimize_deviation_extreme_generic`; `negative_selection_biglotto`; `feature_discovery_and_retrospective`; `exhaustive_feature_sweep_v2`; `predict_evolutionary_gum`
- `MINIMUM_DATA`: Causal standardized residual vectors across numbers or frozen strategies; predefined admissible groups.
- `DERIVED_FEATURES`: Penalized maximum subset score; subset size; alarm duration; null-calibrated threshold.
- `TARGET`: Next-period group residual or fixed allocation/abstention action.
- `COMPARATOR`: Global mean statistic; maximum single coordinate; H20 scalar anomaly.
- `TEMPORAL_DESIGN`: Calibrate scan penalty and alarm threshold on earlier null windows; evaluate delayed actions in outer folds.
- `LEAKAGE_GUARD`: Admissible groups fixed before testing; no post-alarm subgroup renaming; multiplicity included in null calibration.
- `EXPECTED_COST`: MEDIUM.
- `SUCCESS_SIGNAL`: Sparse-scan alarms precede a replicated group-level residual effect and improve the fixed action beyond global and max-coordinate controls.
- `FAILURE_SIGNAL`: Alarms are post hoc; unstable; or give no delayed target benefit.
- `IF_POSITIVE_NEXT`: Freeze one group universe and scan penalty for Track B replication.

## Specification count and execution state

- Surviving canonical external hypotheses: 21
- Fast-falsification specifications created: 21
- High-priority survivors without a specification: 0
- Tests executed: 0
- External claims locally validated: 0
