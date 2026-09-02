# B649 Track D Frontier V2 Successor Selection R1

TASK_ID: B649_TRACK_D_FRONTIER_V2_SUCCESSOR_SELECTION_R1  
STATUS: PASS  
MODE: READ_ONLY_RESEARCH_DIRECTION_DECISION  
CORE_OBJECTIVE: MAXIMIZE_PREDICTION_SUCCESS_RATE_RESEARCH_VALUE

## 1. CURRENT_RESEARCH_STATE

ORIGINAL_TOP10_FIRST_PASS_STATUS: EXHAUSTED_OR_DEFERRED  
EXECUTED_NOT_ADVANCED: 9  
STRUCTURALLY_DEFERRED: 1  
SELECTABLE_REMAINING_IN_ORIGINAL_TOP10: 0  
FRONTIER_V2_SIZE: 49  
FRONTIER_V2_STATUS: NOT_SATURATED

The nine exact Level-1 designs are closed as `CURRENT_DESIGN_NEGATIVE`; this does not permanently reject their broad research families. H02/H27 remains `STRUCTURALLY_DEFERRED`, not negative.

CUMULATIVE_BOTTLENECK_INFERENCE: SUPPORTED_FOR_PRIORITIZATION_NOT_ESTABLISHED_AS_THEOREM

The evidence supports moving the next unit of work toward `CANDIDATE_QUALITY + CONDITIONAL_PREDICTIVE_INFORMATION` and away from `FINAL_PORTFOLIO_GEOMETRY`. The strongest reason is not one positive result, but the joint pattern: geometry changed without predictive gain, while several candidate-, residual-, and state-level designs produced weak clues that did not survive their full advancement gates.

The normalized Frontier V2 status columns predate several sealed results. For first-pass disposition, the nine sealed Track B reports and this task's authoritative packet take precedence over stale registry labels.

## 2. KEY_LESSONS_FROM_FIRST_PASS

1. `PORTFOLIO_GEOMETRY` is `LOW_PRIORITY_FOR_NOW`. H06/H14 materially changed overlap, diversity, and coverage, but produced `NO_PORTFOLIO_EFFICIENCY_SIGNAL` and `NO_SIGNAL` on predictive outcomes. Better arrangement of the same candidate material did not create better candidates.
2. `WEAK_CLUE` exists at the candidate/information layer, but no tested design is selectable. H04/H07 produced a small, stable proper-score improvement without an actionable number-selection result; H05/H10 produced a distinct direct-ticket ranking with positive point estimates in 4/5 folds but negative uncertainty bounds; H10/H17 beat trailing-50 but was indistinguishable from static Beta; H01, H07, and H09 showed small conditional or cross-strategy point estimates that failed strong-comparator, stability, or uncertainty gates.
3. Simple strong comparators remain decisive. H03/H04 found no incremental information in the tested multi-window contrasts, H08/H12 found no temporal-hypergraph gain over static structure, and H10/H17 added no meaningful edge over static Beta. The next experiment should test whether different strategies contain complementary errors that can improve the candidate score itself, not add another regime gate to a weak base score.

RESEARCH_FAMILY_STATUS:

- Cross-strategy complementarity: `UNTESTED` as a candidate-scoring mechanism; `WORTH_REVISITING_DIFFERENTLY` from H01.
- Candidate-quality stacking/ranking: `WEAK_CLUE`; exact proposed mechanism untested.
- Dynamic gating/weighting: `WEAK_CLUE`, but lower priority until candidate quality improves.
- Pair/triple and temporal motif structure: tested designs `CURRENT_DESIGN_NEGATIVE`; broader families remain open.
- Portfolio geometry alone: `LOW_PRIORITY_FOR_NOW`.
- Information-theoretic conditional forecasting: `UNTESTED` and retained as a low-cost fallback.

## 3. TOP_3_NEXT_DIRECTIONS

### 1

TITLE: CAUSAL_COMPLEMENTARITY_AWARE_CANDIDATE_SCORE_STACKING  
TYPE: NEW_COMBINATION / ENSEMBLE / FEATURE_SEARCH  
WHY_NOW: It directly tests the highest-priority inference from the first pass: candidate quality is the bottleneck, and strategies may add value through different mistakes even when leadership gates and portfolio geometry fail.  
WHAT_NEW_INFORMATION: Whether strict-prior Strategy x Candidate-K ranks, residual reliability, and error-complementarity features can be combined into a better per-number score and one deterministic legal ticket than the best single strategy, static consensus, and a flat stack without complementarity.  
EXPECTED_INFORMATION_GAIN: HIGH  
DATA_READINESS: HIGH  
IMPLEMENTATION_COST: MEDIUM  
COMPUTE_COST: MEDIUM  
SEARCH_FRIENDLY: YES

### 2

TITLE: H08_PAIRWISE_LISTWISE_PER_NUMBER_RANKING  
TYPE: EXISTING_HYPOTHESIS / FEATURE_SEARCH  
WHY_NOW: H04/H07 improved Brier score slightly but had near-random discrimination and no legal-ticket projection. A ranking loss is better aligned with top-six candidate quality than another calibration-only model.  
WHAT_NEW_INFORMATION: Whether the apparent H04 limitation was mainly an objective mismatch rather than an absence of usable number-level information, measured by actual-number rank, top-six recall, and a fixed one-ticket M2+ endpoint.  
EXPECTED_INFORMATION_GAIN: HIGH  
DATA_READINESS: MEDIUM  
IMPLEMENTATION_COST: MEDIUM  
COMPUTE_COST: MEDIUM  
SEARCH_FRIENDLY: YES

### 3

TITLE: EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER  
TYPE: EXISTING_HYPOTHESIS / EXTERNAL_FRONTIER / FEATURE_DISCOVERY  
WHY_NOW: It is the clearest low-cost test of genuinely conditional sequence information after fixed-window contrasts and the tested state-space model failed to beat strong static controls.  
WHAT_NEW_INFORMATION: Whether variable-depth symbolic contexts improve prequential log loss beyond IID, trailing-frequency, and fixed-order Markov controls before any ticket-level action is attempted.  
EXPECTED_INFORMATION_GAIN: MEDIUM  
DATA_READINESS: HIGH  
IMPLEMENTATION_COST: LOW  
COMPUTE_COST: LOW  
SEARCH_FRIENDLY: YES

## 4. NEXT_RESEARCH_DIRECTION

NEXT_RESEARCH_DIRECTION: CAUSAL_COMPLEMENTARITY_AWARE_CANDIDATE_SCORE_STACKING

ORIGIN: NEW_SYNTHESIS_FROM_EXISTING_RESULTS

FRONTIER_RELATIONSHIP: H02 complementary-error graph + H25 out-of-fold stacking + Strategy x Candidate-K features, with H01/H04/H05/H06/H10 used only as scoped clues and comparators.

MECHANISM: At each target, use only prior data to measure which frozen direct-output strategies make decorrelated or sign-complementary errors. Combine their ordered Candidate-K indicators, prior residual quality, and complementarity-cluster features in a bounded out-of-fold stacker. The stacker emits one 49-number score vector; a deterministic top-six constructor emits exactly one legal ticket.

This is not a rescue or confirmation of H01, H02, H05, H06, or H25. H01 selected a leader or consensus state, H02's existing spec builds a complementarity graph/portfolio, H05 scored tickets inside a fixed pool, H06 changed portfolio geometry, and H25 is a flat residual stack. The selected direction tests a new causal path: `complementary strategy errors -> number-level candidate score -> one legal ticket -> held-out hit depth`.

## 5. WHY_THIS_IS_HIGHEST_VALUE_NOW

- It targets candidate generation before portfolio arrangement, matching the strongest cumulative inference from H06 and the weak candidate-level clues from H04, H05, and H10.
- It reuses ready historical strategy outputs, the sealed Strategy x Candidate-K authority, family labels, and residual histories. It does not require a new database, external data, neural runtime, or portfolio optimizer.
- It can distinguish four possibilities in one bounded experiment: no complementarity, descriptive complementarity only, complementarity captured by a simple flat stack, or genuinely incremental complementarity-aware candidate improvement.
- It is orthogonal to the exact H01 leadership gate and H06 geometry test while remaining cheaper and more directly actionable than high-dimensional tensor, neural, Hawkes, or copula alternatives.

CLASS_REVIEW:

- `CANDIDATE_QUALITY_IMPROVEMENT` and `STRATEGY_COMBINATION` are selected together.
- `DYNAMIC_WEIGHTING` is not selected as the main mechanism because H01, H07, H09, and H10 did not establish robust context-dependent improvement over their strongest comparators. Prior-only reliability may be a feature, but the terminal action is not a regime gate.
- `FEATURE_DISCOVERY` is included through complementarity and Candidate-K rank features; H08 and EH04 remain the next two directions.
- `CANDIDATE_K / PARAMETER_SEARCH` is included as a bounded feature-depth search over the existing K=1..6 authority, not promoted as a standalone fishing exercise.
- `EXTERNAL_FRONTIER`: EH04 is the best low-cost fallback. EH01, EH03, EH10, and EH27 primarily add state/anomaly gates before candidate quality is repaired. EH02 and EH09 are informative but costlier directed/tensor forms of dependence; EH06, EH25, and EH26 have higher implementation cost or stronger input/model assumptions. None currently has a better information-gain-to-cost ratio than the simple complementarity-aware stack.
- `CROSS_LOTTERY_REPLICATION` is lower priority now: B649 already has the direct inputs needed to test the selected mechanism, and no current evidence shows that T539 or P638 would yield higher information value for this question.

## 6. DISCOVERY_MODE

DISCOVERY_MODE: YES

Discovery is authorized only on `SEARCH_DATA`. All strategy subsets, feature sets, K-depth choices, lookback windows, model family, regularization, and deterministic tie rules must be chosen without reading the held-out outcomes. After selection, serialize one identifiable configuration and run it once on the held-out period.

## 7. WHAT_CAN_BE_SEARCHED

SEARCH_SPACE:

- Direct ordered-output strategies with common causal coverage, capped at 20 and selected inside search folds; portfolio identities with undefined number-order aggregation remain excluded.
- Candidate-K prefix indicators for K=1..6 from the sealed Strategy x Candidate-K authority.
- Strict-prior residual-reliability windows 50, 300, and 750; no arbitrary window sweep.
- Complementarity representations: paired residual covariance/correlation, residual-sign complementarity, and complementarity clusters.
- Strategy-subset policies: family-balanced representatives, complementarity-cluster representatives, and all eligible direct strategies up to the cap.
- Two bounded learned score families: regularized linear/nonnegative stacking and one shallow tree stacker. Static equal weighting is a baseline, not another searched model.
- Regularization and ensemble weights selected by nested chronological validation on search data.
- One deterministic score-to-top-six constructor and one ticket per target. Ticket count, legality rule, tie rule, and target universe are fixed across all arms.

NOT_SEARCHED: target-conditioned features, future data, arbitrary windows, unrestricted interactions, portfolio geometry, ticket multiplicity, outcome-selected held-out blocks, Cohort V2 results, or rescue tuning after held-out evaluation.

## 8. DATA_TO_USE

HISTORICAL_DATA:

- Sealed B649 canonical historical outcomes and raw historical authority through 2026-07-10.
- Sealed Strategy x Candidate-K ordered outputs and exact same-K random baselines where available.
- Strict-prior per-strategy residual histories and family labels from the completed historical authorities.
- The nine sealed Level-1 reports only as research clues and comparator definitions; their outcomes are not input features.

SEARCH_DATA: Causal target draws from `103000001` through the last eligible target before `113000006`, using nested expanding/blocked validation. For every target t, features and model state stop at t-1.

DATA_EXCLUDED:

- Cohort V2 future target results, prospective hits, interim scores, and checkpoint performance.
- Any target draw or future-overlapping row in its own features.
- Portfolio identities without a preregistered, outcome-blind number-order aggregation contract.

COHORT_V2_PROSPECTIVE_DATA_USED: NO

## 9. HELD_OUT_EVALUATION

HELD_OUT_PERIOD: Target draws `113000006` through `115000069`, 300 chronological targets in the sealed Strategy x Candidate-K authority.

The 300 targets are unavailable to configuration selection. After one configuration is locked, evaluate it once and partition the period into six consecutive 50-target blocks only for stability reporting. No held-out result may change the strategy set, feature set, K depths, model, weights, threshold, constructor, or baseline.

This is a retrospective configuration holdout, not prospective confirmation. It may justify the next experiment but does not establish future edge, betting readiness, or Cohort admission.

## 10. SUCCESS_METRIC

PRIMARY_SUCCESS_METRIC: Held-out one-ticket `M2+` rate for the complementarity-aware top-six ticket, at exactly one legal ticket per target.

PRIMARY_BASELINES:

1. Search-frozen strongest eligible single strategy.
2. Static family-balanced/equal-weight Candidate-K consensus.
3. Identical out-of-fold flat stack without complementarity features.
4. Exact same-ticket-count random baseline.

SUCCESS requires all of the following on the locked held-out period:

- Positive pooled M2+ delta versus baselines 1, 2, and 3.
- One-sided 95% moving-block lower bound above zero versus baselines 1, 2, and 3.
- Positive M2+ delta versus each of baselines 1, 2, and 3 in at least four of six chronological blocks.
- Exact equality of target universe, legal-ticket budget, and multiplicity across predictive arms.
- The gain is not explained only by M1+, coverage, or strategy count; report M1+, M3+, M4+, top-six recall, mean actual-number rank, and per-number Brier/log loss as secondary diagnostics.

An interesting graph, stable cluster, better training loss, or geometry improvement without held-out hit-depth improvement is not success.

## 11. STOP_OR_PIVOT_RULE

WHEN_TO_STOP_OR_PIVOT:

- Stop this direction after the single bounded search and locked held-out run if any primary success condition fails.
- Stop if complementarity features do not beat the identical flat stack; that means the new mechanism added no predictive information.
- Stop if improvement disappears under same-budget or exact-random normalization, is driven by one chronological block, or comes only from M1+/proper-score diagnostics without M2+ improvement.
- Stop if the selected subset, feature family, or weights are unstable across search folds, or if required compute exceeds `MEDIUM` without a pre-held-out signal.
- Do not rescue by expanding windows, models, interactions, ticket count, or held-out reuse.
- First pivot: H08 pairwise/listwise per-number ranking. Second pivot: EH04 CTW symbolic residual forecasting.

## 12. MINIMAL_B_HANDOFF

NEXT_B_TASK_ID: B649_TRACK_B_COMPLEMENTARITY_AWARE_CANDIDATE_STACK_DISCOVERY_R1

RESEARCH_QUESTION: Can strict-prior Strategy x Candidate-K ranks and cross-strategy error complementarity produce a one-ticket top-six candidate score with higher held-out M2+ success than the strongest single strategy, static consensus, and an otherwise identical flat stack?

DISCOVERY_MODE: YES

SEARCH_SPACE: Up to 20 direct ordered-output strategies; K=1..6 prefix features; 50/300/750 prior-residual windows; covariance, sign-complementarity, and cluster features; family-balanced/complementarity subsets; regularized linear/nonnegative stack and one shallow tree stack; one fixed deterministic top-six constructor.

HISTORICAL_DATA: Sealed B649 canonical outcomes, Strategy x Candidate-K authority, exact baselines, family labels, and strict-prior residual histories through 2026-07-10. No Cohort V2 prospective data.

SEARCH_PERIOD: `103000001` through the last eligible target before `113000006`, nested chronological search with cutoff t-1.

HELD_OUT_PERIOD: `113000006` through `115000069`, n=300, untouched until one configuration is locked; six 50-target reporting blocks.

BASELINES: Search-frozen best single strategy; static family-balanced/equal-weight consensus; identical flat out-of-fold stack without complementarity; exact one-ticket random.

SUCCESS_METRIC: One-ticket held-out M2+ improvement satisfying the pooled uncertainty, block-stability, and equal-budget rules in Section 10; M1+/M3+/M4+, top-six recall, actual-number rank, Brier, and log loss are secondary.

STOP_OR_PIVOT: One search and one held-out evaluation only. Stop on any primary-gate failure, feature instability, multiplicity/budget explanation, or failure to beat the flat stack; pivot to H08, then EH04.

EXPECTED_OUTPUT: One compact Track B experiment report; one serialized winning-or-null configuration; search-versus-held-out ledger; per-target predictions for all baselines; primary/secondary metrics; causal/leakage and equal-budget checks; final `ADVANCE` or `DO_NOT_ADVANCE`. No production model, Cohort change, repository mutation, database mutation, or prospective claim.

COHORT_V2_PROSPECTIVE_DATA_USED: NO  
REPO_MUTATION: NONE  
DB_MUTATION: NONE  
BLOCKERS: NONE  
NEXT: Send this compact selected research direction to Track B for implementation-first execution.

END
