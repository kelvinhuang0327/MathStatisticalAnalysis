# Two tied resolved owners: analytic full-profile bounds

Task: `B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1`.
Worker route: STANDARD_JUDGED; scientific Judge: SELF_CHECK_ONLY.
Formal Family authority: NOT_ACCEPTED. No Family adoption is performed.

## Fixed authority and source identities

Base: `ee4bb2f22ff101522e73952a3f11c66c55d95098`, tree
`876d80cb5fb524af925bd35e0d6042093248710e`.
Frozen: `6569a9667d5e2094c8542cdff9905c3fd89f9e44`, tree
`986d20859c86be9036b2321ac47e2e9622786a3b`.
The fixed 24-event result is
`matrix-native-results/b649-t261-24-event-local-family-integration-r1-result.json`,
SHA-256 `a1a40b170ff8e0eb7b9fcf10d33ecf56b1ceaa0a92652facea2f3e8bcfcbca7e`.
It records 4,647 resolved rows and these sole tied resolved owners at 313392232.
Neither target occurs in its changes from Frozen or its 24 events.

The established digest-checked source replay supplies the actual catalog degree
tuples, caps, S4 bases and source labels. The degree tuples are not inferred as
unverified data from the requested strings.

| Profile | Replayed triple-degree histogram | Original cap | S4 base | Row.source suffix |
|---|---|---:|---:|---|
| A: 65555555555442000000 | 6^1, 5^10, 4^2, 2^1, 0^6 | 266 | 112 | NB_CERTIFICATES[1620] |
| B: 66555555554433000000 | 6^2, 5^8, 4^2, 3^2, 0^6 | 266 | 112 | NB_CERTIFICATES[1467] |

Both source labels have prefix
`b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:`.
These indices refer to **virtual replay-generated catalog rows** in
`b649_k20_min_s2_nb_degree_cap_frontier_r1.py::refine_resolved`, not literal
members of the summary JSON. That JSON has no NB_CERTIFICATES array. The source
proof is the module's NB neighbourhood-capacity lemma; the existing replay
checks its adoption against the pinned result. This distinction is retained in
the result rather than inventing a JSON proof locator.

Bounded prior-art inspection: the pinned NB module proves the original cap;
`b649_k20_min_s2_topw12_split_cap_certificate_r1.py` already proves the general
core/zero identity below. The pinned source/tests contain no other direct
profile-specific certificate for these targets. This work specializes that
existing identity with a shared analytic inequality; it does not claim the
general identity as new mathematics or claim an exhaustive literature search.

## Load-bearing support premises

Every legal min-S2 realization consists of 20 tickets, capacity six labels per
ticket, 22 triple-support labels, 27 pair-support labels, and pair-linearity:
no ticket pair is used twice among all supports. These are the pinned model in
`b649_k20_min_s2_dangerous_core_realizability_r5.py::validate_k20_support_realization`
and the NB module's structural premises.

Let d_x count triple labels through ticket x. Its overlap graph G has degree
g_x = 2d_x + (6-d_x) = 6+d_x and 93 edges. The complement H has degree
13-d_x and 97 edges. Both source profiles have sum d = 66, core K of size
14, and zero part Z of size six. Their degree data give

    Phi = C(20,3) - 18*97 + sum_x C(13-d_x,2) = 290.

Independently, Phi = C(20,3) - (1/2)sum_x (6+d_x)(13-d_x) = 290.
Counting a vertex triple according to its H edges gives T=t(G)=Phi-t(H).

## Exact identity and shared analytic inequality

For x in K put sigma_x = |N_G(x) intersect Z|. A triple label cannot reach a
zero ticket, so **0 <= sigma_x <= 6-d_x**. For u in Z put
zeta_u = |N_G(u) intersect K|. Its G degree is six and Z contains only five
other vertices, hence **1 <= zeta_u <= 6**. Both sums count exactly the
same cross edges, so **sum sigma = sum zeta = r**.

Write M=H[K], N=H[Z]. Their degrees are
h_x=7-d_x+sigma_x and a_u=zeta_u-1. Define

    P = t(M) + t(N)
        + sum_{xy in E(M)} |N_G(x) intersect N_G(y) intersect Z|
        + sum_{uv in E(N)} |N_G(u) intersect N_G(v) intersect K| >= 0.

Every mixed H triangle has exactly one within-part edge. Over xy in M its
possible zero apices number 6-sigma_x-sigma_y plus the corresponding common
G-neighbour count. Over uv in N the analogous count is
14-zeta_u-zeta_v plus its common G-neighbour count. Summation gives

    t(H) = 6|E(M)| + 14|E(N)|
           - sum sigma_x h_x - sum zeta_u a_u + P.

Here 2|E(M)|=32+r and 2|E(N)|=r-6. Therefore, using cross-edge balance,

    T = 236 + sum_K sigma_x(sigma_x+2-d_x)
            + sum_Z zeta_u(zeta_u-6) - P.

For every real q in [1,6], (q-1)(q-6)<=0, so q(q-6)<=q-6.
Applying this to each zero coordinate and using sum zeta=sum sigma yields
the **exact load-bearing upper inequality**

    T <= 200 + sum_K sigma_x(sigma_x+3-d_x) - P
      <= 200 + sum_K max_{0<=s<=6-d_x} s(s+3-d_x).

Each core quadratic is convex, so its maximum on the whole closed interval
occurs at an endpoint. In particular the maxima for d=6,5,4,3,2 are
0,0,2,9,20 respectively. Thus

    A: T <= 200 + 2*2 + 20 = 224.
    B: T <= 200 + 2*2 + 2*9 = 222.

These inequalities hold for **every legal realization** of each profile.
Dropping simultaneous graphicality, parity and support decomposition constraints
only enlarges the domain. No existence, sampling, local optimization, or finite
graph enumeration is used. Completeness follows from the universal map from
legal supports to the displayed variables and inequalities. Coordinate checks
and tests audit arithmetic; they do not replace this proof. Neither cap's
attainment is asserted.

## Complete Route-B recount and rounding

For each target the source Route-B premises hold by the same support model.
Let W=sum C(g,2)=824, J=sum C(g,3), B=sum d(g-2)=586, Amax=floor(B/3)=195.
J_A=2286, J_B=2288, and max g=12. For each integer 22<=t<=cap use

    k(t) = max(0, ceil((J - 10*(W-3t))/4)),
    a(t) = min(k(t),195),
    S4(t) = max(112, 448*a(t) + 679*(k(t)-a(t))),
    S3(t) = 2800*W + 11872*(t-22) - 30800,
    U(t) = 308390040 + S3(t) - floor(4*S4(t)/7).

The pinned R32 source proves the K4 lower bound and the contained-triple K4
upper bound Amax. With 4K4 bounded below by the displayed numerator,
the ceiling is necessary. Its S4 function increases in K4, so substitution
of this lower bound is valid. The S4 credit rounds the rational union upper
bound upward: ceil(integer-4*S4/7)=integer-floor(4*S4/7).
The lower endpoint 22 counts the 22 distinct support triangles, using
pair-linearity. Every permitted integer t is retained, including endpoints.

| Profile | Domain / term count | Argmax t | K4 / contained | S4 | S3 | New admissible bound |
|---|---|---:|---|---:|---:|---:|
| A | 22..224 / 203 | 224 | 192 / 192 | 86016 | 4674544 | **313015432** |
| B | 22..222 / 201 | 222 | 177 / 177 | 79296 | 4650800 | **312995528** |

Both old complete envelopes have 245 terms, 22..266, peaking at
(t,U,K4,a,S4,S3)=(266,313392232,507,195,299208,5173168).
The result stores all old and new terms. The checker compares independent
integer and exact-Fraction implementations and the existing R32 helper at
every term, and checks each new envelope is exactly the corresponding prefix.

## Scope and frontier accounting

Both new bounds are strictly below 313392232. Lowering only A or only B
leaves the other owner at 313392232. Lowering both would strictly lower the
resolved maximum because the fixed ledger identifies them as its sole owners.
The exact next resolved numeric maximum is NOT_PROVED here: no third profile
is researched, no new Family ledger engine is built, and no update is installed.
The unchanged 197-profile cursor still gives Family bound 313394584 and
Family gain zero. New winning outcomes: zero.

No mathematical premise remains unproved within the pinned min-S2 support
model. An independent fresh-context mathematical Judge and subsequent Family
correctness integration remain outstanding. SELF_CHECK_ONLY is not independent
verification or formal acceptance. No global K20 optimality claim is made.
