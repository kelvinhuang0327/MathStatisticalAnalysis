# B649 Track D External Research Frontier R1

`TASK_ID: B649_TRACK_D_EXTERNAL_RESEARCH_FRONTIER_EXPANSION_R1`

`STATUS: COMPLETE_DISCOVERY_AND_SPECIFICATION_ONLY`

INTENT: current Track D authority contains 28 internally audited hypotheses and no external frontier artifacts; the task expects a provenance-preserving external discovery frontier with targeted 28/133 collision checks and fast-falsification specs; the opened Packet says create exactly ten repo-external artifacts without repo, DB, sealed-root, H01, or other Track D mutation.

## Executive result

The external scan reviewed 40 meaningful primary or idea-generating sources: 17 GitHub repositories, 19 papers/preprints, and 4 official technical documentation pages. It yielded 43 raw method ideas, abstracted and deduplicated into 27 canonical predictive hypotheses. Semantic collision checking against the existing 28 found:

- 12 genuinely new hypotheses;
- 4 extensions of existing hypotheses;
- 5 mechanistically explicit new combinations of existing hypotheses;
- 5 subcases already covered by the current surface; and
- 1 exact existing-hypothesis match: DPP diversity selection alone is H14.

The proposed discovery frontier therefore retains 21 external survivors and preserves all 28 existing open hypotheses, for a proposed total of 49. This is a proposal only; it does not create a canonical Cohort V2 and does not alter any Track D authority.

No external method was executed. No external efficacy claim was locally validated. All efficacy-related source statements remain `EXTERNAL_UNVERIFIED_CLAIM`, and all local validation states are `NOT_RUN`.

## Authority and reproducibility pins

### Current workspace identity

- Repository: `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis`
- Branch observed at preflight: `codex/b649-horizon-minimax-target-native-migration-r1`
- HEAD observed at preflight: `fc720ea8965faf95021a59d3fe3dae61ae3ef6c3`
- Tree observed at preflight: `64474415e7c4a34abd190b32d7a2e8a2a47d02f3`
- Initial repository status: clean

### Required internal inputs

| Input | Verified SHA-256 |
|---|---|
| `B649_TRACK_D_RESEARCH_SURFACE_R1.md` | `26add8e34cb259cffdd54c6cd8f91373980ffe7c2277b17b2afaca8c936c8859` |
| `B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_R1.md` | `6758482663fd46f14f86a293f0eef1a2bc77ff3186931267c5197f8cac87287b` |
| `B649_TRACK_D_REMAINING18_DEEP_AUDIT_R1.md` | `03f7b603ebd700beef05a035608dc61f40ba64db2f6daba345ec0cbe4099fe7e` |
| `B649_TRACK_D_WHAT_WE_HAVE_NOT_TRIED_R1.md` | `73107eded714e3bb28bfec21b73494923c0f94735ff581d30112a73eb2acfc05` |

### Historical catalog pin

- Historical commit: `2db4da27aee716805c393eb9c7dd41aff8e9527e`
- Historical tree: `cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c`
- Catalog path: `src/lottolab/strategies/data/biglotto_full_strategy_catalog_v1.json`
- Git blob: `fe93150e002bd7217be54501fdc9d390f81f79db`
- Raw blob SHA-256: `e604a038622fa9476aa86b33cd8068287664ec49cd5a27c81996ecb59a88dfbf`
- Catalog-declared SHA-256: `9e2d9f6c3cffbfe9867d4aaafbf8c9315922503fc0b806dfc84627699e0d82e3`
- Inspection mechanism: read-only `git cat-file`, `git ls-tree`, and existing sealed audit artifacts; the shared worktree was not switched or moved.

## Scope and collision standard

The scan did not treat a library name or model family as a hypothesis. Every raw idea was normalized to:

`INFORMATION_SET + TRANSFORMATION + TARGET + TEMPORAL_RULE + SELECTION_OR_GATING`

The 28-way collision test compared those semantics, not labels such as “Bayesian”, “graph”, or “Transformer”. The targeted 133-strategy check was performed only after external deduplication. Each retained hypothesis has five nearest historical identities with one of `EXACT`, `STRONG_OVERLAP`, `FAMILY_ONLY`, or `NO_MEANINGFUL_OVERLAP` and an explicit basis. No survivor has an `EXACT` historical-strategy match.

## Search coverage

The registry covers every required family. One source can support more than one family; counts below therefore are not additive.

| Required family | Representative primary sources | Resulting hypotheses or collision evidence |
|---|---|---|
| A. Sequential/time-series | River; BOCPD; Matrix Profile; NVAR | EH01; EH05; EH07; EH15; EH19 |
| B. Information theory | transfer entropy; CTW; permutation entropy | EH02; EH04; EH10 |
| C. Higher-order dependence | TensorLy; vine copulas; JIDT | EH02; EH09; EH24; EH26 |
| D. Meta-learning/selection | DESlib; River; residual tensor factors | EH09; EH15; EH20 |
| E. Ranking/probability | MAPIE; conformal risk control | EH05; EH13; EH16; EH23 |
| F. Anomaly/rare state | STUMPY; Alibi Detect; MMD; density ratio; optimal transport | EH01; EH05; EH11; EH12; EH14 |
| G. Graph/structural | JIDT; giotto-tda; existing graph audit | EH02; EH08; targeted collision evidence |
| H. Combinatorial/portfolio | DPPy; calibrated-probability combination | EH16; EH21 |
| I. Bayesian/stochastic | BOCPD; Hawkes/tick; CTW | EH04; EH06; EH17; EH19 |
| J. Neural/representation | ReservoirPy; TS2Vec; lottery repositories as low-confidence idea sources | EH07; EH22; EH25 |
| K. Nonlinear dynamics | recurrence quantification; persistent homology; permutation entropy | EH03; EH08; EH10 |
| L. Statistical testing | MMD; scan statistics; e-processes | EH11; EH14; EH18; EH27 |
| M. Negative/exclusion | conformal abstention; e-process suspension; scan-triggered fallback | EH13; EH18; EH27 |
| N. Objective redesign | allocation; abstention; M1+/M2+/M3+ portfolio targets | EH01; EH13–EH18; EH27 |
| Lottery-specific | two hobby prediction repositories; one dataset repository; one 6/49 entropy paper | Primarily collision evidence EH22 and narrowly scoped EH10 inspiration |

Lottery-specific hobby repositories were classified `LOW_CONFIDENCE_SOURCE`. They were useful only for idea discovery and for showing that static frequency/Markov/neural ensembles are already covered. No claimed win rate or predictive accuracy was imported as project evidence.

## Canonical inventory decision

| ID | Canonical hypothesis | Classification | Survivor | Tier |
|---|---|---:|---:|---:|
| EH01 | Matrix-profile motif/discord regime allocator | GENUINELY_NEW_HYPOTHESIS | YES | TIER_A |
| EH02 | Transfer-entropy directed lag graph | GENUINELY_NEW_HYPOTHESIS | YES | TIER_B |
| EH03 | Recurrence-quantification state gate | GENUINELY_NEW_HYPOTHESIS | YES | TIER_B |
| EH04 | Context-tree-weighted symbolic residual forecaster | GENUINELY_NEW_HYPOTHESIS | YES | TIER_A |
| EH05 | Density-ratio importance-weighted recalibration | GENUINELY_NEW_HYPOTHESIS | YES | TIER_B |
| EH06 | Hawkes excitation/inhibition residual scorer | GENUINELY_NEW_HYPOTHESIS | YES | TIER_E |
| EH07 | NVAR/reservoir causal residual meta-feature | GENUINELY_NEW_HYPOTHESIS | YES | TIER_E |
| EH08 | Persistent-homology rolling structure gate | GENUINELY_NEW_HYPOTHESIS | YES | TIER_E |
| EH09 | Strategy×draw×metric tensor-factor residual gate | GENUINELY_NEW_HYPOTHESIS | YES | TIER_B |
| EH10 | Permutation-entropy ordinal state gate | EXTENSION_OF_EXISTING | YES | TIER_A |
| EH11 | MMD joint-distribution shift allocator | EXTENSION_OF_EXISTING | YES | TIER_A |
| EH12 | Wasserstein-window shift allocator | EXTENSION_OF_EXISTING | YES | TIER_A |
| EH13 | Conformal set-size/coverage abstention | COMBINATION_OF_EXISTING | YES | TIER_C |
| EH14 | Context-conditioned MMD drift gate | COMBINATION_OF_EXISTING | YES | TIER_B |
| EH15 | Changepoint-triggered meta-selection | COMBINATION_OF_EXISTING | YES | TIER_C |
| EH16 | Calibrated-probability × DPP portfolio | COMBINATION_OF_EXISTING | YES | TIER_C |
| EH17 | State-space posterior × multiwindow disagreement | COMBINATION_OF_EXISTING | YES | TIER_C |
| EH18 | E-process anytime-valid promotion/abstention gate | EXTENSION_OF_EXISTING | YES | TIER_A |
| EH19 | BOCPD run-length gate | SUBCASE_OF_EXISTING | NO | N/A |
| EH20 | DES local-competence selector | SUBCASE_OF_EXISTING | NO | N/A |
| EH21 | DPP diversity portfolio alone | EXACT_EXISTING_HYPOTHESIS | NO | N/A |
| EH22 | Static lottery neural/Markov ensemble | SUBCASE_OF_EXISTING | NO | N/A |
| EH23 | Conformal calibration alone | SUBCASE_OF_EXISTING | NO | N/A |
| EH24 | Tensor decomposition of pair/triple co-occurrence | SUBCASE_OF_EXISTING | NO | N/A |
| EH25 | TS2Vec causal residual embedding | GENUINELY_NEW_HYPOTHESIS | YES | TIER_D |
| EH26 | Stationary vine-copula residual dependence | GENUINELY_NEW_HYPOTHESIS | YES | TIER_E |
| EH27 | Sparse subset-scan conditional-edge gate | GENUINELY_NEW_HYPOTHESIS | YES | TIER_B |

The “subcase” decisions are deliberately retained in the inventory and collision matrix. This prevents future external scans from repeatedly rediscovering the same covered methods.

## Top 10 new external hypotheses

These ten are selected from the 12 genuinely new hypotheses, balancing information gain and early falsifiability. EH07 and EH08 remain retained as high-orthogonality long shots rather than being padded into the main ten.

1. **EH01 — Matrix-profile motif/discord regime allocator.** Tests whether causal analogue support is more useful than a generic change/anomaly alarm.
2. **EH04 — Context-tree-weighted symbolic residual forecaster.** Provides a cheap variable-memory control against fixed-order Markov ideas.
3. **EH05 — Density-ratio importance-weighted recalibration.** Directly tests covariate-shift adaptation with an effective-sample-size safety fallback.
4. **EH02 — Transfer-entropy directed lag graph.** Separates directional conditional information flow from ordinary co-occurrence.
5. **EH09 — Strategy×draw×metric tensor-factor residual gate.** Tests multiway residual interactions that flat stacking cannot encode explicitly.
6. **EH03 — Recurrence-quantification state gate.** Introduces recurrence geometry as a state descriptor with simple component controls.
7. **EH27 — Sparse subset-scan conditional-edge gate.** Targets sparse coordinated effects that a global null may hide.
8. **EH06 — Hawkes excitation/inhibition residual scorer.** Tests an event-history mechanism absent from the current surface.
9. **EH25 — TS2Vec causal residual embedding.** Tests self-supervised residual representation rather than another supervised neural predictor.
10. **EH26 — Stationary vine-copula residual dependence.** Separates calibrated marginals from conditional higher-order and tail dependence.

## Top 5 cheap fast falsifications

1. **EH10 — Permutation-entropy ordinal state gate:** fixed orders and windows; compare with Shannon entropy and variance.
2. **EH04 — CTW symbolic residual forecaster:** compare prequential code/log loss with IID and fixed-order Markov controls.
3. **EH01 — Matrix-profile allocator:** one fixed window; compare with scalar H19/H20 gates and ungated allocation.
4. **EH15 — Changepoint-triggered meta-selection:** one detector × one horizon/eligibility action with a 2×2 ablation.
5. **EH18 — E-process promotion/abstention gate:** validate null calibration and optional-stopping safety before real monitoring.

## Top 5 high-orthogonality long shots

1. **EH08 — Persistent-homology rolling structure gate.** Maximum representation orthogonality; high scale-selection risk.
2. **EH06 — Hawkes excitation/inhibition residual scorer.** New event-time mechanism; stability and identifiability risk.
3. **EH25 — TS2Vec causal residual embedding.** Strong representation novelty; substantial compute and leakage burden.
4. **EH26 — Stationary vine-copula residual dependence.** New joint-tail mechanism; structure-selection risk.
5. **EH07 — NVAR/reservoir causal residual meta-feature.** Low-capacity nonlinear dynamics; seed and regularization sensitivity.

## Top 5 external methods already covered

1. **EH21 — DPP diversity portfolio alone → H14 exact.** DPP/submodular portfolio selection is already an explicit open hypothesis.
2. **EH19 — BOCPD run-length gate → H19 subcase.** BOCPD is a concrete changepoint allocator implementation, not a new hypothesis.
3. **EH20 — DES local-competence selection → H01/H03 subcase.** Dynamic selection is contained by residual gating/mixture-of-experts semantics.
4. **EH22 — Static lottery neural/Markov ensemble → H03/H23/H24/H25 subcase.** A source-specific model bundle adds no new causal mechanism.
5. **EH23 — Conformal calibration alone → H07/H09 subcase.** Calibration becomes a survivor only when coupled to the explicit abstention action in EH13.

## Combination hypotheses retained without combinatorial explosion

Five combinations survived because each has a clear mechanism, causal design, and testable output:

- EH13: calibrated probability/uncertainty × conformal set-size abstention;
- EH14: regime/context × MMD joint drift;
- EH15: changepoint × residual meta-selection;
- EH16: calibrated per-number probability × DPP ticket portfolio;
- EH17: state-space posterior × multi-window disagreement.

Other possible cross-products were not enumerated. Component novelty alone was insufficient.

## Targeted collision result against the historical 133

The pinned catalog was inspected read-only, and the prior sealed collision artifacts were used to preserve canonical strategy semantics. The survivor collision file contains exactly five nearest historical identities for each of the 21 survivors: 105 comparisons total.

- `EXACT`: 0
- `STRONG_OVERLAP`: component or target overlap, never all semantic dimensions
- `FAMILY_ONLY`: same broad family without the proposed transformation/target/gate
- `NO_MEANINGFUL_OVERLAP`: generic prediction/evaluation similarity only

No family-level similarity was upgraded to an exact match. The most common strong overlaps were expected: Markov methods near EH04, graph/co-occurrence methods near EH02/EH06/EH26, ensemble methods near EH09/EH13/EH15, and portfolio methods near EH16. Each retained hypothesis still differs on at least one load-bearing semantic dimension.

## Fast-falsification queue

All 21 survivors have a specification in `B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md`. Each specification includes the required source inspiration, novelty basis, closest internal hypotheses and strategies, minimum data, derived features, target, comparator, causal temporal design, leakage guard, cost, success/failure signals, and next action.

No test was run. The specifications intentionally prefer small component ablations and proper scoring or paired-loss targets before ticket-level claims. Expensive methods are not ranked highly merely for complexity.

## Claim-safety and lottery-source handling

- Every source row preserves direct URL, access date, method abstraction, and reproducibility status.
- All external efficacy findings or repository claims are tagged `EXTERNAL_UNVERIFIED_CLAIM`.
- `LOCAL_VALIDATION_STATUS` is `NOT_RUN` for every external source and hypothesis.
- The project does not adopt a source’s reported accuracy, win rate, return, or forecasting claim.
- S37 and S38 are low-confidence hobby repositories and support idea discovery/collision only.
- S39 is an external dataset reference and was not used to replace local historical authority.
- S40 is a lottery-specific primary paper. Its empirical results are not locally reproduced and are not treated as B649 evidence.

## Validation checklist

| Requirement | Result |
|---|---|
| Meaningful external sources ≥ 20 | PASS — 40 |
| GitHub repositories ≥ 8 | PASS — 17 |
| Papers/preprints ≥ 8 | PASS — 19 |
| Other primary technical sources ≥ 4 | PASS — 4 official documentation pages |
| Required families A–N covered | PASS |
| Lottery-specific sources included and claim-safe | PASS |
| Source claims retain provenance | PASS |
| Performance claims external/unverified | PASS |
| Existing 28 preserved | PASS — 28/28 copied unchanged into proposed frontier |
| No false exact match from family similarity | PASS |
| Every survivor has a canonical definition | PASS — 21/21 |
| Every survivor has top-5 historical neighbors | PASS — 21×5 |
| Every survivor has a fast-falsification spec | PASS — 21/21 |
| Proposed tests require no future information | PASS by specification; execution NOT_RUN |
| Repo mutation | NONE |
| DB mutation | NONE |
| Sealed-root mutation | NONE |
| Track B H01 interference | NONE |
| Other Track D task interference | NONE |
| External code execution/package installation | NONE |
| Checksum replay | PASS — replayed after sealing against the nine non-self-referential artifact entries |

## Limitations and blockers

- `BLOCKERS: NONE` for the requested discovery, abstraction, collision, and specification deliverables.
- Empirical validation is intentionally deferred; it was prohibited by this task.
- Source quality is heterogeneous. The inventory uses primary papers, official documentation, and official repositories for load-bearing method definitions; low-confidence lottery repositories do not support efficacy claims.
- A targeted top-five search is not a full new 21×133 re-audit. That is consistent with the Packet and builds on the existing sealed 133 and 28 collision authorities.
- “Genuinely new” means semantically absent from the reviewed 28 and targeted historical neighbors, not globally unprecedented in statistics or machine learning.
- Proposed tiers and priority scores are discovery ordering, not production priority or evidence of predictive value.

## Proposed next step

Merge the 21 survivors with the 28-item research frontier only as a proposed discovery queue. Execute later through separately authorized Track B packets, beginning with the cheapest high-information falsifications and preserving strict nested temporal controls.

## Output set

1. `B649_TRACK_D_EXTERNAL_RESEARCH_FRONTIER_R1.md`
2. `B649_TRACK_D_EXTERNAL_SOURCE_REGISTRY_R1.csv`
3. `B649_TRACK_D_EXTERNAL_HYPOTHESIS_INVENTORY_R1.csv`
4. `B649_TRACK_D_EXTERNAL_VS_EXISTING28_MATRIX_R1.csv`
5. `B649_TRACK_D_EXTERNAL_SURVIVOR_133_COLLISION_R1.csv`
6. `B649_TRACK_D_EXTERNAL_FAST_FALSIFICATION_SPECS_R1.md`
7. `B649_TRACK_D_PROPOSED_RESEARCH_FRONTIER_V2_R1.csv`
8. `B649_TRACK_D_EXTERNAL_PRIORITY_RANKING_R1.csv`
9. `B649_TRACK_D_EXTERNAL_FRONTIER_MANIFEST_R1.json`
10. `B649_TRACK_D_EXTERNAL_FRONTIER_SHA256SUMS_R1.txt`

`EXTERNAL_CLAIMS_LOCALLY_VALIDATED: 0`

`REPO_MUTATION: NONE`

`DB_MUTATION: NONE`

`SEALED_TASK_DATA_MUTATION: NONE`

`TRACK_B_H01_INTERFERENCE: NONE`

`OTHER_TRACK_D_INTERFERENCE: NONE`
