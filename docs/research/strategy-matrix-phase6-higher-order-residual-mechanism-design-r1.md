# STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1 — design

Status: DESIGN COMPLETE — OWNER REVIEW REQUIRED ｜ 2026-08-16 ｜ no native
triple-geometry computation executed

```text
PREREGISTRATION_STATUS: DRAFT_NOT_LOCKED
REAL_S3_GEOMETRY_TRIPLE_HISTOGRAM: NOT_RUN
NEW_MATRIX_SCIENTIFIC_CELL: NONE
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

This document designs the next Matrix-native combinatorial mechanism study.
It does not predict draws, measure profit, choose numbers, rerun Phase 5 or
Arm-C, or create a result. The question is why the sealed Phase-5 low-overlap
geometry mechanism study found `PAIRWISE_COLLISION_EXACTLY_SUFFICIENT` for
`DAILY_539` at every tested `k>1`, while `BIG_LOTTO` and `POWER_LOTTO_zone1`
show `PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL` — a nonzero,
sign-opposing higher-order residual — at every tested `k>1`.

## 0. Identity and authority

```text
TASK_ID:              STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1
FUTURE_STUDY_ID:      STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
SOURCE_TYPE_NOW:       STRATEGY_MATRIX_DESIGN
FUTURE_EVIDENCE_TYPE: EXACT_COMBINATORIAL
FIXED_PHASE5_AUTHORITY (Owner-supplied, not rederived):
  REDUNDANCY_REDUCTION_REPLICATED
  PAIRWISE_COLLISION_REDUCTION_REPLICATED
  GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

The design was derived from canonical `origin/main` commit `8110479`
(merge of PR #138), tree `a82dc823bab4d396ac63a8856d507b43d393047d`. The
dirty, diverged local `main` checkout (still on `e8de3bf`, 13 commits behind
`origin/main`, carrying unrelated in-progress work) was not used as
scientific or file authority; this design was built in a dedicated worktree
checked out directly from `origin/main`, following the same pattern the
Phase-5 mechanism design itself used. No `AGENTS.md` or `AGENTS.override.md`
applies in that canonical tree.

Owner authorization is design-only. `AUTHORIZE_MATRIX_PHASE6_HIGHER_ORDER_
RESIDUAL_MECHANISM_DESIGN_R1`. One later task may lock and execute only
after separate authorization. Push, PR, merge, Arm-C replication, P638
Zone2, historical draws, repair of sealed artifacts, and production or
prospective actions remain outside this task.

## 1. Sealed inputs read, not modified or re-executed

The unique sealed Phase-5 mechanism artifact family satisfying the Owner's
authority requirement (preregistration, multiplicity spectra, `S_j`
decomposition, portfolio geometry for all 3 native structures) is
`low-overlap-geometry-mechanism-v1`, published by PR #138 (commits `05e09d1`
design + `4d15e2f` lock/execute, merged `8110479`). No other file under
`docs/research/` matches on `collision_moments`, `HIGHER_ORDER_RESIDUAL`, or
`multiplicity_counts`; the family is unique. This is a *different*, earlier,
lower-level study than the untracked local
`strategy-matrix-phase5-geometry-only-portfolio-application-r1-report.md`
(a later realized-coverage-vs-random application study built on top of this
mechanism result) — that file was not read and is not authority here.

| Path | Git blob SHA-1 |
|---|---|
| `docs/research/strategy-matrix-phase5-low-overlap-geometry-mechanism-design-r1.md` | `89debbe5a53dc671cbb1b0e50c3511e4848c0b22` |
| `docs/research/low-overlap-geometry-mechanism-v1-preregistration-draft.md` | `e3ab36f0f6f740adb231bff0df915c88dc847540` |
| `docs/research/low-overlap-geometry-mechanism-v1-execution-plan-schema.md` | `ac84418d522ca9ba4e2415d73f84cbaf6e271193` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-preregistration.md` | `17b1ae14523bcd63f48d226a3134a2c5531ee654` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-preregistration-hash.json` | `c26e61a62dbebcfa44881d5a23f044a0ed52e04f` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-report.md` | `0243589b14068ea6a3f32d8af37e4db9b7569065` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json` | `dc17f0b39c9baf81f8c85162d5db554e7ca2797a` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-attempt-ledger.json` | `0a5700d065aecf2c311665a093374d3e7c888d73` |
| `src/lottolab/research/low_overlap_geometry_mechanism.py` | `20b6e0d70b17ef4e34c4d3d6f89196685c5bd22c` |
| `tests/unit/test_low_overlap_geometry_mechanism.py` | `16d671b2abb0919ce1c0abcea2d1a1135f684df1` |

Locked Phase-5 preregistration SHA-256:
`8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be`.

The reusable pure formulas in `low_overlap_geometry_mechanism.py`
(`exact_hit_multiplicity_decomposition`, `portfolio_geometry`,
`ticket_pair_hit_event_intersection_size`,
`s2_from_ticket_pair_intersection_histogram`) are read-only inputs to this
design and to `tests/unit/test_higher_order_residual_mechanism.py`. None is
modified. The new module
`src/lottolab/research/higher_order_residual_mechanism.py` does not import
them (it stays a self-contained pure-combinatorics module, mirroring the
sealed module's own "pure combinatorial helpers" framing) but is designed to
compose with them: a future executor combines this design's triple-order
functions with the sealed module's pairwise/multiplicity functions on the
same portfolios.

## 2. What the sealed Phase-5 report actually shows

Per-cell mechanism descriptor (`low-overlap-geometry-mechanism-v1-report.md`
S4), `k>1` cells only:

```text
DAILY_539:           PAIRWISE_COLLISION_EXACTLY_SUFFICIENT           (5/5 k values)
BIG_LOTTO:            PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL (5/5 k values)
POWER_LOTTO_zone1:    PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL (5/5 k values)
```

The sealed "Full signed decomposition" table (S3) gives every `+DELTA_S3`
and `H` value directly; both are **already exact, sealed numbers** — this
design does not need to recompute them:

```text
BIG_LOTTO:         T3 = -64, -512, -6208, -13248, -18816   (k=3,5,10,15,20)
POWER_LOTTO_zone1: T3 = -64, -512, -2048, -3392, -3776     (k=3,5,10,15,20)
DAILY_539:         T3 =   0,    0,     0,     0,     0     (k=3,5,10,15,20)
```

`T4` is small and positive throughout for both non-`DAILY_539` structures
(`+1,+93,+360,+593` for `BIG_LOTTO`; `+1,+17,+87,+95` for
`POWER_LOTTO_zone1`), and `T5=0` at every tabulated cell — `T3` is the
dominant, sign-opposing higher-order term everywhere it is nonzero. This is
a descriptive observation, not (yet) an identity; see S7.

The sealed geometry table (S5) additionally shows that **`max_pairwise_
overlap` is 0 or 1, for both arms, at every `k` in the ladder, in all three
structures** — `DAILY_539` is not "less overlapping" than `BIG_LOTTO` or
`POWER_LOTTO_zone1` by this measure. Whatever separates
`PAIRWISE_COLLISION_EXACTLY_SUFFICIENT` from `..._PRIMARY_WITH_HIGHER_
ORDER_RESIDUAL` is not "how much the tickets overlap" in the pairwise
sense — all three structures overlap by the same small amount. Sections 5–6
show this is not a coincidence.

## 3. Mechanism model (as specified by the Owner, restated exactly)

For a portfolio of `k` tickets covering winning state `w`:

```text
c(w) = number of portfolio tickets covering w
S_j  = sum_w C(c(w), j)
COVERED = S1 - S2 + S3 - S4 + ...
```

identical to the sealed Phase-5 formulas (design doc S4, preregistration
S5). Phase 5 established `P = -DELTA_S2` (pairwise) as the primary benefit.
This design's target quantity, exactly as specified:

```text
HIGHER_ORDER_RESIDUAL = H = DELTA_S3 - DELTA_S4 + DELTA_S5 - ...
                           = T3 + T4 + T5 + ...,  T_j = (-1)^(j+1) DELTA_S_j
```

Primary question: what exact portfolio geometry generates the nonzero
opposing residual in `BIG_LOTTO`/`POWER_LOTTO_zone1`, and why is it zero in
`DAILY_539`? The answer below is not assumed; it is derived from an exact
inequality (S5) and then verified computationally, both at toy scale and by
plugging the real `(n,d,m)` parameters into the same formula (S6).

## 4. Design analysis — what can and cannot explain the split

Per the Owner's list of candidate features, evaluated against the sealed
data (S2 above) and toy evidence (S8):

```text
multiplicity spectrum N_c            -- ALREADY SEALED; gives S_j exactly,
                                         but not a geometric explanation
signed S3+ terms (T_j)               -- ALREADY SEALED (S2); descriptive,
                                         not yet tied to geometry
pairwise-overlap profile / S2        -- RULED OUT ALONE: Toy Test A (S8.A)
                                         proves two portfolios can share an
                                         identical pairwise histogram and S2
                                         while differing in S3 (0 vs 64)
number-use/reuse concentration       -- DESCRIPTIVE ONLY: no identity in
unique-number coverage                  this design or Phase 5 connects
                                         either to S3; not pursued further
ticket-triple intersection histogram -- EXACT (new, S5-S6): the natural
higher-order hit-event intersections    j=3 generalization of Phase 5's own
                                         S2-geometry identity; not yet
                                         computed for any real portfolio
```

The pairwise-overlap profile and `S2` are demonstrably **insufficient
alone** (Toy Test A). The multiplicity-route numbers (`N_c`, `S_j`, `T_j`,
`H`) are **already fully known and sufficient to state the phenomenon**
exactly, but say nothing about *why* geometrically. Only the ticket-triple
intersection histogram — new, not present in any sealed artifact — can
supply a genuine geometric identity for `S3`, exactly as it did for `S2` in
Phase 5.

## 5. Exact identity: the Necessary Mass Bound Lemma

For a ticket triple `{t1, t2, t3}` (each of size `d`), let `r_12, r_13,
r_23` be the pairwise ticket-number intersection sizes and `s = |t1 ∩ t2 ∩
t3|`. Partition the pool into the eight regions by membership pattern in
`{t1, t2, t3}`; for a winning draw `w` (`|w|=d`), let `n_S` be the number of
`w`'s elements of membership-pattern `S ⊆ {1,2,3}`.

```text
sum_S n_S = d                                  (w has exactly d elements)
x_i = sum_{S: i in S} n_S >= m for i=1,2,3     (w hits all three tickets)
```

Summing the three per-ticket requirements and subtracting the size budget:

```text
sum_i x_i = sum_S |S| n_S >= 3m
sum_S (|S|-1) n_S = (sum_i x_i) - d >= 3m - d
n_12 + n_13 + n_23 + 2 n_123 - n_empty >= 3m - d
```

where `n_12` is shorthand for the "in exactly `t1,t2`" region count, etc.
Since `n_empty >= 0` and the region capacities are `n_12 <= r_12-s`, `n_13
<= r_13-s`, `n_23 <= r_23-s`, `n_123 <= s`:

```text
r_12 + r_13 + r_23 - s  >=  n_12+n_13+n_23+2n_123  >=  3m - d
```

**Necessary Mass Bound Lemma.** If `r_12 + r_13 + r_23 - s < 3m - d`, no
winning draw can hit all three tickets at threshold `m` — the triple's
`H_m^(3)` (defined in S6) is exactly `0`, for *every* pool size `n`. The
bound is `n`-independent by construction: `n` never enters the derivation.

**Corollary (uniform overlap cap).** If every pairwise overlap in a
portfolio satisfies `r_ij <= c`, the largest achievable value of `r_12+r_13
+r_23-s` over any triple in it is `3c` (three distinct pairwise-only
overlaps, `s=0`; a shared triple point only lowers the bound, since raising
`s` by `1` raises the left side by at most `3-1=2` per unit while the
`r_ij<=c` cap is unchanged). So if `3c < 3m-d`, i.e. `d < 3(m-1)+3c`, every
triple in the portfolio has `H_m^(3)=0`, regardless of `k` or `n`.

**Applied at `m=3`, `c=1`** (the sealed empirical cap for all three
structures, S2): the bound requires `d < 6`. `DAILY_539` (`d=5`) is
strictly below the bound — `S3=0` is **forced**, for either arm, at any
`k`, not merely observed. `BIG_LOTTO`/`POWER_LOTTO_zone1` (`d=6`) sit
exactly *at* the bound (`3c=3=3m-d`) — not ruled out, but with zero slack:
only a triple that uses the *entire* available overlap budget (three
distinct single-number pairwise overlaps, no triple point) can possibly
contribute, which is also why the effect is small relative to the pairwise
term everywhere it is observed (S2's contribution-share table: 97–99%
pairwise). This is the same reasoning `max_pairwise_overlap_forces_zero_
triple_collisions` in the new module implements, and the same one `triple_
collision_is_impossible` checks per-triple.

Pool size does not appear anywhere in this derivation. `DAILY_539`'s pool
(`n=39`) is in fact numerically closer to `POWER_LOTTO_zone1`'s (`n=38`)
than to `BIG_LOTTO`'s (`n=49`), yet it patterns with neither — it is the
odd one out under pool size and the exact match under draw size `d`. This
is not proof that `n` plays no role in the *magnitude* of the residual
(S9), only that it cannot be the driver of the *zero-versus-nonzero* split,
since the necessary-condition boundary never references it.

## 6. Exact identity: `S3` from the ticket-triple intersection histogram

Generalizing Phase-5 S5's `S2_GEOMETRY == S2_MULTIPLICITY` check by one
order:

```text
H_m^(3)(n,d,r_12,r_13,r_23,s) = sum over region hit-counts (n_S)_{S subset {1,2,3}}
    of  prod_S C(region_size(S), n_S)
    subject to  sum_S n_S = d  and  sum_{S: i in S} n_S >= m  for i=1,2,3

S3_GEOMETRY = sum over canonical shapes (histogram) of
    (triple count at that shape) * H_m^(3)(n, d, shape)

S3_MULTIPLICITY = sum_w C(c(w), 3)                      (Phase-5's own route)

REQUIRED: S3_GEOMETRY == S3_MULTIPLICITY, exactly, at every future cell.
```

`H_m^(3)` depends only on the *canonical* shape — the sorted multiset
`{r_12,r_13,r_23}` plus `s` — because relabeling which ticket is `t1`/`t2`/
`t3` permutes which region is named `n_12` vs `n_13` vs `n_23` without
changing any region's size or any ticket's own threshold requirement; the
formula, built symmetrically over the three tickets, is invariant under
that relabeling (verified computationally, S8/S10 — this design does not
merely assert the symmetry).

`src/lottolab/research/higher_order_residual_mechanism.py` implements
`ticket_triple_hit_event_intersection_size` (the `H_m^(3)` formula, via
bounded recursion over the eight regions rather than a naive `O((d+1)^8)`
product — worst-case node count is bounded by the number of ways to
distribute `d` items into 8 bins, `C(d+7,7)`, which is small for the `d<=6`
cases this design needs), `ticket_triple_intersection_histogram` (the
portfolio-level canonical-shape histogram, the triple-order analog of
`portfolio_geometry`'s pairwise histogram), and `s3_from_ticket_triple_
intersection_histogram` (the geometry route itself). All three are
exercised only against toy/synthetic portfolios in this design (S8); native
execution is deliberately absent.

**Generalization (stated, not implemented).** The same construction extends
to any `j`: partition the pool into `2^j` regions for a `j`-ticket subset,
sum region-hit-count assignments meeting every one of the `j` thresholds,
and weight by the `j`-tuple intersection histogram. `S_j_GEOMETRY == S_j_
MULTIPLICITY` would hold at every order by the identical argument. This
design does not implement `j>=4`: `T4` is already known (sealed, small,
positive, S2) and `T5=0` at every already-sealed cell, so a `j=4` geometric
identity is a strictly secondary diagnostic (mirroring how Phase 5 itself
kept `M4+`/`M5+` secondary and non-decision-changing) — see S12 for the
scope boundary this design proposes.

## 7. Retrodiction: the lemma and formula reproduce sealed numbers exactly

This is executable now, without touching any native portfolio or winning
space — it is pure arithmetic evaluation of the derived formula at the real
`(n,d,m)` triples, cross-checked against numbers the sealed report already
publishes. All of the following are asserted and pass in `tests/unit/
test_higher_order_residual_mechanism.py` (16/16), not merely claimed:

1. `BIG_LOTTO`'s and `POWER_LOTTO_zone1`'s sealed Sidon `k=3` portfolios
   both have `max_pairwise_overlap=1` for all 3 pairs (S2, "1/1" mean
   overlap); their Arm-B `k=3` portfolios are fully disjoint (`max_
   pairwise_overlap=0`), so `S3_ArmB=0` and `DELTA_S3 = -S3_Sidon`.
   Evaluating `ticket_triple_hit_event_intersection_size` at the boundary
   shape (`r_12=r_13=r_23=1, s=0`) gives exactly `64` at **both**
   `pool_size=49` and `pool_size=38` — matching the sealed `DELTA_S3=-64`
   for **both** lotteries at `k=3` exactly (report S3), computed from the
   formula alone.
2. The same shape evaluated at `pool_size` in `{15, 16, 20, 38, 49, 100}`
   gives `64` at every one — computationally confirming the boundary shape
   is pool-size independent in the range spanning the toy tests up to both
   real pool sizes (not merely asserted from the S5 derivation).
3. `max_pairwise_overlap_forces_zero_triple_collisions(draw_size=5,
   minimum_matches=3, max_pairwise_overlap=1)` is `True`
   (`DAILY_539`'s shape) and `max_pairwise_overlap_forces_zero_triple_
   collisions(draw_size=6, minimum_matches=3, max_pairwise_overlap=1)` is
   `False` (`BIG_LOTTO`/`POWER_LOTTO_zone1`'s shape) — the identical
   empirical overlap cap (S2 above), opposite outcomes, driven by `d`
   alone.

This retrodiction is a genuine, falsifiable check: had the sealed `k=3`
values not been `-64`/`-64`/`0`, or had the formula produced a different
number, this design would have failed at exactly this step, before any
Owner review.

## 8. Toy counterexamples (Owner-required A/B/C)

All in `tests/unit/test_higher_order_residual_mechanism.py`, verified
against direct brute-force winner enumeration where the pool is small
enough, and cross-checked against the sealed real numbers where it is not.

**A — identical pairwise geometry/S2, different S3.** `STAR_M3_D6` (all
three pairwise overlaps run through the same shared number, `s=1`) and
`CHAIN_M3_D6` (three distinct shared numbers, `s=0`) both have pairwise
histogram `{r=1: 3 pairs}` and identical `S2`, at the real `M3+` threshold
(`m=3`) and `BIG_LOTTO`/`POWER_LOTTO_zone1`'s draw size (`d=6`) — but
`S3 = 0` for `STAR` and `S3 = 64` for `CHAIN`. This replays, at the on-
target `(m,d)`, the same qualitative point the sealed Phase-5 test suite
already independently established with its own toy `m=2,d=3` fixture
(`test_equal_pairwise_geometry_can_hide_a_higher_order_coverage_
difference`) — a second, independent construction reaching the same
conclusion at the parameters this design actually needs.

**B — exact conditions where `S3=0`.** The Necessary Mass Bound Lemma
applied at `DAILY_539`'s shape (`d=5,m=3`, boundary triple `r=1,1,1,s=0`)
gives `mass=3 < required=4`: proven impossible, confirmed `0` by both the
formula and direct enumeration. The identical triple shape at `BIG_LOTTO`/
`POWER_LOTTO_zone1`'s shape (`d=6,m=3`) gives `mass=3 == required=3`: not
ruled out, and `CHAIN_M3_D6` above shows it is in fact realized (`S3=64`).

**C — a higher-order term opposing the pairwise benefit.** `DISJOINT_M3_D6`
(no shared numbers between any pair; the "Arm-B-like" role) vs
`CHAIN_M3_D6` (the "Sidon-like" role) at a shared pool (`n=18`): `DISJOINT`
has smaller `S2` (`P = -DELTA_S2 > 0`, favoring it), but its one ticket
triple is fully disjoint (`S3=0`) while `CHAIN`'s sits at the nonzero
boundary (`S3=64`), so `T3 = DELTA_S3 = -64 < 0` erodes part of `DISJOINT`'s
net advantage: `DELTA_COVERED = P + T3`, with `0 < DELTA_COVERED < P`
verified exactly — the identical sign pattern as the real sealed `BIG_LOTTO`
`k=3` cell.

## 9. Mechanism hypotheses (ranked, not assumed)

```text
H1 (PRIMARY, proven necessary condition, S5-S8):
   draw size d relative to threshold m, not pool size n, determines whether
   S3 can be nonzero under the empirically observed max_pairwise_overlap<=1
   regime. d=5 (DAILY_539) forces S3=0 identically; d=6 (BIG_LOTTO,
   POWER_LOTTO_zone1) sits exactly at the boundary where a narrow class of
   "saturated" triples (three distinct single-number pairwise overlaps, no
   triple point) can contribute, and only such triples can.

H2 (SECONDARY, NOT yet established, needs the bounded experiment S11):
   the magnitude and k-growth of the residual (S12's illustrative ratios:
   -0.6% of net gain at k=3 growing to -15% to -25% by k=20) should track
   how many actual ticket triples in the real Arm-B/Sidon portfolios realize
   the saturated boundary shape as k grows and disjoint slots run out. This
   is plausible given H1 but is NOT demonstrated by this design -- it is the
   explicit target of the smallest discriminating experiment (S11).

H3 (CONSIDERED AND WEAKENED, not ruled impossible but not supported):
   pool size n as the primary driver. Weakened by: (a) the Necessary Mass
   Bound Lemma never references n; (b) DAILY_539 (n=39) sits numerically
   between POWER_LOTTO_zone1 (n=38) and BIG_LOTTO (n=49) yet patterns with
   neither on the zero/nonzero split; (c) the formula gives an identical
   value (64) at n=49 and n=38 for the shared BIG_LOTTO/POWER_LOTTO_zone1
   boundary shape. n may still affect magnitude (H2) through how many
   saturated triples a constructor is forced into at a given k and pool
   size -- that is a distinct question from the zero/nonzero split H1
   answers, and is left to S11/S15, not resolved here.
```

`Do not assume the answer` is honored by keeping H2 explicitly open and by
stating H3's weakening evidence rather than declaring it false.

## 10. Existing-evidence sufficiency

The multiplicity-route numbers this design cites (`S_j`, `T_j`, `H`,
`max_pairwise_overlap`, per-cell mechanism descriptor) are **already fully
sealed** in `low-overlap-geometry-mechanism-v1-result.json` and `-report.md`
— no new computation is needed to know *what* the residual is, at any
lottery or `k`. What is **not** in any sealed artifact is the raw ticket
contents or any triple-wise (as opposed to pairwise) intersection
structure: "portfolios were not stored in the sealed result JSONs" (sealed
report S9, runtime notes) — only the pairwise histogram was persisted (S6
sealed / S5 preregistration). The `S3_GEOMETRY == S3_MULTIPLICITY` identity
(S6) — the thing that would turn H1 from "consistent with" into "the
demonstrated mechanism for these specific sealed portfolios" — therefore
cannot be evaluated from sealed data alone; it requires regenerating the
deterministic portfolios (Phase 5 already established this is
reproducible, at measured cost) and computing their triple-wise structure,
which no sealed file contains.

```text
EXISTING_EVIDENCE_SUFFICIENCY: NEW_BOUNDED_COMBINATORIAL_EXPERIMENT_REQUIRED
```

## 11. Smallest discriminating experiment (design only — not executed)

1. Regenerate each lottery's Arm-B and Sidon `k=20` portfolios through the
   unchanged canonical constructors named in the sealed Phase-5
   preregistration S3 (`cyclic_sidon_shift*`, `greedy_min_overlap_
   constructor*`); take ladder prefixes exactly as Phase 5 did. No new
   constructor, tie-break, or randomness.
2. For each `(lottery, arm, k)`, compute `ticket_triple_intersection_
   histogram` over the `k`-ticket prefix (`C(k,3)` triples; `C(20,3)=1140`
   at most).
3. Compute `S3_GEOMETRY` via `s3_from_ticket_triple_intersection_histogram`
   at the lottery's real `(n,d,m)`.
4. Assert `S3_GEOMETRY == S3_MULTIPLICITY`, reading `S3_MULTIPLICITY`
   **directly from the already-sealed** `low-overlap-geometry-mechanism-v1-
   result.json` (`collision_moments["3"]` per arm/k) — no new winning-space
   enumeration is needed, because that number is already exact and sealed.
5. Report the realized triple-shape histogram itself (how many triples at
   each `k` sit at the saturated boundary shape vs elsewhere) as the direct
   answer to H2.

This is a genuinely *smaller* experiment than Phase 5's own execution: it
skips the ~1000-second winning-space streaming pass entirely (S3_
MULTIPLICITY is reused, not recomputed) and needs only portfolio
regeneration (Phase 5's own measured total: ~774.5s `BIG_LOTTO` + ~30.0s
`DAILY_539` + ~159.0s `POWER_LOTTO_zone1` ≈ 16.1 minutes) plus a
`C(k,3)`-bounded, sub-second geometry computation per cell. `DAILY_539`
would still be included, as a confirming (not discriminating) cell: H1
predicts `S3_GEOMETRY=0` there too, and the check should not skip a lottery
merely because its answer is already known.

## 12. Future endpoints (predefined now, not computed now)

```text
full_signed_s3_plus_decomposition:
  ALREADY SEALED (values); GEOMETRICALLY EXPLAINED only after S11 runs

higher_order_residual (H):
  ALREADY SEALED; H = T3 (dominant) + T4 (small, secondary) + T5 (=0 so far)

residual_to_net_gain_ratio := H / DELTA_COVERED (signed; NOT_APPLICABLE
  when DELTA_COVERED == 0), distinct from the sealed cancellation-aware
  PAIRWISE_ABSOLUTE_CONTRIBUTION_SHARE (|P|/(|P|+sum|T_j|)): this ratio
  keeps sign and is computable NOW from already-sealed numbers alone, shown
  here for illustration only (not a new classification):

    BIG_LOTTO          k=3..20: -0.58%, -1.40%, -5.45%, -10.39%, -15.36%
    POWER_LOTTO_zone1  k=3..20: -0.83%, -2.00%, -8.47%, -22.19%, -25.35%
    DAILY_539          k=3..20:  0.00% at every k (H is exactly 0)

  the magnitude grows with k in both nonzero structures -- the direct,
  already-computable motivation for H2 and S11's triple-shape-count report.

triple_or_higher_collision_spectrum:
  (S3,...,Sk) per cell ALREADY SEALED numerically; tabulating it explicitly
  is a formatting task, not a new computation

exact_geometry_to_higher_order_identity_checks:
  S3_GEOMETRY == S3_MULTIPLICITY is the ONE new required check (S6, S11);
  S4_GEOMETRY == S4_MULTIPLICITY is defined (S6 generalization) but scoped
  OUT as non-primary (S15)
```

No arbitrary composite score is introduced; `residual_to_net_gain_ratio` is
a direct ratio of two already-defined, already-sealed exact quantities, not
a new weighting or index.

## 13. Claim boundary

```text
PREDICTIVE_ADVANTAGE:           NOT_TESTED
PROFITABILITY:                  NOT_TESTED
PRIZE_VALUE_ADVANTAGE:          NOT_TESTED
ECONOMIC_OPTIMALITY:            NOT_TESTED
GLOBAL_OPTIMUM_STATUS:          UNKNOWN
FUTURE_STRUCTURE_GENERALIZATION: NOT_TESTED
P638_ZONE2:                     OUT_OF_SCOPE
ARM_C:                          OUT_OF_SCOPE
REAL_S3_GEOMETRY_RESULTS:       NOT_RUN
```

This design and its toy tests support only exact combinatorial mechanism
claims: the Necessary Mass Bound Lemma (S5), the `S3` geometry identity
definition (S6), and the retrodiction of already-sealed `k=3` numbers from
that formula (S7). They do not support any claim about future draws, prize
value, profitability, or global constructor optimality.

## 14. Toy/synthetic formula verification in this design

`tests/unit/test_higher_order_residual_mechanism.py` — 16 tests, 0 native
portfolio, 0 historical draw, 0 sealed-artifact mutation:

```text
- STAR vs CHAIN share a pairwise histogram/S2 but differ in S3 (0 vs 64) --
  Toy Test A, at the real m=3,d=6 parameters
- S3_GEOMETRY == S3_MULTIPLICITY for STAR, CHAIN, and DISJOINT (3 cases) --
  the core new identity, toy-verified
- ticket_triple_hit_event_intersection_size matches direct brute-force
  winner enumeration on 5 parametrized toy shapes, including both sealed-
  fixture-identical tickets (star-toy, chain-toy)
- symmetric under permuting which ticket is labeled 1/2/3 (6 permutations
  of 3 distinct r-values)
- pool-size independent at the exact boundary shape, verified at 6 pool
  sizes from 15 up to both real lottery pool sizes (38, 49)
- Necessary Mass Bound Lemma forces zero at DAILY_539's shape (d=5,m=3),
  confirmed by direct enumeration -- Toy Test B (impossible side)
- the identical best-case shape is NOT ruled out at BIG_LOTTO/POWER_LOTTO_
  zone1's shape (d=6,m=3) -- Toy Test B (boundary side)
- the portfolio-level corollary matches the identical empirical overlap cap
  (<=1) to opposite outcomes across d=5 vs d=6
- the formula alone retrodicts the sealed DELTA_S3=-64 for BOTH BIG_LOTTO
  and POWER_LOTTO_zone1 at k=3
- a higher-order term (T3=-64) provably erodes part of a favorable pairwise
  term (P>0) without reversing the net gain's sign -- Toy Test C
```

All 16 pass; `ruff check` and `pyright` (strict) are clean on both new
files (S17).

## 15. Remaining pre-lock issues

```text
K_LADDER_SCOPE:
  full {1,3,5,10,15,20} ladder (matching Phase 5 exactly, DAILY_539 kept as
  a confirming cell) vs a reduced subset -- RECOMMENDED: full ladder, for
  direct comparability with the sealed Phase-5 table; Owner may reduce it
  at lock time without changing this design's identities

J4_GEOMETRY_SCOPE:
  S4_GEOMETRY==S4_MULTIPLICITY is defined (S6) but this design recommends
  keeping it OUT of the primary Phase-6 classification (T4 is small,
  already sealed, and never changes the sign of H in any sealed cell) --
  Owner may promote it to a secondary diagnostic at lock time, mirroring
  Phase 5's own M4+/M5+ treatment

INVALID_SHAPE_BEHAVIOR:
  _triple_region_sizes raises (stops) on any negative region rather than
  skipping or clamping -- matches Phase 5's "no fallback, tolerance, or
  omitted cell" convention; carry this into the execution plan (S16)

H2_IS_NOT_YET_ANSWERED:
  this design explains the zero/nonzero split (H1) but explicitly does NOT
  explain the magnitude/k-growth pattern (H2, S9/S12) -- that is S11's
  stated purpose, not a gap in this design

SCIENTIFIC_DEFINITION_GAPS: NONE IDENTIFIED
INPUT_MAPPING_GAPS:        NONE IDENTIFIED
METRIC_SEMANTICS_GAPS:     NONE IDENTIFIED
COMPUTATIONAL_BLOCKER:     NONE IDENTIFIED
OWNER_REVIEW:              REQUIRED
LOCK_AUTHORIZATION:        REQUIRED AND NOT GRANTED
EXECUTION_AUTHORIZATION:   REQUIRED AND NOT GRANTED
```

## 16. Artifacts created by this design task

```text
docs/research/strategy-matrix-phase6-higher-order-residual-mechanism-design-r1.md
docs/research/higher-order-residual-mechanism-v1-preregistration-draft.md
docs/research/higher-order-residual-mechanism-v1-execution-plan-schema.md
src/lottolab/research/higher_order_residual_mechanism.py
tests/unit/test_higher_order_residual_mechanism.py
```

No hash, locked preregistration, execution tool, result JSON, result
report, attempt ledger, Matrix scientific cell, or historical-data artifact
is created. No sealed Phase-5 artifact is modified.

## 17. No-rescue and claim boundary

The future execution may not add a constructor, change the delta
direction, drop a failing `k`, change the `M3+` threshold, suppress a
signed higher-order term, or use a secondary event to rescue or
reinterpret H1/H2 after results are visible. A changed design requires a
new draft and Owner review before any native triple-geometry computation.

```text
PREDICTIVE_ADVANTAGE:   NOT_TESTED
PRIZE_VALUE_ADVANTAGE:  NOT_TESTED
ECONOMIC_OPTIMALITY:    NOT_TESTED
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
P638_ZONE2:             OUT_OF_SCOPE
ARM_C:                  OUT_OF_SCOPE
REAL_S3_GEOMETRY_RESULTS: NOT_RUN
```

```text
FINAL_CLASSIFICATION:
PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_READY_FOR_OWNER_REVIEW
```
