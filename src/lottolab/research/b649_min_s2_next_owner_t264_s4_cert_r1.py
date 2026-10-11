"""Quartet-incidence certificate for 66665555555421000000 at T=264 only.

All quantifiers concern legal minimum-S2 fibers: 22 linear triple-label
supports and 27 pair-label supports on twenty six-label tickets. Their simple
overlap graph G has g_v=6+d_v. T counts ALL graph triangles, including the 22
core supports. The pinned R30 attempt 2781 refutes OW<=38, hence T>=265,
because OW=W-3T. Its exact-support model represents every legal fiber: it
selects the triple/pair supports, fixes ticket loads and d, forbids repeated
pairs, and lower-bounds each open-wedge indicator. The extra nonedge bound
is valid by |N(a) intersect N(b)|>=g_a+g_b-18. No solver is run here.

Definitions. K counts K4 quartets; J=sum_v C(g_v,3) counts centered three-
stars, without an induced requirement. For each open wedge (v; x,y), choose
a third neighbor of v; R=sum_v OW_v*(g_v-2) counts these choices with their
missing leaf pair. C counts induced claws. A counts K4s containing a core
triple; D1 counts diamonds containing a core triple; P1 counts a core triple
plus an outside vertex with exactly one neighbor in that triple.

A quartet contains at most one core triple, since two would share a pair.
The exhaustive local table (K,J,R,C; weight before core correction) is:
 K4:     (1,4,0,0; 679)
 diamond:(0,2,2,0; 112)
 paw:    (0,1,2,0;   0)
 claw:   (0,1,3,1;   0)
 all others: (0,0,0,0; 0).
Containing a core triple lowers K4's weight by 231 and diamond's by 112.
The official any-prize rule is hits(main)+hits(special)>=3. The pinned R2
incidence DP checks all 64 labeled graphs and all 32 possible core-marked
graphs, with tickets padded to six labels in the official 49-label space.
This exhausts local types, including projections of triples that extend
outside the quartet. It is not a random-graph or fiber-realization search.
Summing this exact table proves, for EVERY legal fiber,
 S4 = 231K + 112J - 56R - 231A - 112D1 + 56C.

In the stated cell, W=833, J=2366, g_max=12 and OW=41. Thus R<=10*41=410.
Every nontriangle triple in N(v) contains a nonedge and is counted at least
once by R. The remaining triples are counted four times over K4s, giving
4K>=J-R>=1956 and K>=489 (the reused R30 K4 inequality).

Sum external neighbors over the 22 core supports. A support's vertices
have g_v-2 neighbors outside it. Summing by memberships gives
B=sum_v d_v*(g_v-2)=604. An outside vertex with three, two or one neighbors
contributes to A, D1 or P1, respectively; the quartet/support association
is unique. Hence B=3A+2D1+P1, with C,P1>=0 and integer A,D1>=0.
If A<=200, 231A+112D1<=56B+63A<=46424. Otherwise A=201, so D1=0 and
231A+112D1<=46431. The latter is attained in the capacity RELAXATION by
(A,D1,P1)=(201,0,1); no realization is asserted. Consequently
 S4>=231*489+112*2366-56*410-46431=308560.

Only the T=264 envelope term receives this floor. Every lower-T term keeps
the pinned Route-B floor. R2's at-most-seven winners and Bonferroni excess
give credit floor(4*S4/7); the reused R20 and R32 formulas are checked against
exact rational arithmetic. The maximum over 22..264 is the profile bound.
No ledger, theorem, incumbent or combined result is updated, and no family
bound is certified. Reproduction requires the pinned local Git objects.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

from lottolab.domain import lottery_rules as rules

from . import b649_k20_min_s2_higher_order_closure_r2 as r2
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32

TASK_ID = "B649_MIN_S2_NEXT_OWNER_T264_S4_INCIDENCE_CERT_R1"
BASE_HEAD = "cc493492701d19ad433bba967f14c2f27f844c3e"
BASE_TREE = "82e3f6ca1660282906a55a9f32302c826bb97fe1"
LEDGER_HEAD = "2f70925698cb28758fdf29a62bc5e91028c03a81"
LEDGER_TREE = "216bd91dee0afa58f8186a38aec52b1d47781ef8"
LEDGER_SHA256 = "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3"
LEDGER_FILE = "b649-k20-min-s2-split-cap-current-owner-chase-r1-result.json"
R30_HEAD = "6ba4811304ec6528738a0c0b38969901b264d241"
R30_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
TARGET_PROFILE = "66665555555421000000"
PROFILE = tuple(map(int, TARGET_PROFILE))
T = 264
ATTEMPT_INDEX = 2781
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIRECTORY = "docs/research/matrix-native-results"
RESULT_PATH = ROOT / RESULT_DIRECTORY / "b649-min-s2-next-owner-t264-s4-cert-r1-result.json"
PAIRS = tuple(combinations(range(4), 2))
CORES = tuple(combinations(range(4), 3))
integer, object_row, rows = r32.integer, r32.object_row, r32.rows


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def cap_identity(proof: Mapping[str, object]) -> None:
    """Reject wrong profiles, statuses, routes, thresholds and attempt identities."""
    require(
        r32.r28.r26.accepted_cap(proof, (PROFILE,), T) == T,
        "R30 does not certify cap264",
    )
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": ATTEMPT_INDEX,
        "WEDGE_COUNT": r32.k4_premises(PROFILE)[0],
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": 39,
        "OPEN_WEDGE_INDICATOR_COUNT": 20 * comb(19, 2),
        "ROUTE": r32.CAP_SOURCE_ROUTE,
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
    }
    require(all(proof.get(k) == v for k, v in expected.items()), "R30 source identity mismatch")


def authority() -> tuple[dict[str, object], dict[str, str]]:
    """Pin inputs and executed helpers without a solver or full ledger replay."""
    for head, tree in ((BASE_HEAD, BASE_TREE), (LEDGER_HEAD, LEDGER_TREE)):
        require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "tree mismatch")
    for older, newer in ((R30_HEAD, LEDGER_HEAD), (LEDGER_HEAD, BASE_HEAD)):
        subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], cwd=ROOT, check=True)
    manifest: dict[str, str] = {}
    inputs: dict[str, dict[str, object]] = {}
    for head, name, digest in (
        (LEDGER_HEAD, LEDGER_FILE, LEDGER_SHA256),
        (R30_HEAD, r32.r30.RESULT_FILENAME, R30_SHA256),
    ):
        path = f"{RESULT_DIRECTORY}/{name}"
        raw = git("show", f"{head}:{path}")
        require(sha256(raw) == digest, "pinned result digest mismatch")
        require(raw == git("show", f"{BASE_HEAD}:{path}"), "base changed pinned result")
        inputs[name] = object_row(json.loads(raw))
        manifest[f"{head}:{path}"] = digest
    ledger = inputs[LEDGER_FILE]
    require(
        not any(
            object_row(c).get("PROFILE_ID") == TARGET_PROFILE for c in rows(ledger["CERTIFICATES"])
        ),
        "split chase already replaced target; resolve its new authority",
    )
    # R30 delegates exact-support construction to R28/R26. Pin their ACTUAL
    # source at R30 as well as every helper we execute at the ledger commit.
    for module in (r32.r30, r32.r28, r32.r28.r26):
        require(module.__file__ is not None, "missing model source")
        path = Path(str(module.__file__)).resolve().relative_to(ROOT).as_posix()
        raw = git("show", f"{R30_HEAD}:{path}")
        require((ROOT / path).read_bytes() == raw, f"R30 source changed: {path}")
        manifest[f"{R30_HEAD}:{path}"] = sha256(raw)
    for module in (r2, r32, r32.r30, r32.r28, r32.r28.r26, r32.r31, r32.r28.r26.batch, rules):
        require(module.__file__ is not None, "missing reused source")
        path = Path(str(module.__file__)).resolve().relative_to(ROOT).as_posix()
        raw = git("show", f"{LEDGER_HEAD}:{path}")
        require((ROOT / path).read_bytes() == raw, f"reused source changed: {path}")
        manifest[f"{LEDGER_HEAD}:{path}"] = sha256(raw)
    # R32 imports these pure mathematical helpers directly.
    for name in (
        "b649_k20_min_s2_realizable_core_class_bound_r4.py",
        "b649_k20_min_s2_resolved_above_cursor_owner_chase_r20.py",
    ):
        path = f"src/lottolab/research/{name}"
        raw = git("show", f"{LEDGER_HEAD}:{path}")
        require((ROOT / path).read_bytes() == raw, f"reused source changed: {path}")
        manifest[f"{LEDGER_HEAD}:{path}"] = sha256(raw)
    proof = object_row(rows(inputs[r32.r30.RESULT_FILENAME]["GROUP_ATTEMPTS"])[ATTEMPT_INDEX])
    cap_identity(proof)
    return proof, dict(sorted(manifest.items()))


@dataclass(frozen=True)
class Incidence:
    k: int
    j: int
    r: int
    a: int
    d1: int
    c: int
    p1: int

    @property
    def s4(self) -> int:
        return (
            231 * self.k + 112 * self.j - 56 * self.r - 231 * self.a - 112 * self.d1 + 56 * self.c
        )


def local_pattern(mask: int, core: tuple[int, ...] | None) -> tuple[Incidence, tuple[int, ...]]:
    """One four-ticket pattern only; no general graph or support framework."""
    if type(mask) is not int or not 0 <= mask < 64 or (core is not None and core not in CORES):
        raise ValueError("invalid quartet pattern")
    edges = {pair for bit, pair in enumerate(PAIRS) if mask & (1 << bit)}
    core_edges = set(combinations(core, 2)) if core is not None else set[tuple[int, int]]()
    if not core_edges <= edges:
        raise ValueError("core triple lacks a shadow edge")
    neighbors = [{b if a == v else a for a, b in edges if v in (a, b)} for v in range(4)]
    j = sum(comb(len(n), 3) for n in neighbors)
    r = sum(
        sum(tuple(sorted(pair)) not in edges for pair in combinations(n, 2))
        for n in neighbors
        if len(n) == 3
    )
    e = len(edges)
    counts = Incidence(
        int(e == 6),
        j,
        r,
        int(e == 6 and core is not None),
        int(e == 5 and core is not None),
        int(sorted(map(len, neighbors)) == [1, 1, 1, 3]),
        int(e == 4 and core is not None),
    )
    incidence = [0] * 16
    if core is not None:
        incidence[sum(1 << v for v in core)] = 1
    for a, b in edges - core_edges:
        incidence[(1 << a) | (1 << b)] = 1
    for v in range(4):
        load = sum(count for label_mask, count in enumerate(incidence) if label_mask & (1 << v))
        incidence[1 << v] += 6 - load
    incidence[0] = 49 - sum(incidence)
    return counts, tuple(incidence)


def verify_local_identity() -> dict[str, object]:
    """Exhaust all local patterns against pinned official semantics and R2's DP."""
    prize_rule = rules.BIG_LOTTO_RULE_CONTRACT.prize_rule
    require(prize_rule is not None, "missing official prize rule")
    for hits in range(7):
        for special in (False, True):
            if hits == 6 and special:
                continue  # Main and special are disjoint; this signature is impossible.
            winner = isinstance(
                rules.resolve_big_lotto_prize_tier(hits, special), rules.BigLottoPrizeTier
            )
            require(winner == (hits + int(special) >= 3), "official any-prize semantics changed")
    checked, weights = 0, set[int]()
    for mask in range(64):
        for core in (None, *CORES):
            core_mask = sum(1 << PAIRS.index(pair) for pair in combinations(core, 2)) if core else 0
            if mask & core_mask != core_mask:
                continue
            counts, profile = local_pattern(mask, core)
            actual = r2.compressed_four_ticket_intersection_count(
                profile,
                pool_size=49,
                draw_size=6,
                outright_matches=3,
            )
            expected = (
                448
                if counts.a
                else 679
                if counts.k
                else 112
                if mask.bit_count() == 5 and core is None
                else 0
            )
            require(actual == expected == counts.s4, "quartet identity or official weight failed")
            weights.add(actual)
            checked += 1
    require(checked == 96 and weights == {0, 112, 448, 679}, "incomplete local proof")
    return {
        "PATTERNS_CHECKED": checked,
        "WEIGHTS": sorted(weights),
        "OFFICIAL_RULE_SHA256": prize_rule.source_sha256 if prize_rule else None,
    }


def maximum_loss(capacity: int) -> tuple[int, int, int, int]:
    """Exact integer capacity relaxation; for fixed A, the largest D1 is worst."""
    if type(capacity) is not int or capacity < 0:
        raise ValueError("capacity must be a nonnegative integer")
    candidates = (
        (
            231 * a + 112 * ((capacity - 3 * a) // 2),
            a,
            (capacity - 3 * a) // 2,
            (capacity - 3 * a) % 2,
        )
        for a in range(capacity // 3 + 1)
    )
    return max(candidates)


def target_inequalities(profile: tuple[int, ...] = PROFILE, triangles: int = T) -> dict[str, int]:
    if profile != PROFILE or type(triangles) is not int or triangles != T:
        raise ValueError("certificate scope is target profile at T264 only")
    w, j, top = r32.k4_premises(profile)
    ow = w - 3 * triangles
    r_max = (top - 2) * ow
    k_min = r32.r30.k4_lower_bound([6 + d for d in profile], ow)
    require(4 * (k_min - 1) < j - r_max <= 4 * k_min, "K4 ceiling is not exact")
    b = r32.outside_degree_sum(profile)
    loss, a, d1, p1 = maximum_loss(b)
    require((w, j, b) == (833, 2366, 604), "target profile identities changed")
    require(loss == 231 * (b // 3) and 3 * a + 2 * d1 + p1 == b, "loss proof failed")
    s4 = 231 * k_min + 112 * j - 56 * r_max - loss
    return {
        "W": w,
        "J": j,
        "OPEN_WEDGES": ow,
        "R_MAX": r_max,
        "K_MIN": k_min,
        "B": b,
        "LOSS_MAX": loss,
        "LOSS_A": a,
        "LOSS_D1": d1,
        "LOSS_P1": p1,
        "S4_LOWER_BOUND": s4,
    }


def verify_target_counts(counts: Incidence) -> int:
    """Check load-bearing inequalities on a count vector, not its realizability."""
    q = target_inequalities()
    require(
        all(type(v) is int and v >= 0 for v in asdict(counts).values()), "negative/noninteger count"
    )
    require(counts.j == q["J"], "J identity failed")
    require(counts.r <= q["R_MAX"], "R upper bound failed")
    require(counts.k >= q["K_MIN"], "K lower bound failed")
    require(3 * counts.a + 2 * counts.d1 + counts.p1 == q["B"], "core capacity identity failed")
    require(counts.a <= counts.k, "A exceeds all K4s")
    require(231 * counts.a + 112 * counts.d1 <= q["LOSS_MAX"], "loss inequality failed")
    require(counts.s4 >= q["S4_LOWER_BOUND"], "S4 lower bound failed")
    return counts.s4


def target_rows(value: object) -> Iterator[Mapping[str, object]]:
    """A bounded profile lookup in result blobs, without reconstructing any ledger."""
    if isinstance(value, dict):
        row = object_row(cast(object, value))
        if row.get("PROFILE_ID", row.get("TARGET_PROFILE")) == TARGET_PROFILE or (
            row.get("PROFILE_IDS") == [TARGET_PROFILE] and row.get("STATUS") == "INFEASIBLE"
        ):
            yield row
        for child in row.values():
            yield from target_rows(child)
    elif isinstance(value, list):
        for child in rows(cast(object, value)):
            yield from target_rows(child)


def reject_superseding_rows(value: object, bound: int) -> None:
    for row in target_rows(value):
        for key in (
            "CURRENT_BOUND",
            "BOUND",
            "ALL_T_MAX_BOUND",
            "PROFILE_BOUND_AFTER",
            "CERTIFIED_OWNER_BOUND",
            "NEW_BOUND",
        ):
            if type(row.get(key)) is int:
                require(integer(row[key]) > bound, "existing target certificate already supersedes")
        for key in ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", "TRIANGLE_CAP", "CERTIFIED_T_CAP"):
            if type(row.get(key)) is int:
                require(integer(row[key]) >= T, "existing target has a stricter cap authority")


def supersession_check(bound: int) -> dict[str, str]:
    """Audit immutable base results containing this profile; no family replay."""
    manifest: dict[str, str] = {}
    for entry in git("ls-tree", "-r", BASE_HEAD, "--", RESULT_DIRECTORY).decode().splitlines():
        metadata, path = entry.split("\t")
        mode, kind, oid = metadata.split()
        if "min-s2" not in path or not path.endswith(".json"):
            continue
        require(mode == "100644" and kind == "blob", "unsafe result inventory entry")
        raw = git("cat-file", "blob", oid)
        if TARGET_PROFILE.encode() in raw:
            reject_superseding_rows(json.loads(raw), bound)
            manifest[path] = sha256(raw)
    require(bool(manifest), "target result audit found no authority")
    return manifest


def profile_envelope() -> tuple[list[r32.Term], list[r32.Term], dict[str, int]]:
    q = target_inequalities()
    base = r32.r28.profile_s4_floor(PROFILE)
    before = r32.route_b_envelope(PROFILE, T, base)
    require([term[0] for term in before] == list(range(22, T + 1)), "envelope has a gap")
    after = list(before)
    t, _bound, k, a, old_s4, s3 = before[-1]
    s4 = max(old_s4, q["S4_LOWER_BOUND"])
    checked_s3, bound = r32.bound_from_cap(PROFILE, t, s4)
    require(checked_s3 == s3, "S3 identity failed")
    after[-1] = t, bound, k, a, s4, s3
    for term in after:
        exact = r32.K20_S1 - r32.K20_S2 + term[5] - Fraction(4 * term[4], 7)
        require(0 <= term[1] - exact < 1, "Bonferroni integer rounding failed")
    require(after[:-1] == before[:-1], "lower-T terms changed")
    return before, after, q


def compute_result() -> dict[str, object]:
    proof, provenance = authority()
    local = verify_local_identity()
    before, after, q = profile_envelope()
    best = max(after, key=lambda term: (term[1], term[0]))
    audit = supersession_check(best[1])
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "FORMAL_S4_CERTIFICATE",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TARGET_PROFILE": TARGET_PROFILE,
        "CERTIFICATE_SCOPE": "TARGET_PROFILE_T264_ONLY",
        "CERTIFIED_T_CAP": T,
        "PROOF": __doc__,
        "R30_CAP264_IDENTITY": "PASS",
        "R30_ATTEMPT": proof,
        "AUTHORITY_PROVENANCE": provenance,
        "EXISTING_CERTIFICATE_AUDIT": audit,
        "QUARTET_IDENTITY": "PASS",
        "LOCAL_QUARTET_CHECK": local,
        "INCIDENCE_INEQUALITIES": "PASS",
        "INCIDENCE_CONSTRAINTS": q,
        "T264_S4_LOWER_BOUND": q["S4_LOWER_BOUND"],
        "T264_UPPER_BOUND": after[-1][1],
        "FULL_PROFILE_UPPER_BOUND": best[1],
        "FULL_PROFILE_ARGMAX_T": best[0],
        "PROFILE_BOUND_BEFORE": max(term[1] for term in before),
        "T264_TERM_BEFORE": list(before[-1]),
        "T264_TERM_AFTER": list(after[-1]),
        "TERM_COLUMNS": ["T", "UPPER_BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4_FLOOR", "S3"],
        "LOWER_T_SCOPE": [22, T - 1],
        "LOWER_T_TERM_COUNT": len(before) - 1,
        "LOWER_T_TERMS_SHA256": sha256(json.dumps(before[:-1], separators=(",", ":")).encode()),
        "LOWER_T_MAX_TERM": list(max(before[:-1], key=lambda term: (term[1], term[0]))),
        "LOWER_T_TERMS_UNCHANGED": True,
        "FAMILY_BOUND_AUTHORITY_PRODUCED": False,
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SEARCH_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
        "NEXT_ACTION": "END_WITH_FORMAL_S4_CERTIFICATE",
    }


def render(result: Mapping[str, object]) -> bytes:
    return (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()


def main() -> None:
    payload = render(compute_result())
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing exact result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    print(json.dumps({"RESULT": str(RESULT_PATH), "SHA256": sha256(payload)}))


if __name__ == "__main__":
    main()
