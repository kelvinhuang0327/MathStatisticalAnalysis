"""Scientific closure of the frozen K20 fiber Slice 1: no strict gain in its 992 cells.

Slice 1 is the frozen manifest of 992 (degree profile, T) cells. Each cell asks whether a
minimum-S2 fiber structure with that triple-degree profile and at least T overlap-graph
triangles exists. This module binds three existing exact authorities into one verified result:

* 990 cells are empty by R30 CP-SAT INFEASIBLE refutations, re-derived from the pinned R30
  result through the hash-pinned overlay;
* 1 cell, 66665555555322000000 at T=266, is empty by the closed-form open-wedge theorem
  (open wedges >= 48 > 33, hence T <= 261);
* 1 cell, the incumbent 55555555555511111100 at T=270, is closed exactly: the graph is forced
  to K12 + (K8 - e), the structure is a pointed STS(13) plus one fixed L side, five
  isomorphism classes remain, and their exact official counts peak at 313,263,888.

The T270 part is re-derived here from the pinned closure result, not trusted: the arithmetic,
the STS(13) automorphism groups and the labeled-count mass check, the five representatives
(rebuilt, validated by the frozen census, recounted by the pinned evaluator) and the
classification of the canonical start portfolio. No solver and no search runs. The RUN1
census ledgers are never read, so their UNKNOWN records cannot count against an exact proof.
Nothing here claims the global K20 optimum, lower-T cells or Slice 2.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import comb, factorial, prod
from pathlib import Path
from subprocess import CalledProcessError
from typing import cast

from lottolab.research import b649_fiber_t266_closed_form_certificate as t266
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_certificate_reuse as reuse
from lottolab.research import b649_k20_fiber_slice1_r30_refutation_overlay as overlay

TASK_ID = "B649_FIBER_SLICE1_PROVEN_NO_STRICT_GAIN_CLOSURE_R1"
SCHEMA_VERSION = 1
RESULT_RELATIVE = (
    "docs/research/matrix-native-results/b649-fiber-slice1-no-strict-gain-closure-r1-result.json"
)
RESULT_SHA256 = "a53eab695a54ccf44aa2b80803ca9aca2367399e8096904159751d71456de27f"
T270_RESULT_RELATIVE = (
    "docs/research/matrix-native-results/b649-fiber-t270-structural-exact-closure-r1-result.json"
)
T270_TASK_ID = "B649_K20_FIBER_INCUMBENT_T270_STRUCTURAL_EXACT_CLOSURE_R1"
T270_STATUS = "PROVED_NO_STRICT_GAIN_WITHIN_DEFINED_PROFILE_T270_CELL"
T270_RESULT_SHA256 = "cd136425601d69c4cf1f437ea11a2c2bd25ff9d295e2cc2f670092aeb20176b8"
T270_SOURCE_COMMIT = "2f2054da69a327a5b14a4f39d4e623b364edf321"
T270_SOURCE_DIRECTORY = "research-archive/B649_K20_FIBER_INCUMBENT_T270_STRUCTURAL_EXACT_CLOSURE_R1"
T270_SCRIPT_SHA256 = "45ee56d3426c363137c74ce76f8762d50e10d180d20220fd994b336c04dfce07"
T270_TEST_SHA256 = "4ac139d0c00d2dc9015de016351b7fe928109fea83506ba913976e6eda2a2894"
INCUMBENT_PROFILE = "55555555555511111100"
INCUMBENT_T = 270
EXACT_CELL_MAX = 313_263_888
START_CLASS = "NONCYCLIC/orbit3"
T266_SOURCE_COMMIT = "55c504908efd39793f639a148520ea4175a4bf38"
T266_MODULE_RELATIVE = "src/lottolab/research/b649_fiber_t266_closed_form_certificate.py"

MANIFEST_CELLS = 992
R30_CELLS = 990
T266_CELL = (t266.TARGET_PROFILE, t266.TARGET_T)
T270_CELL = (INCUMBENT_PROFILE, INCUMBENT_T)

STS_ORDER = 13
STS_BLOCKS = 26
STS_CLASS_NAMES = ("CYCLIC", "NONCYCLIC")
H_TICKETS = 12
L_TICKETS = 8
HEAVY_DEGREE = census.TICKET_CAPACITY + 5
LIGHT_DEGREES = (6, 6, 7, 7, 7, 7, 7, 7)
# The forced L side on tickets 12..19: two disjoint triples, and K8 minus the edge 18-19.
L_TRIPLES: tuple[census.Triple, ...] = ((12, 13, 14), (15, 16, 17))
L_NON_EDGE: census.Pair = (18, 19)

Block = tuple[int, ...]
Blocks = tuple[Block, ...]
Cell = tuple[str, int]


class ClosureError(RuntimeError):
    """A pinned authority, proof step or count differs from the closure contract."""


def _obj(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ClosureError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ClosureError(f"{name} must be a list")
    return cast(list[object], value)


def _int(value: object, name: str) -> int:
    if type(value) is not int:
        raise ClosureError(f"{name} must be an integer")
    return value


def _str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ClosureError(f"{name} must be a string")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ClosureError(message)


# Steiner triple systems on 13 points ---------------------------------------------------------


def third_points(blocks: Blocks) -> dict[tuple[int, int], int]:
    return {(x, y): z for block in blocks for x, y, z in itertools.permutations(block)}


def is_sts13(blocks: Blocks) -> bool:
    """Exactly 26 triples that cover each of the 78 point pairs once."""

    pairs = [p for block in blocks for p in itertools.combinations(sorted(block), 2)]
    return (
        len(blocks) == STS_BLOCKS
        and all(
            len(block) == 3 and len(set(block)) == 3 and all(0 <= x < STS_ORDER for x in block)
            for block in blocks
        )
        and len(pairs) == len(set(pairs)) == comb(STS_ORDER, 2)
    )


def _close(
    image: dict[int, int], source: dict[tuple[int, int], int], target: dict[tuple[int, int], int]
) -> bool:
    """Extend a partial point map along the third-point rule; True iff it is a bijection."""

    changed = True
    while changed:
        changed = False
        for x, y in itertools.permutations(tuple(image), 2):
            z, w = source[(x, y)], target[(image[x], image[y])]
            if z in image:
                if image[z] != w:
                    return False
            else:
                image[z] = w
                changed = True
    return len(image) == STS_ORDER and len(set(image.values())) == STS_ORDER


def isomorphisms(source: Blocks, target: Blocks) -> list[tuple[int, ...]]:
    """Every point bijection f with f(source) == target.

    An isomorphism of Steiner triple systems is fixed by the images of three points that do not
    lie on one block, so all 13*12*11 candidate base images are closed and checked. Three such
    points generate a subsystem with at least 7 points, and a proper subsystem of an STS(13)
    has at most (13 - 1) / 2 = 6, so the closure of a consistent base image is total.
    """

    src, dst = third_points(source), third_points(target)
    wanted = {frozenset(block) for block in target}
    base = (0, 1, next(p for p in range(STS_ORDER) if p not in (0, 1, src[(0, 1)])))
    found: list[tuple[int, ...]] = []
    for a, b, c in itertools.permutations(range(STS_ORDER), 3):
        if c == dst[(a, b)]:
            continue
        image = {base[0]: a, base[1]: b, base[2]: c}
        if (
            _close(image, src, dst)
            and {frozenset(image[p] for p in blk) for blk in source} == wanted
        ):
            found.append(tuple(image[p] for p in range(STS_ORDER)))
    return found


def point_orbits(group: Sequence[tuple[int, ...]]) -> list[list[int]]:
    orbits: list[list[int]] = []
    seen: set[int] = set()
    for point in range(STS_ORDER):
        if point not in seen:
            orbit = sorted({g[point] for g in group})
            seen.update(orbit)
            orbits.append(orbit)
    return orbits


def pasch_count(blocks: Blocks) -> int:
    """Four triples on six points, any two meeting in one point: an isomorphism invariant."""

    sets = [frozenset(block) for block in blocks]
    return sum(
        len(frozenset[int]().union(*quad)) == 6
        and all(len(x & y) == 1 for x, y in itertools.combinations(quad, 2))
        for quad in itertools.combinations(sets, 4)
    )


def fixed_matching_completions() -> int:
    """Labeled STS(13) on 0..12 that contain the six blocks {0, 2i-1, 2i}, counted exactly."""

    full = (1 << STS_ORDER) - 1
    covered = [0] * STS_ORDER

    def cover(x: int, y: int) -> None:
        covered[x] |= 1 << y
        covered[y] |= 1 << x

    def uncover(x: int, y: int) -> None:
        covered[x] &= ~(1 << y)
        covered[y] &= ~(1 << x)

    for i in range(1, STS_ORDER // 2 + 1):
        for x, y in ((0, 2 * i - 1), (0, 2 * i), (2 * i - 1, 2 * i)):
            cover(x, y)

    def count() -> int:
        for v in range(STS_ORDER):
            free = full & ~covered[v] & ~(1 << v)
            if free:
                break
        else:
            return 1
        w = (free & -free).bit_length() - 1
        candidates = free & ~covered[w] & ~(1 << w)
        total = 0
        while candidates:
            u = (candidates & -candidates).bit_length() - 1
            candidates &= candidates - 1
            for x, y in ((v, w), (v, u), (w, u)):
                cover(x, y)
            total += count()
            for x, y in ((v, w), (v, u), (w, u)):
                uncover(x, y)
        return total

    return count()


def labeled_sts13_total() -> tuple[int, int]:
    """(completions of one fixed matching at point 0, labeled STS(13) on 13 points).

    Every labeled STS(13) has exactly one perfect matching of the other 12 points at point 0,
    and relabelling 1..12 moves any matching to any other, so the total is the number of
    matchings, 11!! = 10395, times the completions of one of them.
    """

    completions = fixed_matching_completions()
    return completions, prod(range(1, STS_ORDER - 1, 2)) * completions


# The T270 cell: forced graph and structure ---------------------------------------------------


def structural_arithmetic(profile: census.Profile, cap: int) -> dict[str, object]:
    """Every T >= cap that the degree profile allows, and the only one a structure realizes.

    Edge identity: for an edge uv the open wedges with an arm uv number
    (deg u - 1 - |N(u) & N(v)|) + (deg v - 1 - |N(u) & N(v)|), and an open wedge has two arms,
    so the sum over edges is 2 * open. For u of degree 11 and v of degree <= 7 the u side is
    at least 10 - 6 = 4, which gives 4c <= 2 * open for c = e(H, L). Parity of the degree sum
    of H gives c even, c = 2 forces 10 open wedges, and c = 0 forces K12 + (K8 - e).
    """

    degrees = [census.TICKET_CAPACITY + d for d in profile]
    heavy = [d for d in degrees if d == HEAVY_DEGREE]
    light = sorted(d for d in degrees if d != HEAVY_DEGREE)
    _require(
        len(heavy) == H_TICKETS and tuple(light) == LIGHT_DEGREES,
        "profile is not twelve degree-11 tickets and the pinned L side",
    )
    edges = sum(degrees) // 2
    _require(edges == 3 * census.TRIPLE_LINES + census.PAIR_LINES, "edge count differs")
    wedges = census.wedge_count(profile)
    heavy_sum, light_sum = sum(heavy), sum(light)
    # u-side term of an H-L edge: (deg u - 1) - |N(u) & N(v)| >= (11 - 1) - (deg v - 1)
    hl_term = (HEAVY_DEGREE - 1) - (max(light) - 1)
    _require(hl_term == 4, "the H-L edge term is not at least 4")
    survivors: list[int] = []
    trace: list[dict[str, object]] = []
    for t in range(cap, wedges // 3 + 1):
        open_wedges = wedges - 3 * t
        admitted: list[int] = []
        for c in range(2 * open_wedges // hl_term + 1):
            if (heavy_sum - c) % 2:
                continue
            _require(c in (0, 2), "an H-L edge count outside the proved cases is admissible")
            heavy_edges = (heavy_sum - c) // 2
            if c == 2:
                # one non-adjacent pair x, y inside H, and each other H ticket is a centre
                _require(heavy_edges == comb(H_TICKETS, 2) - 1, "c = 2 leaves one H non-edge")
                forced = H_TICKETS - 2
                _require(forced > open_wedges, "c = 2 is not excluded by the open-wedge count")
                continue
            _require(heavy_edges == comb(H_TICKETS, 2), "c = 0 makes H complete")
            missing = comb(L_TICKETS, 2) - light_sum // 2
            _require(missing == 1, "L is not K8 minus one edge")
            triangles = comb(H_TICKETS, 3) + comb(L_TICKETS, 3) - (L_TICKETS - 2) * missing
            if triangles == t:
                admitted.append(c)
        if admitted:
            survivors.append(t)
        trace.append({"T": t, "OPEN_WEDGES": open_wedges, "ADMITTED_C": admitted})
    _require(survivors == [cap], "T above the cap is realizable or the cap is not")
    return {
        "DEGREES": "11^12, 7^6, 6^2",
        "EDGES": edges,
        "W": wedges,
        "H_DEGREE_SUM": heavy_sum,
        "L_DEGREE_SUM": light_sum,
        "HL_EDGE_TERM_LOWER_BOUND": hl_term,
        "TRIANGLES_OF_K12_PLUS_K8_MINUS_E": comb(H_TICKETS, 3)
        + comb(L_TICKETS, 3)
        - (L_TICKETS - 2),
        "T_TRACE": trace,
        "REALIZABLE_T": survivors,
        "CELL_AT_LEAST_CAP_EQUALS_CELL_AT_CAP": True,
    }


def light_pairs(triples: Sequence[census.Triple], non_edge: census.Pair) -> tuple[census.Pair, ...]:
    """Every K8 edge on tickets 12..19 except the triple edges and the one non-edge."""

    taken = {p for t in triples for p in itertools.combinations(t, 2)}
    return tuple(
        p
        for p in itertools.combinations(range(H_TICKETS, census.TICKET_COUNT), 2)
        if p not in taken and p != non_edge
    )


def pointed_structure(blocks: Blocks, point: int) -> census.Structure:
    """The T270-cell structure of the pointed STS(13) (blocks, point).

    The 12 other points become H tickets 0..11 in increasing order. Blocks through ``point``
    become the 6 H pair lines and the other 20 blocks the H triple lines; L is the forced side.

    Conversely every cell structure has this form. A line's tickets are pairwise adjacent and
    c = 0, so each line lies in H or in L. An H ticket is on 5 triple and 1 pair line, so the 6
    H pair lines are a perfect matching, and a new point on each of them makes the H lines
    cover all 78 pairs of 13 points once: an STS(13). The 2 L triple lines hold the six
    degree-7 tickets once each, and the 21 L pair lines are the other edges of K8 - e. H and L
    differ in degree, so the structure's class is its pointed STS(13) class: one per orbit of
    Aut(STS) on points. The official count is invariant under relabelling numbers and tickets.
    """

    ticket = {p: i for i, p in enumerate(q for q in range(STS_ORDER) if q != point)}
    triples: list[census.Triple] = list(L_TRIPLES)
    pairs: list[census.Pair] = list(light_pairs(L_TRIPLES, L_NON_EDGE))
    for block in blocks:
        rest = sorted(ticket[x] for x in block if x != point)
        if len(rest) == 2:
            pairs.append((rest[0], rest[1]))
        else:
            triples.append((rest[0], rest[1], rest[2]))
    return census.Structure(tuple(sorted(triples)), tuple(sorted(pairs)))


@dataclass(frozen=True, slots=True)
class StsClass:
    name: str
    blocks: Blocks
    automorphisms: int
    orbits: tuple[tuple[int, ...], ...]
    pasch: int


def sts_class(name: str, blocks: Blocks) -> StsClass:
    _require(is_sts13(blocks), f"{name} is not an STS(13)")
    group = isomorphisms(blocks, blocks)
    _require(tuple(range(STS_ORDER)) in group, f"{name}: the identity is not an automorphism")
    orbits = tuple(tuple(orbit) for orbit in point_orbits(group))
    return StsClass(name, blocks, len(group), orbits, pasch_count(blocks))


def classification_completeness(classes: Sequence[StsClass], labeled: int) -> dict[str, int]:
    """No third STS(13) class: the labeled class sizes 13!/|Aut| already sum to the total.

    Distinct Pasch counts make the classes distinct, so their labeled members are disjoint.
    """

    _require(
        len({c.pasch for c in classes}) == len(classes), "Pasch counts do not separate classes"
    )
    _require(
        all(factorial(STS_ORDER) % c.automorphisms == 0 for c in classes),
        "an automorphism group order does not divide 13!",
    )
    masses = {c.name: factorial(STS_ORDER) // c.automorphisms for c in classes}
    _require(sum(masses.values()) == labeled, "the labeled STS(13) total leaves room for a class")
    return masses


def sts_classification(
    representatives: Mapping[str, Blocks],
) -> tuple[dict[str, StsClass], dict[str, object]]:
    _require(tuple(representatives) == STS_CLASS_NAMES, "representatives are not the two classes")
    classes = {name: sts_class(name, blocks) for name, blocks in representatives.items()}
    cyclic, noncyclic = (classes[name] for name in STS_CLASS_NAMES)
    _require(
        not isomorphisms(cyclic.blocks, noncyclic.blocks), "the representatives are isomorphic"
    )
    completions, labeled = labeled_sts13_total()
    masses = classification_completeness(list(classes.values()), labeled)
    return classes, {
        "CLASSES": {
            c.name: {
                "AUTOMORPHISM_GROUP_ORDER": c.automorphisms,
                "PASCH_COUNT": c.pasch,
                "POINT_ORBITS": [list(o) for o in c.orbits],
                "LABELED_MASS": masses[c.name],
            }
            for c in classes.values()
        },
        "CROSS_ISOMORPHISMS": 0,
        "FIXED_MATCHING_COMPLETIONS": completions,
        "PERFECT_MATCHINGS_OF_12": prod(range(1, STS_ORDER - 1, 2)),
        "LABELED_STS13_TOTAL": labeled,
        "COMPLETE": True,
    }


def classify(structure: census.Structure, classes: Mapping[str, StsClass]) -> str:
    """The class STS/orbit<least point> of a structure in the T270 cell, or fail closed.

    The structure must have the incumbent profile with tickets in profile order, at least 270
    triangles, no line across H and L and the forced L side. Its H lines plus a point 12 on
    the H pair lines must be an STS(13).
    """

    profile = census.decode_profile(INCUMBENT_PROFILE)
    _require(
        census.realization(profile, structure).triangles >= INCUMBENT_T, "structure is below T270"
    )
    lines = (*structure.triples, *structure.pairs)
    _require(all(len({v < H_TICKETS for v in line}) == 1 for line in lines), "a line joins H and L")
    light_triples = tuple(t for t in structure.triples if t[0] >= H_TICKETS)
    _require(
        sorted(v for t in light_triples for v in t) == list(range(H_TICKETS, H_TICKETS + 6)),
        "the L triples do not partition the six degree-7 tickets",
    )
    _require(
        tuple(p for p in structure.pairs if p[0] >= H_TICKETS)
        == light_pairs(light_triples, L_NON_EDGE),
        "the L pair lines are not K8 minus the triple edges and 18-19",
    )
    blocks = tuple(t for t in structure.triples if t[2] < H_TICKETS) + tuple(
        (a, b, H_TICKETS) for a, b in structure.pairs if b < H_TICKETS
    )
    _require(is_sts13(blocks), "the H lines do not complete to an STS(13)")
    for sts in classes.values():
        maps = isomorphisms(blocks, sts.blocks)
        if maps:
            image = maps[0][H_TICKETS]
            return f"{sts.name}/orbit{next(o for o in sts.orbits if image in o)[0]}"
    raise ClosureError("the completed STS(13) is in no representative class")


def representatives(
    classes: Mapping[str, StsClass], evaluate: census.Evaluator
) -> list[dict[str, object]]:
    """One rebuilt, validated and exactly counted portfolio per pointed STS(13) class."""

    profile = census.decode_profile(INCUMBENT_PROFILE)
    rows: list[dict[str, object]] = []
    for sts in classes.values():
        for orbit in sts.orbits:
            class_id = f"{sts.name}/orbit{orbit[0]}"
            structure = pointed_structure(sts.blocks, orbit[0])
            real = census.realization(profile, structure)
            _require(
                real.triangles == INCUMBENT_T
                and real.open_wedges == census.wedge_count(profile) - 3 * INCUMBENT_T,
                f"{class_id} is not a T270 structure",
            )
            _require(classify(structure, classes) == class_id, f"{class_id} misclassifies")
            tickets = census.portfolio(structure)
            rows.append(
                {
                    "CLASS_ID": class_id,
                    "STS_CLASS": sts.name,
                    "DELETED_POINT_ORBIT": list(orbit),
                    "GRAPH_TRIANGLES": real.triangles,
                    "OPEN_WEDGES": real.open_wedges,
                    "PORTFOLIO_SHA256": census.compact_tickets_sha256(tickets),
                    "OFFICIAL_EXACT_COUNT": evaluate(tickets),
                }
            )
    return rows


# The pinned T270 closure: authority, archive and independent re-derivation ------------------


def load_t270(root: Path) -> tuple[dict[str, object], bytes]:
    raw = (root / T270_RESULT_RELATIVE).read_bytes()
    _require(census.sha256_bytes(raw) == T270_RESULT_SHA256, "T270 closure differs from its pin")
    data = _obj(json.loads(raw), "T270 result")
    domain = _obj(data["EXACT_CELL_DOMAIN"], "EXACT_CELL_DOMAIN")
    dependencies = _obj(data["DEPENDENCY_SHA256"], "DEPENDENCY_SHA256")
    proof = _obj(data["STRUCTURAL_COMPLETENESS_PROOF"], "STRUCTURAL_COMPLETENESS_PROOF")
    expected: list[tuple[object, object]] = [
        (data.get("TASK_ID"), T270_TASK_ID),
        (data.get("TASK_STATUS"), T270_STATUS),
        (proof.get("STATUS"), "PROVED"),
        (data.get("EXACT_CELL_MAX"), EXACT_CELL_MAX),
        (data.get("STRICT_GAIN"), "NO"),
        (data.get("UNPROVED_ITEMS"), []),
        (domain.get("TRIPLE_DEGREE_PROFILE"), INCUMBENT_PROFILE),
        (domain.get("OVERLAP_GRAPH_TRIANGLES_T_ALL_TRIANGLES"), INCUMBENT_T),
        (domain.get("MAX_PAIRWISE_OVERLAP"), 1),
        (dependencies.get("SCRIPT"), T270_SCRIPT_SHA256),
        (dependencies.get("EVALUATOR"), census.EVALUATOR_SHA256),
        (dependencies.get("BASELINE_PORTFOLIO"), census.START_NORMALIZED_SHA256),
        (dependencies.get("BASELINE_RESULT_FILE"), census.START_FILE_SHA256),
    ]
    _require(
        all(type(seen) is type(value) and seen == value for seen, value in expected),
        "T270 result does not state the pinned closure",
    )
    return data, raw


def t270_archive(root: Path, raw: bytes) -> dict[str, object]:
    """The in-tree copy has the bytes of the closure archived at 2f2054da."""

    pins = {
        "result.json": T270_RESULT_SHA256,
        "t270_structural_closure.py": T270_SCRIPT_SHA256,
        "test_t270_structural_closure.py": T270_TEST_SHA256,
    }
    for name, sha in pins.items():
        try:
            data = census.git_show(root, T270_SOURCE_COMMIT, f"{T270_SOURCE_DIRECTORY}/{name}")
        except CalledProcessError as error:
            raise ClosureError(f"T270 archive commit lacks {name}") from error
        _require(census.sha256_bytes(data) == sha, f"archived T270 {name} differs from its pin")
        _require(name != "result.json" or data == raw, "in-tree T270 copy differs from archive")
    return {
        "COMMIT": T270_SOURCE_COMMIT,
        "DIRECTORY": T270_SOURCE_DIRECTORY,
        "FILES_SHA256": pins,
        "IN_TREE_COPY": T270_RESULT_RELATIVE,
        "IN_TREE_COPY_BYTE_IDENTICAL": True,
    }


def recorded_representatives(data: Mapping[str, object]) -> dict[str, Blocks]:
    status = _obj(data["STS13_CLASSIFICATION_STATUS"], "STS13_CLASSIFICATION_STATUS")
    entries = _obj(status["GENERATOR_REPRESENTATIVES"], "GENERATOR_REPRESENTATIVES")
    return {
        name: tuple(
            tuple(_int(x, "point") for x in _list(block, "block"))
            for block in _list(json.loads(_str(_obj(entries[name], name)["BLOCKS"], name)), name)
        )
        for name in STS_CLASS_NAMES
    }


def recorded_classes(data: Mapping[str, object]) -> dict[str, tuple[str, tuple[int, ...], int]]:
    accounting = _obj(data["EXACT_SCORE_ACCOUNTING"], "EXACT_SCORE_ACCOUNTING")
    table: dict[str, tuple[str, tuple[int, ...], int]] = {}
    for raw in _list(accounting["ISOMORPHISM_CLASSES"], "ISOMORPHISM_CLASSES"):
        entry = _obj(raw, "class")
        table[_str(entry["CLASS_ID"], "CLASS_ID")] = (
            _str(entry["STS_CLASS"], "STS_CLASS"),
            tuple(_int(p, "point") for p in _list(entry["DELETED_POINT_ORBIT"], "orbit")),
            _int(entry["FRESH_CANONICAL_COUNT"], "count"),
        )
    return table


def t270_closure(root: Path, evaluate: census.Evaluator) -> dict[str, object]:
    """Re-derive the T270 cell maximum from the pinned closure's two STS(13) representatives."""

    data, raw = load_t270(root)
    archive = t270_archive(root, raw)
    arithmetic = structural_arithmetic(census.decode_profile(INCUMBENT_PROFILE), INCUMBENT_T)
    classes, classification = sts_classification(recorded_representatives(data))
    rows = representatives(classes, evaluate)
    derived: dict[str, tuple[str, tuple[int, ...], int]] = {}
    for row in rows:
        orbit = tuple(_int(p, "point") for p in _list(row["DELETED_POINT_ORBIT"], "orbit"))
        derived[_str(row["CLASS_ID"], "class")] = (
            _str(row["STS_CLASS"], "STS class"),
            orbit,
            _int(row["OFFICIAL_EXACT_COUNT"], "count"),
        )
    _require(derived == recorded_classes(data), "re-derived classes or counts differ from T270")
    status = _obj(data["STS13_CLASSIFICATION_STATUS"], "STS13_CLASSIFICATION_STATUS")
    entries = _obj(status["GENERATOR_REPRESENTATIVES"], "GENERATOR_REPRESENTATIVES")
    _require(
        all(
            _obj(entries[c.name], c.name).get("AUTOMORPHISM_GROUP_ORDER") == c.automorphisms
            for c in classes.values()
        ),
        "re-derived automorphism group orders differ from T270",
    )
    start = census.verify_start(root, evaluate)
    tickets, _ = census.start_portfolio(root)
    start_profile, start_structure = census.structure_from_tickets(tickets)
    start_class = classify(start_structure, classes)
    _require(
        census.profile_id(start_profile) == INCUMBENT_PROFILE
        and start_class == START_CLASS
        and derived[start_class][2] == start["COUNT"],
        "the canonical start is not a NONCYCLIC/orbit3 member of the cell at its count",
    )
    counts = [count for _, _, count in derived.values()]
    proof = _obj(data["STRUCTURAL_COMPLETENESS_PROOF"], "STRUCTURAL_COMPLETENESS_PROOF")
    return {
        "CELL": list(T270_CELL),
        "SOURCE_TASK_ID": T270_TASK_ID,
        "SOURCE_STATUS": T270_STATUS,
        "RESULT_SHA256": T270_RESULT_SHA256,
        "ARCHIVE": archive,
        "STRUCTURAL_PROOF_STEPS": sorted(_obj(proof["PROOF"], "PROOF")),
        "STRUCTURAL_ARITHMETIC": arithmetic,
        "STS13_CLASSIFICATION": classification,
        "REPRESENTATIVES": rows,
        "ISOMORPHISM_CLASS_COUNT": len(rows),
        "RECORDED_CLASS_TABLE_MATCHES": True,
        "START": {**start, "CLASS_ID": start_class},
        "EXACT_CELL_MAX": max(counts),
        "MAX_ATTAINED_BY": sorted(k for k, (_, _, c) in derived.items() if c == max(counts)),
    }


# Binding the 992 frozen Slice-1 cells ------------------------------------------------------


def partition(manifest: census.Manifest, loaded: overlay.Overlay) -> dict[str, object]:
    """990 R30 imports, the T266 theorem cell and the T270 cell: disjoint, and all 992."""

    cells = [overlay.cell_of(row) for row in manifest.rows]
    _require(len(set(cells)) == len(cells) == MANIFEST_CELLS, "manifest is not 992 cells")
    imported = set(loaded.imports)
    _require(len(imported) == R30_CELLS and imported <= set(cells), "R30 imports are not 990 cells")
    _require(set(cells) - imported == {T266_CELL, T270_CELL}, "the two other cells differ")
    _require(loaded.r30_realized == frozenset({T270_CELL}), "R30 realized another cell")
    return {
        "MANIFEST_CELLS": len(cells),
        "R30_CP_SAT_INFEASIBLE": len(imported),
        "T266_CLOSED_FORM_THEOREM": 1,
        "T270_EXACT_CLOSURE": 1,
        "DISJOINT_AND_COVERING": True,
        "ONE_T_PER_CELL": True,
        "T266_MANIFEST_INDEX": cells.index(T266_CELL),
        "T270_MANIFEST_INDEX": cells.index(T270_CELL),
    }


def r30_certificates(
    manifest: census.Manifest, loaded: overlay.Overlay, root: Path
) -> dict[str, object]:
    """Re-derive the overlay from the pinned R30 result, then re-read each imported attempt."""

    overlay.verify_overlay(loaded, manifest, root)
    result, _ = overlay.r30_result(root)
    attempts = overlay.attempts_of(result)
    rows = {overlay.cell_of(row): row for row in manifest.rows}
    for cell, imported in loaded.imports.items():
        attempt = attempts[_int(imported[4], "attempt")]
        wedges = census.wedge_count(rows[cell].profile)
        _require(
            attempt.get("STATUS") == census.INFEASIBLE
            and attempt.get("CERTIFICATE_KIND") == overlay.CERTIFICATE
            and attempt.get("ROUTE") == overlay.ROUTE_A
            and attempt.get("PROFILE_IDS") == [cell[0]]
            and attempt.get("WEDGE_COUNT") == wedges
            and attempt.get("REFUTED_GRAPH_TRIANGLE_COUNT") == cell[1]
            and attempt.get("OPEN_WEDGE_CEILING_REFUTED") == wedges - 3 * cell[1]
            and overlay.line_sha256(attempt) == imported[6],
            f"{cell}: its R30 attempt is not a single-profile INFEASIBLE refutation of the cell",
        )
    return {
        "OVERLAY_RELATIVE": overlay.OVERLAY_RELATIVE,
        "OVERLAY_SHA256": loaded.sha256,
        "IMPORTS_SHA256": _str(loaded.data["IMPORTS_SHA256"], "IMPORTS_SHA256"),
        "R30_TASK_HEAD": overlay.R30_TASK_HEAD,
        "R30_RESULT_SHA256": overlay.R30_RESULT_SHA256,
        "CERTIFICATE": overlay.CERTIFICATE,
        "CERTIFIED_CELLS": len(loaded.imports),
        "OVERLAY_REDERIVED_FROM_R30_RESULT": True,
        "ATTEMPTS_RECHECKED": len(loaded.imports),
        "PER_CELL_MODEL_EQUIVALENCE_SHA256": reuse.EQUIVALENCE_SHA256,
        "PER_CELL_MODEL_EQUIVALENCE": "PINNED_DIGEST_NOT_RERUN",
    }


def t266_certificate(manifest: census.Manifest, root: Path) -> dict[str, object]:
    """The closed-form theorem at its source commit certifies exactly the T266 cell."""

    try:
        source = census.git_show(root, T266_SOURCE_COMMIT, T266_MODULE_RELATIVE)
    except CalledProcessError as error:
        raise ClosureError("T266 source commit is not in the object store") from error
    module = Path(str(t266.__file__)).read_bytes()
    _require(source == module, "T266 theorem module differs from its source commit")
    _require(reuse.EQUIVALENCE_SHA256 == t266.EQUIVALENCE_SHA256, "model-equivalence pins disagree")
    certified: dict[Cell, Mapping[str, object]] = {}
    for row in manifest.rows:
        body = t266.certificate(manifest, row, reuse.EQUIVALENCE_SHA256, root)
        if body is not None:
            certified[overlay.cell_of(row)] = body
    _require(list(certified) == [T266_CELL], "the theorem does not certify exactly one cell")
    body = certified[T266_CELL]
    arithmetic = _obj(body["ARITHMETIC"], "ARITHMETIC")
    wedges = _int(arithmetic["W"], "W")
    open_min = _int(arithmetic["OPEN_WEDGES_MIN"], "OPEN_WEDGES_MIN")
    t_max = _int(arithmetic["T_MAX"], "T_MAX")
    ceiling = wedges - 3 * t266.TARGET_T
    _require(
        ceiling < open_min and t_max < t266.TARGET_T and body["CEILING"] == ceiling,
        "the theorem bound does not exclude the cell",
    )
    return {
        "CELL": list(T266_CELL),
        "CERTIFICATE": t266.CERTIFICATE,
        "PROOF_IDENTITY": t266.PROOF_IDENTITY,
        "PROOF_SHA256": t266.PROOF_SHA256,
        "SOURCE_COMMIT": T266_SOURCE_COMMIT,
        "MODULE_SHA256": census.sha256_bytes(module),
        "W": wedges,
        "OPEN_WEDGE_CEILING_AT_T": ceiling,
        "OPEN_WEDGES_MIN": open_min,
        "T_MAX": t_max,
        "CENSUS_CHASE_REQUEST_SHA256": body["CENSUS_CHASE_REQUEST_SHA256"],
    }


def disposition(cell_max: int) -> str:
    return "STRICT_GAIN_FOUND" if census.is_gain(cell_max) else "PROVED_NO_STRICT_GAIN"


def closure(root: Path, evaluate: census.Evaluator) -> dict[str, object]:
    manifest = census.load_manifest(root / census.MANIFEST_RELATIVE, census.MANIFEST_SHA256)
    _require(manifest.threshold == census.STRICT_GAIN_THRESHOLD, "gain threshold differs")
    loaded = overlay.load_overlay(root / overlay.OVERLAY_RELATIVE, overlay.OVERLAY_SHA256)
    cells = partition(manifest, loaded)
    r30 = r30_certificates(manifest, loaded, root)
    theorem = t266_certificate(manifest, root)
    exact = t270_closure(root, evaluate)
    cell_max = _int(exact["EXACT_CELL_MAX"], "EXACT_CELL_MAX")
    verdict = disposition(cell_max)
    proved = verdict == "PROVED_NO_STRICT_GAIN"
    return {
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "TASK_ID": TASK_ID,
        "SLICE1_SCIENTIFIC_NO_STRICT_GAIN": "PROVED" if proved else "REFUTED",
        "SLICE1_SCIENTIFIC_DISPOSITION": verdict,
        "FROZEN_SLICE1_NO_STRICT_GAIN": "PASS" if proved else "FAIL",
        "MAX_OFFICIAL_EXACT_COUNT": cell_max,
        "START_COUNT": census.START_COUNT,
        "STRICT_GAIN_THRESHOLD": census.STRICT_GAIN_THRESHOLD,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "SCOPE": {
            "CLAIM": "no fiber structure in the 992 frozen Slice-1 cells has an official exact "
            "count of at least the strict-gain threshold",
            "LOWER_T_CELLS": "NOT_CLAIMED",
            "SLICE2": "NOT_CLAIMED",
            "OFF_FIBER": "NOT_CLAIMED",
            "GLOBAL_MIN_S2_FAMILY": "NOT_CLAIMED",
        },
        "RUN1_EXECUTION_TERMINAL": "NOT_CLAIMED",
        "RUN1_EVIDENCE": {
            "CENSUS_RUN1_LEDGERS_READ": False,
            "RUN1_RECORDS_USED": False,
            "NOTE": "a scientific closure; RUN1 execution state is neither read nor changed",
        },
        "MANIFEST": {
            "RELATIVE": census.MANIFEST_RELATIVE,
            "SHA256": manifest.sha256,
            "PROFILES_SHA256": _obj(manifest.data["SLICE1"], "SLICE1")["PROFILES_SHA256"],
        },
        "PARTITION": cells,
        "R30_CERTIFICATES": r30,
        "T266_CERTIFICATE": theorem,
        "T270_EXACT_CLOSURE": exact,
        "EVALUATOR": census.verify_evaluator(root),
        "EVIDENCE_BOUNDARY": {
            "CP_SAT_SOLVES": 0,
            "MODELS_BUILT": 0,
            "SEARCH": "NONE",
            "PORTFOLIOS_COUNTED": "FIVE_CLASS_REPRESENTATIVES_AND_THE_CANONICAL_START",
        },
    }


def render(result: Mapping[str, object]) -> bytes:
    return (json.dumps(result, indent=1, sort_keys=True) + "\n").encode()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--write", action="store_true", help="create the result file if absent")
    args = parser.parse_args(argv)
    root = census.repo_root()
    data = render(closure(root, census.official_evaluator()))
    path = root / RESULT_RELATIVE
    if args.write and not path.exists():
        overlay.write_new(path, data)
    _require(path.read_bytes() == data, "the committed result differs from its re-derivation")
    _require(census.sha256_bytes(data) == RESULT_SHA256, "the result differs from its pin")
    print(json.dumps({"RESULT": RESULT_RELATIVE, "SHA256": census.sha256_bytes(data)}))


if __name__ == "__main__":
    main()
