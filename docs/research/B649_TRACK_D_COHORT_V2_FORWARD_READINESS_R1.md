# B649 Track D Cohort V2 Forward Readiness and Capability Gap Map R1

TASK_ID: B649_TRACK_D_COHORT_V2_FORWARD_READINESS_AND_CAPABILITY_GAP_MAP_R1

STATUS: PASS

PINNED_HISTORICAL_HEAD: 2db4da27aee716805c393eb9c7dd41aff8e9527e

PINNED_HISTORICAL_TREE: cb6b9c3685739c381d6a5f7a92fa7668ed93cc9c

MODE: READ_ONLY_DESIGN_RESEARCH_WITH_NINE_ALLOWLISTED_OFF_REPOSITORY_ARTIFACTS

## Executive decision

All 28 canonical hypotheses and all 51 current-executable-within-historical identities are mapped. The runtime capability registry contains 44 capabilities: required C01–C32 plus twelve evidence-driven shared/runtime capabilities C33–C44.

| Forward readiness class | Count |
|---|---|
| READY_NOW | 1 |
| READY_WITH_DERIVED_FEATURES | 1 |
| READY_WITH_SMALL_ENGINEERING | 6 |
| READY_WITH_MEDIUM_ENGINEERING | 5 |
| REQUIRES_NEW_MODEL_OUTPUT | 9 |
| REQUIRES_NEW_RUNTIME_ARCHITECTURE | 5 |
| HISTORICAL_ONLY_CURRENTLY | 1 |

The single highest-value shared investment is C33 SHARED_ROLLING_STATE_ENGINE. It contributes to 16 hypothesis dependency paths and has moderate scope, but it completes zero hypotheses by itself. C39 and C40 are broader infrastructure dependencies, yet neither creates missing model outputs.

H28 is READY_NOW only at the protocol/observer level. It still has zero true post-freeze observations and therefore no prospective result. H04 is the easiest newly enabled hypothesis: its 50/300/750 features are derivable, but a versioned producer/adapter remains necessary.

## Authority and non-interference

All seven Packet inputs rehashed to their expected SHA-256 values. The historical repository source was read only through the pinned commit. The live branch, repository files, database, Track B H01, Cohort V1, R4 observer, EWMA protocol, and sealed predecessor roots were not mutated.

Primary runtime evidence:

- Pinned catalog: src/lottolab/strategies/catalog.py@2db4da27aee716805c393eb9c7dd41aff8e9527e;blob=099f2a8c9ccbacc8306b2397c560bef413b24217 (SHA-256 f69adde6d71390e716cfd4d6967932adb94b22b3dfb1bd451a87c9bf11257a4f).
- Pinned base adapter: src/lottolab/strategies/adapters/base.py@2db4da27aee716805c393eb9c7dd41aff8e9527e;blob=a4e5571491c7358d8624acb8fe53f99c3bba9611 (SHA-256 39161a069851421c5014185086b43771f3e0f90d06e4cd80f4b1a8e3e3062448).
- Pinned full catalog: src/lottolab/strategies/data/biglotto_full_strategy_catalog_v1.json@2db4da27aee716805c393eb9c7dd41aff8e9527e; blob fe93150e002bd7217be54501fdc9d390f81f79db (SHA-256 e604a038622fa9476aa86b33cd8068287664ec49cd5a27c81996ecb59a88dfbf).
- Candidate-K universe: /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_STRATEGY_K_HISTORICAL_MATRIX_AUTHORITY_R1/strategy_universe.json; SHA-256 e645900ba8f6822af4be8851f1fb29807e181a21542de4ab5f2560a8f13cffc8.
- Frozen R4 observer: /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_COMBINATION_PROSPECTIVE_FORWARD_OBSERVER_R4/observer_contract.json; SHA-256 123ac9abf6eceb751a52374fd40d455f09bdd86497ab62ef08a273085edf3b91.
- Frozen EWMA protocol: /Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_EWMA_PROSPECTIVE_SHADOW_PROTOCOL_R4/prospective_protocol.json; SHA-256 0beb0f5dd5bab357c1658966c2c56e192aa84d1fb176c8b6c2554d1376b90b12.

## Population boundaries

| Population | Count | Meaning |
|---|---|---|
| HISTORICAL_ANALYZABLE | 133 | Sealed historical research population. |
| CURRENT_EXECUTABLE_WITHIN_HISTORICAL | 51 | Exact current catalog ∩ historical identity set mapped here. |
| HISTORICAL_ONLY_RAW_ONLY | 82 | Historical evidence without an exact current executable identity. |
| COMPLETE_CURRENT_EXECUTABLE_B649_CATALOG | 68 | Different current catalog population; not substituted for 51. |
| CANDIDATE_K_DIRECT_AVAILABLE | 7 | Seven single-ticket historical direct paths; not rank/probability. |
| CURRENT_PORTFOLIO_WITHOUT_CANONICAL_NUMBER_AGGREGATION | 44 | Portfolio paths with positional tickets but no canonical number aggregation. |
| COHORT_V1_FROZEN | 40 | Frozen and unchanged. |
| COHORT_V1_FORWARD_GENERATABLE | 3 | Three frozen A combinations under R4 only. |
| COHORT_V1_UNAVAILABLE | 37 | Not a statement about historical research validity. |

Exact 51 catalog-order identity-list SHA-256, including trailing LF: 2cd735bb6a7114aa395d376a6eee0483b6fd4312abfed7d67f7aa8a80a62b764.

Family distribution across the 51: ML_like=7, deviation=6, folklore=1, frequency=6, hot_cold=4, markov=1, report=1, unknown=2, utility=18, zone=5.

Response shapes: SINGLE_TICKET=7; PORTFOLIO=44. Native counts: 1-ticket=7, 2-ticket=10, 3-ticket=17, 4-ticket=2, 5-ticket=3, 6-ticket=1, 7-ticket=4, 8-ticket=2, 10-ticket=1, 11-ticket=1, 12-ticket=1, 25-ticket=1, 54-ticket=1.

Minimum-history distribution: min_history_1=42, min_history_20=2, min_history_50=4, min_history_100=2, min_history_200=1.

Executable is not a total-function claim. quick_ml_predict deterministically closes for every history length at least five; twelve additional named adapters retain explicit data-dependent closure surfaces; all fixed portfolios fail closed if exact ticket validation is not met. The matrix therefore records loadable runtime paths and truthful availability semantics rather than claiming 51 successful outputs per future draw.

## Canonical and Top10 program ID namespace

The Top10 program reused H01–H10 labels for a selected subset of canonical H01–H28. Canonical IDs remain primary in every artifact; top10_program_id is an explicit alias column.

| Canonical ID | Top10 program ID | Top10 program title |
|---|---|---|
| H01 | H01 | CROSS_STRATEGY_RESIDUAL_GATED_META_SELECTOR |
| H27 | H02 | HORIZON_MINIMAX_DISAGREEMENT_CONFIRMATION |
| H04 | H03 | MULTI_WINDOW_SLOPE_ACCELERATION_DISAGREEMENT |
| H07 | H04 | CALIBRATED_PER_NUMBER_PROBABILITIES |
| H10 | H05 | DIRECT_TICKET_LEVEL_RESIDUAL_SCORING |
| H14 | H06 | DPP_SUBMODULAR_PORTFOLIO_SELECTION |
| H19 | H07 | CHANGE_POINT_TRIGGERED_ALLOCATION |
| H12 | H08 | TEMPORAL_HYPERGRAPH_MOTIF_RESIDUALS |
| H21 | H09 | CONDITIONAL_NEGATIVE_INFORMATION_SUPPRESSION |
| H17 | H10 | DYNAMIC_BAYESIAN_STATE_SPACE_MODELING |

Consequently Packet special cases Top10 H03/H06/H07 are canonical H04/H14/H19. This report never applies those special-case instructions to canonical H03/H06/H07.

## Runtime truth boundary

The public generic adapter output exposes only emitted main numbers, validated legal main numbers, and special_number=None. It does not expose strategy scores, number scores, probabilities, ticket scores, internal ranks, uncertainty, latent state, special predictions, or seed metadata. Internal computations are not promoted to canonical public capabilities.

All 51 implementations are reproducible from the same causal input and code when they succeed: 20 have no load-bearing RNG, 25 use the frozen history-length-seeded statistical path, one uses a fixed local seed 42, three use SHA-256 request/history-derived CPython MT19937, and two use SHA-256 request/history-derived legacy NumPy MT19937. The public output does not carry seed provenance.

The base input validates CausalDrawRow shape but has no target identity and does not prove strict chronology or target exclusion. Causal cutoff remains a caller/observer responsibility. R4 demonstrates the required two-phase design but is frozen to four producer members inside three A-pair candidates; it is not generic compatibility for the 51 or Cohort V2.

## 28-hypothesis summary

Score order is Discovery readiness / Forward readiness / Forward enablement cost / Shared capability reuse. Cost 5 means hardest.

| ID | Top10 alias | Hypothesis | Historical readiness | Forward class | D/F/C/R | Minimum forward enablement |
|---|---|---|---|---|---|---|
| H01 | H01 | Cross-strategy residual-gated meta-selector | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_MEDIUM_ENGINEERING | 5/3/3/5 | Causal rolling outcome/residual ledger over capability-verified experts; deterministic frozen gate; generic two-phase observer. |
| H02 | — | Complementary-error graph across strategies | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_MEDIUM_ENGINEERING | 5/2/3/5 | Rolling strategy-outcome graph; deterministic complementarity cover/selector; forward overlay and observer. |
| H03 | — | Mixture-of-experts with out-of-fold gating | READY_FOR_HISTORICAL_EXPERIMENT | REQUIRES_NEW_MODEL_OUTPUT | 5/2/4/5 | Deterministic nested/OOF expert-weight contract; replay pipeline; fixed expert set; shadow adapter. |
| H04 | H03 | 50/300/750 slope, acceleration and disagreement signal | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_DERIVED_FEATURES | 5/4/1/5 | Versioned 50/300/750 causal feature producer; fixed level-only comparator; deterministic score-to-legal-ticket adapter. |
| H05 | — | Conditional consensus by regime/state | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_SMALL_ENGINEERING | 5/4/1/4 | Ticket-support/family-breadth/state overlay over an exact verified current member set. |
| H06 | — | Conditional anti-consensus / minority signal | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_SMALL_ENGINEERING | 5/4/1/4 | Deterministic minority-support/substitution gate and paired no-action observer. |
| H07 | H04 | Calibrated per-number probability model | PARTIAL_HISTORICAL_INPUT_PATH | REQUIRES_NEW_MODEL_OUTPUT | 4/1/4/5 | Typed dense 49-vector P(appear) contract; nested temporal calibration/replay; proper scoring; legal constructor and adapter. |
| H08 | — | Per-number ranking-loss model | PARTIAL_HISTORICAL_INPUT_PATH | REQUIRES_NEW_MODEL_OUTPUT | 3/1/4/4 | Deterministic dense 49-number score/rank vector with declared semantics; fixed constructor and replay. |
| H09 | — | Predictive uncertainty / ensemble dispersion | PARTIAL_HISTORICAL_INPUT_PATH | REQUIRES_NEW_MODEL_OUTPUT | 4/1/3/5 | Comparable OOF expert outputs; calibrated failure-risk/uncertainty; frozen abstain/downweight/diversify action. |
| H10 | H05 | Direct ticket-level scorer with pair/triple residual terms | READY_FOR_HISTORICAL_EXPERIMENT | REQUIRES_NEW_MODEL_OUTPUT | 5/1/4/4 | Frozen bounded causal ticket pool/generator; deterministic typed ticket score; sparse pair/triple replay; fixed top-k constructor. |
| H11 | — | Pair/triple interaction residual after marginal number scores | READY_FOR_HISTORICAL_EXPERIMENT | REQUIRES_NEW_MODEL_OUTPUT | 5/1/4/4 | Frozen marginal score; sparse pair/triple residual output; bounded ticket-scoring adapter. |
| H12 | H08 | Temporal hypergraph motifs / communities | READY_FOR_HISTORICAL_EXPERIMENT | REQUIRES_NEW_RUNTIME_ARCHITECTURE | 4/1/5/4 | Preregistered motif vocabulary/decay; rolling hypergraph engine; residual scorer; historical replay and versioned adapter. |
| H13 | — | Temporal graph change rather than static graph score | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_MEDIUM_ENGINEERING | 5/2/3/5 | Rolling graph snapshots/deltas; deterministic graph-change score/flag; fixed constructor and observer adapter. |
| H14 | H06 | DPP/submodular portfolio selection under a calibrated score | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_SMALL_ENGINEERING | 5/4/2/5 | Identical bounded candidate pool/budget/cutoff; deterministic DPP-MAP/submodular adapter; exact matched comparators. |
| H15 | — | Multi-objective hit-depth / coverage / overlap / payout-proxy optimizer | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_SMALL_ENGINEERING | 5/3/2/5 | Freeze typed candidate score/proxy, objective weights, universe, and budget; deterministic optimizer and observer. |
| H16 | — | Joint main-number/special-number conditional model | PARTIAL_HISTORICAL_INPUT_PATH | REQUIRES_NEW_RUNTIME_ARCHITECTURE | 3/0/5/4 | Joint probability/full-ticket-score schema; legal main+special constructor; deterministic training/replay/runtime and observer. |
| H17 | H10 | Dynamic Bayesian state-space probability model | READY_FOR_HISTORICAL_EXPERIMENT | REQUIRES_NEW_MODEL_OUTPUT | 4/1/4/5 | Deterministic filtered latent posterior/probability contract with priors/init identity; causal replay; legal constructor and adapter. |
| H18 | — | HMM latent-regime gating | READY_FOR_HISTORICAL_EXPERIMENT | REQUIRES_NEW_MODEL_OUTPUT | 4/1/4/5 | Filtered, never smoothed, state-probability output; frozen allocation map; deterministic initialization/replay and adapter. |
| H19 | H07 | Change-point-triggered strategy allocation | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_MEDIUM_ENGINEERING | 5/3/3/5 | Forward-only fitted detector; persistent alarm state; frozen allocation action and observer. |
| H20 | — | Entropy/distribution-shift anomaly gating | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_SMALL_ENGINEERING | 5/4/1/5 | Causal entropy/JSD/tail-mass event producer; frozen threshold/action; small overlay and observer. |
| H21 | H09 | Negative-information candidate suppressor | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_MEDIUM_ENGINEERING | 5/2/3/4 | Independently frozen positive selector; causal typed negative score; matched suppression and conditional wrapper. |
| H22 | — | Conditional/nested exact null and paired counterfactual calibration | READY_FOR_HISTORICAL_EXPERIMENT | HISTORICAL_ONLY_CURRENTLY | 5/0/2/5 | Bind to one frozen adaptive selector and replay selection inside a paired/nested null. |
| H23 | — | LSTM as residual/meta-feature, not direct ticket generator | PARTIAL_HISTORICAL_INPUT_PATH | REQUIRES_NEW_RUNTIME_ARCHITECTURE | 3/0/5/4 | Deterministic causal sequence/mask/normalization pipeline; OOF embedding/residual output; model fingerprint and runtime adapter. |
| H24 | — | Transformer as residual/meta-feature | PARTIAL_HISTORICAL_INPUT_PATH | REQUIRES_NEW_RUNTIME_ARCHITECTURE | 3/0/5/4 | Minimal causal-masked deterministic encoder; OOF output; exact fingerprint and runtime adapter. |
| H25 | — | XGBoost stacking strategy outputs and history | READY_FOR_HISTORICAL_EXPERIMENT | REQUIRES_NEW_MODEL_OUTPUT | 5/2/3/5 | Deterministic shallow OOF stacker emitting typed residual/failure score or expert weights plus shadow adapter. |
| H26 | — | Special-aware portfolio geometry | PARTIAL_HISTORICAL_INPUT_PATH | REQUIRES_NEW_RUNTIME_ARCHITECTURE | 3/0/5/4 | Legal main+special candidate/output representation; special-aware objective; exact prize baseline and optimizer adapter. |
| H27 | H02 | Preregistered confirmation of horizon-minimax disagreement | READY_FOR_HISTORICAL_EXPERIMENT | READY_WITH_SMALL_ENGINEERING | 3/3/2/4 | Bit-for-bit fixed producer reproduction; deterministic two-ticket adapter; frozen observer. |
| H28 | — | Prospective confirmation of frozen EWMA drift H1/H2 | PROTOCOL_ONLY_CALENDAR_GATED | READY_NOW | 1/5/0/3 | No new enablement: operate the exact frozen observer and wait for post-freeze eligible draws. |

## Priority architecture findings

### H01 / Top10 H01 residual-gated meta-selector

H01_NOT_BLOCKED_BY_CANDIDATE_K_7_OF_133_LIMIT: TRUE

H01 needs forward strategy tickets, lagged performance/residual state, a causal cutoff, a frozen deterministic gate, and a generic observer. It does not need a source strategy internal rank, per-number probability, number-level score, or Candidate-K path. No ticket order or exposure order is used as internal rank.

The exact 51 is a structurally meaningful upper-bound meta-selection population: it spans 10 observed family labels and 50 identities remain potentially usable at normal history after excluding the known quick_ml total closure. This is enough for a meaningful fixed expert subset in architecture terms, but the exact per-draw eligible set, closures, minimum histories, family balance, and observer contract must be preflighted and frozen. This is not a claim that all 51 emit on every target.

### H04 / Top10 H03 multi-window derivatives

The window levels, slope, acceleration, and disagreement are fully derivable from strict-prior rolling history. No existing strategy needs a new internal output. H04 is the easiest newly built Cohort V2 candidate path, conditional on a versioned feature producer, typed score semantics, fixed legal constructor, causal replay, and observer adapter.

### H14 / Top10 H06 DPP/submodular operator

PREDICTIVE_SIGNAL_READINESS: 2/5, inherited from the upstream producer or declared candidate utility.

PORTFOLIO_OPERATOR_READINESS: 4/5.

H14 can be implemented conceptually as a post-prediction portfolio operator over the same frozen candidate pool, budget, cutoff, and ticket count. It does not require a new draw-prediction model for a geometry-only claim. A proxy utility is acceptable only for discovery and must remain labeled; a predictive-quality claim requires a typed candidate score.

### H19 / Top10 H07 and H20 temporal gates

H19 change-point allocation and H20 entropy/distribution-shift gating should share C33/C35 rolling temporal state infrastructure, but remain distinct hypotheses, output fields, thresholds, actions, and multiplicity units. H20 is small engineering; H19 is medium because detector initialization, persistent alarm state, and time-since-alarm semantics are additional load-bearing state.

### Second wave

- H20: minimum is a causal entropy/divergence event producer, frozen threshold/action, and observer overlay.
- H02: minimum is a rolling complementary-error graph and deterministic cover/selector over verified forward experts.
- H11: minimum is a frozen marginal number score plus sparse pair/triple residual output and bounded ticket scorer.
- H09: minimum is comparable OOF expert outputs plus typed calibrated uncertainty and a frozen action.
- H08: minimum is a new deterministic 49-number rank/score vector; legacy internal rank reconstruction is forbidden.

## Top rankings

TOP_5_FORWARD_READY_HYPOTHESES: H28 Prospective confirmation of frozen EWMA drift H1/H2; H04 50/300/750 slope, acceleration and disagreement signal; H20 Entropy/distribution-shift anomaly gating; H05 Conditional consensus by regime/state; H06 Conditional anti-consensus / minority signal

TOP_5_CHEAPEST_TO_ENABLE: H28 Prospective confirmation of frozen EWMA drift H1/H2; H04 50/300/750 slope, acceleration and disagreement signal; H05 Conditional consensus by regime/state; H06 Conditional anti-consensus / minority signal; H20 Entropy/distribution-shift anomaly gating

TOP_5_HIGHEST_CAPABILITY_UNLOCK_VALUE: C33 SHARED_ROLLING_STATE_ENGINE; C39 SHARED_CAUSAL_FEATURE_STORE; C40 SHARED_FORWARD_OBSERVER_ADAPTER; C38 SHARED_MODEL_SCORE_CONTRACT; C37 SHARED_PORTFOLIO_GEOMETRY_ENGINE

TOP_5_HIGHEST_DISCOVERY_VALUE_BUT_FORWARD_HARD: H10 Direct ticket-level scorer with pair/triple residual terms; H11 Pair/triple interaction residual after marginal number scores; H12 Temporal hypergraph motifs / communities; H16 Joint main-number/special-number conditional model; H24 Transformer as residual/meta-feature

SINGLE_HIGHEST_VALUE_SHARED_CAPABILITY: C33 SHARED_ROLLING_STATE_ENGINE.

HYPOTHESES_SERVED_BY_C33: H01;H02;H03;H04;H05;H06;H09;H12;H13;H17;H18;H19;H20;H21;H25;H28. This is 16 contributory dependency paths and zero hypotheses fully unlocked by C33 alone.

## New-output and shared-runtime design

Thirteen output-contract candidates are defined in B649_TRACK_D_NEW_OUTPUT_CONTRACT_GAPS_R1.md. The common envelope freezes identity, code/tree, feature/model digest, target/cutoff, history digest, determinism/seed semantics, availability, payload, and semantic hash. Arbitrary scores may not become probabilities; ticket order/exposure order may not become internal ranks.

The shared unlock CSV reports dependency counts, Top10 counts, second-wave counts, near-term readiness gain, scope, reuse, and an explicit priority. `CAPABILITY_UNLOCK_PRIORITY` is a lexicographic engineering judgment: dedicated shared bundles C33–C44 are assessed first because they consolidate multiple leaf requirements; within that tier, direct blocker reduction and near-term forward gain precede reuse, breadth, and scope; foundational leaf contracts C01–C32 follow. The `RAW_COVERAGE_LEVERAGE_SCORE_NOT_RANKING_KEY` is a diagnostic coverage formula, not the sort key: broad safety/observer prerequisites can score highly without manufacturing a missing state, model, or operator output. This is why C33 outranks broader infrastructure such as C30/C39/C40. HYPOTHESES_UNLOCKED_COUNT means dependency paths served, not hypotheses completed by that one capability; the separate sole-completion column is zero for every missing shared capability.

## Engineering scope and persistence policy

Scope estimates are relative XS/S/M/L/XL, not work-hour forecasts. Each capability registry row states likely surfaces and whether new schema, adapter, replay, training, observer, or DB work is needed.

No production DB change is proposed. Near-term capability state should be classified as RUNTIME_ONLY_CAPABILITY, EPHEMERAL_RESEARCH_OUTPUT, or SEALED_RESEARCH_ARTIFACT. FUTURE_PRODUCTION_PERSISTENCE remains a later Owner-authorized decision after a forward contract proves useful.

## Cohort V2 and V1 preservation

The conceptual Cohort V2 contract is PASS as a design artifact and NOT EXECUTED. Discovery does not require all prospective gates. Prospective entry requires a sealed signal/spec, exact producer, strict cutoff, deterministic/seeded behavior, replay parity, semantic output contract, observer consumption, frozen configuration, and a new predeclared multiplicity family.

Cohort V2 is a separate future family. Cohort V1 remains 40 frozen / 3 forward-generatable / 37 unavailable, with its membership, Holm family, checkpoints, observer, and interpretation untouched.

## Validation and limitations

- 28/28 canonical hypotheses mapped across all 44 capabilities: 1,232 matrix rows.
- 51/51 current executable historical identities mapped in pinned catalog order.
- All capability entries have an authority/source and limitation; none is UNKNOWN.
- No internal rank was inferred from tickets; no probability was inferred from arbitrary scores.
- Exact current executable success on a future target remains target-dependent because loadable adapters are not total functions.
- H27 and H28 remain calendar/evidence gated; engineering readiness cannot fabricate untouched prospective evidence.
- This report makes no predictive-advantage, production-readiness, or Cohort V2 selection claim.

END
