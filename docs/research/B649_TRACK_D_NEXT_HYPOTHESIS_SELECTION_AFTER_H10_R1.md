# B649 Track D Next Hypothesis Selection After H10 R1

TASK_ID:
B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H10_R1

STATUS:
PASS

MODE:
READ_ONLY_RESEARCH_DECISION

TASK_CLASS:
READ_ONLY_ANALYSIS

WORKER_ROUTE:
STANDARD

JUDGE_MODE:
NOT_APPLICABLE

OWNER_RESEARCH_POLICY:
WIDE_IN_STRICT_OUT

RESEARCH_LINE:
FUTURE_COHORT_V3_DISCOVERY

OUTPUT_PATH:
/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H10_R1.md

INTENT: the sealed H10/H17 result is descriptively positive versus trailing-50 but inferentially WEAK_SIGNAL with LEVEL_1_DECISION=DO_NOT_ADVANCE against the load-bearing static-Beta comparator; the task expects exact B649 R1 closure without global-family overreach, preservation of H02/H27's structural deferral, exact original Top-10 arithmetic, and exactly one successor; the opened queue and experiment authorities leave only H06/H14 selectable and require a bounded same-pool portfolio-efficiency test rather than a new predictive-information claim.

## 1. H10/H17 canonical mapping and sealed local decision

H10_DISPLAY_ID:
H10

H10_CANONICAL_ID:
H17

H10_CANONICAL_TITLE:
DYNAMIC_BAYESIAN_STATE_SPACE_MODELING

H10_EXECUTION_TASK_ID:
B649_TRACK_B_H10_DYNAMIC_BAYESIAN_STATE_SPACE_MODELING_LEVEL1_R1

H10_SEALED_TASK_ROOT:
/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H10_DYNAMIC_BAYESIAN_STATE_SPACE_MODELING_LEVEL1_R1

H10_FINAL_RESULT_AVAILABLE:
YES

H10_DESCRIPTIVE_CLASSIFICATION:
POSITIVE_BUT_UNCERTAIN

H10_INFERENTIAL_CLASSIFICATION:
WEAK_SIGNAL

H10_RESEARCH_CLASSIFICATION:
WEAK_SIGNAL

H10_LEVEL_1_DECISION:
DO_NOT_ADVANCE

H10_EXECUTION_STATUS:
EXECUTED_NOT_ADVANCED

H10_LEVEL_2_RUN:
NO

H10_RECOMMEND_LEVEL_2:
NO

H10_STABILITY_RESULT:
FAIL

H10_UNCERTAINTY_RESULT:
FAIL

H10_POSTERIOR_UNCERTAINTY_RESULT:
PASS

H10_MEANINGFUL_EFFECT_GATE:
FAIL

H10_CAUSALITY_AUDIT:
PASS

H10_FILTERING_SMOOTHING_AUDIT:
PASS

H10_SMOOTHING_USED_IN_PREDICTIVE_PATH:
NO

H10_COHORT_V2_FIREWALL:
PASS

H10_EXACT_MODEL:
H10_DCT3_LINEAR_GAUSSIAN_FILTER_V1 — one three-dimensional continuous latent state using fixed DCT modes 1–3, diagonal AR(1) transition phi=0.95, fixed process/emission variances, and exact diagonal Kalman filtering without smoothing or hyperparameter fitting.

H10_PRIMARY_COMPARATOR:
STATIC_BETA_BINOMIAL_EXPANDING_ONE_PSEUDODRAW_V1

H10_TEMPORAL_COMPARATOR:
TRAILING_50_BETA_BINOMIAL_ONE_PSEUDODRAW_V1

H10_PRIMARY_ENDPOINT:
MEAN_PER_NUMBER_BRIER_IMPROVEMENT

| Primary Brier contrast | Observed delta | 95% cluster-bootstrap interval | Holm p | Positive folds |
|---|---:|---:|---:|---:|
| Dynamic minus static Beta | 0.000000322228896 | [-0.000005179577232, 0.000006721159490] | 0.460418701171875 | 2/5 |
| Dynamic minus trailing 50 | 0.001905127882367 | [0.001781848053176, 0.002026793140844] | 0.000061035156250 | 5/5 |

H10_PREREGISTERED_MEANINGFUL_EDGE:
0.000100000000000 Brier improvement

H10_B649_MEANINGFUL_EDGE_STATUS:
EXCLUDED_FOR_THIS_DESIGN

[Confirmed] The dynamic model was descriptively better than trailing-50 in all five folds, but the load-bearing dynamic-minus-static-Beta effect was approximately 0.000000322, its interval crossed zero, and its upper bound remained below the frozen 0.0001 meaningful edge. The preregistered meaningful-effect, stability, and uncertainty gates therefore failed.

H10_DESIGN_POWER_AT_DECLARED_EDGE_PER_CONTRAST:
0.490636762335554

H10_DESIGN_POWER_JOINT_INDEPENDENCE_APPROXIMATION:
0.240724432555115

H10_TARGET_MDE_FOR_80_PERCENT_JOINT_POWER:
0.000165783593089

H10_POWER_INTERPRETATION:
The approximately 49% per-contrast design power limits inference about the global family. It does not authorize a B649 rescue, remediation, new design, or Level 2, and it does not change the exact R1 DO_NOT_ADVANCE decision.

H10_B649_CURRENT_DESIGN:
DO_NOT_ADVANCE

H10_B649_R1_CELL:
B649 × H10/H17 × LEVEL1_R1 = EXECUTED_NOT_ADVANCED

H10_B649_R1_REMEDIATION:
NOT_AUTHORIZED

H10_B649_REMEDIATION:
NOT_AUTHORIZED

H10_B649_LEVEL2:
NOT_AUTHORIZED

H10_RESCUE:
NOT RUN

H10_RERUN:
NOT RUN

H10_GLOBAL_FAMILY:
RETAIN

GLOBAL_FAMILY_EXHAUSTED:
NO

EXHAUSTED_AT_DECLARED_EDGE:
NO

H10_T539:
UNTESTED

H10_P638:
UNTESTED

CROSS_LOTTERY_H10_LEDGER:

HYPOTHESIS:
H10/H17 DYNAMIC_BAYESIAN_STATE_SPACE_MODELING

B649:
R1 SEALED; WEAK_SIGNAL; DO_NOT_ADVANCE; MEANINGFUL_EDGE_EXCLUDED_FOR_THIS_DESIGN

GLOBAL_FAMILY:
RETAIN

T539:
UNTESTED

P638:
UNTESTED

CROSS_LOTTERY_WORK_LAUNCHED:
NO

MANIFEST_STATUS:
PASS — experiment_record_state SEALED; task identity, WEAK_SIGNAL classification, DO_NOT_ADVANCE decision, preregistration hash, 17 payload entries, and payload-tree hash are present.

SHA256SUMS_STATUS:
PASS — `shasum -a 256 -c SHA256SUMS` returned exit 0 and `OK` for MANIFEST.json plus all 17 sealed payload entries (18 checked entries total).

H10_PAYLOAD_TREE_SHA256:
426d08b4d8472470a7ed6888c98a8b28f7f65871b6c4018ee8ca8241b4219daa

H10_PREREGISTRATION_SHA256:
2e5160633b86113581673a05df2a068203d9df0baf720fa158f29e9abdf30428

| H10 sealed decision surface | Observed SHA-256 |
|---|---|
| report.md | db4176fc76640a80db91a718aae06f15a9c7c8e09b020d7459a52a482ac53841 |
| MANIFEST.json | adf98b1600da22954511e7e186ee156657d3b89608b9b1446acd01c1f87311c9 |
| SHA256SUMS | 5b61fa3c585f848e36c2082c3c794780c80f9c3770b4821e227d548fee3e0e4b |
| preregistered_level1_contract.json | 2e5160633b86113581673a05df2a068203d9df0baf720fa158f29e9abdf30428 |
| validation.json | 8ec82e52741a8f6fb8ae717368a2a90213a4424902eed82bbb271b3b7e4dd337 |

[Confirmed] The H10 report, manifest, validation record, preregistered contract, and checksum inventory agree on the mapping, result, exact-design meaningful-edge exclusion, Level-2 status, and design-power caveat.

STOP_H10_CANONICAL_MAPPING_UNRESOLVED:
NOT TRIGGERED

STOP_H10_FINAL_RESULT_NOT_AVAILABLE:
NOT TRIGGERED

STOP_H10_FINAL_DECISION_AMBIGUOUS:
NOT TRIGGERED

STOP_H10_SEALED_EVIDENCE_CONTRADICTION:
NOT TRIGGERED

## 2. Track D authorities and bounded integrity

LATEST_PRIOR_QUEUE_SELECTION_AUTHORITY:
/Users/kelvin/VibeCoding-WorkSpace/B649_NEXT_HYPOTHESIS_SELECTION_AFTER_H08_R1.md

LATEST_PRIOR_QUEUE_SELECTION_SHA256:
4f472a1297b8212f03fbd0bb211484592b2e7efcc76cd3792fe29948db330d93

| Existing Track D authority | Observed SHA-256 |
|---|---|
| /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_RESEARCH_SURFACE_R1.md | 26add8e34cb259cffdd54c6cd8f91373980ffe7c2277b17b2afaca8c936c8859 |
| /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_R1.md | 6758482663fd46f14f86a293f0eef1a2bc77ff3186931267c5197f8cac87287b |
| /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md | 335c5921978fd167658dd14c3bdac539edfdf2b405609d9e275fcbe024e4959d |
| /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_PRIORITY_RANKING_R1.csv | b0953cf2548e1fe9a941197d26a5bee9456b75adfa99361a1195acbcf663b869 |
| /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_HYPOTHESIS_DATA_SUFFICIENCY_MATRIX_R1.csv | 9200b55d61b6fde69fa173c97bac419e8f9c10813fd415aef03f76662b1874ab |

SUPPORTING_FRONTIER_AUTHORITIES_LOCATED:

- /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2_NORMALIZED_R1.csv — 6381f574410b93efc02c96f70aa017f40db53328c4b532b78efd9bb1fb2c2dcb
- /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_FRONTIER_V2_DISCOVERY_WAVES_R1.csv — 953bd940a72fdec42c08cdab4ca8ff7451287b45ce4e91f9bf506dfbd177823c
- /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_FRONTIER_V2_SPEC_REGISTRY_R1.csv — fa8801edbeb91040d6e189dd7fcb2e8ec5cd8424dacd7f412ffe034f41d1ac43

FRONTIER_V2_SELECTION_CONTENT_USED:
NO — fallback is not eligible because one original Top-10 hypothesis remains selectable.

EXTERNAL_RESEARCH_SEARCH:
NOT RUN

AUTHORITY_REGENERATION:
NOT RUN

COLLISION_MATRIX_REBUILD:
NOT RUN

FRONTIER_REBUILD:
NOT RUN

REPOSITORY_ROOT:
/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis

BRANCH:
main

INITIAL_HEAD:
22705b9068d38ad4d610a49eb3ce6df57eaf4d6d

INITIAL_TREE:
9ef03038447150676e4252b45556033c38c69cea

FINAL_HEAD:
22705b9068d38ad4d610a49eb3ce6df57eaf4d6d

FINAL_TREE:
9ef03038447150676e4252b45556033c38c69cea

WORKTREE_STATUS:
CLEAN; branch main tracks origin/main at +0/-0. Initial and final HEAD/tree are identical.

WORKTREE_MODE:
EXISTING_CANONICAL_WORKTREE; no switch, checkout, reset, restore, clean, stash, add, commit, push, or PR action was run.

## 3. Original Top-10 execution ledger and arithmetic

[Confirmed] The frozen discovery-priority authority contains exactly ten unique display IDs. The collision authority supplies the one-to-one aliases. The sealed prior queue authority establishes seven exact closures; the independently verified sealed H10 result establishes the eighth.

| Discovery priority | Display ID | Canonical ID | Canonical title | Current queue status |
|---:|---|---|---|---|
| 1 | H01 | H01 | CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR | EXECUTED_NOT_ADVANCED |
| 2 | H03 | H04 | MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT | EXECUTED_NOT_ADVANCED |
| 3 | H07 | H19 | CHANGE_POINT_TRIGGERED_ALLOCATION | EXECUTED_NOT_ADVANCED |
| 4 | H02 | H27 | HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION | STRUCTURALLY_DEFERRED |
| 5 | H09 | H21 | CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION | EXECUTED_NOT_ADVANCED |
| 6 | H05 | H10 | DIRECT_TICKET_LEVEL_RESIDUAL_SCORING | EXECUTED_NOT_ADVANCED |
| 7 | H06 | H14 | DPP_SUBMODULAR_PORTFOLIO_SELECTION | SELECTABLE |
| 8 | H04 | H07 | CALIBRATED_PER_NUMBER_PROBABILITIES | EXECUTED_NOT_ADVANCED |
| 9 | H08 | H12 | TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS | EXECUTED_NOT_ADVANCED |
| 10 | H10 | H17 | DYNAMIC_BAYESIAN_STATE_SPACE_MODELING | EXECUTED_NOT_ADVANCED |

EXECUTION_LEDGER:

H01/H01 = EXECUTED_NOT_ADVANCED

H03/H04 = EXECUTED_NOT_ADVANCED

H07/H19 = EXECUTED_NOT_ADVANCED

H09/H21 = EXECUTED_NOT_ADVANCED

H05/H10 = EXECUTED_NOT_ADVANCED

H04/H07 = EXECUTED_NOT_ADVANCED

H08/H12 = EXECUTED_NOT_ADVANCED

H10/H17 = EXECUTED_NOT_ADVANCED

ORIGINAL_TOP10_COUNT:
10

EXECUTED_NOT_ADVANCED_COUNT:
8

STRUCTURALLY_DEFERRED_COUNT:
1

UNEXECUTED_COUNT:
2

SELECTABLE_COUNT:
1

ORIGINAL_TOP10_SELECTABLE_COUNT:
1

ORIGINAL_TOP10_EXHAUSTED_OR_DEFERRED:
NO

[Confirmed] Schema-aware parsing reproduced the arithmetic: ten unique discovery rows minus eight exact executed-not-advanced cells leaves H02/H27 and H06/H14 unexecuted; H02/H27 remains structurally deferred, so H06/H14 is the single selectable item.

NO_EXECUTED_HYPOTHESIS_REENTERED_QUEUE:
PASS

## 4. Remaining original Top-10 candidates

### H02 / canonical H27 — HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION

DISPLAY_ID:
H02

CANONICAL_ID:
H27

CANONICAL_TITLE:
HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION

ORIGINAL_PRIORITY:
DISCOVERY_PRIORITY 4

STATUS:
STRUCTURALLY_DEFERRED, NOT NEGATIVE, NOT EXECUTED, NOT SELECTABLE

DEFER_REASON:
NO_PREAUTHORIZED_UNTOUCHED_INDEPENDENT_CONFIRMATION_EVIDENCE

STRUCTURAL_BLOCKER:
The sealed 1,957-target producer supports reproduction or historical stress only and cannot independently confirm itself. Engineering cannot manufacture untouched evidence, and Cohort V2 prospective evidence is forbidden for this purpose.

H10_FAILURE_RELEVANCE:
NONE — H10's exact DCT3/Kalman filtered-state design and static-Beta comparison do not supply or invalidate H02's required untouched Horizon Minimax confirmation evidence.

STRUCTURAL_DEFERRAL_PRESERVED:
PASS

### H06 / canonical H14 — DPP_SUBMODULAR_PORTFOLIO_SELECTION

DISPLAY_ID:
H06

CANONICAL_ID:
H14

CANONICAL_TITLE:
DPP_SUBMODULAR_PORTFOLIO_SELECTION

ORIGIN:
ORIGINAL_TRACK_D_TOP_10

ORIGINAL_PRIORITY:
DISCOVERY_PRIORITY 7; original research-surface Top-10 section ordinal 6

NOVELTY:
4/5; MEDIUM_HIGH

ORTHOGONALITY:
3/5; MEDIUM

POTENTIAL_INFORMATION_GAIN:
4/5

COLLISION_STATUS:
OPEN; exact 0, strong 12, weak 8, same-family/different-hypothesis 10

HISTORICAL_TESTABILITY:
5/5; READY_FOR_HISTORICAL_EXPERIMENT after bounded preparation

DATA_READINESS:
A bounded causal legal-ticket pool is derivable, exact overlap geometry is derivable from native tickets, and historical deltas are authoritative. Candidate ranking is proxy-only unless a new causal score is generated and must never be relabeled as strategy-internal ranking.

HISTORICAL_TEST_COST:
MEDIUM

FORWARD_READINESS:
READY_WITH_SMALL_ENGINEERING; 4/5 under the prior queue authority. A DPP/submodular forward adapter is not currently pinned.

EXPERIMENT_SPEC_STATUS:
DRAFT_ONLY; NEEDS_BOUNDED_PREPARATION

PREPARATION_REQUIRED:
Freeze the identical candidate-pool hash, score/proxy semantics, ticket count, number pool, budget, information cutoff, one DPP-MAP kernel, one submodular objective, seed policy, matched greedy/orthogonal/conditional-random comparators, primary portfolio-efficiency endpoint, and quantitative Level-1 gate.

STRUCTURAL_BLOCKER:
NONE

H01_FAILURE_RELEVANCE:
NONE

H03_FAILURE_RELEVANCE:
NONE

H07_FAILURE_RELEVANCE:
NONE

H09_FAILURE_RELEVANCE:
NONE

H05_FAILURE_RELEVANCE:
NONE — H05's failed direct ticket-interaction residual score is not required as H06's upstream utility.

H04_FAILURE_RELEVANCE:
NONE for the geometry-only claim; H04's failed probability producer cannot be treated as predictive support.

H08_FAILURE_RELEVANCE:
LOW — both may act on legal candidate tickets, but H06 does not reuse H08's motif information source, decay, residual transformation, or advance gate; H08's failed score cannot be rescued by a portfolio wrapper.

H10_FAILURE_RELEVANCE:
LOW — a probability score can be an upstream input, but H06's primary hypothesis is the same-pool portfolio operator. The failed H10 DCT3/Kalman score is neither required nor valid predictive support and cannot be rescued through H06.

PREDICTIVE_DISCOVERY_QUESTION:
Does DPP create new predictive information? Not as its primary mechanism. DPP/submodular selection rearranges a frozen candidate set; any outcome residual beyond portfolio efficiency is a separate, stricter claim.

PORTFOLIO_RESEARCH_QUESTION:
Does one frozen DPP-MAP or submodular objective improve construction of a fixed predictive candidate set under identical information, candidate pool, ticket count, number pool, budget, utility definition, and cutoff versus matched greedy, orthogonal, and conditional-random comparators?

PREDICTIVE_INFORMATION_GAIN:
LOW_TO_MEDIUM_AND_CONDITIONAL on the validity of a separately frozen upstream score.

PORTFOLIO_EFFICIENCY_GAIN:
HIGH_INFORMATION_VALUE. Coverage, diversity, overlap, and fixed-budget efficiency are the direct research targets.

INTERPRETATION_BOUNDARY:
Coverage, diversity, or overlap reduction alone does not establish improved draw prediction.

STATUS:
SELECTABLE

## 5. Required one-candidate shortlist

NEXT_CANDIDATE_SHORTLIST_COUNT:
1

NEXT_CANDIDATE_SHORTLIST:

### 1

DISPLAY_ID:
H06

CANONICAL_ID:
H14

TITLE:
DPP_SUBMODULAR_PORTFOLIO_SELECTION

ORIGIN:
ORIGINAL_TRACK_D_TOP_10

ORIGINAL_PRIORITY:
DISCOVERY_PRIORITY 7

H10_FAILURE_RELEVANCE:
LOW

PREPARATION_REQUIRED:
Freeze one identical causal candidate pool and utility semantics, ticket count, number pool, budget, cutoff, one DPP-MAP kernel, one submodular objective, seed policy, matched comparators, and separate portfolio-efficiency versus predictive endpoints/gates.

SHORTLIST_CARDINALITY:
PASS — exactly one candidate is selectable, so exactly one is listed. No external, second-wave, or structurally deferred item was added.

## 6. Selected single successor

NEXT_B_HYPOTHESIS:
H06 / canonical H14 — DPP_SUBMODULAR_PORTFOLIO_SELECTION

RESEARCH_LINE:
FUTURE_COHORT_V3_DISCOVERY

SELECTION_REASON:
H06/H14 is the only remaining selectable original Top-10 hypothesis and has no explicit blocker. The frozen queue rule therefore selects it directly before any Frontier V2 transition. It remains historically falsifiable with a bounded same-pool Level-1 design and tests a portfolio-construction mechanism not closed by the eight prior exact failures.

WHAT_NEW_INFORMATION_IT_TESTS:
Portfolio-level set geometry and marginal utility—candidate quality/diversity decomposition, pairwise overlap/similarity, DPP determinant structure, submodular marginal gain, unique-number coverage, and fixed-budget portfolio efficiency—over one already frozen causal candidate set. It does not claim to create a new predictive signal.

WHAT_PRIOR_EXECUTED_HYPOTHESES_DO_NOT_TEST:
H01 tested cross-strategy residual-gated meta-selection; H03 fixed multi-window derivatives; H07 one change alarm/allocation rule; H09 conditional negative suppression; H05 one direct ticket-interaction residual score; H04 one ridge-logistic per-number probability producer; H08 one temporal hypergraph motif residual; and H10 one DCT3/Kalman filtered-state probability model. None compared an exact DPP-MAP and submodular portfolio operator against greedy, orthogonal, and conditional-random alternatives on the identical pool, utility, ticket count, number pool, budget, and cutoff.

WHAT_NEGATIVE_RESULT_WOULD_RULE_OUT:
Portfolio-efficiency improvement from the one preregistered DPP-MAP kernel and one submodular objective under the frozen candidate pool, utility semantics, ticket count, number pool, budget, cutoff, seed policy, comparators, primary endpoint, and gate. It would not close every DPP, submodular, portfolio-size, kernel, utility, candidate producer, or diversification design.

WHAT_POSITIVE_RESULT_WOULD_JUSTIFY:
A request for separately authorized Level 2 across multiple frozen pool/portfolio sizes with exact uncertainty and bounded producer-by-optimizer interactions. It would not establish new predictive information from coverage/diversity alone, authorize Level 2 automatically, create Cohort V3, alter Cohort V2, or promote a production/betting system.

DISCOVERY_VALUE:
MEDIUM_HIGH overall; HIGH for portfolio-efficiency research and LOW_TO_MEDIUM_CONDITIONAL for predictive discovery.

DATA_READINESS:
READY_FOR_BOUNDED_HISTORICAL_EXPERIMENT; BOUNDED_PREPARATION_REQUIRED

HISTORICAL_TEST_COST:
MEDIUM

FORWARD_READINESS:
READY_WITH_SMALL_ENGINEERING; 4/5, but forward readiness is not the selection rationale.

EXPECTED_RESEARCH_DEPTH:
LEVEL_1_FAST_FALSIFICATION_ONLY

H10_RESCUE_SELECTED:
NO

## 7. Track B specification boundary

TRACK_B_EXISTING_SPEC_LOCATOR:
/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md, section H06 — DPP_SUBMODULAR_PORTFOLIO_SELECTION, draft task ID B649_TRACK_B_H06_DPP_SUBMODULAR_PORTFOLIO_SELECTION_DRAFT_R1

TRACK_B_SPEC_HASH:
335c5921978fd167658dd14c3bdac539edfdf2b405609d9e275fcbe024e4959d

TRACK_B_SPEC_STATUS:
NEEDS_BOUNDED_PREPARATION

REQUIRED_PREPARATION_OR_ADAPTATION:

1. Freeze one causal candidate-pool definition and exact pool hash before target scoring; every optimizer receives the identical pool.
2. Freeze candidate score or proxy semantics. A proxy must remain labeled proxy-only and may not be relabeled as a strategy-internal or calibrated predictive score.
3. Freeze ticket count, number pool, budget, information cutoff, portfolio size, and one primary portfolio-efficiency utility.
4. Freeze exactly one DPP-MAP kernel/quality-diversity decomposition and one submodular marginal-utility objective for Level 1.
5. Compare EXISTING_GREEDY, ORTHOGONAL, DPP-MAP, SUBMODULAR_GREEDY, and CONDITIONAL_RANDOM on identical inputs; freeze the conditional-random seed policy.
6. Separate overlap/coverage/diversity efficiency from predictive hit-depth. Freeze one primary portfolio-efficiency endpoint and a quantitative ADVANCE/DO_NOT_ADVANCE gate; predictive residual is secondary and stricter.
7. Enforce cutoff date or canonical chronology strictly before target; tune any kernel/utility only inside blocked training folds. Target-conditioned kernels and post-hoc objective selection are forbidden.
8. Keep Level 1 to one pool, portfolio size, kernel, submodular objective, and gate. Alternative pools, sizes, kernels, utilities, seeds, endpoints, or producer-by-optimizer searches require separate authorization.
9. Bind all eight exact DO_NOT_ADVANCE results narrowly. Do not use H04, H05, H08, or H10 as a rescued upstream predictive producer.

PREPARATION_PERFORMED:
NO

LEVEL_1_RUN:
NO

LEVEL_2_RUN:
NO

NEXT_B_HYPOTHESIS_SPECIFICATION:

DISPLAY_ID:
H06

CANONICAL_ID:
H14

TITLE:
DPP_SUBMODULAR_PORTFOLIO_SELECTION

CORE_RESEARCH_QUESTION:
Under an identical frozen causal candidate set, score/proxy semantics, ticket count, number pool, budget, and cutoff, does one preregistered DPP-MAP or submodular objective improve portfolio efficiency over matched greedy, orthogonal, and conditional-random construction?

NEW_INFORMATION_SOURCE:
No new predictive raw information is required. The new transformation is portfolio-level set geometry: pairwise overlap/similarity, quality-diversity decomposition, determinant structure, submodular marginal gain, and unique-number coverage derived from the frozen candidate pool.

PRIMARY_COMPARATOR:
EXISTING_GREEDY, ORTHOGONAL, and CONDITIONAL_RANDOM on the identical candidate pool, utility, ticket count, number pool, budget, and cutoff.

LEVEL_1_BOUNDARY:
One fixed candidate pool and portfolio size; one DPP-MAP kernel; one submodular objective; matched greedy, orthogonal, and conditional-random comparators; one primary portfolio-efficiency endpoint; no alternative kernel/objective/pool/size search and no Level 2.

CAUSALITY_GUARD:
Candidate pool, candidate score/proxy, similarity, budget, utility, and all optimizer parameters must be frozen using information strictly before each target. Identical inputs are mandatory across arms; target-conditioned kernels and post-outcome objective selection are forbidden.

ADVANCE_GATE_AUTHORITY:
The H06 LEVEL_1_DESIGN, PASS_CRITERIA, FAILURE_CRITERIA, fairness invariant, and multiplicity boundary in /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md. Before execution, Track B must minimally adapt them into a preregistered numeric portfolio-efficiency, comparator, fold-stability, uncertainty, causality, and fairness gate; this decision artifact invents no threshold.

FORBIDDEN_RESCUE:
No post-outcome change to candidate pool, score/proxy semantics, ticket count, number pool, budget, cutoff, portfolio size, kernel, quality-diversity balance, submodular utility, seed, comparator, endpoint, threshold, or uncertainty rule; no use of failed H04/H05/H08/H10 outputs as rescued predictive support.

EXPECTED_INFORMATION_GAIN:
HIGH for the exact portfolio-efficiency class; LOW_TO_MEDIUM_AND_CONDITIONAL for new predictive information. Positive coverage/diversity alone is not predictive-edge evidence.

COHORT_RELATIONSHIP:
FUTURE_COHORT_V3_DISCOVERY; COHORT_V2_RELATIONSHIP=NONE; this specification does not create Cohort V3.

PENDING: H06/H14 bounded preparation and Level-1 historical fast falsification - awaiting separate Owner authorization.

## 8. Frontier, firewall, validation, and lifecycle

ORIGINAL_TOP10_EXHAUSTED_OR_DEFERRED:
NO

EXTERNAL_FRONTIER_FALLBACK_USED:
NO

FRONTIER_V2_TRANSITION:
NOT RUN

COHORT_V2_PROSPECTIVE_DATA_READ:
NO

COHORT_V2_PROSPECTIVE_DATA_USED_FOR_SELECTION:
NO

C_INTERIM_RESULT_USED:
NO

POST_FREEZE_V2_OUTCOME_USED:
NO

CURRENT_V2_TARGET_USED:
NO

COHORT_V2_RELATIONSHIP:
NONE

TRACK_C_INTERFERENCE:
NONE

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

SEALED_TASK_DATA_MUTATION:
NONE

COHORT_V2_MUTATION:
NONE

COHORT_V3_CREATION:
NONE

TRACK_C_MUTATION:
NONE

TRACK_B_RESULT_MUTATION:
NONE

VALIDATION:

H10/H17 mapping verified: PASS

H10 sealed checksum inventory: PASS

Exact B649 × H10/H17 × Level-1 R1 cell closed: PASS

H10 global family retained: PASS

T539/P638 remain UNTESTED: PASS

Execution ledger cardinality: PASS

Original Top-10 exact membership: PASS

H02 structural deferral preserved: PASS

Selectable count exactly one: PASS

Shortlist cardinality exactly one: PASS

No executed hypothesis re-entered queue: PASS

No H10 rescue selected: PASS

No Cohort V2 prospective evidence consumed: PASS

Exactly one successor selected: PASS

H06 existing spec locator/hash resolved: PASS

Repository mutation: NONE

Database mutation: NONE

Track C interference: NONE

BLOCKERS:
NONE for this queue decision. H02/H27 remains separately STRUCTURALLY_DEFERRED. H06/H14 requires bounded preparation and separate Owner authorization before any Level-1 execution.

ATTEMPT_LEDGER:
One targeted `jq` query assumed the earlier H08 validation schema and failed when H10's `validation.json` had no `.checks` array. The exact H10 manifest/validation keys were then inspected, a schema-correct query was run successfully, and no file, experiment, repository, database, or sealed task state was changed.

IMPLEMENTATION_LIFECYCLE_STATUS:
COMPLETE

PR_PUBLICATION_STATUS:
NOT_APPLICABLE

POSTMERGE_LIFECYCLE_STATUS:
NOT_APPLICABLE

BRANCH_CLEANUP_STATUS:
NOT_APPLICABLE

FULL_PR_LIFECYCLE_CLOSED:
NO

CURRENT_CONTEXT_PERCENT:
UNKNOWN

CURRENT_CONTEXT_USAGE_SOURCE:
HEURISTIC

QUALITATIVE_CONTEXT_PRESSURE:
MEDIUM

FILES_WRITTEN_DURING_TASK:
/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H10_R1.md

FILES_RETAINED_AT_END:
/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H10_R1.md

FILES_DELETED_BEFORE_END:
NONE

NEXT:
Send exactly H06 / canonical H14 DPP_SUBMODULAR_PORTFOLIO_SELECTION to Track B for separately authorized bounded preparation and Level-1 historical fast falsification. Do not execute H06 here, do not start Frontier V2, and do not authorize H10 remediation or Level 2.

END
