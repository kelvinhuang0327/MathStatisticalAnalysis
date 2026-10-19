"""Universal analytic certificate for exactly three specified minimum-S2 profiles.

Assumptions: 20 tickets, each containing six DISTINCT labels, use exactly 49
labels. Exactly 22 supports have size three and 27 have size two; there are
no other supports. Pair-linearity means an unordered pair of tickets belongs
to at most one support. The exact triple-degree tuple d is one of TARGETS.
Every triple contributes three distinct graph edges, every pair one; edges
from distinct supports cannot coincide. Thus |E(G)|=3*22+27=93. A ticket
with d triple labels has 2d distinct triple neighbours and 6-d distinct pair
neighbours, all disjoint, so g=6+d. For each target sum(d)=66, sum(g)=186,
W=sum C(g,2)=825, with 14 positive d vertices K and six zero vertices Z.

Goodman derivation: a three-vertex subset with one or two G edges contributes
exactly two to sum_v g_v(19-g_v), by choosing the vertex incident to one edge
and one nonedge. A homogeneous triple contributes zero. Hence
T(G)+T(H)=C(20,3)-sum_v g_v(19-g_v)/2, H=complement(G).
Since sum g^2=2W+186, the right side is 1140-((19*186)-(1650+186))/2=291.

Define sigma_x=|N_G(x) intersect Z| for x in K, and
zeta_z=|N_G(z) intersect K| for z in Z. A triple cannot contain a zero, so
all K-Z edges use pair labels: 0<=sigma_x<=6-d_x. A zero has degree six and
at most five neighbours in Z: 1<=zeta_z<=6. Both sums equal the cross-edge
count r. These are NECESSARY conditions of every legal support realization.
Let M=H[K], N=H[Z]. Their degrees are h_x=7-d_x+sigma_x and a_z=zeta_z-1,
giving |E(M)|=(32+r)/2 and |E(N)|=(r-6)/2.

For an M edge xy, its H common neighbours in Z number exactly
6-sigma_x-sigma_y+c_Z(xy), where c_Z(xy)=|N_G(x) intersect N_G(y) intersect Z|.
For an N edge uv the analogous number is 14-zeta_u-zeta_v+c_K(uv).
Every mixed H triangle has exactly one same-part edge and is counted once.
Therefore T(H)=6|E(M)|+14|E(N)|-sum_K sigma*h-sum_Z zeta*a+P,
where P=T(M)+T(N)+sum_{xy in E(M)} c_Z(xy)+sum_{uv in E(N)} c_K(uv).
T(M) and T(N) count sets of three vertices forming cliques, so are nonnegative
integers. Every c_Z and c_K is the cardinality of an explicitly defined set,
so is a nonnegative integer; summation preserves nonnegativity. This proves
P>=0 term by term, including all four distinct contributions.
The first two terms are 54+10r. Subtracting from Goodman and using both
cross-degree sums equal to r proves the exact split
T(G)=237+sum_K sigma_x(sigma_x+3-d_x)+sum_Z zeta_z(zeta_z-7)-P.

Analytic relaxation: put c=6-d and f(s)=s(s+3-d). For c>0,
f(s)=(s/c)f(c)-s(c-s)<=max(0,f(c)) on the entire real interval [0,c].
For c=0 the only s is zero. Thus the pointwise upper contribution is
max(0,(6-d)(9-2d)): for d=6,5,4,3,2 it is respectively 0,0,2,9,20.
For 1<=z<=6, (z-1)(z-6)<=0, so z(z-7)<=-6.
Dropping -P increases the upper bound, and independently maximizing each
coordinate increases it again; this can only enlarge the feasible region.
No independent maxima need occur together, and no attainability is claimed.
The three exact histograms are (6^1,5^11,3^1,2^1,0^6),
(6^2,5^8,4^3,2^1,0^6), and (6^2,5^9,3^3,0^6).
Their bounds are respectively 237+9+20-36=230,
237+3*2+20-36=227, and 237+3*9-36=228. This proof is universal;
there is no integer-state, graph, portfolio, or outcome enumeration.

Only the pinned Base Route-B evaluator is used, with its actual source closure
checked against immutable Git objects. Every integer T in 22..cap is retained
(a necessary interval, not a claim that every T is realizable). S4 is a lower
bound: max(inherited floor, Route-B floor), never their sum. Its credit is
floor(4*S4/7), equivalently the final bound is rounded UP. No adopted S5 value
exists for any target; the exact Base adoption scopes are checked. The old
cap is the minimum of each target's sealed R30 refutation, NB and class caps.
All 4647 Base resolved bounds are scanned, applying donor A/B stored numeric
replacements as FIXED CONDITIONAL PROJECTION INPUTS, then the three new rows.
Every one of the 197 cursor IDs and bounds is retained and re-evaluated by
Base's coarse evaluator. This does not rerun historical proofs for other rows
or upgrade their dispositions. Scientific acceptance of this new certificate
and canonical adoption are separate. Global optimality and prediction gains
are not established. Only one external fresh focused review is requested.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import comb
from pathlib import Path
from types import ModuleType
from typing import cast

from . import b649_k20_min_s2_nb_degree_cap_frontier_r1 as nb
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_THREE_MAX_PROFILES_SHARED_CERTIFICATE_R2"
IMPLEMENTATION_HEAD = "61bad6d9ed4bdb6977d076d6b7fa28ac7b05f82a"
IMPLEMENTATION_TREE = "78f4a11e774c3c6fe3a13d0f1ab10f7e7d8c7ed0"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
DIRECTORY = "docs/research/matrix-native-results"
BASE_SHA = "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632"
BASE_RESULT = (
    f"{DIRECTORY}/b649-min-s2-two-bonf5-owners-exact-composition-r1-result-{BASE_SHA}.json"
)
R30_PATH = f"{DIRECTORY}/{route.CAP_SOURCE_RESULT}"
R30_SHA = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
TARGETS = ("65555555555532000000", "66555555554442000000", "66555555555333000000")
HISTOGRAMS = (
    {6: 1, 5: 11, 3: 1, 2: 1, 0: 6},
    {6: 2, 5: 8, 4: 3, 2: 1, 0: 6},
    {6: 2, 5: 9, 3: 3, 0: 6},
)
DONORS = (
    (
        "a7a7efb1280156ab3fbab97abac0a2e8cc3cd6ec",
        "fb49c11fcfadfa28618e4a043b240c31c36fc0e3",
        f"{DIRECTORY}/b649-min-s2-owner-a-exact-bound-r1-result.json",
        "1e248e752622645685447e4b2c382f12aab36d5c25d1c42fb7771e16dceabab0",
    ),
    (
        "97dcfa9a2cfec1ef30097d808ecb6f87e9c6241f",
        "83fbdfece095ec5f88ac411a9d2db7a9aaf833f3",
        f"{DIRECTORY}/b649-min-s2-owner-b-exact-bound-r1-result-"
        "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b.json",
        "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b",
    ),
)
SOURCE = "src/lottolab/research/b649_three_max_profiles_shared_certificate_r2.py"
TEST = "tests/unit/test_b649_three_max_profiles_shared_certificate_r2.py"
RESULT = ROOT / DIRECTORY / "b649-three-max-profiles-shared-certificate-r2-result.json"
type Term = tuple[int, int, int, int, int, int]


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def obj(value: object) -> dict[str, object]:
    require(isinstance(value, dict), "object required")
    return cast(dict[str, object], value)


def integer(value: object) -> int:
    require(type(value) is int, "exact integer required")
    return cast(int, value)


def string(value: object) -> str:
    require(isinstance(value, str), "string required")
    return cast(str, value)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def projection(value: Mapping[str, int]) -> bytes:
    # Preserve the mathematical Base's original projection digest convention.
    return json.dumps(
        [{"PROFILE_ID": p, "CURRENT_BOUND": value[p]} for p in sorted(value)], sort_keys=True
    ).encode()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def identity(head: str, tree: str) -> None:
    require(git("cat-file", "-t", head).strip() == b"commit", "wrong commit")
    require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "tree pin mismatch")


def blob(head: str, path: str, digest: str) -> bytes:
    raw = git("show", f"{head}:{path}")
    require(sha(raw) == digest, "blob pin mismatch")
    return raw


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    require(len(pairs) == len({k for k, _ in pairs}), "duplicate JSON key/row")
    return dict(pairs)


def decode(raw: bytes) -> dict[str, object]:
    return obj(json.loads(raw, object_pairs_hook=unique_object))


@dataclass(frozen=True)
class Assumptions:
    tickets: int = 20
    labels_per_ticket: int = 6
    labels: int = 49
    triples: int = 22
    pairs: int = 27
    pair_linearity: bool = True
    support_sizes: tuple[int, ...] = (2, 3)


MODEL = Assumptions()


def theorem(pid: str, assumptions: Assumptions = MODEL) -> dict[str, object]:
    require(
        assumptions == MODEL
        and all(
            type(v) is int
            for v in (
                assumptions.tickets,
                assumptions.labels_per_ticket,
                assumptions.labels,
                assumptions.triples,
                assumptions.pairs,
                *assumptions.support_sizes,
            )
        )
        and assumptions.pair_linearity is True,
        "wrong support assumptions",
    )
    require(pid in TARGETS, "wrong exact profile")
    d = tuple(map(int, pid))
    require(dict(Counter(d)) == HISTOGRAMS[TARGETS.index(pid)], "profile histogram mismatch")
    g = tuple(6 + v for v in d)
    edges = assumptions.triples * comb(3, 2) + assumptions.pairs
    w = sum(comb(v, 2) for v in g)
    goodman = Fraction(comb(len(d), 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    require(
        len(d) == 20
        and sum(d) == 66
        and d.count(0) == 6
        and edges == 93
        and sum(g) == 2 * edges
        and w == 825
        and goodman == 291,
        "theorem degree/edge/wedge hypotheses fail",
    )
    contributions = [max(0, (6 - v) * (9 - 2 * v)) for v in d if v]
    # 54 is the constant of 6*(32+r)/2 + 14*(r-6)/2, not a fitted cap.
    split_constant = integer(goodman.numerator) - (6 * 32 // 2 - 14 * 6 // 2)
    cap = split_constant + sum(contributions) - 6 * d.count(0)
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "HISTOGRAM": dict(Counter(d)),
        "DEGREE_SUM": sum(d),
        "EDGES": edges,
        "WEDGES": w,
        "CORE_COUNT": len(d) - d.count(0),
        "ZERO_COUNT": d.count(0),
        "GOODMAN_SUM": int(goodman),
        "SPLIT_CONSTANT": split_constant,
        "CORE_POINTWISE_UPPER_CONTRIBUTIONS": contributions,
        "ZERO_POINTWISE_UPPER_SUM": -6 * d.count(0),
        "ANALYTIC_CAP": cap,
        "ASSUMPTIONS": asdict(assumptions),
        "COMPLETENESS": "NOT_APPLICABLE — ANALYTIC_UNIVERSAL_BOUND",
        "ATTAINABILITY": "NOT_ASSERTED",
    }


def source_pins() -> dict[str, str]:
    """Bind the actual transitive evaluator/helper closure, excluding unrelated imports."""
    queue = [route, nb]
    seen: set[str] = set()
    pins: dict[str, str] = {}
    while queue:
        module = queue.pop()
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        require(module.__file__ is not None, "source-less evaluator helper")
        path = Path(string(module.__file__)).resolve()
        relative = path.relative_to(ROOT).as_posix()
        raw = git("show", f"{BASE_HEAD}:{relative}")
        require(path.read_bytes() == raw, f"evaluator differs from mathematical Base: {relative}")
        pins[relative] = sha(raw)
        for value in vars(module).values():
            child = value if isinstance(value, ModuleType) else None
            if inspect.isfunction(value) or inspect.isclass(value):
                child = sys.modules.get(value.__module__)
            if child is not None and child.__name__.startswith("lottolab.research."):
                queue.append(child)
    require(len(pins) == 22, "evaluator source closure drift")
    require(not any(name.startswith("ortools") for name in sys.modules), "solver loaded")
    return dict(sorted(pins.items()))


def validate_envelope(pid: str, cap: int, floor: int, terms: Sequence[Term]) -> None:
    """Check every position and exact rational term, including both endpoints."""
    require(pid in TARGETS and type(cap) is int and 22 <= cap <= 275, "wrong profile/cap")
    require(type(floor) is int and floor >= 0, "wrong S4 floor")
    require([t[0] for t in terms] == list(range(22, cap + 1)), "incomplete T envelope")
    d = tuple(map(int, pid))
    w, choose3, top = route.k4_premises(d)
    a_max = sum(v * (6 + v - 2) for v in d) // 3
    for t, bound, k4, contained, s4, s3 in terms:
        require(all(type(v) is int for v in (t, bound, k4, contained, s4, s3)), "noninteger term")
        open_wedges = w - 3 * t
        excess = choose3 - (top - 2) * open_wedges
        expected_k4 = max(0, -(-excess // 4))
        require(k4 == expected_k4 and contained == min(k4, a_max), "K4 rounding/containment")
        require(s4 == max(floor, 679 * k4 - 231 * contained), "S4 direction/floor")
        # Independent expansion of Base R4's exact local S3 identity.
        expected_s3 = 2800 * open_wedges + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(route.K20_S1 - route.K20_S2 + expected_s3) - Fraction(4 * s4, 7)
        require(
            s3 == expected_s3 and bound == -(-exact.numerator // exact.denominator),
            "S3 or final ceiling rounding",
        )


def envelope(pid: str, cap: int, floor: int) -> list[Term]:
    terms = route.route_b_envelope(tuple(map(int, pid)), cap, floor)
    validate_envelope(pid, cap, floor, terms)
    return terms


def checked_rows(rows: Sequence[tuple[str, int]], expected: Mapping[str, int]) -> dict[str, int]:
    require(len(rows) == len({p for p, _ in rows}) == 4647, "wrong/duplicate resolved rows")
    require(all(type(v) is int for _, v in rows), "noninteger resolved bound")
    require(dict(rows) == dict(expected), "resolved row omitted/changed")
    return dict(rows)


def family(resolved: Mapping[str, int], cursor: Mapping[str, int]) -> dict[str, object]:
    require(not (set(resolved) & set(cursor)), "overlapping resolved/cursor IDs")
    merged = dict(resolved) | dict(cursor)
    maximum = max(merged.values())
    levels = sorted(set(resolved.values()), reverse=True)
    return {
        "MAXIMUM": maximum,
        "ALL_MAX_OWNERS": sorted(p for p, b in merged.items() if b == maximum),
        "RESOLVED_MAXIMUM": levels[0],
        "NEXT_DISTINCT_RESOLVED_BOUND": levels[1],
        "RESOLVED_ROWS_SCANNED": len(resolved),
        "CURSOR_ROWS_SCANNED": len(cursor),
    }


def compute_result() -> dict[str, object]:
    identity(IMPLEMENTATION_HEAD, IMPLEMENTATION_TREE)
    identity(BASE_HEAD, BASE_TREE)
    pins = source_pins()
    sealed = decode(blob(BASE_HEAD, BASE_RESULT, BASE_SHA))
    resolved = {p: integer(b) for p, b in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    original = checked_rows(list(resolved.items()), resolved)
    require(sha(projection(original)) == sealed["BOUNDS_SHA256_AFTER"], "Base ledger digest")
    cursor = obj(sealed["CURSOR"])
    coarse = {p: integer(b) for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(
        len(coarse) == 197 and set(coarse) == set(cast(list[str], cursor["PROFILE_IDS"])),
        "cursor ID partition mismatch",
    )
    require(sha(render(cursor)) == sealed["CURSOR_SHA256"], "cursor pin")
    require(max(coarse.values()) == cursor["BOUND"], "cursor maximum mismatch")
    for pid, bound in coarse.items():
        require(
            route.r28.coarse_profile_envelope(tuple(map(int, pid))).family_upper_bound == bound,
            "cursor row bound differs from Base evaluator",
        )
    donor_inputs: list[dict[str, object]] = []
    for head, tree, path, digest in DONORS:
        identity(head, tree)
        donor = decode(blob(head, path, digest))
        pid = string(donor["TARGET_PROFILE"])
        require(
            donor["BASE_HEAD"] == BASE_HEAD and donor["BASE_TREE"] == BASE_TREE,
            "donor belongs to a different mathematical Base",
        )
        require(original[pid] == donor["CURRENT_PROFILE_BOUND"], "donor old row drift")
        bound = integer(donor["NEW_FULL_PROFILE_BOUND"])
        expected = dict(original)
        expected[pid] = bound
        if "RESOLVED_ROW_BOUNDS" in donor:
            require(obj(donor["RESOLVED_ROW_BOUNDS"]) == expected, "donor changed other rows")
            require(donor["CURSOR"] == cursor, "donor cursor drift")
        else:
            # Donor A seals map digests instead of serializing every bound.
            require(
                sha(json.dumps(expected, sort_keys=True).encode())
                == donor["PROJECTED_LEDGER_SHA256"],
                "donor A projected ledger digest",
            )
            others = {p: b for p, b in expected.items() if p != pid}
            require(
                sha(json.dumps(others, sort_keys=True).encode()) == donor["OTHER_4646_ROWS_SHA256"]
                and donor["LEDGER_ROWS"] == len(expected),
                "donor A other rows changed",
            )
            require(donor["CURSOR_SHA256"] == sha(render(cursor)), "donor A cursor drift")
        resolved[pid] = bound
        donor_inputs.append(
            {
                "HEAD": head,
                "TREE": tree,
                "RESULT_PATH": path,
                "RESULT_SHA256": digest,
                "PROFILE_ID": pid,
                "OLD_BOUND": original[pid],
                "FIXED_INPUT_BOUND": bound,
                "STORED_TASK_STATUS": donor["TASK_STATUS"],
                "ACCEPTANCE": "FIXED_CONDITIONAL_INPUT_ONLY; NO_AUTHORITY_UPGRADE",
            }
        )
    before = dict(resolved)
    r30 = decode(blob(BASE_HEAD, R30_PATH, R30_SHA))
    attempts = cast(list[dict[str, object]], r30["GROUP_ATTEMPTS"])
    adopted_s5 = set(obj(sealed["PROFILE_CERTIFICATES"])) | {
        string(obj(sealed["INHERITED_TARGET_BONFERRONI_5"])["PROFILE_ID"])
    }
    require(not (set(TARGETS) & adopted_s5), "target has adopted S5; evaluator scope must change")
    certificates: list[dict[str, object]] = []
    for pid in TARGETS:
        proof = theorem(pid)
        d = tuple(map(int, pid))
        references = [
            a for a in attempts if a.get("PROFILE_IDS") == [pid] and a.get("STATUS") == "INFEASIBLE"
        ]
        require(bool(references), "missing target cap authority")
        refutation = min(
            references, key=lambda a: integer(a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        )
        sealed_cap = integer(refutation["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        require(
            route.r28.r26.accepted_cap(refutation, (d,), sealed_cap) == sealed_cap,
            "target refutation not accepted by Base",
        )
        nb_cap, class_cap = nb.profile_nb_cap(d)[2], nb.r18_cap(d)
        old_cap = min(sealed_cap, nb_cap, class_cap)
        s4 = route.r28.profile_s4_floor(d)  # Separately query this exact row, no copied constant.
        old = envelope(pid, old_cap, s4)
        new_cap = integer(proof["ANALYTIC_CAP"])
        new = envelope(pid, new_cap, s4)
        old_bound, new_bound = max(t[1] for t in old), max(t[1] for t in new)
        require(before[pid] == old_bound, "target old envelope differs from Base row")
        resolved[pid] = new_bound
        certificates.append(
            {
                "THEOREM": proof,
                "PROFILE_ID": pid,
                "OLD_T_CAP": old_cap,
                "NEW_T_CAP": new_cap,
                "OLD_CAP_AUTHORITY": {
                    "PATH": R30_PATH,
                    "SHA256": R30_SHA,
                    "REFUTATION": refutation,
                    "NB_CAP": nb_cap,
                    "CLASS_CAP": class_cap,
                },
                "S4_AUTHORITY": {
                    "BASE_HEAD": BASE_HEAD,
                    "FUNCTION": (
                        "b649_k20_min_s2_current_cursor_class_owner_chase_r28.profile_s4_floor"
                    ),
                    "EXACT_PROFILE": pid,
                    "INHERITED_FLOOR": s4,
                    "RULE": "MAX(INHERITED, ROUTE_B); LOWER_BOUND_SUBTRACTED",
                },
                "S5_AUTHORITY": {
                    "ADOPTED_SCOPE_IN_BASE": sorted(adopted_s5),
                    "VALUE": None,
                    "USED": False,
                    "STATUS": "NO_ADOPTED_TARGET_CERTIFICATE",
                },
                "OLD_T_RANGE": [22, old_cap],
                "NEW_T_RANGE": [22, new_cap],
                "OLD_TERM_COUNT": len(old),
                "NEW_TERM_COUNT": len(new),
                "OLD_ALL_T_TERMS": old,
                "NEW_ALL_T_TERMS": new,
                "OLD_BOUND": old_bound,
                "NEW_BOUND": new_bound,
                "ROW_DELTA": old_bound - new_bound,
                "OLD_ALL_ARGMAX": [t for t in old if t[1] == old_bound],
                "NEW_ALL_ARGMAX": [t for t in new if t[1] == new_bound],
            }
        )
    require(
        sorted(p for p in before if before[p] != resolved[p]) == sorted(TARGETS),
        "projection changed non-target row",
    )
    checked_rows(list(resolved.items()), {p: resolved[p] for p in original})
    first, last = family(before, coarse), family(resolved, coarse)
    incumbent = integer(sealed["INCUMBENT"])
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_PROVEN; PENDING_EXTERNAL_FOCUSED_REVIEW",
        "IMPLEMENTATION_BASE": {"HEAD": IMPLEMENTATION_HEAD, "TREE": IMPLEMENTATION_TREE},
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": BASE_RESULT,
            "RESULT_SHA256": BASE_SHA,
        },
        "SOURCE_PINS": pins,
        "PROOF": __doc__,
        "DONOR_FIXED_INPUTS": donor_inputs,
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "NEW_CERTIFICATE_ACCEPTANCE": "CANDIDATE_FOR_ONE_FRESH_FOCUSED_SCIENTIFIC_REVIEW",
        "PROJECTION_STATUS": "BASE_SPECIFIC_CONDITIONAL; NOT_CANONICAL_ADOPTION",
        "BASE_PROVENANCE_VERBATIM": sealed["PROVENANCE"],
        "INHERITED_CAVEATS_LOCATOR": {
            "HEAD": BASE_HEAD,
            "PATH": BASE_RESULT,
            "FIELD": "INHERITED_CAVEATS_AND_STATUS_VERBATIM",
            "DISPOSITION": "PRESERVED_WITHOUT_UPGRADE",
        },
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4_FLOOR", "S3"],
        "ROUNDING": "K4_CEILING; A_MAX_FLOOR; FINAL_RATIONAL_CEILING = BASE - FLOOR(4*S4/7)",
        "CERTIFICATES": certificates,
        "RESOLVED_ROW_BOUNDS_BEFORE": before,
        "RESOLVED_ROW_BOUNDS_AFTER": resolved,
        "RESOLVED_ROWS": len(resolved),
        "BOUNDS_SHA256_BEFORE": sha(projection(before)),
        "BOUNDS_SHA256_AFTER": sha(projection(resolved)),
        "PROJECTED_FAMILY_BEFORE": first,
        "PROJECTED_FAMILY_AFTER": last,
        "FAMILY_DELTA": integer(first["MAXIMUM"]) - integer(last["MAXIMUM"]),
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": integer(last["MAXIMUM"]) - incumbent,
        "CURSOR": cursor,
        "CURSOR_PRESERVED": "PASS — ALL_197_IDS_AND_BOUNDS_UNCHANGED",
        "CURSOR_SHA256_BEFORE": sha(render(cursor)),
        "CURSOR_SHA256_AFTER": sha(render(cursor)),
        "GRAPH_ENUMERATION_COMPLETENESS": "NOT_APPLICABLE — ANALYTIC_UNIVERSAL_BOUND",
        "SOLVER_CALLS": 0,
        "GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def verify_result(stored: Mapping[str, object]) -> None:
    require(
        render(stored) == render(compute_result()), "stored certificate not exactly reproducible"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce the three-profile analytic certificate")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if RESULT.exists():
        require(RESULT.read_bytes() == raw, "stored certificate differs")
    else:
        require(not args.verify, "missing certificate")
        with RESULT.open("xb") as out:
            out.write(raw)
    print(
        json.dumps(
            {
                "RESULT": str(RESULT),
                "SHA256": sha(raw),
                "FAMILY_BEFORE": result["PROJECTED_FAMILY_BEFORE"],
                "FAMILY_AFTER": result["PROJECTED_FAMILY_AFTER"],
                "GAP": result["GAP_TO_INCUMBENT"],
            }
        )
    )


if __name__ == "__main__":
    main()
