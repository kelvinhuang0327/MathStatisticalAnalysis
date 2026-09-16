# B649 Track D Frontier V2 Successor Reselection After Residual Rerank R1

TASK_ID: B649_TRACK_D_FRONTIER_V2_SUCCESSOR_RESELECTION_AFTER_RESIDUAL_RERANK_R1  
STATUS: PASS  
MODE: READ_ONLY_RESEARCH_DIRECTION_DECISION  
CORE_OBJECTIVE: MAXIMIZE_PREDICTION_SUCCESS_RATE

## 1. Decision basis

LATEST_B_RESULT: CONSENSUS_PLUS_PAIRWISE_RESIDUAL_RERANK  
LATEST_B_DECISION: DO_NOT_ADVANCE

STATIC_CONSENSUS_M2_PLUS: 67/300 (22.33%)  
RESIDUAL_RERANKER_M2_PLUS: 56/300 (18.67%)  
DELTA_VS_CONSENSUS: -11/300 (-3.67 pp)  
POSITIVE_BLOCKS: 0/6  
SEARCH_CONFIGURATIONS: 2,592  
SEARCH_PERIOD_BEST_IMPROVEMENT: +24/720 M2+  
HELDOUT_RESULT: -11/300 M2+  
SEARCH_OVERFIT_SIGNAL: YES

[Confirmed] The completed Track B report and independent aggregation of its direct `heldout_results.csv`, `block_results.csv`, `ranking_diagnostics.csv`, and `search_results.csv` agree on these figures. The selected reranker changed 300/300 tickets, averaged 2.7367 replacements, removed 116 consensus numbers that later won, and promoted 93 eventual winners. The six 50-target M2+ deltas were -2, 0, -5, 0, -2, and -2.

[Confirmed] Static consensus remains the strongest observed held-out baseline. The complementarity-aware stack reached 21.67%, above the strongest single strategy at 18.33% and flat stack at 20.00%, but below static consensus at 22.33%. The residual reranker then used a richer same-surface correction and fell to 18.67% despite a favorable search result.

CURRENT_BOTTLENECK_INFERENCE: The current bottleneck appears more likely to be new or better predictive information than portfolio geometry or more aggressive reweighting of the same consensus signals.  
SUPPORTED_FOR_PRIORITIZATION: YES

[Inferred] This is a prioritization decision, not a theorem. Two successive transformations of the existing strategy-support surface failed to beat static consensus, and the more invasive transformation showed clear search-to-held-out reversal. The evidence supports buying new information before buying more weighting complexity. It does not establish that pairwise ranking, ensembling, or consensus improvement can never work.

## 2. Candidate comparison

The highest weights are on `NEW_INFORMATION_SOURCE` and `FAILURE_INFORMATION_VALUE`.

| Direction | New information | Ability to beat consensus | Orthogonality to prior failures | Data readiness | Cost | Search-friendly | Failure information value |
|---|---|---|---|---|---|---|---|
| EH04 — CTW symbolic residual forecaster | HIGH | HIGH | HIGH | HIGH | LOW | YES | HIGH |
| EH10 — permutation-entropy ordinal-state gate | HIGH | MEDIUM | HIGH | HIGH | LOW | YES | HIGH |
| EH01 — matrix-profile motif/discord allocator | HIGH | MEDIUM | HIGH | HIGH | LOW–MEDIUM | YES | MEDIUM–HIGH |
| EH02 — transfer-entropy directed-lag graph | HIGH | MEDIUM | HIGH | MEDIUM | MEDIUM | YES | MEDIUM |
| H08 — standalone per-number ranking loss | LOW / UNPROVEN | MEDIUM | LOW–MEDIUM | MEDIUM | MEDIUM | YES | MEDIUM |
| New temporal-information + consensus synthesis | HIGH | HIGH | HIGH | MEDIUM | MEDIUM | YES | MEDIUM |

H08_EVALUATION: The standalone H08 design is materially different in anchoring and target decomposition: it learns the full per-number order rather than a correction to frozen consensus. However, the current authorities do not establish a materially new predictive input, while its pairwise/listwise per-number objective overlaps the failed rerank family. H08 is therefore downgraded for the next unit of cost, not closed permanently. It should return only as a `NEW_GENERATION` with genuinely new inputs and a new evaluation design.

NEW_SYNTHESIS_EVALUATION: A future `STATIC_CONSENSUS + NEW_TEMPORAL_INFORMATION` synthesis is attractive, but selecting the clean EH04 information test first gives better failure attribution. A synthesis is an allowed downstream arm after EH04 demonstrates independent temporal signal; it is not a separate parallel direction now.

## 3. TOP_3_NEXT_DIRECTIONS

### 1

TITLE: EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER  
ORIGIN: EXISTING_FRONTIER_V2_EH04  
CORE_NEW_INFORMATION: Variable-order temporal context in strict-prior per-number appearance, gap, or rank symbol streams, summarized by CTW posterior predictive probability, excess code length versus IID, and context-posterior mass.  
WHY_IT_COULD_BEAT_STATIC_CONSENSUS: Static consensus aggregates cross-strategy support but does not represent variable-depth temporal dependencies. EH04 can supply a causal per-number score that is information-orthogonal to another transformation of the consensus vote.  
OVERLAP_WITH_FAILED_RESIDUAL_RERANK: LOW  
EXPECTED_INFORMATION_GAIN: HIGH  
DATA_READINESS: HIGH  
IMPLEMENTATION_COST: LOW  
SEARCH_FRIENDLY: YES

### 2

TITLE: EH10_PERMUTATION_ENTROPY_ORDINAL_STATE_GATE  
ORIGIN: EXISTING_FRONTIER_V2_EH10  
CORE_NEW_INFORMATION: A causal information-theoretic temporal state derived from ordinal-pattern complexity rather than static strategy votes.  
WHY_IT_COULD_BEAT_STATIC_CONSENSUS: A real ordinal-complexity state could identify periods in which consensus confidence should be accepted, attenuated, or replaced. It is cheap to falsify and highly orthogonal to the failed reranker.  
OVERLAP_WITH_FAILED_RESIDUAL_RERANK: NONE  
EXPECTED_INFORMATION_GAIN: HIGH  
DATA_READINESS: HIGH  
IMPLEMENTATION_COST: LOW  
SEARCH_FRIENDLY: YES

### 3

TITLE: EH01_MATRIX_PROFILE_MOTIF_DISCORD_REGIME_ALLOCATOR  
ORIGIN: EXISTING_FRONTIER_V2_EH01  
CORE_NEW_INFORMATION: Recurrent motifs and discords in temporal number/strategy sequences, providing a recurrence-based regime signal absent from static voting.  
WHY_IT_COULD_BEAT_STATIC_CONSENSUS: If past motif neighborhoods have repeatable next-draw behavior, their local evidence can identify when the consensus ranking is systematically incomplete.  
OVERLAP_WITH_FAILED_RESIDUAL_RERANK: NONE  
EXPECTED_INFORMATION_GAIN: MEDIUM  
DATA_READINESS: HIGH  
IMPLEMENTATION_COST: MEDIUM  
SEARCH_FRIENDLY: YES

## 4. Selected direction

NEXT_RESEARCH_DIRECTION: EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER  
ORIGIN: EXISTING_FRONTIER_V2_EH04

WHY_THIS_DIRECTION_NOW: EH04 is the best next marginal research investment because it combines a genuinely new temporal information source, a direct per-number prediction path, high historical data readiness, low implementation cost, and a clean falsification test against IID, trailing-frequency, and fixed-order Markov controls. It preserves static consensus as the comparator and optional downstream base without repeating an aggressive same-signal rerank.

WHAT_NEW_INFORMATION_IT_ADDS: Variable-length conditional structure in each number's strict-prior symbol history. The opened Frontier V2 spec requires prequential CTW, fold-local symbol bins and depth choice, and no full-history compression dictionary.

WHY_NOT_DIRECTION_2: EH10 is cheaper and equally orthogonal, but it first yields a global or ordinal state gate rather than a direct number-specific forecast. Its route to one-ticket M2+ is therefore more indirect and more dependent on a second allocation design.

WHY_NOT_DIRECTION_3: EH01 adds valuable motif/discord structure, but window length, distance, neighbor, and allocator choices create more search surface and weaker failure attribution. EH04 can first answer the narrower question: does variable-order temporal context predict number-level outcomes better than simple temporal controls?

WHAT_FAILURE_WOULD_RULE_OUT: Failure to improve outer prequential code length/log loss over IID, trailing frequency, and fixed-order Markov depths 1–3 would rule out this exact EH04 generation—its tested alphabets, depth caps, and CTW mechanism—as the next source of predictive information. A proper-loss gain that does not transfer to locked one-ticket M2+ would rule out using that signal for ticket selection. Neither result rules out all temporal methods.

WHAT_SUCCESS_WOULD_JUSTIFY: Stable outer-fold proper-loss improvement followed by a locked, equal-budget one-ticket M2+ gain over contemporaneous static consensus on genuinely untouched chronological data would justify a new-generation consensus-plus-CTW study and independent confirmation. It would not by itself justify operational adoption.

## 5. Minimal Track B handoff

NEXT_B_TASK_ID: B649_TRACK_B_EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER_DISCOVERY_R1

TITLE: EH04 Context-Tree-Weighted Symbolic Residual Forecaster Discovery

ORIGIN: EXISTING_FRONTIER_V2_EH04

RESEARCH_QUESTION: Does variable-order, strict-prior symbolic temporal context provide per-number predictive information that survives simple temporal controls and improves one-ticket M2+ over frozen static consensus?

DISCOVERY_MODE: YES

NEW_INFORMATION_SOURCE: Per-number variable-order temporal context from binary appearance, causal gap-bin, and causal rank-bin symbol streams; CTW posterior predictive probability and excess code length versus IID. Static consensus is a baseline and optional downstream base, not the source of the temporal signal.

SEARCH_SPACE: Predeclared bounded choices for symbol-stream family, fold-local symbolization/binning, maximum CTW depth, minimum context support, one simple probability calibration option, candidate K, and a bounded simple CTW/consensus blend arm. Include standalone CTW. Fix deterministic tie handling and one legal six-number ticket. Exclude pairwise/listwise residual reranking, portfolio geometry, unbounded feature additions, and post-evaluation rescue tuning.

DATA_TO_USE: All currently inspected historical targets, including targets `113000006–115000069`, are `DEVELOPMENT_DATA` only. Use expanding-window, strict-prior prequential folds; fit symbol edges, contexts, depth, and calibration inside each training fold. Do not use Cohort V2 prospective outcomes. Reserve a later chronological target stream proven disjoint from Cohort V2 and unavailable during locking for untouched evaluation.

EVALUATION_DESIGN: Stage 1 is nested expanding-window development evaluation. Select one configuration using only inner chronological folds, then test information gain on non-overlapping outer folds with per-number log loss, code length, calibration, and stability versus IID/uniform, trailing frequency, and fixed-order Markov depths 1–3. Stage 2 locks the full pipeline before any disjoint future outcomes are read and compares exactly one CTW-derived ticket with exactly one contemporaneous static-consensus ticket. For a 300-target evaluation, report six consecutive 50-target blocks. Existing exposed targets may support discovery but must never be labeled untouched confirmation.

PRIMARY_BASELINE: STATIC_CONSENSUS

OTHER_BASELINES: IID_UNIFORM; TRAILING_FREQUENCY; FIXED_ORDER_MARKOV_DEPTHS_1_TO_3; STRONGEST_SINGLE; PREVIOUS_FLAT_STACK; FAILED_RESIDUAL_RERANKER_REFERENCE_ONLY

PRIMARY_SUCCESS_METRIC: ONE_TICKET_M2_PLUS

STOP_OR_PIVOT: Stop EH04 if it fails to beat every simple temporal control on outer prequential log loss/code length with chronological stability, if the locked ticket method fails to improve contemporaneous static-consensus M2+, or if apparent gain requires high ticket churn, unbounded search, or post-evaluation tuning. For a 300-target untouched evaluation, require at least +6 M2+ targets and positive delta in at least 4/6 blocks before advancing. On failure, pivot to EH10; do not rescue EH04 or H08 on the exposed 300 targets.

EXPECTED_OUTPUT: One compact discovery report; one serialized locked EH04 configuration; complete inner-search and outer-prequential summaries; per-target probabilities and exactly one legal ticket per arm; overall/block M1+/M2+/M3+/M4+; calibration/code-length diagnostics; search-to-evaluation transfer; leakage/equal-budget checks; and one `ADVANCE`, `DO_NOT_ADVANCE`, or `AWAITING_DISJOINT_PROSPECTIVE_EVALUATION` decision.

## 6. Boundaries and uncertainty

COHORT_V2_PROSPECTIVE_DATA_USED: NO  
FRONTIER_V2_REGENERATED: NO  
PRIOR_B_EXPERIMENTS_RERUN: NO  
COLLISION_AUDIT_REDONE: NO  
EXTERNAL_SCAN_RUN: NO  
REPO_MUTATION: NONE  
DB_MUTATION: NONE

[Unknown] EH04's future M2+ performance and the calendar date on which a sufficiently large, Cohort-V2-disjoint chronological evaluation stream will exist.

COULD_NOT_VERIFY: Future/prospective predictive lift. The existing Frontier V2 external-method claims were not refreshed because this task forbids a new external scan; they are planning provenance, not efficacy evidence.

INTENT: existing authorities rank EH04 as unexecuted new temporal information and the latest residual reranker overfits and harms held-out M2+; the task expects exactly one successor direction and a minimal Track B handoff; the opened EH04 spec says use prequential CTW on fixed prior-only symbol streams and advance only if it beats IID/fixed-order controls before ticket-level testing.

BLOCKERS: NONE

NEXT: Send exactly `EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER` to Track B for implementation-first discovery.

END
