# Three tied resolved profiles: a common full-profile bound

Task: `B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1`.
Route: STANDARD_JUDGED. Judge mode: SELF_CHECK_ONLY.
Formal Family authority: NOT_ACCEPTED. No ledger row is installed.

## Fixed sources

Base HEAD `b53a776a025a5218eef73e9a6933b972b4f5395b`, tree
`d1b6d18bd41d45bd2cbc5b947f23cd6561e6d6b1`. Its 27-event result has SHA256
`766ebb9b2a046c50002082b19a3d60bfd77e8fc46ab894bfa2fd5fe542ca5d25`.
Frozen HEAD `6569a9667d5e2094c8542cdff9905c3fd89f9e44`, tree
`986d20859c86be9036b2321ac47e2e9622786a3b`.
The base records 4,647 rows and the three targets at the next distinct resolved
level 313391844. None has an event or change from Frozen. Their individual
Frozen bounds are cross-checked in the committed six-row authority result.

The unchanged existing `topw12_coverage_repair_r1.start_chase` zero-solve replay
recovers the actual catalog degrees, cap, S4 base and source row. It finishes
successfully through the installed protected launcher; the complete capture
(including argv, stdout, stderr, exit and exact worktree HEAD/tree) is embedded
in the result. The capture is SHA256
`4f4f56225d8ae9cb2e212d323659e7bc50bea0db3b6f7cfe0cfa5087f0c8fd43`.
The existing engine performs its established sealed replay, not a new ledger
implementation. Only the three target catalog records are extracted.

| Profile | Actual triple-degree distribution | Old cap | S4 base | Catalog source suffix |
|---|---|---:|---:|---|
| A: 65555555555531100000 | 6^1, 5^11, 3^1, 1^2, 0^5 | 266 | 112 | NB_CERTIFICATES[1616] |
| B: 66555555554441100000 | 6^2, 5^8, 4^3, 1^2, 0^5 | 266 | 112 | NB_CERTIFICATES[1466] |
| C: 66555555555422100000 | 6^2, 5^9, 4^1, 2^2, 1^1, 0^5 | 266 | 112 | NB_CERTIFICATES[1450] |

The source prefix is
`b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:`.
These suffixes identify **virtual replay-generated catalog rows**, not literal
members of the summary JSON. The exact proof locator is the base Git blob
`src/lottolab/research/b649_k20_min_s2_nb_degree_cap_frontier_r1.py`,
module docstring and `refine_resolved`. The catalog combines the verified NB,
R18 and prior catalog caps; no cap is reverse-engineered from a bound.

The support model is pinned in `dangerous_core_realizability_r5` and its
validator. The general core/zero identity is prior art in
`topw12_split_cap_certificate_r1`. The new result specializes that identity
and a common secant inequality to these three complete profiles. The prior
two-owner certificate at `ba4bb2b678d62364e4383962763d8ac38c5b303b` supplies
relevant methodology and the catalog-locator caveat, not any target cap.

## Universal support premises and Goodman identity

There are 20 tickets, each carrying six labels: 22 labels have supports of
size three and 27 have supports of size two. Supports are pair-linear: no
ticket pair is used twice. If d_x counts triple labels through x, distinct
labels give disjoint sets of other tickets, so the overlap graph G is simple
and has degree g_x = 2d_x+(6-d_x)=6+d_x. It has 93 edges.
The complement H has degree 13-d_x and 97 edges. Each target has sum d=66,
sum d^2=322, core K={d>0} of size 15, and zero part Z of size five.

For an independent derivation of Goodman, a mixed-colour vertex triple has
exactly two vertices incident to unlike-colour edges. Therefore
sum_x g_x(19-g_x) counts twice the nonmonochromatic triples, giving

    t(G)+t(H) = C(20,3) - (1/2)sum_x (6+d_x)(13-d_x) = 290.

Independently, inclusion-exclusion on the H edges within every vertex triple
gives

    t(G) = C(20,3) - 18*97 + sum_x C(13-d_x,2) - t(H)
         = 290 - t(H).

## Exact complement decomposition

For x in K define sigma_x=|N_G(x) intersect Z|. No triple support can contain
a zero-degree ticket, hence only pair labels reach Z and
0 <= sigma_x <= 6-d_x. For u in Z define zeta_u=|N_G(u) intersect K|.
Its graph degree is six, with at most four neighbours in Z, so
2 <= zeta_u <= 6. Cross-edge balance gives sum sigma = sum zeta = r.

Put M=H[K], N=H[Z]. Their degrees are

    h_x=8-d_x+sigma_x,      a_u=zeta_u-2,
    2|E(M)|=54+r,          2|E(N)|=r-10.

For an M edge xy, its Z apices in H number
5-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|.
For an N edge uv, its K apices number
15-zeta_u-zeta_v+|N_G(u) intersect N_G(v) intersect K|.
Every mixed H triangle has exactly one within-part edge, so

    t(H) = 5|E(M)| + 15|E(N)|
           - sum_K sigma_x h_x - sum_Z zeta_u a_u + P,

    P = t(M)+t(N)
        + sum_{xy in E(M)} |N_G(x) intersect N_G(y) intersect Z|
        + sum_{uv in E(N)} |N_G(u) intersect N_G(v) intersect K| >= 0.

Each of the four terms is a cardinality. Substitution and cross-edge balance
yield the exact identity

    T = 230 + sum_K sigma_x(sigma_x-4-d_x) + sum_Z zeta_u^2 - P.

## Common analytic bound for all realizations

For every real q in [2,6], (q-2)(q-6)<=0, hence q^2<=8q-12.
Applying this to all five zero coordinates and using cross-edge balance:

    T <= 170 + sum_K sigma_x(sigma_x+4-d_x) - P.

The core quadratic is convex. Its maximum on the entire legal interval
[0,6-d] is max(0,(6-d)(10-2d)). For d=6,5,4,3,2,1 the maxima are
0,0,4,12,24,40. Consequently

    A: T <= 170 + 12 + 2*40       = 262.
    B: T <= 170 + 3*4 + 2*40      = 262.
    C: T <= 170 + 4 + 2*24 + 40   = 262.

This proves T<=262 for every legal realization of each **complete profile**.
Every such realization maps to the displayed ranges, balance identity and
nonnegative remainder. Dropping graphicality, parity, simultaneous support
decomposition and the remainder only enlarges the necessary domain. No
sample, restricted fiber or feasibility solver supports the proof. The
coordinate and small-graph checks supplement the algebra; they are not its
completeness argument. Attainment of T=262 is not asserted. The source rows
are CLASS_ENVELOPE_ONLY and carry no realization witness.

## Complete Route-B recount

All three profiles have W=sum C(g,2)=824,
B=sum d(g-2)=586, A_MAX=floor(B/3)=195 and max g=12.
Their U=sum C(g,3) values are respectively 2289,2290,2292.
For every integer 22<=t<=cap, the existing Route-B proof gives

    k(t)=max(0,ceil((U-10*(824-3t))/4)),
    a(t)=min(k(t),195),
    S4(t)=max(112,448*a(t)+679*(k(t)-a(t))),
    S3(t)=2800*824+11872*(t-22)-30800,
    upper(t)=308390040+S3(t)-floor(4*S4(t)/7).

The K4 inequality follows by counting triangles in each vertex neighbourhood:
its missing pairs destroy at most g_max-2 neighbour triples each; summing
over centres gives 4*K4 >= U-(g_max-2)*(W-3t).
A K4 contains at most one triple support by pair-linearity. Summing the
outside-neighbour bounds for all 22 supports gives at most
floor(sum d(g-2)/3)=195 contained-triple quartets. The pinned R32 local
quartet counts are 448 with a contained triple and 679 without one.
The resulting S4 floor increases with the actual K4 count, so substituting
the lower bound k(t) is admissible. Each actual graph has T>=22 because the
22 support triples are distinct triangles. Thus the full domain is retained.

The upper-bound credit rounds upward as required:
ceil(integer-4*S4/7)=integer-floor(4*S4/7).
Separate integer and exact-Fraction implementations, plus the unchanged
pinned R32 implementation, agree at **every old and new term**.

| Profile | Old domain / count | New domain / count | Argmax t | K4 | Contained | S4 | S3 | New bound |
|---|---|---|---:|---:|---:|---:|---:|---:|
| A | 22..266 / 245 | 22..262 / 241 | 262 | 478 | 195 | 279517 | 5125680 | 313355996 |
| B | 22..266 / 245 | 22..262 / 241 | 262 | 478 | 195 | 279517 | 5125680 | 313355996 |
| C | 22..266 / 245 | 22..262 / 241 | 262 | 478 | 195 | 279517 | 5125680 | 313355996 |

Every old envelope peaks at
(266,313391844,508,195,299887,5173168). Each new envelope is its complete
prefix. There are 1,458 checked old/new terms in total (735 old plus 723 new).
All actual S4 values are multiples of seven. Therefore the wrong-rounding
negative control uses an explicitly synthetic S4+1 arithmetic witness to
distinguish floor from ceiling; it is not claimed to be a profile realization.

## Scope and prospective accounting

Each complete-profile upper bound falls by 35848 and is 35744 below the
requested threshold 313391740. All three owners of the researched level
improve. Their deltas are not added and called a Family gain.

The fixed 27-event base still has a higher resolved bound 313392128.
With the Planner-supplied 197-class bound 313258872, a projection on that
unchanged base therefore remains 313392128. No fourth profile is studied.
The exact next global frontier is UNKNOWN here. The supplied 313391740 is
the research threshold, not an independently recomputed Family authority.
Formal Family authority remains NOT_ACCEPTED; new winning outcomes are zero;
global K20 optimality is UNKNOWN.

Within the pinned support model no unproved mathematical premise is used.
The independent fresh-context mathematical Judge and later Family correctness
integration remain separate subsequent tasks. SELF_CHECK_ONLY does not claim
independent verification or formal adoption.
