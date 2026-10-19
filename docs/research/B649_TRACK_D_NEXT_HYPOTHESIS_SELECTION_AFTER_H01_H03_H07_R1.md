# B649 Track D Next Hypothesis Selection After H01/H03/H07 R1

TASK_ID: B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H01_H03_H07_R1

STATUS: PASS

MODE: READ_ONLY_RESEARCH_DECISION

OWNER_RESEARCH_POLICY: WIDE_IN_STRICT_OUT

RESEARCH_LINE: FUTURE_COHORT_V3_DISCOVERY

OUTPUT_PATH: /Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_NEXT_HYPOTHESIS_SELECTION_AFTER_H01_H03_H07_R1.md

## 1. Authority and sealed-result verification

[Confirmed] The five load-bearing Track D authorities rehash to the SHA-256 values sealed by H01, H03, and H07:

- `B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_R1.md`: `6758482663fd46f14f86a293f0eef1a2bc77ff3186931267c5197f8cac87287b`
- `B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`: `335c5921978fd167658dd14c3bdac539edfdf2b405609d9e275fcbe024e4959d`
- `B649_TRACK_D_TOP10_PRIORITY_RANKING_R1.csv`: `b0953cf2548e1fe9a941197d26a5bee9456b75adfa99361a1195acbcf663b869`
- `B649_TRACK_D_HYPOTHESIS_DATA_SUFFICIENCY_MATRIX_R1.csv`: `9200b55d61b6fde69fa173c97bac419e8f9c10813fd415aef03f76662b1874ab`
- The separately sealed Top-10 collision matrix was not rebuilt or searched.

[Confirmed] The supporting forward-readiness authority was read as feasibility evidence only. It does not override historical discovery priority.

[Confirmed] Full `SHA256SUMS` verification passed for all files in each of these sealed task roots:

- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_H01_CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR_R1`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H03_MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT_DRAFT_R1`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_TRACK_B_H07_CHANGE_POINT_TRIGGERED_ALLOCATION_LEVEL1_R1`

No experiment reproduction command was run.

### EXECUTION_LEDGER

| Display ID | Canonical ID | Semantic title | Sealed result | Binding queue status |
|---|---|---|---|---|
| H01 | H01 | CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR | `RESEARCH_CLASSIFICATION=WEAK_SIGNAL`; Level-1 advancement gate failed; `LEVEL_2_RUN=NO` | EXECUTED_NOT_ADVANCED |
| H03 | H04 | MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT | `RESEARCH_CLASSIFICATION=NO_SIGNAL`; `ADVANCEMENT_GATE_STATUS=FAIL`; `LEVEL_2_RUN=NO` | EXECUTED_NOT_ADVANCED |
| H07 | H19 | CHANGE_POINT_TRIGGERED_ALLOCATION | `RESEARCH_CLASSIFICATION=WEAK_SIGNAL`; preregistered stability/advancement gate failed; `LEVEL_2_RUN=NO`; `ADVANCE=NO` | EXECUTED_NOT_ADVANCED |

H01: EXECUTED_NOT_ADVANCED

H03 / canonical H04: EXECUTED_NOT_ADVANCED

H07 / canonical H19: EXECUTED_NOT_ADVANCED

H07_REMEDIATION: NOT_REQUIRED

H07_LEVEL2: NOT_AUTHORIZED

The unpinned Python 3.14.4 provenance caveat and the matched-random episode start/length display caveat are non-load-bearing under the binding closure. They do not reopen H07 and do not change its failed preregistered stability gate.

## 2. Canonical queue accounting

ORIGINAL_TOP10_COUNT: 10

EXECUTED_NOT_ADVANCED_COUNT: 3

REMAINING_UNTESTED_TOP10_COUNT: 7

[Confirmed] The original discovery-priority authority contains ten rows. Removing only display H01, display H03/canonical H04, and display H07/canonical H19 leaves seven exact hypotheses.

| Display ID | Canonical ID | Canonical title | Original Track D priority | Current status |
|---|---|---|---:|---|
| H01 | H01 | CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR | 1 | EXECUTED_NOT_ADVANCED |
| H03 | H04 | MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT | 2 | EXECUTED_NOT_ADVANCED |
| H07 | H19 | CHANGE_POINT_TRIGGERED_ALLOCATION | 3 | EXECUTED_NOT_ADVANCED |
| H02 | H27 | HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION | 4 | OPEN_ONLY_AS_INDEPENDENT_CONFIRMATION |
| H09 | H21 | CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION | 5 | OPEN |
| H05 | H10 | DIRECT_TICKET_LEVEL_RESIDUAL_SCORING | 6 | OPEN |
| H06 | H14 | DPP_SUBMODULAR_PORTFOLIO_SELECTION | 7 | OPEN |
| H04 | H07 | CALIBRATED_PER_NUMBER_PROBABILITIES | 8 | OPEN |
| H08 | H12 | TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS | 9 | OPEN |
| H10 | H17 | DYNAMIC_BAYESIAN_STATE_SPACE_MODELING | 10 | OPEN |

TOP10_POOL_EXHAUSTED_OR_BLOCKED: NO

No Second-Wave, External EH, or Proposed Frontier V2 hypothesis enters this decision.

## 3. Required data for every remaining original Top-10 candidate

Scores below are copied from the pre-existing discovery-priority authority; `5/5` is best. Forward enablement cost uses `5/5` as hardest. Preparation is a historical Level-1 prerequisite assessment, not implementation authorization.

| Display / canonical | Canonical title | Original priority | Novelty | Orthogonality | Historical testability | Data sufficiency / preparation | Historical test cost | Forward readiness | Forward enablement | Collision status | Spec | H01 relevance | H03 relevance | H07 relevance |
|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|
| H02 / H27 | HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION | 4 | 4/5 | 5/5 | 3/5 | Historical reproduction/stress inputs are ready, but untouched confirmation evidence is absent; `PREPARATION=BLOCKING_FOR_INDEPENDENT_CONFIRMATION` | LOW for reproduction/stress; elapsed-time high for real confirmation | `READY_WITH_SMALL_ENGINEERING`; 3/5 | 2/5; S | Exact 0 inside 133; core producer already tested outside 133; open only as independent confirmation | YES | NONE | MEDIUM | LOW |
| H09 / H21 | CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION | 5 | 4/5 | 5/5 | 5/5 | Historical outcomes are ready; positive selector/score coverage is partial and one positive × negative × condition tuple must be independently frozen; `PREPARATION=MODERATE` | LOW–MEDIUM for one fixed pair | `READY_WITH_MEDIUM_ENGINEERING`; 2/5 | 3/5; M | Exact 0; strong overlap 10; `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN` | YES | LOW | NONE | LOW |
| H05 / H10 | DIRECT_TICKET_LEVEL_RESIDUAL_SCORING | 6 | 5/5 | 5/5 | 5/5 | Sealed ticket/combination histories are ready; bounded candidate generator and typed ticket score are new research outputs; `PREPARATION=MODERATE` | MEDIUM at 256 candidates; HIGH if interactions proliferate | `REQUIRES_NEW_MODEL_OUTPUT`; 1/5 | 4/5; L | Exact 0; strong overlap 11; OPEN | YES | NONE | NONE | NONE |
| H06 / H14 | DPP_SUBMODULAR_PORTFOLIO_SELECTION | 7 | 4/5 | 3/5 | 5/5 | Candidate pool, overlap, and proxy utility are available/derivable; same-pool/budget/cutoff binding remains; `PREPARATION=MINIMAL` | MEDIUM | `READY_WITH_SMALL_ENGINEERING`; 4/5 | 2/5; S | Exact 0; strong overlap 12; OPEN | YES | NONE | NONE | NONE |
| H04 / H07 | CALIBRATED_PER_NUMBER_PROBABILITIES | 8 | 5/5 | 5/5 | 4/5 | Historical outcomes exist, but calibrated 49-number probabilities must be generated causally; `PREPARATION=MODERATE` | MEDIUM–HIGH | `REQUIRES_NEW_MODEL_OUTPUT`; 1/5 | 4/5; XL | Exact 0; strong overlap 1; OPEN | YES | NONE | NONE | NONE |
| H08 / H12 | TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS | 9 | 5/5 | 5/5 | 4/5 | Raw draws and pair/triple history support offline work, but a preregistered rolling motif feature path is new; `PREPARATION=MODERATE` | MEDIUM for minimal motifs; HIGH for broad search | `REQUIRES_NEW_RUNTIME_ARCHITECTURE`; 1/5 | 5/5; XL | Exact 0; strong overlap 11; OPEN | YES | NONE | LOW | LOW |
| H10 / H17 | DYNAMIC_BAYESIAN_STATE_SPACE_MODELING | 10 | 5/5 | 5/5 | 4/5 | Causal counts/outcomes exist, but filtered posterior/probability outputs and inference are new; `PREPARATION=MODERATE` | MEDIUM–HIGH | `REQUIRES_NEW_MODEL_OUTPUT`; 1/5 | 4/5; L | Exact 0; strong overlap 7; OPEN | YES | NONE | LOW | LOW |

### Failure-relevance interpretation

- H02's H03 relevance is MEDIUM because both use cross-horizon information, but H02 tests fixed joint horizon support and independent confirmation, not slope/acceleration as incremental predictors. Its H07 relevance is LOW because it has no JSD change alarm or p300-to-p50 episode action.
- H09's H01 relevance is LOW because it has a conditional gate, but not a cross-strategy residual-leadership selector. Its H07 relevance is LOW because its context-conditioned suppression is not a change-point detector plus allocation episode.
- H05 and H06 do not depend on the information sources or action mechanisms tested by H01, H03, or H07.
- H04 tests calibrated probabilities and proper scoring, not the failed derivative or alarm mechanisms.
- H08 and H10 have only LOW broad temporal overlap with H03/H07; neither materially reuses the same information source and action mechanism.
- No remaining candidate has HIGH failure relevance to H01, H03, or H07.

## 4. NEXT_CANDIDATE_SHORTLIST = 3

### RANK: 1

DISPLAY_ID: H09

CANONICAL_ID: H21

CANONICAL_TITLE: CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION

ORIGINAL_PRIORITY: 5

WHY_STILL_OPEN: Existing negative/exclusion producers do not test the predeclared interaction between an independently frozen positive selector, one causal context, and conditional suppression. The collision authority classifies it `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`.

H01_FAILURE_RELEVANCE: LOW — conditional gating overlaps only at a broad control-flow level; H09 does not use cross-strategy residual leadership as its load-bearing mechanism.

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: LOW — H09 does not reuse the JSD detector, alarm threshold, episode window, or p300-to-p50 allocation response.

NOVELTY: 4/5

ORTHOGONALITY: 5/5

DATA_READINESS: `READY_FOR_HISTORICAL_EXPERIMENT`; `PREPARATION=MODERATE` to bind one independently selected positive selector, one negative signal, one condition, fixed suppression intensity, fixed budget, and matched-random schedule before evaluation.

HISTORICAL_TEST_COST: LOW–MEDIUM for one frozen pair.

FORWARD_READINESS: `READY_WITH_MEDIUM_ENGINEERING`; forward readiness 2/5; enablement cost 3/5; scope M.

EXPERIMENT_SPEC_AVAILABLE: YES — `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, `## H09 — CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION`, lines 449–502.

WHY_NOW: It is the earliest authority-ranked remaining hypothesis whose load-bearing question is historically falsifiable now. It was already second in the prior shortlist, is orthogonal to all three completed mechanisms, and supports a clean paired negative result.

WHY_NOT_NOW: The positive/negative/condition tuple must be frozen without H09 outer outcomes. H01's exploratory best selector and any favorable H07 variant cannot be used as a post-hoc rescue input.

### RANK: 2

DISPLAY_ID: H05

CANONICAL_ID: H10

CANONICAL_TITLE: DIRECT_TICKET_LEVEL_RESIDUAL_SCORING

ORIGINAL_PRIORITY: 6

WHY_STILL_OPEN: Pair/triple, Apriori, combination, and portfolio methods do not test a causal direct ticket-level residual score on an identical frozen bounded candidate set.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

NOVELTY: 5/5

ORTHOGONALITY: 5/5

DATA_READINESS: `READY_FOR_HISTORICAL_EXPERIMENT`; `PREPARATION=MODERATE` because the 256-ticket candidate pool and typed ticket-interaction score must be created and frozen before outcomes are evaluated.

HISTORICAL_TEST_COST: MEDIUM at the bounded Level-1 size; HIGH if candidate sizes or interactions proliferate.

FORWARD_READINESS: `REQUIRES_NEW_MODEL_OUTPUT`; forward readiness 1/5; enablement cost 4/5; scope L.

EXPERIMENT_SPEC_AVAILABLE: YES — `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, `## H05 — DIRECT_TICKET_LEVEL_RESIDUAL_SCORING`, lines 233–286.

WHY_NOW: It tests a maximally orthogonal and high-information interaction target. A negative result would rule out incremental pair/triple ticket information over additive scoring on the same frozen candidates.

WHY_NOT_NOW: It follows H09 in original priority and needs a new bounded generator, typed score, and deterministic replay before the Level-1 comparison can start.

### RANK: 3

DISPLAY_ID: H06

CANONICAL_ID: H14

CANONICAL_TITLE: DPP_SUBMODULAR_PORTFOLIO_SELECTION

ORIGINAL_PRIORITY: 7

WHY_STILL_OPEN: Existing covering, greedy, orthogonal, and portfolio methods do not provide an exact DPP or predeclared submodular objective under the mandatory same-pool, same-budget, same-cutoff fairness invariant.

H01_FAILURE_RELEVANCE: NONE

H03_FAILURE_RELEVANCE: NONE

H07_FAILURE_RELEVANCE: NONE

NOVELTY: 4/5

ORTHOGONALITY: 3/5

DATA_READINESS: `READY_FOR_HISTORICAL_EXPERIMENT`; `PREPARATION=MINIMAL` to freeze the candidate pool, proxy/utility semantics, portfolio size, budget, and matched comparators.

HISTORICAL_TEST_COST: MEDIUM.

FORWARD_READINESS: `READY_WITH_SMALL_ENGINEERING`; forward readiness 4/5; enablement cost 2/5; scope S.

EXPERIMENT_SPEC_AVAILABLE: YES — `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, `## H06 — DPP_SUBMODULAR_PORTFOLIO_SELECTION`, lines 287–340.

WHY_NOW: It is the next original-priority candidate after H05 and can deliver a well-controlled answer about portfolio efficiency with existing overlap geometry.

WHY_NOT_NOW: Its primary discovery value is portfolio efficiency rather than new predictive information, and its original orthogonality score is 3/5. A structural overlap improvement can be useful without establishing predictive edge.

## 5. Selected hypothesis

NEXT_B_HYPOTHESIS: H09 / canonical H21 — CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION

RESEARCH_LINE: FUTURE_COHORT_V3_DISCOVERY

SELECTION_REASON: H09 is the highest pre-existing priority remaining after excluding H02 from immediate selection only because independent confirmation lacks untouched evidence. H09 tests a distinct conditional-negative interaction, is historically falsifiable with a single frozen pair, has an existing Level-1 specification, and preserves the original queue instead of optimizing for an easy positive result.

WHY_SELECTED_OVER_SHORTLIST_2: H09 retains original priority 5 versus H05's priority 6 and has lower bounded Level-1 preparation and compute cost. H05 remains open and is not weakened by H01/H03/H07.

WHY_SELECTED_OVER_SHORTLIST_3: H09 retains original priority 5 versus H06's priority 7, has original orthogonality 5/5 versus 3/5, and tests incremental information rather than only portfolio geometry. H06 remains open.

WHY_NOT_SHORTLIST_2: H05 is not selected first because H09 is earlier in the frozen queue and can be falsified with one paired fixed-pair design before constructing a new typed ticket-level model.

WHY_NOT_SHORTLIST_3: H06 is not selected first because the research-information-gain criterion favors H09's conditional signal question over a geometry-first operator whose success need not imply predictive edge.

WHAT_NEW_INFORMATION_IT_TESTS: Whether a preregistered negative signal has incremental value only when an independently frozen positive selector and causal context jointly activate suppression, after holding candidate universe, ticket budget, and suppression count fixed.

WHAT_NEGATIVE_RESULT_WOULD_RULE_OUT: The exact frozen positive-selector × negative-signal × condition × suppression-action interaction under the fixed Level-1 population, budget, endpoint, and matched-random comparator. It would not rule out all negative information, all conditional models, or alternate untested pairs.

WHAT_POSITIVE_RESULT_WOULD_JUSTIFY: Advancement only to a separately authorized Level-2 nested blocked replay with exclusion-only, unconditional-negative, conditional-negative, positive-only, and matched-random controls. It would not justify Level 2 automatically, Cohort V3 creation, prospective claims, production promotion, or betting use.

DISCOVERY_VALUE: HIGH — discovery readiness 5/5; pre-existing information-gain score 4/5; a scoped negative result is decision-useful.

DATA_READINESS: `READY_FOR_HISTORICAL_EXPERIMENT`; `PREPARATION=MODERATE` for the frozen component tuple and paired comparator contract.

HISTORICAL_TEST_COST: LOW–MEDIUM for exactly one positive selector, one negative signal, one condition, and one suppression intensity.

FORWARD_READINESS: `READY_WITH_MEDIUM_ENGINEERING`; forward readiness 2/5; enablement cost 3/5; scope M. Forward readiness is supporting feasibility only and did not drive selection.

EXPECTED_RESEARCH_DEPTH: LEVEL_1_FAST_FALSIFICATION_ONLY

TRACK_B_EXISTING_SPEC_LOCATOR: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_TOP10_TRACK_B_EXPERIMENT_SPECS_R1.md`, `## H09 — CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION`, lines 449–502; draft task ID `B649_TRACK_B_H09_CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION_DRAFT_R1`.

TRACK_B_SPEC_STATUS: NEEDS_MINIMAL_ADAPTATION

REQUIRED_MINIMAL_SPEC_ADAPTATION:

1. Before any outer outcome is read, bind exact values for `positive_selector_version`, `negative_signal_version`, one condition, suppression intensity/removal count, candidate universe, ticket budget, primary paired endpoint, and matched-random seed schedule.
2. Add a binding provenance rule that the positive selector is selected independently of H09 outcomes; H01's post-hoc exploratory winner and any retuned H07 detector/window/response are forbidden rescue inputs.
3. Add the sealed H01/H03/H07 task IDs and payload hashes to the context ledger as `EXECUTED_NOT_ADVANCED`; they remove only their exact hypotheses and do not alter H09's comparator family, pass/fail gate, or Level-1 depth.

Do not write or execute the adapted Track B worker prompt in this decision task.

## 6. Non-interference and next action

COHORT_V2_RELATIONSHIP: NONE

The current frozen Horizon Minimax prospective Cohort V2 line is independent. H01, H03, H07, and H09 have `NO_IMPACT_ON_COHORT_V2`.

TRACK_A_INTERFERENCE: NONE

TRACK_C_INTERFERENCE: NONE

REPO_MUTATION: NONE

DB_MUTATION: NONE

SEALED_TASK_DATA_MUTATION: NONE

COHORT_V2_MUTATION: NONE

TRACK_A_MUTATION: NONE

TRACK_C_MUTATION: NONE

TRACK_B_RESULT_MUTATION: NONE

EXTERNAL_SEARCH: NOT RUN

EXPERIMENT_EXECUTION: NOT RUN

LEVEL_2_AUTHORIZATION: NOT AUTHORIZED

BLOCKERS: NONE

NEXT: Send exactly one selected hypothesis — display H09 / canonical H21 `CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION` — to Track B for Level-1 historical fast falsification. Do not execute multiple hypotheses concurrently from this decision.

END
