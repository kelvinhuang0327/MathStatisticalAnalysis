"""Universal Route-B/K4/S4 envelopes for exactly the 39 W=784 cursors.

MODEL AND COVERAGE. Twenty six-label tickets, 22 triple supports, 27 pair
supports, and pair-linearity give d in {0,...,6}^20, sorted descending,
sum d=66. A cursor names this histogram and ALL its legal support realizations,
not a representative graph. Pair-linearity gives g=6+d and sum g=186.
Enumerate only degree histograms: all 5126, exactly 197 with W<=785, exactly
41 with W=785 and exactly 39 with W=784. The last set equals the complete
maximum-owner set in the SHA-pinned direct result, in its original order.
No graphical or support-decomposition screen is applied to this band.
Resolved rows and the 282 excluded rows are inherited, not recertified.

W784 PREMISES. W=sum C(6+d,2)=663+sum d^2/2, so sum d^2=242.
The triple supports give 22 distinct graph triangles. Each graph triangle
closes three distinct centred wedges, hence 22<=t<=floor(784/3)=261 and
o=784-3t>=0. Every integer in this whole range is retained, whether realizable
or not: this relaxation can only enlarge the legal set.

K4. Let o_v count nonedges in N(v). Each spoils at most g_v-2 triples of N(v),
by adjoining a third neighbour. The union bound on spoiled triples yields
4q >= sum C(g,3)-sum (g_v-2)o_v >= J-(g_max-2)o.
Thus q>=L=max(0,ceil((J-(g_max-2)o)/4)). The right inequality uses o_v>=0;
overcounting spoiled triples weakens, rather than strengthens, the bound.

CONTAINED TRIPLES AND S4. Two triple supports in one K4 would share a ticket
pair, forbidden by pair-linearity. For each triple S, its number of common
outside neighbours is at most min_{v in S}(g_v-2), hence at most their average.
Summing over the 22 supports counts each contained-triple K4 once, and gives
a<=floor(sum d_v(g_v-2)/3)=floor((242+264)/3)=168, also a<=q.
The Base's exact local quartet counts are 448 with a triple and 679 without;
they depend on the six-label model, not W. Re-execute the pinned local count
function to check both. All other quartet intersections are nonnegative.
For the actual q,a, S4>=448a+679(q-a)>=f(q)=679q-231min(q,168).
f is nonnegative and increases by 448 up to 168 and by 679 thereafter.
Consequently S4>=f(L). Taking MAX with the independently valid Base floor
is sound; ADD is not. The Base profile floor is checked for every member:
each has zero or one inactive ticket, so the seven-inactive-ticket exception
does not apply and its floor is 112. Floor zero produces the same maxima,
so the inherited 112 floor is not essential to the improvement.

S3 AND UNION. Restrict label supports to the selected ticket subset: local
pair masks can come from global triples whose third ticket is outside it.
The quartet weights above likewise refer to restricted incidence masks.
Three-ticket local intersections are zero with at most one graph edge,
2800 for an open wedge, 20272 for a triangle of three distinct local pair
masks, and 7000 for a contained triple support. Hence the Base exact identity
S3=2800o+20272(t-22)+7000*22 holds for every legal realization.
S1=372228640 and S2=63838600 are fixed by this model. Outcomes distinguish
six main labels and one special: each seven-label set has seven assignments.
Winning means at least three labels in their union. In a seven-label outcome,
choose a winning three-hit subset for each winning ticket. Their pairs are
distinct, so 3r<=C(7,2) and r<=7. For integers r=0,...,7,
1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)C(r,4).
Sum over outcomes, substitute the LOWER S4 floor into its negative coefficient,
and take the exact rational CEILING. Equivalently an integral S1-S2+S3 minus
floor(4*S4/7). No S5 certificate, status, or term is used for these cursors.

SHARED THEOREM. Over all 39 histograms rederive J_min=1971 and g_max<=12.
Use A_max=168 and the whole 22..261 range. Replacing each J by its minimum
and g_max by 12 lowers L, lowers the increasing S4 floor, and raises each
union-bound term. Thus the shared envelope dominates every member at every t.
Its maximum is a common universal bound; exact degree-specific envelopes
are adopted per row. Every term and every argmax is saved, without relying
on monotonicity or claiming attainability of any relaxation endpoint.

ARITHMETIC AND FAMILY. K4 is rounded UP, A_max DOWN, S4 floors combined by
MAX, and the final Fraction UP. W784's A_max is 168, not W785's 169.
All 39 replacements are computed, and all other 158 cursor bounds plus all
4647 resolved bounds and the original exclusions/caveats are preserved.
Aggregate the full 4844-row ledger to obtain the new maximum and next level.
A gain is claimed only when every original maximum owner strictly drops and
the complete aggregation drops. CONDITIONAL_PROJECTION only: no canonical
adoption, global optimum, or prediction success improvement is asserted.
One independent fresh focused verdict is external to this self-hashed JSON,
so the reviewed tree remains identical to the one local commit's tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from fractions import Fraction
from importlib import import_module
from math import comb
from pathlib import Path
from typing import Any, cast

upstream: Any = import_module("lottolab.research.b649_cursor_41_owner_shared_bound_r1")
direct: Any = import_module("lottolab.research.b649_next_three_owner_cursor_floor_r1")
route: Any = upstream.route
type Record = dict[str, Any]
type Term = tuple[int, int, int, int, int, int]

TASK_ID = "B649_W784_39_CURSOR_SHARED_BOUND_R1"
INPUT_HEAD = "2159f5257e8c0742662bc087f4cf9bb275a515a5"
INPUT_TREE = "2018f025de0a5d47c0542bfa00cc5d8bba6ac8de"
UPSTREAM_HEAD = "06664eeb1a7ecb8138e15f70bac32681f84bbf55"
UPSTREAM_TREE = "11cf44e93cf921446118edf3b26127ff24e0fd49"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
INPUT_RESULT = (
    "docs/research/matrix-native-results/b649-next-three-owner-cursor-floor-r1-result.json"
)
INPUT_SHA = "72fa2649bfb76174b52bef6161218b48e54a4413463bdb38d53280a6cf924a28"
UPSTREAM_RESULT = (
    "docs/research/matrix-native-results/b649-cursor-41-owner-shared-bound-r1-result.json"
)
UPSTREAM_SHA = "f298983c96e321d5c4d1e5e3a53f127b2b730bf84d115ead4005dc63f2d8e148"
BASE_RESULT: str = upstream.r2.BASE_RESULT
BASE_SHA: str = upstream.r2.BASE_SHA
OWNER_ORDER_SHA = "08bb3d7e43b4b2ae438311b234489dedec153cc0e89eadd5c0448e0136c6254c"
SOURCE = "src/lottolab/research/b649_w784_39_cursor_shared_bound_r1.py"
TEST = "tests/unit/test_b649_w784_39_cursor_shared_bound_r1.py"
RESULT = "docs/research/matrix-native-results/b649-w784-39-cursor-shared-bound-r1-result.json"
ROOT = Path(__file__).resolve().parents[3]
CODE_PINS = {
    direct.SOURCE: "36832313285c6ee53f07e8a9ebda9fef0d630acfe0bc53c6262051c43ac1a979",
    direct.TEST: "fc74e32fe231405cebf46528db9d6ea54ab45f7a8d1e1249ab0aa961d1840f66",
    upstream.SOURCE: "c1e65bd5300fbd83be743e0a963622bd2686d23a855039cadadc6deb8f514e65",
    upstream.TEST: "61d3ed10d7c0b8b94c3a8da540a1a3a1e229978f8204ada63ccd3b32a8e79fa7",
}


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def ids_digest(ids: Sequence[str]) -> str:
    """Bind the exact original order; do not sort away a source-order change."""
    return sha(json.dumps(list(ids)).encode())


def unique_object(pairs: list[tuple[str, Any]]) -> Record:
    require(len(pairs) == len({k for k, _ in pairs}), "duplicate JSON/ledger row")
    return dict(pairs)


def decode(raw: bytes) -> Record:
    return cast(Record, json.loads(raw, object_pairs_hook=unique_object))


def git(*args: str, repo: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=repo).decode().strip()


def blob(head: str, path: str, repo: Path = ROOT) -> bytes:
    return subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)


def pinned_blob(head: str, path: str, digest: str, repo: Path = ROOT) -> bytes:
    data = blob(head, path, repo)
    require(sha(data) == digest, "result/source SHA pin: " + path)
    return data


def verify_identity(candidate: str = "HEAD", repo: Path = ROOT) -> str:
    require(sys.version_info[:2] == (3, 13), "Python 3.13 required")
    for head, tree in (
        (INPUT_HEAD, INPUT_TREE),
        (UPSTREAM_HEAD, UPSTREAM_TREE),
        (BASE_HEAD, BASE_TREE),
    ):
        require(git("rev-parse", head + "^{tree}", repo=repo) == tree, "Git TREE pin")
    require(
        git("merge-base", "--is-ancestor", UPSTREAM_HEAD, INPUT_HEAD, repo=repo) == "",
        "upstream ancestry",
    )
    head = git("rev-parse", candidate, repo=repo)
    if head == INPUT_HEAD:
        return "INPUT_HEAD_WITH_WORKING_CANDIDATE"
    require(
        git("rev-list", "--parents", "-n", "1", head, repo=repo).split()[1:] == [INPUT_HEAD],
        "direct single-parent child required",
    )
    paths = git("diff-tree", "--no-commit-id", "--name-status", "-r", head, repo=repo)
    require(
        sorted(paths.splitlines()) == sorted(f"A\t{p}" for p in (SOURCE, TEST, RESULT)),
        "exactly three authorized additions required",
    )
    for path in (SOURCE, TEST):
        require((ROOT / path).read_bytes() == blob(head, path, repo), "runtime candidate identity")
    return "FIXED_DIRECT_CHILD"


def fixed_input(repo: Path = ROOT) -> tuple[Record, Record, Record]:
    for path, digest in CODE_PINS.items():
        ref = UPSTREAM_HEAD if path in (upstream.SOURCE, upstream.TEST) else INPUT_HEAD
        require(
            (ROOT / path).read_bytes() == pinned_blob(ref, path, digest, repo),
            "upstream runtime source identity",
        )
    fixed = decode(pinned_blob(INPUT_HEAD, INPUT_RESULT, INPUT_SHA, repo))
    prior = decode(pinned_blob(UPSTREAM_HEAD, UPSTREAM_RESULT, UPSTREAM_SHA, repo))
    base = decode(pinned_blob(BASE_HEAD, BASE_RESULT, BASE_SHA, repo))
    for path, digest in ((INPUT_RESULT, INPUT_SHA), (UPSTREAM_RESULT, UPSTREAM_SHA)):
        require(sha((ROOT / path).read_bytes()) == digest, "working result SHA pin")
    require(
        prior["SOURCE_SHA256"] == CODE_PINS[upstream.SOURCE]
        and prior["TEST_SHA256"] == CODE_PINS[upstream.TEST],
        "upstream certificate code pins",
    )
    require(
        fixed["SOURCE_SHA256"] == CODE_PINS[direct.SOURCE]
        and fixed["TEST_SHA256"] == CODE_PINS[direct.TEST],
        "direct certificate code pins",
    )
    require(
        fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"] == prior["CURSOR_ROW_BOUNDS_AFTER"],
        "accepted upstream cursor ledger",
    )
    return fixed, prior, base


def coverage(cursor: Sequence[str], owners: Sequence[str], resolved: Sequence[str]) -> Record:
    raw = {"".join(map(str, p)): upstream.wedges(p) for p in upstream.raw_histograms()}
    require(len(cursor) == len(set(cursor)) == 197, "cursor row count/duplicates")
    require(len(owners) == len(set(owners)) == 39, "owner count/duplicates")
    require(len(resolved) == len(set(resolved)) == 4647, "resolved row count/duplicates")
    require(set(cursor) == {p for p, w in raw.items() if w <= 785}, "cursor coverage relation")
    require(set(owners) == {p for p, w in raw.items() if w == 784}, "W784 owner coverage relation")
    require(ids_digest(owners) == OWNER_ORDER_SHA, "owner order/digest")
    require(not set(cursor) & set(resolved) and set(resolved) <= raw.keys(), "resolved partition")
    excluded = sorted(raw.keys() - set(cursor) - set(resolved), reverse=True)
    require(len(excluded) == 282, "inherited exclusion count")
    return {
        "MEANING": "EXACT_SORTED_DEGREE_HISTOGRAM; ALL_LEGAL_SUPPORT_REALIZATIONS",
        "CONTINUATIONS": "ALL_LEGAL_GRAPHS_AND_TRIPLE_DECOMPOSITIONS; ALL_T_22_TO_261",
        "RAW_HISTOGRAMS": len(raw),
        "W_LE_785_COUNT": len(cursor),
        "W785_COUNT": sum(w == 785 for w in raw.values()),
        "W784_COUNT": sum(w == 784 for w in raw.values()),
        "CURSOR_W_HISTOGRAM": dict(sorted(Counter(raw[p] for p in cursor).items())),
        "OWNER_ORDER_SHA256": ids_digest(owners),
        "UPSTREAM_DESCENDING_DIGEST_CONVENTION": upstream.ids_digest(owners),
        "EXCLUDED_IDS": excluded,
        "EXCLUDED_IDS_SHA256": upstream.ids_digest(excluded),
        "EXCLUDED_W_RANGE": [min(raw[p] for p in excluded), max(raw[p] for p in excluded)],
        "SCREENS_USED_IN_CURSOR_BAND": "NONE",
        "R18_R30_CAPS_OR_STATUSES_USED_FOR_39": 0,
    }


def theorem(pid: str, owners: Sequence[str]) -> Record:
    require(pid in owners, "wrong histogram/W class")
    d = tuple(map(int, pid))
    require(
        len(d) == 20
        and tuple(sorted(d, reverse=True)) == d
        and all(0 <= x <= 6 for x in d)
        and sum(d) == 66,
        "wrong degree histogram",
    )
    g = tuple(6 + x for x in d)
    w = sum(comb(x, 2) for x in g)
    require(w == 784 and sum(g) == 186, "wrong histogram/W class")
    squares = sum(x * x for x in d)
    a_total = sum(x * (x + 4) for x in d)
    require(squares == 2 * w - 1326 == 242 and a_total == 506, "degree-specific premises")
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "W": w,
        "SUM_D_SQUARED": squares,
        "SUM_C_G_3": sum(comb(x, 3) for x in g),
        "G_MAX": max(g),
        "A_MAX_NUMERATOR": a_total,
        "A_MAX": a_total // 3,
        "INACTIVE_TICKETS": d.count(0),
        "T_RANGE": [22, w // 3],
        "ASSUMPTIONS": asdict(upstream.MODEL),
    }


def exact_term(w: int, j: int, top: int, a_max: int, floor: int, t: int) -> Term:
    opened = w - 3 * t
    require(opened >= 0 and floor >= 0 and a_max >= 0, "nonnegative premises")
    k4 = max(0, -(-(j - (top - 2) * opened) // 4))
    contained = min(k4, a_max)
    s4 = max(floor, 448 * contained + 679 * (k4 - contained))
    s3 = 2800 * opened + 20272 * (t - 22) + 154000
    exact = Fraction(route.K20_S1 - route.K20_S2 + s3) - Fraction(4 * s4, 7)
    return t, -(-exact.numerator // exact.denominator), k4, contained, s4, s3


def validate_envelope(
    facts: Mapping[str, Any], cap: int, floor: int, terms: Sequence[Sequence[int]]
) -> None:
    require(type(cap) is int and cap == facts["W"] // 3, "universal triangle range")
    require(type(floor) is int and floor >= 0, "S4 floor premise")
    require([r[0] for r in terms] == list(range(22, cap + 1)), "incomplete envelope")
    for row in terms:
        require(len(row) == 6 and all(type(x) is int for x in row), "term shape/integrality")
        expected = exact_term(
            facts["W"], facts["SUM_C_G_3"], facts["G_MAX"], facts["A_MAX"], floor, row[0]
        )
        for at, message in (
            (2, "K4 ceiling"),
            (3, "A_max contained-K4"),
            (4, "S4 MAX floor"),
            (5, "S3 identity"),
            (1, "Fraction ceiling"),
        ):
            require(row[at] == expected[at], message)


def envelope(facts: Mapping[str, Any], floor: int) -> list[Term]:
    d = tuple(facts["D"])
    terms = cast(list[Term], route.route_b_envelope(d, facts["W"] // 3, floor))
    validate_envelope(facts, facts["W"] // 3, floor, terms)
    return terms


def class_envelope(
    facts: Mapping[str, Record], owners: Sequence[str], j: int, top: int, a_max: int, floor: int
) -> list[Term]:
    require(set(facts) == set(owners) and len(facts) == 39, "class owner completeness")
    require(
        type(j) is int and 0 <= j <= min(f["SUM_C_G_3"] for f in facts.values()),
        "class J lower bound",
    )
    require(
        type(top) is int and max(f["G_MAX"] for f in facts.values()) <= top <= 12,
        "class degree ceiling",
    )
    require(
        type(a_max) is int and a_max == 168 and all(f["A_MAX"] == a_max for f in facts.values()),
        "class A_max",
    )
    require(floor == 112, "class Base S4 floor")
    return [exact_term(784, j, top, a_max, floor, t) for t in range(22, 262)]


def checked_rows(rows: Sequence[tuple[str, int]], expected: Mapping[str, int]) -> dict[str, int]:
    require(len(rows) == len(expected) == len({p for p, _ in rows}), "ledger row count/duplicate")
    require(
        all(type(b) is int for _, b in rows) and dict(rows) == expected, "ledger row identity/bound"
    )
    return dict(rows)


def family_summary(resolved: Mapping[str, int], cursor: Mapping[str, int]) -> Record:
    require(len(resolved) == 4647 and len(cursor) == 197, "family row count")
    require(not resolved.keys() & cursor.keys(), "family ledger overlap")
    require(all(type(b) is int for b in (*resolved.values(), *cursor.values())), "ledger integers")
    rows = dict(resolved) | dict(cursor)
    levels = sorted(set(rows.values()), reverse=True)
    return {
        "MAXIMUM": levels[0],
        "ALL_MAX_OWNERS": sorted(p for p, b in rows.items() if b == levels[0]),
        "NEXT_DISTINCT_BOUND": levels[1],
        "ALL_NEXT_DISTINCT_OWNERS": sorted(p for p, b in rows.items() if b == levels[1]),
        "CURSOR_MAXIMUM": max(cursor.values()),
        "RESOLVED_MAXIMUM": max(resolved.values()),
        "CURSOR_ROWS_SCANNED": len(cursor),
        "RESOLVED_ROWS_SCANNED": len(resolved),
        "TOTAL_PROJECTED_ROWS": len(rows),
    }


def replace_owners(
    cursor: Mapping[str, int], new: Mapping[str, int], owners: Sequence[str]
) -> dict[str, int]:
    require(
        len(cursor) == 197 and set(new) == set(owners) and len(new) == 39,
        "all 39 owner replacements required",
    )
    require(
        set(new) <= cursor.keys() and all(type(b) is int and b < cursor[p] for p, b in new.items()),
        "strict owner tightening",
    )
    return {p: new.get(p, b) for p, b in cursor.items()}


def family_status(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    new: Mapping[str, int],
    owners: Sequence[str],
) -> str:
    strict = (
        set(new) == set(owners)
        and len(new) == 39
        and all(type(b) is int and b < before["MAXIMUM"] for b in new.values())
    )
    return (
        "PROVEN_FAMILY_GAIN"
        if strict and after["MAXIMUM"] < before["MAXIMUM"]
        else "NO_PROVEN_FAMILY_GAIN"
    )


def compute_result(candidate: str = "HEAD", repo: Path = ROOT) -> Record:
    mode = verify_identity(candidate, repo)
    fixed, prior, base = fixed_input(repo)
    source_pins = upstream.r2.source_pins()  # Verify the frozen 22-source evaluator closure only.
    require(source_pins == prior["SOURCE_PINS"], "Base closure pins")
    resolved = checked_rows(
        list(fixed["RESOLVED_ROWS_AFTER"].items()), fixed["RESOLVED_ROWS_AFTER"]
    )
    cursor = checked_rows(
        list(fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"].items()), prior["CURSOR_ROW_BOUNDS_AFTER"]
    )
    before = family_summary(resolved, cursor)
    owners = fixed["ALL_NEW_MAX_OWNERS"]
    require(
        before == fixed["FAMILY_AFTER"]
        and before["MAXIMUM"] == 313391784
        and before["NEXT_DISTINCT_BOUND"] == 313391740
        and before["ALL_MAX_OWNERS"] == owners
        and all(p in cursor for p in owners),
        "fixed complete family/owner frontier",
    )
    covered = coverage(list(cursor), owners, list(resolved))
    inherited = fixed["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]
    require(
        inherited
        == {
            "COUNT": 282,
            "IDS_SHA256": covered["EXCLUDED_IDS_SHA256"],
            "W_RANGE": covered["EXCLUDED_W_RANGE"],
        },
        "inherited exclusion partition",
    )
    facts = {p: theorem(p, owners) for p in owners}
    require((route.K20_S1, route.K20_S2) == (372228640, 63838600), "Base S1/S2")
    weights = route.r30.k4_quartet_weights()
    require(
        weights == route.K4_WEIGHTS == {route.WITH_TRIPLE: 448, route.WITHOUT_TRIPLE: 679},
        "Base K4 local weights",
    )
    per: Record = {}
    for pid in owners:
        f, old = facts[pid], cursor[pid]
        d = tuple(f["D"])
        floor = route.r28.profile_s4_floor(d)
        require(f["INACTIVE_TICKETS"] in (0, 1) and floor == 112, "W784 Base floor applicability")
        require(
            route.r28.coarse_profile_envelope(d).family_upper_bound == old == 313391784,
            "old coarse cursor bound",
        )
        require(
            pid not in base["CERTIFICATES_ADOPTED"]
            and pid not in base["PROFILE_CERTIFICATES"]
            and pid != base["INHERITED_TARGET_BONFERRONI_5"]["PROFILE_ID"],
            "unexpected cursor S5",
        )
        terms = envelope(f, floor)
        new = max(r[1] for r in terms)
        require(new == max(r[1] for r in envelope(f, 0)), "Base floor zero ablation")
        per[pid] = {
            **f,
            "OLD_BOUND": old,
            "NEW_BOUND": new,
            "DELTA": old - new,
            "S4_BASE": floor,
            "S5_USED": False,
            "TERM_COUNT": len(terms),
            "ALL_T_TERMS": terms,
            "ALL_T_TERMS_SHA256": sha(render(terms)),
            "MAXIMUM": new,
            "ALL_ARGMAX": [r for r in terms if r[1] == new],
        }
    j = min(f["SUM_C_G_3"] for f in facts.values())
    shared = class_envelope(facts, owners, j, 12, 168, 112)
    require(
        all(
            all(
                s[0] == p[0] and s[1] >= p[1]
                for s, p in zip(shared, per[pid]["ALL_T_TERMS"], strict=True)
            )
            for pid in owners
        ),
        "class domination at every T",
    )
    shared_max = max(r[1] for r in shared)
    new_bounds = {p: per[p]["NEW_BOUND"] for p in owners}
    after_cursor = replace_owners(cursor, new_bounds, owners)
    require(
        {p: b for p, b in after_cursor.items() if p not in owners}
        == {p: b for p, b in cursor.items() if p not in owners},
        "other 158 cursor bounds",
    )
    after = family_summary(resolved, after_cursor)
    status = family_status(before, after, new_bounds, owners)

    def code_bytes(path: str) -> bytes:
        return (
            (ROOT / path).read_bytes()
            if mode.startswith("INPUT_HEAD")
            else blob(candidate, path, repo)
        )

    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "PATH": INPUT_RESULT,
            "SHA256": INPUT_SHA,
        },
        "UPSTREAM_CURSOR_CERTIFICATE": {
            "HEAD": UPSTREAM_HEAD,
            "TREE": UPSTREAM_TREE,
            "PATH": UPSTREAM_RESULT,
            "SHA256": UPSTREAM_SHA,
        },
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PATH": BASE_RESULT,
            "SHA256": BASE_SHA,
        },
        "SOURCE_SHA256": sha(code_bytes(SOURCE)),
        "TEST_SHA256": sha(code_bytes(TEST)),
        "UPSTREAM_CODE_PINS": CODE_PINS,
        "EVALUATOR_SOURCE_PINS": source_pins,
        "PROOF": __doc__,
        "OWNER_IDS": owners,
        "OWNER_IDS_ORDER_SHA256": ids_digest(owners),
        "CURSOR_COVERAGE": covered,
        "PER_CURSOR": per,
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4_FLOOR", "S3"],
        "TOTAL_TERM_COUNT": sum(r["TERM_COUNT"] for r in per.values()),
        "SHARED_THEOREM": {
            "UNIVERSALITY": "ALL_LEGAL_REALIZATIONS_OF_ALL_39_W784_HISTOGRAMS",
            "W": 784,
            "T_RANGE": [22, 261],
            "TERM_COUNT": len(shared),
            "J_MIN": j,
            "G_MAX_CEILING": 12,
            "A_MAX": 168,
            "BOUND": shared_max,
            "ALL_T_TERMS": shared,
            "ALL_ARGMAX": [r for r in shared if r[1] == shared_max],
            "DOMINATES_EVERY_MEMBER_AT_EVERY_T": True,
            "RELAXATION_ENDPOINT_REALIZABILITY_ASSERTED": False,
        },
        "K4_S4_AMAX_AUTHORITY": {
            "K4_WEIGHTS_REEXECUTED": weights,
            "A_MAX_NUMERATOR": 506,
            "A_MAX": 168,
            "BASE_FLOOR": 112,
            "FLOOR_ZERO_GIVES_SAME_MAXIMA": True,
            "S4_RULE": "MAX(BASE,679*K4-231*MIN(K4,A_MAX)); NEVER ADD",
        },
        "EXACT_ARITHMETIC_AND_ROUNDING": "K4_CEILING; A_MAX_FLOOR; S4_MAX; FRACTION_CEILING",
        "FRACTIONAL_S4_CREDIT_TERMS": sum(
            (4 * t[4]) % 7 != 0 for p in per.values() for t in p["ALL_T_TERMS"]
        ),
        "S5_USED": False,
        "ALL_39_COVERED": True,
        "ALL_39_STRICTLY_TIGHTENED": all(new_bounds[p] < cursor[p] for p in owners),
        "FAMILY_BEFORE": before,
        "FAMILY_AFTER": after,
        "FAMILY_DELTA": before["MAXIMUM"] - after["MAXIMUM"],
        "ALL_NEW_MAX_OWNERS": after["ALL_MAX_OWNERS"],
        "NEXT_DISTINCT_BOUND": after["NEXT_DISTINCT_BOUND"],
        "INCUMBENT": fixed["INCUMBENT"],
        "GAP_TO_INCUMBENT": after["MAXIMUM"] - fixed["INCUMBENT"],
        "CURSOR_ROW_BOUNDS_BEFORE": cursor,
        "CURSOR_ROW_BOUNDS_AFTER": after_cursor,
        "OTHER_CURSOR_ROWS_UNCHANGED": 158,
        "CURSOR_IDS_197_PRESERVED": set(cursor) == set(after_cursor),
        "RESOLVED_ROWS": resolved,
        "RESOLVED_4647_PRESERVED": True,
        "RESOLVED_ROWS_SHA256": sha(upstream.r2.projection(resolved)),
        "INHERITED_EXCLUSION": fixed["INHERITED_EXCLUSION"],
        "INHERITED_CAVEATS_REFERENCE": fixed["INHERITED_CAVEATS_REFERENCE"],
        "UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM": fixed["UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM"],
        "PRIOR_REVIEW_CAVEAT_VERBATIM": fixed["PRIOR_REVIEW_CAVEAT"],
        "UPSTREAM_WORKER_ATTEMPT_HISTORY_VERBATIM": fixed["WORKER_ATTEMPT_HISTORY"],
        "HISTORICAL_CERTIFICATES_RECERTIFIED": False,
        "WORKER_ATTEMPT_HISTORY": [
            {
                "OBSERVED": "system Python lacked numpy for frozen evaluator imports",
                "DISPOSITION": "used repository Python 3.13.8 environment with PYTHONPATH=src",
            },
            {
                "OBSERVED": "Base result absent in checkout",
                "DISPOSITION": "read immutable Git blob at pinned Base HEAD",
            },
            {
                "OBSERVED": "initial focused lint/typecheck found formatting and typing issues",
                "DISPOSITION": "repaired source/tests; checked with explicit Python 3.13",
            },
            {
                "OBSERVED": "independent local-count test initially counted seven-label sets",
                "DISPOSITION": "corrected test to multiply by seven main/special assignments",
            },
        ],
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "FRESH_JUDGE": "ONE_FRESH_FOCUSED_REVIEW_ON_FROZEN_TREE; VERDICT_EXTERNAL_TO_JSON",
        "SOLVER_CALLS": 0,
        "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NONE",
        "PRODUCTION_MUTATION": "NONE",
        "REMAINING_TASK_MODEL": "最強模型(未解數學問題); 強模型(已驗收結果正式接合)",
    }


def validate_payload(payload: object, expected: object) -> None:
    require(render(payload) == render(expected), "result differs from complete recomputation")


def verify_result(candidate: str = "HEAD", repo: Path = ROOT) -> None:
    expected = compute_result(candidate, repo)
    data = (
        (ROOT / RESULT).read_bytes()
        if git("rev-parse", candidate, repo=repo) == INPUT_HEAD
        else blob(candidate, RESULT, repo)
    )
    decode(data)  # Reject duplicate keys before comparing the exact byte representation.
    require(data == render(expected), "stored result differs from complete recomputation")


def main() -> None:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    if args.write_result:
        require(not (ROOT / RESULT).exists(), "result already exists")
        (ROOT / RESULT).write_bytes(render(result))
    if args.verify:
        verify_result()
    print(
        json.dumps(
            {k: result[k] for k in ("TASK_STATUS", "FAMILY_BEFORE", "FAMILY_AFTER", "FAMILY_DELTA")}
        )
    )


if __name__ == "__main__":
    main()
