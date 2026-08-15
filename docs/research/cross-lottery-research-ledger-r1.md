# Cross-Lottery Research Ledger R1

Status: OPERATIONAL SSOT | generated 2026-08-14 | 10 priors, 18 cells

Source of truth: `docs/research/cross_lottery_research_ledger_r1.json`. This file is generated from it — never hand-edited. Schema and lifecycle: `docs/research/cross-lottery-research-ledger-r1-schema.md`.

## Priors (mechanism-level coverage facts)

| Mechanism class | Lottery | Coverage | Detail |
|---|---|---|---|
| MARGINAL | BIG_LOTTO | `DIRECTLY_TESTED` | Main-ball and special-ball per-number frequency, 49+49 tests, Holm-corrected. |
| POSITIONAL | BIG_LOTTO | `DIRECTLY_TESTED` | 6-rank order-statistic test, exact-variance z-test per rank. |
| JOINT_PAIRWISE | BIG_LOTTO | `DIRECTLY_TESTED` | 1,176 pair co-occurrence tests, Holm-corrected. |
| SERIAL_FIRST_ORDER | BIG_LOTTO | `DIRECTLY_TESTED` | Non-overlapping consecutive-pair overlap vs. exact hypergeometric. |
| TEMPORAL_REGIME_COARSE | BIG_LOTTO | `PARTIALLY_TESTED` | 8 fixed contiguous eras, sum-of-six only -- not a change-point search. |
| CONDITIONAL | BIG_LOTTO | `DIRECTLY_TESTED` | Phase 0 H04/H07-CONDITIONAL (recency: last-seen-gap + was-in-previous-draw) directly tests this mechanism class; see cells below. Broader conditional-state definitions beyond this one design remain untested. |
| CHANGE_POINT | BIG_LOTTO | `NOT_TESTED` | No change-point/regime-shift search exists at any resolution. |
| HIGHER_ORDER_INTERACTION | BIG_LOTTO | `NOT_TESTED` | Only pairwise (2-number) joint structure was tested; no triples+. |
| MULTI_LAG_SERIAL | BIG_LOTTO | `NOT_TESTED` | Only lag-1 (adjacent draw) serial dependence was tested. |
| TICKET_LEVEL_RESIDUAL | BIG_LOTTO | `NOT_TESTED` | The audit is entirely about the draw-generating process, not any strategy's predictions against it. |

## Hypothesis cells by lottery

| Hypothesis family | BIG_LOTTO | DAILY_539 | POWER_LOTTO (z1/z2) | Next priority |
|---|---|---|---|---|
| H07_H19_CHANGE_POINT_TRIGGERED_ALLOCATION | WEAK_SIGNAL (unverified) | UNTESTED | UNTESTED / UNTESTED | HIGH |
| H09_H21_CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION | WEAK_SIGNAL (unverified) | UNTESTED | UNTESTED / UNTESTED | HIGH |
| H01_CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR | WEAK_SIGNAL (unverified) | UNTESTED | UNTESTED / UNTESTED | MEDIUM |
| H05_H10_DIRECT_TICKET_LEVEL_RESIDUAL_SCORING | WEAK_SIGNAL (unverified) | UNTESTED | UNTESTED / UNTESTED | MEDIUM |
| H08_H12_TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS | NO_SIGNAL (unverified) | UNTESTED | UNTESTED / UNTESTED | MEDIUM |
| DIVERSIFICATION | SIDON_BELOW_FRONTIER_MARGIN | OUTPERFORMS_RANDOM_EXPECTED_COVERAGE | OUTPERFORMS_RANDOM_EXPECTED_COVERAGE / UNTESTED | MEDIUM |
| H03_H04_MULTI_WINDOW_SLOPE_ACCELERATION | NO_SIGNAL (unverified) | UNTESTED | UNTESTED / UNTESTED | LOW |
| REGIME_CHANGE_POINT | NO_EVIDENCE_OF_REGIME_CHANGE | UNTESTED | UNTESTED / UNTESTED | LOW |
| H04_H07_CALIBRATED_PER_NUMBER_PROBABILITIES | POSITIVE_WITHIN_NULL_RANGE | POSITIVE_WITHIN_NULL_RANGE | POSITIVE_WITHIN_NULL_RANGE / POSITIVE_WITHIN_NULL_RANGE | NONE |
| H02_H27 | STRUCTURALLY_DEFERRED (unverified) | UNTESTED | UNTESTED / UNTESTED | NONE |
| ALLOCATION_EXPOSURE | STRUCTURALLY_DEFERRED | UNTESTED | UNTESTED / UNTESTED | NONE |

## Replication queue

Positive results awaiting a second lottery before being read as more than lottery-specific. Takes priority over starting a new discovery-queue mechanism in the same lottery.

| Cell | Lottery | Classification | Next priority |
|---|---|---|---|
| `DIVERSIFICATION_COVERAGE_B649_V1__BIG_LOTTO` | BIG_LOTTO | OUTPERFORMS_RANDOM_EXPECTED_COVERAGE | MEDIUM |
| `DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539` | DAILY_539 | OUTPERFORMS_RANDOM_EXPECTED_COVERAGE | MEDIUM |
| `DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO` | BIG_LOTTO | SIDON_BELOW_FRONTIER_MARGIN | MEDIUM |

## Full cell detail

### `H01_META_SELECTOR__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: ALLOCATION
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `WEAK_SIGNAL` | decision_state: `DO_NOT_ADVANCE`
- retest_eligible: True
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H03_H04_MULTI_WINDOW__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: TEMPORAL_REGIME_COARSE
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `NO_SIGNAL` | decision_state: `DO_NOT_ADVANCE`
- retest_eligible: True
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H07_H19_CHANGE_POINT__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: CHANGE_POINT
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `WEAK_SIGNAL` | decision_state: `DO_NOT_ADVANCE`
- retest_eligible: True
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H09_H21_NEGATIVE_SUPPRESSION__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: ALLOCATION
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `WEAK_SIGNAL` | decision_state: `DO_NOT_ADVANCE`
- retest_eligible: True
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H05_H10_TICKET_RESIDUAL__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: TICKET_LEVEL_RESIDUAL
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `WEAK_SIGNAL` | decision_state: `DO_NOT_ADVANCE`
- retest_eligible: True
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H04_H07_MARGINAL_LEGACY__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: MARGINAL
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `WEAK_SIGNAL_INSUFFICIENT_DISCRIMINATION` | decision_state: `DO_NOT_ADVANCE`
- retest_eligible: True
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H08_H12_TEMPORAL_HYPERGRAPH__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: STRUCTURAL
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `NO_SIGNAL` | decision_state: `DO_NOT_ADVANCE`
- retest_eligible: True
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H02_H27__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: STRUCTURAL
- record_state: `REPORTED_LEGACY`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `REPORTED_UNVERIFIED`
- descriptive_classification: `STRUCTURALLY_DEFERRED` | decision_state: `STRUCTURALLY_DEFERRED`
- retest_eligible: False
- source: Carried from this program's original cross-lottery planning conversation (pre-Phase -1). NOT independently re-verified against a sealed artifact in this or any tracked session -- evidence_grade reflects this honestly. Do not treat this cell's descriptive_classification as re-confirmed.

### `H04_H07_CONDITIONAL__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: CONDITIONAL
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `POSITIVE_WITHIN_NULL_RANGE` | decision_state: `DO_NOT_ADVANCE`
- primary_endpoint: -0.000156 (Brier(CALIBRATED_CONDITIONAL) - Brier(CAUSAL_MARGINAL_EMPIRICAL), pooled over evaluation folds 3-5)
- null_replay_percentile: 0.41
- artifacts: docs/research/phase0-h04-conditional-preregistration.md, docs/research/phase0-h04-conditional-report.md, docs/research/phase0-results/big_lotto.json
- retest_eligible: True
- source: Computed and independently verified in this session (Phase 0).

### `H04_H07_CONDITIONAL__DAILY_539`

- lottery: DAILY_539
- mechanism_class: CONDITIONAL
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `POSITIVE_WITHIN_NULL_RANGE` | decision_state: `DO_NOT_ADVANCE`
- primary_endpoint: -0.000040 (Brier(CALIBRATED_CONDITIONAL) - Brier(CAUSAL_MARGINAL_EMPIRICAL), pooled over evaluation folds 3-5)
- null_replay_percentile: 0.77
- artifacts: docs/research/phase0-h04-conditional-preregistration.md, docs/research/phase0-h04-conditional-report.md, docs/research/phase0-results/daily_539.json
- retest_eligible: True
- source: Computed and independently verified in this session (Phase 0).

### `H04_H07_CONDITIONAL__POWER_LOTTO_zone1`

- lottery: POWER_LOTTO / zone1
- mechanism_class: CONDITIONAL
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `POSITIVE_WITHIN_NULL_RANGE` | decision_state: `DO_NOT_ADVANCE`
- primary_endpoint: -0.000222 (Brier(CALIBRATED_CONDITIONAL) - Brier(CAUSAL_MARGINAL_EMPIRICAL), pooled over evaluation folds 3-5)
- null_replay_percentile: 0.34
- artifacts: docs/research/phase0-h04-conditional-preregistration.md, docs/research/phase0-h04-conditional-report.md, docs/research/phase0-results/power_lotto.json
- retest_eligible: True
- source: Computed and independently verified in this session (Phase 0).

### `H04_H07_CONDITIONAL__POWER_LOTTO_zone2`

- lottery: POWER_LOTTO / zone2
- mechanism_class: CONDITIONAL
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `POSITIVE_WITHIN_NULL_RANGE` | decision_state: `DO_NOT_ADVANCE`
- primary_endpoint: -0.000100 (Brier(CALIBRATED_CONDITIONAL) - Brier(CAUSAL_MARGINAL_EMPIRICAL), pooled over evaluation folds 3-5)
- null_replay_percentile: 0.54
- artifacts: docs/research/phase0-h04-conditional-preregistration.md, docs/research/phase0-h04-conditional-report.md, docs/research/phase0-results/power_lotto.json
- retest_eligible: True
- source: Computed and independently verified in this session (Phase 0).

### `REGIME_CHANGE_POINT_CUSUM_B649_V1__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: CHANGE_POINT
- related_legacy_evidence (not the same design): `H07_H19_CHANGE_POINT__BIG_LOTTO`
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `NO_EVIDENCE_OF_REGIME_CHANGE` | decision_state: `DO_NOT_ADVANCE`
- global_mechanism_status: `RETAINED_FOR_FUTURE_GENERATIONS` | exhausted: False
- primary_endpoint: +964.000000 (global trimmed max-|CUSUM| of per-draw sum-of-six vs. exact fair-6/49 null)
- null_replay_percentile: 0.10
- artifacts: docs/research/matrix-native-results/regime-changepoint-cusum-b649-v1-preregistration.md, docs/research/matrix-native-results/regime-changepoint-cusum-b649-v1-preregistration-hash.json, docs/research/matrix-native-results/regime-changepoint-cusum-b649-v1-result.json, docs/research/matrix-native-results/regime-changepoint-cusum-b649-v1-attempt-ledger.json, docs/research/matrix-native-results/regime-changepoint-cusum-b649-v1-report.md
- retest_eligible: True
- source: Computed and independently verified in this session (Strategy Matrix Phase 1). Not the same design as legacy H07_H19 -- see related_legacy_evidence, whose own grade remains REPORTED_UNVERIFIED and is unaffected by this cell.

### `ALLOCATION_EXPOSURE_EFFICIENCY_B649_V1__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: ALLOCATION
- related_legacy_evidence (not the same design): `H09_H21_NEGATIVE_SUPPRESSION__BIG_LOTTO`
- record_state: `DESIGN_ABANDONED`
- preregistration_grade: `NOT_PREREGISTERED_UNDER_R1` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `STRUCTURALLY_DEFERRED` | decision_state: `STRUCTURALLY_DEFERRED`
- global_mechanism_status: `RETAINED_FOR_FUTURE_GENERATIONS` | exhausted: False
- experiment_run: False | result: `NOT_FAILED` (a deferral, not a negative finding)
- deferral_reason: PURE_EXPOSURE_EFFECT_NOT_IDENTIFIABLE_SEPARATELY_FROM_PORTFOLIO_GEOMETRY_WITHOUT_AN_EXTERNAL_UTILITY_COST_CONTRACT -- for k uniformly random distinct tickets, exact coverage equals the verified Q_random_m(k) closed form by construction; any fixed portfolio's excess over that baseline is attributable to its geometry, never to k alone, so ALLOCATION_EXPOSURE has no residual content separate from DIVERSIFICATION once PRIZE_VALUE_EFFICIENCY is (already, separately) confirmed data-infeasible. Verified by the task's own author, not merely asserted.
- artifacts: docs/research/allocation-exposure-efficiency-b649-v1-preregistration.md
- retest_eligible: True
- source: Reusable primitives preserved, not discarded: exact C(49,6) enumeration feasibility and the verified Q_random_m(k) closed form (src/lottolab/research/exact_coverage_baseline.py, 18 tests) carry forward directly into DIVERSIFICATION_COVERAGE_B649_V1.

### `DIVERSIFICATION_COVERAGE_B649_V1__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: STRUCTURAL
- evidence_type: `EXACT_COMBINATORIAL` | uncertainty: NONE -- exact enumeration / exact closed form
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `OUTPERFORMS_RANDOM_EXPECTED_COVERAGE` | decision_state: `REPLICATION_REQUIRED`
- global_mechanism_status: `RETAIN_AND_REPLICATE` | exhausted: False
- predictive_advantage: `NOT_TESTED` | prize_value_advantage: `NOT_TESTED` | economic_optimality: `NOT_TESTED`
- primary_endpoint: +0.013295 (D_3(20) = Q_sidon_M3+(20) - Q_random_expected_M3+(20), exact combinatorics, exact value 232873368979434815903103141927996609520609913134520474550364154631313559621962152611930026635215720204285651202/17516035489352387109541999036559473464103481230202915287248593610270558339703433004585795393675081781900509821117. Sealed artifact records this cell's classification as `OUTPERFORMS_RANDOM_COVERAGE` verbatim; `OUTPERFORMS_RANDOM_EXPECTED_COVERAGE` is this ledger's Owner-clarified summary label for the identical result -- see _CLASSIFICATION_LABEL_CLARIFICATION in this file.)
- artifacts: docs/research/matrix-native-results/diversification-coverage-b649-v1-preregistration.md, docs/research/matrix-native-results/diversification-coverage-b649-v1-preregistration-hash.json, docs/research/matrix-native-results/diversification-coverage-b649-v1-result.json, docs/research/matrix-native-results/diversification-coverage-b649-v1-attempt-ledger.json, docs/research/matrix-native-results/diversification-coverage-b649-v1-report.md
- retest_eligible: True
- source: Computed and independently verified in this session (Strategy Matrix Phase 1) via complete C(49,6) enumeration, exact fractions.Fraction arithmetic, no simulation. Split cleanly off ALLOCATION_EXPOSURE_EFFICIENCY_B649_V1 (DESIGN_ABANDONED) once exposure and geometry were correctly told apart. Makes no predictive-advantage or prize-value claim.

### `DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539`

- lottery: DAILY_539
- mechanism_class: STRUCTURAL
- evidence_type: `EXACT_COMBINATORIAL` | uncertainty: NONE -- exact enumeration / exact closed form
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `OUTPERFORMS_RANDOM_EXPECTED_COVERAGE` | decision_state: `REPLICATION_REQUIRED`
- global_mechanism_status: `RETAIN_AND_REPLICATE` | exhausted: False
- predictive_advantage: `NOT_TESTED` | prize_value_advantage: `NOT_TESTED` | economic_optimality: `NOT_TESTED`
- primary_endpoint: +0.009292 (D_3(20) = Q_sidon_M3+(20) - Q_random_expected_M3+(20), exact combinatorics, exact value 7936665663334624487805755106998757032043297207603505890465577337229935222707753273/854116625879098836238200337908424671905738564473126295698485942275321822152736920680. Native replication of DIVERSIFICATION_COVERAGE_B649_V1 into DAILY_539's 5/39 structure; classification terminology locked correctly from the start, no ledger-layer relabeling needed (contrast DIVERSIFICATION_COVERAGE_B649_V1's primary_endpoint_definition).)
- artifacts: docs/research/matrix-native-results/diversification-coverage-t539-v1-preregistration.md, docs/research/matrix-native-results/diversification-coverage-t539-v1-preregistration-hash.json, docs/research/matrix-native-results/diversification-coverage-t539-v1-result.json, docs/research/matrix-native-results/diversification-coverage-t539-v1-attempt-ledger.json, docs/research/matrix-native-results/diversification-coverage-t539-v1-report.md
- retest_eligible: True
- source: Computed and independently verified in this session (Strategy Matrix Phase 2) via complete C(39,5) enumeration, exact fractions.Fraction arithmetic, no simulation. Native replication cell: independently derived and independently verified Sidon base set in Z_39, not copied from B649's base set (see diversification-coverage-t539-v1-preregistration.md Sec 3 for the wording correction on that point). Makes no predictive-advantage or prize-value claim.

### `DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1`

- lottery: POWER_LOTTO / zone1
- mechanism_class: STRUCTURAL
- evidence_type: `EXACT_COMBINATORIAL` | uncertainty: NONE -- exact enumeration / exact closed form
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `OUTPERFORMS_RANDOM_EXPECTED_COVERAGE` | decision_state: `ADVANCE_TO_NEXT_LEVEL`
- global_mechanism_status: `RETAIN_AND_REPLICATE` | exhausted: False
- predictive_advantage: `NOT_TESTED` | prize_value_advantage: `NOT_TESTED` | economic_optimality: `NOT_TESTED`
- primary_endpoint: +0.059630 (D_3(20) = Q_sidon_M3+(20) - Q_random_expected_M3+(20), exact combinatorics, exact value 7853527786631591480259845893250386474155474781980381800465203448861951641046516894880073018607706299/131704396033130947118708343818273549765660895754369989224055944711504240598168786106602790393615591370. Native replication of DIVERSIFICATION_COVERAGE_B649_V1 and DIVERSIFICATION_COVERAGE_T539_V1 into POWER_LOTTO Zone-1's 6/38 structure (Zone-2 1-of-8 out of scope; see zone2 NOT_TESTED note below). Constructor required a completed backtracking search, not plain greedy: 38 is the first even pool size this mechanism was run against, and 19=38/2 is self-inverse, which plain greedy cannot satisfy (see preregistration Sec 3). Q_sidon(M6) == Q_random(M6) exactly for every k (D_6(k)=0), the same degenerate exact-match case as T539's M5: with draw_size=6, M6 means the draw equals a ticket outright, which no fixed-vs-random geometry distinction can affect.)
- artifacts: docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-preregistration.md, docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-preregistration-hash.json, docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-result.json, docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-attempt-ledger.json, docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-report.md
- retest_eligible: True
- source: Computed and independently verified in this session (Strategy Matrix Phase 3) via complete C(38,6) = 2,760,681-draw enumeration, exact fractions.Fraction arithmetic, no simulation. Native replication cell: independently derived and independently verified Sidon-type base set in Z_38 (see diversification-coverage-p638-zone1-v1-preregistration.md Sec 3 for the even-modulus obstruction and its resolution), not copied from B649's or T539's base set. Makes no predictive-advantage or prize-value claim. decision_state is ADVANCE_TO_NEXT_LEVEL rather than REPLICATION_REQUIRED because this repository has exactly three lottery types (BIG_LOTTO, DAILY_539, POWER_LOTTO) and this single-zone diversification mechanism has now been natively replicated, positively, in all three -- CROSS_LOTTERY_REPLICATION_STATUS: SUPPORTED_IN_3_NATIVE_LOTTERY_STRUCTURES. This does not imply a universal predictive mechanism, a forecasting edge, economic optimality, or profitability -- the evidence type remains EXACT_COMBINATORIAL portfolio-geometry coverage, not forecasting. The B649 and T539 sibling cells' own decision_state fields are left unchanged (REPLICATION_REQUIRED, as sealed at the time), per the ledger's no-retroactive-edit rule.

### `DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1__BIG_LOTTO`

- lottery: BIG_LOTTO
- mechanism_class: STRUCTURAL
- evidence_type: `EXACT_COMBINATORIAL_BOUNDED_SEARCH` | uncertainty: NONE for Q_X(k) values (exact, via the parity-verified fast evaluator, not sampled/simulated). The optimizer SEARCH itself is BOUNDED (56,730/65,610 evaluations used across the ladder), not exhaustive -- BEST_FOUND_Q(k) is a found maximum among 3 disclosed arms under one fixed seeded budget, not a proven optimum.
- record_state: `SEALED`
- preregistration_grade: `R1_PREREGISTERED` | evidence_grade: `LOCAL_VERIFIED`
- descriptive_classification: `SIDON_BELOW_FRONTIER_MARGIN` | decision_state: `REPLICATION_REQUIRED`
- global_mechanism_status: `RETAIN_AND_REPLICATE` | exhausted: False
- predictive_advantage: `NOT_TESTED` | prize_value_advantage: `NOT_TESTED` | economic_optimality: `NOT_TESTED`
- primary_endpoint: +0.015571 (SIDON_FRONTIER_GAP(20) = BEST_FOUND_Q_M3+(20) - Q_sidon_M3+(20), exact combinatorics via the c7e3b4a fast evaluator (parity-verified against complete C(49,6) enumeration). Best-found arm at k=20 is C (RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1, a bounded seeded search, 56,730/65,610 evaluations used). FRONTIER_CAPTURE_RATIO(20) = 0.46057 -- Sidon captures only 46% of the random-relative improvement this bounded search found at k=20 (the largest tested k); the ratio was lower at every smaller k (16-30%). SIDON_FRONTIER_CLASSIFICATION: SIDON_BELOW_FRONTIER_MARGIN at every k>1 (FRONTIER_CAPTURE_RATIO < 0.90 everywhere). Arm B (GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1, no Sidon/difference-set algebra) also exceeds -- not just reproduces -- Sidon's own gain over random at every k (1.64x-6.08x).)
- artifacts: docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-preregistration.md, docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-preregistration-hash.json, docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-result.json, docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-attempt-ledger.json, docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-report.md
- retest_eligible: True
- source: Computed and independently verified in this session (Strategy Matrix Phase 5, Generation 2) via the fast-evaluator-backed (c7e3b4a, parity-verified) bounded_coverage_optimizer_fast module, at real B649 scale for the first time -- neither arm B nor arm C had been invoked at (49,6) before this task (971b97b, design only). Sidon-shift (arm A, the sealed DIVERSIFICATION_COVERAGE_B649_V1 reference) turned out to be meaningfully below the frontier this one bounded search found, not near it. Both challenger arms are ELIGIBLE_FOR_T539_P638_REPLICATION per 971b97b Sec 11's three-condition rule. Makes no predictive-advantage or prize-value claim; GLOBAL_OPTIMUM_STATUS remains UNKNOWN -- the search sampled a disclosed, bounded, vanishingly small fraction of the C(49,6)=13,983,816 candidate space per slot, never exhaustive.
