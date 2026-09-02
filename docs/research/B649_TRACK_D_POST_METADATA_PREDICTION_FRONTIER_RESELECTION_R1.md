# B649 Track D — Post-Metadata Prediction Frontier Reselection R1

TASK_ID: B649_TRACK_D_POST_METADATA_PREDICTION_FRONTIER_RESELECTION_R1  
STATUS: COMPLETE — EXACTLY_ONE_DIRECTION_SELECTED  
MODE: READ_ONLY_RESEARCH_DECISION  

No experiment was run. No Cohort V2 prospective outcome was used. Predictive value of every candidate below remains `[Unknown]` until a separately authorized historical experiment.

EVIDENCE_BASIS: `[Confirmed]` `TRACK_D_CROSS_LOTTERY_HIGHER_ORDER_SYNTHESIS_AND_NEXT_DIRECTION_R1.md`; `B649_TRACK_D_CROSS_EXPERIMENT_WEAK_SIGNAL_META_MINING_R1.md`; `B649_TRACK_D_INFORMATION_FAMILY_GUIDED_NEXT_DIRECTION_R1.md`; `B649_TRACK_D_CONCESSION_PROTOCOL_ERA_MECHANISM_FEASIBILITY_R1.md`; and `.task-data/B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1/{report.md,missing_information_candidates.csv}`.

## A_TO_E_COMPARISON

| OPTION | RANK | DECISION |
|---|---:|---|
| A. DIFFERENT_TARGET_REPRESENTATION | 2 | Best no-new-data fallback: direct legal-set comparison is better aligned to M2+/M3+ than absolute Top-6, but it cannot add raw information and remains exposed to the same chronological-transfer failure. |
| B. NEW_STRATEGY_GENERATION_MECHANISM | 4 | A joint unordered-set generator would be new, but without a new input it still mines the same draw-history substrate whose low-order structure and prior learned mechanisms have failed. |
| C. CROSS_LOTTERY_NATIVE_PREDICTIVE_REPLICATION | 3 | Data-ready and high failure value, but no existing B649 mechanism has survived chronological holdout; replicate a concrete structured-set mechanism only as a fallback, not first. |
| D. EXTERNAL_ORTHOGONAL_INFORMATION | 1 | Strictly prior T539/P638 outcomes are a real, catalog-absent, betting-cutoff-safe source for B649. Individual-lottery uniformity does not establish cross-series conditional independence. |
| E. OTHER NEW SYNTHESIS | 5 | Combining a new source and a new target in the first test could be direct, but would confound failure attribution; stage it only after one component survives alone. |

## TOP_3_NEXT_DIRECTIONS

### 1

TITLE: CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_SINGLE_TICKET_PREDICTOR  
TYPE: D — EXTERNAL_ORTHOGONAL_INFORMATION  
NEW_INFORMATION_SOURCE: Completed T539 and P638 main-number draws with `foreign_draw_date < B649_target_date`; the production-source audit found this source in 0 of 69 B649 strategies. Same-day foreign draws are excluded.  
WHY_IT_COULD_IMPROVE_P_MATCH: Each lottery can be marginally uniform while cross-lottery lagged conditional dependence still exists. A standalone, low-capacity foreign-context scorer could expose a weak conditional shift and convert it directly into one legal B649 ticket, without consensus reranking, family weighting, portfolio geometry, or an era flag.  
DATA_READINESS: HIGH — verified read-only histories exist for cleaned B649, T539, and P638 zone 1, with draw dates and main numbers sufficient for strict as-of joins. No new ingestion is required.  
IMPLEMENTATION_COST: LOW–MEDIUM — one causal join, one fixed pool-size-normalized representation, one simple generator, one no-foreign comparator, and one date-permuted placebo.  
TRANSFER_POTENTIAL: HIGH — the same normalized contract can rotate the target lottery to T539 or P638 while preserving each game's pool/pick rules.

### 2

TITLE: STRUCTURED_CONTRASTIVE_LEGAL_SET_QUALITY_TARGET  
TYPE: A — DIFFERENT_TARGET_REPRESENTATION  
NEW_INFORMATION_SOURCE: No new raw source; new supervision comes from relative ordering of matched legal candidate sets by realized match depth, rather than six independent absolute-number labels.  
WHY_IT_COULD_IMPROVE_P_MATCH: It removes the objective mismatch between per-number ranking and the actual unordered-set M2+/M3+ endpoint, and can learn candidate-set interactions directly. The main risk is that representation cannot manufacture information absent from the underlying history.  
DATA_READINESS: HIGH — existing B649 draws and deterministic legal-ticket construction are sufficient; no Cohort V2 outcome is needed.  
IMPLEMENTATION_COST: MEDIUM — requires a frozen matched-negative protocol, a bounded set scorer, and chronological replay, but no new external pipeline.  
TRANSFER_POTENTIAL: HIGH — match-depth labels and legal-set constraints parameterize naturally to 5-of-39 and 6-of-38.

### 3

TITLE: T539_FIRST_NATIVE_REPLICATION_OF_STRUCTURED_SET_SCORING  
TYPE: C — CROSS_LOTTERY_NATIVE_PREDICTIVE_REPLICATION  
NEW_INFORMATION_SOURCE: A structurally different target population, T539 first and P638 zone 1 second; predictor inputs remain target-native strictly prior history.  
WHY_IT_COULD_IMPROVE_P_MATCH: T539's longer history and different game shape can reveal whether a structured-set target has population-level transfer that B649-specific searches missed. This is prediction replication with legal-ticket M2+/M3+ output, not another fairness test.  
DATA_READINESS: HIGH — the verified T539 and P638 historical tables and game contracts already exist.  
IMPLEMENTATION_COST: MEDIUM — reuse one frozen structured-set contract with lottery-native pool/pick parameters and no per-lottery retuning.  
TRANSFER_POTENTIAL: HIGH by design, but PRIOR EXPECTATION: LOW–MEDIUM because all three lotteries' existing marginal through quadruple diagnostics are null.

## SELECTION

NEXT_RESEARCH_DIRECTION = CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_SINGLE_TICKET_PREDICTOR

WHY_THIS_DIRECTION_NOW: `[Inferred]` It is the only data-ready candidate that changes the raw information set, has a direct one-ticket M2+/M3+ path, is strictly available before the betting cutoff, and is absent from the catalog. It tests a relationship not answered by within-lottery marginal/pair/triple/quadruple diagnostics. A null result is still valuable because it closes the highest-readiness missing information source before spending more on target-only model complexity.

NEW_INFORMATION_SOURCE: The most recent completed T539 and P638 zone-1 draws strictly earlier than each B649 target date, represented in a fixed pool-size-normalized form. This is historical foreign-lottery context, not equipment metadata, `year >= 2024`, post-cutoff data, payout/EV data, or a recombination of existing strategy outputs.

DISCOVERY_MODE: BOUNDED_LEVEL_1_HISTORICAL_DISCOVERY — preregister one fixed foreign-context representation and one low-capacity standalone one-ticket generator; compare against the identical no-foreign-input model and a date-permuted foreign-context placebo; use chronological development/validation/untouched holdout; perform no window, entropy, motif, consensus, family-weight, or portfolio search and no post-holdout rescue tuning.

DATA_TO_USE: Cleaned B649 historical main draws as targets; T539 `source_draws` and P638 zone-1 `draws` as foreign context; join only rows with `foreign_draw_date < B649_target_date`; exclude same-day rows, P638 zone 2, Cohort V2 prospective outcomes, equipment/ball metadata, payout fields, and all post-target information.

PRIMARY_SUCCESS_METRIC: Exposure-matched single-ticket paired uplift in chronological-holdout M2+ rate versus the locked no-foreign-input comparator; M3+ paired uplift is the mandatory depth confirmation and must not be negative. Report block stability and the matched-random comparator. Payout/EV is not a success metric.

STOP_OR_PIVOT: Stop after one frozen discovery pass and one untouched chronological holdout. Stop and do not rescue-tune if M2+ has no positive stable paired lift, M3+ degrades, or the date-permuted placebo matches/exceeds the real alignment. On failure, pivot to Direction 2 (`STRUCTURED_CONTRASTIVE_LEGAL_SET_QUALITY_TARGET`). On success, freeze the exact mechanism and open a separate T539/P638 native-transfer task; do not promote it directly to production.

NEXT_TASK_TRACK: TRACK_B  
NEXT_TASK_ID: B649_TRACK_B_CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_PREDICTION_LEVEL1_R1

## FINAL

TASK_ID: B649_TRACK_D_POST_METADATA_PREDICTION_FRONTIER_RESELECTION_R1  
STATUS: COMPLETE — EXACTLY_ONE_DIRECTION_SELECTED  
TOP_3_NEXT_DIRECTIONS: (1) CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_SINGLE_TICKET_PREDICTOR; (2) STRUCTURED_CONTRASTIVE_LEGAL_SET_QUALITY_TARGET; (3) T539_FIRST_NATIVE_REPLICATION_OF_STRUCTURED_SET_SCORING  
NEXT_RESEARCH_DIRECTION: CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_SINGLE_TICKET_PREDICTOR  
WHY_THIS_DIRECTION_NOW: Only Top-3 option with a verified data-ready, catalog-absent raw information source and a direct chronological single-ticket M2+/M3+ test.  
NEW_INFORMATION_SOURCE: Strictly prior completed T539/P638 zone-1 draw outcomes, used as B649 foreign-lottery context.  
DISCOVERY_MODE: BOUNDED_LEVEL_1_HISTORICAL_DISCOVERY  
DATA_TO_USE: Cleaned B649 targets plus strictly earlier T539/P638 main-number histories; no same-day foreign rows and no Cohort V2 prospective outcomes.  
PRIMARY_SUCCESS_METRIC: Paired chronological-holdout M2+ uplift; M3+ non-degradation/confirmation; no payout/EV substitution.  
STOP_OR_PIVOT: One frozen pass and one untouched holdout; stop on no stable M2+ lift, M3+ degradation, or placebo parity; then pivot to Direction 2.  
NEXT_TASK_TRACK: TRACK_B  
NEXT_TASK_ID: B649_TRACK_B_CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_PREDICTION_LEVEL1_R1  
REPO_MUTATION: NONE  
DB_MUTATION: NONE  
END
