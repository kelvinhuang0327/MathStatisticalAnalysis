# EH02 — B649 Track B cross-lottery transfer entropy — locked preregistration

Status: LOCKED before any EH02 statistic was computed ｜ 2026-08-16

## 0. Identity and authorization chain

```text
TASK_ID:                 EXPERIMENT_H02_V1_LOCK_EXECUTE_R1
AUTHORITY_A (proposal):  B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md (off-repo)
AUTHORITY_A_SHA256:      69e03026ce40962cfed8a8295336918edc6f6db8d3d6f0f3f5a487a1bfc9262b
AUTHORITY_B (resolution):B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1.md (off-repo)
AUTHORITY_B_SHA256:      76aef07bedb10d51ab0446170c116bf9b5ffee8fc3b5c36ad8e13c14f46daae7
OWNER_AUTHORIZATION:     AUTHORIZE_EXPERIMENT_H02_V1_LOCK_EXECUTE_R1
VARIANT_ID:              EH02_CROSS_LOTTERY_TRANSFER_ENTROPY_B649_V1
HYPOTHESIS_FAMILY_ID:    TRANSFER_ENTROPY_DIRECTED_LAG_GRAPH (Frontier V2 catalog name;
                          descriptive only, this task does not write to the
                          cross-lottery research ledger)
LOTTERY_TYPE:            BIG_LOTTO (target); DAILY_539, POWER_LOTTO (Zone-1 only) (sources)
NEUTRAL_ALIASES:         Dataset A = target (BIG_LOTTO); Dataset B = source 1
                          (DAILY_539); Dataset C = source 2 (POWER_LOTTO Zone-1)
```

**Authority location, explicitly ratified.** Both authority artifacts are
off-repo (`~/VibeCoding-WorkSpace/*.md`, one directory above this project's
git root) and untracked by git — no commit hash pins them the way every
other input to this design is pinned. Discovered missing from an
under-the-project-workspace search, then located at their known prior-session
paths and confirmed unique (each contains exactly one occurrence of its
required `FINAL_CLASSIFICATION` marker). The Owner explicitly authorized
using them as-is at their current content hash (recorded above as
`AUTHORITY_A_SHA256`/`AUTHORITY_B_SHA256`) rather than requiring an in-repo
copy, on condition that any drift between authority-pinning and this lock
stops the task (`STOP_H02_AUTHORITY_DRIFT`) — reverified immediately before
this document was written; both hashes were unchanged.

**Acceptance-gate note.** Both authority documents are self-stopping
(`STATUS: PROPOSAL_FOR_OWNER_REVIEW` / `DATA_AUTHORITY_AND_PARAMETER_LOCK_
RESOLVED_FOR_OWNER_REVIEW`, each ends with `STOP.`) — neither approves
itself, and no separate `owner_decision_id` artifact exists. The current
task's own Owner-authorized packet (`AUTHORIZE_EXPERIMENT_H02_V1_LOCK_
EXECUTE_R1`) names both artifacts explicitly as "the scientific authority"
and directs applying them without outcome-dependent revision. This chat-level
authorization is treated as the acceptance record, the same pattern
`b649-track-b-eh01-eh10-lock-execute-r1` already established (no
`ACCEPTANCE_GATE: PASS` file exists there either).

**Parameter-drift check: PASS.** Every scalar/categorical value below was
read directly from Authority A Sec. 0/12/15 and Authority B Sec. 5.1/7 (not
from chat memory); nothing here is invented or rescued. `STOP_H02_POST_LOCK_
CHANGE_REQUIRED` does not apply — no load-bearing field was left unresolved.

## 1. Scientific claim (per Authority A Sec. 4.1, 17.2)

For each of `EDGE_1: T539 -> B649` and `EDGE_2: P638Z1 -> B649`: does `L`'s
causally available last-strictly-prior draw contain directed conditional
information about B649's next main-number-sum tertile, beyond what B649's
own immediately preceding value already predicts, under the locked
representation, discretization, and both required controls (timing,
directionality)? `SIGNAL` means
`EH02_DIRECTED_INFORMATION_TRANSFER_AT_LOCKED_REPRESENTATION_LAG_AND_
CONTROLS` only, per edge. Not a predictive-advantage, allocation, prize
-value, universal-causality, or arbitrary-lag claim (all `NOT_TESTED`).
Both edges are reported separately; concordant labels do not form a joint
effect, discordant labels do not permit reporting only the favorable edge.

## 2. Exact definitions: authoritative source

Every formula (scalar representation, causal alignment, discretization, tie
handling, the Schreiber-2000 plug-in transfer-entropy and mutual-information
estimators, null/surrogate construction, timing and directionality controls,
Holm correction, classification thresholds) is defined verbatim in Authority
A Sec. 2-10, pinned by `AUTHORITY_A_SHA256` above, and is not re-derived
here. This document and `tools/hash_preregistration_eh02_b649.py`'s
`LOCKED_PARAMETERS` record only the scalar/categorical choices that pin one
exact design out of that design space, mirroring the precedent set by
`eh01-eh10-b649-ordinal-temporal-v1-preregistration.md`.

**Implementation-level operationalizations pinned by this task (not present
as an exact formula in Authority A, decided before any real data is read,
`PROJECT_CONVENTION`/`STANDARD_STATISTICAL_CONVENTION` rationale only — see
`src/lottolab/research/b649_eh02_transfer_entropy.py` module docstring for
full detail):**

- Each of the three physical series (B649, T539, P638 Zone-1) is
  causally tertile-discretized exactly once, over its own full chronological
  history; the resulting bin labels are reused unchanged whether that series
  is acting as target or as source (forward vs. reverse direction).
- Tertile cutpoints at causal position `i` (`m = i` strictly-prior
  observations) use order-statistic ranks `floor(k*m/3)` for `k=1,2` over the
  tie-broken-ascending prior sample; positions with `m < 2` take the middle
  bin by convention (both always inside the 200-observation burn-in, so this
  convention never reaches an analyzed row).
- `ERA4` permutation key material uses each position's *global* 1-indexed
  eligible-index position, not a per-era-local renumbering (mirrors the
  EH01/EH10 shared module's own choice of a global rather than locally
  re-based key).

Implementation: `src/lottolab/research/b649_eh02_transfer_entropy.py` (tie
handling, discretization, TE/MI estimators, `EDGE_ID`-and-hypothesis-salted
permutation generator, causal alignment); `src/lottolab/research/
b649_eh02_dataset.py` (T539/P638 Zone-1 read-only loaders; B649 reuses
`b649_eh01_eh10_dataset.load_clean_b649_history` unchanged, same pin).
`Holm` correction and `ERA4` era-boundary assignment are imported directly
from `b649_eh01_eh10_shared` (identical mathematics, no reason to
re-implement). Cross-checked against the required hand-computable synthetic
fixture (Authority A Sec. 13.3) in `tests/unit/test_b649_eh02_transfer_
entropy.py` before any real B649/T539/P638 value was read.

## 3. Dataset identity (resolves Authority A prelock issues 2-3, per Authority B)

```text
DATASET_A (target, BIG_LOTTO):
  source_path:    /Users/kelvin/VibeCoding-WorkSpace/.task-data/
                   BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite
  table:          research_draw_bindings
  filter:         lottery_type=BIG_LOTTO AND
                   draw_data_version=canonical-full-history-2382-draws-v1 AND
                   EXCLUDE_DATE_LIKE (150 contaminant rows excluded)
  row_count:      2138
  date_range:     2007-03-09 .. 2026-07-31
  logical_sha256: a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918
  (identical pin to EH01/EH10; selected over the 2,145-row legacy
   strategy-replay byproduct chain -- see Authority B Sec. 1 for the full
   provenance resolution.)

DATASET_B (source 1, DAILY_539):
  source_path:    /Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/
                   T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/t539_wave1.sqlite3
  table:          source_draws
  filter:         lottery_type=DAILY_539
  row_count:      5930
  date_range:     2007-01-01 .. 2026-08-01
  logical_sha256: 794ef4e5ed3268c750f484836b0c31591ce56f287dca4b882b5925a6fddcaa42

DATASET_C (source 2, POWER_LOTTO Zone-1):
  source_path:    /Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/
                   P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/p638_wave1.sqlite3
  table:          draws (Zone-1 main_numbers_json only; Zone-2/second_number
                   confirmed OUT_OF_SCOPE, never read into any join/hash/count)
  row_count:      1933
  date_range:     2008-01-24 .. 2026-07-30
  logical_sha256: 49c1911154a0f95256ab12b25f5301dfb4480e4302dc0d3b6f422d247ee46df0

EXPECTED ELIGIBILITY (Authority B Sec. 4; independently reproduced by the
runner before any TE/MI statistic is computed -- STOP_DATASET_AUTHORITY_
MISMATCH if it disagrees):
  EDGE_1 (T539->B649):    eligible post-burn-in 1937; ERA4 sizes [485,484,484,484]
  EDGE_2 (P638Z1->B649):  eligible post-burn-in 1846; ERA4 sizes [462,461,462,461]
```

Reading raw draw values to establish this identity (row count, date range,
content hash) is preregistration-time dataset pinning, not an
outcome-blindness breach — it is a structural fact about each dataset
container, computed the same way Authority B itself established these facts
without computing any TE/MI/p-value. No EH02 statistic was computed before
this hash was locked.

## 4. Implementation route (resolves Authority A prelock issues 4-6)

```text
estimator_algorithm: discrete plug-in (Schreiber 2000) conditional transfer
                      entropy and unconditioned lagged mutual information,
                      O(n) counting over the eligible index set -- no
                      pairwise/k-NN sweep
dependencies_added:   none (pure Python 3.13 stdlib: hashlib, math, sqlite3,
                      bisect, datetime, collections.Counter -- this project
                      has no numpy/scipy installed)
synthetic_fixture_check: two hand-derived 3-symbol cases over the same 9
                      (x_prev, y_prior) pairs (all combinations of {0,1,2}^2
                      exactly once): full-dependency (x_next = y_prior) gives
                      TE = MI = ln(3) exactly; null (x_next = x_prev, y
                      irrelevant) gives TE = MI = 0 exactly. Both must PASS
                      before any real B649/T539/P638 value is read.
repository:           /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis
branch:               main
lock_time_base_head:  e6d5d0785d900386c2469bb626dc6ad2f2195282
runner_path:          tools/run_eh02_b649_v1.py
```

## 5. No-rescue commitment

After `tools/hash_preregistration_eh02_b649.py` is run and
`preregistration_hash_sha256` is recorded, no representation, lag, bin count,
tie rule, estimator, null, seed, permutation count, era rule, stale-day
offset, directionality gate, threshold, or comparator decision may change in
response to any EH02 result. A materially different design is a new variant
ID under a new Owner-approved proposal (Authority A Sec. 17.1).
`PARAMETER_RESCUE_RUN: NO` is reported unconditionally regardless of outcome.

## 6. Scope boundary

`EH02_DIRECTED_INFORMATION_TRANSFER_AT_LOCKED_REPRESENTATION_LAG_AND_
CONTROLS`: in scope, for `EDGE_1` and `EDGE_2` independently.
`PREDICTIVE_ADVANTAGE` / `ALLOCATION_BENEFIT` / `PRIZE_VALUE_ADVANTAGE` /
`UNIVERSAL_CROSS_LOTTERY_CAUSALITY` / `ARBITRARY_LAG_GENERALIZATION`: out of
scope, `NOT_TESTED`. No combined `EDGE_1`+`EDGE_2` effect is computed. No
production prediction generation. No DB mutation (every dataset opened
read-only). No newly-available contextual field or metadata beyond what
Authority A/B name.

## 7. Preregistration hash

Computed over the canonical JSON (LCJ-1, `lottolab.evidence.canonical_json`)
of every locked parameter in sections 3-4 above plus every EH02
representation/estimator/null/control/multiplicity/classification parameter
from Authority A Sec. 2-10 and Authority B Sec. 5 — recorded in
`docs/research/matrix-native-results/eh02-b649-cross-lottery-transfer-entropy-v1-preregistration-hash.json`
by `tools/hash_preregistration_eh02_b649.py`, generated together with this
document and never regenerated after any EH02 result exists.
