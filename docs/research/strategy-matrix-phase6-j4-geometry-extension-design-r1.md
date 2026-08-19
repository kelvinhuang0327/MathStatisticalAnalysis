# STRATEGY_MATRIX_PHASE6_J4_GEOMETRY_EXTENSION_DESIGN_R1

Status: DESIGN COMPLETE — OWNER REVIEW REQUIRED ｜ 2026-08-17 ｜ no real J4
execution

```text
AUTHORITY_STATUS: RESOLVED
MATERIALITY_RULE: FROZEN_BEFORE_TABLE
VALUE_OF_INFORMATION_CLASSIFICATION: J4_GEOMETRY_EXTENSION_LOW_INFORMATION_VALUE
REAL_J4_EXECUTION: NOT_RUN
PORTFOLIO_REGENERATION: NOT_RUN
WINNING_SPACE_ENUMERATION: NOT_RUN
NEW_MATRIX_SCIENTIFIC_CELL: NONE
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

This is a design-only value-of-information gate for extending the exact
Phase-6 S3 geometry explanation to S4+. It does not rerun Phase 5 or Phase 6,
lock or execute J4, regenerate a native portfolio, enumerate a winning space,
start Arm-C, or modify a sealed artifact.

## 1. Authority resolution

The current canonical `origin/main` is commit
`ad18702ddc5a8ae770b8dc4a738dc0905681d44a`, tree
`ccdf02066aa18ae34f4c08cba7291528986bdf10`. It contains one unique sealed
Phase-6 publication family satisfying the Owner packet:

| sealed Phase-6 input | Git blob SHA-1 |
|---|---|
| `docs/research/matrix-native-results/higher-order-residual-mechanism-v1-preregistration.md` | `bc9f6f376296ee3471e6afa02035b3c266d0d596` |
| `docs/research/matrix-native-results/higher-order-residual-mechanism-v1-preregistration-hash.json` | `06951f5f6ade2501c004d5b09b48cf2044aa6d1d` |
| `docs/research/matrix-native-results/higher-order-residual-mechanism-v1-report.md` | `d7bf3baef56b81303fae41ad7e51f0e5f5920ab3` |
| `docs/research/matrix-native-results/higher-order-residual-mechanism-v1-result.json` | `4d5a9b50e3355f61df23034cdb0762d4a27c1813` |
| `docs/research/matrix-native-results/higher-order-residual-mechanism-v1-attempt-ledger.json` | `e0dabc2d3cad16ddac7a4ec30d6a9fe06fe3f1c9` |

That family contains the locked Phase-6 preregistration, the real S3
geometry identity replicated over all 30 real `(structure, arm, k>=3)` cells,
the saturated-triple decomposition, the signed higher-order comparison terms,
and the exact portfolio hashes. The Phase-6 result's locked preregistration
SHA-256 is
`354d96bcee4c9e4efb59e3e88f18c686fdfb23ed00be5dae2c0ea0d133e550a6`.

Its read-only upstream is the unique sealed Phase-5
`low-overlap-geometry-mechanism-v1` family. The load-bearing result blob is
`dc17f0b39c9baf81f8c85162d5db554e7ca2797a`, its locked preregistration
SHA-256 is
`8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be`, and
the sealed result contains the full per-arm `S_j` multiplicity decomposition,
the exact `DELTA_COVERED`, and the comparison-level signed terms. Authority
is therefore resolved; no fallback or second publication family was used.

The dirty local `main` checkout was not treated as authority. Work was
performed in a clean worktree at the canonical `origin/main` commit. No
sealed Phase-5 or Phase-6 path is changed by this design.

## 2. Value-of-information gate

For the sealed Arm-B-minus-Sidon comparison, use only the already-sealed
values:

```text
T_j       = (-1)^(j+1) * DELTA_S_j
H_4PLUS   = sum(j>=4, T_j)
ratio     = H_4PLUS / DELTA_COVERED, when DELTA_COVERED != 0
```

The table also shows the signed arm-level `S4+` values, where
`S4+_arm = sum(j>=4, (-1)^(j+1) S_j^arm)`, so the comparison is auditable:
`T4+ = S4+_ARM_B - S4+_SIDON`. In the sealed cells every signed term at
order `j>=5` is exactly zero, so `H_4PLUS = T4` here. This is a read-only
tabulation, not a recomputation.

### Frozen materiality rule

Before interpreting the sealed table, freeze this one outcome-blind rule:

> J4 is materially load-bearing only if at least one nonzero opposing-residual
> cell with `T3 != 0` satisfies the exact rational inequality
> `abs(H_4PLUS) / abs(T3) >= 1/20` (5%). If `T3 == 0`, there is no remaining
> opposing S3 residual for J4 to explain, so that cell cannot warrant J4.

The 5% floor is a substantive-change threshold for the mechanism decision,
not a fitted property of this table. It is evaluated using integer counts and
the exact rational `1/20`; no decimal rounding can promote a cell. The
requested `H_4PLUS / DELTA_COVERED` ratio is reported as context and is not a
second decision rule.

### Sealed S4+ contribution table

`—` means the denominator is zero or `T3=0`, so the corresponding ratio is not
defined. The comparison direction is `ARM_B - SIDON` in every row.

| Structure | k | ARM_B S4+ | SIDON S4+ | T3 | T4 | T5+ | H4+ | DELTA_COVERED | H4+/DELTA_COVERED | abs(H4+)/abs(T3) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BIG_LOTTO | 1 | 0 | 0 | — | 0 | 0 | 0 | 0 | — | — |
| BIG_LOTTO | 3 | 0 | 0 | -64 | 0 | 0 | 0 | 11036 | 0/1 | 0/1 |
| BIG_LOTTO | 5 | 0 | -1 | -512 | 1 | 0 | 1 | 36489 | 1/36489 | 1/512 |
| BIG_LOTTO | 10 | 0 | -93 | -6208 | 93 | 0 | 93 | 112285 | 93/112285 | 93/6208 |
| BIG_LOTTO | 15 | -30 | -390 | -13248 | 360 | 0 | 360 | 124012 | 90/31003 | 5/184 |
| BIG_LOTTO | 20 | -201 | -794 | -18816 | 593 | 0 | 593 | 118677 | 593/118677 | 593/18816 |
| DAILY_539 | 1 | 0 | 0 | — | 0 | 0 | 0 | 0 | — | — |
| DAILY_539 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 108 | 0/1 | — |
| DAILY_539 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 360 | 0/1 | — |
| DAILY_539 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 900 | 0/1 | — |
| DAILY_539 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 1044 | 0/1 | — |
| DAILY_539 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 828 | 0/1 | — |
| POWER_LOTTO_zone1 | 1 | 0 | 0 | — | 0 | 0 | 0 | 0 | — | — |
| POWER_LOTTO_zone1 | 3 | 0 | 0 | -64 | 0 | 0 | 0 | 7736 | 0/1 | 0/1 |
| POWER_LOTTO_zone1 | 5 | 0 | -1 | -512 | 1 | 0 | 1 | 25489 | 1/25489 | 1/512 |
| POWER_LOTTO_zone1 | 10 | 0 | -17 | -2048 | 17 | 0 | 17 | 23969 | 17/23969 | 17/2048 |
| POWER_LOTTO_zone1 | 15 | -118 | -205 | -3392 | 87 | 0 | 87 | 14895 | 29/4965 | 87/3392 |
| POWER_LOTTO_zone1 | 20 | -632 | -727 | -3776 | 95 | 0 | 95 | 14519 | 95/14519 | 95/3776 |

The maximum exact `abs(H4+)/abs(T3)` is `593/18816` for BIG_LOTTO at
`k=20`, approximately 3.15%, below the frozen 5% floor. The maximum exact
`H4+/DELTA_COVERED` is `95/14519` for POWER_LOTTO Zone-1 at `k=20`,
approximately 0.65%. No cell passes the precommitted rule. The remaining
opposing residual is therefore not materially load-bearing at order four or
higher on the sealed evidence.

```text
VALUE_OF_INFORMATION_CLASSIFICATION: J4_GEOMETRY_EXTENSION_LOW_INFORMATION_VALUE
J4_GEOMETRY_EXTENSION_WARRANTED: NO
```

This is a stop decision, not a claim that S4 is mathematically uninteresting.
No J4 preregistration draft is created because execution is not warranted by
the frozen gate.

## 3. Conditional exact J4 mechanism design

The following is the smallest exact geometry design retained for owner review
if a later owner decision overrides the low-information stop. It is not a
claim that a real J4 run should occur.

### 3.1 Full quadruple shape

For four tickets `t1,...,t4` of size `d`, let `A` range over the 16 subsets of
`{1,2,3,4}`. Define `q_A` as the number of pool elements belonging to exactly
the tickets in `A`; `q_empty` is outside their union. The six pairwise
intersections, four triple intersections, and one four-ticket intersection
determine these regions by Möbius inversion:

```text
I_B = |intersection of tickets in B|, with I_{i}=d
q_A = sum(B superset-or-equal-to A, (-1)^(|B|-|A|) I_B)
q_empty = pool_size - |t1 union t2 union t3 union t4|
```

The exact canonical shape is the lexicographically smallest 16-vector
`(q_empty, q_{1}, q_{2}, ..., q_{1234})` over all 24 permutations of ticket
labels. This full incidence-preserving shape is required: a sorted list of
the six pairwise values and a sorted list of the four triple values alone can
merge non-isomorphic quadruples with different event counts.

The pure helper is
`src/lottolab/research/fourth_order_geometry.py`:

```text
canonical_quadruple_region_shape
ticket_quadruple_intersection_histogram
```

### 3.2 Exact S4 geometry identity

For a shape `q` and a draw with region counts `x_A`, define

```text
H_m^(4)(n,d,q) =
  sum_x product_A C(q_A, x_A)
  subject to sum_A x_A = d
             sum_(A contains i) x_A >= m  for i=1,2,3,4

S4_GEOMETRY = sum_q histogram[q] * H_m^(4)(n,d,q)
S4_MULTIPLICITY = sum_w C(c(w), 4)
```

The identity `S4_GEOMETRY == S4_MULTIPLICITY` is proven by double counting
the same finite set of pairs `(winning draw w, unordered four-ticket subset
that hits w)`. The first route groups by the ticket quadruple's exact region
shape; the second groups by the draw's ticket-hit multiplicity. The helper
`ticket_quadruple_hit_event_intersection_size` evaluates the finite region
sum by bounded exact recursion, and
`s4_from_ticket_quadruple_region_histogram` performs the histogram sum.

### 3.3 Exact mass bound and saturated classes

For any draw hitting all four tickets,

```text
sum_i hits_i >= 4m
sum_A (|A|-1) x_A >= 4m-d
```

The available shape mass is

```text
M4 = sum_(|A|>=2) (|A|-1) q_A
   = sum_(six pairwise I_ij) - sum_(four triple I_ijl) + I_1234
   = 4d - |t1 union t2 union t3 union t4|
```

Therefore `M4 < 4m-d` is a proven, pool-size-independent sufficient
condition for `H_m^(4)=0`. Under a portfolio-wide pairwise cap `r_ij <= c`,
`M4 <= 6c`; hence `6c < 4m-d` forces `S4=0` for every quadruple. At the
sealed `m=3,c=1` boundary, `d=5` is forced zero (`6<7`), while `d=6` is
allowed at equality (`6=6`). Equality defines a saturated quadruple shape
class: any contributing draw must exhaust the shape's available positive
sharing mass. Saturation is necessary, not sufficient; the exact H4 sum still
decides whether the class contributes.

The pure helpers are:

```text
quadruple_collision_mass
quadruple_collision_is_impossible
quadruple_shape_is_saturated
max_pairwise_overlap_forces_zero_quadruple_collisions
```

### 3.4 Proven identities versus hypotheses

| statement | status |
|---|---|
| Full 16-region histogram plus exact region sum gives S4 exactly | PROVEN COMBINATORIAL IDENTITY |
| Six pairwise + four triple + one quadruple intersection values determine the regions when incidence is retained | PROVEN BY MÖBIUS INVERSION |
| `M4 < 4m-d` forces S4 contribution zero | PROVEN NECESSARY MASS BOUND |
| Pairwise cap `c=1` forces S4=0 at `d=5,m=3` | PROVEN COROLLARY |
| Saturated quadruple count explains the real S4+ magnitude | HYPOTHESIS — NOT TESTED NATIVE |
| Saturated shape mix distinguishes BIG_LOTTO from POWER_LOTTO Zone-1 | HYPOTHESIS — NOT TESTED NATIVE |
| S4+ is the complete explanation of the S3+ residual | NOT CLAIMED; S5+ must remain explicit |

## 4. Toy/formula tests

`tests/unit/test_fourth_order_geometry.py` is toy-scale only and covers all
Owner-required cases:

| case | synthetic result |
|---|---|
| A: same/equivalent S2 and S3, different S4 | `(n,d,m)=(8,3,2)`, both have `(S2,S3)=(28,6)`, but S4 is `0` versus `1` |
| B: sufficient zero condition | `(d,m,c)=(5,3,1)`, required mass `7`, maximum mass `6`, so S4 is forced `0` |
| C: realizable nonzero S4 | four `d=6` tickets with six distinct pairwise-shared numbers, `(n,d,m)=(18,6,3)`, S4 is `1` |
| D: geometry route versus brute force | exact S4 equality is checked on A, B, C, and both A-portfolios |

The brute-force route is deliberately limited to these tiny synthetic spaces.
It is not a permitted future native execution route.

## 5. Conditional future execution scope

If the Owner later overrides the low-information classification, the smallest
scientifically identifiable real scope remains:

```text
structures: BIG_LOTTO, DAILY_539, POWER_LOTTO_zone1
arms: ARM_B + SIDON
event: primary M3+ only (minimum_matches=3)
historical_draws: false
monte_carlo: false
winning_space_enumeration: false
Arm-C: out of scope
P638 Zone-2: out of scope
new lottery structures: out of scope
```

### K-ladder assessment

The authorized sealed ladder `{1,3,5,10,15,20}` is the only ladder whose
comparison-level `S_j` values are already sealed. Its first available J4 cell
is `k=5`; `k=1` and `k=3` carry no quadruple. Although `k=4` would be the
atomic one-quadruple diagnostic in a fresh study, the sealed Phase-5 result
has no `k=4` multiplicity cell. Adding `k=4` would therefore require a new
sealed S4 input or an unauthorized winning-space computation, so it is not a
permitted future real scope under this packet.

Within the authorized ladder, `{5,10,20}` is the smallest reduced J4 ladder
that retains the first mixture, a mid-scale shape mix, and the maximum-prefix
endpoint. It is mechanism-identifiable, but it drops the `k=15` growth check.
Because runtime cost is explicitly non-load-bearing, the recommended future
J4 primary ladder is `{5,10,15,20}` with `{1,3}` retained only as optional
cross-phase portfolio-audit rows. The default configured ladder remains
`{1,3,5,10,15,20}`; this choice is not a runtime-saving reduction and does
not manufacture an unsealed `k=4` result.

### Portfolio authority and feasibility

The sealed Phase-6 portfolio hashes plus canonical deterministic constructors
are sufficient to define a future integrity gate, but the hashes do not
contain ticket contents. A future real J4 run would therefore require:

```text
PORTFOLIO_REGENERATION_REQUIREMENT:
  NOT_REQUIRED_FOR_THIS_VALUE_OF_INFORMATION_GATE;
  REQUIRED_FOR_FUTURE_REAL_J4 to materialize tickets and verify hashes.
```

The future executor must regenerate each canonical `k=20` portfolio once,
take exact prefixes, and verify the sealed Phase-6/Phase-5 hashes before
computing any quadruple histogram. It must not regenerate a winning space.

Sealed Phase-6 measurements provide a non-load-bearing planning envelope:

```text
BIG_LOTTO Arm-B constructor:       765.237 s
DAILY_539 Arm-B constructor:        30.202 s
POWER_LOTTO Zone-1 Arm-B:          151.248 s
Sidon constructors (all three):     0.000 s
sealed triple-geometry total:        0.021 s
sealed total:                      946.713 s (~15.8 min)
```

The inherited constructor floor is observed. The J4 pure geometry tail is
`UNKNOWN` because no native quadruple pass was run; it is expected to remain
small relative to constructor generation [Inferred], since it uses only
`C(20,4)=4845` ticket quadruples, exact 16-region shapes, and `d<=6`, but that
expectation is not execution evidence. Computational feasibility is
therefore `FEASIBLE_WITHOUT_WINNING_SPACE_ENUMERATION`, subject to the
future authorization and hash gates.

## 6. Claim boundary

This design could support, in a separately authorized future run:

- an exact S4/quadruple-geometry identity;
- a quantitative fraction of the sealed residual attributable to S4+;
- a necessary mass-bound explanation for zero/nonzero S4 cells.

It does not test or claim:

- predictive advantage, profitability, prize/economic value;
- global constructor optimality (`GLOBAL_OPTIMUM_STATUS` remains `UNKNOWN`);
- full S3+ explanation merely from explaining S4;
- S5+ being zero outside the already-sealed cells;
- Arm-C, P638 Zone-2, or new lottery structures.

## 7. Final design disposition

```text
AUTHORITY_STATUS: RESOLVED
SEALED_S4PLUS_CONTRIBUTION_TABLE: COMPLETE (read-only exact values)
MATERIALITY_RULE: abs(H4PLUS)/abs(T3) >= 1/20, exact, frozen pre-table
VALUE_OF_INFORMATION_CLASSIFICATION: J4_GEOMETRY_EXTENSION_LOW_INFORMATION_VALUE
J4_EXACT_IDENTITIES: DESIGNED, TOY-TESTED ONLY
J4_MECHANISM_HYPOTHESES: SEPARATED FROM PROVEN IDENTITIES
TOY_COUNTEREXAMPLES: COMPLETE
FUTURE_STRUCTURE_SCOPE: 3 sealed native structures, Arm-B + Sidon
FUTURE_K_LADDER: configured {1,3,5,10,15,20}; J4 primary {5,10,15,20}; optional audit {1,3}
PORTFOLIO_REGENERATION_REQUIREMENT: NOT_REQUIRED_FOR_GATE; REQUIRED_IF_EXECUTED
COMPUTATIONAL_FEASIBILITY: FEASIBLE_WITHOUT_WINNING_SPACE_ENUMERATION
PREREGISTRATION_DRAFT: NOT_CREATED (route not warranted)
REAL_J4_EXECUTION: NOT_RUN
PORTFOLIO_REGENERATION: NOT_RUN
WINNING_SPACE_ENUMERATION: NOT_RUN
```

Final classification: `PHASE6_J4_GEOMETRY_EXTENSION_DESIGN_READY_FOR_OWNER_REVIEW`.
