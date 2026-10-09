"""Closed-form certificate for one frozen Slice-1 cell; no model build or solve."""

from __future__ import annotations

from pathlib import Path

from lottolab.research import b649_k20_fiber_near_top_s3_census as census

CERTIFICATE = "CLOSED_FORM_THEOREM_CERTIFICATE"
CERTIFIED_STATUS = "NO_REALIZATION_IN_SLICE_BY_CLOSED_FORM_THEOREM"
PROOF_IDENTITY = "B649_66665555555322000000_OPEN_WEDGE_BOUND_V1"
PROOF_VERSION = 1
TARGET_PROFILE = "66665555555322000000"
TARGET_T = 266
T_MAX = 261

# Independent pins: changing a census constant cannot silently authorize a new model.
R28_HEAD = "155f6f1cc083f4dcd17918484e26be0810c08854"
R28_TREE = "548fdbe01805b52b447318f18fca4e83100dd0e2"
R28_SHA256 = "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0"
ENGINE_SHA256 = "479f3163659a91234d23637b697527224e947ae3268e49515cd609ca82ca6276"
MANIFEST_SHA256 = "4b1df0503ab0c4a780e56b6189821f1d2f9080c2124dc6951d8663580e79e64f"
EQUIVALENCE_SHA256 = "7bf4bed1d679f302cbaff33c86e4e71d066ac3571d64f2d773a18d764ba4988c"

PROOF = """Let G be the simple overlap graph of any support structure accepted by
the pinned R28 support_union_model for the singleton profile 66665555555322000000.
Each vertex v lies on d(v) triple lines and 6-d(v) double (pair) lines. The
pair-disjointness constraint makes these incidences distinct graph neighbours,
so deg_G(v)=2d(v)+(6-d(v))=6+d(v). There are 22 triple lines and 27 double
lines. Active means d(v)>0: this profile has 14 active and 6 inactive vertices,
four with d(v)=6; every active degree is at least 2. No triple meets an inactive
vertex. A degree-6 active vertex v has no double lines and has 12 distinct
active neighbours out of 13 possible, hence one missing active neighbour u.

Let m count active-inactive double edges and e_II count inactive-inactive
double edges. Inactive double incidence is 6*6=36=m+2e_II. Simplicity gives
e_II<=C(6,2)=15, hence m>=6. Active double incidence is
14*6-sum(d)=84-66=18, so active-active double edges number (18-m)/2;
in particular m is even and m<=18. The active induced graph has
3*22+(18-m)/2=75-m/2 edges, hence C(14,2)-(75-m/2)=16+m/2 nonedges.

Fix a degree-6 vertex v and its unique missing active neighbour u. Put d=d(u)
and let x count u's active-inactive double edges. Then d>=2 and
0<=x<=6-d. Vertex u has 6+d-x active neighbours and 7-d+x missing active
neighbours, including v. An open wedge is a centre and an unordered pair of
distinct, nonadjacent endpoints joined to the centre.

Category A: wedges centred at v with both endpoints active. Its neighbour
set is exactly the active vertices other than v,u. Of the 16+m/2 active
nonedges, those incident to v or u number 1+(7-d+x)-1=7-d+x (v,u is
counted twice before subtracting one). Thus A has 9+d+m/2-x distinct wedges.
Category B: wedges with endpoints v and an inactive vertex i, centred at an
active vertex a. Each active-inactive double edge a-i with a!=u supplies
one wedge: v-a is present and v-i absent. Exactly x edges have a=u, so B
has m-x distinct wedges. A and B are disjoint by their endpoint types.
Together they number 9+d+3m/2-2x >= 9+d+3m/2-2(6-d)
=3d-3+3m/2 >= 3+3m/2.

For the four degree-6 vertices, the four A sets have distinct centres.
The four B sets have distinct degree-6 endpoints (their other endpoint is
inactive). A B-centre has a double edge to an inactive vertex and therefore
cannot have degree 6. Thus no B wedge belongs to any A set. All four counted
sets are pairwise disjoint, even when u itself has degree 6. Consequently
open wedges >= 4*(3+3m/2) >= 4*(3+9)=48.

The total wedges W=sum_v C(6+d(v),2)=831 satisfy W=3T+open_wedges,
since each graph triangle closes exactly three wedges. Therefore
T<=floor((831-48)/3)=261. R28's Boolean indicators are forced to 1 on
every actual open wedge; they may overcount but cannot undercount. A request
for T>=266 has indicator ceiling 831-3*266=33<48 and is infeasible.
No additional R28 constraints are needed for this implication. R1 emits this
certificate only for the frozen T=266 cell of this exact profile; it makes
no execution claim for any lower-T cell, any other profile, or Slice 2.
"""
PROOF_SHA256 = census.sha256_bytes(PROOF.encode())


class TheoremError(census.CensusError):
    """A theorem assumption or authority differs from this exact proof."""


def verify_arithmetic() -> dict[str, object]:
    """Check the closed-form counts and worst-case bounds, without sampling graphs."""

    profile = census.decode_profile(TARGET_PROFILE)
    active = sum(d > 0 for d in profile)
    inactive = len(profile) - active
    sixes = profile.count(6)
    minimum_active_degree = min(d for d in profile if d)
    double_incidence = active * 6 - sum(profile)
    m_min = inactive * 6 - inactive * (inactive - 1)
    # 9+d-2x >= 9+d-2(6-d) = 3d-3, minimized at d=2.
    per_vertex_constant = 3 * minimum_active_degree - 3
    per_vertex_min = per_vertex_constant + 3 * m_min // 2
    open_min = sixes * per_vertex_min
    wedges = census.wedge_count(profile)
    if (
        (active, inactive, sixes, sum(profile), minimum_active_degree) != (14, 6, 4, 66, 2)
        or (double_incidence, m_min, per_vertex_constant, per_vertex_min, open_min, wedges)
        != (18, 6, 3, 12, 48, 831)
        or (wedges - open_min) // 3 != T_MAX
        or wedges - 3 * TARGET_T >= open_min
    ):
        raise TheoremError("closed-form arithmetic or profile assumptions differ")
    return {
        "ACTIVE_VERTICES": active,
        "INACTIVE_VERTICES": inactive,
        "DEGREE_6_VERTICES": sixes,
        "MIN_ACTIVE_TRIPLE_DEGREE": minimum_active_degree,
        "ACTIVE_DOUBLE_INCIDENCE": double_incidence,
        "M_MIN": m_min,
        "M_MAX": double_incidence,
        "M_PARITY": "EVEN",
        "CATEGORY_A": "9+d+m/2-x",
        "CATEGORY_B": "m-x",
        "X_BOUND": "0<=x<=6-d; d>=2",
        "PER_VERTEX_BOUND": "3+3m/2",
        "PER_VERTEX_MIN": per_vertex_min,
        "OPEN_WEDGES_MIN": open_min,
        "W": wedges,
        "T_MAX": T_MAX,
    }


def certificate(
    manifest: census.Manifest,
    row: census.SliceRow,
    equivalence_sha256: str,
    root: Path,
) -> dict[str, object] | None:
    """Certify only the exact frozen cell under verified byte authority, otherwise fail closed."""

    if (row.profile_id, row.cap) != (TARGET_PROFILE, TARGET_T):
        return None
    if (
        (census.R28_COMMIT, census.R28_TREE, census.R28_MODULE_SHA256)
        != (R28_HEAD, R28_TREE, R28_SHA256)
        or census.engine_sha256() != ENGINE_SHA256
        or manifest.sha256 != MANIFEST_SHA256
        or equivalence_sha256 != EQUIVALENCE_SHA256
    ):
        raise TheoremError("theorem model/manifest authority differs from its independent pins")
    pinned = census.load_manifest(root / census.MANIFEST_RELATIVE, MANIFEST_SHA256)
    if manifest != pinned or row != next(r for r in pinned.rows if r.profile_id == TARGET_PROFILE):
        raise TheoremError("theorem cell or manifest differs from the frozen manifest")
    r28 = census.git_show(root, R28_HEAD, census.R28_MODULE_RELATIVE)
    if census.sha256_bytes(r28) != R28_SHA256:
        raise TheoremError("theorem R28 source bytes differ from their pin")
    arithmetic = verify_arithmetic()
    request = census.SolveRequest(row.profile, row.cap, (), census.SOLVE_SECONDS)
    return {
        "SOURCE": "CLOSED_FORM_OPEN_WEDGE_INFEASIBILITY_PROOF",
        "NATIVE_SOLVE": False,
        "SCOPE": "THIS_PROFILE_AT_THIS_T_ONLY",
        "PROFILE_ID": TARGET_PROFILE,
        "T": TARGET_T,
        "CEILING": request.ceiling,
        "CENSUS_CHASE_REQUEST_SHA256": request.digest(),
        "PROOF_IDENTITY": PROOF_IDENTITY,
        "PROOF_VERSION": PROOF_VERSION,
        "PROOF_SHA256": PROOF_SHA256,
        "PROOF": PROOF,
        "ARITHMETIC": arithmetic,
        "MODEL": "R28.support_union_model:SINGLETON_PROFILE",
        "R28_HEAD": R28_HEAD,
        "R28_TREE": R28_TREE,
        "R28_MODULE_SHA256": R28_SHA256,
        "ENGINE_SHA256": ENGINE_SHA256,
        "MANIFEST_SHA256": MANIFEST_SHA256,
        "MODEL_EQUIVALENCE_SHA256": equivalence_sha256,
    }
