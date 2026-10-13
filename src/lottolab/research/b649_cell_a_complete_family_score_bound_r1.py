"""CELL_A exact-count upper bound: every CELL_A solution is a pointed STS(13) and one U side.

Scope. One statement for one cell. Every solution of the frozen CELL_A model (profile
55555555555511111100 at T = 270) maps, by a ticket permutation and a bijection of the 49 numbers,
onto one of the 26 portfolios of the 12+8 family (82e88ada): one of two STS(13) designs with one
of its 13 points deleted, plus a fixed eight-ticket U side. The official exact count is invariant
under such maps, so the 26 donor counts bound CELL_A: every CELL_A solution counts at most
313,263,888, and none reaches the strict-gain threshold 313,263,889. Nothing is solved and nothing
is scored here. The 26 counts are REUSED EVIDENCE from the donor result. Other cells, profiles and
targets, and the global K20 optimum (UNKNOWN), are outside the theorem.

Premises. The four constraint families of the frozen model that the rigidity certificate
(24ff183c, sha db91bb06) uses, with d = (5^12, 1^6, 0^2): tickets 0..11 (H) have d = 5, tickets
12..17 have d = 1 and tickets 18, 19 have d = 0.

* ticket v lies on exactly d_v triple lines and 6 - d_v pair lines;
* two tickets share at most one line, and e(a, b) is the number of lines holding both;
* every centre c and pair {a, b} has a 0/1 indicator o >= e(c,a) + e(c,b) - e(a,b) - 1;
* the indicators sum to at most W - 3T = 816 - 810 = 6.

The model's cut on non-adjacent pairs, the engine's no-goods and its lex-leader rows only remove
solutions. None of them is a premise. From these premises alone the rigidity certificate proves
that the overlap graph is K12 + (K8 - e), with e = {18, 19}, and that no edge crosses H and U. Its
proof is reused, not repeated.

Proof.

* 1. Split. A line is a clique of the overlap graph and no edge crosses H and U, so every line lies
  inside H or inside U. The 49 numbers split into 20 + 6 H lines and 2 + 21 U lines.
* 2. H side. A ticket of H lies on five triple lines and one pair line, all inside H. The six pair
  lines form a perfect matching F2, and G[H] = K12 puts every pair of H on exactly one line.
  Extension: add oo (labelled 12) and {a, b, oo} for ab in F2. Every pair of the 13 points then
  lies in exactly one of 26 blocks, so this is an STS(13). Inverse: in any STS(13) D, a point p
  lies on (13 - 1) / 2 = 6 blocks. Deleting p leaves the 20 blocks avoiding p and the six pairs
  {a, b} with {a, b, p} in D. These six pairs are a perfect matching of the other 12 points, which
  each lie on five triples and one pair, with every pair covered once. Deleting oo from the
  extension returns F3 and F2 exactly. Extending the deletion of p returns D with p renamed oo.
  ``extend_h`` and ``deletion`` check both directions on every input.
* 3. U side. Tickets 12..17 carry one triple line each, 18 and 19 none, and 6 / 3 = 2 U triples
  exist. So the U triples are two disjoint triples on exactly 12..17. G[U] = K8 - {18, 19}, and each
  edge lies on exactly one line. So the 21 pair lines are the 27 - 6 edges of K8 - e outside the two
  triangles, and the triples determine them. There are C(6, 3) / 2 = 10 unordered partitions.
  Mapping the sorted first triple onto 12, 13, 14, the second onto 15, 16, 17 and fixing 18, 19
  preserves K8 - e and carries triples to triples, so it maps every U side onto the donor U side
  (numbers 27..49). The U side therefore has one incidence class. ``u_partitions`` replays all ten.
* 4. Merge. H and U share no ticket and no line. The two ticket maps therefore form one ticket
  permutation pi, and L -> pi(L) on lines is one bijection sigma of the 49 numbers: ticket v holds
  n iff pi(v) holds sigma(n). The pinned evaluator (blob 3d053b2d) counts outcomes (D, s), s not
  in D. Such an outcome wins when some ticket t has |t & D| >= 3, or |t & D| = 2 and s in t. Both
  conditions depend only on |t & D| and on whether s is in t. Sigma preserves both and permutes the
  outcomes, and ticket order never enters. So the exact count is invariant: count(S) =
  count(donor).
* 5. Classification (EXTERNAL, not re-proved here). Heinlein and Östergård, Enumerating Steiner
  triple systems (2023), DOI 10.1002/jcd.21906, Introduction: STS(13) has two isomorphism classes.
  The donor CYCLIC and NONCYCLIC designs are valid STS(13) with Pasch counts 13 and 8, and a
  complete isomorphism search finds none between them. So they represent the two classes. An
  isomorphism phi from the extension onto a donor design sends oo to some p. Restricted to H, phi
  maps the H side onto the deletion of p. The 2 x 13 pointed constructions therefore cover every
  CELL_A H side. ``cover`` builds phi, pi and sigma and checks them on complete supports. The
  automorphism groups (orders 39 and 6) have point orbits 13 and 6, 3, 3, 1. The frozen engine's
  exact canonical form (03b5691f) independently separates the 26 constructions into exactly these
  five classes, C1..C5.
* 6. Counts (REUSED EVIDENCE). These are the 26 CANDIDATE_COUNTS rows of the donor result (blob
  73920c95 at 82e88ada). Each row's PORTFOLIO_SHA256 is reproduced from the in-memory deletion, so
  each count belongs to exactly that portfolio. The counts are constant on classes: C1 313,263,867,
  C2 313,263,888, C3 313,263,881, C4 313,263,888, C5 313,263,881. Caveat: the result records no
  scorer hash. The evaluator blob 3d053b2d is the blob at the evaluator's path in the donor commit
  tree, which the census also pins as EVALUATOR_BLOB. That identity is an inference from the
  commit tree, not an attestation by the original run.
* 7. Conclusion. Every CELL_A solution has count <= 313,263,888 < 313,263,889. All 26 pointed
  constructions satisfy the four premises, so in the original structural domain C2 and C4 attain
  the bound. The donor's sealed winner NONCYCLIC/5, recounted fresh and by seven-sets, is in C4.
  Exclusion rows may remove every attaining structure but cannot raise the bound.
"""

from __future__ import annotations

import ast
import json
import subprocess
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations, permutations
from pathlib import Path
from typing import cast

from lottolab.research import b649_cell_a_overlap_rigidity_certificate as rigidity
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_two_open_cells_targeted_solver as engine

TASK_ID = "B649_CELL_A_COMPLETE_FAMILY_SCORE_BOUND_R1"
BASE_COMMIT = "24ff183c68ac02ea497044921207913a16ec09bd"
PROFILE_ID = rigidity.PROFILE_ID
TARGET_T = rigidity.TARGET_T
PROFILE = census.decode_profile(PROFILE_ID)
RIGIDITY_CERTIFICATE_SHA256 = "db91bb0689e978de16e33776fe975515c899c31396107b5908daed35d07d6c96"
UPPER_BOUND = 313_263_888
STRICT_GAIN_THRESHOLD = UPPER_BOUND + 1
VERDICT = "CELL_A_EXACT_COUNT_AT_MOST_313263888"

POINTS = 13
OO = 12
H = tuple(range(12))
POSITIVE_U = tuple(range(12, 18))
ZERO_U = (18, 19)
U = (*POSITIVE_U, *ZERO_U)
H_SET, U_SET = frozenset(H), frozenset(U)
DONOR_U_TRIPLES = ((12, 13, 14), (15, 16, 17))
DESIGN_NAMES = ("CYCLIC", "NONCYCLIC")

type Block = tuple[int, int, int]
type Design = tuple[Block, ...]
type Pair = tuple[int, int]
type Permutation = tuple[int, ...]
type ScoreRow = tuple[str, int, str, int]
type Reader = Callable[[str, str], bytes]


class BoundError(ValueError):
    """An input lies outside CELL_A, a pin differs, or a proof step does not hold."""


@dataclass(frozen=True, slots=True)
class SourcePin:
    role: str
    commit: str
    path: str
    blob: str


_RESEARCH = "src/lottolab/research/"
SOURCES = (
    SourcePin(
        "RIGIDITY_CERTIFICATE",
        "24ff183c68ac02ea497044921207913a16ec09bd",
        _RESEARCH + "b649_cell_a_overlap_rigidity_certificate.py",
        "d3b06e36f6dca849c56574100aa5bcc3711f2463",
    ),
    SourcePin(
        "FROZEN_ENGINE",
        "03b5691fac02c3a125c91cf4120b6219c3143b5e",
        _RESEARCH + "b649_k20_two_open_cells_targeted_solver.py",
        "1334605792bf6b46ceeed7b2806ba593b7548841",
    ),
    SourcePin(
        "FROZEN_CENSUS",
        "03b5691fac02c3a125c91cf4120b6219c3143b5e",
        _RESEARCH + "b649_k20_fiber_near_top_s3_census.py",
        "c660faec6d7c916057df0c924c930460aca5697e",
    ),
    SourcePin(
        "CONSTRUCTOR",
        "82e88ada111bf6d0999ac9c0c167a160a6ae5df8",
        _RESEARCH + "b649_k20_overlap_block_repartition_12_8_exhaustive_r1.py",
        "b5d9dd41481762bad815e14119c6e7c39ce1d8e3",
    ),
    SourcePin(
        "DONOR_RESULT",
        "82e88ada111bf6d0999ac9c0c167a160a6ae5df8",
        "docs/research/matrix-native-results/"
        "b649-k20-overlap-block-repartition-12-8-exhaustive-r1-result.json",
        "73920c95b918f74771e9a4f003f61a3959760c4b",
    ),
    SourcePin(
        "EVALUATOR",
        "82e88ada111bf6d0999ac9c0c167a160a6ae5df8",
        _RESEARCH + "b649_official_any_prize_exact.py",
        "3d053b2d9bc2182fc00b22889e837be5d0ba10aa",
    ),
    SourcePin(
        "STS_AUTOMORPHISM_HELPER",
        "7b573db44f56c49e2a0bbb7c002f092e5839d62b",
        _RESEARCH + "b649_k20_11_9_single_bridge_sts13_family_exact_r1.py",
        "1d9c60e154996484fdd6a24f81a73189cf3da901",
    ),
)

EXTERNAL_CLASSIFICATION = {
    "STATEMENT": "STS(13) has exactly two isomorphism classes",
    "SOURCE": "Heinlein and Östergård, Enumerating Steiner triple systems (2023)",
    "DOI": "10.1002/jcd.21906",
    "LOCATION": "Introduction",
    "STATUS": "EXTERNAL_PUBLISHED_RESULT_NOT_REPROVED_HERE",
}

# Both designs verbatim from STS13_DESIGNS of the helper (7b573db), pinned there as ab9438ef and
# copied by it from build_sts13_classes() of the constructor (82e88ada).
STS13_DESIGNS_SHA256 = "ab9438ef501f32f186490c7ff9adf388f7672a55e7d013bde0ae0ea1bd03acca"
STS13_DESIGNS: dict[str, Design] = {
    "CYCLIC": (
        (0, 1, 4), (0, 2, 7), (0, 3, 12), (0, 5, 11), (0, 6, 8), (0, 9, 10), (1, 2, 5),
        (1, 3, 8), (1, 6, 12), (1, 7, 9), (1, 10, 11), (2, 3, 6), (2, 4, 9), (2, 8, 10),
        (2, 11, 12), (3, 4, 7), (3, 5, 10), (3, 9, 11), (4, 5, 8), (4, 6, 11), (4, 10, 12),
        (5, 6, 9), (5, 7, 12), (6, 7, 10), (7, 8, 11), (8, 9, 12),
    ),
    "NONCYCLIC": (
        (0, 1, 7), (0, 2, 4), (0, 3, 12), (0, 5, 11), (0, 6, 8), (0, 9, 10), (1, 2, 5),
        (1, 3, 8), (1, 4, 9), (1, 6, 12), (1, 10, 11), (2, 3, 6), (2, 7, 9), (2, 8, 10),
        (2, 11, 12), (3, 4, 7), (3, 5, 10), (3, 9, 11), (4, 5, 8), (4, 6, 11), (4, 10, 12),
        (5, 6, 9), (5, 7, 12), (6, 7, 10), (7, 8, 11), (8, 9, 12),
    ),
}  # fmt: skip
# FIXED_EIGHT_TICKETS of the constructor (82e88ada) verbatim: the donor U side, numbers 27..49.
FIXED_EIGHT_TICKETS: census.Tickets = (
    (27, 29, 30, 31, 32, 33),
    (27, 34, 35, 36, 37, 38),
    (27, 39, 40, 41, 42, 43),
    (28, 29, 34, 39, 44, 45),
    (28, 30, 35, 40, 46, 47),
    (28, 31, 36, 41, 48, 49),
    (32, 37, 42, 44, 46, 48),
    (33, 38, 43, 45, 47, 49),
)

# REUSED EVIDENCE: the donor result's CANDIDATE_COUNTS rows. Entry p of a design is its deleted
# point p: (PORTFOLIO_SHA256, OFFICIAL_ANY_PRIZE_OUTCOME_COUNT). Nothing here recomputes a count.
DONOR_ROWS_SHA256 = "7da2e87cca5d8bab4a782aa78c98550e88f96ffd41e8e8d14fe09d60369398f1"
_DONOR_COUNTS: dict[str, tuple[tuple[str, int], ...]] = {
    "CYCLIC": (
        ("c0657150a652fcf0ec7ad0fb024e88f5b839ad6dc42150e96726bdb2ca997024", 313_263_867),
        ("15db820aac71f11005717431926f1599e1b6b14e578ad8c5f402aa6c76e9bbd9", 313_263_867),
        ("67edce28c8a45e16f9e972e59b68d9888f752f3356f350890a6d9bdd997c5acb", 313_263_867),
        ("b4c3b19f47fdccf47bc5b7f36221b63eacda73a467cbdcfd049ab50319f31f9c", 313_263_867),
        ("47b63210d5d85258f192458925e34dd7bec651edf9efeb92276e618841976a96", 313_263_867),
        ("833208dcac60af84f4925e584182e411bb44deb0827a9d0c4c8d4e977f944693", 313_263_867),
        ("f9661a21f54b69a774877fc0a8adccc15c90e4087fd33deac29712b501ab4100", 313_263_867),
        ("93ee7c29df9790291eb74c73d026c4143ee3f6b60b1678e51ea929a47b8c2525", 313_263_867),
        ("60784e844917e8ea991e52be45c32c63d01bc35e7d695104489840dc54b6f5db", 313_263_867),
        ("137f451a440dda18b3af25cd1a10f02ad092ccd5a11d45e9185ec9ed902a64cc", 313_263_867),
        ("956ed0f80b7c54542424da76d64099f652a3a8e93e3cc11b6535ef6210c5c327", 313_263_867),
        ("133948994135e1dcd8c35270ac9ff2ee2987a3f056b1718c008299fb9398c7b8", 313_263_867),
        ("c0657150a652fcf0ec7ad0fb024e88f5b839ad6dc42150e96726bdb2ca997024", 313_263_867),
    ),
    "NONCYCLIC": (
        ("6a537ea56c2741e1208dbbb4abf1064bc74508f2d356712920d348d11e3a4a24", 313_263_888),
        ("dd313824121b901b07e797119a48875b97b06eafb17d0be33e0f37c3ea8fa230", 313_263_888),
        ("58524d611a3bce7b9c408889aee77695c6085a2afa0623192329d691463a71c3", 313_263_881),
        ("8055e98e52f56d54ce0932cb985951c28b64d1e4c883934100207de8902f0c8b", 313_263_888),
        ("b1c1574090a061436728b94d8c5ba3881d8bfacc9f734482b6ff6e5ed23a3a84", 313_263_888),
        ("10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b", 313_263_888),
        ("434ccd42bae0968d3601d3a4318326e4eb7bd8a019cf52bf7747ea14df497a4e", 313_263_881),
        ("7d73802ab5915ed42723eaf4a0a913f1100e0c4e035a9e1fc4b62145345927fd", 313_263_881),
        ("15cb12b820dfb50025fbe814019592ccbfdc3b1a651a77122827b92905c42a0b", 313_263_888),
        ("dfe579d6ab8efb0d07c0b0ead41f8e50e10043dd6403194cca7a8695da45b62d", 313_263_881),
        ("952ac381e5500bf734bc3eb68e7c3aba147fb380a29d5efdbbd4f255e5e039cd", 313_263_888),
        ("c2afdd2f5856be202a2009dd12ae858f4c100d7bab42ed2ace6892bc64f24426", 313_263_888),
        ("a797104dda09aea658cc98b106bc862df21536f939c0895af2525c53e0e4f2ab", 313_263_888),
    ),
}
DONOR_ROWS: tuple[ScoreRow, ...] = tuple(
    (name, point, sha, count)
    for name, entries in _DONOR_COUNTS.items()
    for point, (sha, count) in enumerate(entries)
)
DONOR_SEAL = {
    "TASK_STATUS": "COMPLETE",
    "SEAL_PARITY": "PASS",
    "CANDIDATES_TOTAL": 26,
    "CANONICAL_CANDIDATE_EVALUATIONS": 26,
    "BEST_COUNT": UPPER_BOUND,
    "BEST_STS_CLASS": "NONCYCLIC",
    "BEST_DELETED_POINT": 5,
    "FRESH_CANONICAL_RECOUNT": UPPER_BOUND,
    "INDEPENDENT_7SET_RECOUNT": UPPER_BOUND,
}

# The five pointed classes: one automorphism orbit of deleted points each.
CLASS_TABLE: tuple[tuple[str, str, tuple[int, ...]], ...] = (
    ("C1", "CYCLIC", tuple(range(POINTS))),
    ("C2", "NONCYCLIC", (0, 1, 4, 8, 11, 12)),
    ("C3", "NONCYCLIC", (2, 7, 9)),
    ("C4", "NONCYCLIC", (3, 5, 10)),
    ("C5", "NONCYCLIC", (6,)),
)
REUSED_CLASS_COUNTS = {
    "C1": 313_263_867,
    "C2": 313_263_888,
    "C3": 313_263_881,
    "C4": 313_263_888,
    "C5": 313_263_881,
}


def _json_sha256(value: object) -> str:
    """Compact JSON without key sorting: the donors' convention for designs and portfolios."""

    return census.sha256_bytes(json.dumps(value, separators=(",", ":")).encode())


def rows_sha256(rows: Sequence[ScoreRow]) -> str:
    return census.sha256_bytes(census.canonical_json([list(row) for row in rows]).encode())


def check_scope(profile_id: str, t: int) -> None:
    if (profile_id, t) != (PROFILE_ID, TARGET_T):
        raise BoundError(
            f"this bound covers only CELL_A {PROFILE_ID} at T = {TARGET_T}, "
            f"not {profile_id} at T = {t}"
        )


# STS(13): validity, isomorphism, automorphisms --------------------------------------------


def is_sts13(blocks: Sequence[Block]) -> bool:
    if len(blocks) != 26 or len(set(blocks)) != 26:
        return False
    if any(
        len(b) != 3 or tuple(sorted(set(b))) != b or not 0 <= b[0] < b[2] < POINTS for b in blocks
    ):
        return False
    covered = Counter(p for b in blocks for p in combinations(b, 2))
    return set(covered) == set(combinations(range(POINTS), 2)) and set(covered.values()) == {1}


def _third(design: Design) -> dict[Pair, int]:
    table: dict[Pair, int] = {}
    for block in design:
        for a, b in permutations(block, 2):
            table[(a, b)] = next(v for v in block if v not in (a, b))
    return table


def _image(phi: Permutation, block: Block) -> Block:
    a, b, c = sorted(phi[v] for v in block)
    return a, b, c


def _close(
    source: Mapping[Pair, int], target: Mapping[Pair, int], seed: Mapping[int, int]
) -> Permutation | None:
    """Extend ``seed`` by third points: phi(third(a, b)) = third(phi(a), phi(b)), or None."""

    mapping = dict(seed)
    if len(set(mapping.values())) != len(mapping):
        return None
    changed = True
    while changed:
        changed = False
        for a, b in combinations(sorted(mapping), 2):
            x, y = source[(a, b)], target[(mapping[a], mapping[b])]
            if x in mapping:
                if mapping[x] != y:
                    return None
            elif y in mapping.values():
                return None
            else:
                mapping[x] = y
                changed = True
    if len(mapping) != POINTS:
        raise BoundError("a non-collinear triple did not generate the STS(13)")
    return tuple(mapping[v] for v in range(POINTS))


def sts_isomorphisms(
    source: Design, target: Design, *, first: bool = False
) -> tuple[Permutation, ...]:
    """Every point bijection carrying the blocks of ``source`` onto those of ``target``.

    Three non-collinear points generate an STS(13). Their closure is a subsystem with at least 7
    points, and a proper subsystem of an STS(13) has at most (13 - 1) / 2 = 6. So an isomorphism is
    fixed by the images of one such triple, and every candidate image triple is tried. A closed
    map is kept only when it carries the block set onto the block set.
    """

    if not (is_sts13(source) and is_sts13(target)):
        raise BoundError("isomorphisms need two valid STS(13)")
    s_third, t_third = _third(source), _third(target)
    blocks = frozenset(target)
    x, y = 0, 1
    z = next(v for v in range(POINTS) if v not in (x, y, s_third[(x, y)]))
    found: list[Permutation] = []
    for xi, yi in permutations(range(POINTS), 2):
        for zi in range(POINTS):
            if zi in (xi, yi, t_third[(xi, yi)]):
                continue
            phi = _close(s_third, t_third, {x: xi, y: yi, z: zi})
            if phi is not None and frozenset(_image(phi, b) for b in source) == blocks:
                if first:
                    return (phi,)
                found.append(phi)
    return tuple(sorted(found))


def pasch_count(design: Design) -> int:
    return sum(
        1
        for quad in combinations(design, 4)
        if set(Counter(v for b in quad for v in b).values()) == {2}
        and len({v for b in quad for v in b}) == 6
    )


@cache
def automorphisms(name: str) -> tuple[Permutation, ...]:
    """Aut of a donor design, checked to contain the identity and be closed under composition."""

    group = sts_isomorphisms(STS13_DESIGNS[name], STS13_DESIGNS[name])
    members = set(group)
    if tuple(range(POINTS)) not in members or any(
        tuple(g[h[v]] for v in range(POINTS)) not in members for g in group for h in group
    ):
        raise BoundError(f"Aut({name}) is not a group")
    return group


@cache
def point_orbits(name: str) -> tuple[tuple[int, ...], ...]:
    group = automorphisms(name)
    orbits = {tuple(sorted({g[p] for g in group})) for p in range(POINTS)}
    return tuple(sorted(orbits, key=lambda orbit: (-len(orbit), orbit)))


# Step 2: H extension and its inverse ------------------------------------------------------


def deletion(design: Design, point: int) -> tuple[tuple[int, ...], Design, tuple[Pair, ...]]:
    """The other 12 points, the 20 blocks avoiding ``point`` and the matching it leaves.

    Fails closed unless the 12 points each lie on five triples and one pair and every pair of them
    is covered once.
    """

    if not is_sts13(design) or not 0 <= point < POINTS:
        raise BoundError("deletion needs a valid STS(13) and one of its points")
    remaining = tuple(v for v in range(POINTS) if v != point)
    avoiding = tuple(sorted(b for b in design if point not in b))
    through = tuple(
        sorted(cast(Pair, tuple(v for v in b if v != point)) for b in design if point in b)
    )
    on_triples = Counter(v for b in avoiding for v in b)
    covered = Counter(p for line in (*avoiding, *through) for p in combinations(line, 2))
    if (
        len(avoiding) != 20
        or sorted(v for p in through for v in p) != list(remaining)
        or any(on_triples[v] != 5 for v in remaining)
        or set(covered) != set(combinations(remaining, 2))
        or set(covered.values()) != {1}
    ):
        raise BoundError(f"deleting {point} does not leave F3 and a perfect matching F2")
    return remaining, avoiding, through


def extend_h(structure: census.Structure) -> Design:
    """F3 on H plus {a, b, oo} for ab in F2, checked as an STS(13) and against its inverse."""

    triples = tuple(t for t in structure.triples if set(t) <= H_SET)
    matching = tuple(p for p in structure.pairs if set(p) <= H_SET)
    if len(triples) != 20 or sorted(v for p in matching for v in p) != list(H):
        raise BoundError("H does not carry 20 triple lines and a perfect matching of pair lines")
    design = tuple(sorted((*triples, *((a, b, OO) for a, b in matching))))
    if not is_sts13(design):
        raise BoundError("F3 on H with oo + F2 is not an STS(13)")
    remaining, avoiding, through = deletion(design, OO)
    if remaining != H or avoiding != tuple(sorted(triples)) or through != tuple(sorted(matching)):
        raise BoundError("deleting oo from the extension does not return the H lines")
    return design


def pointed_portfolio(name: str, point: int) -> census.Tickets:
    """The constructor's ``_portfolio_for_deleted_point``: H ticket i is the i-th other point,
    numbers 1..20 are the avoiding blocks, 21..26 the matching, then the fixed eight tickets."""

    remaining, avoiding, through = deletion(STS13_DESIGNS[name], point)
    index = {v: i for i, v in enumerate(remaining)}
    tickets: list[list[int]] = [[] for _ in remaining]
    for number, line in enumerate((*avoiding, *through), start=1):
        for v in line:
            tickets[index[v]].append(number)
    return tuple(tuple(sorted(t)) for t in tickets) + FIXED_EIGHT_TICKETS


def pointed_structure(name: str, point: int) -> census.Structure:
    profile, structure = census.structure_from_tickets(pointed_portfolio(name, point))
    if profile != PROFILE:
        raise BoundError(f"{name}/{point} does not carry the CELL_A profile")
    return structure


# Step 3: the U side -----------------------------------------------------------------------


def u_partitions() -> tuple[tuple[Block, Block], ...]:
    """The C(6, 3) / 2 = 10 unordered splits of the six d = 1 tickets into two triples."""

    splits: list[tuple[Block, Block]] = []
    for first in combinations(POSITIVE_U, 3):
        if POSITIVE_U[0] in first:
            a, b, c = sorted(set(POSITIVE_U) - set(first))
            splits.append((first, (a, b, c)))
    return tuple(splits)


def u_lines(triples: Sequence[Block]) -> tuple[tuple[Block, ...], tuple[Pair, ...]]:
    """The two triples and the 21 edges of K8 - {18, 19} outside their two triangles."""

    ordered = tuple(sorted(cast(Block, tuple(sorted(t))) for t in triples))
    if len(ordered) != 2 or sorted(v for t in ordered for v in t) != list(POSITIVE_U):
        raise BoundError("U triple lines are not two disjoint triples on the six d = 1 tickets")
    inside = {p for t in ordered for p in combinations(t, 2)}
    pairs = tuple(p for p in combinations(U, 2) if p != ZERO_U and p not in inside)
    return ordered, pairs


def u_mapping(triples: Sequence[Block]) -> dict[int, int]:
    """First sorted triple onto 12, 13, 14, second onto 15, 16, 17; 18 and 19 fixed."""

    first, second = u_lines(triples)[0]
    mapping = {
        **dict(zip(first, DONOR_U_TRIPLES[0], strict=True)),
        **dict(zip(second, DONOR_U_TRIPLES[1], strict=True)),
        **{v: v for v in ZERO_U},
    }
    donor = u_lines(DONOR_U_TRIPLES)
    image = u_lines([cast(Block, tuple(mapping[v] for v in t)) for t in (first, second)])
    pairs = tuple(
        sorted(cast(Pair, tuple(sorted(mapping[v] for v in p))) for p in u_lines(triples)[1])
    )
    if sorted(mapping) != list(U) or image != donor or pairs != donor[1]:
        raise BoundError("the U map does not carry these U lines onto the donor U lines")
    return mapping


# The CELL_A domain and the cover ------------------------------------------------------------


def check_cell_a(
    structure: census.Structure, profile_id: str = PROFILE_ID, t: int = TARGET_T
) -> rigidity.StructureLedger:
    """Fail closed unless ``structure`` meets the four premises with d = (5^12, 1^6, 0^2)."""

    check_scope(profile_id, t)
    try:
        census.validate_structure(PROFILE, structure)
    except census.CensusError as error:
        raise BoundError(f"not a CELL_A structure: {error}") from error
    for line in (*structure.triples, *structure.pairs):
        if not (set(line) <= H_SET or set(line) <= U_SET):
            raise BoundError(f"line {line} crosses H and U; rigidity step F excludes it")
    u_lines([t for t in structure.triples if set(t) <= U_SET])
    try:
        return rigidity.structure_ledger(structure.triples, structure.pairs)
    except rigidity.CertificateError as error:
        raise BoundError(f"outside the CELL_A premises: {error}") from error


def number_bijection(
    source: census.Tickets, target: census.Tickets, tickets: Sequence[int]
) -> tuple[int, ...]:
    """sigma with ticket v of ``source`` holding n iff ticket tickets[v] of ``target`` holds
    sigma(n), checked on every ticket. Entry n - 1 is sigma(n)."""

    if len(source) != len(target) or sorted(tickets) != list(range(len(source))):
        raise BoundError("the ticket map is not a permutation of the portfolio")

    def holders(portfolio: census.Tickets) -> dict[int, frozenset[int]]:
        held: dict[int, set[int]] = {}
        for v, ticket in enumerate(portfolio):
            for n in ticket:
                held.setdefault(n, set()).add(v)
        return {n: frozenset(h) for n, h in held.items()}

    target_lines = {line: n for n, line in holders(target).items()}
    sigma: dict[int, int] = {}
    for n, line in holders(source).items():
        image = frozenset(tickets[v] for v in line)
        if image not in target_lines:
            raise BoundError(f"number {n}: its line has no image line")
        sigma[n] = target_lines[image]
    numbers = list(range(1, census.POOL_SIZE + 1))
    if sorted(sigma) != numbers or sorted(sigma.values()) != numbers:
        raise BoundError("the line map is not a bijection of the 49 numbers")
    for v, ticket in enumerate(source):
        if sorted(sigma[n] for n in ticket) != sorted(target[tickets[v]]):
            raise BoundError(f"ticket {v} does not map onto ticket {tickets[v]}")
    return tuple(sigma[n] for n in numbers)


@dataclass(frozen=True, slots=True)
class PointedClass:
    class_id: str
    design: str
    points: tuple[int, ...]
    canonical_id: str
    count: int


@cache
def _canonical_ids() -> dict[tuple[str, int], str]:
    return {
        (name, p): engine.canonicalize(PROFILE, pointed_structure(name, p)).witness_id
        for name in DESIGN_NAMES
        for p in range(POINTS)
    }


def check_rows(rows: Sequence[ScoreRow]) -> dict[tuple[str, int], int]:
    """The reused rows: complete, each tied to its in-memory portfolio by SHA, and pinned."""

    keys = [(name, point) for name, point, _, _ in rows]
    if sorted(keys) != [(n, p) for n in DESIGN_NAMES for p in range(POINTS)]:
        raise BoundError("score rows do not cover the 26 pointed constructions exactly once")
    for name, point, sha, count in rows:
        if census.compact_tickets_sha256(pointed_portfolio(name, point)) != sha:
            raise BoundError(f"{name}/{point}: PORTFOLIO_SHA256 differs from its deletion")
        if type(count) is not int:
            raise BoundError(f"{name}/{point}: count is not an integer")
    if rows_sha256(rows) != DONOR_ROWS_SHA256:
        raise BoundError("score rows differ from the pinned donor rows")
    return {(name, point): count for name, point, _, count in rows}


def pointed_classes(rows: Sequence[ScoreRow] = DONOR_ROWS) -> tuple[PointedClass, ...]:
    """Classes = Aut point orbits; the canonical form must agree, and so must the counts."""

    counts = check_rows(rows)
    canonical = _canonical_ids()
    found: list[PointedClass] = []
    for name in DESIGN_NAMES:
        for orbit in point_orbits(name):
            ids = {canonical[(name, p)] for p in orbit}
            scores = {counts[(name, p)] for p in orbit}
            if len(ids) != 1:
                raise BoundError(f"{name} orbit {orbit} splits under the canonical form")
            if len(scores) != 1:
                raise BoundError(f"{name} orbit {orbit}: reused counts are not constant")
            label = f"C{len(found) + 1}"
            found.append(PointedClass(label, name, orbit, ids.pop(), scores.pop()))
    if len({c.canonical_id for c in found}) != len(found):
        raise BoundError("two orbits share one canonical form")
    if tuple((c.class_id, c.design, c.points) for c in found) != CLASS_TABLE:
        raise BoundError("the pointed classes differ from the pinned class table")
    if {c.class_id: c.count for c in found} != REUSED_CLASS_COUNTS:
        raise BoundError("class counts differ from the pinned reused counts")
    return tuple(found)


@dataclass(frozen=True, slots=True)
class Cover:
    """``tickets[v]`` is solution ticket v's donor ticket; ``numbers[n - 1]`` is sigma(n)."""

    class_id: str
    design: str
    deleted_point: int
    tickets: Permutation
    numbers: tuple[int, ...]
    count: int


def _classify(design: Design) -> tuple[str, Permutation]:
    for name in DESIGN_NAMES:
        found = sts_isomorphisms(design, STS13_DESIGNS[name], first=True)
        if found:
            return name, found[0]
    raise BoundError(
        "the extension is isomorphic to neither donor STS(13); this contradicts the external "
        "classification"
    )


def cover(
    structure: census.Structure,
    *,
    profile_id: str = PROFILE_ID,
    t: int = TARGET_T,
    classes: Sequence[PointedClass] | None = None,
) -> Cover:
    """Map one CELL_A solution onto its donor portfolio and return its class and reused count."""

    check_cell_a(structure, profile_id, t)
    design = extend_h(structure)
    u_triples = tuple(line for line in structure.triples if set(line) <= U_SET)
    u_pairs = tuple(line for line in structure.pairs if set(line) <= U_SET)
    if u_pairs != u_lines(u_triples)[1]:
        raise BoundError("U pair lines are not the K8 - e edges outside the two U triangles")
    name, phi = _classify(design)
    point = phi[OO]
    index = {v: i for i, v in enumerate(v for v in range(POINTS) if v != point)}
    u_map = u_mapping(u_triples)
    tickets = tuple(index[phi[v]] if v in H_SET else u_map[v] for v in range(census.TICKET_COUNT))
    numbers = number_bijection(census.portfolio(structure), pointed_portfolio(name, point), tickets)
    owner = next(
        c for c in (classes or pointed_classes()) if c.design == name and point in c.points
    )
    if engine.canonicalize(PROFILE, structure).witness_id != owner.canonical_id:
        raise BoundError("the canonical form disagrees with the structural cover")
    return Cover(owner.class_id, name, point, tickets, numbers, owner.count)


# Source identity --------------------------------------------------------------------------


def _pin(role: str) -> SourcePin:
    return next(pin for pin in SOURCES if pin.role == role)


def verify_loaded_modules() -> None:
    """The imported rigidity, census and engine modules are byte-identical to their pins."""

    for role, module in (
        ("RIGIDITY_CERTIFICATE", rigidity),
        ("FROZEN_CENSUS", census),
        ("FROZEN_ENGINE", engine),
    ):
        path = module.__file__
        if path is None or census.git_blob_id(Path(path).read_bytes()) != _pin(role).blob:
            raise BoundError(f"{role}: the loaded module differs from blob {_pin(role).blob}")
    if _pin("EVALUATOR").blob != census.EVALUATOR_BLOB:
        raise BoundError("the census pins a different evaluator blob")


def git_reader(root: Path) -> Reader:
    def read(commit: str, path: str) -> bytes:
        command = ["git", "-C", str(root), "cat-file", "blob", f"{commit}:{path}"]
        return subprocess.run(command, check=True, capture_output=True).stdout

    return read


def _literal(source: bytes, name: str) -> object:
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id == name:
            return cast(object, ast.literal_eval(value))
    raise BoundError(f"no literal {name}")


def _donor_rows(result: Mapping[str, object]) -> tuple[ScoreRow, ...]:
    raw = result.get("CANDIDATE_COUNTS")
    if not isinstance(raw, list):
        raise BoundError("donor result has no CANDIDATE_COUNTS list")
    rows: list[ScoreRow] = []
    for item in cast(list[object], raw):
        row = cast(dict[str, object], item) if isinstance(item, dict) else {}
        name, point = row.get("STS_CLASS"), row.get("DELETED_POINT")
        sha, count = row.get("PORTFOLIO_SHA256"), row.get("OFFICIAL_ANY_PRIZE_OUTCOME_COUNT")
        if not (isinstance(name, str) and isinstance(sha, str)) or not (
            type(point) is int and type(count) is int
        ):
            raise BoundError("donor score row is malformed")
        rows.append((name, point, sha, count))
    return tuple(rows)


def verify_sources(read: Reader) -> dict[str, str]:
    """Every pin resolves to its blob, and each reused literal equals its donor's bytes."""

    blobs: dict[str, bytes] = {}
    for pin in SOURCES:
        if len(pin.commit) != 40 or len(pin.blob) != 40:
            raise BoundError(f"{pin.role}: pins must be full object ids")
        data = read(pin.commit, pin.path)
        if census.git_blob_id(data) != pin.blob:
            raise BoundError(f"{pin.role}: {pin.commit}:{pin.path} is not blob {pin.blob}")
        blobs[pin.role] = data
    if _literal(blobs["CONSTRUCTOR"], "FIXED_EIGHT_TICKETS") != FIXED_EIGHT_TICKETS:
        raise BoundError("FIXED_EIGHT_TICKETS differs from the constructor")
    helper = blobs["STS_AUTOMORPHISM_HELPER"]
    if (
        _literal(helper, "STS13_DESIGNS") != STS13_DESIGNS
        or _literal(helper, "STS13_DESIGNS_SHA256") != STS13_DESIGNS_SHA256
    ):
        raise BoundError("STS13_DESIGNS differs from the helper")
    loaded = cast(object, json.loads(blobs["DONOR_RESULT"]))
    result = cast(dict[str, object], loaded) if isinstance(loaded, dict) else {}
    if _donor_rows(result) != DONOR_ROWS:
        raise BoundError("DONOR_ROWS differ from the donor result's CANDIDATE_COUNTS")
    if any(result.get(field) != value for field, value in DONOR_SEAL.items()):
        raise BoundError("the donor result's seal fields differ")
    verify_loaded_modules()
    return {pin.role: pin.blob for pin in SOURCES}


# The certificate --------------------------------------------------------------------------


@cache
def _construction_facts() -> dict[str, object]:
    """Designs, both directions of step 2 on all 26 constructions, and all ten U splits."""

    if _json_sha256({n: [list(b) for b in d] for n, d in STS13_DESIGNS.items()}) != (
        STS13_DESIGNS_SHA256
    ):
        raise BoundError("the STS(13) designs differ from their pin")
    cyclic, noncyclic = (STS13_DESIGNS[name] for name in DESIGN_NAMES)
    if not (is_sts13(cyclic) and is_sts13(noncyclic)) or sts_isomorphisms(cyclic, noncyclic):
        raise BoundError("the donor designs are not two non-isomorphic STS(13)")
    for name in DESIGN_NAMES:
        for p in range(POINTS):
            structure = pointed_structure(name, p)
            check_cell_a(structure)
            # rho renames the other points 0..11 in order and p to oo.
            rho = [OO] * POINTS
            for i, v in enumerate(v for v in range(POINTS) if v != p):
                rho[v] = i
            image = tuple(sorted(_image(tuple(rho), b) for b in STS13_DESIGNS[name]))
            if image != extend_h(structure):
                raise BoundError(f"{name}/{p}: extending the deletion does not return the design")
    donor_u = census.structure_from_tickets(pointed_portfolio("CYCLIC", 0))[1]
    if u_lines(DONOR_U_TRIPLES) != (
        tuple(t for t in donor_u.triples if set(t) <= U_SET),
        tuple(p for p in donor_u.pairs if set(p) <= U_SET),
    ):
        raise BoundError("the fixed eight tickets do not realize the donor U lines")
    splits = u_partitions()
    for split in splits:
        u_mapping(split)
    return {
        "PASCH_COUNTS": {name: pasch_count(STS13_DESIGNS[name]) for name in DESIGN_NAMES},
        "AUTOMORPHISM_GROUP_ORDERS": {name: len(automorphisms(name)) for name in DESIGN_NAMES},
        "U_PARTITIONS": len(splits),
        "U_PAIR_LINES": len(u_lines(splits[0])[1]),
    }


def certificate(
    profile_id: str = PROFILE_ID, t: int = TARGET_T, rows: Sequence[ScoreRow] = DONOR_ROWS
) -> dict[str, object]:
    """The covering argument for CELL_A, its reused counts, the bound and its SHA-256."""

    check_scope(profile_id, t)
    verify_loaded_modules()
    rigid = rigidity.certificate()
    if rigid["CERTIFICATE_SHA256"] != RIGIDITY_CERTIFICATE_SHA256 or rigid["VERDICT"] != (
        rigidity.RIGID
    ):
        raise BoundError("the rigidity certificate differs from its pin")
    facts = _construction_facts()
    classes = pointed_classes(rows)
    bound = max(c.count for c in classes)
    if bound != UPPER_BOUND or census.STRICT_GAIN_THRESHOLD != STRICT_GAIN_THRESHOLD:
        raise BoundError(f"the reused maximum {bound} is not {UPPER_BOUND}")
    winner = next(
        c
        for c in classes
        if c.design == DONOR_SEAL["BEST_STS_CLASS"] and DONOR_SEAL["BEST_DELETED_POINT"] in c.points
    )
    if (winner.class_id, winner.count) != ("C4", DONOR_SEAL["BEST_COUNT"]):
        raise BoundError("the donor's sealed winner is not the C4 attainment")
    record: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "BASE_COMMIT": BASE_COMMIT,
        "PROFILE_ID": PROFILE_ID,
        "TARGET_T": TARGET_T,
        "D_PROFILE": "5^12 1^6 0^2",
        "MODEL_ASSUMPTIONS": list(rigidity.ASSUMPTIONS),
        "NOT_PREMISES": ["non-adjacent-pair cut", "engine no-goods", "lex-leader rows"],
        "RIGIDITY_CERTIFICATE_SHA256": RIGIDITY_CERTIFICATE_SHA256,
        "SOURCES": [
            {"ROLE": p.role, "COMMIT": p.commit, "PATH": p.path, "BLOB": p.blob} for p in SOURCES
        ],
        "EXTERNAL_CLASSIFICATION": EXTERNAL_CLASSIFICATION,
        "STS13_DESIGNS_SHA256": STS13_DESIGNS_SHA256,
        **facts,
        "H_EXTENSION": "F3 (20) + {a, b, oo} for F2 (6) = STS(13); deleting oo is its inverse",
        "U_INCIDENCE_CLASSES": 1,
        "POINTED_CONSTRUCTIONS": len(rows),
        "CONSTRUCTIONS_IN_ORIGINAL_CELL_A_DOMAIN": len(rows),
        "CLASSES": [
            {
                "CLASS": c.class_id,
                "DESIGN": c.design,
                "DELETED_POINTS": list(c.points),
                "SIZE": len(c.points),
                "CANONICAL_WITNESS_ID": c.canonical_id,
                "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": c.count,
                "COUNT_EVIDENCE": "REUSED",
            }
            for c in classes
        ],
        "CLASS_SIZES": [len(c.points) for c in classes],
        "DONOR_ROWS_SHA256": rows_sha256(rows),
        "REUSED_SCORE_PROVENANCE": {
            "RESULT_BLOB": _pin("DONOR_RESULT").blob,
            "EVALUATOR_BLOB": _pin("EVALUATOR").blob,
            "DONOR_SEAL": DONOR_SEAL,
            "CAVEAT": (
                "the donor result records no scorer hash; the evaluator blob is the blob at its "
                "path in the donor commit tree, an inference, not an attestation of the run"
            ),
        },
        "CELL_A_EXACT_UPPER_BOUND": bound,
        "STRICT_GAIN_THRESHOLD": STRICT_GAIN_THRESHOLD,
        "ATTAINING_CLASSES": [c.class_id for c in classes if c.count == bound],
        "ATTAINMENT_SCOPE": (
            "original CELL_A structural domain; the donor's sealed winner NONCYCLIC/5 is in C4; "
            "exclusion rows may remove attainment but never raise the bound"
        ),
        "CP_SAT_CALLS": 0,
        "NEW_EXACT_SCORING_CALLS": 0,
        "NOT_CLAIMED": {
            "STS13_CLASSIFICATION": "EXTERNAL_NOT_REPROVED",
            "OTHER_CELLS_PROFILES_OR_TARGETS": "OUT_OF_SCOPE",
            "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        },
        "VERDICT": VERDICT,
    }
    body = census.canonical_json(record).encode()
    return {**record, "CERTIFICATE_SHA256": census.sha256_bytes(body)}


def verify_certificate(record: Mapping[str, object]) -> None:
    """Refuse a record that differs in any field from the re-derived certificate."""

    expected = certificate()
    differing = sorted(
        k for k in expected.keys() | record.keys() if record.get(k) != expected.get(k)
    )
    if differing:
        raise BoundError(f"certificate differs from its derivation in {differing}")


def main() -> None:
    verify_sources(git_reader(census.repo_root()))
    print(json.dumps(certificate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
