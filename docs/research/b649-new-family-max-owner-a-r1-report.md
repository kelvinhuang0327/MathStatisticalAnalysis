# B649_NEW_FAMILY_MAX_OWNER_A_R1 — full Profile certificate

SELF_CHECK_ONLY. For `66655555555511100000`, the full legal support model satisfies
**T ≤ 257**. Original Route-B arithmetic then gives **313332416**, a strict reduction
of **62928** from 313395344 and below the requested ceiling 313395164. Attainment of
T=257 is not asserted. Family gain and new winning outcomes are both zero; global K20
optimality remains unknown. Only this Profile was researched.

The repository is `kelvinhuang0327/MathStatisticalAnalysis`. Frozen HEAD is
`6569a9667d5e2094c8542cdff9905c3fd89f9e44`, TREE is
`986d20859c86be9036b2321ac47e2e9622786a3b`, and the frozen next-owner result digest is
`880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743`.
All three match. The retained worktree is
`/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_NEW_FAMILY_MAX_OWNER_A_R1`.

The frozen ledger's actual Row was independently recovered by its zero-solve six-row
replay: 4,647 rows and both sealed ledger digests matched, with proof/search entrypoints
disabled. This one-time acquisition took 38.529633 CPU seconds. Its Row.source is
`b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1199]`, cap is 264,
S4 base is 112, and bound is 313395344. Its recorded realization is exactly the R12
`PROFILE_BOUNDS[30]` witness. The frozen next-owner change did not change this Profile.
The new program uses targeted frozen-blob reads rather than repeating the complete
ledger replay: the six-row ledger bound, the archived S4 donor's row/source/cap, the
original profile S4 floor and R12 witness are checked. All actually imported research
dependencies are checked byte for byte against their frozen blobs.

Prior art provides the R15 complement-graph cap 273, the retained catalog/NB cap 264,
the R32 Route-B rule, and the universal core/zero identity. The old complete split
degree relaxation has 302 states and maximum F=285 here; P≥0 alone does not improve
264. Its conditional special-Profile P floor is inapplicable. This certificate adds
one restriction on the three degree-one vertices, and does not reuse a witness as an
upper-bound proof or repeat an existing certificate.

## Independent identities

Let d be the twenty digits of the complete Profile. Directly counting gives
`6^3,5^9,1^3,0^5`, Σd=66 and Σd²=336. There are 15 positive-degree vertices K and
5 zero-degree vertices Z. A legal minimum-S2 support realization has 22 linear triple
supports and 27 pair supports, six labels on each ticket, and all support 2-subsets
distinct. Its simple shadow-plus-pair graph G has degree 6+d and 93 edges; its complement
H has degree 13−d and 97 edges.

Count vertex triples by their H edges, or count mixed wedges (each non-monochromatic
vertex triple contributes two). These give, independently,

\[
t(G)+t(H)=1140-18\cdot97+903=297
=1140-\tfrac12\sum_v(6+d_v)(13-d_v).
\]

Thus T=t(G)=297−t(H). This is the classical complement triangle identity associated
with [Goodman's 1959 paper](https://www.tandfonline.com/doi/abs/10.1080/00029890.1959.11989408);
the computation and proof here are independent of any external formula lookup.

Put M=H[K], MZ=H[Z], σx=|NG(x)∩Z| and ζu=|NG(u)∩K|. Every triple is inside K,
so 0≤σx≤6−dx. Every zero has G degree six and at most four zero neighbours, so 2≤ζu≤6.
Both sums count the same cross edges, r=Σσ=Σζ. Consequently

\[
\deg_M(x)=8-d_x+\sigma_x,\quad \deg_{MZ}(u)=\zeta_u-2,
\quad |M|=(54+r)/2,\quad |MZ|=(r-10)/2.
\]

A mixed H triangle has exactly one same-part edge. For xy∈M its zero apices number
5−σx−σy+|NG(x)∩NG(y)∩Z|. For uv∈MZ its core apices number
15−ζu−ζv+|NG(u)∩NG(v)∩K|. Summing these counts proves

\[
t(H)=60+12r-\sum_x\sigma_x(8-d_x+\sigma_x)-\sum_u\zeta_u^2+P,
\]

where

\[
P=t(M)+t(MZ)+\sum_{xy\in M}|N_G(x)\cap N_G(y)\cap Z|
              +\sum_{uv\in MZ}|N_G(u)\cap N_G(v)\cap K|\ge0.
\]

All four summands are cardinalities. Let L={d=1}, let a be the sum of σ over the nine
d=5 vertices, and let q1,q2,q3 be the σ values at L. At d=6, σ=0; at d=5, σ∈{0,1}.
Substituting r=a+Σq gives the exact identity

\[
T=F-P,\qquad F=237-2a+\sum_{i=1}^3q_i(q_i+1)+\sum_{u=1}^5\zeta_u(\zeta_u-6).
\]

## The new restriction and its complete relaxation

Each of the three d=6 vertices has twelve distinct triple-shadow neighbours in K.
Only eleven other vertices lie in K\L, so each has at least one shadow neighbour in L.
Therefore the L-to-(K\L) shadow edges number at least three. The shadow degree sum on
L is six, so twice its internal shadow edge count is at most three: there is at most
one internal shadow edge. Core pair incidence at L is B=Σ(5−qi). Shadow edges and pair
edges are disjoint. Hence, for J=G[L], the single new combinatorial restriction is

\[
2|J|\le2+B.
\]

Let E be the edges of the complement of J on L and ni=degE(i). For ij∈E, the two
M-neighbour sets in K\L have sizes 7+qi−ni and 7+qj−nj in a universe of size twelve.
Thus the number of M triangles using ij and one vertex outside L is at least
max(0,2+qi+qj−ni−nj). Its common G zero neighbours number at least max(0,qi+qj−5).
Different edges ij count different two-L triangles; these triangles, the all-L triangle,
and the common-zero summands are distinct contributions to P. Therefore

\[
P\ge\ell(q,J):=\mathbf1_{|E|=3}
 +\sum_{ij\in E}\left[\max(0,2+q_i+q_j-n_i-n_j)+\max(0,q_i+q_j-5)\right].
\]

The program enumerates exactly a∈{0,…,9}, sorted q∈{0,…,5}³, all eight labelled J,
and sorted ζ=2+degree(MZ) from all 1,024 simple graphs on five vertices (31 degree
vectors). It retains Σζ=a+Σq and 2|J|≤2+B. Every legal support realization maps to
one of these states: sorting q merely permutes J, and all J are included; sorting Z
preserves F and the necessary degree condition. No support or simultaneous core graph
conditions are imposed, so this is a proved superset, not a restricted sample.

All **3,771** retained states are checked with integers, and

\[
\max(F-\ell)=257\quad\Longrightarrow\quad\boxed{T\le257}.
\]

The canonical state-list SHA256 is
`76efd02282a3db8c6652a7d2ec0edd791e0eec2e7fa720848d30ced274bc7a5c`.
For example, the extremal relaxation state a=9, q=(5,5,5), ζ=(4,4,4,6,6), |J|=1
has F=285 and ℓ=28. It is not claimed realizable. The recorded legal witness instead
has T=190, t(H)=107 and P=19+0+13+5=37≥ℓ=11; it checks the identities only.
There are no unproved load-bearing assumptions beyond the stipulated legal support model.

## Original Route-B recount and self-check receipt

The Profile gives W=831, ΣC(6+d,3)=2350, maximum G degree twelve and Amax=200. For every
integer 22≤t≤cap, the unchanged Route-B rule is

\[
K_4(t)=\max(0,\lceil[2350-10(831-3t)]/4\rceil),\quad c=\min(K_4,200),
\]
\[
S_4=\max(112,448c+679(K_4-c)),\quad S_3=2800\cdot831+11872(t-22)-30800,
\]
\[
B(t)=372228640-63838600+S_3-\lfloor4S_4/7\rfloor.
\]

All 243 original terms and the 236-term new prefix were recounted. Independent exact
rationals check every K4 ceiling, A floor, S4 value, S3 value and final bound ceiling;
both frozen R32 and split implementations agree. The envelope is explicitly maximized,
so no monotonicity assumption is used.

| cap | all-T maximum | argmax t | K4 | contained | S4 | S3 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 264 | 313395344 | 264 | 490 | 200 | 286510 | 5169024 |
| 263 | 313386188 | 263 | 483 | 200 | 281757 | 5157152 |
| 257 | 313332416 | 257 | 438 | 200 | 251202 | 5085920 |

The widest sufficient integer cap for 313395164 is **263**: cap 263 passes and cap 264
exceeds the target by 180. The full-Profile cap 257 improves the original owner bound
by 62928 and satisfies the priority target.

Focused command, from the retained worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_b649_new_family_max_owner_a_r1.py
```

Exit code **0**, **26 passed**. The tests independently check the complete zero-degree
image using Erdős–Gallai, map all 302 prior degree configurations into the new superset,
test vertex relabelling, and reject wrong Profile/core-zero premises, a missing state,
a nongraphical zero vector, wrong caps, all Row identity fields, frozen digest/tree
tampering, wrong K4/S4/S3/rounding terms and changed source implementations.
Ruff formatting/checks pass. Focused Pyright reports 0 errors, 0 warnings, 0 informations.
No repository full suite, CP-SAT, FIBER, multiprocessing, global search or heavy solver ran.

Measured CPU for the load-bearing acquisition, result generation and final focused
verification is 38.529633+0.104988+4.197063=**42.831684 seconds**. Small exploratory probes
and initial check/repair attempts are additional, uninstrumented individually; their
bounded durations keep the total conservatively below 60 seconds, within the 120-second
limit. CPU-bound concurrency was one throughout. Initial Ruff style findings, one
unsupported Pyright option combination, and one unnecessary-comparison type finding
were repaired; all final checks pass. An initial metadata probe used a nonexistent
NB_CERTIFICATES serialized key and was replaced by the actual frozen ledger replay.

Mathematical result JSON SHA256:
`5e92e6726f11ef678755cb08b1e8f5e854fda8a013ebefe0dcdb91420b42bfe2`.
The JSON is reproducible without timing or Git self-references. The sole local commit's
HEAD/TREE and clean-worktree status are reported after committing in the final handoff.
Push and merge are NOT_RUN; production mutation is NONE. The worktree is retained.
