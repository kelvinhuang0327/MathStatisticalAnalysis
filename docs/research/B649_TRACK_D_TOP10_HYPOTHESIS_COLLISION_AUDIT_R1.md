# B649 Track D Top-10 Hypothesis Collision Audit R1

- TASK_ID: `B649_TRACK_D_TOP10_HYPOTHESIS_COLLISION_AUDIT_AND_EXPERIMENT_SPECS_R1`
- STATUS: `PASS`
- MODE: `LONG_RUNNING_READ_ONLY_RESEARCH`
- PINNED_HISTORICAL_HEAD: `2db4da27aee716805c393eb9c7dd41aff8e9527e`
- PINNED_TREE: `cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c`
- LIVE_WORKTREE_BRANCH_OBSERVED: `codex/b649-horizon-minimax-target-native-migration-r1`
- INPUT_REPORT: `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_RESEARCH_SURFACE_R1.md`
- INPUT_REPORT_SHA256: `26add8e34cb259cffdd54c6cd8f91373980ffe7c2277b17b2afaca8c936c8859`
- [實測] INPUT_REPORT_HASH_VERIFIED
- CHECKSUM_VALIDATION: `PASS` for 8 directly used sealed roots with SHA256SUMS checks
- RESEARCH_POSTURE: `WIDE_IN / STRICT_OUT`; no hypothesis is promoted, and historical negative evidence does not by itself close an open hypothesis.

## Executive conclusion

All ten hypotheses were compared against every one of the 133 historical identities. The deterministic semantic audit produced 1,330 rows: **0 exact matches, 92 strong component overlaps, 77 weak overlaps, 115 same-family/different-hypothesis relations, and 1,046 no-meaningful-overlap relations**. All ten remain open under the packet’s exact-match standard.

H02 needs a special qualification: its core fixed horizon-minimax producer was already directly tested in the sealed next-generation study **outside** the 133-identity population. It therefore remains open only as an independent-confirmation question; rerunning or repartitioning the same 1,957 targets is reproduction/stress evidence, not confirmation.

H01 remains the recommended first Track B experiment because the minimum rank-free design can be built entirely from sealed strategy×draw×ticket outcomes, hit depth, exact baselines, family labels, chronology, and derived pre-target overlap/residual features. Forward execution is a later and narrower capability gate.

## Authority and population boundary

| Population/capability | Count | Meaning |
|---|---:|---|
| Historical analyzable | 133 | Checksummed native ticket histories; discovery population |
| Current executable within historical | 51 | Runtime overlap, not automatic feature/adapter eligibility |
| Historical raw-only | 82 | Valid for sealed historical analysis; not forward runnable |
| Candidate-K direct within overlap | 7 | Number-level matrix authority; not equal to 51 or 133 |
| Frozen candidates | 40 | Prospective candidate cohort |
| Frozen forward-generatable | 3 | Current forward capability, not historical population |
| Frozen unavailable | 37 | 17 A plus 20 C unavailable under frozen evidence |

These sets are deliberately not conflated. The 133 are used for historical collision/discovery; every forward spec requires a separate producer-level preflight.

### Sealed roots read

- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_HIT_DEPTH_PROJECTION_R1` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_FINAL_133_MULTI_TICKET_RANKING_REVIEW_R1` — checksum: `NOT_RERUN; DIRECT_READ`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_133_STATISTICAL_ROBUSTNESS_FAMILY_REVIEW_R1` — checksum: `NOT_RERUN; DIRECT_READ`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_STRATEGY_K_HISTORICAL_MATRIX_AUTHORITY_R1` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROJECTION_R1` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_CANDIDATE_FREEZE_R1` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_FORWARD_OBSERVER_R4` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_NEXT_GENERATION_STRATEGY_RESEARCH_R1` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OFFICIAL_CAUSAL_REGIME_ANALYSIS_R1` — checksum: `NOT_RERUN; DIRECT_READ`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_R2_OVERNIGHT_NEGATIVE_SIGNAL_STRUCTURE_AND_ANTI_BIAS_DESIGN_R1` — checksum: `NOT_RERUN; DIRECT_READ`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_R2_FULL_UNIVERSE_PRIZE_AWARE_INFERENTIAL_VALIDATION_R1` — checksum: `PASS`
- `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_R2_RAW_FOUNDATION_CANONICAL_METRICS_REBUILD_R1` — checksum: `NOT_RERUN; DIRECT_READ`

### Pinned catalog and source limitation

- Pinned catalog: `/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/src/lottolab/strategies/data/biglotto_full_strategy_catalog_v1.json` via committed head `2db4da27aee716805c393eb9c7dd41aff8e9527e`; 221 records, with all 133 historical identities joined.
- All 133 joined records carry source path/commit/blob/hash, method family, Candidate-K, native-ticket, combination-count, order/duplicate semantics, and reproduction status.
- `[Unknown]` The frozen source commit `49a25effa62fc24f40789c16be6f11bdfb41a4a9` and its source blobs are not present in either local object database. No network fetch was authorized. Collision labels therefore rely on committed catalog semantics plus checksummed raw behavior and sealed report conclusions, not filename alone and not unavailable source bodies.

## Raw-foundation integrity and chronology audit

- 221 unique identity-ledger rows: 135 BACKTESTED, 74 CLOSED, 12 aliases.
- Historical coverage: 133 unique strategies and 2,590,280 declared ticket rows.
- Stream verification: 133/133 raw files, 2,590,280 actual rows, 2,590,280 unique `(strategy_id,target_draw_id,ticket_position)` keys, zero duplicates.
- Required 23-field schema: zero missing/null required values; zero illegal predicted tickets; zero illegal actual main/special results; zero hit-count inconsistencies; zero ticket-position errors.
- Replay provenance: 2,584,573 exact-preserved rows and 5,707 recovered-frozen-native rows.
- Chronology caveat: 2,831 recovered rows across `research_cluster_enhancements` (2,721), `backtest_radical_strategy` (86), and `test_cluster_cover` (24) have source-local numeric cutoff IDs that are not comparable to official target IDs. Every such row has `historical_input_cutoff_date < target_draw_date`. Future experiments must compare dates or the canonical chronological index—not raw numeric IDs—for those records.
- ATTEMPT_LEDGER: the first streaming check incorrectly joined coverage directly to a nonexistent raw-file column and read zero rows (`HARNESS_JOIN_MISSING`). It was rejected and rerun with the identity-ledger file mapping; the corrected result is the one reported above.

## Collision classification standard

An `EXACT_HYPOTHESIS_MATCH` requires high agreement on predictive information set, transformation, target, gating logic, composition semantics, and temporal semantics. A shared filename token, method family, graph/frequency/Bayesian primitive, or portfolio output is insufficient. `STRONG_COMPONENT_OVERLAP` means a core mechanism is present but at least one hypothesis-defining dimension is absent. `WEAK_COMPONENT_OVERLAP` means only a primitive/comparator/output behavior overlaps. `UNKNOWN` was not needed because the committed semantic catalog and sealed behavioral evidence were sufficient for these bounded labels, despite source-body unavailability.

The rule set is deterministic: fixed pinned population sorted by canonical identity; fixed curated strong/weak semantic sets; family fallback only after strong/weak checks; otherwise no meaningful overlap. No target outcomes or performance ranks enter collision labeling.

## Alias mapping to the prior report

| Packet ID | Prior-report canonical ID | Canonical wording |
|---|---|---|
| H01 | H01 | `CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR` |
| H02 | H27 | `HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION` |
| H03 | H04 | `MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT` |
| H04 | H07 | `CALIBRATED_PER_NUMBER_PROBABILITIES` |
| H05 | H10 | `DIRECT_TICKET_LEVEL_RESIDUAL_SCORING` |
| H06 | H14 | `DPP_SUBMODULAR_PORTFOLIO_SELECTION` |
| H07 | H19 | `CHANGE_POINT_TRIGGERED_ALLOCATION` |
| H08 | H12 | `TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS` |
| H09 | H21 | `CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION` |
| H10 | H17 | `DYNAMIC_BAYESIAN_STATE_SPACE_MODELING` |

## Collision summary

| ID | Exact | Strong | Weak | Same family / different | No meaningful | Unknown | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| H01 | 0 | 12 | 10 | 7 | 104 | 0 | OPEN |
| H02 | 0 | 9 | 7 | 17 | 100 | 0 | OPEN |
| H03 | 0 | 11 | 4 | 15 | 103 | 0 | OPEN |
| H04 | 0 | 1 | 8 | 10 | 114 | 0 | OPEN |
| H05 | 0 | 11 | 9 | 11 | 102 | 0 | OPEN |
| H06 | 0 | 12 | 8 | 10 | 103 | 0 | OPEN |
| H07 | 0 | 8 | 8 | 15 | 102 | 0 | OPEN |
| H08 | 0 | 11 | 7 | 0 | 115 | 0 | OPEN |
| H09 | 0 | 10 | 8 | 5 | 110 | 0 | OPEN |
| H10 | 0 | 7 | 8 | 25 | 93 | 0 | OPEN |

## H01 — CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR

1. **WHAT_IS_NEW?** A causal gate chooses or weights strategy outputs using only lagged, baseline-residual performance, family disagreement, regime descriptors, and portfolio overlap; it does not reuse an internal strategy rank.

2. **WHAT_ALREADY_EXISTS?** Ensembles, consensus, optimizer, and diversification methods exist. None of the 133 is an exact cross-strategy residual-gated selector with the same causal information set, target, gate, and two-population design.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__advanced_methods_benchmark__87ee0d15033c` (ML_like); `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` (utility); `legacy_biglotto__backtest_biglotto_7bet_optimized__2881417de6f8` (utility); `legacy_biglotto__biglotto_diversified_ensemble__36dbfc14b360` (ML_like); `legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d` (ML_like); `legacy_biglotto__feature_discovery_and_retrospective__e2ea8b18945d` (frequency); `legacy_biglotto__hybrid_integration_benchmark__5789ca885422` (report); `legacy_biglotto__optimized_ensemble__e05e0fde22d7` (ML_like); `legacy_biglotto__predict_6expert__ff7c2b15f371` (ML_like); `legacy_biglotto__predict_consensus_ensemble__3ceb975a355c` (ML_like).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 12.

6. **REQUIRED_INPUT_DATA:** 133-strategy raw ticket outcomes; Hit Depth FULL/750/300/50; exact same-native-multiplicity baselines; family labels; draw chronology; pre-target regime descriptors; portfolio-overlap features.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Lagged per-strategy residuals, stability/dispersion, family disagreement, causal overlap graph, and fold-local gate features. No source-internal number rank is required.

9. **TARGET_OUTPUT:** Primary: fixed-budget next-draw OFFICIAL_ANY_PRIZE residual versus exact same-ticket-count random. Secondary: M2+, M3+, calibration of above-baseline probability; M4+ only descriptive because it is sparse.

10. **HISTORICAL_TEST_DESIGN:** Two stages: HISTORICAL_DISCOVERY_POPULATION=all 133 using native portfolio outcomes; FORWARD_ELIGIBLE_SUBSET=only identities passing current runtime/adapter preflight (51 is an upper bound, not automatic eligibility). Use nested expanding blocks and a frozen 5-ticket comparison where the 20-candidate authority supports it.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Expanding or rolling training with contiguous held-out draw blocks; every feature ends at target-1. Candidate experts and gate hyperparameters are selected in inner folds only.

12. **RANDOMNESS_REQUIREMENT:** Deterministic model/tie-break preferred. If stochastic learners are explored, predeclare seed list and aggregate across seeds; exact baseline simulation seeds must be fixed.

13. **LEAKAGE_RISKS:** Target result, future recalculated rank, post-target performance, full-history statistics containing target, hindsight thresholds, and expert selection using outer-test performance are forbidden.

14. **MULTIPLICITY_RISKS:** Winner’s curse across 133 experts, objectives, windows, model classes, and gates. Use family-level screening, nested selection, one primary endpoint, blocked outer folds, and multiplicity-adjusted secondary claims.

15. **FORWARD_EXECUTION_PATH:** Historical discovery may use all 133; a separate adapter/runtime preflight narrows the 51 currently executable identities and then the 3/40 frozen forward-generatable candidates. No assumption that all 51 can supply each feature.

16. **COMPUTE_COST:** Medium: rank-free artifact-first Level 1 is hours; nested all-133 Level 2 is moderate; broad model search is deferred.

17. **FAILURE_CRITERIA:** No reproducible out-of-block gain over exact baseline/equal-weight/frozen-static selectors; gains vanish under family holdout; unstable expert concentration; or any leakage/control failure.

18. **SUCCESS_CRITERIA:** Predeclared primary endpoint improves in multiple outer blocks with stable denominator, positive uncertainty-aware residual, family-holdout persistence, and no dependence on target-containing features. This advances research only.

19. **SHOULD_TRACK_B_TEST?** YES — Track B first experiment.

20. **PRIORITY:** DISCOVERY #1; prospective readiness depends on adapter preflight.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: Artifact-only fixed-rule gate on lagged residual/stability over a predeclared small expert set; blocked holdout against exact random, equal-weight, and frozen-static selectors.
- LEVEL 2 — STANDARD HISTORICAL TEST: Nested expanding blocks over all 133 native portfolios; one primary any-prize residual, M2+/M3+ secondary; family-holdout sensitivity; separate current-runtime preflight.
- LEVEL 3 — DEEP EXPLORATION: Bounded model/gate family, regime interactions, seed stability, alternative objectives, and prospective protocol draft only if Level 2 advances.

### H01 required A–H findings

**A. Foundation sufficiency.** Yes. Raw Foundation R2 directly identifies strategy×draw×ticket outcome, and Hit Depth Projection R1 supplies strategy×draw/window hit-depth summaries with exact native-multiplicity baselines.

**B. Internal rank.** Not required. Construct labels/features from prior outcomes, native portfolios, family, regime, and overlap. Candidate A/C ranks may be used only in a separate explicitly named proxy experiment.

**C. Target comparison.**

| Target | Strength | Weakness | Recommendation |
|---|---|---|---|
| Next-draw best strategy | Direct selector objective | Severe winner’s curse; unstable tie/cardinality | Exploratory only |
| Family winner | Reduces 133-way multiplicity | Coarse and family labels heterogeneous | Useful intermediate target |
| Strategy-above-baseline event | Stable binary/probabilistic gate | Baseline and ticket count must match | Good calibration target |
| M2+ | Dense, interpretable hit-depth | May reward many tickets without exact control | Secondary with exact baseline |
| M3+ | More decision-relevant | Sparser | Secondary confirmatory |
| M4+ | High depth | Very sparse/unstable | Descriptive only |
| Residual vs same-ticket-count baseline | Directly controls native multiplicity | Requires exact baseline discipline | Primary alongside any-prize |

**D. Allowed pre-target meta-features.** Trailing performance, 750/300/50 deltas, family disagreement, causal regime descriptors, portfolio overlap, and lagged residual structure are allowed when recomputed inside each fold.

**E. Forbidden features.** Target result, future recalculated rank, post-target performance, full-history statistics containing the target, hindsight-selected thresholds, or outer-test-selected experts.

**F. Two populations.** Use all 133 for historical discovery. Use the 51 current-executable overlap only as an upper-bound preflight set; producer-by-producer forward eligibility must be verified, and the frozen 3/40 figure is a different cohort capability boundary.

**G. Bias control.** Freeze candidate experts/features/primary endpoint; use nested blocked selection; screen/hold out families; compare equal/static/baseline selectors; adjust secondary families; report every attempted gate.

**H. Minimum experiment.** Yes: a rank-free, deterministic, fixed-rule gate can run entirely over sealed raw/Hit Depth authorities without repo, DB, observer, cohort, candidate-freeze, or production mutation.

## H02 — HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION

1. **WHAT_IS_NEW?** Independent confirmation of the fixed horizon-minimax producer: a number must remain acceptable across 30/120/FULL_PREFIX horizons and a two-ticket overlap constraint, rather than merely scoring well in one window.

2. **WHAT_ALREADY_EXISTS?** The sealed next-generation authority already directly tested b649_new_horizon_minimax_disagreement_r1 outside the 133: 1,957 eligible targets, horizons 30/120/FULL_PREFIX, two tickets, max overlap 2, deterministic ties; deltas versus exact 2-ticket random were +0.0136584 FULL, +0.0163878 LONG, +0.00238779 MID, +0.0190545 SHORT. Status remains FRESH_BOUNDED_PENDING.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` (utility); `legacy_biglotto__backtest_biglotto_7bet_optimized__2881417de6f8` (utility); `legacy_biglotto__backtest_diversified_3bet__03acff1d1bf7` (utility); `legacy_biglotto__research_variant_history__149648f9fffc` (zone); `legacy_biglotto__test_ces__78d17c530ab8` (utility); `legacy_biglotto__test_dms__b63442289bd5` (utility); `legacy_biglotto__test_greedy_optimizer__82df7f878ece` (utility); `legacy_biglotto__test_mwsc__ba37643d6a3b` (utility); `legacy_biglotto__verify_elite7_claim__937afa8d6133` (utility).

4. **EXACT_COLLISION_COUNT:** 0 within the 133. The sealed next-generation producer is a directly tested unit outside the 133, so H02 is not historically virgin.

5. **STRONG_OVERLAP_COUNT:** 9.

6. **REQUIRED_INPUT_DATA:** Draw chronology and pre-target 49-number frequencies at 30, 120, and full prefix; fixed producer parameters; exact two-ticket random baseline; untouched/reserved or prospective outcomes for confirmation.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Horizon-wise ranks/scores, per-number minimax score, disagreement, and fixed overlap-constrained ticket construction.

9. **TARGET_OUTPUT:** Predeclared two-ticket any-prize and M2+/M3+ deltas versus exact two-ticket random; confirmation must be on data not used by the 1,957-target evaluation.

10. **HISTORICAL_TEST_DESIGN:** Level 1 reproduces sealed results; Level 2 stress-tests contiguous blocks and parameter invariance but is not independent confirmation; Level 3 is separately authorized prospective shadow observation.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Strict prior history; preserved 1,957 targets may be partitioned for stability only. A genuinely untouched post-freeze sample is required for confirmatory language.

12. **RANDOMNESS_REQUIREMENT:** None in producer; number-ascending ties. Baseline Monte Carlo uses fixed disclosed seeds or exact combinatorial expectation.

13. **LEAKAGE_RISKS:** Calling reused historical targets “confirmation”; retuning horizons/overlap on the same 1,957; full-prefix including target; prospective backfill.

14. **MULTIPLICITY_RISKS:** Three shortlisted next-generation producers and multiple windows. Keep H02 parameters fixed and the confirmation endpoint singular.

15. **FORWARD_EXECUTION_PATH:** No post-freeze observation exists in R4 and no pinned new-producer adapter is available. Prospective execution requires separate Track B engineering and Owner authorization.

16. **COMPUTE_COST:** Low for reproduction/stability; elapsed-time high for genuine prospective confirmation.

17. **FAILURE_CRITERIA:** Reproduction mismatch; negative/unstable blocked performance; any parameter retuning after outcome inspection; or no untouched sample for a confirmatory claim.

18. **SUCCESS_CRITERIA:** Bit-for-bit reproduction plus stable historical stress behavior advances to a frozen prospective protocol; only untouched/prospective evidence can confirm.

19. **SHOULD_TRACK_B_TEST?** YES, but label historical work REPRODUCTION/STRESS, not confirmation.

20. **PRIORITY:** High information value; immediate confirmation readiness is limited by zero post-freeze outcomes.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: Recompute the sealed 1,957-target fixed producer and exact two-ticket deltas; require bit-for-bit parameter/ticket agreement.
- LEVEL 2 — STANDARD HISTORICAL TEST: Contiguous block and window stability using the same frozen producer; explicitly label as historical stress, not independent confirmation.
- LEVEL 3 — DEEP EXPLORATION: Separately authorized prospective shadow observation with frozen producer, no tuning, and a predeclared confirmation endpoint.

## H03 — MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT

1. **WHAT_IS_NEW?** The signal is change between windows—slope, acceleration, and cross-horizon disagreement—not the frequency level itself and not H02’s requirement that all horizons agree.

2. **WHAT_ALREADY_EXISTS?** Frequency, EWMA, multi-window, drift, and walk-forward strategies exist, but no 133 strategy targets the incremental predictive value of slope/acceleration/disagreement after controlling for window levels.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` (utility); `legacy_biglotto__backtest_biglotto_6bet_ewma__e1b5e100d254` (frequency); `legacy_biglotto__backtest_biglotto_7bet_optimized__2881417de6f8` (utility); `legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac` (frequency); `legacy_biglotto__feature_discovery_and_retrospective__e2ea8b18945d` (frequency); `legacy_biglotto__research_variant_history__149648f9fffc` (zone); `legacy_biglotto__test_ces__78d17c530ab8` (utility); `legacy_biglotto__test_dms__b63442289bd5` (utility); `legacy_biglotto__test_greedy_optimizer__82df7f878ece` (utility); `legacy_biglotto__test_mwsc__ba37643d6a3b` (utility).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 11.

6. **REQUIRED_INPUT_DATA:** Chronological draw history and pre-target 49-number counts for 50/300/750/FULL views; legal ticket construction; exact same-count baseline.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** p50-p300 slope; (p50-p300)-(p300-p750) acceleration; rank disagreement; turnover; fold-local scaling.

9. **TARGET_OUTPUT:** Per-number next-draw appearance probability or a fixed ticket outcome derived from those scores; primary test must compare against a level-only frequency model.

10. **HISTORICAL_TEST_DESIGN:** Fit a parsimonious causal incremental model; compare LEVEL_ONLY versus LEVEL_PLUS_SLOPE versus LEVEL_PLUS_SLOPE_ACCELERATION_DISAGREEMENT under identical splits and construction.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Expanding blocked time folds with minimum 750 prior draws for the complete view; no random row split.

12. **RANDOMNESS_REQUIREMENT:** Deterministic features/model first; fixed seeds and multiple-seed stability only at Level 3.

13. **LEAKAGE_RISKS:** Computing windows with target, global scaling, globally chosen breakpoints, or selecting window formulas on outer-test data.

14. **MULTIPLICITY_RISKS:** Many window definitions and transforms. Level 1 fixes 50/300/750 and one acceleration formula; Level 3 owns a bounded family with correction.

15. **FORWARD_EXECUTION_PATH:** Raw draw history makes features forward-computable, but a new versioned Track B producer/adapter is still required.

16. **COMPUTE_COST:** Low to medium.

17. **FAILURE_CRITERIA:** No incremental gain over level-only frequency, unstable sign across blocks, or gain only after broad window search.

18. **SUCCESS_CRITERIA:** Predeclared incremental improvement in proper scoring and fixed-ticket residual across multiple blocks.

19. **SHOULD_TRACK_B_TEST?** YES — cheap, clearly distinguishable falsification.

20. **PRIORITY:** Discovery top tier and strong prospective readiness.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: Fixed 50/300/750 slope and acceleration in a simple deterministic model versus level-only frequency.
- LEVEL 2 — STANDARD HISTORICAL TEST: Nested expanding folds, proper scores plus fixed-ticket residual, FULL/750/300/50 views, and incremental ablations.
- LEVEL 3 — DEEP EXPLORATION: Bounded alternative windows/transforms, regime interactions, multiple seeds/models, corrected as one declared family.

## H04 — CALIBRATED_PER_NUMBER_PROBABILITIES

1. **WHAT_IS_NEW?** Emit and validate causal out-of-sample P(number appears) for all 49 numbers, including calibration—not merely a score or rank.

2. **WHAT_ALREADY_EXISTS?** XGBoost/ML/attention/Bayesian-style strategies emit tickets or scores, but the 133 raw authority does not preserve calibrated probabilities, reliability, Brier, log loss, ECE, or calibration curves.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__xgboost_model__38c72a70c627` (ML_like).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 1.

6. **REQUIRED_INPUT_DATA:** Pre-target draw features, binary 49-number next-draw targets, model outputs generated anew, and nested calibration partitions.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Raw logits/probabilities, calibrated probabilities, reliability bins, Brier/log loss/ECE, sharpness, and calibration slope/intercept.

9. **TARGET_OUTPUT:** 49 correlated binary appearance outcomes per draw; primary proper score at the draw block level.

10. **HISTORICAL_TEST_DESIGN:** Compare causal frequency probability, uncalibrated model, Platt/beta/isotonic calibration fitted only in inner history; evaluate held-out proper scoring and reliability.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Nested blocked temporal calibration; calibrator never sees the outer evaluation block.

12. **RANDOMNESS_REQUIREMENT:** Fixed seed set for model training; deterministic calibration where possible; report seed distribution.

13. **LEAKAGE_RISKS:** Normalizing arbitrary scores and calling them probabilities, calibration on evaluation data, row-level random split across numbers/draws, target-derived feature selection.

14. **MULTIPLICITY_RISKS:** Models, calibrators, bins, and feature sets. Predeclare primary Brier score/model pair; treat other metrics as secondary.

15. **FORWARD_EXECUTION_PATH:** Requires new probability-output interface and forward adapter; cannot be reconstructed from historical tickets.

16. **COMPUTE_COST:** Medium to high depending model family.

17. **FAILURE_CRITERIA:** Worse proper score than causal frequency, severe reliability error, probability invalidity, or calibration gain absent out of sample.

18. **SUCCESS_CRITERIA:** Better predeclared proper score plus materially improved reliability across blocked folds without losing all sharpness.

19. **SHOULD_TRACK_B_TEST?** YES after probability-output engineering.

20. **PRIORITY:** High novelty; not an tonight-with-existing-artifacts experiment.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: Causal frequency-probability baseline plus one simple model; report Brier/log loss/ECE without post-hoc calibration.
- LEVEL 2 — STANDARD HISTORICAL TEST: Nested blocked calibration comparing uncalibrated, Platt/beta/isotonic outputs with draw-level uncertainty.
- LEVEL 3 — DEEP EXPLORATION: Bounded model families, reliability/sharpness frontier, multiple seeds, and alternative calibration objectives.

## H05 — DIRECT_TICKET_LEVEL_RESIDUAL_SCORING

1. **WHAT_IS_NEW?** Score legal six-number tickets directly through joint residual features instead of ranking numbers first and then constructing tickets.

2. **WHAT_ALREADY_EXISTS?** Combination, Apriori, pair/triple, covering, and portfolio evaluators exist. They do not exactly match a causal direct ticket-level residual model over a frozen bounded candidate set.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__backtest_apriori__2abb53765703` (utility); `legacy_biglotto__backtest_biglotto_portfolio__0b8100ce7ac8` (utility); `legacy_biglotto__covering_strategy_research__214ecc206fc9` (statistical); `legacy_biglotto__evaluate_combinations__d49d0787d0c6` (statistical); `legacy_biglotto__optimal_2bet_3bet_matrix__6e5aec296145` (statistical); `legacy_biglotto__portfolio_optimizer__1a6efc7959b6` (statistical); `legacy_biglotto__predict_biglotto_apriori__cda690ae84c2` (utility); `legacy_biglotto__test_ces__78d17c530ab8` (utility); `legacy_biglotto__test_cluster_cover__5b43959e7c55` (utility); `legacy_biglotto__test_greedy_optimizer__82df7f878ece` (utility).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 11.

6. **REQUIRED_INPUT_DATA:** Pre-target draw history; fixed legal-ticket candidate generator; sum/zone/parity/pair/triple/overlap features; ticket outcomes and exact candidate-pool comparators.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Joint ticket residuals versus marginal independence, causal interaction features, and bounded candidate scores.

9. **TARGET_OUTPUT:** Ticket-level hit depth/any-prize or residual versus candidate-matched random; number-level metrics are secondary.

10. **HISTORICAL_TEST_DESIGN:** Generate and freeze 256/1,024/4,096 candidate tickets per target from causal rules; compare additive-number score versus ticket-interaction score on the identical candidate set.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Candidate generation and feature fitting end at target-1; nested blocked folds for feature/regularization choices.

12. **RANDOMNESS_REQUIREMENT:** Deterministic candidate generator preferred; otherwise fixed seeds and identical candidate pool shared by all scorers.

13. **LEAKAGE_RISKS:** Candidate pool chosen using target, joint frequencies including target, searching all 13,983,816 tickets after viewing outcomes, or comparator pool mismatch.

14. **MULTIPLICITY_RISKS:** Many interactions and candidate sizes. Freeze a small basis at Level 1; use hierarchical regularization and bounded families later.

15. **FORWARD_EXECUTION_PATH:** Requires a new bounded candidate generator/scorer; does not require source-internal ranking.

16. **COMPUTE_COST:** Medium at bounded sizes; high if interactions proliferate. Full-universe brute force is explicitly out.

17. **FAILURE_CRITERIA:** No incremental residual over additive scoring on same candidates; overfit interactions; unstable candidate-size dependence.

18. **SUCCESS_CRITERIA:** Stable held-out gain over additive and matched random within the same fixed candidate pool and budget.

19. **SHOULD_TRACK_B_TEST?** YES, after H01/H03 fast tests or in parallel when engineering capacity exists.

20. **PRIORITY:** High discovery, medium-low readiness.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: Freeze 256 candidates and compare additive-number versus one regularized ticket-interaction score.
- LEVEL 2 — STANDARD HISTORICAL TEST: Repeat at 256/1,024/4,096 candidates in nested blocked folds with exact candidate-matched baselines and hit-depth.
- LEVEL 3 — DEEP EXPLORATION: Bounded interaction families, hierarchical regularization, regime interactions, and candidate-generator sensitivity—no full-universe brute force.

## H06 — DPP_SUBMODULAR_PORTFOLIO_SELECTION

1. **WHAT_IS_NEW?** Optimize portfolio diversity with a determinantal or explicit submodular marginal-utility objective, not just generic greedy/covering/orthogonal heuristics.

2. **WHAT_ALREADY_EXISTS?** Covering, cluster cover, orthogonal diversification, greedy, portfolio, and multi-bet optimizers are strongly related. None of the 133 records an exact DPP objective or the same predeclared submodular utility.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e` (statistical); `legacy_biglotto__backtest_biglotto_portfolio__0b8100ce7ac8` (utility); `legacy_biglotto__backtest_diversified_2bet__78b1d5f5121c` (frequency); `legacy_biglotto__backtest_diversified_3bet__03acff1d1bf7` (utility); `legacy_biglotto__biglotto_diversified_ensemble__36dbfc14b360` (ML_like); `legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d` (ML_like); `legacy_biglotto__covering_strategy_research__214ecc206fc9` (statistical); `legacy_biglotto__orthogonal_diversification_benchmark__ce068c676ca5` (statistical); `legacy_biglotto__portfolio_optimizer__1a6efc7959b6` (statistical); `legacy_biglotto__research_true_orthogonal__d8652a872a49` (statistical).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 12.

6. **REQUIRED_INPUT_DATA:** A frozen causal candidate-ticket pool, candidate utility proxy, pairwise overlap/similarity, fixed ticket count/number pool/budget/cutoff, and exact matched baselines.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** DPP kernel/quality-diversity decomposition, submodular marginal gain, portfolio overlap, unique-number coverage, and conditional-random comparator.

9. **TARGET_OUTPUT:** Portfolio hit-depth/any-prize and overlap efficiency; predictive edge and diversification benefit reported separately.

10. **HISTORICAL_TEST_DESIGN:** On each identical candidate pool compare EXISTING_GREEDY, ORTHOGONAL, DPP, SUBMODULAR, CONDITIONAL_RANDOM with the same ticket count, number pool, budget, and cutoff.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Candidate scores/similarities are pre-target; tune kernel/utility only inside blocked training folds.

12. **RANDOMNESS_REQUIREMENT:** DPP sampling and conditional random use a frozen seed list; also compare deterministic MAP/greedy variants.

13. **LEAKAGE_RISKS:** Different candidate pools, ticket budgets, or candidate scores across optimizers; target-conditioned kernel; post-hoc objective selection.

14. **MULTIPLICITY_RISKS:** Optimizer × kernel × utility × portfolio size. One primary utility and fixed sizes first; family-wise correction later.

15. **FORWARD_EXECUTION_PATH:** Portfolio construction can wrap a forward-capable producer, but the DPP/submodular adapter itself is not pinned and requires Track B engineering.

16. **COMPUTE_COST:** Medium; kernel operations scale with bounded candidate pool.

17. **FAILURE_CRITERIA:** No improvement over matched greedy/orthogonal/conditional random, or gains explained solely by larger unique-number coverage.

18. **SUCCESS_CRITERIA:** Reproducible portfolio efficiency improvement under exact fairness controls; any predictive residual is a separate, stricter claim.

19. **SHOULD_TRACK_B_TEST?** YES — strong readiness once candidate pool is frozen.

20. **PRIORITY:** Top prospective-readiness tier, not automatic predictive-edge priority.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: One fixed candidate pool and portfolio size; compare existing greedy, orthogonal, DPP-MAP, submodular greedy, and conditional random.
- LEVEL 2 — STANDARD HISTORICAL TEST: Multiple frozen pool sizes/portfolio sizes under identical budgets; overlap, coverage, hit-depth, and exact uncertainty.
- LEVEL 3 — DEEP EXPLORATION: Bounded kernels/utilities, sampling versus MAP, seed stability, and producer × optimizer interactions with correction.

### H06 fairness invariant

`same candidate pool + same ticket count + same number pool + same budget + same information cutoff` is mandatory for every EXISTING_GREEDY / ORTHOGONAL / DPP / SUBMODULAR / CONDITIONAL_RANDOM comparison. Diversity or overlap reduction is reported as portfolio efficiency, not predictive edge.

## H07 — CHANGE_POINT_TRIGGERED_ALLOCATION

1. **WHAT_IS_NEW?** Change allocation only after a causally detected change point; this is neither H02 cross-horizon confirmation nor H03 treating window derivatives as direct signals.

2. **WHAT_ALREADY_EXISTS?** EWMA, drift, regime, adaptive, and multi-window strategies exist; no exact alarm-triggered allocation rule with detector training and response frozen before evaluation.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` (utility); `legacy_biglotto__backtest_biglotto_6bet_ewma__e1b5e100d254` (frequency); `legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae` (utility); `legacy_biglotto__backtest_p0p1_upgrade__15e895017d2f` (utility); `legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac` (frequency); `legacy_biglotto__feature_discovery_and_retrospective__e2ea8b18945d` (frequency); `legacy_biglotto__predict_evolutionary_gum__b3e96cf483b0` (regime); `legacy_biglotto__research_variant_history__149648f9fffc` (zone).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 8.

6. **REQUIRED_INPUT_DATA:** Draw chronology, causal regime descriptors, strategy residual histories, detector state, frozen alarm response, and matched alarm-frequency comparators.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Sequential change statistic/posterior, alarm state, time-since-alarm, and post-alarm allocation weights.

9. **TARGET_OUTPUT:** Incremental fixed-budget outcome residual of event-triggered allocation versus never-switch, always-regime, and random alarms matched on frequency.

10. **HISTORICAL_TEST_DESIGN:** Fit detector on inner history; freeze threshold and allocation response; replay sequentially without resets informed by future data.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Sequential expanding evaluation with detector state carried causally; outer blocks remain untouched during tuning.

12. **RANDOMNESS_REQUIREMENT:** Deterministic detector preferred; random-alarm comparator uses fixed seeds and matched alarm count/duration.

13. **LEAKAGE_RISKS:** Retrospective breakpoint placement, using future segment means, refitting threshold on outer outcomes, or assigning regime labels with full history.

14. **MULTIPLICITY_RISKS:** Detector families, thresholds, features, allocation responses. Fix one detector/response at Level 1 and nest all selection.

15. **FORWARD_EXECUTION_PATH:** Draw-level features are available; new detector/allocation producer and persistent state contract are required.

16. **COMPUTE_COST:** Low to medium.

17. **FAILURE_CRITERIA:** No gain versus matched random alarms/never-switch; excessive alarms; benefit disappears with causal breakpoint detection.

18. **SUCCESS_CRITERIA:** Stable incremental benefit localized after pre-target alarms and robust to matched-frequency random alarm controls.

19. **SHOULD_TRACK_B_TEST?** YES.

20. **PRIORITY:** High discovery/readiness after H03’s simpler incremental test.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: One causal detector/threshold and one frozen allocation response versus never-switch and matched random alarms.
- LEVEL 2 — STANDARD HISTORICAL TEST: Sequential replay across blocked periods with always-regime, random-alarm, and detector ablations; FULL/750/300/50 descriptors.
- LEVEL 3 — DEEP EXPLORATION: Bounded detector families, response functions, regime interactions, multiple seeds, and alarm-cost objective.

## H08 — TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS

1. **WHAT_IS_NEW?** Use time-decayed hyperedges and evolving higher-order motifs, then score residual occurrence beyond marginal/pairwise independence and static community structure.

2. **WHAT_ALREADY_EXISTS?** Pair co-occurrence, graphs, PageRank-like methods, clique/Apriori, cluster, and pair/triple logic exist. No exact temporal hypergraph motif-evolution residual is present.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__backtest_apriori__2abb53765703` (utility); `legacy_biglotto__backtest_cluster_pivot_biglotto__b28957a6433e` (utility); `legacy_biglotto__backtest_graph_method__dbc90b86f02a` (utility); `legacy_biglotto__cooccurrence_graph__25fa2e473092` (neighbor); `legacy_biglotto__graph_predictor__cd70713a5709` (ML_like); `legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee` (hot_cold); `legacy_biglotto__optimize_biglotto_cluster__b2a833918f95` (frequency); `legacy_biglotto__predict_biglotto_apriori__cda690ae84c2` (utility); `legacy_biglotto__test_cag__7ca5343dfedd` (utility); `legacy_biglotto__test_cluster_cover__5b43959e7c55` (utility).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 11.

6. **REQUIRED_INPUT_DATA:** Chronological six-number draw hyperedges before target; causal marginal/pair/triple baselines; motif vocabulary; decay and community state.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Time-decayed motif counts, higher-order residuals versus independence, motif velocity, dynamic community membership, and ticket motif score.

9. **TARGET_OUTPUT:** Next-draw motif/ticket residual and fixed-ticket outcomes versus marginal, static graph, co-occurrence, and Apriori baselines.

10. **HISTORICAL_TEST_DESIGN:** Begin with a tiny predefined motif set and one decay; ablate STATIC_GRAPH, STATIC_HYPERGRAPH, TEMPORAL_COUNTS, TEMPORAL_RESIDUALS.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Expanding blocked history; every hyperedge/decay/community update ends at target-1.

12. **RANDOMNESS_REQUIREMENT:** Deterministic motifs/community when possible; fixed seed list for stochastic community detection.

13. **LEAKAGE_RISKS:** Global graph including target/future, motif vocabulary mined on outer test, community smoothing backward from future, or target-informed decay.

14. **MULTIPLICITY_RISKS:** Combinatorial motif vocabulary is the main risk. Predefine a minimal set, hierarchical tests, and bounded Level 3 search.

15. **FORWARD_EXECUTION_PATH:** Requires new feature and scoring pipeline; raw draw history is sufficient for offline construction.

16. **COMPUTE_COST:** Medium for minimal motifs; high for broad motif/community search.

17. **FAILURE_CRITERIA:** No residual beyond marginal/static graph baselines; instability across folds/decays; discoveries vanish after motif-family correction.

18. **SUCCESS_CRITERIA:** Incremental held-out residual from predefined temporal higher-order features across multiple blocks.

19. **SHOULD_TRACK_B_TEST?** YES as a high-upside structural experiment after cheaper falsifiers.

20. **PRIORITY:** High novelty, lower readiness.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: One decay and tiny predefined pair/triple motif-residual set versus marginal and static graph baselines.
- LEVEL 2 — STANDARD HISTORICAL TEST: Temporal hypergraph updates in expanding blocks; static/temporal/residual/community ablations and fixed tickets.
- LEVEL 3 — DEEP EXPLORATION: Bounded motif vocabulary, decay family, dynamic communities, multiple seeds, and hierarchical multiplicity control.

## H09 — CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION

1. **WHAT_IS_NEW?** Apply a negative signal only when a separately frozen positive selector and context jointly satisfy a predeclared condition; the interaction is the hypothesis.

2. **WHAT_ALREADY_EXISTS?** Exclusion-only, must-not-hit, negative selection, anti-consensus, cold/hot suppression, and constraint filters exist. They test negative information, but not the full positive-selector × conditional-suppression design.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__anti_consensus_strategy__a454ddd26cef` (folklore); `legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5` (hot_cold); `legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae` (utility); `legacy_biglotto__backtest_must_hit__909c91fd2fd0` (utility); `legacy_biglotto__constraint_filter_predictor__3a85b3995002` (sum_range); `legacy_biglotto__negative_selection_biglotto__98f860c52cc2` (hot_cold); `legacy_biglotto__test_4bet_dcb__3c7e3e661ad8` (utility); `legacy_biglotto__test_cag__7ca5343dfedd` (utility); `legacy_biglotto__test_cluster_cover__5b43959e7c55` (utility); `legacy_biglotto__test_zdp__e80cc7e95453` (utility).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 10.

6. **REQUIRED_INPUT_DATA:** Frozen positive selector outputs/scores, pre-target negative features, causal condition/gate, identical candidate/budget, outcomes, and matched random suppression.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Conditional negative score, gate state, removed-number/ticket set, suppression intensity, and paired counterfactual portfolio.

9. **TARGET_OUTPUT:** Incremental outcome residual of CONDITIONAL_SUPPRESSION over POSITIVE_ONLY, EXCLUSION_ONLY, UNCONDITIONAL_NEGATIVE, and RANDOM_MATCHED_SUPPRESSION.

10. **HISTORICAL_TEST_DESIGN:** Choose and freeze one positive selector without using H09 evaluation outcomes; apply one predeclared negative condition; compare paired target draws.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Positive selector and suppression gate tuned only in inner blocked history; outer draw results never influence which selector is chosen.

12. **RANDOMNESS_REQUIREMENT:** Matched random suppression uses fixed seeds, same removal count, and same candidate universe.

13. **LEAKAGE_RISKS:** Choosing positive selector from outer results, target-derived kill list, tuning condition after paired outcomes, or comparing different budgets.

14. **MULTIPLICITY_RISKS:** Many positive × negative × condition combinations. Level 1 tests exactly one of each; Level 3 uses hierarchical interaction testing.

15. **FORWARD_EXECUTION_PATH:** Requires both components to be forward-capable and a new conditional wrapper; current 51/133 runtime overlap is only a preflight universe.

16. **COMPUTE_COST:** Low to medium for a fixed pair.

17. **FAILURE_CRITERIA:** Conditional version does not beat positive-only and matched random suppression, or any apparent gain comes from ticket-count/budget change.

18. **SUCCESS_CRITERIA:** Stable paired incremental gain specific to the condition, with no unconditional degradation and corrected interaction evidence.

19. **SHOULD_TRACK_B_TEST?** YES — preserve as FAMILY_TESTED_NEW_HYPOTHESIS_OPEN.

20. **PRIORITY:** High-value, relatively cheap conditional interaction test.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: One frozen positive selector, one negative signal, one condition; paired comparison with positive-only and matched random suppression.
- LEVEL 2 — STANDARD HISTORICAL TEST: Nested blocked replay including exclusion-only, unconditional negative, conditional negative, and matched-random controls.
- LEVEL 3 — DEEP EXPLORATION: Bounded positive × negative × context interactions, suppression intensity, regime effects, and hierarchical correction.

### H09 closure decision

Historical negative/exclusion families are tested, but the positive-selector × conditional-suppression interaction is not. Classification: `FAMILY_TESTED_NEW_HYPOTHESIS_OPEN`.

## H10 — DYNAMIC_BAYESIAN_STATE_SPACE_MODELING

1. **WHAT_IS_NEW?** Infer a latent temporal state with posterior uncertainty and state evolution, then use that posterior for number/ticket probabilities or allocation.

2. **WHAT_ALREADY_EXISTS?** Static Bayesian weights, Markov transitions, EWMA/frequency dynamics, ML, and regime descriptors exist. Bayesian is not state-space; none of the 133 is an exact latent dynamic probabilistic state model.

3. **CLOSEST_EXISTING_STRATEGIES:** `legacy_biglotto__backtest_biglotto_6bet_ewma__e1b5e100d254` (frequency); `legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b` (markov); `legacy_biglotto__backtest_markov_repeat_exception__9bd283fca5f3` (statistical); `legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac` (frequency); `legacy_biglotto__predict_evolutionary_gum__b3e96cf483b0` (regime); `legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361` (markov); `legacy_biglotto__xgboost_model__38c72a70c627` (ML_like).

4. **EXACT_COLLISION_COUNT:** 0 within the 133.

5. **STRONG_OVERLAP_COUNT:** 7.

6. **REQUIRED_INPUT_DATA:** Chronological draw observations, pre-target number/structural features, specified latent-state dynamics/emissions/priors, and proper-score outcomes.

7. **INPUT_DATA_ALREADY_AVAILABLE?** Historical primitives are available as described in the sufficiency matrix; new model outputs/runtime adapters remain explicitly partial or unavailable.

8. **NEW_DERIVED_FEATURES_REQUIRED:** Filtered (not smoothed) state posterior, transition uncertainty, posterior predictive number probabilities, and state-conditioned ticket scores.

9. **TARGET_OUTPUT:** Held-out log loss/Brier for posterior predictive outputs plus fixed-ticket residual versus static Beta/Bayesian, trailing frequency, Markov/HMM-like, and regime baselines.

10. **HISTORICAL_TEST_DESIGN:** Start with a low-dimensional conjugate/dynamic logistic state model; use filtering only; compare static and dynamic ablations before richer nonlinear variants.

11. **TEMPORAL_SPLIT_REQUIREMENT:** Nested expanding time blocks; filter at target using data through target-1. Backward-smoothed states are forbidden for prediction evaluation.

12. **RANDOMNESS_REQUIREMENT:** Deterministic filtering where possible; fixed chains/seeds and convergence diagnostics for approximate inference.

13. **LEAKAGE_RISKS:** Posterior smoothing with future observations, tuning state count on outer test, global standardization, or reporting in-sample posterior fit.

14. **MULTIPLICITY_RISKS:** State dimensions, priors, transition forms, emissions, inference methods. One parsimonious primary model first; bounded family later.

15. **FORWARD_EXECUTION_PATH:** Requires a new stateful probability producer/adapter and explicit state persistence/versioning.

16. **COMPUTE_COST:** Medium to high; nonlinear/particle/MCMC variants are Level 3 only.

17. **FAILURE_CRITERIA:** No proper-score gain over static/trailing baselines, non-identifiability, poor convergence, or only smoothed/in-sample improvement.

18. **SUCCESS_CRITERIA:** Filtered posterior predictions improve proper scoring and calibration across blocked folds with stable interpretable state behavior.

19. **SHOULD_TRACK_B_TEST?** YES as a long-shot/high-information experiment after lower-cost candidates.

20. **PRIORITY:** High novelty, lowest near-term readiness among Top 10.

### Three experiment depths

- LEVEL 1 — FAST FALSIFICATION: Low-dimensional filtered dynamic model versus static Beta/trailing-frequency baselines on proper scores.
- LEVEL 2 — STANDARD HISTORICAL TEST: Nested blocked model comparison with filtered posteriors, calibration, fixed-ticket construction, and Markov/regime ablations.
- LEVEL 3 — DEEP EXPLORATION: Bounded state dimensions/priors/emissions, nonlinear/particle alternatives, multiple seeds/chains, and convergence gates.

## Distinguishing H02, H03, and H07

| Hypothesis | Signal | Decision semantics | Confirmation caveat |
|---|---|---|---|
| H02 | Cross-horizon robustness/minimax | Accept only when horizons jointly support a fixed producer | Same 1,957 draws cannot independently confirm |
| H03 | Window slope/acceleration/disagreement | The derivative/disagreement itself predicts | Must beat level-only window features |
| H07 | Sequential change alarm | Change allocation only after a causal alarm | Retrospective breakpoint placement is forbidden |

## Evidence-context conclusions

- Hit Depth authority contains 3,192 core rows = 133 strategies × 4 windows × 6 depths, with no duplicate keys and exact same-native-multiplicity baselines.
- Combination authority contains 8,778 pairs and 383,306 triples (392,084 identities; 3,136,672 cells). Candidate A is a current-portfolio vote proxy and C is a trailing-frequency proxy; neither is strategy-internal rank. Its 1,007 cross-window-stable identities remain discovery-biased.
- Robustness authority evaluated 17,024 cells: 3,118 positive descriptively, zero positive after Bonferroni, and 731 negative after Bonferroni. This constrains claims but does not close nonidentical Top-10 hypotheses.
- Negative/portfolio evidence contains 1,270,706 duplicate ticket rows. Exact duplicates waste budget; distinct-ticket overlap induces correlated wins. A portfolio optimizer can remove a structural handicap without creating predictive information.
- Official causal-regime analysis has 1,399 targets with 750 prior draws, 20 candidates, 5/10/15/20 tickets, and four causal regime features. Its 71 high-sample positive cells are exploratory and multiplicity-exposed, so H01/H07 must not treat them as confirmed.
- R4 has zero post-freeze prospective observations. No Top-10 result may be described as prospective confirmation.

## Nearest-neighbor evidence appendix

The exact identities are also present row-by-row in the collision matrix. These lists show the strongest semantic neighbors, not exact duplicates.

### H01

- `legacy_biglotto__advanced_methods_benchmark__87ee0d15033c` — `ML_like` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` — `utility` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__backtest_biglotto_7bet_optimized__2881417de6f8` — `utility` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__biglotto_diversified_ensemble__36dbfc14b360` — `ML_like` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d` — `ML_like` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__feature_discovery_and_retrospective__e2ea8b18945d` — `frequency` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__hybrid_integration_benchmark__5789ca885422` — `report` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__optimized_ensemble__e05e0fde22d7` — `ML_like` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__predict_6expert__ff7c2b15f371` — `ML_like` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.
- `legacy_biglotto__predict_consensus_ensemble__3ceb975a355c` — `ML_like` — ensemble/meta-selection component exists, but no causal cross-strategy residual gate with frozen candidate selection.

### H02

- `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__backtest_biglotto_7bet_optimized__2881417de6f8` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__backtest_diversified_3bet__03acff1d1bf7` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__research_variant_history__149648f9fffc` — `zone` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__test_ces__78d17c530ab8` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__test_dms__b63442289bd5` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__test_greedy_optimizer__82df7f878ece` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__test_mwsc__ba37643d6a3b` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.
- `legacy_biglotto__verify_elite7_claim__937afa8d6133` — `utility` — multi-window or robust selection component exists, but not the same horizon-wise minimax confirmation rule.

### H03

- `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` — `utility` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__backtest_biglotto_6bet_ewma__e1b5e100d254` — `frequency` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__backtest_biglotto_7bet_optimized__2881417de6f8` — `utility` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac` — `frequency` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__feature_discovery_and_retrospective__e2ea8b18945d` — `frequency` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__research_variant_history__149648f9fffc` — `zone` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__test_ces__78d17c530ab8` — `utility` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__test_dms__b63442289bd5` — `utility` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__test_greedy_optimizer__82df7f878ece` — `utility` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.
- `legacy_biglotto__test_mwsc__ba37643d6a3b` — `utility` — window-frequency/drift component exists, but slope, acceleration, and disagreement are not the predictive target.

### H04

- `legacy_biglotto__xgboost_model__38c72a70c627` — `ML_like` — model score/rank exists, but calibrated out-of-sample P(number appears) authority is absent.

### H05

- `legacy_biglotto__backtest_apriori__2abb53765703` — `utility` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__backtest_biglotto_portfolio__0b8100ce7ac8` — `utility` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__covering_strategy_research__214ecc206fc9` — `statistical` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__evaluate_combinations__d49d0787d0c6` — `statistical` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__optimal_2bet_3bet_matrix__6e5aec296145` — `statistical` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__portfolio_optimizer__1a6efc7959b6` — `statistical` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__predict_biglotto_apriori__cda690ae84c2` — `utility` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__test_ces__78d17c530ab8` — `utility` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__test_cluster_cover__5b43959e7c55` — `utility` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.
- `legacy_biglotto__test_greedy_optimizer__82df7f878ece` — `utility` — ticket interaction or candidate evaluation exists, but no direct causal residual score over a fixed legal-ticket candidate set.

### H06

- `legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e` — `statistical` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__backtest_biglotto_portfolio__0b8100ce7ac8` — `utility` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__backtest_diversified_2bet__78b1d5f5121c` — `frequency` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__backtest_diversified_3bet__03acff1d1bf7` — `utility` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__biglotto_diversified_ensemble__36dbfc14b360` — `ML_like` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d` — `ML_like` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__covering_strategy_research__214ecc206fc9` — `statistical` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__orthogonal_diversification_benchmark__ce068c676ca5` — `statistical` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__portfolio_optimizer__1a6efc7959b6` — `statistical` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.
- `legacy_biglotto__research_true_orthogonal__d8652a872a49` — `statistical` — portfolio diversity/covering optimization exists, but no DPP or explicitly submodular marginal-utility objective.

### H07

- `legacy_biglotto__auto_optimizer_alpha__7eaa9572e384` — `utility` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.
- `legacy_biglotto__backtest_biglotto_6bet_ewma__e1b5e100d254` — `frequency` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.
- `legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae` — `utility` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.
- `legacy_biglotto__backtest_p0p1_upgrade__15e895017d2f` — `utility` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.
- `legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac` — `frequency` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.
- `legacy_biglotto__feature_discovery_and_retrospective__e2ea8b18945d` — `frequency` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.
- `legacy_biglotto__predict_evolutionary_gum__b3e96cf483b0` — `regime` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.
- `legacy_biglotto__research_variant_history__149648f9fffc` — `zone` — adaptive/window/regime component exists, but allocation is not triggered only by a causally detected change point.

### H08

- `legacy_biglotto__backtest_apriori__2abb53765703` — `utility` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__backtest_cluster_pivot_biglotto__b28957a6433e` — `utility` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__backtest_graph_method__dbc90b86f02a` — `utility` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__cooccurrence_graph__25fa2e473092` — `neighbor` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__graph_predictor__cd70713a5709` — `ML_like` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee` — `hot_cold` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__optimize_biglotto_cluster__b2a833918f95` — `frequency` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__predict_biglotto_apriori__cda690ae84c2` — `utility` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__test_cag__7ca5343dfedd` — `utility` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.
- `legacy_biglotto__test_cluster_cover__5b43959e7c55` — `utility` — graph, co-occurrence, or Apriori component exists, but no time-decayed higher-order motif residual model.

### H09

- `legacy_biglotto__anti_consensus_strategy__a454ddd26cef` — `folklore` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5` — `hot_cold` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae` — `utility` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__backtest_must_hit__909c91fd2fd0` — `utility` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__constraint_filter_predictor__3a85b3995002` — `sum_range` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__negative_selection_biglotto__98f860c52cc2` — `hot_cold` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__test_4bet_dcb__3c7e3e661ad8` — `utility` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__test_cag__7ca5343dfedd` — `utility` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__test_cluster_cover__5b43959e7c55` — `utility` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.
- `legacy_biglotto__test_zdp__e80cc7e95453` — `utility` — negative/exclusion signal exists, but it is not conditionally applied to a separately frozen positive selector.

### H10

- `legacy_biglotto__backtest_biglotto_6bet_ewma__e1b5e100d254` — `frequency` — Bayesian/Markov/dynamic-frequency component exists, but no latent probabilistic state-space posterior drives predictions.
- `legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b` — `markov` — Bayesian/Markov/dynamic-frequency component exists, but no latent probabilistic state-space posterior drives predictions.
- `legacy_biglotto__backtest_markov_repeat_exception__9bd283fca5f3` — `statistical` — Bayesian/Markov/dynamic-frequency component exists, but no latent probabilistic state-space posterior drives predictions.
- `legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac` — `frequency` — Bayesian/Markov/dynamic-frequency component exists, but no latent probabilistic state-space posterior drives predictions.
- `legacy_biglotto__predict_evolutionary_gum__b3e96cf483b0` — `regime` — Bayesian/Markov/dynamic-frequency component exists, but no latent probabilistic state-space posterior drives predictions.
- `legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361` — `markov` — Bayesian/Markov/dynamic-frequency component exists, but no latent probabilistic state-space posterior drives predictions.
- `legacy_biglotto__xgboost_model__38c72a70c627` — `ML_like` — Bayesian/Markov/dynamic-frequency component exists, but no latent probabilistic state-space posterior drives predictions.

## What we have not tried (bounded Top-10 view)

- A rank-free causal cross-strategy residual gate trained/evaluated with nested family-aware blocks.
- Independent untouched confirmation of the fixed horizon-minimax producer.
- Incremental slope/acceleration/disagreement after controlling for frequency levels.
- Persisted, out-of-sample calibrated 49-number probabilities with proper scoring.
- Candidate-restricted direct ticket interaction residual scoring.
- Fair same-pool DPP/submodular comparison separating diversity from predictive edge.
- Sequential change-point-only allocation with matched random alarms.
- Time-decayed higher-order hypergraph motif residuals.
- A frozen positive selector crossed with conditional negative suppression.
- Filtered latent state-space posterior predictions benchmarked against static Bayesian/frequency/Markov methods.

## Optional experiment portfolios

- **Top 5 cheap:** H03 fixed derivatives; H09 one fixed conditional pair; H02 reproduction/stability; H07 one detector; H01 fixed-rule small expert gate.
- **Top 5 high-upside:** H01, H03, H09, H05, H08.
- **Top 5 long-shot/high-cost:** H10, H08 broad motifs, H04 model-family calibration, H05 richer interactions, H06 producer×optimizer interactions.

## Determinism, limits, and handoff

- Deterministic inputs: pinned commit/tree, verified prior-report hash, sorted 133 identities, fixed semantic rule sets, and fixed score weights.
- Source bodies from frozen commit 49a25eff are locally unavailable; the audit does not infer internal ranks/probabilities or claim line-level source proof.
- No strategy was implemented; no historical/prospective experiment was executed; specs are drafts without authorization tokens.
- No repo, DB, sealed task-data, candidate freeze, observer, cohort, prospective operation, commit, branch, push, or PR mutation is part of this artifact set.
