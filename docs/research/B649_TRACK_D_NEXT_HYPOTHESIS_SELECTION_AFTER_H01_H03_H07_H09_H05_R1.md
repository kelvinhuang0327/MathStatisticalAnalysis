# B649 Track D Next Hypothesis Selection After H01/H03/H07/H09/H05 R1

TASK_ID: B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H01_H03_H07_H09_H05_R1

STATUS: PASS

MODE: READ_ONLY_RESEARCH_DECISION

TASK_CLASS: READ_ONLY_ANALYSIS

WORKER_ROUTE: STANDARD

JUDGE_MODE: NOT_APPLICABLE

OWNER_RESEARCH_POLICY: WIDE_IN_STRICT_OUT

RESEARCH_LINE: FUTURE_COHORT_V3_DISCOVERY

PROSPECTIVE_STATUS: NOT_FROZEN

OUTPUT_PATH: /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H01_H03_H07_H09_H05_R1.md

INTENT: the existing queue leaves H02/H27 structurally deferred and four selectable original Top-10 hypotheses after five exact closures; the task expects a three-candidate shortlist and exactly one successor maximizing research information gain; the opened Track D ranking and experiment spec put H06/H14 earlier by frozen priority but give H04/H07 higher novelty, orthogonality, and potential information gain and define a bounded causal probability Level-1 path.

## 1. Authority and integrity

[Confirmed] Historical source authority is pinned to commit `2db4da27aee716805c393eb9c7dd41aff8e9527e`, which resolves locally to tree `cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c`.

[Confirmed] The live shared worktree was observed without moving it: branch `codex/biglotto68-to-t539-p638-cross-lottery-closure-r1`, HEAD `bc84ccc812408ebbf30018221eecc1c6fcf3f028`, tree `5f19524858747463f9551294e16cd2c8e5c20ed1`, clean status. Live-head movement relative to the pinned historical authority is not a blocker.

[Confirmed] The required Track D authorities were opened directly. Their observed SHA-256 values are:

| Authority | SHA-256 |
|---|---|
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_RESEARCH_SURFACE_R1.md` | `26add8e34cb259cffdd54c6cd8f91373980ffe7c2277b17b2afaca8c936c8859` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_R1.md` | `6758482663fd46f14f86a293f0eef1a2bc77ff3186931267c5197f8cac87287b` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md` | `335c5921978fd167658dd14c3bdac539edfdf2b405609d9e275fcbe024e4959d` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_PRIORITY_RANKING_R1.csv` | `b0953cf2548e1fe9a941197d26a5bee9456b75adfa99361a1195acbcf663b869` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_HYPOTHESIS_DATA_SUFFICIENCY_MATRIX_R1.csv` | `9200b55d61b6fde69fa173c97bac419e8f9c10813fd415aef03f76662b1874ab` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_COHORT_V2_FORWARD_READINESS_R1.md` | `58f142f7f04fe57be015416751bf80cafbb3f4fba21ce34d989792bc7842e2d3` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_28_HYPOTHESIS_FORWARD_MATRIX_R1.csv` | `97493cb6230c6630a24ec4e962789e171743bb9b4f71685212ad78780513d784` |

[Confirmed] The discovery-priority authority contains exactly ten unique original Top-10 display IDs. The canonical alias map is one-to-one:

| Display | Canonical | Canonical title | Discovery priority |
|---|---|---|---:|
| H01 | H01 | CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR | 1 |
| H03 | H04 | MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT | 2 |
| H07 | H19 | CHANGE_POINT_TRIGGERED_ALLOCATION | 3 |
| H02 | H27 | HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION | 4 |
| H09 | H21 | CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION | 5 |
| H05 | H10 | DIRECT_TICKET_LEVEL_RESIDUAL_SCORING | 6 |
| H06 | H14 | DPP_SUBMODULAR_PORTFOLIO_SELECTION | 7 |
| H04 | H07 | CALIBRATED_PER_NUMBER_PROBABILITIES | 8 |
| H08 | H12 | TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS | 9 |
| H10 | H17 | DYNAMIC_BAYESIAN_STATE_SPACE_MODELING | 10 |

EXTERNAL_RESEARCH_SEARCH: NOT RUN

COLLISION_AUDIT_REBUILD: NOT RUN

RESEARCH_FRONTIER_REBUILD: NOT RUN

CAPABILITY_AUDIT_REBUILD: NOT RUN

EXPERIMENT_EXECUTION: NOT RUN

## 2. Sealed result verification

[Confirmed] Minimal sealed-root review found no material contradiction. The listed `MANIFEST.json`, `report.md`, and `validation.json` hashes match each root's `SHA256SUMS`; no experiment reproducer was run.

| Display / canonical | Sealed result root | Binding result | Queue classification |
|---|---|---|---|
| H01 / H01 | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_H01_CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR_R1` | `WEAK_SIGNAL`; advancement gate `FAIL`; Level 2 `NO`; forward feasibility `NOT_ADVANCED` | EXECUTED_NOT_ADVANCED |
| H03 / H04 | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H03_MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT_DRAFT_R1` | `NO_SIGNAL`; Level 1 `FAIL`; final advancement `false`; Level 2 `NO` | EXECUTED_NOT_ADVANCED |
| H07 / H19 | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H07_CHANGE_POINT_TRIGGERED_ALLOCATION_LEVEL1_R1` | `WEAK_SIGNAL`; Level 1 `FAIL`; `ADVANCE: NO`; Level 2 `NO` | EXECUTED_NOT_ADVANCED |
| H09 / H21 | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H09_CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION_LEVEL1_R1` | `WEAK_SIGNAL`; stability and uncertainty `FAIL`; `DO_NOT_ADVANCE`; Level 2 `NO` | EXECUTED_NOT_ADVANCED |
| H05 / H10 | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H05_DIRECT_TICKET_LEVEL_RESIDUAL_SCORING_LEVEL1_R1` | `WEAK_SIGNAL`; 4/5 positive folds but both one-sided 95% lower bounds below zero; `DO_NOT_ADVANCE`; zero Level-2, 1024-pool, 4096-pool, or rescue runs | EXECUTED_NOT_ADVANCED |

STOP_B_RESULT_CONTRADICTION: NOT TRIGGERED

H05 point-estimate positivity does not override its preregistered uncertainty gate. H05 is closed only for the exact frozen direct-ticket interaction residual basis, 256-ticket pool, folds, budget, endpoints, comparators, and confidence rule.

## 3. Execution ledger and pool arithmetic

EXECUTION_LEDGER:

- H01/H01: EXECUTED_NOT_ADVANCED
- H03/H04: EXECUTED_NOT_ADVANCED
- H07/H19: EXECUTED_NOT_ADVANCED
- H09/H21: EXECUTED_NOT_ADVANCED
- H05/H10: EXECUTED_NOT_ADVANCED

ORIGINAL_TOP10_COUNT: 10

EXECUTED_NOT_ADVANCED_COUNT: 5

UNEXECUTED_TOP10_COUNT: 5

STRUCTURALLY_DEFERRED_TOP10_COUNT: 1

SELECTABLE_TOP10_COUNT: 4

### H02/H27 structural-defer check

DISPLAY_ID: H02

CANONICAL_ID: H27

CANONICAL_TITLE: HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION

DEFER_REASON: The fixed producer has already been evaluated on 1,957 historical targets. Those targets can support reproduction or stress analysis only; they cannot independently confirm themselves. The allowed authority recognizes no genuinely untouched/reserved confirmation block and no legitimate post-freeze observation.

MINIMAL_CURRENT_EVIDENCE_CHECK: The forward matrix still states that engineering cannot create the required untouched confirmation sample. No Cohort V2 interim result, unfinished Track A data, current live observation, post-selection evidence, or unsealed Track B result was used to cure this gap.

STATUS: STRUCTURALLY_DEFERRED, NOT NEGATIVE

## 4. Every unexecuted original Top-10 candidate

### H02 / canonical H27 — HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION

ORIGINAL_TRACK_D_PRIORITY: DISCOVERY_PRIORITY 4; original Top-10 section ordinal 2

NOVELTY: 4/5; HIGH in the original narrative scale

ORTHOGONALITY: 5/5; HIGH

POTENTIAL_INFORMATION_GAIN: 5/5

COLLISION_STATUS: OPEN; exact 0, strong 9, weak 7, same-family/different-hypothesis 17

HISTORICAL_TESTABILITY: 3/5; reproduction/stress is possible, independent confirmation is not currently possible

DATA_SUFFICIENCY: Historical inputs and fixed producer parameters exist; untouched confirmatory outcomes do not

HISTORICAL_TEST_COST: LOW for reproduction/stress; elapsed-time high for genuine confirmation

FORWARD_READINESS: READY_WITH_SMALL_ENGINEERING; 3/5

FORWARD_ENABLEMENT_COST: 2/5; scope S

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: DRAFT_EXISTS; CONFIRMATION_BLOCKED_BY_UNTOUCHED_EVIDENCE

NEW_MODEL_OUTPUT_REQUIRED: NO new predictive model; typed reproduction output and adapter would be needed

RUNTIME_CAPABILITY_REQUIRED: Bit-for-bit producer reproduction, deterministic two-ticket adapter, frozen observer, causal cutoff, and typed score contract

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW — both use multiple horizons, but H02 requires joint horizon robustness rather than derivative/disagreement increments

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: YES — no untouched confirmation sample

PREPARATION_REQUIRED: Reproduce the fixed producer bit-for-bit, freeze one confirmation endpoint and observer, then wait for separately authorized untouched evidence

### H06 / canonical H14 — DPP_SUBMODULAR_PORTFOLIO_SELECTION

ORIGINAL_TRACK_D_PRIORITY: DISCOVERY_PRIORITY 7; original Top-10 section ordinal 6

NOVELTY: 4/5; MEDIUM_HIGH

ORTHOGONALITY: 3/5; MEDIUM

POTENTIAL_INFORMATION_GAIN: 4/5

COLLISION_STATUS: OPEN; exact 0, strong 12, weak 8, same-family/different-hypothesis 10

HISTORICAL_TESTABILITY: 5/5; READY_FOR_HISTORICAL_EXPERIMENT

DATA_SUFFICIENCY: A bounded causal ticket pool and overlap geometry are available or derivable; upstream predictive utility is conditional and must retain its true semantics

HISTORICAL_TEST_COST: MEDIUM

FORWARD_READINESS: READY_WITH_SMALL_ENGINEERING; 4/5

FORWARD_ENABLEMENT_COST: 2/5; scope S

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: DRAFT_ONLY; NEEDS_BOUNDED_PREPARATION

NEW_MODEL_OUTPUT_REQUIRED: NO for a geometry-only claim; a typed upstream candidate score is required for any predictive-edge claim

RUNTIME_CAPABILITY_REQUIRED: Frozen same-pool contract, DPP kernel or equivalent, deterministic DPP-MAP/submodular operator, portfolio geometry, and exact matched comparators

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: NONE — operating on already-produced tickets does not reuse H05's failed typed direct-ticket interaction residual mechanism

PREDICTIVE_DISCOVERY_VALUE: LOW_TO_MEDIUM_AND_CONDITIONAL; predictive readiness 2/5 and inherited from the upstream producer or typed utility

PORTFOLIO_RESEARCH_VALUE: HIGH; portfolio-operator readiness 4/5

STRUCTURAL_BLOCKER: NONE

PREPARATION_REQUIRED: Freeze identical candidate-pool hash, utility semantics, ticket count, number pool, budget, cutoff, seed, one DPP-MAP kernel, one submodular objective, and greedy/orthogonal/conditional-random comparators

### H04 / canonical H07 — CALIBRATED_PER_NUMBER_PROBABILITIES

ORIGINAL_TRACK_D_PRIORITY: DISCOVERY_PRIORITY 8; original Top-10 section ordinal 4

NOVELTY: 5/5; HIGH

ORTHOGONALITY: 5/5; HIGH

POTENTIAL_INFORMATION_GAIN: 5/5

COLLISION_STATUS: OPEN; exact 0, strong 1, weak 8, same-family/different-hypothesis 10

HISTORICAL_TESTABILITY: 4/5; PARTIAL_HISTORICAL_INPUT_PATH

DATA_SUFFICIENCY: Causal history and binary 49-number outcomes exist; calibrated typed probabilities are absent from all 133 historical ticket records and cannot be recovered from rank, frequency score, hotness, PageRank, vote count, or arbitrary normalized score

HISTORICAL_TEST_COST: MEDIUM_TO_HIGH

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

FORWARD_ENABLEMENT_COST: 4/5; scope XL

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: DRAFT_ONLY; NEEDS_BOUNDED_PREPARATION

NEW_MODEL_OUTPUT_REQUIRED: YES — typed dense causal 49-vector `P(number appears)` with model/calibration provenance

RUNTIME_CAPABILITY_REQUIRED: Causal feature producer, deterministic blocked/OOF training replay, temporal calibration partitions, proper scoring, reliability output, legal ticket constructor, and versioned adapter

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW — H03 rejected the incremental frozen slope/acceleration/disagreement basis, not probability production or out-of-sample calibration

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: NONE — the missing typed output is bounded engineering/data preparation, not scientific disqualification

PREPARATION_REQUIRED: Freeze one simple causal probability producer and empirical-frequency comparator, draw-block training/calibration/evaluation splits, Brier primary metric, log-loss/reliability assessment, valid probability semantics, and optional legal ticket secondary endpoint

### H08 / canonical H12 — TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS

ORIGINAL_TRACK_D_PRIORITY: DISCOVERY_PRIORITY 9; original Top-10 section ordinal 8

NOVELTY: 5/5; HIGH

ORTHOGONALITY: 5/5; HIGH

POTENTIAL_INFORMATION_GAIN: 5/5

COLLISION_STATUS: OPEN; exact 0, strong 11, weak 7, same-family/different-hypothesis 0

HISTORICAL_TESTABILITY: 4/5; READY_FOR_HISTORICAL_EXPERIMENT

DATA_SUFFICIENCY: Strict-prior chronological draw and pair/triple history support offline construction; no temporal-hypergraph feature/scoring pipeline exists

HISTORICAL_TEST_COST: MEDIUM for one tiny preregistered motif set; HIGH for broad motif/community search

FORWARD_READINESS: REQUIRES_NEW_RUNTIME_ARCHITECTURE; 1/5

FORWARD_ENABLEMENT_COST: 5/5; scope XL

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: DRAFT_ONLY; NEEDS_BOUNDED_PREPARATION

NEW_MODEL_OUTPUT_REQUIRED: YES — typed temporal motif residual/number-or-ticket score

RUNTIME_CAPABILITY_REQUIRED: Frozen motif vocabulary/decay, causal rolling hypergraph state, residual scorer, marginal/pair/static-graph baselines, deterministic replay, and adapter

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW — temporal evolution is shared only broadly; the failed window-derivative mechanism is not reused

H07_FAILURE_RELEVANCE: LOW — no frozen JSD detector, threshold, or allocation response is reused

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: MEDIUM — both examine higher-order residual structure, but H08 tests time-decayed motif evolution beyond marginal/static graph baselines, not H05's frozen direct-ticket pair/triple score on the 256-ticket pool

STRUCTURAL_BLOCKER: NONE

PREPARATION_REQUIRED: Predeclare a tiny motif vocabulary and one decay, freeze strict-prior graph updates and marginal/pair/static comparators, and forbid outer-test motif mining

### H10 / canonical H17 — DYNAMIC_BAYESIAN_STATE_SPACE_MODELING

ORIGINAL_TRACK_D_PRIORITY: DISCOVERY_PRIORITY 10; original Top-10 section ordinal 10

NOVELTY: 5/5; HIGH

ORTHOGONALITY: 5/5; HIGH

POTENTIAL_INFORMATION_GAIN: 5/5

COLLISION_STATUS: OPEN; exact 0, strong 7, weak 8, same-family/different-hypothesis 25

HISTORICAL_TESTABILITY: 4/5; READY_FOR_HISTORICAL_EXPERIMENT

DATA_SUFFICIENCY: Causal counts, chronology, and outcomes support a bounded model; no typed filtered posterior, posterior-predictive probability vector, uncertainty output, replay, or adapter exists

HISTORICAL_TEST_COST: MEDIUM_TO_HIGH

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

FORWARD_ENABLEMENT_COST: 4/5; scope L

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: DRAFT_ONLY; NEEDS_BOUNDED_PREPARATION

NEW_MODEL_OUTPUT_REQUIRED: YES — filtered latent posterior, posterior-predictive 49-vector, uncertainty, diagnostics, and versioned state

RUNTIME_CAPABILITY_REQUIRED: Frozen parsimonious state model, deterministic causal filtering and replay, convergence gates, proper-score comparators, state persistence, legal constructor, and adapter

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW — both are temporal, but H10 tests filtered latent-state dynamics rather than fixed window derivatives

H07_FAILURE_RELEVANCE: LOW — H10 does not reuse the failed change detector, threshold, or allocation response

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: NONE

PREPARATION_REQUIRED: Freeze state dimension, priors, initialization, transitions/emissions, inference, filtered-not-smoothed semantics, blocked replay, proper scoring, and convergence criteria

## 5. NEXT_CANDIDATE_SHORTLIST = 3

NEXT_CANDIDATE_SHORTLIST: 3

### 1

RANK: 1

DISPLAY_ID: H04

CANONICAL_ID: H07

CANONICAL_TITLE: CALIBRATED_PER_NUMBER_PROBABILITIES

ORIGINAL_PRIORITY: DISCOVERY_PRIORITY 8; original Top-10 section ordinal 4

WHY_STILL_OPEN: No historical authority exposes calibrated out-of-sample 49-number probabilities; tickets, ranks, and arbitrary scores are not probability outputs.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: NONE

NOVELTY: 5/5

ORTHOGONALITY: 5/5

POTENTIAL_INFORMATION_GAIN: 5/5

DATA_READINESS: PARTIAL_HISTORICAL_INPUT_PATH; causal history/outcomes exist, typed probability outputs do not

HISTORICAL_TEST_COST: MEDIUM_TO_HIGH

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: NEEDS_BOUNDED_PREPARATION

PREPARATION_REQUIRED: Typed causal 49-vector producer; fixed model/features; draw-block train/calibration/evaluation replay; Brier/log-loss/reliability contract; legal constructor only for a secondary ticket endpoint

STRUCTURAL_BLOCKER: NONE

WHY_NOW: It is the highest remaining candidate with 5/5 novelty, orthogonality, and information gain that directly tests new predictive information rather than portfolio geometry. Its moderate preparation cost is not a scientific blocker.

WHY_NOT_NOW: It cannot start until the typed probability semantics, causal partitions, model identity, primary proper score, and reliability assessment are frozen under separate Track B authorization.

### 2

RANK: 2

DISPLAY_ID: H06

CANONICAL_ID: H14

CANONICAL_TITLE: DPP_SUBMODULAR_PORTFOLIO_SELECTION

ORIGINAL_PRIORITY: DISCOVERY_PRIORITY 7; original Top-10 section ordinal 6

WHY_STILL_OPEN: Existing covering/diversification methods do not test the exact DPP-MAP or frozen submodular objective under identical pool, budget, ticket count, number pool, and cutoff.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: NONE

NOVELTY: 4/5

ORTHOGONALITY: 3/5

POTENTIAL_INFORMATION_GAIN: 4/5

DATA_READINESS: READY_FOR_HISTORICAL_EXPERIMENT; candidate pool and geometry are available or derivable

HISTORICAL_TEST_COST: MEDIUM

FORWARD_READINESS: READY_WITH_SMALL_ENGINEERING; 4/5

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: NEEDS_BOUNDED_PREPARATION

PREPARATION_REQUIRED: Freeze identical candidate pool, utility semantics, ticket count, number pool, budget, cutoff, seed, kernel/objective, and matched optimizers

STRUCTURAL_BLOCKER: NONE

WHY_NOW: It is the earliest remaining selectable hypothesis in the frozen ranking and can cleanly test fixed-budget portfolio efficiency.

WHY_NOT_NOW: Its predictive discovery value is conditional on the upstream score. A positive geometry result may reduce overlap or improve coverage without demonstrating any new ability to predict the draw.

### 3

RANK: 3

DISPLAY_ID: H08

CANONICAL_ID: H12

CANONICAL_TITLE: TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS

ORIGINAL_PRIORITY: DISCOVERY_PRIORITY 9; original Top-10 section ordinal 8

WHY_STILL_OPEN: Static graph, co-occurrence, Apriori, and H05's frozen direct ticket residual do not test preregistered time-decayed higher-order motif evolution after marginal/static residualization.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW

H07_FAILURE_RELEVANCE: LOW

H09_FAILURE_RELEVANCE: NONE

H05_FAILURE_RELEVANCE: MEDIUM

NOVELTY: 5/5

ORTHOGONALITY: 5/5

POTENTIAL_INFORMATION_GAIN: 5/5

DATA_READINESS: READY_FOR_OFFLINE_HISTORICAL_CONSTRUCTION

HISTORICAL_TEST_COST: MEDIUM for the bounded Level 1; high for broad motif search

FORWARD_READINESS: REQUIRES_NEW_RUNTIME_ARCHITECTURE; 1/5

EXPERIMENT_SPEC_AVAILABLE: YES

SPEC_STATUS: NEEDS_BOUNDED_PREPARATION

PREPARATION_REQUIRED: Freeze a tiny motif vocabulary, one decay, causal rolling update, residual definition, and marginal/pair/static comparators

STRUCTURAL_BLOCKER: NONE

WHY_NOW: It has maximum novelty, orthogonality, and information-gain scores and would test a genuinely higher-order temporal mechanism.

WHY_NOT_NOW: It is lower in the frozen ranking, has medium relevance to H05's broader residual-interaction family, and requires heavier architecture and multiplicity control than H04.

H10/H17 remains open but is outside the three-item shortlist because it is last in the frozen priority and requires a more parameter-rich model/replay contract than H04. H02/H27 remains structurally deferred, not negative.

## 6. Selected single successor

NEXT_B_HYPOTHESIS: H04 / canonical H07 — CALIBRATED_PER_NUMBER_PROBABILITIES

RESEARCH_LINE: FUTURE_COHORT_V3_DISCOVERY

SELECTION_REASON: H04 is the strongest remaining predictive-discovery experiment. It has 5/5 novelty, orthogonality, and potential information gain; is meaningfully orthogonal to the five exact failed mechanisms; can be historically falsified with causal blocked probability outputs and proper scoring; and has a bounded existing spec path. Selecting it over the earlier H06 is the Packet-required distinction between research information gain and easiest engineering: H06's primary value is portfolio efficiency, while H04 tests whether the system can produce valid, informative out-of-sample probabilities at all.

WHY_SELECTED_OVER_SHORTLIST_2: H06/H14 is earlier and cheaper, but its predictive value is inherited from an upstream producer. It may improve diversity, overlap, or coverage without discovering predictive information. H04 directly tests a new predictive representation and calibration claim.

WHY_SELECTED_OVER_SHORTLIST_3: H08/H12 has comparable novelty and information-gain scores, but it is lower in the frozen ranking, has MEDIUM H05 relevance at the broad residual-interaction level, and needs a new rolling-hypergraph architecture with tighter multiplicity control. H04 provides a cleaner bounded falsification first.

WHY_NOT_SHORTLIST_2: H06 remains open and should follow as a portfolio-efficiency question, but it is not the next predictive-discovery hypothesis.

WHY_NOT_SHORTLIST_3: H08 remains open and high-value, but its heavier temporal-feature architecture and residual-family proximity make it a later test than the simpler typed probability question.

WHAT_NEW_INFORMATION_IT_TESTS: Whether a causal model can emit valid dense probabilities for all 49 numbers that improve held-out proper scoring and reliability over a causal empirical-frequency baseline, without treating arbitrary ranks or scores as probabilities.

WHAT_PRIOR_H01_H03_H07_H09_H05_DID_NOT_TEST: H01 tested cross-strategy residual/leadership meta-selection; H03 tested the incremental frozen multi-window derivative/disagreement basis; H07 tested one JSD change-alarm and allocation response; H09 tested one conditional negative suppression contract; H05 tested one fixed direct ticket pair/triple residual basis on a 256-ticket pool. None tested a typed causal 49-number probability vector with out-of-sample proper scoring and calibration assessment.

WHAT_NEGATIVE_RESULT_WOULD_RULE_OUT: Incremental held-out value of the one preregistered simple causal probability producer and calibration contract over the empirical-frequency probability baseline under the frozen training/calibration/evaluation blocks and primary proper score. It would not close every probability model, Bayesian state-space model, feature family, or ticket constructor.

WHAT_POSITIVE_RESULT_WOULD_JUSTIFY: A request for separately authorized Level 2 with nested blocked calibration, a bounded calibrator/model comparison, draw-level uncertainty, reliability/sharpness analysis, and a frozen legal ticket secondary endpoint. It would not authorize Level 2 automatically, create Cohort V3, modify Cohort V2, establish prospective edge, or permit betting/production use.

DISCOVERY_VALUE: HIGH

DATA_READINESS: PARTIAL_HISTORICAL_INPUT_PATH; BOUNDED_PREPARATION_REQUIRED

HISTORICAL_TEST_COST: MEDIUM_TO_HIGH

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

EXPECTED_RESEARCH_DEPTH: LEVEL_1_FAST_FALSIFICATION_ONLY

## 7. Track B spec boundary

TRACK_B_EXISTING_SPEC_LOCATOR: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, section `H04 — CALIBRATED_PER_NUMBER_PROBABILITIES`, draft task ID `B649_TRACK_B_H04_CALIBRATED_PER_NUMBER_PROBABILITIES_DRAFT_R1`

TRACK_B_SPEC_STATUS: NEEDS_BOUNDED_PREPARATION

REQUIRED_PREPARATION_OR_ADAPTATION:

1. Define and freeze a typed dense 49-number probability output whose values are valid `P(number appears)` predictions with model version, feature cutoff, training block, calibration block, evaluation block, and determinism/seed provenance. Do not normalize arbitrary scores or ranks into probabilities.
2. Freeze one simple causal model and the causal empirical-frequency probability baseline. All features and training end before the evaluation target; row-random splitting across numbers or draws is forbidden.
3. Freeze draw-block training/calibration/evaluation replay. Level 1 uses the single preregistered producer and reports uncalibrated and, only if preregistered, calibration-split output; broader Platt/beta/isotonic comparison remains Level 2.
4. Freeze primary draw-block Brier score, with log loss and reliability/ECE as secondary diagnostics; define invalid-probability, denominator, calibration, and leakage failure gates.
5. If a ticket endpoint is retained as secondary, freeze one legality-preserving constructor, ticket budget, cutoff, and exact same-count comparator. Proper scoring remains the Level-1 predictive-information criterion.
6. Bind the five sealed results as `EXECUTED_NOT_ADVANCED`; do not reuse their outer-test outcomes to select features, model family, calibration method, or thresholds.

No preparation or experiment was executed by this decision task.

REQUIRED_FUTURE_PATH: Track D selection -> separately authorized Track B Level 1 -> if `ADVANCE`, separately authorized Level 2 -> if later evidence supports it, separately authorized candidate freeze -> future Cohort V3.

## 8. Final boundaries and lifecycle

TOP10_POOL_EXHAUSTED_OR_BLOCKED: NO

EXTERNAL_FRONTIER_FALLBACK_USED: NO

COHORT_V2_RELATIONSHIP: NONE

H05_REMEDIATION: NOT_REQUIRED

H05_LEVEL2: NOT_AUTHORIZED

1024_POOL: NOT_AUTHORIZED

4096_POOL: NOT_AUTHORIZED

TRACK_A_INTERFERENCE: NONE

TRACK_B_RESULT_MUTATION: NONE

TRACK_C_INTERFERENCE: NONE

REPO_MUTATION: NONE

DB_MUTATION: NONE

SEALED_TASK_DATA_MUTATION: NONE

COHORT_V2_MUTATION: NONE

COHORT_V3_CREATION: NONE

LEVEL_1_RUN: NO

LEVEL_2_RUN: NO

BLOCKERS: NONE for this queue decision. H02/H27 remains separately structurally deferred by the untouched-confirmation-sample requirement.

IMPLEMENTATION_LIFECYCLE_STATUS: COMPLETE

PR_PUBLICATION_STATUS: NOT_APPLICABLE

POSTMERGE_LIFECYCLE_STATUS: NOT_APPLICABLE

BRANCH_CLEANUP_STATUS: NOT_APPLICABLE

FULL_PR_LIFECYCLE_CLOSED: NO

NEXT: Send exactly H04 / canonical H07 `CALIBRATED_PER_NUMBER_PROBABILITIES` to Track B for separately authorized Level-1 historical fast falsification.

Do not start multiple hypotheses from this decision.

END
