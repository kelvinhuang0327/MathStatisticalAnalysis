# EH01 / EH10 — B649 Track B ordinal/temporal — locked preregistration

Status: LOCKED before any EH01/EH10 statistic was computed ｜ 2026-08-16

## 0. Identity and authorization chain

```text
TASK_ID:                B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_LOCK_EXECUTE_R1
CONTINUES:               B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_FALSIFICATION_R1
                          (STOPPED 2026-08-16, STOP_EH01_EH10_SPEC_AUTHORITY_INCOMPLETE)
PROPOSAL:                B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md
PROPOSAL_SHA256:         76629e97f0f7a44848075da6e615f9c946e2b80dedb23bc3d77a6e67104fd094
OWNER_AUTHORIZATION:     AUTHORIZE_B649_TRACK_B_EH01_EH10_ORDINAL_TEMPORAL_LOCK_EXECUTE_R1
EH01_VARIANT_ID:         EH01_MATRIX_PROFILE_MOTIF_DISCORD_B649_V1
EH10_VARIANT_ID:         EH10_PERMUTATION_ENTROPY_ORDINAL_B649_V1
HYPOTHESIS_FAMILY_ID:    HIGHER_ORDER_TEMPORAL_STRUCTURE (descriptive only; this task
                          does not write to the cross-lottery research ledger)
LOTTERY_TYPE:            BIG_LOTTO
```

**Acceptance-gate note.** The proposal document itself is intentionally
self-stopping (`STATUS: PROPOSAL_FOR_OWNER_REVIEW`, `LOCK_STATUS: NOT_LOCKED`,
ends with `STOP.`) — no file on disk contains a literal `ACCEPTANCE_GATE:
PASS` marker, because the proposal cannot approve itself. The Owner's
2026-08-16 chat authorization — which names this exact proposal path,
reproduces its "Recommended locks" table and comparator decision verbatim
under "FIXED LOCKS", and issues the token above — is treated as the
acceptance record. It is logged here explicitly, rather than assumed
silently, because no separate written `ACCEPTANCE_GATE` artifact exists.

**Parameter-drift check: PASS.** Every numeric/categorical value under
"FIXED LOCKS" in the Owner's execute packet was compared line-by-line against
section 0 ("Recommended locks") and the "Required return block" (section 16)
of the proposal; they match exactly. `STOP_EH01_EH10_PARAMETER_PROPOSAL_DRIFT`
does not apply.

## 1. Scientific claims (structural only, per the proposal's own downgrade)

**EH01.** The chronological B649 main-number-sum series contains a causal
repeated-subsequence motif or causal discord, at horizons 26/52/104 draws,
more extreme than expected under chronological exchangeability.
`SIGNAL` means `EH01_STRUCTURAL_SIGNAL_AT_LOCKED_REPRESENTATION_AND_HORIZON`
only — not a claim that a motif/discord-gated allocator improves strategy
loss (that comparator is removed as unidentifiable on the current source
tree, with no proxy; see proposal section 3.6).

**EH10.** The same series contains a causal rolling ordinal-complexity
deficit, at orders 3/4/5 over a 124-draw window, more extreme than expected
under the same null. `SIGNAL` means
`EH10_ORDINAL_STRUCTURAL_SIGNAL_AT_LOCKED_REPRESENTATION_ORDER_AND_WINDOW`
only.

Neither claim is about predictive advantage, allocation benefit, prize
value, or economic optimality (all `NOT_TESTED`, proposal section 14.2).

## 2. Exact definitions: authoritative source

Every formula (z-normalization, causal admissibility, motif/discord
statistics, ordinal-pattern construction, tie handling, entropy
normalization, null/surrogate generation, Holm correction, classification
thresholds) is defined verbatim in
`B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md` sections 2-9, pinned
by `PROPOSAL_SHA256` above, and is not re-derived here. This document and
`tools/hash_preregistration_eh01_eh10_b649.py`'s `LOCKED_PARAMETERS` record
only the scalar/categorical choices that pin one exact design out of that
document's parameter space — mirroring the precedent set by
`greedy-min-overlap-constructor-p638-zone1-v1-preregistration.md` (locks
execution-time parameters only; geometry/classification definitions already
frozen elsewhere are not re-hashed).

Implementation: `src/lottolab/research/b649_eh01_matrix_profile.py` (EH01),
`src/lottolab/research/b649_eh10_permutation_entropy.py` (EH10),
`src/lottolab/research/b649_eh01_eh10_shared.py` (permutation/Holm/era
mechanics shared by both). Each carries its own literal-formula reference
implementation, cross-checked against the optimized real-execution path on
synthetic fixtures in `tests/unit/test_b649_eh01_matrix_profile.py` and
`tests/unit/test_b649_eh10_permutation_entropy.py` — the proposal's required
`synthetic_fixture_check` (section 10.3). No matrix-profile or
permutation-entropy package is added to the project; both hypotheses are
pure-Python/stdlib, matching this project's existing numpy-free convention.

## 3. Dataset identity (resolves proposal prelock issue #2)

```text
source_path:            /Users/kelvin/VibeCoding-WorkSpace/.task-data/
                          BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite
table:                   research_draw_bindings
lottery_type:            BIG_LOTTO
draw_data_version:       canonical-full-history-2382-draws-v1 (verified superset;
                          the older canonical-full-history-2157-draws-v1 rows are a
                          strict content subset -- 0 rows present there and absent here)
eligible_history_rule:   EXCLUDE rows where draw_number == YYYYMMDD(draw_date)
                          (150 rows -- a different, mislabeled game; same
                          discriminator independently used by the 2026-08-12
                          contamination audit and the sealed
                          REGIME_CHANGE_POINT_CUSUM_B649_V1 cell)
row_count:               2138
date_range:              2007-03-09 .. 2026-07-31
logical_sha256:          a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918
```

Reading raw draw values to establish this identity (row count, date range,
contamination count, content hash) is preregistration-time dataset pinning,
not an outcome-blindness breach: it is a structural fact about the dataset
container, computed the same way the original proposal's own section 1.2
inspected structural facts (dependency declarations, rule contracts) without
computing any EH01/EH10 statistic. No motif/discord/entropy value was
computed before this hash was locked.

## 4. Implementation route (resolves proposal prelock issues #3-4)

```text
eh01_algorithm:    causal (strict-left, non-overlapping) O(n^2) incremental
                    diagonal dot-product profile, restricted to the causal
                    admissible region only (never computes the symmetric/
                    future half a general-purpose matrix profile would)
eh10_algorithm:     direct rolling ordinal-pattern scan (already O(n * W * d),
                    no shortcut needed -- EH10's total cost is negligible
                    next to EH01's)
dependencies_added: none (pure Python 3.13 stdlib: hashlib, math, sqlite3,
                    itertools -- this project has no numpy/scipy installed)
parallelism:        stdlib multiprocessing across independent permutation
                    replicates (an execution-engineering choice; changes
                    wall-clock only, not any locked statistic, seed, or
                    ordering -- every replicate's result is independent of
                    how many workers computed it)
synthetic_fixture_check: PASS -- 66/66 tests, including an engineered exact
                    motif tie (support_count=3, matched exactly between the
                    literal-formula and optimized implementations) and a
                    monotonic-series zero-entropy ground truth for EH10
```

## 5. No-rescue commitment

After `tools/hash_preregistration_eh01_eh10_b649.py` is run and
`preregistration_hash_sha256` is recorded, no window, order, tie rule,
null policy, permutation count, era partition, threshold, or comparator
decision may change in response to any EH01 or EH10 result. A materially
different design is a new variant ID under a new Owner-approved proposal,
exactly as proposal section 14.1 states. `PARAMETER_RESCUE_RUN: NO` is
reported unconditionally regardless of outcome.

## 6. Scope boundary

`STRUCTURAL_TEMPORAL_ORDINAL_EVIDENCE`: in scope, for EH01 and EH10
independently. `PREDICTIVE_ADVANTAGE` / `ALLOCATION_BENEFIT` /
`PRIZE_VALUE_ADVANTAGE` / `ECONOMIC_OPTIMALITY`: out of scope, `NOT_TESTED`.
No combined EH01+EH10 effect is computed (proposal section 6.1, 14.4). No
production prediction generation. No DB mutation (the sealed baseline is
opened `PRAGMA query_only`). No cross-lottery replication in this task.

## 7. Preregistration hash

Computed over the canonical JSON (LCJ-1, `lottolab.evidence.canonical_json`)
of every locked parameter in sections 3-4 above plus every EH01/EH10
statistic/null/multiplicity/classification parameter from proposal sections
3-9 — recorded in
`docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-preregistration-hash.json`
by `tools/hash_preregistration_eh01_eh10_b649.py`, generated together with
this document and never regenerated after any EH01/EH10 result exists.
