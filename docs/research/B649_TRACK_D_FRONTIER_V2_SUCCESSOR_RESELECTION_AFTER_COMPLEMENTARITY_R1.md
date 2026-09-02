# B649 Track D Frontier V2 Successor Reselection After Complementarity R1

TASK_ID: B649_TRACK_D_FRONTIER_V2_SUCCESSOR_RESELECTION_AFTER_COMPLEMENTARITY_R1  
STATUS: PASS  
MODE: READ_ONLY_RESEARCH_DIRECTION_DECISION  
CORE_OBJECTIVE: MAXIMIZE_PREDICTION_SUCCESS_RATE

## 1. Latest B result and decision basis

LATEST_B_RESULT: CAUSAL_COMPLEMENTARITY_AWARE_CANDIDATE_SCORE_STACKING  
LATEST_B_DECISION: DO_NOT_ADVANCE

LATEST_HELDOUT_M2_PLUS:

- COMPLEMENTARITY_STACK: 21.67%
- STRONGEST_SINGLE: 18.33%
- FLAT_STACK: 20.00%
- STATIC_CONSENSUS: 22.33%

[Confirmed] The sealed B report and direct held-out result table agree on all four rates. The search ledger contains 936 configurations plus one header row; held-out data was not used for configuration, parameter, feature, or strategy-subset selection. `COMPLEMENTARITY_ADDED_VALUE: UNCERTAIN`, `EVIDENCE_STRENGTH: WEAK`, and `DISCOVERY_DECISION: DO_NOT_ADVANCE` are the final sealed findings.

[Confirmed] The named Frontier V2 authorities retain H08 as an unexecuted per-number ranking-loss direction with medium readiness/cost, and EH04 as an unexecuted, low-cost, high-readiness symbolic residual direction. No Frontier regeneration, 133-strategy collision audit, or external search was performed.

SOURCES_OPENED: `.task-data/B649_TRACK_B_COMPLEMENTARITY_AWARE_CANDIDATE_STACK_DISCOVERY_R1/report.md`; its direct `heldout_results.csv`, `baseline_results.csv`, `locked_configuration.json`, `ablation_results.csv`, and `search_ledger.csv`; `B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2_NORMALIZED_R1.csv`; `B649_TRACK_D_FRONTIER_V2_DISCOVERY_WAVES_R1.csv`; `B649_TRACK_D_FRONTIER_V2_SPEC_REGISTRY_R1.csv`; `B649_TRACK_D_FRONTIER_V2_COVERAGE_AND_SATURATION_R1.md`; and `B649_TRACK_D_FRONTIER_V2_SUCCESSOR_SELECTION_R1.md`.

[Inferred] The result supports a narrow prioritization update, not a family closure:

1. Multi-strategy aggregation may contain useful pooled information because 21.67% exceeded the strongest single strategy's 18.33%.
2. The tested complementarity weighting did not establish incremental value: its 1.67-point advantage over the flat stack was weak and uncertain.
3. Static consensus remains the strongest observed comparator at 22.33%; the next unit of research should improve candidate ordering, not portfolio geometry or another subset-weighting formula.

[Unknown] Whether any proposed successor will outperform static consensus on held-out M2+; this document selects the experiment with the highest expected information value, not a proven predictive edge.

COULD_NOT_VERIFY: Future or prospective performance. Frontier V2's external-method claims were not refreshed because this task explicitly forbids external search; they are used only as existing planning provenance, not as new evidence of efficacy.

## 2. Top three next directions

### 1

TITLE: CONSENSUS_PLUS_PAIRWISE_RESIDUAL_RERANK  
ORIGIN: NEW_SYNTHESIS_FROM_EXISTING_RESULTS  
CORE_MECHANISM: Freeze static consensus as the base per-number score, then learn a bounded causal residual correction using pairwise/listwise top-six ranking loss. Search only strict-prior consensus margins, strategy-support/rank dispersion, family breadth, residual-reliability features, candidate depth, regularization, and correction strength. Emit exactly one deterministic legal ticket.  
WHY_IT_COULD_BEAT_STATIC_CONSENSUS: Static consensus averages support but does not learn which near-boundary inversions are systematically costly. A residual ranker can preserve the strong base while correcting only historically repeatable top-six ordering errors.  
EXPECTED_INFORMATION_GAIN: HIGH  
DATA_READINESS: HIGH  
IMPLEMENTATION_COST: MEDIUM  
DISCOVERY_SEARCH_FRIENDLY: YES

### 2

TITLE: H08_PAIRWISE_LISTWISE_PER_NUMBER_RANKING  
ORIGIN: EXISTING_FRONTIER_V2_H08  
CORE_MECHANISM: Train a standalone causal per-number ranker with pairwise/listwise loss so relative number ordering—not absolute calibration or raw support—is the learning target; project the locked top six into one legal ticket.  
WHY_IT_COULD_BEAT_STATIC_CONSENSUS: Its objective directly penalizes top-six misordering and can learn nonlinear relative preferences that equal-weight support cannot express.  
EXPECTED_INFORMATION_GAIN: HIGH  
DATA_READINESS: MEDIUM  
IMPLEMENTATION_COST: MEDIUM  
DISCOVERY_SEARCH_FRIENDLY: YES

### 3

TITLE: EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER  
ORIGIN: EXISTING_FRONTIER_V2_EH04  
CORE_MECHANISM: Encode strict-prior residual/number-state sequences symbolically and use variable-order context-tree weighting to forecast conditional residual information, then convert the locked causal score into one deterministic legal ticket.  
WHY_IT_COULD_BEAT_STATIC_CONSENSUS: It introduces variable-depth temporal context that a static cross-strategy vote does not represent and that fixed-window/state designs may miss.  
EXPECTED_INFORMATION_GAIN: MEDIUM  
DATA_READINESS: HIGH  
IMPLEMENTATION_COST: LOW  
DISCOVERY_SEARCH_FRIENDLY: YES

## 3. Selected direction

NEXT_RESEARCH_DIRECTION: CONSENSUS_PLUS_PAIRWISE_RESIDUAL_RERANK

ORIGIN: NEW_SYNTHESIS_FROM_EXISTING_RESULTS

WHY_THIS_DIRECTION_NOW: It uses the latest experiment's strongest positive fact—static consensus is the best observed comparator—while changing the mechanism that failed. The base score is frozen; the new test is whether a ranking-loss residual layer can make better top-six boundary decisions, not whether another complementarity or subset weight can improve the same stack.

WHAT_NEW_INFORMATION_IT_TESTS: Whether causal features describing consensus confidence, support shape, and prior consensus errors contain enough relative-order information to improve one-ticket held-out M2+ beyond the uncorrected consensus.

WHY_IT_IS_BETTER_THAN_DIRECTION_2: Standalone H08 must relearn both the broad signal already captured by consensus and its residual errors. Anchoring the model to consensus isolates incremental ranking value, reduces the chance of discarding a strong base, raises data readiness, and still includes a standalone H08 arm to measure whether the anchor helps.

WHY_IT_IS_BETTER_THAN_DIRECTION_3: EH04 is highly orthogonal and cheaper, but its first evidence path is conditional sequence/proper-loss improvement before ticket-level gain. The selected direction directly optimizes the current bottleneck and primary endpoint using already sealed strategy-support inputs.

WHAT_STATIC_CONSENSUS_DOES_NOT_CAPTURE: The asymmetric cost of top-six boundary inversions; confidence encoded by consensus score margins; disagreement shape and family breadth behind the same total support; and strict-prior contexts in which consensus has repeatedly promoted or suppressed the wrong borderline number.

WHAT_FAILURE_WOULD_TEACH_US: If a bounded residual reranker cannot beat the untouched consensus, candidate-quality gains are unlikely to come from another transformation of the same strategy-support surface. The next pivot should then be EH04's genuinely new temporal representation, not another complementarity, subset-weighting, or portfolio-diversity variant.

## 4. Minimal Track B handoff

NEXT_B_TASK_ID: B649_TRACK_B_CONSENSUS_PLUS_PAIRWISE_RESIDUAL_RERANK_DISCOVERY_R1

TITLE: Consensus Plus Pairwise Residual Rerank Discovery

ORIGIN: NEW_SYNTHESIS_FROM_EXISTING_RESULTS

RESEARCH_QUESTION: Can a bounded causal pairwise/listwise residual correction to frozen static-consensus scores produce a one-ticket top-six ranking with materially higher held-out M2+ than untouched static consensus?

DISCOVERY_MODE: YES

SEARCH_SPACE: Pairwise logistic, listwise softmax, and top-six-weighted ranking losses; feature subsets from frozen consensus score/rank/margin, strategy support and rank dispersion, family breadth, and strict-prior consensus residual reliability; candidate-pool K; regularization; bounded residual blend strength; deterministic tie rule. Search may choose these only on chronological search data. Ticket multiplicity, portfolio geometry, held-out blocks, and post-held-out rescue tuning are fixed or excluded.

SEARCH_DATA: Targets 103000001–113000005 (n=1,117), with nested chronological validation and every target's features/model state cut off at t-1.

HELD_OUT_DATA: Targets 113000006–115000069 (n=300), unavailable to within-task configuration choice; lock one configuration before loading outcomes and report six consecutive 50-target blocks. Because this period's aggregate comparator rate is already known from the prior B task, treat it as a discovery holdout, not fresh confirmatory or prospective evidence.

PRIMARY_BASELINE: STATIC_CONSENSUS

OTHER_BASELINES: STRONGEST_SINGLE; STANDALONE_H08_PAIRWISE_LISTWISE_RANKER; LATEST_COMPLEMENTARITY_STACK; EXACT_ONE_TICKET_RANDOM

PRIMARY_SUCCESS_METRIC: ONE_TICKET_HELD_OUT_M2_PLUS

STOP_OR_PIVOT_RULE: `DO_NOT_ADVANCE` if the locked method improves static consensus by less than 2.00 percentage points (fewer than six additional M2+ targets out of 300), is positive in fewer than four of six chronological blocks, improves only search data, changes rankings without improving hit depth, or needs unbounded complexity/rescue tuning. `ADVANCE` only with at least +2.00 points versus static consensus, positive delta in at least four blocks, identical one-ticket budget/target universe, and no held-out selection. On failure, pivot to EH04 rather than another weighting or portfolio variant.

EXPECTED_OUTPUT: One compact B discovery report; one serialized locked configuration; complete search-versus-held-out ledger; per-target predictions for the selected method and all baselines; overall/block M1+/M2+/M3+/M4+ results; ranking diagnostics; leakage/equal-budget checks; final `ADVANCE` or `DO_NOT_ADVANCE`.

COHORT_V2_PROSPECTIVE_DATA_USED: NO  
REPO_MUTATION: NONE  
DB_MUTATION: NONE  
BLOCKERS: NONE  
NEXT: Send this compact selected direction to Track B for implementation-first discovery.

END
