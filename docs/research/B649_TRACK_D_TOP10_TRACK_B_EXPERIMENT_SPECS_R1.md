# B649 Track B Top-10 Draft Experiment Specifications R1

- SOURCE_TASK_ID: `B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_AND_EXPERIMENT_SPECS_R1`
- PINNED_HISTORICAL_HEAD: `2db4da27aee716805c393eb9c7dd41aff8e9527e`
- STATUS: `DRAFT_ONLY / OWNER_AUTHORIZATION_REQUIRED_BEFORE_EXECUTION`
- These packets design experiments only. They contain no authorization token and permit no DB write, production promotion, candidate refreeze, cohort mutation, or prospective operation.

## Shared authority and truth rules

- Raw Foundation R2 supplies the 133 historical identities and native ticket-level outcomes.
- Hit Depth Projection R1 supplies exact native-multiplicity FULL/750/300/50 outcome/baseline views.
- Candidate-K authority is direct for 7 historical/current identities only; Combination A/C rankings are proxies.
- Current executable (51), historical analyzable (133), direct Candidate-K (7), frozen (40), and forward-generatable (3) are distinct sets.
- Strict-prior chronology uses target dates/canonical indices where source-local numeric draw IDs are incomparable.
- A PASS means “advance research,” never predictive proof or production readiness.

## H01 — CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR

TASK_ID: `B649_TRACK_B_H01_CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR_DRAFT_R1`

HYPOTHESIS_ID: `H01` / `CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR`

GOAL: A causal gate chooses or weights strategy outputs using only lagged, baseline-residual performance, family disagreement, regime descriptors, and portfolio overlap; it does not reuse an internal strategy rank.

WHY_NOT_DUPLICATE: Ensembles, consensus, optimizer, and diversification methods exist. None of the 133 is an exact cross-strategy residual-gated selector with the same causal information set, target, gate, and two-population design.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Historical discovery may use all 133; a separate adapter/runtime preflight narrows the 51 currently executable identities and then the 3/40 frozen forward-generatable candidates. No assumption that all 51 can supply each feature.

FEATURES_ALLOWED: 133-strategy raw ticket outcomes; Hit Depth FULL/750/300/50; exact same-native-multiplicity baselines; family labels; draw chronology; pre-target regime descriptors; portfolio-overlap features. Lagged per-strategy residuals, stability/dispersion, family disagreement, causal overlap graph, and fold-local gate features. No source-internal number rank is required.

FEATURES_FORBIDDEN: Target result, future recalculated rank, post-target performance, full-history statistics containing target, hindsight thresholds, and expert selection using outer-test performance are forbidden.

TARGET: Primary: fixed-budget next-draw OFFICIAL_ANY_PRIZE residual versus exact same-ticket-count random. Secondary: M2+, M3+, calibration of above-baseline probability; M4+ only descriptive because it is sparse.

BASELINE: Exact same-ticket-count random; equal-weight consensus; frozen static selector; regime-only selector.

WINDOWS: FULL, LONG_750, MID_300, SHORT_50 as causal lagged features and separately reported outcomes.

LEVEL_1_DESIGN: Artifact-only fixed-rule gate on lagged residual/stability over a predeclared small expert set; blocked holdout against exact random, equal-weight, and frozen-static selectors.

LEVEL_2_DESIGN: Nested expanding blocks over all 133 native portfolios; one primary any-prize residual, M2+/M3+ secondary; family-holdout sensitivity; separate current-runtime preflight.

LEVEL_3_DESIGN: Bounded model/gate family, regime interactions, seed stability, alternative objectives, and prospective protocol draft only if Level 2 advances.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Target result, future recalculated rank, post-target performance, full-history statistics containing target, hindsight thresholds, and expert selection using outer-test performance are forbidden.

MULTIPLICITY_BOUNDARY: Winner’s curse across 133 experts, objectives, windows, model classes, and gates. Use family-level screening, nested selection, one primary endpoint, blocked outer folds, and multiplicity-adjusted secondary claims.

OUTPUT_SCHEMA: target_draw_id, outer_fold, candidate_strategy_id, selected_strategy_ids/weights, feature_cutoff, native_ticket_count, baseline_id, M1..M6, any_prize, residual, gate_score, family, leakage_checks.

PASS_CRITERIA: Predeclared primary endpoint improves in multiple outer blocks with stable denominator, positive uncertainty-aware residual, family-holdout persistence, and no dependence on target-containing features. This advances research only.

FAIL_CRITERIA: No reproducible out-of-block gain over exact baseline/equal-weight/frozen-static selectors; gains vanish under family holdout; unstable expert concentration; or any leakage/control failure.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Medium: rank-free artifact-first Level 1 is hours; nested all-133 Level 2 is moderate; broad model search is deferred.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H02 — HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION

TASK_ID: `B649_TRACK_B_H02_HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION_DRAFT_R1`

HYPOTHESIS_ID: `H02` / `HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION`

GOAL: Independent confirmation of the fixed horizon-minimax producer: a number must remain acceptable across 30/120/FULL_PREFIX horizons and a two-ticket overlap constraint, rather than merely scoring well in one window.

WHY_NOT_DUPLICATE: The sealed next-generation authority already directly tested b649_new_horizon_minimax_disagreement_r1 outside the 133: 1,957 eligible targets, horizons 30/120/FULL_PREFIX, two tickets, max overlap 2, deterministic ties; deltas versus exact 2-ticket random were +0.0136584 FULL, +0.0163878 LONG, +0.00238779 MID, +0.0190545 SHORT. Status remains FRESH_BOUNDED_PENDING.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e; B649_NEXT_GENERATION_STRATEGY_RESEARCH_R1.

HISTORICAL_POPULATION: Sealed 1,957 eligible targets for reproduction/stress only; H02 producer is outside the 133 strategy set.

FORWARD_ELIGIBLE_POPULATION: No post-freeze observation exists in R4 and no pinned new-producer adapter is available. Prospective execution requires separate Track B engineering and Owner authorization.

FEATURES_ALLOWED: Draw chronology and pre-target 49-number frequencies at 30, 120, and full prefix; fixed producer parameters; exact two-ticket random baseline; untouched/reserved or prospective outcomes for confirmation. Horizon-wise ranks/scores, per-number minimax score, disagreement, and fixed overlap-constrained ticket construction.

FEATURES_FORBIDDEN: Calling reused historical targets “confirmation”; retuning horizons/overlap on the same 1,957; full-prefix including target; prospective backfill.

TARGET: Predeclared two-ticket any-prize and M2+/M3+ deltas versus exact two-ticket random; confirmation must be on data not used by the 1,957-target evaluation.

BASELINE: Exact two-ticket random and sealed frozen producer reproduction.

WINDOWS: Producer horizons 30/120/FULL_PREFIX; report FULL/LONG_750/MID_300/SHORT_50 outcome views.

LEVEL_1_DESIGN: Recompute the sealed 1,957-target fixed producer and exact two-ticket deltas; require bit-for-bit parameter/ticket agreement.

LEVEL_2_DESIGN: Contiguous block and window stability using the same frozen producer; explicitly label as historical stress, not independent confirmation.

LEVEL_3_DESIGN: Separately authorized prospective shadow observation with frozen producer, no tuning, and a predeclared confirmation endpoint.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Calling reused historical targets “confirmation”; retuning horizons/overlap on the same 1,957; full-prefix including target; prospective backfill.

MULTIPLICITY_BOUNDARY: Three shortlisted next-generation producers and multiple windows. Keep H02 parameters fixed and the confirmation endpoint singular.

OUTPUT_SCHEMA: target_draw_id, producer_version, horizons, ticket_1, ticket_2, overlap, cutoff, baseline, M1..M6, any_prize, residual, block_id, reproduction_match, evidence_role.

PASS_CRITERIA: Bit-for-bit reproduction plus stable historical stress behavior advances to a frozen prospective protocol; only untouched/prospective evidence can confirm.

FAIL_CRITERIA: Reproduction mismatch; negative/unstable blocked performance; any parameter retuning after outcome inspection; or no untouched sample for a confirmatory claim.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: under hours; LEVEL_2: hours; LEVEL_3: elapsed prospective observation period, not compressible by compute.

EXPECTED_COMPUTE: Low for reproduction/stability; elapsed-time high for genuine prospective confirmation.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H03 — MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT

TASK_ID: `B649_TRACK_B_H03_MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT_DRAFT_R1`

HYPOTHESIS_ID: `H03` / `MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT`

GOAL: The signal is change between windows—slope, acceleration, and cross-horizon disagreement—not the frequency level itself and not H02’s requirement that all horizons agree.

WHY_NOT_DUPLICATE: Frequency, EWMA, multi-window, drift, and walk-forward strategies exist, but no 133 strategy targets the incremental predictive value of slope/acceleration/disagreement after controlling for window levels.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Raw draw history makes features forward-computable, but a new versioned Track B producer/adapter is still required.

FEATURES_ALLOWED: Chronological draw history and pre-target 49-number counts for 50/300/750/FULL views; legal ticket construction; exact same-count baseline. p50-p300 slope; (p50-p300)-(p300-p750) acceleration; rank disagreement; turnover; fold-local scaling.

FEATURES_FORBIDDEN: Computing windows with target, global scaling, globally chosen breakpoints, or selecting window formulas on outer-test data.

TARGET: Per-number next-draw appearance probability or a fixed ticket outcome derived from those scores; primary test must compare against a level-only frequency model.

BASELINE: Causal trailing-frequency level-only models; exact same-ticket-count random.

WINDOWS: Feature windows 50/300/750/FULL; report stable FULL/LONG/MID/SHORT outcomes.

LEVEL_1_DESIGN: Fixed 50/300/750 slope and acceleration in a simple deterministic model versus level-only frequency.

LEVEL_2_DESIGN: Nested expanding folds, proper scores plus fixed-ticket residual, FULL/750/300/50 views, and incremental ablations.

LEVEL_3_DESIGN: Bounded alternative windows/transforms, regime interactions, multiple seeds/models, corrected as one declared family.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Computing windows with target, global scaling, globally chosen breakpoints, or selecting window formulas on outer-test data.

MULTIPLICITY_BOUNDARY: Many window definitions and transforms. Level 1 fixes 50/300/750 and one acceleration formula; Level 3 owns a bounded family with correction.

OUTPUT_SCHEMA: target_draw_id, number, p50, p300, p750, pfull, slope, acceleration, disagreement, model_id, fold, predicted_probability/score, ticket, outcomes, baseline_delta.

PASS_CRITERIA: Predeclared incremental improvement in proper scoring and fixed-ticket residual across multiple blocks.

FAIL_CRITERIA: No incremental gain over level-only frequency, unstable sign across blocks, or gain only after broad window search.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Low to medium.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H04 — CALIBRATED_PER_NUMBER_PROBABILITIES

TASK_ID: `B649_TRACK_B_H04_CALIBRATED_PER_NUMBER_PROBABILITIES_DRAFT_R1`

HYPOTHESIS_ID: `H04` / `CALIBRATED_PER_NUMBER_PROBABILITIES`

GOAL: Emit and validate causal out-of-sample P(number appears) for all 49 numbers, including calibration—not merely a score or rank.

WHY_NOT_DUPLICATE: XGBoost/ML/attention/Bayesian-style strategies emit tickets or scores, but the 133 raw authority does not preserve calibrated probabilities, reliability, Brier, log loss, ECE, or calibration curves.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Requires new probability-output interface and forward adapter; cannot be reconstructed from historical tickets.

FEATURES_ALLOWED: Pre-target draw features, binary 49-number next-draw targets, model outputs generated anew, and nested calibration partitions. Raw logits/probabilities, calibrated probabilities, reliability bins, Brier/log loss/ECE, sharpness, and calibration slope/intercept.

FEATURES_FORBIDDEN: Normalizing arbitrary scores and calling them probabilities, calibration on evaluation data, row-level random split across numbers/draws, target-derived feature selection.

TARGET: 49 correlated binary appearance outcomes per draw; primary proper score at the draw block level.

BASELINE: Causal empirical-frequency probability; uncalibrated model; trivial 6/49 marginal reference.

WINDOWS: Nested expanding calibration/evaluation blocks; report FULL/750/300/50 where denominators are stable.

LEVEL_1_DESIGN: Causal frequency-probability baseline plus one simple model; report Brier/log loss/ECE without post-hoc calibration.

LEVEL_2_DESIGN: Nested blocked calibration comparing uncalibrated, Platt/beta/isotonic outputs with draw-level uncertainty.

LEVEL_3_DESIGN: Bounded model families, reliability/sharpness frontier, multiple seeds, and alternative calibration objectives.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Normalizing arbitrary scores and calling them probabilities, calibration on evaluation data, row-level random split across numbers/draws, target-derived feature selection.

MULTIPLICITY_BOUNDARY: Models, calibrators, bins, and feature sets. Predeclare primary Brier score/model pair; treat other metrics as secondary.

OUTPUT_SCHEMA: target_draw_id, number, raw_probability, calibrated_probability, outcome, model, calibrator, fold, Brier, log_loss, ECE_bin, calibration_slope/intercept.

PASS_CRITERIA: Better predeclared proper score plus materially improved reliability across blocked folds without losing all sharpness.

FAIL_CRITERIA: Worse proper score than causal frequency, severe reliability error, probability invalidity, or calibration gain absent out of sample.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Medium to high depending model family.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H05 — DIRECT_TICKET_LEVEL_RESIDUAL_SCORING

TASK_ID: `B649_TRACK_B_H05_DIRECT_TICKET_LEVEL_RESIDUAL_SCORING_DRAFT_R1`

HYPOTHESIS_ID: `H05` / `DIRECT_TICKET_LEVEL_RESIDUAL_SCORING`

GOAL: Score legal six-number tickets directly through joint residual features instead of ranking numbers first and then constructing tickets.

WHY_NOT_DUPLICATE: Combination, Apriori, pair/triple, covering, and portfolio evaluators exist. They do not exactly match a causal direct ticket-level residual model over a frozen bounded candidate set.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Requires a new bounded candidate generator/scorer; does not require source-internal ranking.

FEATURES_ALLOWED: Pre-target draw history; fixed legal-ticket candidate generator; sum/zone/parity/pair/triple/overlap features; ticket outcomes and exact candidate-pool comparators. Joint ticket residuals versus marginal independence, causal interaction features, and bounded candidate scores.

FEATURES_FORBIDDEN: Candidate pool chosen using target, joint frequencies including target, searching all 13,983,816 tickets after viewing outcomes, or comparator pool mismatch.

TARGET: Ticket-level hit depth/any-prize or residual versus candidate-matched random; number-level metrics are secondary.

BASELINE: Additive number score on the identical candidate pool; matched random candidate/ticket selection.

WINDOWS: Nested expanding blocks; FULL/750/300/50 outcome views.

LEVEL_1_DESIGN: Freeze 256 candidates and compare additive-number versus one regularized ticket-interaction score.

LEVEL_2_DESIGN: Repeat at 256/1,024/4,096 candidates in nested blocked folds with exact candidate-matched baselines and hit-depth.

LEVEL_3_DESIGN: Bounded interaction families, hierarchical regularization, regime interactions, and candidate-generator sensitivity—no full-universe brute force.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Candidate pool chosen using target, joint frequencies including target, searching all 13,983,816 tickets after viewing outcomes, or comparator pool mismatch.

MULTIPLICITY_BOUNDARY: Many interactions and candidate sizes. Freeze a small basis at Level 1; use hierarchical regularization and bounded families later.

OUTPUT_SCHEMA: target_draw_id, candidate_pool_id, ticket, marginal_score, interaction_features, residual_score, selected, fold, cutoff, hit_depth, baseline_delta.

PASS_CRITERIA: Stable held-out gain over additive and matched random within the same fixed candidate pool and budget.

FAIL_CRITERIA: No incremental residual over additive scoring on same candidates; overfit interactions; unstable candidate-size dependence.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Medium at bounded sizes; high if interactions proliferate. Full-universe brute force is explicitly out.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H06 — DPP_SUBMODULAR_PORTFOLIO_SELECTION

TASK_ID: `B649_TRACK_B_H06_DPP_SUBMODULAR_PORTFOLIO_SELECTION_DRAFT_R1`

HYPOTHESIS_ID: `H06` / `DPP_SUBMODULAR_PORTFOLIO_SELECTION`

GOAL: Optimize portfolio diversity with a determinantal or explicit submodular marginal-utility objective, not just generic greedy/covering/orthogonal heuristics.

WHY_NOT_DUPLICATE: Covering, cluster cover, orthogonal diversification, greedy, portfolio, and multi-bet optimizers are strongly related. None of the 133 records an exact DPP objective or the same predeclared submodular utility.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Portfolio construction can wrap a forward-capable producer, but the DPP/submodular adapter itself is not pinned and requires Track B engineering.

FEATURES_ALLOWED: A frozen causal candidate-ticket pool, candidate utility proxy, pairwise overlap/similarity, fixed ticket count/number pool/budget/cutoff, and exact matched baselines. DPP kernel/quality-diversity decomposition, submodular marginal gain, portfolio overlap, unique-number coverage, and conditional-random comparator.

FEATURES_FORBIDDEN: Different candidate pools, ticket budgets, or candidate scores across optimizers; target-conditioned kernel; post-hoc objective selection.

TARGET: Portfolio hit-depth/any-prize and overlap efficiency; predictive edge and diversification benefit reported separately.

BASELINE: EXISTING_GREEDY; ORTHOGONAL; DPP; SUBMODULAR; CONDITIONAL_RANDOM on identical inputs.

WINDOWS: Nested expanding blocks; FULL/750/300/50 portfolio outcome views.

LEVEL_1_DESIGN: One fixed candidate pool and portfolio size; compare existing greedy, orthogonal, DPP-MAP, submodular greedy, and conditional random.

LEVEL_2_DESIGN: Multiple frozen pool sizes/portfolio sizes under identical budgets; overlap, coverage, hit-depth, and exact uncertainty.

LEVEL_3_DESIGN: Bounded kernels/utilities, sampling versus MAP, seed stability, and producer × optimizer interactions with correction.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Different candidate pools, ticket budgets, or candidate scores across optimizers; target-conditioned kernel; post-hoc objective selection.

MULTIPLICITY_BOUNDARY: Optimizer × kernel × utility × portfolio size. One primary utility and fixed sizes first; family-wise correction later.

OUTPUT_SCHEMA: target_draw_id, candidate_pool_hash, optimizer, seed, ticket_count, budget, number_pool, selected_tickets, pair_overlap, unique_coverage, hit_depth, baseline_delta.

PASS_CRITERIA: Reproducible portfolio efficiency improvement under exact fairness controls; any predictive residual is a separate, stricter claim.

FAIL_CRITERIA: No improvement over matched greedy/orthogonal/conditional random, or gains explained solely by larger unique-number coverage.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Medium; kernel operations scale with bounded candidate pool.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H07 — CHANGE_POINT_TRIGGERED_ALLOCATION

TASK_ID: `B649_TRACK_B_H07_CHANGE_POINT_TRIGGERED_ALLOCATION_DRAFT_R1`

HYPOTHESIS_ID: `H07` / `CHANGE_POINT_TRIGGERED_ALLOCATION`

GOAL: Change allocation only after a causally detected change point; this is neither H02 cross-horizon confirmation nor H03 treating window derivatives as direct signals.

WHY_NOT_DUPLICATE: EWMA, drift, regime, adaptive, and multi-window strategies exist; no exact alarm-triggered allocation rule with detector training and response frozen before evaluation.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Draw-level features are available; new detector/allocation producer and persistent state contract are required.

FEATURES_ALLOWED: Draw chronology, causal regime descriptors, strategy residual histories, detector state, frozen alarm response, and matched alarm-frequency comparators. Sequential change statistic/posterior, alarm state, time-since-alarm, and post-alarm allocation weights.

FEATURES_FORBIDDEN: Retrospective breakpoint placement, using future segment means, refitting threshold on outer outcomes, or assigning regime labels with full history.

TARGET: Incremental fixed-budget outcome residual of event-triggered allocation versus never-switch, always-regime, and random alarms matched on frequency.

BASELINE: Never-switch; always-regime; matched-frequency random alarms; static best training selector.

WINDOWS: Sequential expanding detector; FULL/750/300/50 descriptors/outcome views.

LEVEL_1_DESIGN: One causal detector/threshold and one frozen allocation response versus never-switch and matched random alarms.

LEVEL_2_DESIGN: Sequential replay across blocked periods with always-regime, random-alarm, and detector ablations; FULL/750/300/50 descriptors.

LEVEL_3_DESIGN: Bounded detector families, response functions, regime interactions, multiple seeds, and alarm-cost objective.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Retrospective breakpoint placement, using future segment means, refitting threshold on outer outcomes, or assigning regime labels with full history.

MULTIPLICITY_BOUNDARY: Detector families, thresholds, features, allocation responses. Fix one detector/response at Level 1 and nest all selection.

OUTPUT_SCHEMA: target_draw_id, detector_state, alarm, threshold_version, time_since_alarm, allocation_before/after, comparator_alarm, cutoff, outcomes, residual.

PASS_CRITERIA: Stable incremental benefit localized after pre-target alarms and robust to matched-frequency random alarm controls.

FAIL_CRITERIA: No gain versus matched random alarms/never-switch; excessive alarms; benefit disappears with causal breakpoint detection.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Low to medium.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H08 — TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS

TASK_ID: `B649_TRACK_B_H08_TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS_DRAFT_R1`

HYPOTHESIS_ID: `H08` / `TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS`

GOAL: Use time-decayed hyperedges and evolving higher-order motifs, then score residual occurrence beyond marginal/pairwise independence and static community structure.

WHY_NOT_DUPLICATE: Pair co-occurrence, graphs, PageRank-like methods, clique/Apriori, cluster, and pair/triple logic exist. No exact temporal hypergraph motif-evolution residual is present.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Requires new feature and scoring pipeline; raw draw history is sufficient for offline construction.

FEATURES_ALLOWED: Chronological six-number draw hyperedges before target; causal marginal/pair/triple baselines; motif vocabulary; decay and community state. Time-decayed motif counts, higher-order residuals versus independence, motif velocity, dynamic community membership, and ticket motif score.

FEATURES_FORBIDDEN: Global graph including target/future, motif vocabulary mined on outer test, community smoothing backward from future, or target-informed decay.

TARGET: Next-draw motif/ticket residual and fixed-ticket outcomes versus marginal, static graph, co-occurrence, and Apriori baselines.

BASELINE: Marginal frequency; pair co-occurrence; static graph; static Apriori/hypergraph.

WINDOWS: Expanding temporal graph; fixed decay plus FULL/750/300/50 sensitivity.

LEVEL_1_DESIGN: One decay and tiny predefined pair/triple motif-residual set versus marginal and static graph baselines.

LEVEL_2_DESIGN: Temporal hypergraph updates in expanding blocks; static/temporal/residual/community ablations and fixed tickets.

LEVEL_3_DESIGN: Bounded motif vocabulary, decay family, dynamic communities, multiple seeds, and hierarchical multiplicity control.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Global graph including target/future, motif vocabulary mined on outer test, community smoothing backward from future, or target-informed decay.

MULTIPLICITY_BOUNDARY: Combinatorial motif vocabulary is the main risk. Predefine a minimal set, hierarchical tests, and bounded Level 3 search.

OUTPUT_SCHEMA: target_draw_id, motif_id, decay, causal_count, independence_expectation, residual, community_id, model, fold, selected_ticket, hit_depth, baseline_delta.

PASS_CRITERIA: Incremental held-out residual from predefined temporal higher-order features across multiple blocks.

FAIL_CRITERIA: No residual beyond marginal/static graph baselines; instability across folds/decays; discoveries vanish after motif-family correction.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Medium for minimal motifs; high for broad motif/community search.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H09 — CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION

TASK_ID: `B649_TRACK_B_H09_CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION_DRAFT_R1`

HYPOTHESIS_ID: `H09` / `CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION`

GOAL: Apply a negative signal only when a separately frozen positive selector and context jointly satisfy a predeclared condition; the interaction is the hypothesis.

WHY_NOT_DUPLICATE: Exclusion-only, must-not-hit, negative selection, anti-consensus, cold/hot suppression, and constraint filters exist. They test negative information, but not the full positive-selector × conditional-suppression design.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Requires both components to be forward-capable and a new conditional wrapper; current 51/133 runtime overlap is only a preflight universe.

FEATURES_ALLOWED: Frozen positive selector outputs/scores, pre-target negative features, causal condition/gate, identical candidate/budget, outcomes, and matched random suppression. Conditional negative score, gate state, removed-number/ticket set, suppression intensity, and paired counterfactual portfolio.

FEATURES_FORBIDDEN: Choosing positive selector from outer results, target-derived kill list, tuning condition after paired outcomes, or comparing different budgets.

TARGET: Incremental outcome residual of CONDITIONAL_SUPPRESSION over POSITIVE_ONLY, EXCLUSION_ONLY, UNCONDITIONAL_NEGATIVE, and RANDOM_MATCHED_SUPPRESSION.

BASELINE: POSITIVE_ONLY; EXCLUSION_ONLY; UNCONDITIONAL_NEGATIVE; RANDOM_MATCHED_SUPPRESSION.

WINDOWS: Nested expanding blocks; FULL/750/300/50 outcome views.

LEVEL_1_DESIGN: One frozen positive selector, one negative signal, one condition; paired comparison with positive-only and matched random suppression.

LEVEL_2_DESIGN: Nested blocked replay including exclusion-only, unconditional negative, conditional negative, and matched-random controls.

LEVEL_3_DESIGN: Bounded positive × negative × context interactions, suppression intensity, regime effects, and hierarchical correction.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Choosing positive selector from outer results, target-derived kill list, tuning condition after paired outcomes, or comparing different budgets.

MULTIPLICITY_BOUNDARY: Many positive × negative × condition combinations. Level 1 tests exactly one of each; Level 3 uses hierarchical interaction testing.

OUTPUT_SCHEMA: target_draw_id, positive_selector_version, negative_signal_version, condition, gate, suppressed_items, matched_random_items, budget, paired_outcomes, incremental_residual.

PASS_CRITERIA: Stable paired incremental gain specific to the condition, with no unconditional degradation and corrected interaction evidence.

FAIL_CRITERIA: Conditional version does not beat positive-only and matched random suppression, or any apparent gain comes from ticket-count/budget change.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Low to medium for a fixed pair.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`

## H10 — DYNAMIC_BAYESIAN_STATE_SPACE_MODELING

TASK_ID: `B649_TRACK_B_H10_DYNAMIC_BAYESIAN_STATE_SPACE_MODELING_DRAFT_R1`

HYPOTHESIS_ID: `H10` / `DYNAMIC_BAYESIAN_STATE_SPACE_MODELING`

GOAL: Infer a latent temporal state with posterior uncertainty and state evolution, then use that posterior for number/ticket probabilities or allocation.

WHY_NOT_DUPLICATE: Static Bayesian weights, Markov transitions, EWMA/frequency dynamics, ML, and regime descriptors exist. Bayesian is not state-space; none of the 133 is an exact latent dynamic probabilistic state model.

PINNED_INPUT_AUTHORITIES: B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2; B649_HIT_DEPTH_PROJECTION_R1; B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1; pinned strategy catalog at 2db4da27aee716805c393eb9c7dd41aff8e9527e.

HISTORICAL_POPULATION: 133/133 historical identities for collision context; experiment-specific eligible draw rows after causal/minimum-history filters.

FORWARD_ELIGIBLE_POPULATION: Requires a new stateful probability producer/adapter and explicit state persistence/versioning.

FEATURES_ALLOWED: Chronological draw observations, pre-target number/structural features, specified latent-state dynamics/emissions/priors, and proper-score outcomes. Filtered (not smoothed) state posterior, transition uncertainty, posterior predictive number probabilities, and state-conditioned ticket scores.

FEATURES_FORBIDDEN: Posterior smoothing with future observations, tuning state count on outer test, global standardization, or reporting in-sample posterior fit.

TARGET: Held-out log loss/Brier for posterior predictive outputs plus fixed-ticket residual versus static Beta/Bayesian, trailing frequency, Markov/HMM-like, and regime baselines.

BASELINE: Static Beta/Bayesian; trailing frequency; Markov/HMM-like; causal regime model.

WINDOWS: Nested expanding filtering; FULL/750/300/50 evaluation views.

LEVEL_1_DESIGN: Low-dimensional filtered dynamic model versus static Beta/trailing-frequency baselines on proper scores.

LEVEL_2_DESIGN: Nested blocked model comparison with filtered posteriors, calibration, fixed-ticket construction, and Markov/regime ablations.

LEVEL_3_DESIGN: Bounded state dimensions/priors/emissions, nonlinear/particle alternatives, multiple seeds/chains, and convergence gates.

LEAKAGE_GUARDS: Enforce cutoff < target by date/canonical chronology; compute transforms inside fold; freeze candidates/features/thresholds before outer evaluation; audit forbidden-feature columns; preserve an attempt ledger. Specific risks: Posterior smoothing with future observations, tuning state count on outer test, global standardization, or reporting in-sample posterior fit.

MULTIPLICITY_BOUNDARY: State dimensions, priors, transition forms, emissions, inference methods. One parsimonious primary model first; bounded family later.

OUTPUT_SCHEMA: target_draw_id, model_version, prior_version, filtered_state_posterior, posterior_predictive_49, fold, seed/chain, diagnostics, Brier, log_loss, calibration, ticket_outcome.

PASS_CRITERIA: Filtered posterior predictions improve proper scoring and calibration across blocked folds with stable interpretable state behavior.

FAIL_CRITERIA: No proper-score gain over static/trailing baselines, non-identifiability, poor convergence, or only smoothed/in-sample improvement.

STOP_CONDITIONS: Stop the experiment on authority hash/schema mismatch, denominator instability, causal-cutoff violation, candidate/comparator unfairness, unregistered outcome-driven change, or resource use beyond the authorized packet. Do not stop merely for negative results.

EXPECTED_RUNTIME: LEVEL_1: tens of minutes to hours; LEVEL_2: hours; LEVEL_3: days/elapsed prospective time as applicable.

EXPECTED_COMPUTE: Medium to high; nonlinear/particle/MCMC variants are Level 3 only.

NO_DB_WRITE: `TRUE`

NO_PRODUCTION_PROMOTION: `TRUE`

OWNER_AUTHORIZATION_TOKEN: `NOT_INCLUDED_BY_DESIGN`
