"""Certify one graph triangle cap from the existing general split theorem.

Only the 620 necessary degree configurations and 217 Route-B terms are
evaluated. The accepted D6 cap260 result is read, never reproved or modified.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

from . import b649_k20_min_s2_current_cursor_class_owner_chase_r28 as model
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as current

split = current.split
ROOT = split.ROOT
TASK_ID = "B649_MIN_S2_D6_GENERIC_CAP238_FORMAL_CERT_R1"
TARGET_PROFILE = "66665555554422000000"
BASE_HEAD = "55065ad5724690319c77239209e6be0bb0fcfe38"
BASE_TREE = "dc34280a7de4c38127f99205a9cb64e873411aa9"
THEOREM_HEAD = "e44a635f1932166734aaa3f64f9469c0e63c7520"
THEOREM_TREE = "8d1b5d168157e8cea47ac44f9ca7537ace053c31"
THEOREM_PATH = "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py"
THEOREM_BLOB = "ade988f4198b11c9591ca4e49e0bd976082bf26a"
THEOREM_SHA256 = "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784"
THEOREM_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-topw12-split-cap-certificate-r1-result.json"
)
THEOREM_RESULT_SHA256 = "e6bab2ae892cfccd5dcea97781e99ad1a664029e55a80c374e3441a586ba5f9d"
OLD_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-next-owner-d6-cap260-certificate-r1-result.json"
)
OLD_RESULT_SHA256 = "eaa9030b7ebeef0676ba3b9c6761b2f9969cbf809ddc6ad48a72a5514fc9f92a"
MODEL_HEAD = "155f6f1cc083f4dcd17918484e26be0810c08854"
MODEL_PATH = "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py"
MODEL_SHA256 = "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0"
NEW_CAP = 238
OLD_BOUND = 313_356_176
INCUMBENT = 313_263_888
RESULT_PATH = (
    ROOT
    / "docs/research/matrix-native-results"
    / ("b649-k20-min-s2-d6-generic-cap238-certificate-r1-result.json")
)

PROOF = """Scope: only profile 66665555554422000000 in the pinned R28 model.
There are 20 tickets with six labels each, 22 size-three supports and 27
size-two supports; every pair belongs to at most one support. Thus G is
simple with 93 edges and degrees 6+d; its complement H has 97 edges and
degrees 13-d. No triple meets a zero-degree vertex. The target has four
d=6, six d=5, two d=4, two d=2 and six d=0 vertices, sum(d)=66.

The original theorem proves a universal identity, not only a relaxation
objective. On a vertex triple with q H-edges, the G-triangle indicator is
1-q+C(q,2)-1[q=3]. Summing gives T=Phi-t(H), Phi=296 for this profile.
Partition into core K (14 vertices) and zero part Z (6 vertices). Define
sigma_x=|N_G(x) intersect Z| and zeta_u=|N_G(u) intersect K|.
The internal H degrees are h_x=7-d_x+sigma_x and a_u=zeta_u-1.
For each H[K] edge xy its common H neighbours in Z number
6-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|; the analogous
H[Z] expression is 14-zeta_u-zeta_v plus common G core neighbours.
Hence exactly T=F-P, with
F=296-3*sum(h)-7*sum(a)+sum(sigma*h)+sum(zeta*a),
P=t(H[K])+t(H[Z])+the two common-G-neighbour sums, all nonnegative.

Every legal structure therefore maps into the necessary degree domain:
0<=sigma_x<=6-d_x, 1<=zeta_u<=6, equal cross-incidence sums; h, a,
6-d-sigma and 6-zeta are simple-graph degree lists; sigma,zeta are
bipartite-graph degree lists. Sorting sigma only within equal-d groups,
and sorting zeta within Z, preserves these premises and F. The existing
integer Erdős-Gallai/Gale-Ryser enumerator exhausts precisely these
canonical degree configurations. It need not realize them simultaneously:
enlarging the domain can only raise an upper bound. There are 620 such
configurations, each using the general P>=0 branch, and max F=238.
The special-profile P>=12+r lemma is never invoked. Thus every legal
structure has graph triangle count T<=238. F=238 is not an assertion of
attainability or of the exact maximum over legal structures.

This T counts all triangles of G, including the 22 distinct support
triangles; it is neither the noncore count T-22 nor a union-score bound.
Therefore every legal integer T lies in 22..238. All 217 terms are
evaluated using the unchanged R32 Route-B rule, S4 base 112 and A_max
199: S4(T)=max(112,679*K4(T)-231*min(K4(T),199)). K4 uses an exact
ceiling and the credit floor(4*S4/7) uses an exact floor. Their maximum
is 313159012 at T=238, below the accepted incumbent by 104876. Strict
gain from this profile is excluded. The existing cap260 result, shared
family ledger and other profiles receive no update.
"""


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def pinned(path: str, head: str, sha256: str | None = None) -> bytes:
    blob = current.git("show", f"{head}:{path}")
    if (ROOT / path).read_bytes() != blob or (sha256 is not None and digest(blob) != sha256):
        raise AssertionError(f"pinned input changed: {path}")
    return blob


def source_authority() -> tuple[dict[str, object], dict[str, object]]:
    if current.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    if current.git("rev-parse", f"{THEOREM_HEAD}^{{tree}}").decode().strip() != THEOREM_TREE:
        raise AssertionError("theorem tree mismatch")
    if current.git("rev-parse", f"{THEOREM_HEAD}:{THEOREM_PATH}").decode().strip() != THEOREM_BLOB:
        raise AssertionError("theorem blob mismatch")
    source = pinned(THEOREM_PATH, THEOREM_HEAD, THEOREM_SHA256)
    doc = ast.parse(source).body[0]
    if not (
        isinstance(doc, ast.Expr)
        and isinstance(doc.value, ast.Constant)
        and isinstance(doc.value.value, str)
    ):
        raise AssertionError("original theorem has no proof text")
    proof = doc.value.value
    original = current.object_row(
        json.loads(pinned(THEOREM_RESULT_PATH, THEOREM_HEAD, THEOREM_RESULT_SHA256))
    )
    if original["PROOF"] != proof:
        raise AssertionError("original proof and result disagree")
    old = current.object_row(json.loads(pinned(OLD_RESULT_PATH, BASE_HEAD, OLD_RESULT_SHA256)))
    if any(
        old[key] != value
        for key, value in {
            "TARGET_PROFILE": TARGET_PROFILE,
            "PROVEN_T_CAP": 260,
            "APPLIED_T_CAP": 260,
            "NEW_R32_PROFILE_BOUND": OLD_BOUND,
            "S4_BASE": 112,
            "A_MAX": 199,
            "MODEL_SEMANTICS": "PASS",
        }.items()
    ):
        raise AssertionError("accepted cap260 authority differs")
    model_source = pinned(MODEL_PATH, MODEL_HEAD, MODEL_SHA256)
    pinned(MODEL_PATH, BASE_HEAD, MODEL_SHA256)
    function = next(
        n
        for n in ast.parse(model_source).body
        if isinstance(n, ast.FunctionDef) and n.name == "support_union_model"
    )
    dependencies: dict[str, str] = {}
    for module in (split, current, r32, model, split.prior, *split.prior.PROVENANCE_MODULES):
        if module.__file__ is None:
            raise AssertionError("reused module has no file")
        path = Path(module.__file__).resolve().relative_to(ROOT).as_posix()
        dependencies[path] = digest(pinned(path, BASE_HEAD))
    return old, {
        "THEOREM_HEAD": THEOREM_HEAD,
        "THEOREM_TREE": THEOREM_TREE,
        "THEOREM_PATH": THEOREM_PATH,
        "THEOREM_BLOB": THEOREM_BLOB,
        "THEOREM_SHA256": THEOREM_SHA256,
        "ORIGINAL_PROOF_SHA256": digest(proof.encode()),
        "ORIGINAL_RESULT_SHA256": THEOREM_RESULT_SHA256,
        "PROOF_KIND": "EXACT_GRAPH_IDENTITY_AND_FINITE_NECESSARY_DEGREE_DOMAIN",
        "GENERAL_BRANCH": "A_NONNEGATIVE_P",
        "CONDITIONAL_P12_USED": False,
        "OLD_RESULT_PATH": OLD_RESULT_PATH,
        "OLD_RESULT_SHA256": OLD_RESULT_SHA256,
        "MODEL_HEAD": MODEL_HEAD,
        "MODEL_PATH": MODEL_PATH,
        "MODEL_SHA256": MODEL_SHA256,
        "MODEL_FUNCTION_AST_SHA256": digest(ast.dump(function).encode()),
        "DEPENDENCY_SHA256": dependencies,
        "STRONGER_STORED_TARGET_CERTIFICATE_IN_BASE_AUDIT": "NONE_FOUND",
        "AUDIT_SCOPE": "BASE_TREE_TARGET_REFERENCES_IN_RESEARCH_MODULES_AND_RESULTS",
    }


def degree_certificate(profile: str = TARGET_PROFILE) -> dict[str, object]:
    if profile != TARGET_PROFILE:
        raise ValueError("only the target profile is authorized")
    p = split.profile_values(profile)
    if Counter(p) != Counter({6: 4, 5: 6, 4: 2, 2: 2, 0: 6}):
        raise AssertionError("target premises differ")
    configurations = list(split.degree_configurations(p))
    cert = split.split_certificate(p)
    if (
        len(configurations) != 620
        or cert["DEGREE_CONFIGURATION_COUNT"] != len(configurations)
        or cert["BRANCH_COUNTS"] != {current.BRANCH_A: len(configurations)}
        or cert["CONDITIONAL_CONFIGURATIONS"] != []
        or cert["P0_TRIANGLE_CAP"] != cert["TRIANGLE_CAP"]
        or max(c.f for c in configurations) != cert["TRIANGLE_CAP"]
        or cert["TRIANGLE_CAP"] != NEW_CAP
    ):
        raise AssertionError("general split theorem does not establish cap238")
    canonical = sorted((c.sigma, c.zeta, c.f) for c in configurations)
    return cert | {
        "CONFIGURATIONS_SHA256": digest(json.dumps(canonical).encode()),
        "F_HISTOGRAM": dict(sorted(Counter(str(c.f) for c in configurations).items())),
        "ALL_LEGAL_STRUCTURES_COVERED": "NECESSARY_DOMAIN_SUPERSET_MODULO_VERTEX_SYMMETRY",
        "CAP_ATTAINABILITY": "NOT_CLAIMED",
    }


def envelope(old: dict[str, object], cap: int) -> dict[str, object]:
    p = split.profile_values(TARGET_PROFILE)
    previous = split.route_b_terms(p, 260, 112)
    terms = split.route_b_terms(p, cap, 112)
    if (
        [list(t) for t in previous] != old["ALL_T_TERMS"]
        or max(t[1] for t in previous) != OLD_BOUND
        or terms != previous[: len(terms)]
        or terms != r32.route_b_envelope(p, cap, 112)
        or [t[0] for t in terms] != list(range(22, cap + 1))
    ):
        raise AssertionError("complete R32 envelope or accepted S4 terms differ")
    best = max(terms, key=lambda t: (t[1], t[0]))
    return {
        "OLD_PROFILE_BOUND": OLD_BOUND,
        "NEW_PROFILE_BOUND": best[1],
        "EXACT_PROFILE_DELTA": OLD_BOUND - best[1],
        "CURRENT_ACCEPTED_INCUMBENT": INCUMBENT,
        "BELOW_INCUMBENT_BY": INCUMBENT - best[1],
        "STRICT_GAIN_POTENTIAL_FOR_PROFILE": (
            "PROVED_EXCLUDED" if best[1] <= INCUMBENT else "NOT_EXCLUDED"
        ),
        "R32_BOUND_RULE": r32.BOUND_RULE,
        "S4_BASE": 112,
        "A_MAX": r32.contained_triple_k4_cap(p),
        "ALL_T_TERMS_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED", "S4_FLOOR", "S3"],
        "ALL_T_TERMS": [list(t) for t in terms],
        "TERM_COUNT": len(terms),
        "ARGMAX_TERM": list(best),
        "TRIANGLE_DOMAIN": [22, cap],
        "ALL_T_STATUS": "PASS_INTEGER_RATIONAL_AND_R32_AGREEMENT",
        "FAMILY_COMPARISON": {
            "KNOWN_FOUR_ROW_OWNER_BOUND": old["KNOWN_FOUR_ROW_OWNER_BOUND"],
            "TARGET_BELOW_THAT_BOUND_BY": current.integer(old["KNOWN_FOUR_ROW_OWNER_BOUND"])
            - best[1],
            "PROFILE_TERM_REDUCTION_IF_ADOPTED": OLD_BOUND - best[1],
            "FAMILY_BOUND_EFFECT": "NOT_VERIFIED_OTHER_TERMS_NOT_INTEGRATED",
            "SHARED_LEDGER_UPDATED": False,
        },
    }


def compute_result() -> dict[str, object]:
    old, authority = source_authority()
    certificate = degree_certificate()
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_STRONGER_PROFILE_RESULT",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TARGET_PROFILE": TARGET_PROFILE,
        "EXISTING_CERTIFIED_CAP": 260,
        "GENERIC_THEOREM_SOURCE": THEOREM_PATH,
        "GENERIC_THEOREM_IDENTITY": authority,
        "THEOREM_APPLICABILITY": "PASS",
        "PROVEN_NEW_CAP": current.integer(certificate["TRIANGLE_CAP"]),
        "MODEL_SEMANTICS": "PASS",
        "DEGREE_CERTIFICATE": certificate,
        "PROOF": PROOF,
        "PROOF_SHA256": digest(PROOF.encode()),
        **envelope(old, current.integer(certificate["TRIANGLE_CAP"])),
        "EXISTING_D6_CERTIFICATE_MUTATED": "NO",
        "SHARED_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "SUPPORT_MODELS_BUILT": 0,
        "PORTFOLIO_ENUMERATIONS": 0,
        "REMOTE_WRITE": "NO",
        "REMAINING_TASK_MODEL": {
            "EXACT_FAMILY_INTEGRATION": "STRONGEST",
            "GIT_AUTHORITY_PUBLICATION": "STRONG",
        },
        "NEXT_ACTION": "END_WITH_STRONGER_CERTIFICATE",
    }


def render(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("only a new result may be written")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as output:
        output.write(render(result))
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "PROVEN_NEW_CAP",
                    "NEW_PROFILE_BOUND",
                    "EXACT_PROFILE_DELTA",
                    "STRICT_GAIN_POTENTIAL_FOR_PROFILE",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
