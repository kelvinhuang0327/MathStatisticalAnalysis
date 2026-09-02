# B649 Track D Remaining-18 Level-1 Fast-Falsification Specs R1

TASK_ID: `B649_TRACK_D_REMAINING_18_OPEN_HYPOTHESES_DEEP_AUDIT_R1`

STATUS: DESIGN_ONLY — NOT RUN

All targets, comparators, folds, feature windows, ticket budgets, and multiplicity families below must be frozen before outcomes are opened. A positive Level-1 result is permission to design a fuller Track B experiment, not evidence of a deployable lottery edge.

## H02 — Complementary-error graph across strategies

- HYPOTHESIS_ID: `H02`
- MINIMUM_REQUIRED_INPUT: Sealed per-draw outcomes and matched baselines for a fixed subset of strategies with common causal coverage, preserved native tickets, family labels, and chronology.
- DERIVED_FEATURES: Strict-prior paired residual covariance, sign-complementarity, residual tail-dependence, graph edges, communities, and minimum-cover portfolios.
- TARGET: Fixed-budget next-block `OFFICIAL_ANY_PRIZE` paired delta, with M3+ hit depth as the single secondary family.
- COMPARATOR: One discovery-frozen static strategy, static equal-weight consensus, graph with shuffled residual histories, and exact same-ticket random.
- CAUSAL_GUARD: Build every edge from draws strictly before its evaluation block; freeze the eligible strategy set without using H01 results or target outcomes.
- MINIMUM_WINDOWS: 750-draw construction window plus at least three non-overlapping chronological evaluation blocks; include 300/50 sensitivity without selecting the winner post hoc.
- OUTPUT_METRIC: Paired primary-rate delta and confidence interval; secondary M3+ delta under a prespecified multiplicity correction.
- EXPECTED_RUNTIME: 1–3 CPU hours for a bounded 20-strategy subset.
- EXPECTED_COMPUTE: MEDIUM; covariance/graph construction dominates, no new prediction model required.
- PROMISING_SIGNAL_RULE: Primary delta is positive in each of the final two blocks, beats both frozen-static and shuffled-graph comparators, and its adjusted lower confidence bound is above zero on the pooled held-out blocks.
- NO_SIGNAL_RULE: Any primary sign reversal across final blocks, failure to beat the frozen-static comparator, or no gain over the shuffled-graph control.
- NEXT_IF_POSITIVE: Preregister one graph estimator and one portfolio rule for a full blocked Track B test.
- NEXT_IF_NEGATIVE: Retain the scoped negative for this residual definition; do not close other complementarity metrics.

## H03 — Mixture-of-experts with out-of-fold gating

- HYPOTHESIS_ID: `H03`
- MINIMUM_REQUIRED_INPUT: Sealed causal candidate portfolios, prior-only outcomes, four frozen regime descriptors, matched baselines, and fixed ticket budget.
- DERIVED_FEATURES: Out-of-fold expert residuals, regime interactions, disagreement, and a small deterministic gate probability vector.
- TARGET: Next-block expert allocation maximizing prespecified `OFFICIAL_ANY_PRIZE` at five tickets.
- COMPARATOR: Discovery-frozen best expert, static equal allocation, and one simple rule-based regime gate.
- CAUSAL_GUARD: Nested blocked folds; an outcome may train only later targets; no H01 intermediate or final result may enter model or hyperparameter selection.
- MINIMUM_WINDOWS: At least four expanding folds with 750 prior draws before the first scored target and two untouched terminal blocks.
- OUTPUT_METRIC: Paired primary delta versus each comparator, gate turnover, and effective expert count.
- EXPECTED_RUNTIME: 2–6 CPU hours.
- EXPECTED_COMPUTE: MEDIUM; restrict to linear/softmax or shallow-tree gating.
- PROMISING_SIGNAL_RULE: Beats both static comparators in both terminal blocks, positive pooled adjusted lower bound, and no collapse to one expert in more than 90% of targets.
- NO_SIGNAL_RULE: Fails either terminal-block comparison or gains disappear against the simple regime gate.
- NEXT_IF_POSITIVE: Freeze the smallest successful gate for independent confirmation.
- NEXT_IF_NEGATIVE: Close only the tested gate class; retain nonparametric or different-information-set MoE variants.

## H05 — Conditional consensus by regime/state

- HYPOTHESIS_ID: `H05`
- MINIMUM_REQUIRED_INPUT: Fixed strategy tickets, disagreement matrix, frozen causal regime labels, outcomes, and same-ticket baselines.
- DERIVED_FEATURES: Consensus strength, family breadth, prior residual quality, and one frozen state/consensus interaction.
- TARGET: Whether consensus tickets improve five-ticket `OFFICIAL_ANY_PRIZE` only inside the declared state.
- COMPARATOR: Static consensus everywhere, best frozen single strategy, and consensus with permuted state labels.
- CAUSAL_GUARD: State thresholds and consensus membership use only prior draws; one interaction is chosen before target inspection.
- MINIMUM_WINDOWS: 750-draw feature window and at least two terminal blocks with a minimum predeclared number of in-state targets.
- OUTPUT_METRIC: Paired in-state delta, out-of-state placebo delta, and M3+ secondary delta.
- EXPECTED_RUNTIME: 30–90 CPU minutes.
- EXPECTED_COMPUTE: LOW.
- PROMISING_SIGNAL_RULE: Positive adjusted in-state delta in both terminal blocks, no positive placebo effect after state permutation, and no material out-of-state harm when the gate is inactive.
- NO_SIGNAL_RULE: Static consensus performs as well, the state interaction reverses, or permuted labels reproduce the gain.
- NEXT_IF_POSITIVE: Confirm the single frozen interaction on a later untouched block.
- NEXT_IF_NEGATIVE: Record a scoped negative; do not generalize to all conditional ensemble weights.

## H06 — Conditional anti-consensus / minority signal

- HYPOTHESIS_ID: `H06`
- MINIMUM_REQUIRED_INPUT: Fixed producer tickets, cross-producer disagreement, prior residual histories, regime descriptors, and exact baselines.
- DERIVED_FEATURES: Minority support, family-weighted disagreement, recent false-positive concentration, and one frozen activation condition.
- TARGET: Fixed-budget paired hit/prize delta when a minority ticket is substituted for the consensus ticket.
- COMPARATOR: Static anti-consensus, static consensus, no-substitution portfolio, and condition-label permutation.
- CAUSAL_GUARD: Freeze upstream producers and substitution count; compute all errors strictly before the target.
- MINIMUM_WINDOWS: 300- and 750-draw feature versions evaluated on the same two terminal blocks.
- OUTPUT_METRIC: Paired `OFFICIAL_ANY_PRIZE` delta and M3+ delta per substituted ticket.
- EXPECTED_RUNTIME: 30–90 CPU minutes.
- EXPECTED_COMPUTE: LOW.
- PROMISING_SIGNAL_RULE: The frozen conditional substitution beats no-substitution and static anti-consensus in both terminal blocks, with positive adjusted pooled lower bound.
- NO_SIGNAL_RULE: No improvement per substituted ticket, inconsistent signs, or the label-permutation control matches the effect.
- NEXT_IF_POSITIVE: Test one independently frozen minority definition.
- NEXT_IF_NEGATIVE: Close only that condition/substitution contract.

## H08 — Per-number ranking-loss model

- HYPOTHESIS_ID: `H08`
- MINIMUM_REQUIRED_INPUT: Causal 49-number feature/exposure matrix for the seven direct Candidate-K paths or a separately frozen reconstruction, draw outcomes, and chronology.
- DERIVED_FEATURES: Strict-prior number features and a deterministic pairwise/listwise ranking score.
- TARGET: Rank the six next-draw main numbers above non-drawn numbers; downstream tickets use one fixed legality-preserving constructor.
- COMPARATOR: Trailing-frequency rank, untrained exposure rank, and a pointwise non-ranking model with identical features.
- CAUSAL_GUARD: Fit only on earlier draws; freeze feature availability and constructor before downstream evaluation.
- MINIMUM_WINDOWS: Four expanding folds, each with at least 750 training draws, plus one untouched terminal block.
- OUTPUT_METRIC: Mean percentile rank of actual main numbers, top-K recall, and fixed-constructor M3+ delta.
- EXPECTED_RUNTIME: 1–3 CPU hours.
- EXPECTED_COMPUTE: MEDIUM.
- PROMISING_SIGNAL_RULE: Improves mean actual-number rank and top-K recall in every terminal fold and produces a positive M3+ delta without changing ticket budget.
- NO_SIGNAL_RULE: Ranking metrics do not beat both comparators or downstream gain disappears under the fixed constructor.
- NEXT_IF_POSITIVE: Add calibrated probability evaluation without changing the ranking-loss result.
- NEXT_IF_NEGATIVE: Close this feature/loss pairing; retain other causal number-level contracts.

## H09 — Predictive uncertainty / ensemble dispersion

- HYPOTHESIS_ID: `H09`
- MINIMUM_REQUIRED_INPUT: Comparable out-of-fold model/ticket outputs, target outcomes, fixed baselines, and enough repeated predictions to estimate calibration.
- DERIVED_FEATURES: Ensemble dispersion, entropy, disagreement by family, empirical calibration bins, and one abstain/downweight rule.
- TARGET: Predict next-target failure risk and improve a fixed-budget portfolio by conditioning on uncertainty.
- COMPARATOR: Mean ensemble score without uncertainty, raw disagreement without calibration, and randomized abstention at the same rate.
- CAUSAL_GUARD: Calibration curves are fit on prior folds only; abstention/downweight rate is frozen before the terminal block.
- MINIMUM_WINDOWS: At least four blocked calibration folds and two terminal evaluation blocks.
- OUTPUT_METRIC: Brier/log loss for failure risk plus paired portfolio delta at matched ticket budget.
- EXPECTED_RUNTIME: 1–3 CPU hours after comparable outputs exist.
- EXPECTED_COMPUTE: MEDIUM.
- PROMISING_SIGNAL_RULE: Better Brier and log loss than both uncertainty comparators in each terminal block and positive matched-budget portfolio delta.
- NO_SIGNAL_RULE: Dispersion is uncalibrated, no better than raw disagreement, or portfolio improvement vanishes at matched budget.
- NEXT_IF_POSITIVE: Freeze one uncertainty measure and one action rule for confirmation.
- NEXT_IF_NEGATIVE: Close only the tested calibration/action pair.

## H11 — Pair/triple interaction residual after marginal number scores

- HYPOTHESIS_ID: `H11`
- MINIMUM_REQUIRED_INPUT: Sealed pair/triple histories, causal marginal number scores, ticket outcomes, exact baseline, and 392,084-combination authority.
- DERIVED_FEATURES: Pair/triple occurrence residuals after expected counts from marginal scores, sparse shrinkage features, and held-out interaction scores.
- TARGET: Incremental ticket hit depth beyond the frozen marginal number model.
- COMPARATOR: Marginal-only ticket score, raw co-occurrence score, and permutation of interaction residuals within cutoff.
- CAUSAL_GUARD: Marginal model and residuals are trained in nested earlier folds; no target pair/triple enters its own feature history.
- MINIMUM_WINDOWS: 750-draw construction window, 300-draw sensitivity, and at least two untouched terminal blocks.
- OUTPUT_METRIC: Incremental held-out deviance/ranking gain and fixed-budget M3+/prize delta.
- EXPECTED_RUNTIME: 4–12 CPU hours.
- EXPECTED_COMPUTE: HIGH because sparse pair/triple expansion dominates.
- PROMISING_SIGNAL_RULE: Positive incremental score in both terminal blocks, gain over raw co-occurrence, and positive fixed-budget M3+ delta after correction.
- NO_SIGNAL_RULE: Residual terms add no held-out score or downstream gain, or permutation matches the effect.
- NEXT_IF_POSITIVE: Freeze the smallest stable interaction basis for a full ticket-level test.
- NEXT_IF_NEGATIVE: Close the tested residualization/window only; do not close all higher-order structure.

## H13 — Temporal graph change rather than static graph score

- HYPOTHESIS_ID: `H13`
- MINIMUM_REQUIRED_INPUT: Strict-prior pair/triple histories, rolling graph snapshots, target outcomes, and fixed ticket constructor.
- DERIVED_FEATURES: Edge-weight deltas, community turnover, centrality velocity, motif birth/death, and graph-change anomaly score.
- TARGET: Whether graph change predicts next-block number/ticket outcomes beyond graph level.
- COMPARATOR: Static graph score, trailing-frequency level, and time-shuffled graph deltas.
- CAUSAL_GUARD: Snapshot endpoints precede targets; window and graph thresholds are frozen without retrospective breakpoint selection.
- MINIMUM_WINDOWS: 50/300/750 graph snapshots with at least three chronological terminal blocks.
- OUTPUT_METRIC: Incremental held-out ranking/deviance and fixed-budget M3+ delta.
- EXPECTED_RUNTIME: 2–6 CPU hours.
- EXPECTED_COMPUTE: MEDIUM.
- PROMISING_SIGNAL_RULE: Graph deltas beat static graph and time-shuffled controls in every terminal block, with positive pooled downstream delta.
- NO_SIGNAL_RULE: Static levels explain the same signal, signs reverse, or shuffled deltas perform equivalently.
- NEXT_IF_POSITIVE: Confirm one graph-change feature family only.
- NEXT_IF_NEGATIVE: Record the scoped negative while retaining different graph definitions.

## H15 — Multi-objective hit-depth / coverage / overlap / payout-proxy optimizer

- HYPOTHESIS_ID: `H15`
- MINIMUM_REQUIRED_INPUT: Fixed candidate tickets/scores, hit-depth outcomes, exact overlap geometry, payout proxy, and matched-budget baselines.
- DERIVED_FEATURES: One preregistered normalized objective combining score, coverage, overlap penalty, hit depth, and payout proxy.
- TARGET: Improve held-out prize/hit-depth at fixed ticket count without degrading coverage beyond a frozen bound.
- COMPARATOR: Score-only selection, overlap-only diversification, and the existing fixed portfolio optimizer.
- CAUSAL_GUARD: Objective weights are chosen on discovery only and frozen; terminal outcomes never tune the Pareto trade-off.
- MINIMUM_WINDOWS: Discovery, validation, and two terminal chronological blocks at one ticket budget.
- OUTPUT_METRIC: Paired prize-rate delta, M3+ delta, unique-number coverage, and mean pairwise overlap.
- EXPECTED_RUNTIME: 2–8 CPU hours.
- EXPECTED_COMPUTE: MEDIUM_HIGH, depending on candidate pool size.
- PROMISING_SIGNAL_RULE: Pareto-dominates every comparator on both terminal blocks or improves the primary outcome with all prespecified geometry constraints satisfied.
- NO_SIGNAL_RULE: No Pareto improvement, primary gain depends on retuned weights, or geometry improves without outcome gain.
- NEXT_IF_POSITIVE: Freeze the single objective vector for confirmation.
- NEXT_IF_NEGATIVE: Close the exact weight/constraint contract, not multi-objective optimization as a family.

## H16 — Joint main-number/special-number conditional model

- HYPOTHESIS_ID: `H16`
- MINIMUM_REQUIRED_INPUT: Main and special draw histories, exact joint prize rules/baseline, chronology, and one legal full-ticket constructor.
- DERIVED_FEATURES: Joint/factorized conditional probabilities, special-given-main features, and calibrated joint ticket score.
- TARGET: Joint held-out likelihood and official prize probability for a legal ticket.
- COMPARATOR: Independent main/special marginals, main-only model with random special number, and exact IID legal baseline.
- CAUSAL_GUARD: All conditional estimates use earlier draws; the constructor and smoothing prior are frozen before holdout.
- MINIMUM_WINDOWS: Four expanding folds with at least 750 prior draws and one untouched terminal block.
- OUTPUT_METRIC: Joint log loss/Brier score and matched-budget official-prize delta.
- EXPECTED_RUNTIME: 2–6 CPU hours once the legal joint contract exists.
- EXPECTED_COMPUTE: MEDIUM.
- PROMISING_SIGNAL_RULE: Beats factorized marginals on both probabilistic metrics in every terminal fold and improves matched-budget official-prize outcome.
- NO_SIGNAL_RULE: Conditional dependence adds no held-out calibration/likelihood gain or cannot improve the legal-ticket comparator.
- NEXT_IF_POSITIVE: Build a separately versioned joint-output adapter for confirmation.
- NEXT_IF_NEGATIVE: Close the tested conditional factorization only.

## H18 — HMM latent-regime gating

- HYPOTHESIS_ID: `H18`
- MINIMUM_REQUIRED_INPUT: Frozen regime-feature table, strictly ordered draws, candidate outcomes, and matched baselines.
- DERIVED_FEATURES: Filtered latent-state probabilities from a small deterministic HMM and one state-to-allocation map.
- TARGET: Next-block expert/portfolio outcome conditional on filtered state.
- COMPARATOR: Fixed empirical regime bands, no-gate allocation, and state labels permuted within training blocks.
- CAUSAL_GUARD: Filtering—not smoothing—at evaluation time; state count and initialization are frozen in discovery.
- MINIMUM_WINDOWS: At least four expanding folds, 750 prior draws before scoring, and two terminal blocks.
- OUTPUT_METRIC: Held-out feature likelihood plus paired allocation/prize delta.
- EXPECTED_RUNTIME: 4–12 CPU hours.
- EXPECTED_COMPUTE: HIGH relative to rule-based regime gates.
- PROMISING_SIGNAL_RULE: Stable state interpretation across folds, better held-out likelihood than empirical bands, and positive allocation delta in both terminal blocks.
- NO_SIGNAL_RULE: State labels are unstable, likelihood does not improve, or allocation gain disappears versus fixed bands.
- NEXT_IF_POSITIVE: Freeze one state count and one allocation map for confirmation.
- NEXT_IF_NEGATIVE: Close the tested HMM parameterization, not all latent-state models.

## H20 — Entropy/distribution-shift anomaly gating

- HYPOTHESIS_ID: `H20`
- MINIMUM_REQUIRED_INPUT: Strict-prior 50/300/750 draw distributions, four frozen regime axes, candidate outcomes, and exact baselines.
- DERIVED_FEATURES: Entropy delta, Jensen–Shannon divergence, tail-mass shift, and one frozen anomaly indicator.
- TARGET: Improve allocation only after a causally observed distribution-shift anomaly.
- COMPARATOR: No gate, fixed regime bands, and anomaly timestamps permuted at the same event rate.
- CAUSAL_GUARD: Threshold and event rate are fixed on discovery; target outcomes cannot define anomalies.
- MINIMUM_WINDOWS: 50/300/750 features, at least two terminal blocks, and a prespecified minimum event count.
- OUTPUT_METRIC: Paired in-event prize/hit delta, out-of-event placebo delta, and event-rate stability.
- EXPECTED_RUNTIME: 30–120 CPU minutes.
- EXPECTED_COMPUTE: LOW.
- PROMISING_SIGNAL_RULE: Positive adjusted in-event delta in both terminal blocks, no comparable permuted-event effect, and stable event rate.
- NO_SIGNAL_RULE: Too few frozen events, sign reversal, or permutation/fixed-band comparator matches the result.
- NEXT_IF_POSITIVE: Confirm one anomaly measure and threshold.
- NEXT_IF_NEGATIVE: Close only that measure/threshold/window tuple.

## H22 — Conditional/nested exact null and paired counterfactual calibration

- HYPOTHESIS_ID: `H22`
- MINIMUM_REQUIRED_INPUT: One frozen adaptive selector, its paired no-action counterfactual, exact ticket/null combinatorics, and chronology.
- DERIVED_FEATURES: Nested-fold selection record, conditional null distribution, paired target deltas, and familywise correction ledger.
- TARGET: Valid type-I error/coverage and calibrated evidence for the adaptive question.
- COMPARATOR: Unconditional exact null and non-nested post-selection analysis.
- CAUSAL_GUARD: Selector is fit only inside each training fold; null simulation/conditioning reproduces the complete selection rule.
- MINIMUM_WINDOWS: At least four outer chronological folds plus enough null replications for a prespecified Monte Carlo error bound.
- OUTPUT_METRIC: Empirical type-I error, confidence-interval coverage, p/e-value calibration, and paired-effect estimate.
- EXPECTED_RUNTIME: 1–3 CPU hours for a bounded selector.
- EXPECTED_COMPUTE: MEDIUM.
- PROMISING_SIGNAL_RULE: Nominal error/coverage is met within the frozen tolerance and the nested analysis remains computationally feasible; any predictive claim must separately survive it.
- NO_SIGNAL_RULE: Conditional calibration is materially anti-conservative, unstable, or infeasible at the required precision.
- NEXT_IF_POSITIVE: Make the nested/paired layer mandatory for the linked Track B hypothesis.
- NEXT_IF_NEGATIVE: Do not promote that linked adaptive claim until a valid null is designed.

## H23 — LSTM as residual/meta-feature, not direct ticket generator

- HYPOTHESIS_ID: `H23`
- MINIMUM_REQUIRED_INPUT: Strictly ordered draw/strategy histories, fixed residual target, deterministic training environment, and blocked folds.
- DERIVED_FEATURES: Seeded causal LSTM embedding produced out of fold and appended to a simple frozen meta-model.
- TARGET: Incremental next-block residual prediction and fixed-budget portfolio delta.
- COMPARATOR: Same meta-model without the embedding, lag-feature linear model, and shuffled-sequence embedding.
- CAUSAL_GUARD: No bidirectional context; embedding for a target is trained only on earlier draws; seeds and training budget are frozen.
- MINIMUM_WINDOWS: Four expanding folds with 750 prior draws and two terminal blocks.
- OUTPUT_METRIC: Incremental held-out loss and paired portfolio delta.
- EXPECTED_RUNTIME: 6–24 hours.
- EXPECTED_COMPUTE: HIGH; GPU optional, deterministic CPU reference required.
- PROMISING_SIGNAL_RULE: Beats both non-neural comparators in each terminal block, shuffled sequence fails, and matched-budget portfolio delta is positive.
- NO_SIGNAL_RULE: Embedding gain is absent, seed-unstable, reproduced by shuffled order, or does not affect downstream outcomes.
- NEXT_IF_POSITIVE: Freeze the smallest deterministic architecture for independent confirmation.
- NEXT_IF_NEGATIVE: Close that architecture/target only; do not cite closed direct LSTM producers as the reason.

## H24 — Transformer as residual/meta-feature

- HYPOTHESIS_ID: `H24`
- MINIMUM_REQUIRED_INPUT: Strictly ordered causal sequences, fixed residual target, deterministic encoder environment, and blocked folds.
- DERIVED_FEATURES: Causal masked Transformer embedding generated out of fold and consumed by a simple frozen meta-model.
- TARGET: Incremental next-block residual prediction and fixed-budget portfolio delta.
- COMPARATOR: Same meta-model without embedding, attention-replay producer output, lag-feature linear model, and shuffled positions.
- CAUSAL_GUARD: Causal mask, earlier-fold training only, frozen positional scheme, seed, width, depth, and training budget.
- MINIMUM_WINDOWS: Four expanding folds with 750 prior draws and two terminal blocks.
- OUTPUT_METRIC: Incremental held-out loss, seed dispersion, and paired portfolio delta.
- EXPECTED_RUNTIME: 8–24 hours.
- EXPECTED_COMPUTE: HIGH.
- PROMISING_SIGNAL_RULE: Stable gain over every comparator in both terminal blocks, shuffled positions remove the gain, and downstream delta is positive.
- NO_SIGNAL_RULE: No stable incremental gain, attention replay performs equivalently, or downstream effect is absent.
- NEXT_IF_POSITIVE: Freeze one minimal causal encoder for confirmation.
- NEXT_IF_NEGATIVE: Close the tested encoder/target only; attention replay remains non-parity evidence.

## H25 — XGBoost stacking strategy outputs and history

- HYPOTHESIS_ID: `H25`
- MINIMUM_REQUIRED_INPUT: Fixed strategy-output matrix, prior-only residuals, chronology, family labels, and exact baselines.
- DERIVED_FEATURES: Lagged cross-strategy outputs/residuals and a shallow deterministic XGBoost stacker trained out of fold.
- TARGET: Next-block expert/ticket residual and fixed-budget prize outcome.
- COMPARATOR: Direct historical XGBoost producer, linear residual stacker, static best strategy, and shuffled residual histories.
- CAUSAL_GUARD: Nested blocked CV; depth, trees, learning rate, and candidate experts frozen before terminal scoring.
- MINIMUM_WINDOWS: Four expanding folds and two untouched terminal blocks.
- OUTPUT_METRIC: Held-out residual loss and paired `OFFICIAL_ANY_PRIZE` delta.
- EXPECTED_RUNTIME: 1–4 CPU hours.
- EXPECTED_COMPUTE: MEDIUM.
- PROMISING_SIGNAL_RULE: Beats linear and static comparators in both terminal blocks, shuffled histories fail, and adjusted pooled outcome delta is positive.
- NO_SIGNAL_RULE: Direct/static models match it, gain is fold-unstable, or residual improvement does not translate downstream.
- NEXT_IF_POSITIVE: Freeze one shallow stacker for confirmation.
- NEXT_IF_NEGATIVE: Close residual stacking under this feature set, not XGBoost as a family.

## H26 — Special-aware portfolio geometry

- HYPOTHESIS_ID: `H26`
- MINIMUM_REQUIRED_INPUT: Candidate legal tickets with main and special components, exact joint prize baseline, pair/triple structure, and portfolio geometry.
- DERIVED_FEATURES: Main-number overlap, special-number concentration, joint coverage, and one special-aware overlap penalty.
- TARGET: Fixed-budget official-prize/hit-depth improvement under the joint ticket contract.
- COMPARATOR: Main-only overlap optimizer, score-only portfolio, and exact IID legal portfolio.
- CAUSAL_GUARD: Joint score and geometry weights frozen on discovery; no terminal prize outcomes tune the portfolio.
- MINIMUM_WINDOWS: Discovery, validation, and two terminal chronological blocks at one ticket budget.
- OUTPUT_METRIC: Paired official-prize delta, M3+ delta, special-hit coverage, and main/special concentration.
- EXPECTED_RUNTIME: 2–6 CPU hours once legal joint candidate tickets exist.
- EXPECTED_COMPUTE: MEDIUM.
- PROMISING_SIGNAL_RULE: Beats main-only geometry in both terminal blocks while satisfying frozen concentration constraints and positive adjusted pooled prize delta.
- NO_SIGNAL_RULE: Geometry changes without joint-outcome improvement or gain depends on retuned special weight.
- NEXT_IF_POSITIVE: Confirm the single special-aware objective on an untouched block.
- NEXT_IF_NEGATIVE: Close that objective only; retain the separate H16 joint probability question.

## H28 — Prospective confirmation of frozen EWMA drift H1/H2

- HYPOTHESIS_ID: `H28`
- MINIMUM_REQUIRED_INPUT: Exact frozen q67 threshold, H1 15-ticket and H2 20-ticket portfolios, shadow observer, calendar-gated draws, and exact matched baselines.
- DERIVED_FEATURES: None beyond the frozen `SHORT_MEDIUM_DRIFT/HIGH` event flag and predeclared sequential evidence state.
- TARGET: Prospective `OFFICIAL_ANY_PRIZE` and prespecified hit-depth delta on post-freeze HIGH events.
- COMPARATOR: Exact same-ticket random and the frozen non-HIGH/no-action rule.
- CAUSAL_GUARD: No re-freeze, threshold update, event relabeling, historical backfill, or reuse of the six pre-freeze unseen observations as prospective.
- MINIMUM_WINDOWS: First prespecified calendar sequence reaching at least 30 post-freeze HIGH events, with H1/H2 kept in one frozen correction family; current post-freeze count is 0.
- OUTPUT_METRIC: Sequential evidence state, event count, paired prize delta, and threshold-stress disclosure.
- EXPECTED_RUNTIME: Compute under one hour per update; evidence duration is calendar-gated and UNKNOWN.
- EXPECTED_COMPUTE: LOW, but not fast in elapsed calendar time.
- PROMISING_SIGNAL_RULE: Frozen sequential boundary is crossed in the positive direction after the minimum event count and both H1/H2 directions remain consistent under the declared family rule.
- NO_SIGNAL_RULE: Negative boundary is crossed, the prespecified horizon ends without signal, or H1/H2 direction materially reverses.
- NEXT_IF_POSITIVE: Seek independent prospective confirmation without changing the frozen contract.
- NEXT_IF_NEGATIVE: Close only the exact q67 H1/H2 prospective contract; preserve other thresholds/features as separate hypotheses.

END
