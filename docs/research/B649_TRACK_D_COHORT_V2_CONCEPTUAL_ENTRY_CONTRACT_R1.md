# B649 Track D Conceptual Cohort V2 Entry Contract R1

TASK_ID: B649_TRACK_D_COHORT_V2_FORWARD_READINESS_AND_CAPABILITY_GAP_MAP_R1

STATUS: PASS_DESIGN_ONLY_NOT_EXECUTED

## Purpose and boundary

This document defines eligibility for a future independent Cohort V2. It creates no cohort, selects no candidate, freezes no membership, starts no observation, changes no strategy, and mutates no observer or database.

Discovery and prospective entry are different. Historical discovery may run with partial forward capability and explicitly labeled proxies. ELIGIBLE_FOR_V2_FREEZE requires every applicable prospective gate below.

## Entry gates

| Gate | Name | Requirement | Applicability |
|---|---|---|---|
| G01 | HISTORICAL_SIGNAL_EXISTS | A predeclared historical experiment advances under its own rule. | PROSPECTIVE_ENTRY_ONLY |
| G02 | FIXED_HYPOTHESIS_SPEC | Canonical ID, any alias, primary outcome, comparator, proxy policy, and multiplicity boundary are sealed. | PROSPECTIVE_ENTRY_ONLY |
| G03 | FORWARD_EXECUTABLE | An exact versioned producer exists at a pinned repository commit/tree. | PROSPECTIVE_ENTRY_ONLY |
| G04 | CAUSAL_OUTPUT_AVAILABLE | Producer reads only strict-prior history and presealed outcome-free artifacts. | PROSPECTIVE_ENTRY_ONLY |
| G05 | SEMANTIC_OUTPUT_CONTRACT | Output validates against one named contract; ranks/probabilities are not inferred. | PROSPECTIVE_ENTRY_ONLY |
| G06 | DETERMINISTIC_OR_SEEDED | Determinism or complete seed/RNG protocol is frozen and fingerprinted. | PROSPECTIVE_ENTRY_ONLY |
| G07 | REPLAY_PARITY | Historical causal replay demonstrates cutoff and repeated-run parity including unavailable semantics. | PROSPECTIVE_ENTRY_ONLY |
| G08 | OBSERVER_CONSUMABLE | A two-phase observer consumes the exact schema before target outcome visibility. | PROSPECTIVE_ENTRY_ONLY |
| G09 | FROZEN_CONFIGURATION | Producer/model/features/constructor/controls/availability and candidate membership are frozen. | PROSPECTIVE_ENTRY_ONLY |
| G10 | PREDECLARED_MULTIPLICITY_FAMILY | A new independent V2 family, endpoints, checkpoints, and correction rule are frozen. | PROSPECTIVE_ENTRY_ONLY |
| G11 | STATE_AND_FINGERPRINT_COMPLETE | Transitive dependencies, initialization, checkpoints, artifacts, and digests are sealed. | WHEN_APPLICABLE |
| G12 | LEGAL_MAIN_SPECIAL_CONTRACT | Main/special hypotheses have a legal joint/conditional representation and scoring path. | WHEN_APPLICABLE |

A candidate failing a gate remains BLOCKED_OUTPUT_CONTRACT, BLOCKED_PRODUCER, BLOCKED_REPLAY, BLOCKED_FINGERPRINT, BLOCKED_OBSERVER, HISTORICAL_ONLY, or NOT_YET_SELECTED. Unavailable output stays unavailable; it is not retrospectively backfilled or replaced with an invented proxy.

## Candidate record

cohort_family_id, candidate_id, canonical_hypothesis_id, top10_program_id_if_any, producer_id, producer_version, repository_commit, repository_tree, input_contract_id, output_contract_id, scoring_contract_id, primary_outcome, causal_cutoff_rule, minimum_history, state_initialization, determinism_mode, seed_protocol, model_artifact_digest, producer_fingerprint, historical_replay_digest, observer_adapter_id, availability_policy, proxy_policy, persistence_class, entry_gate_status.

## Two-phase observation

Phase A runs in an outcome-free process, reads only the frozen contract and strict-prior history, and atomically creates one immutable prediction or unavailable record. Only after Phase A exits may Phase B read the target outcome and atomically create the score. The target outcome must never appear in Phase A content, inputs, logs, or feature artifacts.

Observer scoring is hypothesis-specific. R4 M2_PLUS and its candidate-size hypergeometric baseline are not inherited automatically. Each V2 candidate freezes its own output, primary endpoint, matched baseline, checkpoint rule, and availability handling.

## R4 design precedent and non-reuse

Reusable concepts: two processes, strict-prior history, create-once predictions, semantic hashes, explicit unavailable records, transitive fingerprints, frozen membership, and predeclared checkpoints.

Not reusable as authority: R4 candidate IDs, four-producer member set, A/C proxies, 40-candidate family, 10 controls, M2_PLUS endpoint, hypergeometric baseline, existing observation start, checkpoints, or Holm family. Extending those would mutate Cohort V1/R4 rather than create V2.

## Cohort V1 preservation

Cohort V1 remains exactly 40 frozen candidates, three forward-generatable candidates, and 37 unavailable candidates. Its membership, controls, observer, selection evidence, observation history, terminal family size, checkpoints, and interpretation remain unchanged. V2 must use a new family ID, new membership, new controls, new freeze boundary, new observation start, and new multiplicity contract.

## Persistence and DB policy

Candidate capabilities and predictions use explicit classes: RUNTIME_ONLY_CAPABILITY, EPHEMERAL_RESEARCH_OUTPUT, SEALED_RESEARCH_ARTIFACT, and only later FUTURE_PRODUCTION_PERSISTENCE. Cohort entry does not require a production DB migration. This contract does not design cross-lottery production persistence.

## Readiness interpretation

H28 can operate its separate already-frozen protocol, but that does not enroll it in V2 or supply positive evidence. H22 is inferential infrastructure and cannot be a standalone V2 member. H14 may enter only as an explicitly scoped portfolio operator candidate with upstream predictive-signal semantics kept separate. H16/H26 require legal main/special contracts before entry.

## Freeze decision output

A future authorized freeze should produce a sealed candidate ledger with PASS/FAIL for every gate, exact digests, a new observer contract, an independent multiplicity family, and an observation-start boundary strictly after all configuration and model selection. No item in this R1 design is itself such a freeze.

END
