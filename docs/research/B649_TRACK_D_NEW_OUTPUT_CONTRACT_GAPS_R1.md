# B649 Track D New Output Contract Gaps R1

TASK_ID: B649_TRACK_D_COHORT_V2_FORWARD_READINESS_AND_CAPABILITY_GAP_MAP_R1

STATUS: DESIGN_COMPLETE_NOT_IMPLEMENTED

## Why new contracts are required

The pinned generic adapter publishes only main-number tickets and special_number=None. It publishes no score, rank, probability, uncertainty, latent state, special-number forecast, or seed metadata. Candidate-K and A/C/R4 orders are historical/proxy evidence, not missing public runtime outputs.

The contracts below describe semantic output boundaries. They do not authorize implementation, training, Cohort V2 entry, observer mutation, database writes, or production promotion.

## Common causal output envelope

schema_version, contract_id, canonical_hypothesis_id, top10_program_id_if_any, target_draw, lottery_type, producer_id, producer_version, repository_commit, repository_tree, producer_fingerprint, model_or_feature_artifact_digest, causal_cutoff, history_digest, determinism_mode, seed_protocol, minimum_history, availability_status, unavailable_reason, semantic_payload, semantic_hash.

Availability must be explicit: AVAILABLE or UNAVAILABLE with a frozen reason. Missing predictions may not be backfilled after outcome visibility. Stateful contracts must include a state checkpoint or sufficient replay provenance.

## Contract candidates

| ID | Name | Semantic meaning | Shape | Timing | Causal cutoff | Determinism | Persistence | Historical replay | Observer consumption | Scope | Hypotheses |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OC01 | STRATEGY_SIGNAL_V1 | One directional strategy-level scalar per target with strategy_id, objective_id, value, scale_id, direction, and producer version. | scalar per strategy/target | pre-target Phase A | strict cutoff < target | deterministic or fully seeded | sealed Phase-A output | required | generic observer | M | H01;H03;H09;H18;H25 |
| OC02 | NUMBER_SCORE_VECTOR_V1 | Dense domain-complete scores for 1..49 with named semantics, scale, direction, missing-value and tie policy; explicitly not probability. | 49 records or dense vector | pre-target Phase A | strict cutoff < target | deterministic or fully seeded | semantic hash plus artifact | required | number-score observer | L | H04;H08;H11;H12 |
| OC03 | CALIBRATED_NUMBER_PROBABILITY_VECTOR_V1 | Marginal P(number appears) with event, horizon, calibration population/method/version, and coherence policy. | 49 probabilities | pre-target Phase A | strict cutoff < target | deterministic trained artifact | model/calibrator plus per-draw output | required | proper-score observer | XL | H07;H17 |
| OC04 | EXPLICIT_NUMBER_RANKING_V1 | Total or partial order with source semantics, tie rule, and MODEL_NATIVE versus DERIVED_FROM_NUMBER_SCORE provenance. | ordered 1..49 or typed partial ranking | pre-target Phase A | strict cutoff < target | deterministic tie policy | sealed output and replay | required | rank-aware observer | M | H08 |
| OC05 | TICKET_SCORE_SET_V1 | Bounded legal candidates with stable ticket identity, objective-specific score, direction, selected flag, and selection rule; score is not probability. | bounded list of legal tickets | pre-target Phase A | strict cutoff < target | deterministic or fully seeded | pool and selected output sealed | required | ticket-level observer | L | H10;H11;H14;H15;H26 |
| OC06 | PREDICTIVE_UNCERTAINTY_V1 | Global or per-number uncertainty with explicit type and frozen model/member population. | scalar/vector/interval with type discriminator | pre-target Phase A | strict cutoff < target | frozen members and seeds | member/model identities plus output | required | uncertainty/action observer | L | H09;H17;H18 |
| OC07 | NEGATIVE_INFORMATION_VECTOR_V1 | Per-number suppression evidence with direction, zero/reference meaning, scale, and causal source; not negated unrelated score. | 49 scores or bounded suppressions | pre-target Phase A | strict cutoff < target | deterministic or fully seeded | sealed output and replay | required | suppressor observer | L | H21 |
| OC08 | BAYESIAN_LATENT_STATE_POSTERIOR_V1 | Named latent state plus posterior parameters/samples, prior/model version, update index, and initialization. | typed posterior state | pre-target sequential update | filtered strict-prior only | frozen inference and seed/chain | state checkpoints plus full replay | required | state-aware observer | XL | H17 |
| OC09 | HMM_STATE_POSTERIOR_V1 | Frozen states, filtered posterior vector, transition/emission model, initialization, and decoded-state policy. | K-state probability vector plus metadata | pre-target sequential update | filtered not smoothed | deterministic initialization/inference | model and state checkpoints | required | state/action observer | XL | H18 |
| OC10 | OOF_META_GATE_V1 | Per-strategy gate scores/weights with fold boundaries, eligible producer set, normalization, leakage guard, and model artifact ID. | vector over frozen experts | pre-target Phase A | training and inference strictly prior | deterministic OOF pipeline | OOF ledger, artifact, per-draw gate | required | meta-selector observer | XL | H03;H25 |
| OC11 | TEMPORAL_DECISION_SIGNAL_V1 | Versioned rolling snapshot with explicitly named EWMA, slope, acceleration, change statistic, alarm, or entropy-shift signal; hypotheses remain separate. | typed state/signal record | pre-target sequential update | strict-prior windows/state | deterministic formulas and initialization | checkpoint or sufficient replay provenance | required | generic temporal observer | M | H04;H19;H20;H28 |
| OC12 | SPECIAL_NUMBER_CONDITIONAL_V1 | Typed score or calibrated probability for the distinct special number with declared conditioning context. | domain-complete special-number vector | pre-target Phase A | strict cutoff < target | deterministic trained artifact | model plus sealed prediction | required | special-aware observer | XL | H16;H26 |
| OC13 | MAIN_SPECIAL_JOINT_CANDIDATE_V1 | Sparse bounded legal (main_set, special) candidates with explicit joint score/probability semantics. | bounded joint candidate list | pre-target Phase A | strict cutoff < target | deterministic or fully seeded | model, candidate set, and predictions | required | joint-prize observer | XL | H16;H26 |

## Forbidden semantic promotions

- A score is not a probability without a named event and calibration contract.
- A ticket position, sorted legal ticket, exposure count, Candidate-K order, or R4 top2 exposure order is not a strategy-internal rank.
- Ticket disagreement is not predictive uncertainty unless the member/output population and uncertainty statistic are frozen.
- A negative-selection ticket is not a negative-information score.
- special_hit in an observed candidate set is not a special-number prediction.
- A method-family label or name such as Bayesian, HMM, LSTM, Transformer, XGBoost, or attention does not establish output parity.

## Contract-to-capability mapping

| Contract | Primary capabilities |
|---|---|
| OC01 | C02, C10, C38 |
| OC02 | C03, C38 |
| OC03 | C04, C38, C42 |
| OC04 | C03, C38 |
| OC05 | C05, C37, C41 |
| OC06 | C23, C24, C38 |
| OC07 | C22, C38 |
| OC08 | C25, C33, C42 |
| OC09 | C26, C33, C42 |
| OC10 | C02, C34, C38, C42 |
| OC11 | C08, C13, C33, C35 |
| OC12 | C27, C38, C43 |
| OC13 | C28, C38, C43 |

## Persistence and replay policy

RUNTIME_ONLY_CAPABILITY covers deterministic computation that need not enter production storage. EPHEMERAL_RESEARCH_OUTPUT covers fold-local training/intermediate features. SEALED_RESEARCH_ARTIFACT covers preregistered specs, fingerprints, replay ledgers, model/calibration artifacts, and pre-target predictions. FUTURE_PRODUCTION_PERSISTENCE is deferred and not designed as a cross-lottery DB migration here.

No contract should enter Cohort V2 until historical replay proves strict cutoff and repeated-run parity, and a two-phase observer consumes the exact schema without target outcome content in Phase A.

END
