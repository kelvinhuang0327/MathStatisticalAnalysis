# B649 Track D Next Hypothesis Selection After H01/H03/H07/H09 R1

TASK_ID: B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H01_H03_H07_H09_R1

STATUS: PASS

MODE: READ_ONLY_RESEARCH_DECISION

WORKER_ROUTE: STANDARD

JUDGE_MODE: NOT_APPLICABLE

OWNER_RESEARCH_POLICY: WIDE_IN_STRICT_OUT

RESEARCH_LINE: FUTURE_COHORT_V3_DISCOVERY

PROSPECTIVE_STATUS: NOT_FROZEN

OUTPUT_PATH: /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H01_H03_H07_H09_R1.md

INTENT: the existing queue leaves six unexecuted Top-10 hypotheses, with H02/H27 evidence-gated; the task expects exactly one selectable successor plus a three-item shortlist; the opened Track D ranking and experiment spec place H05/H10 first among currently selectable candidates and define its bounded 256-candidate Level-1 test.

## 1. Authority and integrity

[Confirmed] Historical repository authority remains pinned to commit `2db4da27aee716805c393eb9c7dd41aff8e9527e`, which resolves locally to tree `cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c`.

[Confirmed] The Track D authority files were opened directly and rehashed:

| Authority | SHA-256 |
|---|---|
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_RESEARCH_SURFACE_R1.md` | `26add8e34cb259cffdd54c6cd8f91373980ffe7c2277b17b2afaca8c936c8859` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_R1.md` | `6758482663fd46f14f86a293f0eef1a2bc77ff3186931267c5197f8cac87287b` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md` | `335c5921978fd167658dd14c3bdac539edfdf2b405609d9e275fcbe024e4959d` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_PRIORITY_RANKING_R1.csv` | `b0953cf2548e1fe9a941197d26a5bee9456b75adfa99361a1195acbcf663b869` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_HYPOTHESIS_DATA_SUFFICIENCY_MATRIX_R1.csv` | `9200b55d61b6fde69fa173c97bac419e8f9c10813fd415aef03f76662b1874ab` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_COHORT_V2_FORWARD_READINESS_R1.md` | `58f142f7f04fe57be015416751bf80cafbb3f4fba21ce34d989792bc7842e2d3` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_28_HYPOTHESIS_FORWARD_MATRIX_R1.csv` | `97493cb6230c6630a24ec4e962789e171743bb9b4f71685212ad78780513d784` |
| `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2_NORMALIZED_R1.csv` | `6381f574410b93efc02c96f70aa017f40db53328c4b532b78efd9bb1fb2c2dcb` |

[Confirmed] The five original load-bearing Track D hashes match those sealed into the H01/H03/H07 result manifests. The normalized frontier contains 49 rows: 28 internal and 21 external-derived rows. It was used only to confirm the fallback boundary; no external/frontier hypothesis entered selection.

[Confirmed] The shared repository was clean at the first observation (`bc84ccc812408ebbf30018221eecc1c6fcf3f028`, tree `5f19524858747463f9551294e16cd2c8e5c20ed1`) and later moved cleanly through foreign concurrent work to `930bface2915eb5e6f6a1910448f822eb295c828`, tree `8e78e017284acfc6be3ad751a04904a61469129d`. This task did not move the worktree or modify the repository. The repo-external Track D authorities remained hash-stable.

EXTERNAL_RESEARCH_SEARCH: NOT RUN

COLLISION_AUDIT_REBUILD: NOT RUN

CAPABILITY_AUDIT_REBUILD: NOT RUN

EXPERIMENT_EXECUTION: NOT RUN

## 2. Sealed Track B result verification

[Confirmed] `shasum -a 256 -c SHA256SUMS` passed for every listed payload in each of the four sealed task roots. No experiment reproducer was run.

| Display / canonical | Title | Sealed task root | Binding result | Queue status |
|---|---|---|---|---|
| H01 / H01 | CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_H01_CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR_R1` | `WEAK_SIGNAL`; advancement gate `FAIL`; final advancement false; `LEVEL_2_RUN=NO` | EXECUTED_NOT_ADVANCED |
| H03 / H04 | MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H03_MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT_DRAFT_R1` | `NO_SIGNAL`; Level 1 `FAIL`; advancement gate `FAIL`; final advancement false; `LEVEL_2_RUN=NO` | EXECUTED_NOT_ADVANCED |
| H07 / H19 | CHANGE_POINT_TRIGGERED_ALLOCATION | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H07_CHANGE_POINT_TRIGGERED_ALLOCATION_LEVEL1_R1` | `WEAK_SIGNAL`; Level 1 `FAIL`; stability/uncertainty gate failed; `ADVANCE=NO`; `LEVEL_2_RUN=NO` | EXECUTED_NOT_ADVANCED |
| H09 / H21 | CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION | `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H09_CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION_LEVEL1_R1` | `WEAK_SIGNAL`; `LEVEL_1_DECISION=DO_NOT_ADVANCE`; stability `FAIL`; `LEVEL_2_RUN=NO` | EXECUTED_NOT_ADVANCED |

STOP_B_RESULT_CONTRADICTION: NOT TRIGGERED

Only these four exact tested mechanisms are closed. Their results are not generalized to ticket-level, portfolio, probability, calibration, graph/hypergraph, Bayesian, uncertainty, special-number, neural-representation, or other method families.

## 3. Canonical execution ledger and pool arithmetic

EXECUTION_LEDGER:

- H01 / canonical H01 — CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR: EXECUTED_NOT_ADVANCED
- H03 / canonical H04 — MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT: EXECUTED_NOT_ADVANCED
- H07 / canonical H19 — CHANGE_POINT_TRIGGERED_ALLOCATION: EXECUTED_NOT_ADVANCED
- H09 / canonical H21 — CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION: EXECUTED_NOT_ADVANCED

ORIGINAL_TOP10_COUNT: 10

EXECUTED_NOT_ADVANCED_COUNT: 4

UNEXECUTED_TOP10_COUNT: 6

UNEXECUTED_TOP10_BEFORE_BLOCKER_FILTER: 6

STRUCTURALLY_DEFERRED_TOP10_COUNT: 1

SELECTABLE_TOP10_COUNT: 5

[Confirmed] The six unexecuted hypotheses, retaining original frozen order, are H02/H27, H05/H10, H06/H14, H04/H07, H08/H12, and H10/H17.

### H02 confirmation-evidence check

DISPLAY_ID: H02

CANONICAL_ID: H27

CANONICAL_TITLE: HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION / Preregistered confirmation of horizon-minimax disagreement

STATUS: STRUCTURALLY_DEFERRED

[Confirmed] The allowed authorities state that the sealed 1,957-target population can support only bit-for-bit reproduction and historical stress. No untouched/reserved confirmation block or legitimate post-freeze observation exists. Cohort V2 interim outcomes, active observations, post-selection data, and unfinished Track A/B/C artifacts were not used. Engineering readiness cannot manufacture independent evidence.

H02 is deferred, not negative, and remains outside the current selectable pool.

## 4. Required fields for every selectable candidate

Scores and ordering below are reused from the pre-existing Track D ranking. Forward readiness is supporting feasibility evidence and did not replace discovery priority. `5/5` is best except forward-enablement cost, where `5/5` is hardest.

### Candidate A — H05 / canonical H10

DISPLAY_ID: H05

CANONICAL_ID: H10

CANONICAL_TITLE: DIRECT_TICKET_LEVEL_RESIDUAL_SCORING / Direct ticket-level scorer with pair/triple residual terms

ORIGINAL_TRACK_D_PRIORITY: 6

ORIGINAL_DISCOVERY_SCORE: 4.2200

NOVELTY: 5/5

ORTHOGONALITY: 5/5

COLLISION_STATUS: OPEN_NO_EXACT_HISTORICAL_MATCH; PRIOR_CONTACT=FAMILY_TESTED_NEW_HYPOTHESIS_OPEN; exact matches 0, strong component overlaps 11

HISTORICAL_TESTABILITY: 5/5; READY_FOR_HISTORICAL_EXPERIMENT

DATA_SUFFICIENCY: Sealed ticket/combination histories, legal tickets, hit outcomes, chronology, pair/triple features, exact baselines, and a bounded candidate pool are authoritative or derivable. Existing A/C orderings are proxies and cannot be relabeled as typed ticket scores.

HISTORICAL_TEST_COST: MEDIUM for the frozen 256-candidate Level 1; HIGH only if candidate sizes or interactions proliferate

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

FORWARD_ENABLEMENT_COST: 4/5; scope L

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY — `B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, section `H05 — DIRECT_TICKET_LEVEL_RESIDUAL_SCORING`

REQUIRED_NEW_MODEL_OUTPUT: Deterministic typed ticket-level residual score over one frozen causal candidate pool

REQUIRED_RUNTIME_CAPABILITY: Frozen bounded causal ticket generator/pool; sparse pair/triple feature replay; deterministic typed score contract; identical-pool additive and matched-random comparators; fixed top-k constructor; causal cutoff; deterministic out-of-fold replay

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: NONE

PREPARATION_REQUIRED: MODERATE

### Candidate B — H06 / canonical H14

DISPLAY_ID: H06

CANONICAL_ID: H14

CANONICAL_TITLE: DPP_SUBMODULAR_PORTFOLIO_SELECTION / DPP/submodular portfolio selection under a calibrated score

ORIGINAL_TRACK_D_PRIORITY: 7

ORIGINAL_DISCOVERY_SCORE: 4.1600

NOVELTY: 4/5

ORTHOGONALITY: 3/5

COLLISION_STATUS: OPEN_NO_EXACT_HISTORICAL_MATCH; PRIOR_CONTACT=NOT_TESTED; exact matches 0, strong component overlaps 12

HISTORICAL_TESTABILITY: 5/5; READY_FOR_HISTORICAL_EXPERIMENT

DATA_SUFFICIENCY: A causal candidate pool and overlap geometry are available or derivable. Proxy utility may support a geometry-only discovery claim if labeled; predictive-quality claims require a typed upstream candidate score.

HISTORICAL_TEST_COST: MEDIUM

FORWARD_READINESS: READY_WITH_SMALL_ENGINEERING; 4/5

FORWARD_ENABLEMENT_COST: 2/5; scope S

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY — `B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, section `H06 — DPP_SUBMODULAR_PORTFOLIO_SELECTION`

REQUIRED_NEW_MODEL_OUTPUT: NONE for a geometry-only portfolio-efficiency claim; CONDITIONAL_UPSTREAM_SCORE_REQUIRED for predictive-edge claims

REQUIRED_RUNTIME_CAPABILITY: Identical frozen candidate pool, score/proxy semantics, ticket count, number pool, budget, and cutoff; deterministic DPP-MAP and submodular-greedy operators; exact matched greedy, orthogonal, and conditional-random comparators

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: NONE

PREPARATION_REQUIRED: MINIMAL

PREDICTIVE_DISCOVERY_VALUE: MEDIUM

POST_PREDICTION_PORTFOLIO_VALUE: HIGH

### Candidate C — H04 / canonical H07

DISPLAY_ID: H04

CANONICAL_ID: H07

CANONICAL_TITLE: CALIBRATED_PER_NUMBER_PROBABILITIES / Calibrated per-number probability model

ORIGINAL_TRACK_D_PRIORITY: 8

ORIGINAL_DISCOVERY_SCORE: 4.0000

NOVELTY: 5/5

ORTHOGONALITY: 5/5

COLLISION_STATUS: OPEN_NO_EXACT_HISTORICAL_MATCH; PRIOR_CONTACT=NOT_TESTED; exact matches 0, strong component overlap 1

HISTORICAL_TESTABILITY: 4/5; PARTIAL_HISTORICAL_INPUT_PATH

DATA_SUFFICIENCY: Causal draw history and outcomes exist, but calibrated dense 49-number probabilities are absent from all 133 historical ticket records and cannot be reconstructed by normalizing arbitrary scores or ranks.

HISTORICAL_TEST_COST: MEDIUM_TO_HIGH

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

FORWARD_ENABLEMENT_COST: 4/5; scope XL

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY — `B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, section `H04 — CALIBRATED_PER_NUMBER_PROBABILITIES`

REQUIRED_NEW_MODEL_OUTPUT: Typed dense causal 49-vector `P(number appears)` with calibration provenance

REQUIRED_RUNTIME_CAPABILITY: Deterministic blocked/OOF probability producer; nested temporal calibration and replay; Brier/log-loss/ECE proper scoring; legal ticket constructor; forward adapter

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: NONE; bounded output/model preparation is required

PREPARATION_REQUIRED: MODERATE

### Candidate D — H08 / canonical H12

DISPLAY_ID: H08

CANONICAL_ID: H12

CANONICAL_TITLE: TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS / Temporal hypergraph motifs and communities

ORIGINAL_TRACK_D_PRIORITY: 9

ORIGINAL_DISCOVERY_SCORE: 3.9800

NOVELTY: 5/5

ORTHOGONALITY: 5/5

COLLISION_STATUS: OPEN_NO_EXACT_HISTORICAL_MATCH; PRIOR_CONTACT=FAMILY_TESTED_NEW_HYPOTHESIS_OPEN; exact matches 0, strong component overlaps 11

HISTORICAL_TESTABILITY: 4/5; READY_FOR_HISTORICAL_EXPERIMENT

DATA_SUFFICIENCY: Raw draw and pair/triple histories support offline construction, but no rolling temporal-hypergraph feature/scoring pipeline exists.

HISTORICAL_TEST_COST: MEDIUM for a minimal preregistered motif set; HIGH for broad motif/community search

FORWARD_READINESS: REQUIRES_NEW_RUNTIME_ARCHITECTURE; 1/5

FORWARD_ENABLEMENT_COST: 5/5; scope XL

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY — `B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, section `H08 — TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS`

REQUIRED_NEW_MODEL_OUTPUT: Time-decayed motif counts, independence residuals, temporal community state, and typed number/ticket residual score

REQUIRED_RUNTIME_CAPABILITY: Frozen tiny motif vocabulary and one decay; causal rolling hypergraph engine; residual scorer; marginal/static-graph baselines; deterministic replay and versioned adapter

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW — temporal evolution is shared only at a broad level; the slope/acceleration mechanism is not reused

H07_FAILURE_RELEVANCE: LOW — no frozen change detector, threshold, or allocation response is reused

H09_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: NONE; bounded offline Level 1 remains possible

PREPARATION_REQUIRED: MODERATE

### Candidate E — H10 / canonical H17

DISPLAY_ID: H10

CANONICAL_ID: H17

CANONICAL_TITLE: DYNAMIC_BAYESIAN_STATE_SPACE_MODELING / Dynamic Bayesian state-space probability model

ORIGINAL_TRACK_D_PRIORITY: 10

ORIGINAL_DISCOVERY_SCORE: 3.8200

NOVELTY: 5/5

ORTHOGONALITY: 5/5

COLLISION_STATUS: OPEN_NO_EXACT_HISTORICAL_MATCH; PRIOR_CONTACT=NOT_TESTED; exact matches 0, strong component overlaps 7

HISTORICAL_TESTABILITY: 4/5; READY_FOR_HISTORICAL_EXPERIMENT

DATA_SUFFICIENCY: Causal counts, chronology, and historical outcomes support a bounded model, but no typed filtered posterior, posterior-predictive probability vector, deterministic replay, or adapter exists.

HISTORICAL_TEST_COST: MEDIUM_TO_HIGH

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

FORWARD_ENABLEMENT_COST: 4/5; scope L

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY — `B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, section `H10 — DYNAMIC_BAYESIAN_STATE_SPACE_MODELING`

REQUIRED_NEW_MODEL_OUTPUT: Filtered latent-state posterior, posterior-predictive calibrated 49-number probabilities, transition uncertainty, and state-conditioned ticket score

REQUIRED_RUNTIME_CAPABILITY: Frozen priors/state dimension/initialization/inference; causal filtering only, never future-smoothed; deterministic replay and checkpoints; proper-score baselines; legal constructor and adapter

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: LOW — both are temporal, but H10 tests latent filtered posterior dynamics rather than window derivatives

H07_FAILURE_RELEVANCE: LOW — a latent state model does not reuse the failed change-detector × threshold × allocation action

H09_FAILURE_RELEVANCE: NONE

STRUCTURAL_BLOCKER: NONE; a parsimonious bounded historical model remains possible

PREPARATION_REQUIRED: MODERATE

No selectable candidate has HIGH failure relevance to H01, H03, H07, or H09.

## 5. NEXT_CANDIDATE_SHORTLIST = 3

### RANK: 1

DISPLAY_ID: H05

CANONICAL_ID: H10

CANONICAL_TITLE: DIRECT_TICKET_LEVEL_RESIDUAL_SCORING

ORIGINAL_PRIORITY: 6

WHY_STILL_OPEN: Existing pair/triple, Apriori, combination, and portfolio methods do not test a deterministic causal direct ticket-level residual score on an identical frozen bounded candidate set.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

NOVELTY: 5/5

ORTHOGONALITY: 5/5

DATA_READINESS: READY_FOR_HISTORICAL_EXPERIMENT; candidate pool is derivable and ticket outcomes/baselines are authoritative

HISTORICAL_TEST_COST: MEDIUM at 256 frozen candidates

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY

PREPARATION_REQUIRED: MODERATE

WHY_NOW: It is the highest original-priority selectable hypothesis after H02's structural deferral and H09's exact closure. It retains 5/5 novelty, orthogonality, historical testability, and potential information gain, and a negative Level-1 result would eliminate a meaningful joint-ticket mechanism.

WHY_NOT_NOW: A deterministic 256-ticket causal pool, typed interaction score, regularization, folds, comparator identity, and tie/seed contract must first be frozen under separate Track B authorization.

### RANK: 2

DISPLAY_ID: H06

CANONICAL_ID: H14

CANONICAL_TITLE: DPP_SUBMODULAR_PORTFOLIO_SELECTION

ORIGINAL_PRIORITY: 7

WHY_STILL_OPEN: No prior strategy exactly tests DPP-MAP or an explicitly predeclared submodular marginal-utility objective under the identical-pool, identical-budget, identical-cutoff fairness invariant.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

NOVELTY: 4/5

ORTHOGONALITY: 3/5

DATA_READINESS: READY_FOR_HISTORICAL_EXPERIMENT; candidate pool and overlap geometry are available/derivable

HISTORICAL_TEST_COST: MEDIUM

FORWARD_READINESS: READY_WITH_SMALL_ENGINEERING; 4/5

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY

PREPARATION_REQUIRED: MINIMAL

WHY_NOW: It is next in the frozen ranking and can answer a controlled portfolio-efficiency question with exact same-pool comparators.

WHY_NOT_NOW: Its strongest value is post-prediction portfolio geometry; success would not by itself establish new predictive information. Its original information-gain and orthogonality scores are below H05's.

### RANK: 3

DISPLAY_ID: H04

CANONICAL_ID: H07

CANONICAL_TITLE: CALIBRATED_PER_NUMBER_PROBABILITIES

ORIGINAL_PRIORITY: 8

WHY_STILL_OPEN: The historical system does not expose calibrated out-of-sample 49-number probabilities, and tickets/scores/ranks cannot substitute for that typed probabilistic output.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

H09_FAILURE_RELEVANCE: NONE

NOVELTY: 5/5

ORTHOGONALITY: 5/5

DATA_READINESS: PARTIAL_HISTORICAL_INPUT_PATH; causal history/outcomes exist, probability outputs do not

HISTORICAL_TEST_COST: MEDIUM_TO_HIGH

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

EXPERIMENT_SPEC_AVAILABLE: YES_DRAFT_ONLY

PREPARATION_REQUIRED: MODERATE

WHY_NOW: It tests a scientifically orthogonal predictive-output and calibration mechanism with high discovery value and a clean proper-score failure criterion.

WHY_NOT_NOW: It is lower in the frozen ranking, has 4/5 rather than 5/5 historical testability, and requires a new typed probability producer plus nested replay before Level 1.

H08/H12 and H10/H17 remain open but are outside the three-item shortlist because they are lower in the frozen ranking and require heavier feature/runtime or model preparation. They are not classified negative.

## 6. Selected single successor

NEXT_B_HYPOTHESIS: H05 / canonical H10 — DIRECT_TICKET_LEVEL_RESIDUAL_SCORING

RESEARCH_LINE: FUTURE_COHORT_V3_DISCOVERY

PROSPECTIVE_STATUS: NOT_FROZEN

SELECTION_REASON: H05 is the highest-ranked currently selectable original Top-10 hypothesis. It preserves the frozen queue, is fully orthogonal to the four exact non-advancing mechanisms, is historically falsifiable on a bounded same-pool design, and has an existing Level-1 specification. Its 5/5 novelty, orthogonality, testability, and information-gain scores make both positive and negative outcomes decision-useful.

WHY_SELECTED_OVER_SHORTLIST_2: H05 tests new predictive interaction information directly; H06 primarily tests portfolio efficiency and has lower original information gain and orthogonality. H06 remains open.

WHY_SELECTED_OVER_SHORTLIST_3: H05 is higher in the frozen ranking and ready for historical testing with 5/5 testability. H04 requires a new calibrated probability output and nested replay before its 4/5-testability Level 1. H04 remains open.

WHY_NOT_SHORTLIST_2: H06 is not selected first because its primary answer is portfolio-efficiency/diversity value, not new predictive information; its frozen information-gain and orthogonality scores are also below H05's.

WHY_NOT_SHORTLIST_3: H04 is not selected first because it is lower in the frozen ranking and requires a new typed probability producer plus nested calibration/replay before historical Level 1.

WHAT_NEW_INFORMATION_IT_TESTS: Whether causal pair/triple ticket interactions contain stable held-out residual value beyond an additive number score when both methods rank the exact same frozen 256 legal candidates under the same cutoff and budget.

WHAT_H01_H03_H07_H09_DID_NOT_TEST: H01 tested cross-strategy residual/leadership selection; H03 tested multi-window slope/acceleration/disagreement increments; H07 tested one change-detector × threshold × allocation action; H09 tested one positive-selector × negative-signal × condition × suppression action. None emitted or evaluated a typed direct ticket-level interaction residual score on a fixed candidate pool.

WHAT_PRIOR_H01_H03_H07_H09_DID_NOT_TEST: The same exact distinction above: none of the four prior experiments tested a typed direct ticket-level interaction residual score on an identical frozen candidate pool.

WHAT_NEGATIVE_RESULT_WOULD_RULE_OUT: Incremental value of the exact preregistered regularized pair/triple residual basis over the additive score on the same 256-candidate Level-1 pool, folds, budget, endpoints, and matched-random comparator. It would not close all ticket-level, interaction, pair/triple, or portfolio families.

WHAT_POSITIVE_RESULT_WOULD_JUSTIFY: A request for separately authorized Level 2 using the frozen family at 256/1,024/4,096 candidate sizes in nested blocked folds with exact candidate-matched baselines and hit-depth endpoints. It would not authorize Level 2 automatically, create Cohort V3, modify Cohort V2, establish prospective edge, or permit production/betting use.

DISCOVERY_VALUE: HIGH

DATA_READINESS: READY_FOR_HISTORICAL_EXPERIMENT

HISTORICAL_TEST_COST: MEDIUM at the bounded Level-1 size

FORWARD_READINESS: REQUIRES_NEW_MODEL_OUTPUT; 1/5

EXPECTED_RESEARCH_DEPTH: LEVEL_1_FAST_FALSIFICATION_ONLY

## 7. Track B specification boundary

TRACK_B_EXISTING_SPEC_LOCATOR: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, section `H05 — DIRECT_TICKET_LEVEL_RESIDUAL_SCORING`, draft task ID `B649_TRACK_B_H05_DIRECT_TICKET_LEVEL_RESIDUAL_SCORING_DRAFT_R1`

TRACK_B_SPEC_STATUS: NEEDS_BOUNDED_PREPARATION

REQUIRED_PREPARATION_OR_ADAPTATION:

1. Before any target outcomes are evaluated, define and seal a deterministic causal generator that produces exactly 256 legal candidate tickets per eligible target, including pool identity/hash, ordering, deduplication, cutoff, and tie/seed semantics.
2. Define one typed deterministic ticket score that compares an additive-number component with one preregistered regularized pair/triple residual basis; freeze feature semantics, regularization, training window/folds, and output schema.
3. Bind additive, interaction, and matched-random comparators to the identical candidate pool, ticket budget, target population, folds, endpoints, and cutoff. Do not search the full 13,983,816-ticket universe.
4. Add the four sealed result task IDs/hashes to the context ledger as `EXECUTED_NOT_ADVANCED`; use them only to remove their exact hypotheses and prevent post-hoc rescue or result mining.

No preparation was executed here. No full Track B Worker prompt was generated because the existing spec is usable after bounded preparation.

## 8. Boundaries and lifecycle

TOP10_POOL_EXHAUSTED_OR_BLOCKED: NO

EXTERNAL_FRONTIER_FALLBACK_USED: NO

COHORT_V2_RELATIONSHIP: NONE

H01_H03_H07_H09_IMPACT_ON_COHORT_V2: NONE

H09_REMEDIATION: NOT_REQUIRED

H09_LEVEL2: NOT_AUTHORIZED

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

BLOCKERS: NONE

IMPLEMENTATION_LIFECYCLE_STATUS: COMPLETE

PR_PUBLICATION_STATUS: NOT_AUTHORIZED

POSTMERGE_LIFECYCLE_STATUS: NOT_APPLICABLE

BRANCH_CLEANUP_STATUS: NOT_APPLICABLE

FULL_PR_LIFECYCLE_CLOSED: NO

CHANGED: Exactly this one authorized repo-external Markdown decision artifact

NEXT: Send exactly H05 / canonical H10 `DIRECT_TICKET_LEVEL_RESIDUAL_SCORING` to Track B for separately authorized Level-1 historical fast falsification. Do not start multiple hypotheses from this decision.

END
