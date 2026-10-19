# B649 Track D Remaining-18 Open Hypotheses Deep Audit R1

TASK_ID: `B649_TRACK_D_REMAINING_18_OPEN_HYPOTHESES_DEEP_AUDIT_R1`

STATUS: PASS

MODE: LONG_RUNNING_READ_ONLY_RESEARCH_WITH_AUTHORIZED_OFF_REPO_ARTIFACTS

OWNER_RESEARCH_POLICY: `WIDE_IN_STRICT_OUT`

PINNED_HISTORICAL_HEAD: `2db4da27aee716805c393eb9c7dd41aff8e9527e`

PINNED_HISTORICAL_TREE: `cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c`

REMAINING_HYPOTHESES: 18/18

HISTORICAL_IDENTITIES: 133/133

COLLISION_MATRIX_ROWS: 2394

EXACT_MATCH_TOTAL: 0

STILL_OPEN_COUNT: 18

CLOSED_AS_TRUE_DUPLICATE_COUNT: 0

## Authority and evidence boundary

- [Confirmed] All five input SHA-256 values matched the Packet exactly before artifact creation.
- [Confirmed] The live repository was clean at preflight on branch `codex/b649-horizon-minimax-target-native-migration-r1`, HEAD `fc720ea8965faf95021a59d3fe3dae61ae3ef6c3`, tree `64474415e7c4a34abd190b32d7a2e8a2a47d02f3`.
- [Confirmed] The pinned commit resolves locally and was read with object-safe commands. Its 1,153 tree entries are regular blobs; no symlink, submodule, or special-mode entry was present.
- [Confirmed] The historical 133 collision population comes from the checksummed Top-10 matrix: 133 unique `BACKTESTED` IDs, 128 `RAW_HISTORY_PRESERVED`, 5 `RAW_HISTORY_WITH_RECOVERY_OVERLAY`.
- [Unknown] The older source commit `49a25effa62fc24f40789c16be6f11bdfb41a4a9` named by every historical row is absent from the local object database. As in the sealed Top-10 audit, source-body parity is not claimed; catalog semantics, source/blob/checksum metadata, checksummed behavior, and sealed conclusions are the evidence contract.
- [Confirmed] No H01 in-progress result, target result, parameter, or task-root content was used.
- NOT RUN: network/external-method refresh, H01–H10 experiments, strategy implementation, DB write, Cohort V2 creation, V1 modification, re-freeze, or prospective observation.

### Verified input authorities

| Authority | SHA-256 | Result |
|---|---|---|
| B649_TRACK_D_RESEARCH_SURFACE_R1.md | `26add8e34cb259cffdd54c6cd8f91373980ffe7c2277b17b2afaca8c936c8859` | PASS |
| B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_R1.md | `6758482663fd46f14f86a293f0eef1a2bc77ff3186931267c5197f8cac87287b` | PASS |
| B649_TRACK_D_TOP10_COLLISION_MATRIX_R1.csv | `44689faf7c06b59a7452090fd0952e94dd276609427a1b893fbd67825e52a1d5` | PASS |
| B649_TRACK_D_HYPOTHESIS_DATA_SUFFICIENCY_MATRIX_R1.csv | `9200b55d61b6fde69fa173c97bac419e8f9c10813fd415aef03f76662b1874ab` | PASS |
| B649_TRACK_D_TOP10_PRIORITY_RANKING_R1.csv | `b0953cf2548e1fe9a941197d26a5bee9456b75adfa99361a1195acbcf663b869` | PASS |

## Collision method and strict-out rule

Every remaining hypothesis was crossed with the same 133 canonical identities. `EXACT_HYPOTHESIS_MATCH` requires the same information set, transformation, target, temporal semantics, and gating/composition logic. Family similarity never upgrades a row to exact. Labels were assigned in this precedence: exact (none), curated strong component, curated weak component, same-family/different-hypothesis, otherwise no meaningful overlap. No performance outcome or priority score affected the collision label.

Historical negative evidence is scoped to the exact selection rule, temporal window, native-ticket/projection semantics, comparator/null, and evaluation contract that ran. It is never summarized as “Markov failed”, “XGBoost failed”, or another family-wide denial.

## Aggregate collision result

| Classification | Rows |
|---|---:|
| EXACT_HYPOTHESIS_MATCH | 0 |
| STRONG_COMPONENT_OVERLAP | 220 |
| WEAK_COMPONENT_OVERLAP | 202 |
| SAME_METHOD_FAMILY_DIFFERENT_HYPOTHESIS | 203 |
| NO_MEANINGFUL_OVERLAP | 1769 |
| UNKNOWN | 0 |

### Per-hypothesis collision and score summary

| ID | Exact | Strong | Weak | Same family | None | Novelty | Orthogonality | Testability | Data | Forward | Compute | Info gain | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| H02 | 0 | 32 | 22 | 14 | 65 | 4 | 5 | 5 | 5 | 3 | 4 | 5 | OPEN |
| H03 | 0 | 13 | 14 | 22 | 84 | 4 | 3 | 5 | 5 | 3 | 3 | 4 | OPEN |
| H05 | 0 | 13 | 15 | 7 | 98 | 3 | 3 | 5 | 5 | 4 | 5 | 3 | OPEN |
| H06 | 0 | 3 | 27 | 13 | 90 | 3 | 3 | 5 | 5 | 4 | 5 | 3 | OPEN |
| H08 | 0 | 2 | 10 | 25 | 96 | 4 | 5 | 3 | 3 | 3 | 4 | 5 | OPEN |
| H09 | 0 | 12 | 16 | 5 | 100 | 4 | 5 | 4 | 3 | 3 | 4 | 5 | OPEN |
| H11 | 0 | 18 | 12 | 10 | 93 | 4 | 5 | 5 | 4 | 3 | 3 | 5 | OPEN |
| H13 | 0 | 19 | 15 | 14 | 85 | 4 | 4 | 5 | 5 | 4 | 4 | 4 | OPEN |
| H15 | 0 | 18 | 8 | 10 | 97 | 3 | 3 | 5 | 5 | 4 | 3 | 4 | OPEN |
| H16 | 0 | 0 | 0 | 0 | 133 | 5 | 5 | 3 | 2 | 2 | 3 | 5 | OPEN |
| H18 | 0 | 12 | 10 | 25 | 86 | 4 | 4 | 4 | 4 | 3 | 2 | 5 | OPEN |
| H20 | 0 | 16 | 12 | 15 | 90 | 4 | 4 | 5 | 5 | 5 | 5 | 4 | OPEN |
| H22 | 0 | 11 | 0 | 0 | 122 | 3 | 5 | 5 | 5 | 1 | 4 | 5 | OPEN |
| H23 | 0 | 12 | 3 | 6 | 112 | 4 | 5 | 3 | 2 | 2 | 1 | 4 | OPEN |
| H24 | 0 | 13 | 2 | 6 | 112 | 5 | 5 | 3 | 2 | 2 | 1 | 5 | OPEN |
| H25 | 0 | 13 | 15 | 5 | 100 | 3 | 3 | 5 | 5 | 3 | 4 | 4 | OPEN |
| H26 | 0 | 12 | 8 | 10 | 103 | 5 | 5 | 3 | 2 | 2 | 3 | 5 | OPEN |
| H28 | 0 | 1 | 13 | 16 | 103 | 2 | 3 | 1 | 5 | 5 | 5 | 4 | OPEN |

## Remaining-18 deep audit

### H02 — Complementary-error graph across strategies

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `META_SELECTION`
- COLLISION_COUNTS: exact 0; strong 32; weak 22; same-family/different 14; none 65
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `REQUIRES_SMALL_ADAPTER_WORK`
- SCORES_0_TO_5: novelty 4; orthogonality 5; historical testability 5; data readiness 5; forward path 3; compute feasibility 4; potential information gain 5

1. **What different predictive hypothesis is proposed?** The predictive unit is not a number graph. Nodes are frozen strategies; edges quantify strictly prior paired-error complementarity, and the graph chooses a community/cover for the next block.
2. **Which of the 133 identities are closest?** `optimized_ensemble`, `predict_consensus_ensemble`, `portfolio_optimizer`, `covering_strategy_research`, and `graph_predictor`.
3. **Was it tested directly or only by component?** Only components were tested: static cross-strategy aggregation, portfolio cover/diversification, and number-level graphs. No identity combines the same error information set, graph transformation, next-block target, and causal cover rule.
4. **What does the closest negative evidence actually negate?** The 133 robustness negatives apply to each fixed producer/native portfolio and the named covering/graph/ensemble rules on FULL/750/300/50 windows. They do not test a graph of paired residuals or a graph-selected expert cover.
5. **Which distinct conditional variants remain?** Residual correlation versus tail-complementarity edges; family-constrained communities; budget-specific minimum cover; hard community choice versus soft weights.
6. **Is sealed evidence sufficient for a fast test?** YES. Common-coverage strategy outcomes, exact baselines, chronology, families, and tickets are sealed; graph features are derivable without new model outputs.
7. **Are new derived features required?** Prior-only paired residual covariance, joint failure/tail measures, edge stability, community membership, graph centrality, and cover diagnostics.
8. **Is a new model output required?** No new base producer. A derived graph score and portfolio/allocator output are required.
9. **Is strategy-internal ranking required?** No strategy-internal rank is required; use matched per-draw outcomes and declared portfolio tickets.
10. **What is the forward path?** Build a small read-only graph/cover overlay on a verified forward-capable expert subset; do not assume all 133 execute now.
11. **Could success enter a future Cohort V2?** YES, conditionally, as a separately versioned selector over capability-verified producers after independent confirmation; never rewrite Cohort V1.
12. **What is the largest leakage risk?** Edges or expert eligibility computed with the target outcome, outcome-ranked node selection, or community tuning on terminal blocks.

- CLOSURE_DECISION: `OPEN`

### H03 — Mixture-of-experts with out-of-fold gating

- ORIGINAL_STATUS: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`
- PRIMARY_CLUSTER: `META_SELECTION`
- COLLISION_COUNTS: exact 0; strong 13; weak 14; same-family/different 22; none 84
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 4; orthogonality 3; historical testability 5; data readiness 5; forward path 3; compute feasibility 3; potential information gain 4

1. **What different predictive hypothesis is proposed?** It learns a small causal allocation function from out-of-fold expert residuals and state, rather than using one static ensemble or descriptive regime table.
2. **Which of the 133 identities are closest?** `advanced_methods_benchmark`, `optimized_ensemble`, `predict_6expert`, `predict_consensus_ensemble`, and `predict_evolutionary_gum`.
3. **Was it tested directly or only by component?** Static ensemble and regime components were tested, but no nested out-of-fold learned allocator with the same target and chronology was found.
4. **What does the closest negative evidence actually negate?** Static ensemble native-ticket rules had no corrected positive cells; regime analysis contained exploratory positives, 419 reversals, and 146 non-replications. This scope does not include a frozen OOF allocator.
5. **Which distinct conditional variants remain?** Linear softmax versus shallow-tree gate; residual-only versus residual-plus-regime; hard expert choice versus capped soft allocation.
6. **Is sealed evidence sufficient for a fast test?** YES historically. Causal portfolios and prior outcomes are sealed; the gate itself must be newly trained under nested blocks.
7. **Are new derived features required?** OOF residuals, disagreement, 50/300/750 slopes, four frozen regime descriptors, and portfolio geometry.
8. **Is a new model output required?** YES: per-target expert weights/gate output generated out of fold.
9. **Is strategy-internal ranking required?** No internal rank is required; ticket outcomes and expert identity are sufficient.
10. **What is the forward path?** Requires a deterministic gate output and then a small shadow adapter over forward-capable experts.
11. **Could success enter a future Cohort V2?** YES, after a later untouched confirmation and adapter-capability preflight; it would be a selector layer, not a relabeled producer.
12. **What is the largest leakage risk?** Training residuals in sample, using terminal outcomes to choose experts/features, or importing concurrent H01 results into gate design.

- CLOSURE_DECISION: `OPEN`

### H05 — Conditional consensus by regime/state

- ORIGINAL_STATUS: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`
- PRIMARY_CLUSTER: `META_SELECTION`
- COLLISION_COUNTS: exact 0; strong 13; weak 15; same-family/different 7; none 98
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `FORWARD_READY_WITH_EXISTING_51`
- SCORES_0_TO_5: novelty 3; orthogonality 3; historical testability 5; data readiness 5; forward path 4; compute feasibility 5; potential information gain 3

1. **What different predictive hypothesis is proposed?** Consensus is activated or weighted only under one frozen causal state; the state-by-consensus interaction is the hypothesis.
2. **Which of the 133 identities are closest?** `predict_consensus_ensemble`, `predict_evolutionary_gum`, `optimized_ensemble`, and `biglotto_diversified_ensemble`.
3. **Was it tested directly or only by component?** Static consensus and regime descriptors exist. Their conditional interaction and paired inactive-state comparator were not tested.
4. **What does the closest negative evidence actually negate?** The static consensus producer had no corrected positive cells under its fixed aggregation/native tickets; exploratory regime cells are multiplicity-exposed. Neither result tests conditional activation.
5. **Which distinct conditional variants remain?** One regime axis at a time; consensus strength threshold; family-breadth threshold; activate, downweight, or substitute.
6. **Is sealed evidence sufficient for a fast test?** YES. Fixed producer tickets, state descriptors, outcomes, and exact baselines already exist.
7. **Are new derived features required?** Consensus strength, family breadth, prior residual quality, and one state interaction.
8. **Is a new model output required?** No new base model; one deterministic conditional overlay is enough.
9. **Is strategy-internal ranking required?** Not required. Consensus can be defined from ticket support and producer identity.
10. **What is the forward path?** Can be projected over the current executable subset after verifying the exact member join.
11. **Could success enter a future Cohort V2?** YES conditionally as a separately versioned gate candidate after blocked confirmation.
12. **What is the largest leakage risk?** Choosing the state/threshold after viewing state-specific target outcomes or allowing future regime labels into current targets.

- CLOSURE_DECISION: `OPEN`

### H06 — Conditional anti-consensus / minority signal

- ORIGINAL_STATUS: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`
- PRIMARY_CLUSTER: `META_SELECTION`
- COLLISION_COUNTS: exact 0; strong 3; weak 27; same-family/different 13; none 90
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `FORWARD_READY_WITH_EXISTING_51`
- SCORES_0_TO_5: novelty 3; orthogonality 3; historical testability 5; data readiness 5; forward path 4; compute feasibility 5; potential information gain 3

1. **What different predictive hypothesis is proposed?** A minority ticket is substituted only when a frozen disagreement, state, and prior-error condition holds; static anti-consensus is not the same contract.
2. **Which of the 133 identities are closest?** `anti_consensus_strategy`, `predict_consensus_ensemble`, `predict_evolutionary_gum`, and `negative_selection_biglotto`.
3. **Was it tested directly or only by component?** Static anti-consensus, exclusion, consensus, and regime components exist; the conditional minority interaction was not directly tested.
4. **What does the closest negative evidence actually negate?** The static anti-consensus producer had no corrected positive cells and fixed exclusion producers were also negative under their native selection rules. This does not test a state-conditioned substitution against a paired no-action portfolio.
5. **Which distinct conditional variants remain?** Minority by ticket support or family support; recent-error-weighted minority; one- versus two-ticket substitution; alternative fixed horizons.
6. **Is sealed evidence sufficient for a fast test?** YES. Disagreement, history, regimes, portfolios, and baselines are available or derivable.
7. **Are new derived features required?** Minority support, family-weighted disagreement, prior false-positive concentration, and frozen activation flag.
8. **Is a new model output required?** No new base model; a conditional substitution decision is derived.
9. **Is strategy-internal ranking required?** No internal rank is needed if the minority ticket rule is fixed from support counts.
10. **What is the forward path?** Can run over verified current producers with a small overlay; exact member availability must be checked.
11. **Could success enter a future Cohort V2?** YES conditionally as a distinct gate after confirmation; do not merge it with H21 or static anti-consensus.
12. **What is the largest leakage risk?** Defining minority from post-target errors, optimizing the condition on terminal outcomes, or changing substitution count after seeing results.

- CLOSURE_DECISION: `OPEN`

### H08 — Per-number ranking-loss model

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `NUMBER_LEVEL_MODEL`
- COLLISION_COUNTS: exact 0; strong 2; weak 10; same-family/different 25; none 96
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PARTIAL`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 4; orthogonality 5; historical testability 3; data readiness 3; forward path 3; compute feasibility 4; potential information gain 5

1. **What different predictive hypothesis is proposed?** It learns a causal ranking over all 49 numbers using a ranking loss before one frozen legal-ticket constructor; native ticket output is a different target.
2. **Which of the 133 identities are closest?** `xgboost_model`, `quick_ml_predict`, `dynamic_frequency_predictor`, and `graph_predictor`.
3. **Was it tested directly or only by component?** Direct ML/frequency/graph producers contain scoring primitives, but no canonical 49-number ranking-loss contract exists for the 133 population.
4. **What does the closest negative evidence actually negate?** The direct XGBoost producer had 0 positive and 11 negative corrected cells under its historical feature and ticket-selection contract; frequency and graph negatives likewise apply only to their fixed rules.
5. **Which distinct conditional variants remain?** Pairwise versus listwise loss; seven direct Candidate-K paths versus a frozen reconstructed exposure subset; alternative fixed ticket constructor.
6. **Is sealed evidence sufficient for a fast test?** PARTIAL. Outcomes and chronology are sealed, but canonical number-level exposure exists directly for only seven paths and must not be invented for the rest.
7. **Are new derived features required?** Causal number exposure, trailing counts, gaps, graph features, and strictly prior rank covariates.
8. **Is a new model output required?** YES: a 49-number score/rank vector for every cutoff.
9. **Is strategy-internal ranking required?** It creates its own number ranking; strategy-internal rank is neither required nor available canonically.
10. **What is the forward path?** New deterministic number-output interface and legal constructor are required before shadow execution.
11. **Could success enter a future Cohort V2?** YES after stable number-level semantics, confirmation, and a separately versioned adapter.
12. **What is the largest leakage risk?** Reconstructing exposure with target tickets/outcomes, fitting normalization globally, or selecting the constructor on held-out results.

- CLOSURE_DECISION: `OPEN`

### H09 — Predictive uncertainty / ensemble dispersion

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `META_SELECTION`
- COLLISION_COUNTS: exact 0; strong 12; weak 16; same-family/different 5; none 100
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PARTIAL`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 4; orthogonality 5; historical testability 4; data readiness 3; forward path 3; compute feasibility 4; potential information gain 5

1. **What different predictive hypothesis is proposed?** The proposed signal is calibrated uncertainty/dispersion and its action rule, not the ensemble mean or a static consensus ticket.
2. **Which of the 133 identities are closest?** `optimized_ensemble`, `predict_consensus_ensemble`, `biglotto_diversified_ensemble`, `predict_6expert`, and `advanced_methods_benchmark`.
3. **Was it tested directly or only by component?** Static ensemble aggregation and disagreement components were tested; calibrated uncertainty output and an uncertainty-conditioned target were not.
4. **What does the closest negative evidence actually negate?** Ensemble native-ticket rules had no corrected positive cells under static composition. This does not test whether calibrated uncertainty predicts failure or improves an abstain/downweight action.
5. **Which distinct conditional variants remain?** Entropy, variance, family disagreement, conformal score; abstain, downweight, or diversify; outcome-specific calibration.
6. **Is sealed evidence sufficient for a fast test?** PARTIAL. Comparable OOF outputs can be assembled for a bounded subset, but canonical calibrated probabilities do not already exist.
7. **Are new derived features required?** Cross-model dispersion, family breadth, calibration bins, prior residual covariance, and portfolio overlap.
8. **Is a new model output required?** YES: calibrated failure-risk/uncertainty plus a frozen action output.
9. **Is strategy-internal ranking required?** Internal ranks are not required; comparable probabilities or scores with an explicit calibration contract are.
10. **What is the forward path?** Requires new calibrated output and a shadow action layer over verified producers.
11. **Could success enter a future Cohort V2?** YES conditionally as a gating layer, not as proof that any base expert has edge.
12. **What is the largest leakage risk?** Calibrating in sample, tuning abstention rate on terminal outcomes, or mixing outputs with incomparable cutoff semantics.

- CLOSURE_DECISION: `OPEN`

### H11 — Pair/triple interaction residual after marginal number scores

- ORIGINAL_STATUS: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`
- PRIMARY_CLUSTER: `HIGHER_ORDER_STRUCTURE`
- COLLISION_COUNTS: exact 0; strong 18; weak 12; same-family/different 10; none 93
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 4; orthogonality 5; historical testability 5; data readiness 4; forward path 3; compute feasibility 3; potential information gain 5

1. **What different predictive hypothesis is proposed?** It estimates held-out pair/triple contribution after subtracting expected contribution from frozen marginal number scores.
2. **Which of the 133 identities are closest?** `evaluate_combinations`, `optimal_2bet_3bet_matrix`, `backtest_apriori`, `cooccurrence_graph`, and `portfolio_optimizer`.
3. **Was it tested directly or only by component?** Pair/triple projections, Apriori, co-occurrence, graph, and ticket portfolios were tested as raw/static components. Residualized interaction after a marginal model was not.
4. **What does the closest negative evidence actually negate?** Those fixed association/portfolio rules lacked corrected positive edge under their own windows and native-ticket semantics. They do not test incremental residual interaction or its held-out target.
5. **Which distinct conditional variants remain?** Pairs only, triples only, hierarchical shrinkage; alternative frozen marginal models; score versus ticket-level residual target.
6. **Is sealed evidence sufficient for a fast test?** YES. The 392,084-combination authority, draw chronology, tickets, hit depth, and baselines are sealed; sparse residual features are derivable.
7. **Are new derived features required?** Expected pair/triple counts from marginals, residual occurrence, recency, shrinkage, and interaction stability.
8. **Is a new model output required?** YES: sparse pair/triple residual scores and incremental ticket score.
9. **Is strategy-internal ranking required?** No historical internal rank is needed; a frozen marginal number score is required.
10. **What is the forward path?** New interaction-scoring output and bounded feature computation are required before forward use.
11. **Could success enter a future Cohort V2?** YES after a sparse stable model and independent confirmation; identity must bind the marginal model and interaction basis.
12. **What is the largest leakage risk?** Residualizing with full-history marginals, screening interactions on target outcomes, or allowing target pairs/triples into their own history.

- CLOSURE_DECISION: `OPEN`

### H13 — Temporal graph change rather than static graph score

- ORIGINAL_STATUS: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`
- PRIMARY_CLUSTER: `HIGHER_ORDER_STRUCTURE`
- COLLISION_COUNTS: exact 0; strong 19; weak 15; same-family/different 14; none 85
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `REQUIRES_SMALL_ADAPTER_WORK`
- SCORES_0_TO_5: novelty 4; orthogonality 4; historical testability 5; data readiness 5; forward path 4; compute feasibility 4; potential information gain 4

1. **What different predictive hypothesis is proposed?** The signal is rolling change in graph edges, motifs, communities, or centrality—not the graph level itself.
2. **Which of the 133 identities are closest?** `cooccurrence_graph`, `graph_predictor`, `backtest_graph_method`, `hot_cooccurrence_analyzer`, and `predict_evolutionary_gum`.
3. **Was it tested directly or only by component?** Static graph/co-occurrence and separate regime/window components were tested. Their causal delta transformation was not.
4. **What does the closest negative evidence actually negate?** Static graph and co-occurrence rules had no corrected positive cells under fixed tickets/windows; regime/drift findings are descriptive or threshold-specific. Neither tests graph change beyond level.
5. **Which distinct conditional variants remain?** Edge-weight delta, community turnover, motif birth/death, centrality velocity; 50/300 or 300/750 change.
6. **Is sealed evidence sufficient for a fast test?** YES. Pair/triple history and strict chronology support rolling snapshots and deltas.
7. **Are new derived features required?** Graph snapshots, edge deltas, community turnover, motif events, and time-shuffled controls.
8. **Is a new model output required?** No new base producer is required; a derived graph-change score/flag is needed.
9. **Is strategy-internal ranking required?** Not required; the derived graph score can feed one fixed ticket constructor.
10. **What is the forward path?** Small derived-feature adapter plus a verified current producer/constructor.
11. **Could success enter a future Cohort V2?** YES after one graph definition/window pair survives confirmation.
12. **What is the largest leakage risk?** Retrospective breakpoint placement, graph normalization over future draws, or selecting motifs on terminal outcomes.

- CLOSURE_DECISION: `OPEN`

### H15 — Multi-objective hit-depth / coverage / overlap / payout-proxy optimizer

- ORIGINAL_STATUS: `PARTIALLY_TESTED`
- PRIMARY_CLUSTER: `PORTFOLIO_OPTIMIZATION`
- COLLISION_COUNTS: exact 0; strong 18; weak 8; same-family/different 10; none 97
- FRONTIER_CLASS: `LIKELY_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `REQUIRES_SMALL_ADAPTER_WORK`
- SCORES_0_TO_5: novelty 3; orthogonality 3; historical testability 5; data readiness 5; forward path 4; compute feasibility 3; potential information gain 4

1. **What different predictive hypothesis is proposed?** It freezes one joint objective and matched-budget trade-off across predicted quality, hit depth, coverage, overlap, and payout proxy.
2. **Which of the 133 identities are closest?** `portfolio_optimizer`, `backtest_biglotto_portfolio`, `covering_strategy_research`, `orthogonal_diversification_benchmark`, and `evaluate_combinations`.
3. **Was it tested directly or only by component?** Each objective component and several optimizers were tested separately. No exact joint objective was located; broad legacy optimizer bodies are unavailable, hence `LIKELY` rather than high-confidence novelty.
4. **What does the closest negative evidence actually negate?** Covering/diversification/portfolio native rules had no corrected positive cells; geometry showed overlap can create a handicap but not predictive edge. That scope does not test one frozen joint Pareto objective.
5. **Which distinct conditional variants remain?** Fixed weight vectors, constrained optimization, lexicographic objective, one ticket budget at a time.
6. **Is sealed evidence sufficient for a fast test?** YES. Ticket candidates, outcomes, exact overlap, hit depth, and payout proxy are sealed.
7. **Are new derived features required?** Normalized candidate score, unique-number coverage, pairwise overlap, hit-depth history, and payout proxy.
8. **Is a new model output required?** No new predictive model; a new deterministic portfolio-selection output is required.
9. **Is strategy-internal ranking required?** A declared candidate score is needed; A/C proxy scores may be used only under their explicit proxy labels.
10. **What is the forward path?** Small optimizer adapter over capability-verified candidate tickets.
11. **Could success enter a future Cohort V2?** YES after objective weights and candidate universe are identity-bound and confirmed.
12. **What is the largest leakage risk?** Tuning weights on terminal outcomes, changing the Pareto endpoint after inspection, or conflating geometry improvement with predictive edge.

- CLOSURE_DECISION: `OPEN`

### H16 — Joint main-number/special-number conditional model

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `OTHER`
- COLLISION_COUNTS: exact 0; strong 0; weak 0; same-family/different 0; none 133
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PARTIAL`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 5; orthogonality 5; historical testability 3; data readiness 2; forward path 2; compute feasibility 3; potential information gain 5

1. **What different predictive hypothesis is proposed?** It models the joint main/special distribution and emits a legal full-ticket prediction; outcome-only special metrics are not a predictor.
2. **Which of the 133 identities are closest?** No 133 identity has meaningful joint special-number overlap; the nearest evidence is the special-hit outcome projection outside the producer collision population.
3. **Was it tested directly or only by component?** Special outcomes and main-ticket producers exist separately. No legal joint predictive transformation/output was recovered.
4. **What does the closest negative evidence actually negate?** The 133 negatives cover main-ticket producers. Special-number ranking identities were closed because they lacked legal full-ticket construction, so they do not falsify a joint model.
5. **Which distinct conditional variants remain?** Special conditional on main summary; shared latent state; factorized versus copula-like joint score; calibrated joint prize probability.
6. **Is sealed evidence sufficient for a fast test?** PARTIAL. Main/special histories and exact outcomes exist, but a legal joint output contract and new calibrated model are required.
7. **Are new derived features required?** Main-number state, special-number history, joint co-occurrence, conditional regime, and exact prize mapping.
8. **Is a new model output required?** YES: joint probabilities and a legal main-plus-special ticket score.
9. **Is strategy-internal ranking required?** Historical strategy rank is not required; the joint model creates its own calibrated score.
10. **What is the forward path?** New model output, constructor, runtime, and adapter are required.
11. **Could success enter a future Cohort V2?** YES only after a legal deterministic contract and independent historical confirmation.
12. **What is the largest leakage risk?** Using the realized special number in feature construction, conditioning on future main outcomes, or tuning joint factorization on the terminal block.

- CLOSURE_DECISION: `OPEN`

### H18 — HMM latent-regime gating

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `TEMPORAL_STATE`
- COLLISION_COUNTS: exact 0; strong 12; weak 10; same-family/different 25; none 86
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 4; orthogonality 4; historical testability 4; data readiness 4; forward path 3; compute feasibility 2; potential information gain 5

1. **What different predictive hypothesis is proposed?** It filters latent state probabilities causally and gates allocation; static observed bands and Markov number transitions are different information/target contracts.
2. **Which of the 133 identities are closest?** `predict_evolutionary_gum`, `backtest_biglotto_markov_4bet`, `backtest_markov_repeat_exception`, `backtest_biglotto_6bet_ewma`, and `dynamic_frequency_predictor`.
3. **Was it tested directly or only by component?** Regime, Markov, EWMA, and frequency components were tested. No causal HMM filtering plus state-to-allocation composition was found.
4. **What does the closest negative evidence actually negate?** Fixed Markov/EWMA/regime producers lacked global corrected edge, while regime cells were exploratory and often reversed. This does not test latent state probabilities or filtered gating.
5. **Which distinct conditional variants remain?** Two versus three states; emission on frozen axes versus raw counts; fixed versus sticky transitions; expert-choice versus ticket-weight gate.
6. **Is sealed evidence sufficient for a fast test?** YES historically. Ordered features, regimes, outcomes, and baselines exist; deterministic filtered-state output is new.
7. **Are new derived features required?** Frozen regime axes, transition counts, filtered probabilities, state duration, and prior expert residuals.
8. **Is a new model output required?** YES: filtered HMM state probabilities and allocation output.
9. **Is strategy-internal ranking required?** Not required; state outputs act on fixed producer portfolios.
10. **What is the forward path?** New deterministic HMM runtime/output and shadow gate are required.
11. **Could success enter a future Cohort V2?** YES after state identity, initialization, and allocation map are frozen and confirmed.
12. **What is the largest leakage risk?** Using smoothed states at evaluation time, selecting state count on terminal outcomes, or retrospective state relabeling.

- CLOSURE_DECISION: `OPEN`

### H20 — Entropy/distribution-shift anomaly gating

- ORIGINAL_STATUS: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`
- PRIMARY_CLUSTER: `TEMPORAL_STATE`
- COLLISION_COUNTS: exact 0; strong 16; weak 12; same-family/different 15; none 90
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `FORWARD_READY_WITH_EXISTING_51`
- SCORES_0_TO_5: novelty 4; orthogonality 4; historical testability 5; data readiness 5; forward path 5; compute feasibility 5; potential information gain 4

1. **What different predictive hypothesis is proposed?** A predeclared entropy/divergence anomaly triggers an allocation change; descriptive drift or fixed deviation selection is not the same gate.
2. **Which of the 133 identities are closest?** `optimize_deviation_extreme_generic`, `biglotto_2bet_optimizer`, `predict_evolutionary_gum`, `backtest_biglotto_6bet_ewma`, and `backtest_p0p1_upgrade`.
3. **Was it tested directly or only by component?** Deviation/anomaly producers and regime/drift descriptors exist, but no frozen distribution-shift event controlling allocation was located.
4. **What does the closest negative evidence actually negate?** Deviation producers had no corrected positive edge under fixed rules; regime/drift positives were exploratory or threshold-sensitive. Neither tests an outcome-blind anomaly timestamp and paired action.
5. **Which distinct conditional variants remain?** Entropy delta, Jensen–Shannon divergence, tail-mass shift; 50/300 versus 300/750; activate, abstain, or diversify.
6. **Is sealed evidence sufficient for a fast test?** YES. Required window distributions and regime descriptors are available/derivable.
7. **Are new derived features required?** Entropy, divergence, tail mass, event duration, event rate, and prior-only allocation context.
8. **Is a new model output required?** No new predictive model; a frozen anomaly flag/action is sufficient.
9. **Is strategy-internal ranking required?** Not required.
10. **What is the forward path?** Can overlay verified current producers after a small event/action adapter.
11. **Could success enter a future Cohort V2?** YES as a separately versioned gate after event-count and blocked confirmation.
12. **What is the largest leakage risk?** Choosing thresholds from target performance, retrospective event placement, or adapting the event rule after each outcome.

- CLOSURE_DECISION: `OPEN`

### H22 — Conditional/nested exact null and paired counterfactual calibration

- ORIGINAL_STATUS: `PARTIALLY_TESTED`
- PRIMARY_CLUSTER: `OTHER`
- COLLISION_COUNTS: exact 0; strong 11; weak 0; same-family/different 0; none 122
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `HISTORICAL_ONLY_FOR_NOW`
- SCORES_0_TO_5: novelty 3; orthogonality 5; historical testability 5; data readiness 5; forward path 1; compute feasibility 4; potential information gain 5

1. **What different predictive hypothesis is proposed?** It reproduces an adaptive selector inside the null and evaluates a paired no-action counterfactual; fixed unconditional baselines answer a different question.
2. **Which of the 133 identities are closest?** `scientific_baseline_report`, `sbp_baseline_check`, `compare_random_vs_smart`, `historical_audit_rigorous`, and `big_lotto_exhaustive_audit`.
3. **Was it tested directly or only by component?** Exact baselines and fixed-contract evaluation exist. Selection-aware conditional/nested calibration was not found.
4. **What does the closest negative evidence actually negate?** The 17,024-cell robustness analysis is valid for its fixed family/windows/nulls. A changed adaptive family needs its own conditional null; previous negatives do not validate or invalidate that layer.
5. **Which distinct conditional variants remain?** Nested exact randomization, paired permutation, conditional Poisson-binomial, e-values; selector-specific conditioning sets.
6. **Is sealed evidence sufficient for a fast test?** YES when bound to one frozen selector. Exact combinatorics, paired outcomes, and chronology are reusable.
7. **Are new derived features required?** Outer/inner fold ledger, selector path, conditional null strata, paired deltas, and correction-family identity.
8. **Is a new model output required?** No predictive model output; it generates calibrated evidence and coverage diagnostics.
9. **Is strategy-internal ranking required?** Not required except as an explicitly frozen input to the linked selector.
10. **What is the forward path?** Historical evaluation infrastructure first; it is not a standalone forward producer.
11. **Could success enter a future Cohort V2?** NO as a candidate. If validated, it becomes an evaluation requirement for adaptive Cohort V2 candidates.
12. **What is the largest leakage risk?** Failing to replay selection inside the null, conditioning on target outcomes, or defining the correction family after results.

- CLOSURE_DECISION: `OPEN`

### H23 — LSTM as residual/meta-feature, not direct ticket generator

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `NUMBER_LEVEL_MODEL`
- COLLISION_COUNTS: exact 0; strong 12; weak 3; same-family/different 6; none 112
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PARTIAL`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 4; orthogonality 5; historical testability 3; data readiness 2; forward path 2; compute feasibility 1; potential information gain 4

1. **What different predictive hypothesis is proposed?** A deterministic causal LSTM embedding is produced out of fold and used only as a residual/meta-feature, not as a direct ticket generator.
2. **Which of the 133 identities are closest?** `advanced_methods_benchmark`, `optimized_ensemble`, `predict_6expert`, `attention_replay_predictor`, and `xgboost_model`.
3. **Was it tested directly or only by component?** Static ML/ensemble and attention-replay components exist. Closed LSTM identities lacked analyzable deterministic contracts and were not this residual target.
4. **What does the closest negative evidence actually negate?** No 133 LSTM parity test exists. ML producer negatives cover their exact historical features/output; they do not test a seeded OOF LSTM embedding.
5. **Which distinct conditional variants remain?** Sequence length, residual target, embedding width, number-level versus expert-level consumer—one bounded variant per family.
6. **Is sealed evidence sufficient for a fast test?** PARTIAL. Ordered data exist, but deterministic runtime, embeddings, and nested training must be created.
7. **Are new derived features required?** Causal sequences, lagged outcomes/residuals, masks, and OOF embedding.
8. **Is a new model output required?** YES: deterministic LSTM embedding and residual prediction.
9. **Is strategy-internal ranking required?** Not required; embedding feeds a frozen comparator/meta-model.
10. **What is the forward path?** New deterministic model runtime/output and adapter are required.
11. **Could success enter a future Cohort V2?** YES only after reproducibility, seed stability, blocked gain, and adapter validation.
12. **What is the largest leakage risk?** Bidirectional/future context, global normalization, in-sample embeddings, or architecture search on terminal outcomes.

- CLOSURE_DECISION: `OPEN`

### H24 — Transformer as residual/meta-feature

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `NUMBER_LEVEL_MODEL`
- COLLISION_COUNTS: exact 0; strong 13; weak 2; same-family/different 6; none 112
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PARTIAL`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 5; orthogonality 5; historical testability 3; data readiness 2; forward path 2; compute feasibility 1; potential information gain 5

1. **What different predictive hypothesis is proposed?** A causal masked Transformer embedding is trained out of fold for a residual/meta target; attention replay as a direct producer is not parity.
2. **Which of the 133 identities are closest?** `attention_replay_predictor`, `advanced_methods_benchmark`, `optimized_ensemble`, `predict_6expert`, and `xgboost_model`.
3. **Was it tested directly or only by component?** Attention/ML/ensemble primitives exist, but no deterministic causal Transformer residual embedding contract was tested.
4. **What does the closest negative evidence actually negate?** Attention replay and other ML native-ticket negatives apply to those exact direct outputs. They do not test a causal masked OOF representation used by a separate meta-model.
5. **Which distinct conditional variants remain?** Sequence length, positional encoding, width/depth, residual target; keep one preregistered minimal encoder per test.
6. **Is sealed evidence sufficient for a fast test?** PARTIAL. Data are adequate, but a deterministic encoder/output does not exist and compute is high.
7. **Are new derived features required?** Causal sequences, masks, lagged outcomes/residuals, and OOF embeddings.
8. **Is a new model output required?** YES: deterministic Transformer embedding and residual score.
9. **Is strategy-internal ranking required?** Not required.
10. **What is the forward path?** New model runtime/output, reproducibility contract, and forward adapter are required.
11. **Could success enter a future Cohort V2?** YES only after minimal-model confirmation and exact runtime fingerprinting.
12. **What is the largest leakage risk?** Noncausal attention, full-series normalization, overlapping folds, or model selection on terminal outcomes.

- CLOSURE_DECISION: `OPEN`

### H25 — XGBoost stacking strategy outputs and history

- ORIGINAL_STATUS: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`
- PRIMARY_CLUSTER: `META_SELECTION`
- COLLISION_COUNTS: exact 0; strong 13; weak 15; same-family/different 5; none 100
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PASS`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 3; orthogonality 3; historical testability 5; data readiness 5; forward path 3; compute feasibility 4; potential information gain 4

1. **What different predictive hypothesis is proposed?** The XGBoost target is cross-strategy residual/selection using prior output history; the tested XGBoost identity was a direct producer.
2. **Which of the 133 identities are closest?** `xgboost_model`, `advanced_methods_benchmark`, `optimized_ensemble`, `predict_consensus_ensemble`, and `predict_6expert`.
3. **Was it tested directly or only by component?** Direct XGBoost and static ensemble components were tested, but no blocked-CV residual stacker with the same information set and target was found.
4. **What does the closest negative evidence actually negate?** `xgboost_model` had 0 positive and 11 negative corrected cells for its historical feature/selection/native-ticket contract. It does not negate residual stacking.
5. **Which distinct conditional variants remain?** Binary failure risk versus continuous residual; shallow depth; family-aggregated versus identity-level inputs; one feature family per test.
6. **Is sealed evidence sufficient for a fast test?** YES. Strategy output/history, families, outcomes, and exact baselines are sealed; the stacker output is new.
7. **Are new derived features required?** Lagged outputs, prior residuals, disagreement, window slopes, regime descriptors, and geometry.
8. **Is a new model output required?** YES: OOF residual/failure score or expert weights.
9. **Is strategy-internal ranking required?** No internal rank is required.
10. **What is the forward path?** New deterministic shallow stacker output and shadow adapter are required.
11. **Could success enter a future Cohort V2?** YES after incremental gain over a linear stacker and independent confirmation.
12. **What is the largest leakage risk?** In-sample residuals, target-derived feature selection, early stopping on terminal blocks, or importing H01 outcomes.

- CLOSURE_DECISION: `OPEN`

### H26 — Special-aware portfolio geometry

- ORIGINAL_STATUS: `NOT_TESTED`
- PRIMARY_CLUSTER: `PORTFOLIO_OPTIMIZATION`
- COLLISION_COUNTS: exact 0; strong 12; weak 8; same-family/different 10; none 103
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PARTIAL`
- FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`
- SCORES_0_TO_5: novelty 5; orthogonality 5; historical testability 3; data readiness 2; forward path 2; compute feasibility 3; potential information gain 5

1. **What different predictive hypothesis is proposed?** It optimizes main-ticket overlap and special-number coverage jointly under the exact prize contract; main-only geometry is incomplete.
2. **Which of the 133 identities are closest?** `portfolio_optimizer`, `backtest_biglotto_portfolio`, `covering_strategy_research`, `orthogonal_diversification_benchmark`, and `research_true_orthogonal`.
3. **Was it tested directly or only by component?** Portfolio geometry and special-hit outcomes exist separately. No special-aware joint objective/output was found.
4. **What does the closest negative evidence actually negate?** Existing portfolio/cover/diversification negatives and anti-bias findings apply to main-number geometry under fixed semantics. They do not test joint special coverage.
5. **Which distinct conditional variants remain?** Special concentration penalty, joint coverage, prize-tier-weighted geometry; fixed budget and candidate set.
6. **Is sealed evidence sufficient for a fast test?** PARTIAL. Main geometry and special outcomes exist, but legal special-aware candidate tickets/joint score must be defined.
7. **Are new derived features required?** Main overlap, unique coverage, special concentration, joint ticket coverage, pair/triple structure, and exact prize mapping.
8. **Is a new model output required?** YES: at least a new special-aware portfolio score/output; it may consume H16 output but must not assume H16 success.
9. **Is strategy-internal ranking required?** A declared candidate score is required; historical internal rank is not.
10. **What is the forward path?** New joint ticket representation/output and optimizer adapter are required.
11. **Could success enter a future Cohort V2?** YES only after a legal joint contract and matched-budget confirmation.
12. **What is the largest leakage risk?** Tuning special weights on terminal prizes, using realized special outcomes in candidate construction, or changing candidate universe after results.

- CLOSURE_DECISION: `OPEN`

### H28 — Prospective confirmation of frozen EWMA drift H1/H2

- ORIGINAL_STATUS: `PARTIALLY_TESTED`
- PRIMARY_CLUSTER: `TEMPORAL_STATE`
- COLLISION_COUNTS: exact 0; strong 1; weak 13; same-family/different 16; none 103
- FRONTIER_CLASS: `HIGH_CONFIDENCE_NOT_TRIED`
- DATA_SUFFICIENCY: `PARTIAL_TIME_GATED`
- FORWARD_READINESS: `FORWARD_READY_NOW`
- SCORES_0_TO_5: novelty 2; orthogonality 3; historical testability 1; data readiness 5; forward path 5; compute feasibility 5; potential information gain 4

1. **What different predictive hypothesis is proposed?** The untried dimension is calendar-gated post-freeze confirmation of the exact q67/H1 15-ticket/H2 20-ticket contract; another retrospective partition is not confirmation.
2. **Which of the 133 identities are closest?** `backtest_biglotto_6bet_ewma`, `dynamic_frequency_predictor`, `predict_evolutionary_gum`, `backtest_biglotto_hot_stop_rebound`, and `rgf_walkforward_validator`.
3. **Was it tested directly or only by component?** The base EWMA producer and historical/event-influence H1/H2 were tested. Prospective temporal semantics have not occurred because the post-freeze count is 0.
4. **What does the closest negative evidence actually negate?** Historical q67 point estimates were positive, ±0.001 threshold bounds crossed zero, and only eight HIGH events were present in the latest audit. This neither confirms nor prospectively falsifies frozen H1/H2.
5. **Which distinct conditional variants remain?** The frozen q67 H1/H2 has no permitted adaptive variant. Other thresholds or drift features must be separately named hypotheses and cannot modify this observer.
6. **Is sealed evidence sufficient for a fast test?** NO for the predictive question now: compute is trivial, but evidence is calendar-gated. Only protocol integrity can be checked immediately.
7. **Are new derived features required?** No new feature; retain the exact frozen SHORT_MEDIUM_DRIFT/HIGH event flag and sequential evidence state.
8. **Is a new model output required?** No new model output; reuse the exact frozen EWMA portfolios/protocol.
9. **Is strategy-internal ranking required?** Not required.
10. **What is the forward path?** Protocol/observer is ready now, but post-freeze accumulation remains zero and no re-freeze is allowed.
11. **Could success enter a future Cohort V2?** Potentially, only after independent prospective confirmation and as a separately versioned candidate; do not alter V1.
12. **What is the largest leakage risk?** Backfilling pre-freeze observations, changing q67/event definition, threshold peeking, or counting historical holdouts as prospective.

- CLOSURE_DECISION: `OPEN`

## Cross-hypothesis clustering for all 28 open hypotheses

Clusters are management labels only. No distinct hypothesis is merged, removed, or closed because another hypothesis shares its cluster.

| Primary cluster | Canonical hypothesis IDs |
|---|---|
| META_SELECTION | H01, H02, H03, H05, H06, H09, H25 |
| TEMPORAL_STATE | H04, H18, H19, H20, H28 |
| NUMBER_LEVEL_MODEL | H07, H08, H23, H24 |
| TICKET_LEVEL_MODEL | H10 |
| PORTFOLIO_OPTIMIZATION | H14, H15, H26 |
| HIGHER_ORDER_STRUCTURE | H11, H12, H13 |
| NEGATIVE_INFORMATION | H21 |
| BAYESIAN_DYNAMIC | H17 |
| OTHER | H16, H22, H27 |

## Forward-readiness projection

- FORWARD_READY_NOW_COUNT: 1
- FORWARD_READY_NOW: H28
- FORWARD_READY_WITH_EXISTING_51_COUNT: 3
- FORWARD_READY_WITH_EXISTING_51: H05, H06, H20
- REQUIRES_SMALL_ADAPTER_WORK_COUNT: 3
- REQUIRES_SMALL_ADAPTER_WORK: H02, H13, H15
- REQUIRES_NEW_MODEL_OUTPUT_COUNT: 10
- REQUIRES_NEW_MODEL_OUTPUT: H03, H08, H09, H11, H16, H18, H23, H24, H25, H26
- HISTORICAL_ONLY_FOR_NOW_COUNT: 1
- HISTORICAL_ONLY_FOR_NOW: H22

This is a read-only projection. `FORWARD_READY_NOW` for H28 means the frozen observer/protocol exists; it does not mean evidence exists or the hypothesis passed. The exact per-family join within the 51 current-executable historical identities remains [Unknown].

## Second-wave research queue

This queue does not replace H01–H10 and does not authorize execution. The diversity constraint deliberately spans temporal state, cross-strategy error geometry, higher-order residual structure, calibrated uncertainty, and number-level ranking.

1. H20 — Entropy/distribution-shift anomaly gating
2. H02 — Complementary-error graph across strategies
3. H11 — Pair/triple interaction residual after marginal number scores
4. H09 — Predictive uncertainty / ensemble dispersion
5. H08 — Per-number ranking-loss model

## Top-5 long shots preserved

1. H16 — Joint main-number/special-number conditional model
2. H26 — Special-aware portfolio geometry
3. H24 — Transformer as residual/meta-feature
4. H23 — LSTM as residual/meta-feature, not direct ticket generator
5. H18 — HMM latent-regime gating

## What we have not tried

- HIGH_CONFIDENCE_NOT_TRIED_COUNT: 17
- HIGH_CONFIDENCE_NOT_TRIED: H02, H03, H05, H06, H08, H09, H11, H13, H16, H18, H20, H22, H23, H24, H25, H26, H28
- LIKELY_NOT_TRIED_COUNT: 1
- LIKELY_NOT_TRIED: H15
- UNCERTAIN_COUNT: 0

The standalone frontier document records the exact forms and non-equivalence rationale. `NOT_TRIED` is not a likelihood or success claim.

## Data sufficiency conclusion

DATA_SUFFICIENCY: PARTIAL

- PASS for identity, family, draw/cutoff, native tickets/count, hit depth, special-hit outcome, exact baseline, historical delta, windows, actual draw outcomes, eligible draws, and derivable portfolio geometry.
- PARTIAL for Candidate-K/direct number paths, regime coverage, runtime/adapter joins, and hypothesis-specific pair/triple consumers.
- AVAILABLE_PROXY_ONLY for A/C ranking-like layers; they remain explicitly non-internal-rank proxies.
- UNAVAILABLE as pre-existing canonical outputs for calibrated probabilities and several new neural/stacking/joint models. Those are model products to be generated inside a future experiment, not authority facts to invent now.

## Validation and non-interference

- remaining hypotheses = 18/18 — PASS
- historical identities = 133/133 — PASS
- collision rows = 2,394 — PASS
- each hypothesis has 25 sufficiency-field assessments — PASS
- each hypothesis has one complete Level-1 spec — PASS
- SECOND_WAVE_TOP_5 = exactly 5 — PASS
- TOP_5_LONG_SHOTS = exactly 5 — PASS
- WHAT_WE_HAVE_NOT_TRIED generated — PASS
- method-family similarity classified as exact duplicate = 0 — PASS
- experiments executed = 0 — PASS
- strategy implementation = NONE
- repo mutation by Track D = NONE at report creation checkpoint
- DB mutation = NONE
- sealed `.task-data` mutation = NONE
- Track B H01 interference = NONE

## Scoped unknowns

1. The 49a25e historical source bodies are not locally available; source-body parity is not claimed.
2. Exact per-family forward membership inside the population-level 51/82 split was not recomputed.
3. No external-method/network refresh was run; external methods remain unverified until a separate local replication.
4. H28 elapsed time to a minimum prospective event count is unknown and cannot be accelerated analytically.
5. No hypothesis performance result exists because every Level-1 experiment is intentionally NOT RUN.

## Final research boundary

All 18 remaining hypotheses stay `OPEN`. None is closed as an exact duplicate, logically equivalent prior test, future-information definition, output-less claim, or impossible-with-derivable-input claim. Cost, low prior, family negatives, missing current adapter, and lottery randomness were recorded as constraints—not closure reasons.

NEXT: Use `SECOND_WAVE_TOP_5` as the next research queue after the current Top-10 program.

END
