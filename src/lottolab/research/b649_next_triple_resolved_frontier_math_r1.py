"""Three complete-profile analytic certificates, with no Family ledger update.

The proof is docs/research/B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1.md.
An existing, zero-solve, Git-pinned replay supplies the three catalog rows.
Its completed protected capture is embedded verbatim for portable source audit;
this module does not implement a second ledger or rerun historical research.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import resource
import subprocess
from collections import Counter
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any

TASK_ID = "B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1"
ROOT = Path(__file__).resolve().parents[3]
BASE_HEAD = "b53a776a025a5218eef73e9a6933b972b4f5395b"
BASE_TREE = "d1b6d18bd41d45bd2cbc5b947f23cd6561e6d6b1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
BASE_RESULT = (
    "docs/research/matrix-native-results/b649-tied-two-row-27-event-from-t255-r1-result.json"
)
BASE_RESULT_SHA = "766ebb9b2a046c50002082b19a3d60bfd77e8fc46ab894bfa2fd5fe542ca5d25"
FROZEN_BOUNDS = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
FROZEN_BOUNDS_SHA = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
RESULT_PATH = (
    ROOT
    / "docs/research/matrix-native-results/b649-next-triple-resolved-frontier-math-r1-result.json"
)
PROOF_PATH = ROOT / "docs/research/B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1.md"
TEST_PATH = ROOT / "tests/unit/test_b649_next_triple_resolved_frontier_math_r1.py"
CAPTURE_ROOT = (
    Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints")
    / TASK_ID
    / "captures"
)
SOURCE_CAPTURE = CAPTURE_ROOT / "recover-profile-sources.json"
SOURCE_CAPTURE_SHA = "4f4f56225d8ae9cb2e212d323659e7bc50bea0db3b6f7cfe0cfa5087f0c8fd43"
EXTRACTION_CODE_SHA = "365cb3dc098da502d7b7083a189ad0bef623726e24bcc01b46c08014bb4ad35f"
TARGETS = ("65555555555531100000", "66555555554441100000", "66555555555422100000")
HISTOGRAMS = (
    {6: 1, 5: 11, 3: 1, 1: 2, 0: 5},
    {6: 2, 5: 8, 4: 3, 1: 2, 0: 5},
    {6: 2, 5: 9, 4: 1, 2: 2, 1: 1, 0: 5},
)
SOURCE_INDICES = dict(zip(TARGETS, (1616, 1466, 1450), strict=True))
SOURCE_U = dict(zip(TARGETS, (2289, 2290, 2292), strict=True))
OLD_BOUND = 313_391_844
TARGET_BOUND = 313_391_740
SUPPORT_MODEL = {
    "TICKETS": 20,
    "TICKET_CAPACITY": 6,
    "LABELS": 49,
    "TRIPLE_SUPPORTS": 22,
    "PAIR_SUPPORTS": 27,
    "PAIR_LINEARITY": True,
}
MODULE_PINS = {
    "b649_k20_min_s2_nb_degree_cap_frontier_r1": (
        "0084c857032a1a4f469659562a5e22cb3159c5e81d099cb4ceb87b01d663ca07"
    ),
    "b649_k20_min_s2_topw12_split_cap_certificate_r1": (
        "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784"
    ),
    "b649_k20_min_s2_route_b_current_owner_refinement_r32": (
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d"
    ),
    "b649_k20_min_s2_dangerous_core_realizability_r5": (
        "ad2c524bcdb716af1f1f744435576376499e3f39c3a744aec613542c41964487"
    ),
    "b649_k20_min_s2_realizable_core_class_bound_r4": (
        "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
    ),
    "b649_k20_min_s2_topw12_coverage_repair_r1": (
        "ff663521fd7634825dfbfea01b8a294d5346d2c0d4e4d9dab9a67da97584551d"
    ),
}
Term = list[int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def pinned(head: str, path: str, digest: str) -> bytes:
    raw = git("show", f"{head}:{path}")
    require(sha(raw) == digest, f"Git source digest mismatch: {path}")
    return raw


def load_capture(path: Path = SOURCE_CAPTURE) -> dict:
    raw = path.read_bytes()
    require(sha(raw) == SOURCE_CAPTURE_SHA, "source capture digest mismatch")
    capture = json.loads(raw)
    validate_capture(capture)
    return capture


def validate_capture(capture: dict) -> None:
    require(
        capture.get("schema_version") == 1 and capture.get("exit_status") == 0,
        "source replay did not complete successfully",
    )
    require(capture.get("started_at") and capture.get("ended_at"), "incomplete source capture")
    identity = capture["execution_identity"]
    require(
        (identity["head"], identity["tree"]) == (BASE_HEAD, BASE_TREE),
        "source replay used the wrong Git objects",
    )
    require(identity["worktree_path"] == str(ROOT), "source replay used another worktree")
    command = capture["command"]
    require(
        command[-2] == "-c" and sha(command[-1].encode()) == EXTRACTION_CODE_SHA,
        "source extraction command differs from the observed replay",
    )
    require(capture["stderr"] == "", "source replay has unreviewed stderr")
    rows = json.loads(capture["stdout"])["PROFILE_SOURCES"]
    require(set(rows) == set(TARGETS), "source extraction domain is not exactly three profiles")


def source_authority(capture: dict) -> tuple[dict, list[dict]]:
    """Audit the original replay; read only target entries from fixed artifacts."""
    validate_capture(capture)
    for head, tree in ((BASE_HEAD, BASE_TREE), (FROZEN_HEAD, FROZEN_TREE)):
        require(
            git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree,
            "fixed head/tree mismatch",
        )
    base = json.loads(pinned(BASE_HEAD, BASE_RESULT, BASE_RESULT_SHA))
    frozen = json.loads(pinned(FROZEN_HEAD, FROZEN_BOUNDS, FROZEN_BOUNDS_SHA))
    require(
        (base["TOTAL_EVENTS"], base["ROWS_AFTER"], len(base["EVENT_HISTORY"])) == (27, 4647, 27),
        "fixed base event/row count mismatch",
    )
    require(
        base["NEXT_DISTINCT_RESOLVED_BOUND"] == OLD_BOUND
        and base["NEXT_DISTINCT_RESOLVED_OWNERS"] == list(TARGETS),
        "fixed target owners mismatch",
    )
    require(
        not set(TARGETS).intersection(base["CHANGED_PROFILE_IDS_FROM_FROZEN"])
        and not any(e["PROFILE_ID"] in TARGETS for e in base["EVENT_HISTORY"]),
        "target row was changed after Frozen",
    )
    hashes = {}
    for module, digest in MODULE_PINS.items():
        path = f"src/lottolab/research/{module}.py"
        raw = pinned(BASE_HEAD, path, digest)
        require((ROOT / path).read_bytes() == raw, f"reused implementation differs: {path}")
        hashes[path] = digest
    # The model and Route-B constants are checked against literal assignments in Git.
    r4 = git(
        "show",
        f"{BASE_HEAD}:src/lottolab/research/b649_k20_min_s2_realizable_core_class_bound_r4.py",
    )
    constants = {}
    for node in ast.parse(r4).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    expected = {
        "K20_TICKET_COUNT": 20,
        "K20_TICKET_CAPACITY": 6,
        "K20_LABEL_COUNT": 49,
        "K20_TRIPLE_SUPPORT_COUNT": 22,
        "K20_DOUBLE_SUPPORT_COUNT": 27,
        "K20_S1": 372228640,
        "K20_S2": 63838600,
        "K20_S3_WEDGE_COEFFICIENT": 2800,
        "K20_S3_TRIANGLE_COEFFICIENT": 11872,
        "K20_S3_CONSTANT": 30800,
    }
    require(
        all(constants.get(k) == v for k, v in expected.items()),
        "pinned support/Route-B constants differ",
    )
    rows = json.loads(capture["stdout"])["PROFILE_SOURCES"]
    snapshots = []
    for pid in TARGETS:
        c = rows[pid]
        s = {
            "PROFILE_ID": pid,
            "DEGREES": c["profile"],
            "SUPPORT_MODEL": dict(SUPPORT_MODEL),
            "ORIGINAL_CAP": c["triangle_cap"],
            "S4_BASE": c["s4"],
            "OLD_BOUND": c["bound"],
            "ROW_SOURCE": f"{c['source_result']}:{c['source_row']}",
            "SOURCE_RELAXATION": c["relaxation"],
            "SOURCE_REALIZABILITY": c["realizability"],
            "W_U_GMAX": c["W_U_GMAX"],
            "A_MAX": c["A_MAX"],
            "SOURCE_ROUTE_B_TERM_COUNT": c["ROUTE_B_TERM_COUNT"],
            "SOURCE_ROUTE_B_ARGMAX": c["ROUTE_B_ARGMAX"],
            "ROW_SOURCE_KIND": "VIRTUAL_REPLAY_CATALOG_ROW_NOT_JSON_MEMBER",
            "PROOF_LOCATOR": (
                f"git:{BASE_HEAD}:src/lottolab/research/"
                "b649_k20_min_s2_nb_degree_cap_frontier_r1.py#module-docstring,refine_resolved"
            ),
        }
        validate_snapshot(s)
        require(
            frozen["RESOLVED_ROW_BOUNDS"][pid] == s["OLD_BOUND"], "Frozen target bound mismatch"
        )
        snapshots.append(s)
    return {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_TARGET_BOUNDS_SHA256": FROZEN_BOUNDS_SHA,
        "BASE_EVENTS": 27,
        "BASE_ROWS": 4647,
        "SOURCE_FILE_SHA256": hashes,
        "PROFILE_ROWS": "MATCH",
        "SOURCE_CAPTURE_SHA256": SOURCE_CAPTURE_SHA,
        "SOURCE_LOCATOR_CAVEAT": (
            "NB_CERTIFICATES indices are virtual catalog rows, not summary JSON members"
        ),
    }, snapshots


def validate_snapshot(s: dict) -> None:
    pid = s["PROFILE_ID"]
    require(pid in TARGETS, "wrong profile")
    d = s["DEGREES"]
    require(
        all(type(v) is int for v in d) and Counter(d) == HISTOGRAMS[TARGETS.index(pid)],
        "wrong degree distribution",
    )
    require(
        "".join(map(str, d)) == pid and sum(d) == 66 and len(d) == 20, "profile identity mismatch"
    )
    require(s["SUPPORT_MODEL"] == SUPPORT_MODEL, "wrong support model / ticket capacity")
    require(
        s["ORIGINAL_CAP"] == 266 and s["S4_BASE"] == 112 and s["OLD_BOUND"] == OLD_BOUND,
        "wrong source cap, S4 base or bound",
    )
    expected_source = (
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:"
        f"NB_CERTIFICATES[{SOURCE_INDICES[pid]}]"
    )
    require(
        s["ROW_SOURCE"] == expected_source
        and s["SOURCE_RELAXATION"] == "NB_DEGREE_CAP_ROUTE_B_ALL_T",
        "wrong source row / proof scope",
    )
    require(
        s["W_U_GMAX"] == [824, SOURCE_U[pid], 12] and s["A_MAX"] == 195,
        "wrong recorded Route-B premises",
    )


def premises(s: dict) -> dict:
    validate_snapshot(s)
    d = s["DEGREES"]
    g, h = [6 + v for v in d], [13 - v for v in d]
    core = [v for v in d if v]
    phi = comb(20, 3) - 18 * 97 + sum(comb(v, 2) for v in h)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(a * b for a, b in zip(g, h, strict=True)), 2)
    require(
        (len(core), d.count(0), sum(g), sum(h), phi, goodman, sum(8 - v for v in core))
        == (15, 5, 186, 194, 290, 290, 54),
        "Goodman/split premises mismatch",
    )
    ranges = {str(v): list(range(7 - v)) for v in sorted(set(core), reverse=True)}
    zero_range = list(range(2, 7))
    verify_coverage(d, ranges, zero_range)
    coordinate_values = {v: [x * (x + 4 - int(v)) for x in xs] for v, xs in ranges.items()}
    endpoint_max = {v: max(0, (6 - int(v)) * (10 - 2 * int(v))) for v in ranges}
    require(
        all(max(xs) == endpoint_max[v] for v, xs in coordinate_values.items()),
        "endpoint audit mismatch",
    )
    cap = 170 + sum(endpoint_max[str(v)] for v in core)
    return {
        "DEGREE_HISTOGRAM": {str(k): v for k, v in sorted(Counter(d).items(), reverse=True)},
        "CORE": 15,
        "ZERO": 5,
        "G_EDGES": 93,
        "H_EDGES": 97,
        "PHI_INCLUSION_EXCLUSION": phi,
        "PHI_GOODMAN": int(goodman),
        "W": sum(comb(v, 2) for v in g),
        "U": sum(comb(v, 3) for v in g),
        "A_MAX": sum(v * (v + 4) for v in d) // 3,
        "SIGMA_RANGES": ranges,
        "ZETA_RANGE": zero_range,
        "CORE_QUADRATIC_VALUES": coordinate_values,
        "CORE_ENDPOINT_MAXIMA": endpoint_max,
        "PROVED_T_CAP": cap,
        "RELAXATION_COMPLETENESS": "PROVED_UNIVERSAL_MAP_ALL_LEGAL_REALIZATIONS",
        "NONNEGATIVE_REMAINDER": "P_IS_SUM_OF_FOUR_CARDINALITIES",
        "GOODMAN_IDENTITY": "INDEPENDENT_MIXED_TRIPLE_DOUBLE_COUNT",
    }


def verify_coverage(d: list[int], ranges: dict, zero_range: list[int]) -> None:
    expected = {str(v): list(range(7 - v)) for v in set(d) if v}
    require(
        ranges == expected and zero_range == list(range(2, 7)), "incomplete relaxation coverage"
    )


def split_values(
    s: dict, sigma: list[int], zeta: list[int], remainder: int
) -> tuple[Fraction, int]:
    """Three exact forms on the whole necessary superset; existence is not assumed."""
    validate_snapshot(s)
    d = [v for v in s["DEGREES"] if v]
    require(len(sigma) == 15 and len(zeta) == 5, "wrong cross degree lengths")
    require(
        all(type(x) is int and 0 <= x <= 6 - v for x, v in zip(sigma, d, strict=True)),
        "invalid capacity constraint",
    )
    require(all(type(q) is int and 2 <= q <= 6 for q in zeta), "invalid zero capacity constraint")
    require(sum(sigma) == sum(zeta), "invalid cross-edge balance")
    require(type(remainder) is int and remainder >= 0, "negative remainder")
    h = [8 - v + x for v, x in zip(d, sigma, strict=True)]
    a = [q - 2 for q in zeta]
    direct = (
        Fraction(290)
        - Fraction(5 * sum(h), 2)
        - Fraction(15 * sum(a), 2)
        + sum(x * v for x, v in zip(sigma, h, strict=True))
        + sum(q * v for q, v in zip(zeta, a, strict=True))
        - remainder
    )
    balanced = (
        230
        + sum(x * (x - 4 - v) for x, v in zip(sigma, d, strict=True))
        + sum(q * q for q in zeta)
        - remainder
    )
    upper = 170 + sum(x * (x + 4 - v) for x, v in zip(sigma, d, strict=True)) - remainder
    require(direct == balanced, "split polynomial identity mismatch")
    # upper-direct = sum (q-2)*(6-q), with no rounding or optimization.
    require(
        upper - direct == sum((q - 2) * (6 - q) for q in zeta) >= 0,
        "zero-coordinate secant inequality failed",
    )
    return direct, upper


def graph_identities(n: int, core: set[int], edges: set[tuple[int, int]]) -> dict:
    """Supplemental independent observation of the universal graph identities."""
    vertices = set(range(n))
    require(core <= vertices, "invalid graph partition")
    zero = vertices - core
    all_edges = set(combinations(range(n), 2))
    require(edges <= all_edges, "invalid graph edges")
    complement = all_edges - edges
    nb = {v: {w for w in vertices if tuple(sorted((v, w))) in edges} for v in vertices}

    def triangles(part: set[int], es: set[tuple[int, int]]) -> int:
        return sum(set(combinations(t, 2)) <= es for t in combinations(sorted(part), 3))

    t_g, t_h = triangles(vertices, edges), triangles(vertices, complement)
    g = [len(nb[v]) for v in range(n)]
    require(
        Fraction(t_g + t_h) == comb(n, 3) - Fraction(sum(x * (n - 1 - x) for x in g), 2),
        "Goodman identity failed",
    )
    require(
        t_g == comb(n, 3) - (n - 2) * len(complement) + sum(comb(n - 1 - x, 2) for x in g) - t_h,
        "inclusion-exclusion identity failed",
    )
    m = {e for e in complement if set(e) <= core}
    mz = {e for e in complement if set(e) <= zero}
    sigma = {v: len(nb[v] & zero) for v in core}
    zeta = {v: len(nb[v] & core) for v in zero}
    h = {v: sum(v in e for e in m) for v in core}
    a = {v: sum(v in e for e in mz) for v in zero}
    parts = [
        triangles(core, m),
        triangles(zero, mz),
        sum(len(nb[x] & nb[y] & zero) for x, y in m),
        sum(len(nb[x] & nb[y] & core) for x, y in mz),
    ]
    mixed = (
        len(zero) * len(m)
        + len(core) * len(mz)
        - sum(sigma[v] * h[v] for v in core)
        - sum(zeta[v] * a[v] for v in zero)
    )
    require(t_h == mixed + sum(parts) and min(parts) >= 0, "complement remainder identity failed")
    return {"T_G": t_g, "T_H": t_h, "P_TERMS": parts}


def route_terms(s: dict, cap: int) -> list[Term]:
    validate_snapshot(s)
    require(type(cap) is int and 22 <= cap <= s["ORIGINAL_CAP"], "invalid Route-B cap")
    d = s["DEGREES"]
    g = [6 + v for v in d]
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    amax = sum(v * (v + 4) for v in d) // 3
    terms = []
    for t in range(22, cap + 1):
        numerator = u - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, -((-numerator) // 4))
        contained = min(k4, amax)
        s4 = max(s["S4_BASE"], 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 308390040 + s3 - (4 * s4) // 7
        terms.append([t, bound, k4, contained, s4, s3])
    return terms


def verify_rounding(integer_part: int, s4: int, bound: int) -> None:
    exact = Fraction(integer_part) - Fraction(4 * s4, 7)
    require(bound == -((-exact.numerator) // exact.denominator), "wrong rounding / S4 credit")


def verify_route(s: dict, cap: int, terms: list[Term]) -> None:
    """Separate Fraction path checks every term, ceiling, allowance and credit."""
    validate_snapshot(s)
    require([t[0] for t in terms] == list(range(22, cap + 1)), "incomplete Route-B domain")
    degrees = [v + 6 for v in s["DEGREES"]]
    w = sum(v * (v - 1) // 2 for v in degrees)
    u = sum(v * (v - 1) * (v - 2) // 6 for v in degrees)
    outside = sum(d * (g - 2) for d, g in zip(s["DEGREES"], degrees, strict=True))

    def ceiling(q: Fraction) -> int:
        return -((-q.numerator) // q.denominator)

    amax = Fraction(outside, 3).__floor__()
    for t, bound, k4, contained, s4, s3 in terms:
        expected_k4 = max(0, ceiling(Fraction(u - (max(degrees) - 2) * (w - 3 * t), 4)))
        require(k4 == expected_k4, "wrong K4 ceiling")
        require(contained == min(expected_k4, amax), "wrong contained allowance")
        expected_s4 = max(s["S4_BASE"], 448 * contained + 679 * (k4 - contained))
        require(s4 == expected_s4, "wrong S4 floor")
        expected_s3 = 2800 * w + 11872 * (t - 22) - 30800
        require(s3 == expected_s3, "wrong S3 recount")
        verify_rounding(372228640 - 63838600 + expected_s3, expected_s4, bound)


def certify(s: dict) -> dict:
    p = premises(s)
    cap = p["PROVED_T_CAP"]
    old = route_terms(s, s["ORIGINAL_CAP"])
    new = route_terms(s, cap)
    verify_route(s, s["ORIGINAL_CAP"], old)
    verify_route(s, cap, new)
    require(
        len(old) == s["SOURCE_ROUTE_B_TERM_COUNT"]
        and max(old, key=lambda t: t[1]) == s["SOURCE_ROUTE_B_ARGMAX"]
        and max(t[1] for t in old) == s["OLD_BOUND"],
        "source Route-B envelope mismatch",
    )
    require(new == old[: cap - 21], "new envelope is not the complete prefix")
    # A third arithmetic path uses the unchanged pinned Route-B implementation.
    from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32

    d = tuple(s["DEGREES"])
    require(
        [list(t) for t in r32.route_b_envelope(d, s["ORIGINAL_CAP"], s["S4_BASE"])] == old,
        "pinned R32 old-term mismatch",
    )
    require(
        [list(t) for t in r32.route_b_envelope(d, cap, s["S4_BASE"])] == new,
        "pinned R32 new-term mismatch",
    )
    peak = max(new, key=lambda t: t[1])
    require(peak[1] <= TARGET_BOUND and peak[1] < s["OLD_BOUND"], "target bound not reached")
    return {
        "PROFILE_ID": s["PROFILE_ID"],
        "SOURCE_IDENTITY": s,
        "PREMISES": p,
        "OLD_CAP": s["ORIGINAL_CAP"],
        "PROVED_CAP": cap,
        "OLD_BOUND": s["OLD_BOUND"],
        "NEW_BOUND": peak[1],
        "PROOF_SCOPE": "FULL_PROFILE",
        "LOAD_BEARING_PREMISES": SUPPORT_MODEL,
        "LOAD_BEARING_PROOF": "T <= 170 + sum_core sigma*(sigma+4-d) - P <= 262",
        "RELAXATION_COMPLETENESS": p["RELAXATION_COMPLETENESS"],
        "UNPROVED_ASSUMPTIONS": [],
        "T_ENDPOINT_ATTAINMENT": "NOT_ASSERTED",
        "OLD_ROUTE_B_TERMS": old,
        "ROUTE_B_TERMS": new,
        "OLD_TERM_COUNT": len(old),
        "FULL_TERM_COUNT": len(new),
        "OLD_ARGMAX_TERM": max(old, key=lambda t: t[1]),
        "ARGMAX_TERM": peak,
        "EXACT_INTEGER_RECOUNT": "PASS_ALL_OLD_AND_NEW_TERMS",
        "EXACT_FRACTION_RECOUNT": "PASS_ALL_OLD_AND_NEW_TERMS",
        "K4_CEILING": "PASS",
        "S4_CREDIT": "PASS",
        "CONTAINED_ALLOWANCE": "PASS",
        "ROUNDING_CHECK": "PASS",
        "PINNED_R32_RECOUNT": "PASS_ALL_OLD_AND_NEW_TERMS",
    }


def reject(action: Any) -> str:
    try:
        action()
    except ValueError:
        return "PASS"
    raise AssertionError("invalid mathematical certificate was accepted")


def negative_cases(s: dict) -> dict[str, str]:
    """Meaningful mutants exercise every requested rejection category."""
    p = premises(s)
    wrong_profile = copy.deepcopy(s)
    wrong_profile["PROFILE_ID"] = "0" * 20
    wrong_degrees = copy.deepcopy(s)
    wrong_degrees["DEGREES"][0] -= 1
    wrong_cap = copy.deepcopy(s)
    wrong_cap["ORIGINAL_CAP"] += 1
    sigma = [0] * 15
    remaining = 10
    for i in range(14, -1, -1):
        sigma[i] = min(6 - s["DEGREES"][i], remaining)
        remaining -= sigma[i]
    require(remaining == 0, "negative-control seed incomplete")
    zeta = [2] * 5
    split_values(s, sigma, zeta, 0)
    bad_capacity = sigma.copy()
    bad_capacity[0] = 1
    bad_balance = zeta.copy()
    bad_balance[0] = 3
    bad_ranges = copy.deepcopy(p["SIGMA_RANGES"])
    bad_ranges["1"].pop()
    terms = route_terms(s, p["PROVED_T_CAP"])
    wrong_k4 = copy.deepcopy(terms)
    wrong_k4[-1][2] -= 1
    wrong_s4 = copy.deepcopy(terms)
    wrong_s4[-1][4] += 1
    wrong_credit = copy.deepcopy(terms)
    wrong_credit[-1][1] -= 1
    # All actual S4 terms are multiples of seven. An explicitly synthetic
    # arithmetic witness is necessary to distinguish floor from ceiling.
    integer_part = 308390040 + terms[-1][5]
    rounding_s4 = terms[-1][4] + 1
    wrong_rounded = (Fraction(integer_part) - Fraction(4 * rounding_s4, 7)).__floor__()
    wrong_allowance = copy.deepcopy(terms)
    wrong_allowance[-1][3] += 1
    return {
        "Wrong Profile": reject(lambda: validate_snapshot(wrong_profile)),
        "Wrong Degree Distribution": reject(lambda: validate_snapshot(wrong_degrees)),
        "Wrong Source Cap": reject(lambda: validate_snapshot(wrong_cap)),
        "Invalid Capacity Constraint": reject(lambda: split_values(s, bad_capacity, zeta, 0)),
        "Invalid Cross-edge Balance": reject(lambda: split_values(s, sigma, bad_balance, 0)),
        "Negative Remainder": reject(lambda: split_values(s, sigma, zeta, -1)),
        "Incomplete Relaxation Coverage": reject(
            lambda: verify_coverage(s["DEGREES"], bad_ranges, p["ZETA_RANGE"])
        ),
        "Wrong K4 Ceiling": reject(lambda: verify_route(s, p["PROVED_T_CAP"], wrong_k4)),
        "Wrong S4 Credit": reject(lambda: verify_route(s, p["PROVED_T_CAP"], wrong_credit)),
        "Wrong S4 Floor": reject(lambda: verify_route(s, p["PROVED_T_CAP"], wrong_s4)),
        "Wrong Contained Allowance": reject(
            lambda: verify_route(s, p["PROVED_T_CAP"], wrong_allowance)
        ),
        "Incomplete Route-B Domain": reject(lambda: verify_route(s, p["PROVED_T_CAP"], terms[:-1])),
        "Wrong Rounding": reject(lambda: verify_rounding(integer_part, rounding_s4, wrong_rounded)),
    }


def build_result(capture: dict) -> dict:
    authority, snapshots = source_authority(capture)
    certificates = [certify(s) for s in snapshots]
    negatives = {s["PROFILE_ID"]: negative_cases(s) for s in snapshots}
    require(
        all(v == "PASS" for cases in negatives.values() for v in cases.values()),
        "negative case failure",
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "THREE_FULL_PROFILE_BOUNDS_PROVED_SELF_CHECK_ONLY",
        "WORKER_ROUTE": "STANDARD_JUDGED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "AUTHORITY": authority,
        "SOURCE_RECOVERY_CAPTURE": capture,
        "CERTIFICATES": certificates,
        "COMMON_ANALYTIC_INEQUALITY": "T <= 170 + sum_core sigma*(sigma+4-d) - P",
        "PROOF_SCOPE": "FULL_PROFILE",
        "RELAXATION_COMPLETENESS": "PROVED",
        "THREE_PROFILE_FRONTIER_RESULT": "PROVED",
        "OLD_BOUND_EACH": OLD_BOUND,
        "NEW_BOUND_EACH": max(c["NEW_BOUND"] for c in certificates),
        "TARGET_BOUND_EACH": TARGET_BOUND,
        "NEXT_PROSPECTIVE_BOUND": "UNKNOWN",
        "NEXT_PROSPECTIVE_BOUND_CAVEAT": (
            "No fourth-profile research or full Family recomputation; "
            "threshold 313391740 is Planner-supplied"
        ),
        "BASE_MAX_RESOLVED_BOUND": 313392128,
        "PROSPECTIVE_BASE_PLUS_CLASS197_MAX": 313392128,
        "PROSPECTIVE_STATUS": "ONLY_A_PROJECTION_BASE_HIGHER_OWNER_REMAINS_UNCHANGED",
        "FAMILY_GAIN": "NOT_CLAIMED",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "COUNTEREXAMPLE_STATUS": "NO_COUNTEREXAMPLE_SEARCH; ANALYTIC_UNIVERSAL_PROOF",
        "UNPROVED_ASSUMPTIONS": [],
        "ENDPOINT_ATTAINMENT": "NOT_ASSERTED",
        "NEGATIVE_CASE_RESULTS": negatives,
        "SOURCE_SHA256": sha(Path(__file__).read_bytes()),
        "TEST_SHA256": sha(TEST_PATH.read_bytes()),
        "PROOF_SHA256": sha(PROOF_PATH.read_bytes()),
        "HEAVY_SOLVER_STARTED": False,
        "SOLVER_CALLS": 0,
        "FULL_SUITE": "NOT_RUN",
        "FAMILY_LEDGER_WRITES": 0,
        "REMOTE_WRITES": 0,
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-capture", type=Path, default=SOURCE_CAPTURE)
    parser.add_argument("--test-capture", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build_result(load_capture(args.source_capture))
    if args.test_capture:
        raw = args.test_capture.read_bytes()
        checked = json.loads(raw)
        require(
            checked["exit_status"] == 0 and checked["started_at"] and checked["ended_at"],
            "focused tests not passed",
        )
        require(
            "tests/unit/test_b649_next_triple_resolved_frontier_math_r1.py" in checked["command"],
            "wrong focused test command",
        )
        require(
            checked["execution_identity"]["worktree_path"] == str(ROOT), "test worktree mismatch"
        )
        result["FOCUSED_TEST_CAPTURE"] = checked
        result["FOCUSED_TEST_CAPTURE_SHA256"] = sha(raw)
    result["SEAL"] = {"CANONICAL_PAYLOAD_SHA256": sha(canonical(result))}
    encoded = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    if args.write:
        require(args.test_capture is not None, "terminal result requires focused-test evidence")
        with RESULT_PATH.open("xb") as out:
            out.write(encoded)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "NEW_BOUND_EACH": result["NEW_BOUND_EACH"],
                "CAPS": [c["PROVED_CAP"] for c in result["CERTIFICATES"]],
                "RESULT_SHA256": sha(encoded),
                "WRITE": args.write,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
