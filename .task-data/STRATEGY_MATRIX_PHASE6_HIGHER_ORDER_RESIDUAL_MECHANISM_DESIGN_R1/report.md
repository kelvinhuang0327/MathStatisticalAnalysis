# STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1 — report

Status: COMPLETE — design-only scientific mechanism analysis, primary
question fully resolved from sealed evidence plus one bounded synthetic
confirmation. No production strategy, DB, or sealed Phase-5 artifact
modified.

## 0. Repository-state finding (read before trusting anything below)

Local `main` (checked out here, HEAD `e8de3bf`) diverged from `origin/main`
at commit `1aee753` (around PR #133) and never merged forward. The exact
"Phase 5 publication" this task's packet quotes almost verbatim —
`PAIRWISE_COLLISION_EXACTLY_SUFFICIENT` for DAILY_539,
`PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL` for BIG_LOTTO and
POWER_LOTTO Zone-1 — is `STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1`,
sealed at `origin/main` commit `8110479` (merge) / `4d15e2f` (content, PR
#138). This commit is **not** an ancestor of local `main` and its files do
not exist in this working tree. `origin/main`'s tip is exactly `8110479` —
nothing newer exists there either.

The commit objects were already fetched (`git merge-base --is-ancestor
8110479 origin/main` → yes), so every sealed file used in this report was
read **read-only via `git show 4d15e2f:<path>`** — no checkout, no merge,
no rebase, no write to any branch. `reproduce_analysis.py` does the same
thing programmatically and is the authoritative way to re-fetch these
numbers. This is disclosed as a bounded-preflight finding, not treated as a
blocker: the packet's own canonical claims match this commit's content
exactly, reading it changes nothing, and the packet explicitly forbids
reopening or rerunning Phase 5 — which this does not do.

Everything below is `[Confirmed]` against that pinned commit unless marked
otherwise.

## 1. Canonical inputs (all read-only, none modified)

| Role | Path | Commit |
|---|---|---|
| Sealed mechanism result | `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json` | `4d15e2f` |
| Sealed mechanism report | `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-report.md` | `4d15e2f` |
| Locked design (formal decomposition, already exact) | `docs/research/strategy-matrix-phase5-low-overlap-geometry-mechanism-design-r1.md` | `4d15e2f` |
| Exact identity source module | `src/lottolab/research/low_overlap_geometry_mechanism.py` | `4d15e2f` |
| Sealed toy counterexample test | `tests/unit/test_low_overlap_geometry_mechanism.py` | `4d15e2f` |

The mechanism result's own canonical input provenance (18 sealed cells, 3
Arm-B constructor runs, 3 Sidon runs, 3 winning-space enumerations) is
unchanged from what `low-overlap-geometry-mechanism-v1-report.md` Section 9
already records; this task adds no new lottery-scale evidence cell.

## 2. The decomposition is already sealed — cited, not re-derived

Design-r1.md Sections 4-8 already define the exact machinery this task
needed. Restated only for reference:

```text
E_i = {w in W : |w ∩ t_i| >= m}          (ticket i "hits" winner w)
c(w) = count{i : w in E_i}                (how many tickets hit w)
N_c  = count{w : c(w) = c}                 (multiplicity spectrum)
S_j  = sum_w C(c(w), j)                    (collision moments, j=1..k)

COVERED = S_1 - S_2 + S_3 - S_4 + ...      (exact inclusion-exclusion)
DELTA_X = X_ArmB - X_Sidon                  (frozen delta direction)
P  = -DELTA_S2                              (pairwise component)
T_j = (-1)^(j+1) DELTA_S_j,  j>=3           (signed higher-order term)
H  = sum_{j>=3} T_j                         (higher-order residual)
DELTA_COVERED = P + H
```

Every quantity is an exact integer or `Fraction`; nothing here is
simulated, estimated, or floating-point-load-bearing. This task's job was
to explain the *pattern* in the already-computed `P`, `T_j`, `H` values
across the three lotteries — not to recompute them.

## 3. Cross-structure comparison

Full data in `structure_comparison.csv` (30 rows: 3 lotteries × 5 k-values
× 2 arms) and `higher_order_decomposition.csv` (15 rows). Summary:

| Lottery | pool | draw (`d`) | `3m-d` (m=3) | max r observed (either arm, k<=20) | max multiplicity `c` ever observed | Residual pattern |
|---|---:|---:|---:|---:|---:|---|
| DAILY_539 (T539) | 39 | 5 | 4 | 1 | 2 | `H=0` at every tested k |
| BIG_LOTTO (B649) | 49 | 6 | 3 | 1 | 4 | `H<0` at every tested k>1 |
| POWER_LOTTO Zone-1 (P638 Zone-1) | 38 | 6 | 3 | 1 | 4 | `H<0` at every tested k>1 |

The single structural variable that lines up with the split is **draw size
`d`** (equivalently `3m-d`, since `m=3` is fixed by this study's scope):
`d=5` lotteries never reach `c=3`, `d=6` lotteries do. Pool size (49 vs. 38)
does not separate the groups — BIG_LOTTO and POWER_LOTTO Zone-1 sit on
opposite ends of the pool-size range and behave identically; DAILY_539's
smaller pool (39) does not explain its zero residual, its smaller *draw
size* does.

## 4. The exact mechanism: a triple-collision threshold

For a ticket triple `(t_i, t_j, t_l)`, let `A = t_i ∩ w`, `B = t_j ∩ w`,
`C = t_l ∩ w` for a candidate winner `w` (so `|A|,|B|,|C| <= d`). All three
tickets hit `w` at threshold `m` simultaneously (contributing to `N_c` at
`c>=3`, hence to `S3`) requires `|A|,|B|,|C| >= m`. Exact 3-set
inclusion-exclusion on `A,B,C` inside `w` (`|w|=d`) gives

```text
|A∩B| + |A∩C| + |B∩C| = |A|+|B|+|C| - |A∪B∪C| + |A∩B∩C|
                       >= 3m - d + |A∩B∩C|          (since |A∪B∪C|<=d)
```

and since `A∩B ⊆ t_i∩t_j` etc., `|A∩B|<=r_ij` (the ticket-pair intersection
size). So a **necessary condition** for any triple collision from this
specific ticket triple is:

```text
r_ij + r_il + r_jl - |t_i ∩ t_j ∩ t_l|  >=  3m - d
```

This is the smallest exact statistic that predicts the zero/nonzero split.
It strictly refines "max pairwise overlap" (a portfolio-wide scalar,
already tracked in the sealed schema) by subtracting exactly one more,
genuinely triple-wise quantity: the ticket triple's own three-way
intersection size.

### 4.1 Why DAILY_539 (T539) is structurally immune

`3m-d = 4` for `d=5`. Both arms empirically never exceed `max_pairwise_overlap=1`
at any tested `k<=20` (`structure_comparison.csv`, every DAILY_539 row).
With every pairwise term `<=1`, the left side of the bound is at most
`1+1+1-0=3 < 4` — **impossible regardless of which specific numbers are
shared**. `S3=0` is not a lucky property of the Sidon or greedy-min-overlap
construction; it is forced by `d=5,m=3` arithmetic alone, for *any*
portfolio that keeps pairwise overlap at 1. Section 6 below confirms this
by direct enumeration at `r=1`, both possible sharing patterns, at the real
`d=5,m=3` ratio.

### 4.2 Why BIG_LOTTO and POWER_LOTTO Zone-1 are not

`3m-d = 3` for `d=6`. `max_pairwise_overlap=1` gives a left-side ceiling of
`1+1+1-0=3`, exactly meeting the bound — but *only* if the triple
intersection `|t_i∩t_j∩t_l|=0`. Whether that holds depends on whether the
three pairwise-shared numbers are the same number ("hub", triple
intersection `1`, bound fails: `1+1+1-1=2<3`) or three distinct numbers
("triangle", triple intersection `0`, bound holds with equality:
`1+1+1-0=3>=3`). Section 6 confirms both outcomes occur at the real
`d=6,m=3` ratio, and that the real sealed Sidon portfolios are consistent
with triangle-type sharing (Section 6.3).

## 5. Multiplicity spectrum

Directly from the sealed, dense `collision_moments` arrays (every `S_j` for
`j=0..k` explicitly present, no zeros omitted — `reproduce_analysis.py`
checked this at `k=20` for all three lotteries):

- **DAILY_539**: `S_j=0` for `j>=3`, at every tested `k`, both arms. The
  spectrum never leaves `{0,1,2}`.
- **BIG_LOTTO / POWER_LOTTO Zone-1**: `S_j=0` for `j>=5`, at every tested
  `k` up to 20, both arms. The spectrum never leaves `{0,1,2,3,4}` even at
  20 tickets.

This is an exact, checked, nontrivial empirical fact (not a definitional
truism): no winning combination is ever hit by more than 4 of 20 portfolio
tickets simultaneously at the `M3+` threshold, in either arm, in any of the
three lotteries. It bounds exactly how far a corrected objective function
would ever need to look — order 4, never order 5+, within this tested
regime.

## 6. Triple-overlap test — classification

Per packet Section 7 (A/B/C/D):

**Verdict: B — strongly explanatory but incomplete.**

- `T3` (the `S3`-derived term) is the dominant higher-order contribution:
  `|T3|` is between **100.00% and 103.25%** of `|H|` in every nonzero-residual
  cell (`reproduce_analysis.py` output; exact fractions in
  `higher_order_decomposition.csv`).
- It is not *sufficient* (option A): `T4` is real, exactly computed, nonzero,
  and opposite-signed in every one of the 10 nonzero-residual cells — it is
  what pulls the `T3/H` ratio above 100%, not measurement noise.
- It is not merely *redundant with the multiplicity spectrum* (option C) —
  it is a genuine sub-part of that spectrum, the dominant one, but not the
  whole of it.

### 6.1 Bounded synthetic confirmation (this task, not a sealed cell)

Sealed evidence proves *existence* of the residual exactly but cannot show
*why*, because the sealed schema stores only pairwise histograms, not
triple intersections, and the real portfolios themselves were never
persisted (design-r1.md Section 11). This task ran one small, bounded,
millisecond-scale synthetic check — full design and results in
[`experiment_design.md`](experiment_design.md) — using the sealed,
unmodified exact-enumeration approach applied to six new toy portfolios at
the *real* `d=6,m=3` (B649/P638 Zone-1) and `d=5,m=3` (T539) ratios, not
just the sealed test's toy `d=3,m=2` ratio:

| case | `d` | `m` | max `r` | triple ∩ | bound (`4.`) met | `S3` |
|---|---:|---:|---:|---:|---|---:|
| hub, `r=1` | 6 | 3 | 1 | 1 | No | 0 |
| triangle, `r=1` | 6 | 3 | 1 | 0 | Yes | 64 |
| hub, `r=1` | 5 | 3 | 1 | 1 | No | 0 |
| triangle, `r=1` | 5 | 3 | 1 | 0 | No | 0 |
| hub, `r=2` | 5 | 3 | 2 | 2 | Yes | 27 |
| triangle, `r=2` | 5 | 3 | 2 | 0 | Yes | 3 |

All six match the Section 4 bound exactly (the script asserts this and
would fail loudly on any mismatch — it did not). At the real B649/P638
ratio, hub and triangle diverge (0 vs. 64) at the *same* pairwise overlap
level; at the real T539 ratio, `r=1` fails for both patterns, confirming
Section 4.1's claim is a hard ceiling, not a construction artifact.

### 6.2 Toy proof already sealed (cited, not re-derived)

`test_low_overlap_geometry_mechanism.py::test_equal_pairwise_geometry_can_hide_a_higher_order_coverage_difference`
already proves the same point at toy scale (`pool=7,draw=3,m=2`): two
portfolios with an *identical* pairwise histogram (`{r=1: 3 pairs}`, hence
identical `S2=12`) have `S3=0` vs. `S3=1` and `covered=27` vs. `28`,
depending only on hub-vs-triangle sharing. This task's Section 6.1 extends
the same proof to the real B649/P638/T539 ratios.

### 6.3 Real portfolios are consistent with triangle-type sharing

The sealed `unique_number_coverage` field (whole-pool geometry, already
persisted) indirectly discriminates hub from triangle at `k=3`: a hub
portfolio's three tickets would cover `3d-2` unique numbers, a triangle
portfolio `3d-3`. Real sealed Sidon `k=3`: BIG_LOTTO `unique=15=3*6-3`,
DAILY_539 `unique=12=3*5-3`, POWER_LOTTO Zone-1 `unique=15=3*6-3` — all
match the **triangle** prediction exactly, none match hub (`3d-2`). This is
consistent with, but does not by itself prove, that the same sharing
pattern explains Sidon's larger `S3` relative to Arm-B at higher `k`
(`experiment_design.md` Section 3 has the open follow-up for full
attribution).

## 7. Practical implication for constructor design

```text
T539:              PAIRWISE_OBJECTIVE_SUFFICIENT
B649:               PAIRWISE_OBJECTIVE_INCOMPLETE
P638_ZONE1:         PAIRWISE_OBJECTIVE_INCOMPLETE
```

For B649 and P638 Zone-1, the smallest candidate correction term to a
pure-pairwise (`min max_pairwise_overlap`) objective is a **triple-closure
penalty**: when a new ticket's placement is forced to create pairwise
overlap with two already-selected tickets, prefer reusing the *same*
already-shared number (hub) over introducing a *new* distinct shared number
(triangle) — Section 6 shows hub keeps `S3=0` at `r=1` where triangle does
not. This is a tie-break refinement to the existing greedy rule, not a new
objective; it is not implemented here (out of scope, Section 11 below).

## 8. Claim boundary

```text
predictive_advantage:   NOT_TESTED
prize_value_advantage:  NOT_TESTED
economic_optimality:    NOT_TESTED
global_optimum_status:  UNKNOWN
constructor_changed:    NO
p638_zone2:             NOT_RUN
arm_c:                  NOT_RUN
monte_carlo:            False
new_lottery_scale_evidence: NONE
```

May say: `HIGHER_ORDER_RESIDUAL_MECHANISM_B_STRONGLY_EXPLANATORY_BUT_INCOMPLETE`,
`T539_STRUCTURALLY_PAIRWISE_SUFFICIENT`. May not say: the correction term in
Section 7 has been implemented, tested, or shown to improve any real
portfolio; the Sidon/Arm-B magnitude gap has been fully quantitatively
attributed to hub-vs-triangle counts in the real portfolios (Section 6.3 is
suggestive, not a proof, per `experiment_design.md` Section 3).

## FINAL

```text
TASK_ID: STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1
STATUS: COMPLETE

PHASE5_AUTHORITY_REUSED: YES
  (read read-only via `git show 4d15e2f:<path>` — origin/main only, local
  main does not contain this commit; see Section 0)

STRUCTURES_ANALYZED: T539 / B649 / P638_ZONE1

T539_HIGHER_ORDER_RESIDUAL: ZERO at every tested k>1 (structurally forced,
  not construction-dependent — see Section 4.1)
B649_HIGHER_ORDER_RESIDUAL: NEGATIVE at every tested k>1
  (-64 .. -18223 across k=3..20; T3-dominated, T4 partial offset)
P638_ZONE1_HIGHER_ORDER_RESIDUAL: NEGATIVE at every tested k>1
  (-64 .. -3681 across k=3..20; same pattern as B649)

PAIRWISE_SUFFICIENCY_BY_STRUCTURE:
  T539: SUFFICIENT (exact, structural)
  B649: INSUFFICIENT (87.58%-99.43% of DELTA_COVERED, never 100%)
  P638_ZONE1: INSUFFICIENT (82.46%-99.19% of DELTA_COVERED, never 100%)

TRIPLE_OVERLAP_EXPLANATORY_STATUS: B — strongly explanatory but incomplete
  (T3 is 100.00%-103.25% of |H|; T4 is real, nonzero, opposite-signed)

MULTIPLICITY_SPECTRUM_EXPLANATORY_STATUS: SUFFICIENT_AND_EXACT by
  construction; empirically bounded at order 4 (B649/P638) / order 2
  (T539) through k=20, both arms, all cells checked

MINIMAL_HIGHER_ORDER_STATISTIC:
  per-triple deficit D(i,j,l) = r_ij + r_il + r_jl - |t_i ∩ t_j ∩ t_l|,
  compared against the fixed threshold 3m-d. Existence of a nonzero S3
  requires some ticket triple with D >= 3m-d. Confirmed on 15/15 real
  sealed cells and 6/6 new bounded synthetic cases at the real d,m ratios.

MECHANISM_CLASSIFICATION:
  MIXED_BY_STRUCTURE (not upgraded past evidence, mirrors Phase 5's own
  MIXED_BY_LOTTERY_OR_K precedent):
    T539:              PAIRWISE_SUFFICIENT_GLOBALLY (within tested k<=20, M3+)
    B649:               PAIRWISE_PLUS_MULTIPLICITY_SPECTRUM_SUFFICIENT
    P638_ZONE1:         PAIRWISE_PLUS_MULTIPLICITY_SPECTRUM_SUFFICIENT
  ("PAIRWISE_PLUS_TRIPLE_SUFFICIENT" is not used for B649/P638: T4 is real
  and nonzero, so triple alone is not sufficient; the full spectrum is.)

WHY_T539_RESIDUAL_IS_ZERO:
  d=5,m=3 fixes 3m-d=4. Both arms never exceed max_pairwise_overlap=1
  (empirical, all tested k). 1+1+1-0=3 < 4 always, for any sharing
  pattern (hub or triangle) — a hard combinatorial ceiling, confirmed by
  direct enumeration in Section 6.1, not a property of which constructor
  is used.

WHY_B649_RESIDUAL_IS_NONZERO:
  d=6,m=3 fixes 3m-d=3, exactly reachable at max_pairwise_overlap=1 when
  the triple intersection of the overlapping tickets is 0 ("triangle"
  sharing). Real sealed Sidon k=3 portfolios are consistent with triangle
  sharing (unique_number_coverage matches 3d-3, not the hub prediction
  3d-2 — Section 6.3). Arm-B reaches the same max_pairwise_overlap=1
  ceiling from k=10 onward but keeps S3 smaller than Sidon's at every
  matched k (e.g. 320 vs 6528 at k=10) — consistent with, not proven to be
  caused by, a lower rate of triangle-type (vs. hub-type) forced overlap.

WHY_P638_ZONE1_RESIDUAL_IS_NONZERO:
  Identical mechanism to B649 (same d=6,m=3; pool size 38 vs 49 does not
  change the 3m-d threshold or the hub/triangle distinction).

EXISTING_SEALED_EVIDENCE_SUFFICIENT: YES (for the primary classification
  question — existence, sign, and dominant driver of the residual, per
  structure)

NEW_EXPERIMENT_REQUIRED: NO for the primary question (the one bounded,
  trivially-exact synthetic experiment needed was already designed and
  executed within this task, per packet Section 8's own allowance —
  toy pools, milliseconds, no lottery data, no sealed artifact touched).
  A materially larger, separately-authorizable follow-up exists for full
  quantitative attribution of the Sidon-vs-Arm-B magnitude gap specifically
  (not required for the primary classification) — scoped in
  `experiment_design.md` Section 3 (~16 minutes, regenerates real Arm-B
  portfolios via existing unmodified constructors, no new winning-space
  enumeration).

ARM_C_REQUIRED_NOW: NO
CONSTRUCTOR_CHANGE_AUTHORIZED: NO
GLOBAL_OPTIMUM: UNKNOWN

REPO_MUTATION:
  - 1 new directory: .task-data/STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1/
    (report.md, structure_comparison.csv, higher_order_decomposition.csv,
    mechanism_candidates.csv, experiment_design.md, reproduce_analysis.py)
  - 0 existing files modified
  - 0 sealed Phase-5 artifacts touched (all read via `git show`, read-only)
DB_MUTATION: NONE

NEXT:
  Mechanism resolved for the primary question. Smallest identified
  constructor/objective correction: a triple-closure tie-break (prefer hub
  over triangle sharing when a new ticket is forced to overlap two already-
  selected tickets) for B649/P638 Zone-1 only; T539 needs no correction.
  Designing or implementing that constructor change is a new task requiring
  separate Owner authorization (this task is DESIGN_ONLY and explicitly may
  not implement it). If the Owner instead wants the Sidon-vs-Arm-B magnitude
  gap fully attributed before any constructor work, run the follow-up scoped
  in `experiment_design.md` Section 3 first.
```
