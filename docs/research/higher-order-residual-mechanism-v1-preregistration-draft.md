# STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1 — preregistration DRAFT

Status: DRAFT — NOT LOCKED ｜ 2026-08-16 ｜ native triple-geometry
computation not executed

This draft was produced by
`STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1`. It is
not a Matrix result and has no hash. A later Owner-authorized task must
either approve this exact draft or revise and re-draft it, then create and
verify a lock hash before invoking any native portfolio constructor or
triple-geometry computation. See the design doc
(`strategy-matrix-phase6-higher-order-residual-mechanism-design-r1.md`) for
the full derivation this preregistration freezes the scope of.

```text
PREREGISTRATION_LOCKED: NO
HASH: NOT_COMPUTED
REAL_S3_GEOMETRY_TRIPLE_HISTOGRAM: NOT_RUN
```

## 0. Identity

```text
STUDY_ID:              STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
SOURCE_TYPE:           STRATEGY_MATRIX_NATIVE_MECHANISM
EVIDENCE_TYPE:         EXACT_COMBINATORIAL
DESIGN_SOURCE:         STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1
FIXED_PHASE5_AUTHORITY (unchanged, restated not rederived):
  REDUNDANCY_REDUCTION_REPLICATED
  PAIRWISE_COLLISION_REDUCTION_REPLICATED
  GLOBAL_OPTIMUM_STATUS: UNKNOWN
STARTING_CLASSIFICATION:
  DAILY_539_PAIRWISE_COLLISION_EXACTLY_SUFFICIENT_VS_BIG_LOTTO_POWER_LOTTO_ZONE1_HIGHER_ORDER_RESIDUAL
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 1. Research question and disclosed prior observation

For each native lottery structure and `k>1` exposure rung, does the sealed
`HIGHER_ORDER_RESIDUAL` (`H = T3+T4+...`, already an exact sealed number at
every cell) admit an exact geometric explanation via the ticket-triple
intersection structure — the same kind of identity Phase 5 already proved
for `S2` — and does that explanation account for why `DAILY_539` is
`PAIRWISE_COLLISION_EXACTLY_SUFFICIENT` while `BIG_LOTTO`/`POWER_LOTTO_
zone1` are not?

The zero-versus-nonzero split is already sealed (Phase-5 report S4) and is
not a new outcome-blind hypothesis. This design's own toy-scale Necessary
Mass Bound Lemma (design doc S5) already predicts and, at toy scale plus
formula evaluation at the real `(n,d,m)` triples, retrodicts the sealed
`k=3` `DELTA_S3=-64` for both `BIG_LOTTO` and `POWER_LOTTO_zone1` and the
sealed `DELTA_S3=0` for `DAILY_539` at every tested `k` (design doc S7).
This is disclosed as a known, already-computed starting expectation for
`H1` (design doc S9), not presented as a fresh discovery from native
execution — the native execution's job is to confirm `H1` via the
`S3_GEOMETRY == S3_MULTIPLICITY` identity on the *actual* sealed portfolios
(not a hypothetical shape) and to newly resolve `H2` (the magnitude/k-growth
question), which is genuinely unresolved.

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
P638_ZONE2:          OUT_OF_SCOPE
ARM_C:               OUT_OF_SCOPE
```

`k=1` and `k=3` (only 1 or fewer triples exist) are identity/sanity
boundaries and are excluded from the replicated `k>=3`-with-nontrivial-
triple-count decision predicates where noted below, but are still computed
and reported.

## 3. Frozen arms and input authority

Identical arms and canonical constructors as the sealed Phase-5 study
(unchanged; re-verify at execution time, do not re-derive):

```text
ARM_S: canonical cyclic Sidon-shift portfolio
ARM_B: canonical deterministic greedy minimum-overlap portfolio

BIG_LOTTO:        cyclic_sidon_shift.sidon_shift_portfolio,
                  greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49, 6, k)
DAILY_539:        cyclic_sidon_shift_t539.sidon_shift_portfolio,
                  greedy_min_overlap_constructor_t539.greedy_min_overlap_portfolio_t539
POWER_LOTTO_zone1: cyclic_sidon_shift_p638.sidon_shift_portfolio,
                  greedy_min_overlap_constructor_p638_zone1.greedy_min_overlap_portfolio_p638_zone1
```

The untracked duplicate `cyclic_sidon_shift_p638_zone1.py` remains not a
canonical input and must not be read or imported (unchanged from Phase 5).

**New read-only input for this study:** the sealed
`low-overlap-geometry-mechanism-v1-result.json`
(blob `dc17f0b39c9baf81f8c85162d5db554e7ca2797a`), specifically per
`(lottery, arm)`:

```text
per_lottery[lottery].portfolio_sha256[arm]        -- to verify regeneration
per_lottery[lottery].per_k[k].arms[arm].collision_moments["3"]  -- S3_MULTIPLICITY,
                                                      reused, not recomputed
per_lottery[lottery].per_k[k].arms[arm].geometry.max_pairwise_overlap
```

This file is read-only input; it is not modified, and its own preregistration
hash (`8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be`) is
re-verified unchanged before use, exactly as Phase 5 re-verified its own
upstream inputs.

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
                      (design doc S6; ticket_triple_hit_event_intersection_size)

triple_histogram = {canonical_shape: count of triples with that shape}

S3_GEOMETRY = sum over triple_histogram of count * H_m^(3)(n,d,shape)

mass_bound(shape) = r_ij + r_il + r_jl - s
triple_impossible(shape) = mass_bound(shape) < 3*minimum_matches - draw_size
```

All quantities are exact nonnegative integers; no floating-point value is
load-bearing (unchanged convention from Phase 5).

## 5. Frozen geometry and the independent S3 check

For each arm and `k`, record, in addition to Phase-5's already-frozen
pairwise geometry fields (unchanged, not recomputed — reused from the
sealed result where the portfolio hash matches):

- `ticket_triple_intersection_histogram`: the complete canonical-shape
  histogram over every `C(k,3)` unordered ticket triple.
- `saturated_triple_count`: the number of triples whose shape has
  `mass_bound == 3*minimum_matches - draw_size` exactly (the narrowest
  class that can possibly contribute, per the Necessary Mass Bound Lemma) —
  the direct, predefined answer to `H2` (design doc S9).
- `s3_geometry` and the required identity `S3_GEOMETRY == S3_MULTIPLICITY`.

```text
REQUIRED: S3_GEOMETRY == S3_MULTIPLICITY exactly, at every (lottery, arm, k)
          with k >= 3.
```

This is the triple-order analog of Phase 5's `S2_GEOMETRY == S2_
MULTIPLICITY` check (S5 there, S6 in the design doc here). It is stronger
than a magnitude correlation: it proves precisely how the full ticket-
triple intersection histogram induces the sealed `S3` value.

## 6. Primary endpoints

For every `(lottery, k)` with `k in {3,5,10,15,20}`, persist:

1. `ticket_triple_intersection_histogram` for both arms.
2. `S3_GEOMETRY` for both arms, and the identity check result.
3. `saturated_triple_count` for both arms (the `H2` endpoint).
4. The already-sealed `S3_MULTIPLICITY`, `T3`, `T4`, `T5`, `H`, and
   `mechanism_descriptor`, copied read-only from the sealed result for
   side-by-side reporting — not recomputed, not reclassified.
5. `residual_to_net_gain_ratio = H / DELTA_COVERED` (design doc S12),
   `NOT_APPLICABLE_ZERO_NET_GAIN` when `DELTA_COVERED == 0`.

`k=1` is excluded (no triples exist). Secondary `j=4` geometry
(`S4_GEOMETRY == S4_MULTIPLICITY`) is explicitly OUT OF SCOPE for this
lock unless a lock amendment adds it as a clearly secondary diagnostic; it
can never change the primary classification below (mirrors Phase 5's own
treatment of `M4+`/`M5+`).

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
  S3_MULTIPLICITY == 0 for that cell (i.e. the Necessary Mass Bound Lemma's
  prediction matches the sealed zero/nonzero pattern with no exceptions).

MASS_BOUND_PREDICTION_NOT_UNIVERSAL
  otherwise; list every exception.

GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

`S3_GEOMETRY_IDENTITY_REPLICATED` and `MASS_BOUND_PREDICTS_ZERO_SPLIT` are
separate claims; the first is a pure arithmetic identity, the second is
this design's H1 hypothesis actually being confirmed against the real
portfolios rather than only the toy/formula evidence in S7-S8 of the design
doc. Neither predicate being satisfied is assumed by this preregistration.

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

- source commit/tree/blob or matrix-ID mismatch;
- this preregistration's own hash mismatch;
- regenerated portfolio SHA-256 mismatch against the sealed value (this
  would mean the sealed `S3_MULTIPLICITY` cannot be trusted as describing
  the regenerated portfolio, and reuse is unsafe);
- invalid/non-prefix/duplicate portfolio;
- any negative ticket-triple region size (an unrealizable shape; see
  `_triple_region_sizes`'s validation, design doc S15);
- `S3_GEOMETRY != S3_MULTIPLICITY` at any cell.

No fallback, tolerance, float comparison, Monte Carlo rescue, or omitted
cell is permitted, matching Phase 5's convention exactly.

## 9. Computational feasibility

No winning-space enumeration is required (S8): the dominant cost is portfolio
regeneration, already measured by Phase 5 at ≈774.5s (`BIG_LOTTO`) + ≈30.0s
(`DAILY_539`) + ≈159.0s (`POWER_LOTTO_zone1`) ≈ 16.1 minutes total, plus a
`C(k,3)`-bounded triple-geometry pass (`C(20,3)=1140` triples at most per
lottery per arm) that the toy test suite already demonstrates runs in well
under a second per cell. This is a strictly smaller computation than Phase
5's own execution (design doc S11).

## 10. Scope and no-rescue commitment

Arms, contract, k ladder, endpoints, evaluation method, and
classification/replication rules are locked by this file before any real
native-scale triple-geometry value is computed. No new constructor, no
different event threshold, no k-ladder change, no classification-rule
change, no secondary event promoted to primary, once results are visible.
`P638_ZONE2`, `ARM_C`, prediction, prize value, profit, and global
optimization cannot rescue or reinterpret the primary result. Any change
required after lock stops with
`STOP_HIGHER_ORDER_RESIDUAL_MECHANISM_POST_LOCK_CHANGE_REQUIRED` instead of
being made silently.

```text
PREDICTIVE_ADVANTAGE:   NOT_TESTED
PRIZE_VALUE_ADVANTAGE:  NOT_TESTED
ECONOMIC_OPTIMALITY:    NOT_TESTED
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
P638_ZONE2:             OUT_OF_SCOPE
ARM_C:                  OUT_OF_SCOPE
```

## 11. Preregistration hash

Not yet computed — `PREREGISTRATION_LOCKED: NO`. At lock time, a future
task computes the LCJ-1 canonical-JSON SHA-256 over every locked parameter
above (study/task identity, canonical input commit/tree, exposure ladder,
primary event, per-lottery pool/draw sizes, canonical constructor
identities, the sealed Phase-5 result's own hash and blob SHAs, and the
mechanism/geometry formula definitions), following the identical method
Phase 5 used (`tools/hash_preregistration_low_overlap_geometry_mechanism_
v1.py` is the precedent to adapt, not to modify).

```text
PREREGISTRATION_LOCKED: NO
LOCK_BLOCKERS: OWNER LOCK AUTHORIZATION NOT YET GRANTED (design-only task)
REAL_S3_GEOMETRY_TRIPLE_HISTOGRAM: NOT_RUN
```
