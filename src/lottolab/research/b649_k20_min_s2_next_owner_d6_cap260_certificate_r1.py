"""One D6 theorem transfer and its exact R32 envelope; no solver or family chase.

The source theorem is read as data from its immutable Git blob. Its original
cell/profile restrictions are preserved: only the universal counting argument
is transferred, after checking all its assumptions for this different profile.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import replace
from itertools import product
from pathlib import Path

from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as current

TASK_ID = "B649_MIN_S2_NEXT_OWNER_D6_CAP260_FORMAL_CERT_R1"
TARGET_PROFILE = "66665555554422000000"
BASE_HEAD = "2f70925698cb28758fdf29a62bc5e91028c03a81"
BASE_TREE = "216bd91dee0afa58f8186a38aec52b1d47781ef8"
RESULT_SHA256 = "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3"
LEDGER_DIGEST = "2cf91665b86167e917f47779fdee3cb23b07b1d1b3d2491eae8b3ab42d9307a8"
THEOREM_HEAD = "55c504908efd39793f639a148520ea4175a4bf38"
THEOREM_PATH = "src/lottolab/research/b649_fiber_t266_closed_form_certificate.py"
THEOREM_SHA256 = "0f5b9b3acb830ecf2c997e05c7271b1df3a1a17f7ea0f477fca41d40731596c9"
MODEL_PATH = "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py"
MODEL_HEAD = "155f6f1cc083f4dcd17918484e26be0810c08854"
MODEL_SHA256 = "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0"
PROVEN_T_CAP = 260
COMPARISON_BOUND = 313_401_180
RESULT_PATH = (
    current.ROOT
    / current.prior.RESULT_DIRECTORY
    / ("b649-k20-min-s2-next-owner-d6-cap260-certificate-r1-result.json")
)

PROOF = """For every legal support realization of 66665555554422000000:
1. There are 20 vertices, 22 triple supports and 27 double supports. Each
vertex has six labels, and every vertex pair belongs to at most one support.
Thus the simple overlap graph G has degree 6+d(v). Triple degree zero means
inactive; no triple meets an inactive vertex. There are 14 active vertices,
six inactive vertices, four d=6 vertices, and minimum positive d=2.
2. Let m be the active-inactive double edges and e_II the inactive-inactive
double edges. The six inactive vertices supply 36 double ends, so
36=m+2e_II. Simplicity gives e_II<=C(6,2)=15, hence m>=6. Active double
incidence is 14*6-66=18, so e_AA=(18-m)/2, m is even and m<=18.
The active graph has 3*22+e_AA=75-m/2 edges and 16+m/2 nonedges.
3. A d=6 vertex v has no double supports and has 12 distinct active
neighbours among 13 other active vertices, missing exactly one vertex u.
Write d=d(u)>=2 and x for u's active-inactive double edges, 0<=x<=6-d.
Then u has 6+d-x active neighbours and 7-d+x active nonneighbours.
4. Family A_v consists of open wedges centred at v with active endpoints.
Among active nonedges, the union of those incident to v or u has size
1+(7-d+x)-1=7-d+x, since v's only nonedge is vu. Hence
|A_v|=9+d+m/2-x. Family B_v has endpoints v and an inactive i and active
centre a. Each mixed double edge ai with a!=u supplies exactly one such
wedge; v has no inactive neighbour. Therefore |B_v|=m-x.
5. A_v and B_v have different endpoint types. Their sum is
9+d+3m/2-2x >= 3d-3+3m/2 >= 3+3m/2 >=12.
6. The four A_v families have distinct centres. The four B_v families have
distinct active endpoints v. Every B_v centre has a mixed double support
and so cannot have d=6; no B_v belongs to any A_w. Consequently all eight
families are pairwise disjoint, even when a missing neighbour u has d=6.
Thus at least 4*12=48 distinct open wedges exist.
7. W=sum C(6+d(v),2)=830=3T+O. Hence T<=floor((830-48)/3)=260.
T>=261 would require O<=47, contradicting O>=48. Congruence gives the
optional sharper O>=50 but the same cap. These are universal counts;
neither graph samples nor a solver establish completeness.
8. R28's support_union_model fixes 22 triples, 27 doubles, per-vertex
triple incidence d and double incidence 6-d, pair-disjointness and the
exact graph edge identity. Its Boolean wedge indicators are forced to
one for every actual open wedge. R30 invokes that R28 model. The R32
and current split-cap authorities use the same legal support semantics.
R28 is byte-identical to the source theorem's pinned R28 model; no extra
model constraints are needed for the transferred implication.
The original theorem's cell emitter remains restricted to its original
profile and T=266; this separate certificate concerns only this target.
"""


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def model_function(source: bytes) -> str:
    """Compare actual model syntax without importing or constructing CP-SAT."""

    node = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "support_union_model"
    )
    return ast.dump(node, include_attributes=False)


def theorem_provenance() -> dict[str, object]:
    blob = current.git("show", f"{THEOREM_HEAD}:{THEOREM_PATH}")
    if digest(blob) != THEOREM_SHA256:
        raise AssertionError("source theorem digest mismatch")
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(blob).body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    expected: dict[str, object] = {
        "R28_HEAD": MODEL_HEAD,
        "R28_SHA256": MODEL_SHA256,
        "TARGET_PROFILE": "66665555555322000000",
        "TARGET_T": 266,
        "T_MAX": 261,
    }
    if any(constants.get(k) != v for k, v in expected.items()):
        raise AssertionError("original theorem model or scope mismatch")
    original = current.git("show", f"{MODEL_HEAD}:{MODEL_PATH}")
    present = (current.ROOT / MODEL_PATH).read_bytes()
    if (
        digest(original) != MODEL_SHA256
        or digest(present) != MODEL_SHA256
        or present != current.git("show", f"{BASE_HEAD}:{MODEL_PATH}")
        or model_function(original) != model_function(present)
    ):
        raise AssertionError("relevant support-model semantics differ")
    proof = current.text(constants["PROOF"])
    return {
        "THEOREM_HEAD": THEOREM_HEAD,
        "THEOREM_PATH": THEOREM_PATH,
        "THEOREM_SHA256": THEOREM_SHA256,
        "ORIGINAL_PROOF_SHA256": digest(proof.encode()),
        "ORIGINAL_PROFILE": constants["TARGET_PROFILE"],
        "ORIGINAL_W": 831,
        "MODEL_HEAD": MODEL_HEAD,
        "MODEL_PATH": MODEL_PATH,
        "MODEL_SHA256": MODEL_SHA256,
        "MODEL_FUNCTION_AST_IDENTICAL": True,
        "TRANSFER_SCOPE": "COUNTING_THEOREM_ONLY_ORIGINAL_CELL_EMITTER_NOT_INVOKED",
    }


def family_counts(m: int, d: int, x: int) -> tuple[int, int]:
    """Exact A_v, B_v counts over a superset of all possible local parameters."""

    if not (6 <= m <= 18 and m % 2 == 0 and 2 <= d <= 6 and 0 <= x <= 6 - d):
        raise ValueError("outside the D6 counting premises")
    return 9 + d + m // 2 - x, m - x


def verify_arithmetic(profile: str = TARGET_PROFILE) -> dict[str, object]:
    if profile != TARGET_PROFILE:
        raise ValueError("only the target profile is authorized")
    p = current.split.profile_values(profile)
    active, inactive = sum(d > 0 for d in p), p.count(0)
    sixes, minimum = p.count(6), min(d for d in p if d)
    ends = inactive * 6
    internal_max = inactive * (inactive - 1) // 2
    m_min, m_max = ends - 2 * internal_max, active * 6 - sum(p)
    cases = [
        (m, d, x)
        for m, d in product(range(m_min, m_max + 1, 2), set(p) - {0})
        for x in range(7 - d)
    ]
    for m, d, x in cases:
        a, b = family_counts(m, d, x)
        if a + b < 3 + 3 * m // 2:
            raise AssertionError("a necessary local parameter case violates the theorem")
    per_vertex = 3 * minimum - 3 + 3 * m_min // 2
    open_min = sixes * per_vertex
    wedges = current.overlap_wedge_count(p)
    if (
        (active, inactive, sixes, minimum, sum(p)) != (14, 6, 4, 2, 66)
        or (ends, internal_max, m_min, m_max, per_vertex, open_min, wedges)
        != (36, 15, 6, 18, 12, 48, 830)
        or active - 1 - 2 * 6 != 1
        or (wedges - open_min) // 3 != PROVEN_T_CAP
        or wedges - 3 * (PROVEN_T_CAP + 1) >= open_min
    ):
        raise AssertionError("target D6 arithmetic differs")
    return {
        "ACTIVE_VERTICES": active,
        "INACTIVE_VERTICES": inactive,
        "DEGREE_6_VERTICES": sixes,
        "MIN_ACTIVE_TRIPLE_DEGREE": minimum,
        "INACTIVE_DOUBLE_ENDS": ends,
        "INACTIVE_INTERNAL_DOUBLE_MAX": internal_max,
        "M_MIN": m_min,
        "M_MAX": m_max,
        "M_PARITY": "EVEN",
        "D6_MISSING_ACTIVE_NEIGHBOURS": 1,
        "CATEGORY_A": "9+d+m/2-x",
        "CATEGORY_B": "m-x",
        "PER_VERTEX_MIN": per_vertex,
        "OPEN_WEDGES_MIN": open_min,
        "W": wedges,
        "T_MAX": PROVEN_T_CAP,
        "OPEN_CEILING_AT_T261": 47,
        "NECESSARY_PARAMETER_CASES_CHECKED": len(cases),
        "COMPLETENESS": "UNIVERSAL_COUNTING_PROOF_WITH_NECESSARY_PARAMETER_SUPERSET",
    }


def current_row() -> tuple[current.Row, dict[str, object]]:
    """Recover the exact pinned 4,647-row ledger, adopting no new family term."""

    if current.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    path = f"{current.prior.RESULT_DIRECTORY}/{current.RESULT_FILENAME}"
    blob = current.git("show", f"{BASE_HEAD}:{path}")
    if digest(blob) != RESULT_SHA256 or blob != (current.ROOT / path).read_bytes():
        raise AssertionError("current split-cap result digest mismatch")
    source = Path(current.__file__).resolve().relative_to(current.ROOT).as_posix()
    if Path(current.__file__).read_bytes() != current.git("show", f"{BASE_HEAD}:{source}"):
        raise AssertionError("current ledger implementation changed")
    sealed = current.object_row(json.loads(blob))
    authority = current.load_authority()
    ledger = dict(authority.ledger)
    for index, raw in enumerate(current.rows(sealed["CERTIFICATES"])):
        cert = current.object_row(raw)
        pid = current.text(cert["PROFILE_ID"])
        if current.refine(pid, ledger[pid]) != cert:
            raise AssertionError("stored split certificate replay differs")
        if cert["STATUS"] == current.TIGHTENED:
            ledger[pid] = replace(
                ledger[pid],
                bound=current.integer(cert["ALL_T_MAX_BOUND"]),
                cap=current.integer(cert["TRIANGLE_CAP"]),
                source=f"{current.RESULT_FILENAME}:CERTIFICATES[{index}]",
            )
    serialized = [{"PROFILE_ID": pid, "CURRENT_BOUND": ledger[pid].bound} for pid in sorted(ledger)]
    if (
        len(ledger) != 4647
        or sealed["FINAL_RESOLVED_ROW_COUNT"] != 4647
        or digest(json.dumps(serialized, sort_keys=True).encode()) != LEDGER_DIGEST
        or sealed["FINAL_RESOLVED_ROWS_SHA256"] != LEDGER_DIGEST
    ):
        raise AssertionError("pinned complete ledger differs")
    row = ledger[TARGET_PROFILE]
    if (row.bound, row.cap, row.s4_base) != (313_401_180, 265, 112):
        raise AssertionError("exact current target row differs")
    # This existing universal theorem can prove more, but was not adopted for
    # this row. Record it honestly; this task certifies the requested D6 cap.
    stronger = current.split.split_certificate(TARGET_PROFILE)
    return row, {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "RESULT_SHA256": RESULT_SHA256,
        "LEDGER_DIGEST": LEDGER_DIGEST,
        "RESOLVED_ROW_COUNT": len(ledger),
        "CURRENT_ROW_SOURCE": row.source,
        "STORED_TARGET_CAP_AT_MOST_260": row.cap <= 260,
        "EXISTING_GENERAL_SPLIT_THEOREM": {
            "TRIANGLE_CAP": stronger["TRIANGLE_CAP"],
            "DEGREE_CONFIGURATION_COUNT": stronger["DEGREE_CONFIGURATION_COUNT"],
            "BRANCH_COUNTS": stronger["BRANCH_COUNTS"],
            "ADOPTED_IN_PINNED_LEDGER": False,
            "APPLIED_IN_THIS_D6_RESULT": False,
        },
        "MODULE_PROVENANCE": authority.provenance
        | {source: digest(Path(current.__file__).read_bytes())},
        "PINNED_FAMILY_OWNER_IDS": sealed["FINAL_OWNER_IDS"],
        "FAMILY_COMBINATION": "OUTSIDE_TASK_NOT_APPLIED",
    }


def profile_certificate(row: current.Row) -> dict[str, object]:
    p = current.split.profile_values(TARGET_PROFILE)
    if current.prior.first_failure(current.prior.screen_results(p)) is not None:
        raise AssertionError("target fails a structural screen")
    if current.prior.w8.admissibility_screen(p):
        raise AssertionError("target fails admissibility")
    old = current.split.route_b_terms(p, row.cap, row.s4_base)
    if max(term[1] for term in old) != row.bound:
        raise AssertionError("existing R32 envelope does not reproduce the ledger row")
    cap = min(row.cap, PROVEN_T_CAP)
    terms = current.split.route_b_terms(p, cap, row.s4_base)
    if terms != old[: len(terms)] or terms != current.prior.r32.route_b_envelope(
        p, cap, row.s4_base
    ):
        raise AssertionError("R32 all-T or S4 terms changed")
    best = max(terms, key=lambda term: (term[1], term[0]))
    return {
        "CURRENT_CERTIFIED_T_CAP": row.cap,
        "PROVEN_T_CAP": PROVEN_T_CAP,
        "APPLIED_T_CAP": cap,
        "CURRENT_R32_PROFILE_BOUND": row.bound,
        "NEW_R32_PROFILE_BOUND": best[1],
        "EXACT_PROFILE_DELTA": row.bound - best[1],
        "S4_BASE": row.s4_base,
        "A_MAX": current.prior.r32.contained_triple_k4_cap(p),
        "R32_BOUND_RULE": current.prior.r32.BOUND_RULE,
        "ALL_T_TERMS_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED", "S4_FLOOR", "S3"],
        "ALL_T_TERMS": [list(term) for term in terms],
        "TERM_COUNT": len(terms),
        "ARGMAX_TRIANGLES": best[0],
        "CURRENT_ARGMAX_TERM": list(max(old, key=lambda t: t[1])),
        "ALL_T_STATUS": "PASS_INTEGER_RATIONAL_AND_R32_AGREEMENT",
        "KNOWN_FOUR_ROW_OWNER_BOUND": COMPARISON_BOUND,
        "BELOW_KNOWN_FOUR_ROW_OWNER_BOUND_BY": COMPARISON_BOUND - best[1],
        "POTENTIAL_FAMILY_EFFECT": "NOT_VERIFIED",
        "POTENTIAL_FAMILY_EFFECT_REASON": "FOUR_ROW_FAMILY_AUTHORITY_INTEGRATION_OUTSIDE_TASK",
    }


def compute_result() -> dict[str, object]:
    provenance = theorem_provenance()
    arithmetic = verify_arithmetic()
    row, authority = current_row()
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_D6_PROFILE_RESULT",
        "TARGET_PROFILE": TARGET_PROFILE,
        "THEOREM_TRANSFER": "PASS",
        "MODEL_SEMANTICS": "PASS",
        "THEOREM_PROVENANCE": provenance,
        "CURRENT_AUTHORITY": authority,
        "ARITHMETIC": arithmetic,
        "PROOF": PROOF,
        "PROOF_SHA256": digest(PROOF.encode()),
        **profile_certificate(row),
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "SUPPORT_MODELS_BUILT": 0,
        "PORTFOLIO_ENUMERATIONS": 0,
        "REMOTE_WRITE": "NO",
        "NEXT_TASK_MODEL": {
            "EXACT_FAMILY_AUTHORITY_INTEGRATION": "STRONGEST",
            "RESULT_PUBLICATION": "STRONG",
        },
        "NEXT_ACTION": "END_WITH_CERTIFIED_D6_RESULT",
    }


def render(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("only a new target certificate result may be written")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as output:
        output.write(render(result))
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "CURRENT_CERTIFIED_T_CAP",
                    "PROVEN_T_CAP",
                    "CURRENT_R32_PROFILE_BOUND",
                    "NEW_R32_PROFILE_BOUND",
                    "EXACT_PROFILE_DELTA",
                )
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
