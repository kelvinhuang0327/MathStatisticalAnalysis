# STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1 — locked preregistration

Status: LOCKED before any native triple-geometry computation ｜ 2026-08-16 ｜
Strategy Matrix Phase 6, cross-lottery higher-order (`S3`) residual mechanism

`TASK_ID: STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_LOCK_EXECUTE_R1`,
Owner authorization
`AUTHORIZE_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_LOCK_EXECUTE_R1`.
Locks and executes the design frozen in
`docs/research/strategy-matrix-phase6-higher-order-residual-mechanism-design-r1.md`
and
`docs/research/higher-order-residual-mechanism-v1-execution-plan-schema.md`
(design commit `21cc748bdeb3a81688b62a077665e61a9d079bb9`), which used the
exact same two-step design-then-lock-and-execute pattern the sealed Phase-5
low-overlap geometry mechanism study already used. Three native lottery
structures, two arms (Sidon, Arm-B) each — Arm-C, P638 Zone-2, and
`J4_GEOMETRY` are explicitly `OUT_OF_SCOPE` and have no counterpart in this
task. No winning-space enumeration is performed: `S3_MULTIPLICITY` is reused
read-only from the already-sealed Phase-5 result.

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256
PREREGISTRATION_HASH_SHA256: 354d96bcee4c9e4efb59e3e88f18c686fdfb23ed00be5dae2c0ea0d133e550a6
REAL_S3_GEOMETRY_TRIPLE_HISTOGRAM: NOT_YET_RUN_AT_LOCK_TIME
```

## 0. Identity

```text
STUDY_ID:               STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1
HYPOTHESIS_FAMILY_ID:   DIVERSIFICATION
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE_MECHANISM
EVIDENCE_TYPE:          EXACT_COMBINATORIAL
DESIGN_COMMIT:          21cc748bdeb3a81688b62a077665e61a9d079bb9
CANONICAL_INPUT_COMMIT: 81104798a9f265de400c1a8bc476e109b14e1a4a
CANONICAL_INPUT_TREE:   a82dc823bab4d396ac63a8856d507b43d393047d
FIXED_PHASE5_AUTHORITY (Owner-supplied, not rederived):
  REDUNDANCY_REDUCTION_REPLICATED
  PAIRWISE_COLLISION_REDUCTION_REPLICATED
  GLOBAL_OPTIMUM_STATUS: UNKNOWN
STARTING_CLASSIFICATION:
  DAILY_539_PAIRWISE_COLLISION_EXACTLY_SUFFICIENT_VS_BIG_LOTTO_POWER_LOTTO_ZONE1_HIGHER_ORDER_RESIDUAL
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

The canonical `origin/main` commit/tree, exact sealed input Git blobs, and
this locked preregistration hash must all be re-verified before the first
native constructor call. Any mismatch stops execution with
`STOP_PHASE6_SEALED_INPUT_DRIFT` (input drift) or
`STOP_PHASE6_PORTFOLIO_HASH_MISMATCH` (regenerated portfolio does not match
the sealed one).

## 1. Research question and disclosed prior observation

For each native lottery structure and `k>=3` exposure rung, does the sealed
`HIGHER_ORDER_RESIDUAL` (`H = T3+T4+...`, already an exact sealed number at
every cell) admit an exact geometric explanation via the ticket-triple
intersection structure — the same kind of identity Phase 5 already proved
for `S2` — and does that explanation account for why `DAILY_539` is
`PAIRWISE_COLLISION_EXACTLY_SUFFICIENT` while `BIG_LOTTO`/`POWER_LOTTO_
zone1` are not?

The zero-versus-nonzero split is already sealed (Phase-5 report S4) and is
not a new outcome-blind hypothesis. The design's own toy-scale Necessary
Mass Bound Lemma (design doc S5) already predicts and, at toy scale plus
formula evaluation at the real `(n,d,m)` triples, retrodicts the sealed
`k=3` `DELTA_S3=-64` for both `BIG_LOTTO` and `POWER_LOTTO_zone1` and the
sealed `DELTA_S3=0` for `DAILY_539` at every tested `k` (design doc S7).
This is disclosed as a known, already-computed starting expectation for
`H1`, not presented as a fresh discovery from native execution — the native
execution's job is to confirm `H1` via the `S3_GEOMETRY == S3_MULTIPLICITY`
identity on the *actual* sealed portfolios (not a hypothetical shape) and to
newly resolve `H2` (the magnitude/`k`-growth question), which is genuinely
unresolved.

## 2. Frozen lottery, exposure, and event scope

```text
BIG_LOTTO:          pool=49, draw/ticket=6, event=M3_PLUS
DAILY_539:          pool=39, draw/ticket=5, event=M3_PLUS
POWER_LOTTO_ZONE1:  pool=38, draw/ticket=6, event=ZONE1_M3_PLUS
K_LADDER:            [1, 3, 5, 10, 15, 20]           (identical to Phase 5)
PRIMARY_EVENT:       minimum_matches=3 only
SECONDARY_EVENTS:    NOT_RUN_BY_DEFAULT; cannot change primary decision
MONTE_CARLO:         NONE
HISTORICAL_DRAWS:    NOT_USED
NATIVE_WINNING_SPACE_ENUMERATION: NONE (S3_MULTIPLICITY reused from sealed Phase 5)
P638_ZONE2:          OUT_OF_SCOPE
ARM_C:               OUT_OF_SCOPE
J4_GEOMETRY:         OUT_OF_SCOPE (S4_GEOMETRY==S4_MULTIPLICITY defined but not run)
```

`k=1` is excluded entirely from the per-`k` triple-geometry table: no
ticket triple exists at `k<3`. `k=1` is still computed and reported for
`portfolio_sha256` verification only.

## 3. Frozen arms and input authority

Identical arms and canonical constructors as the sealed Phase-5 study
(unchanged; re-verified at execution time, not re-derived):

```text
ARM_S: canonical cyclic Sidon-shift portfolio
ARM_B: canonical deterministic greedy minimum-overlap portfolio

BIG_LOTTO:         cyclic_sidon_shift.sidon_shift_portfolio,
                   greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49, 6, k)
DAILY_539:         cyclic_sidon_shift_t539.sidon_shift_portfolio,
                   greedy_min_overlap_constructor_t539.greedy_min_overlap_portfolio_t539
POWER_LOTTO_zone1: cyclic_sidon_shift_p638.sidon_shift_portfolio,
                   greedy_min_overlap_constructor_p638_zone1.greedy_min_overlap_portfolio_p638_zone1
```

Sidon base sets (0-indexed, verified unchanged at execution time):

```text
BIG_LOTTO:         (0, 1, 3, 7, 12, 20)
DAILY_539:         (0, 1, 3, 7, 12)
POWER_LOTTO_zone1: (0, 1, 3, 7, 17, 30)
```

The untracked duplicate `cyclic_sidon_shift_p638_zone1.py` remains not a
canonical input and must not be read or imported (unchanged from Phase 5).

**Read-only input for this study:** the sealed
`low-overlap-geometry-mechanism-v1-result.json`
(blob `dc17f0b39c9baf81f8c85162d5db554e7ca2797a`), specifically per
`(lottery, arm)`:

```text
per_lottery[lottery].portfolio_sha256[arm]                       -- to verify regeneration
per_lottery[lottery].per_k[k].arms[arm].collision_moments["3"]    -- S3_MULTIPLICITY, reused
per_lottery[lottery].per_k[k].arms[arm].geometry.max_pairwise_overlap  -- reused, not recomputed
per_lottery[lottery].per_k[k].comparison.higher_order_signed_terms    -- T3/T4/T5, reused
per_lottery[lottery].per_k[k].comparison.delta_covered                -- reused
per_lottery[lottery].per_k[k].comparison.mechanism_descriptor         -- reused
```

This file is read-only input; it is not modified, and its own preregistration
hash (`8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be`) is
re-verified unchanged before use, exactly as Phase 5 re-verified its own
upstream inputs. The Phase-5 pairwise geometry fields (`max_pairwise_
overlap` etc.) are copied read-only from this sealed file for side-by-side
reporting; they are not recomputed by this study.

## 4. Frozen mechanism and geometry quantities

For a portfolio of `k` tickets and threshold `m` (unchanged from Phase 5):

```text
c(w) = number of portfolio tickets hitting w at M3+
S_j  = sum_w C(c(w), j)
COVERED = S1 - S2 + S3 - ...
```

New for this study, for every unordered ticket triple `{t_i,t_j,t_l}`:

```text
r_ij, r_il, r_jl = pairwise ticket-number intersection sizes
s                = |t_i ∩ t_j ∩ t_l|
canonical_shape  = (sorted(r_ij, r_il, r_jl), s)

H_m^(3)(n,d,shape) = exact count of winning draws hitting all 3 tickets at m
                      (ticket_triple_hit_event_intersection_size)

triple_histogram = {canonical_shape: count of triples with that shape}

S3_GEOMETRY = sum over triple_histogram of count * H_m^(3)(n,d,shape)

mass_bound(shape) = r_ij + r_il + r_jl - s
triple_impossible(shape) = mass_bound(shape) < 3*minimum_matches - draw_size
```

All quantities are exact nonnegative integers; no floating-point value is
load-bearing (unchanged convention from Phase 5). Implemented, unchanged
from the design commit, by `src/lottolab/research/higher_order_residual_
mechanism.py` (`canonical_triple_shape`, `ticket_triple_intersection_
histogram`, `ticket_triple_hit_event_intersection_size`, `s3_from_ticket_
triple_intersection_histogram`, `triple_collision_mass_bound`, `triple_
collision_is_impossible`, `max_pairwise_overlap_forces_zero_triple_
collisions`); none of these functions is modified by this lock.

## 5. Frozen geometry and the independent S3 check

For each arm and `k>=3`, record:

- `ticket_triple_intersection_histogram`: the complete canonical-shape
  histogram over every `C(k,3)` unordered ticket triple of the regenerated
  portfolio.
- `saturated_triple_count`: the number of triples whose shape has
  `mass_bound == 3*minimum_matches - draw_size` exactly (the narrowest class
  that can possibly contribute, per the Necessary Mass Bound Lemma) — the
  direct, predefined answer to `H2`.
- `s3_geometry` and the required identity `S3_GEOMETRY == S3_MULTIPLICITY`.

```text
REQUIRED: S3_GEOMETRY == S3_MULTIPLICITY exactly, at every (lottery, arm, k)
          with k >= 3.
```

This is the triple-order analog of Phase 5's `S2_GEOMETRY == S2_
MULTIPLICITY` check. It is stronger than a magnitude correlation: it proves
precisely how the full ticket-triple intersection histogram induces the
sealed `S3` value.

## 6. Primary endpoints

For every `(lottery, k)` with `k in {3,5,10,15,20}`, persist:

1. `ticket_triple_intersection_histogram` for both arms.
2. `S3_GEOMETRY` for both arms, and the identity check result.
3. `saturated_triple_count` for both arms (the `H2` endpoint).
4. The already-sealed `S3_MULTIPLICITY`, `T3`, `T4`, `T5`, `H`, and
   `mechanism_descriptor`, copied read-only from the sealed result for
   side-by-side reporting — not recomputed, not reclassified.
5. `residual_to_net_gain_ratio = H / DELTA_COVERED`,
   `NOT_APPLICABLE_ZERO_NET_GAIN` when `DELTA_COVERED == 0`.

`k=1` is excluded (no triples exist). `S4_GEOMETRY == S4_MULTIPLICITY`
(`j=4` geometry) is explicitly `OUT_OF_SCOPE` for this lock (Owner Packet
`FIXED SCOPE`); `T4`/`T5` are still copied read-only from the sealed result
for context only, per the Owner Packet's `S4+ sealed signed terms may be
reported for context only`.

## 7. Frozen decision outputs

```text
S3_GEOMETRY_IDENTITY_REPLICATED
  iff S3_GEOMETRY == S3_MULTIPLICITY for every (lottery, arm, k>=3) cell.

S3_GEOMETRY_IDENTITY_FAILED
  otherwise; list every failing cell -- this would falsify H1's mechanism
  (not merely weaken it) and execution stops before any classification.

MASS_BOUND_PREDICTS_ZERO_SPLIT
  iff, for every (lottery, arm, k>=3) cell, triple_impossible(shape) being
  true for every triple in the portfolio exactly coincides with
  S3_MULTIPLICITY == 0 for that cell (the Necessary Mass Bound Lemma's
  prediction matches the sealed zero/nonzero pattern with no exceptions).

MASS_BOUND_PREDICTION_NOT_UNIVERSAL
  otherwise; list every exception.

GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

`S3_GEOMETRY_IDENTITY_REPLICATED` and `MASS_BOUND_PREDICTS_ZERO_SPLIT` are
separate claims; the first is a pure arithmetic identity (`H1`'s mechanism,
formally required), the second is `H1`'s hypothesis actually being confirmed
against the real portfolios rather than only the toy/formula evidence in the
design doc. Neither predicate being satisfied is assumed by this lock.

## 8. Exact computation and failure gates

One pass per lottery/arm: regenerate the `k=20` portfolio through the
canonical constructor, verify its SHA-256 against the sealed `portfolio_
sha256`, take ladder prefixes, compute the triple histogram and `S3_
GEOMETRY` per prefix, and compare against the sealed `S3_MULTIPLICITY` read
from `low-overlap-geometry-mechanism-v1-result.json`. No new winning-space
enumeration is performed — that value is already exact and sealed, and
verifying the portfolio hash first is what licenses reusing it instead of
recomputing it.

Execution stops without a result classification on any of:

- source commit/tree/blob or matrix-ID mismatch (`STOP_PHASE6_SEALED_INPUT_DRIFT`);
- this preregistration's own hash mismatch;
- regenerated portfolio SHA-256 mismatch against the sealed value
  (`STOP_PHASE6_PORTFOLIO_HASH_MISMATCH` — this would mean the sealed
  `S3_MULTIPLICITY` cannot be trusted as describing the regenerated
  portfolio, and reuse is unsafe);
- invalid/non-prefix/duplicate portfolio;
- any negative ticket-triple region size (an unrealizable shape;
  `_triple_region_sizes` raises, matching Phase 5's "no fallback,
  tolerance, or omitted cell" convention);
- `sum(triple_histogram counts) != C(k,3)`;
- `S3_GEOMETRY != S3_MULTIPLICITY` at any cell.

No fallback, tolerance, float comparison, Monte Carlo rescue, or omitted
cell is permitted, matching Phase 5's convention exactly.

## 9. Computational feasibility

No winning-space enumeration is required: the dominant cost is portfolio
regeneration, already measured by Phase 5 at ≈774.5s (`BIG_LOTTO`) + ≈30.0s
(`DAILY_539`) + ≈159.0s (`POWER_LOTTO_zone1`) ≈ 16.1 minutes total, plus a
`C(k,3)`-bounded triple-geometry pass (`C(20,3)=1140` triples at most per
lottery per arm) that the toy test suite already demonstrates runs in well
under a second per cell. This is a strictly smaller computation than Phase
5's own execution.

## 10. Scope and no-rescue commitment

Arms, contract, `k` ladder, endpoints, evaluation method, and
classification/replication rules are locked by this file before any real
native-scale triple-geometry value is computed. No new constructor, no
different event threshold, no `k`-ladder change, no classification-rule
change, no secondary event promoted to primary, once results are visible.
`P638_ZONE2`, `ARM_C`, `J4_GEOMETRY`, prediction, prize value, profit, and
global optimization cannot rescue or reinterpret the primary result. Any
change required after this point stops with
`STOP_PHASE6_POST_LOCK_CHANGE_REQUIRED` instead of being made silently.

```text
PREDICTIVE_ADVANTAGE:   NOT_TESTED
PRIZE_VALUE_ADVANTAGE:  NOT_TESTED
ECONOMIC_OPTIMALITY:    NOT_TESTED
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
P638_ZONE2:             OUT_OF_SCOPE
ARM_C:                  OUT_OF_SCOPE
J4_GEOMETRY:            OUT_OF_SCOPE
```

## 11. Preregistration hash

Computed over the LCJ-1 canonical JSON of every locked parameter above
(study/task identity, canonical input commit/tree, exposure ladder, primary
event, per-lottery pool/draw sizes, Sidon base sets, per-arm constructor
identities, the sealed Phase-5 result's own hash/blob SHAs, and this
study's own module blob SHA) by
`tools/hash_preregistration_higher_order_residual_mechanism_v1.py`,
recorded in `higher-order-residual-mechanism-v1-preregistration-hash.json`:

```text
preregistration_hash_sha256 = 354d96bcee4c9e4efb59e3e88f18c686fdfb23ed00be5dae2c0ea0d133e550a6
```

`run_higher_order_residual_mechanism_v1.py` re-verifies this hash before
running and refuses to proceed on a mismatch.

```text
PREREGISTRATION_LOCKED: YES
LOCK_BLOCKERS: NONE
REAL_S3_GEOMETRY_TRIPLE_HISTOGRAM: NOT_YET_RUN_AT_LOCK_TIME
```
