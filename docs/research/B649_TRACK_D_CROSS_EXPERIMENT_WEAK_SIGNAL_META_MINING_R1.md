# B649 Track D — Cross-Experiment Weak-Signal Meta-Mining R1

TASK_ID: B649_TRACK_D_CROSS_EXPERIMENT_WEAK_SIGNAL_META_MINING_R1
MODE: READ_ONLY_DISCOVERY_ANALYSIS
DATE: 2026-08-15
STATUS: COMPLETE

REPO_MUTATION: NONE
DB_MUTATION: NONE
COHORT_CREATED: NONE
EH04_INTERIM_RESULTS_READ: NO (directory `B649_TRACK_B_EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER_DISCOVERY_R1` and the adjacent `B649_TRACK_B_HISTORICAL_SUPPORT_REGIME_COMPATIBILITY_AND_EH04_RECHECK_R1` were both left untouched, out of caution, since the latter's name is EH04-adjacent even though it only checks feature compatibility)
COHORT_V2_PROSPECTIVE_OUTCOMES_USED: NO
TARGET_OUTCOME_USED_TO_SELECT_MODEL_IN_REAL_TIME: NO (oracle values below are post-hoc theoretical headroom only, never a live selection rule)

This is a discovery-only read of pre-existing sealed Level-1 outputs. It does not create a Cohort, rerun any B experiment, retune any model, or select the next B task.

## Sources read (all pre-existing, none re-executed)

All paths are outside git, under `/Users/kelvin/VibeCoding-WorkSpace/`:

| Experiment | Root | Per-target file used |
|---|---|---|
| STATIC_CONSENSUS (backbone) | `B649_TRACK_D_STATIC_CONSENSUS_FAILURE_FEATURES_R1.csv` (workspace root) | itself — 1,417 rows, `m2_plus` + 15 pre-target features + `era` |
| H01 cross-strategy meta-selector | `.task-data/B649_H01_CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR_R1` | `selection_history.csv.gz`, `sensitivity=BASE` rows, 15 policies |
| H03 multi-window slope/accel/disagreement | `.task-data/B649_TRACK_B_H03_MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT_DRAFT_R1` | `ticket_results.csv.gz`, 4 fixed models |
| H04 calibrated per-number probabilities | `.task-data/B649_TRACK_B_H04_CALIBRATED_PER_NUMBER_PROBABILITIES_LEVEL1_R1` | none usable — see NOT_COMPARABLE below |
| H05 direct ticket-level residual scoring | `.task-data/B649_TRACK_B_H05_DIRECT_TICKET_LEVEL_RESIDUAL_SCORING_LEVEL1_R1` | `report.md` headline deltas only (rate-tier, not merged into the binary matrix) |
| H06 DPP/submodular portfolio selection | `.task-data/B649_TRACK_B_H06_DPP_SUBMODULAR_PORTFOLIO_SELECTION_LEVEL1_R1` | `predictive_results.csv`, 5 arms |
| H07 change-point-triggered allocation | `.task-data/B649_TRACK_B_H07_CHANGE_POINT_TRIGGERED_ALLOCATION_LEVEL1_R1` | `detector_replay.csv.gz`, 3 models |
| H08 temporal hypergraph motif residuals | `.task-data/B649_TRACK_B_H08_TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS_LEVEL1_R1` | `report.md` headline deltas only (rate-tier, same shape as H05) |
| H09 conditional negative-info suppression | `.task-data/B649_TRACK_B_H09_CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION_LEVEL1_R1` | `level1_target_ledger.csv`, 1 model |
| H10 dynamic Bayesian state-space | `.task-data/B649_TRACK_B_H10_DYNAMIC_BAYESIAN_STATE_SPACE_MODELING_LEVEL1_R1` | `predictive_results.csv`, 3 models (`hit_depth>=2`) |
| Complementarity-aware candidate stack | `.task-data/B649_TRACK_B_COMPLEMENTARITY_AWARE_CANDIDATE_STACK_DISCOVERY_R1` | `heldout_predictions.csv`, 5 columns incl. a `static_consensus` echo |
| Consensus + pairwise residual reranker | `.task-data/B649_TRACK_B_CONSENSUS_PLUS_PAIRWISE_RESIDUAL_RERANK_DISCOVERY_R1` | `heldout_results.csv`, 4 columns incl. a `static_consensus` echo |

Every file above was read with a streaming CSV/gzip reader, extracting only the target-identifier, model-identifier, and outcome columns needed (several source files are 100+MB; none were loaded whole). Extraction and analysis scripts and the intermediate JSON live only in this session's scratchpad — not written to the repo or to `.task-data`.

## Critical methodology correction made before answering the questions

The naive version of this analysis (pool every model's per-target M2+ flag into one union/oracle) produces a spectacular-looking +50 to +80 percentage-point "oracle uplift" over STATIC_CONSENSUS. **That number is almost entirely an artifact, not a discovery.** The 12 experiments do not all spend the same ticket budget per target:

- STATIC_CONSENSUS, H03, H07, H10, and the two complementarity/reranker files pick **one** 6-number ticket per target.
- H09 fires **two** tickets per target when not suppressed.
- H06 (and its underlying Track-D matrix twin `T1_H06_*`) selects a **5-ticket** portfolio per arm.
- H01 selects an entire strategy's **native portfolio** (order 20–40 tickets per target, `selected_native_ticket_counts` in `selection_history.csv.gz`).
- H05 and H08 both score **20-ticket** pools and report a *rate*, not a win/loss flag.

"At least one ticket hits M2+" scales up mechanically with ticket count under the fixed exact-random per-ticket baseline `p = 150841/998844 = 15.10%` (this constant recurs verbatim across H03/H07/H09/H10's own sealed reports — it is a fixed hypergeometric property of 6/49, not data-dependent). A closed-form check confirms this is exactly what is happening:

| Ticket budget K | Theoretical independent-random oracle `1-(1-p)^K` | Observed in this data |
|---:|---:|---:|
| 2 | 27.92% | H09 conditional model: **28.30%** (n=1,417) |
| 5 | 55.89% | H06 arms: **56.3%–60.3%** (n=300, all 5 arms) |
| 17 | 93.82% | — |

H09's and H06's raw success rates land almost exactly on the pure-ticket-count line — which is precisely what their own sealed reports already concluded (H09: `STABILITY_RESULT: FAIL`, `UNCERTAINTY_RESULT: FAIL`; H06: `PREDICTIVE_RESEARCH_CLASSIFICATION: NO_SIGNAL`). This cross-check is reassuring: it reproduces each experiment's own negative finding through a completely independent route.

Consequence for this task: **all oracle/rescuer/pairwise-error statistics below use only the exposure-matched single-ticket tier** (STATIC_CONSENSUS + H03 + H07 + H10 + the two Tier-1 single-ticket files = 18 single-ticket series total). H01, H06/`T1_H06_*` (portfolio tier) and H09 (2-ticket tier) are reported separately, descriptively, with their ticket-count context attached so they cannot be misread as predictive edge. H05/H08 (20-ticket rate tier) are cited from their own sealed headline numbers only.

## Target-level matrix

Two exposure-matched alignments were built (see also the accompanying CSV):

- **MEGA_SINGLE_TICKET_300**: the 300 most recent targets (`113000006`..`115000069`, entirely `POST_2023`) where all three Tier-1 files (complementarity stack, residual reranker, H06) and H03/H07/H10 overlap. 17 single-ticket series (4 near-duplicate collapses noted below) simultaneously aligned target-by-target. Independently cross-checked: the `static_consensus` echo columns baked into the complementarity-stack file and the reranker file agree with the STATIC_CONSENSUS backbone on all 300 targets, 0 mismatches across 3 independently-sourced copies.
- **BROAD_SINGLE_TICKET_1095**: the wider `105000106`..`115000069` out-of-sample population shared identically by H03, H07, and H10 (`674 PRE_2023 / 421 POST_2023`), 10 single-ticket series.

Delivered CSV (300 rows × 17 model columns + STATIC_CONSENSUS + 8 pre-target features): `B649_TRACK_D_CROSS_EXPERIMENT_WEAK_SIGNAL_META_MINING_R1_MATRIX.csv` (workspace root, alongside this report).

Two exact-duplicate pairs were detected and are counted once, not twice, in headline "N independent signals" language: `H03_LEVEL_ONLY_P300` ≡ `H07_STATIC_P300` (success-indicator correlation = 1.0000 — both are the identical deterministic "static top-6 by trailing p300" ticket) and `T1_IDENTICAL_FLAT_STACK` ≡ `T1_PREVIOUS_FLAT_STACK` (correlation = 1.0000 — the same frozen baseline ticket reused across the two Track-B stacking experiments).

---

## REQUIRED OUTPUT

**TARGETS_ALIGNED:**
300 (MEGA, `POST_2023`-only, exposure-matched, 17 single-ticket series) and 1,095 (BROAD, mixed-era, 10 single-ticket series). STATIC_CONSENSUS backbone itself spans 1,417 targets (`103000001`..`115000069`).

**EXPERIMENTS_COMPARABLE:**
9 of 12 named experiments produced genuine target-level M2+/hit output and were aligned: H01 (portfolio tier), H03 (single-ticket), H06 (5-ticket portfolio tier), H07 (single-ticket), H09 (2-ticket tier), H10 (single-ticket), complementarity-aware candidate stack (single-ticket), consensus+pairwise residual reranker (single-ticket), plus STATIC_CONSENSUS itself as the anchor. 2 of 12 (H05, H08) produced only *rate*-over-20-ticket-pool outputs — kept out of the binary matrix, cited from their own headline deltas as `PARTIALLY_COMPARABLE`. 1 of 12 (H04) is `NOT_COMPARABLE`: its report states `NUMBER_SELECTION_PROJECTION: NOT_RUN` — it only ever produced calibrated per-number probabilities and Brier scores, never a ticket or a win/loss outcome. EH04 was not opened at all (excluded by the Packet).

**STATIC_CONSENSUS_M2_PLUS:**
22.33% on MEGA_300 (`POST_2023`-only — this is the only regime where consensus is known to beat chance, per the prior Track D failure-mode audit); 16.80% on BROAD_1095 (mixed-era, closer to the 15.10% exact-random single-ticket floor).

**ORACLE_MULTI_MODEL_M2_PLUS:**
- MEGA_300 (17 single-ticket series): **73.00%** — but the 17-independent-random-ticket theoretical ceiling for the same K is **93.82%**. The real oracle sits **20.8pp below** what blind ticket diversification alone would achieve, because the 17 series are positively correlated with each other (they largely draw on the same underlying 133-strategy / consensus-support substrate).
- BROAD_1095 (10 single-ticket series): **47.40%** vs a 10-random-ticket theoretical ceiling of **80.55%** — **33.2pp below** the diversification-only benchmark.

**ORACLE_UPLIFT_VS_CONSENSUS:**
+50.67pp (MEGA_300, 22.33%→73.00%) and +30.59pp (BROAD_1095, 16.80%→47.40%) in raw terms. **Both numbers are fully explained by pooling many different single tickets** (a random-ticket-only pool of the same size would show +71.5pp and +63.8pp respectively) **and should not be read as evidence of exploitable complementary predictive skill.** The real models capture *less* of the diversification benefit than pure randomness would, not more.

**BEST_CONSENSUS_FAILURE_RESCUER:**
`H03_LEVEL_ONLY_P300` (≡ `H07_STATIC_P300`), rescuing consensus failures at 13.9%–17.2% depending on window — statistically indistinguishable from the 15.10% unconditional exact-random floor a single random ticket would achieve regardless of whether consensus failed. No model in either exposure-matched block clears the random floor by a margin that survives even a rough noise check (largest single-model rescue-rate excess over 15.10% is +2.1pp on n=233, well under 1 standard error).

**BEST_COMPLEMENTARY_MODEL_PAIR:**
By combined consensus-failure rescue coverage: `H03_LEVEL_ONLY_P300` + `T1_STRONGEST_SINGLE` (MEGA_300, 30.0% coverage of 233 consensus failures) and `H03_LEVEL_PLUS_SLOPE_ACCELERATION_DISAGREEMENT` + `H07_JSD_SWITCH` (BROAD_1095, 25.2% coverage of 911 consensus failures). Reference point: two *independent random* tickets rescue 27.92% of any failure population regardless of correlation with consensus. Both observed "best pairs" are within ~1–2 standard errors of that reference (SE≈2.9pp at n=233, ≈1.5pp at n=911) — i.e. statistically indistinguishable from picking two random tickets. By pairwise *error correlation* (most negative = most complementary), the top pairs in both blocks all involve a random-control column (`T1_RANDOM_RESIDUAL` or `T1_EXACT_RANDOM`), which is the expected behavior of noise correlating weakly with everything, not a designed complementary relationship — and none of these correlations (max |r|≈0.16, n=300, 136 pairs tested) survive a Bonferroni correction for the number of pairs compared.

**ALL_MODEL_FAILURE_RATE:**
26.67% (STATIC_CONSENSUS and all 17 single-ticket candidates simultaneously miss, MEGA_300) / 48.49% (STATIC_CONSENSUS and all 10 candidates simultaneously miss, BROAD_1095 — the higher rate here is mostly the `PRE_2023` sub-population where nothing, including consensus, beats chance).

**PRE_TARGET_CLUSTER_SIGNAL:**
**NO.** Comparing the 8 pre-target consensus-structure features (`n_supported_numbers`, `top1_score`, `top6_mean_support`, `score_entropy_norm`, `support_concentration_hhi`, `strategy_disagreement`, `family_disagreement`, `top6_distinct_families`) between "consensus failed AND at least one weak model rescued" vs. "consensus failed AND every weak model also failed" targets, on both MEGA_300 and BROAD_1095: every standardized effect size is small (|d| ≤ 0.26, most under 0.13), and several features **flip sign** between the two blocks (`top1_score`: +0.01 in MEGA vs −0.13 in BROAD; `score_entropy_norm`: −0.14 vs +0.10; `support_concentration_hhi`: +0.08 vs −0.13). A real cluster-conditional edge should point the same direction in both windows; sign-flipping between the recent-only and mixed-era blocks is itself the signature of noise, not signal. This independently reproduces the prior Track D static-consensus failure-mode audit's finding that no support-shape/family feature survives multiplicity correction ([[b649-track-d-static-consensus-failure-mode-r1]]).

**CONDITIONAL_MODEL_SELECTION_POTENTIAL:**
**LOW.** Three independent lines of evidence converge: (1) the raw oracle uplift is fully — and then some — explained by ticket-count diversification, not model skill; (2) no individual model or pair rescues consensus failures above the rate a random ticket would achieve by chance; (3) no pre-target feature discriminates rescuable from unrescuable consensus failures, and the weak candidate effects that do exist reverse sign between the two evaluation windows.

---

## TOP_5_REUSABLE_WEAK_SIGNALS

Ranked by rescue rate given consensus failure (single-ticket tier only; all rates are within noise of the 15.10% random floor, so "reusable" here means "worth keeping in a future ensemble screen," not "known to help"):

1. `H03_LEVEL_ONLY_P300` / `H07_STATIC_P300` (duplicate pair) — 13.9%–17.2% rescue rate, the least-informative but most stable comparator; useful as a cheap always-available anchor since it needs no fitting.
2. `H07_JSD_SWITCH` — 13.6%–17.7% rescue rate with 0.44 success-correlation to consensus on MEGA_300 (higher agreement than most peers, i.e. genuinely tracks consensus rather than diverging from it, which limits its complementary value but confirms internal consistency).
3. `T1_STRONGEST_SINGLE` (complementarity-stack's best single ticket) — 15.0% rescue rate on the recent 300, the component most worth re-testing since it forms the best-coverage pair with H03/H07 above.
4. `T1_COMPLEMENTARITY_STACK` — the only candidate whose own overall M2+ rate (21.7%) approaches STATIC_CONSENSUS's 22.3% on the same 300 targets, i.e. the single most "consensus-competitive" individual weak signal found, even though it does not rescue consensus's specific failures at an above-chance rate.
5. `H10_TRAILING_50_BETA_BINOMIAL_ONE_PSEUDODRAW_V1` — highest success-correlation with consensus (0.44 on BROAD_1095) among genuinely distinct (non-duplicate) models; useful as a redundancy check rather than a diversification source.

## TOP_3_NEW_RESEARCH_HYPOTHESES

1. **Diversification-corrected oracle benchmark should become a standing gate.** Every future "ensemble/meta-selector/portfolio" B649 experiment should report its oracle or portfolio M2+ rate *against the closed-form `1-(1-p)^K` random-ticket-count baseline for its own K*, not just against STATIC_CONSENSUS. This single check would have flagged H06's and H09's headline "beats consensus" framing as a ticket-count artifact without needing this cross-experiment pass. (Concrete next step: add this as one derived column to Track D's existing experiment ledger rather than a new experiment.)
2. **Search for genuinely decorrelated single-ticket sources, not more models on the same substrate.** All 10+ single-ticket weak signals tested here draw, directly or indirectly, on the same 133-strategy/consensus-support feature base, which is why their pooled oracle underperforms pure random ticket diversity. A productive next Level-1 candidate would be a single-ticket generator built from a genuinely disjoint information source (e.g., cross-lottery structure already validated in [[pr128-strategy-matrix-p638-diversification-merged]], or a pure combinatorial/coverage-design ticket unrelated to any of the 133 strategies) and tested for error-decorrelation against `STATIC_CONSENSUS` and `H03_LEVEL_ONLY_P300` specifically, using the same rescue-rate-vs-random-floor test used here.
3. **If a conditional selector is ever pursued, gate it on era, not on a pre-target feature.** The only reproducible split found across this and the linked prior audits is calendar era (`POST_2023` vs `PRE_2023`), not any consensus-structure feature. A minimal, honest next experiment would be: does *any* candidate model's rescue rate, conditioned only on era, clear the random floor with a pre-registered, multiplicity-corrected test? This is a narrower, cheaper test than the pre-target-feature screen already run here and in [[b649-track-b-static-consensus-error-atlas-r1]], both of which came back negative on feature-conditioning.

## MOST_IMPORTANT_NEW_INFORMATION

**The pooled "many weak B649 experiments together beat STATIC_CONSENSUS by 30–50 points" result is a ticket-diversification illusion, and correcting for it shows the opposite of naive intuition: the real models are *more* redundant with each other than random tickets would be, not more complementary.** Seventeen genuinely independent random single tickets would out-cover STATIC_CONSENSUS's failures better (93.8% theoretical oracle) than the 17 real weak-signal series actually did (73.0% observed) on the identical 300-target window. This is a new, previously unstated fact — none of the individual Level-1 reports could see it because each one only compares itself to STATIC_CONSENSUS or to its own exposure-matched random control, never to the *other* Level-1 experiments' outputs. It reframes the open question for Track D: the bottleneck is not "we haven't found the right weak model yet," it is "the weak models we keep building are correlated with each other via the shared 133-strategy substrate," which points research effort toward sourcing genuinely disjoint signal rather than testing more variations on the same feature base.

---

## Caveats and scope boundaries

- Every number above is retrospective/historical replay evidence on already-realized draws, exactly as the underlying Level-1 reports themselves state. Nothing here is prospective evidence, a betting claim, or production authorization.
- `H01`, `H06`/`T1_H06_*`, and `H09` figures are reported for context only and are explicitly excluded from the oracle/rescuer/complementarity headline numbers because their ticket exposure differs from STATIC_CONSENSUS's single ticket.
- `H05` and `H08` are cited only from their own sealed headline deltas (both effectively zero, CIs crossing zero / all negative respectively); no new computation was performed on their large raw files.
- `H04` is genuinely `NOT_COMPARABLE` — it produced calibrated probabilities, not a ticket or outcome, so no amount of post-processing here can make it target-level comparable without generating a *new* number-selection projection, which this task's Packet forbids (no rerunning/retuning old experiments).
- Pairwise error-correlation numbers use the phi coefficient (Pearson correlation on 0/1 success indicators) on each block's own model set; none of the "most complementary" correlations survive a Bonferroni correction for the number of pairs tested, and are reported as descriptive discovery output only, per the Packet's "no large AutoML, only lightweight pre-target cluster discovery" instruction.
- Consistent with [[biglotto-uniformity-audit-and-baseline-contamination]] and [[b649-track-d-static-consensus-failure-mode-r1]]: any future feature or model built on this population should continue to check era/format-regime homogeneity before trusting a marginal effect; the BROAD_1095 population used here is `674 PRE_2023 / 421 POST_2023` and was reported split-aware throughout.
