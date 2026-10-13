"""Finite support coverage of CELL_A, conditional on the published STS(13) classification.

This is a bridge, not a new rigidity proof or a score computation. The pinned db91 certificate
proves that every solution of the frozen profile 55555555555511111100 at T=270 has overlap
K12 disjoint union (K8-e). A support containing vertices of both components contains a cross
edge, which is impossible. Thus its line decomposition splits into H and U.

On H, rigidity's pointed extension adds infinity to the six matching edges alongside the
twenty triple lines. This is an STS(13): H pairs occur once, and each {infinity,v} occurs once.
Conversely deleting the distinguished point recovers precisely those triples and pairs.
An STS isomorphism carrying infinity to p restricts to a bijection on the twelve remaining
points and sends both kinds of H supports onto the existing constructor's deletion of p.

On U, six vertices have triple degree one and two have triple degree zero. The six incidences
therefore form two disjoint triples on exactly the six positive vertices. Their six edges are
disjoint; the other 27-6=21 edges of K8-e MUST be the pair supports, since every overlap edge
occurs once. Sorting the two triples and mapping their sorted vertices to (12,13,14) and
(15,16,17), and the zero vertices to (18,19), is an explicit degree-preserving bijection.
There are C(6,3)/2=10 unordered partitions; all are replayed below, including their pairs.

The external premise is Heinlein & Östergård, Enumerating Steiner triple systems, Journal of
Combinatorial Designs 31 (2023), 479-495, DOI 10.1002/jcd.21906, introduction: STS(13) has two
unpointed isomorphism classes. This module does NOT prove that classification. The two pinned
designs are valid and distinct, so that premise implies they exhaust the unpointed systems.
Every pointed system consequently maps to one design with one of its thirteen points marked.
The 26 raw keys are canonicalized using the inherited exact SUPPORT canonicalizer; their
quotient is checked against point orbits from the preserved automorphism implementation.
Portfolio byte normalization (25 SHAs) is a different operation from that quotient (5 classes).

For an actual model portfolio, ``cover_solution`` replays extension -> unpointed isomorphism
-> deletion key, combines the H and U maps, then composes the raw-key -> representative map.
Every arrow is checked on complete supports, and both ticket and number bijections are
returned. Matching overlap graphs alone, or matching historical scores, never identifies a
class. Lex-leaders and no-goods take subsets of the covered solution set and cannot add a
sixth class. Other profiles, targets, support models, CELL_A score closure and global K20
optimality are outside this theorem. No CP-SAT or exact scoring entry point is called.

Only pinned Git blobs are donor inputs. Their named construction/group functions are loaded
in memory from the original AST, with scoring/solver functions and nonstandard imports
excluded. No historical result, recount file, donor checkout, or temporary source is read.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import combinations
from math import comb
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

from lottolab.research import b649_cell_a_overlap_rigidity_certificate as rigidity
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_two_open_cells_targeted_solver as engine

TASK_ID = "B649_CELL_A_FIVE_CLASS_COVERAGE_CERTIFICATE_R1"
BASE_HEAD = "24ff183c68ac02ea497044921207913a16ec09bd"
BASE_TREE = "54c122248a3321fdcf688c845a0f9bdd64efe3f2"
RIGIDITY_SHA256 = "db91bb0689e978de16e33776fe975515c899c31396107b5908daed35d07d6c96"
PROFILE_ID = rigidity.PROFILE_ID
TARGET_T = rigidity.TARGET_T
PROFILE = tuple(map(int, PROFILE_ID))
H = frozenset(range(12))
U = frozenset(range(12, 20))
POSITIVE_U = tuple(range(12, 18))
ZERO_U = (18, 19)

type Line = tuple[int, ...]
type Block = tuple[int, int, int]
type Design = tuple[Block, ...]
type Portfolio = tuple[tuple[int, ...], ...]
type Permutation = tuple[int, ...]
type Key = tuple[str, int]


class CoverageError(ValueError):
    """A bridge step failed, or the inputs do not meet the certificate's scope."""


@dataclass(frozen=True, slots=True)
class SourcePin:
    name: str
    commit: str
    path: str
    blob: str
    sha256: str


SOURCES = (
    SourcePin(
        "rigidity",
        BASE_HEAD,
        "src/lottolab/research/b649_cell_a_overlap_rigidity_certificate.py",
        "d3b06e36f6dca849c56574100aa5bcc3711f2463",
        "d62d9f9f558821e318791a8602a4074bf6bbb759bf2b92b7e19481dac3bf982d",
    ),
    SourcePin(
        "engine",
        "03b5691fac02c3a125c91cf4120b6219c3143b5e",
        "src/lottolab/research/b649_k20_two_open_cells_targeted_solver.py",
        "1334605792bf6b46ceeed7b2806ba593b7548841",
        "40e8881168512768257bdd03260008ea8e00b4fb8a56540536d76f35df307628",
    ),
    SourcePin(
        "census",
        "03b5691fac02c3a125c91cf4120b6219c3143b5e",
        "src/lottolab/research/b649_k20_fiber_near_top_s3_census.py",
        "c660faec6d7c916057df0c924c930460aca5697e",
        "479f3163659a91234d23637b697527224e947ae3268e49515cd609ca82ca6276",
    ),
    SourcePin(
        "constructor",
        "82e88ada111bf6d0999ac9c0c167a160a6ae5df8",
        "src/lottolab/research/b649_k20_overlap_block_repartition_12_8_exhaustive_r1.py",
        "b5d9dd41481762bad815e14119c6e7c39ce1d8e3",
        "852c210bcf3b1916c4dad74ca44847eade5c71269e985644724dbc17e1192daa",
    ),
    SourcePin(
        "sts",
        "7b573db44f56c49e2a0bbb7c002f092e5839d62b",
        "src/lottolab/research/b649_k20_11_9_single_bridge_sts13_family_exact_r1.py",
        "1d9c60e154996484fdd6a24f81a73189cf3da901",
        "44d085dc7a9475fd81e3014e507d32a818ebe8179f4c6a0ad98a0d3a4bfb5282",
    ),
)


@dataclass(frozen=True, slots=True)
class ExternalClassification:
    authors: str
    title: str
    journal: str
    doi: str
    location: str
    order: int
    unpointed_classes: int
    locally_proved: bool


CLASSIFICATION = ExternalClassification(
    "Daniel Heinlein; Patric R. J. Östergård",
    "Enumerating Steiner triple systems",
    "Journal of Combinatorial Designs 31 (2023), 479-495",
    "10.1002/jcd.21906",
    "Introduction, paragraph listing class counts for orders 3, 7, 9, 13, 15, 19",
    13,
    2,
    False,
)
CLASSIFICATION_URL = "https://doi.org/10.1002/jcd.21906"


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def check_scope(profile_id: str, t: int, classification: ExternalClassification | None) -> None:
    if (profile_id, t) != (PROFILE_ID, TARGET_T):
        raise CoverageError(f"scope: only CELL_A {PROFILE_ID}, T={TARGET_T}")
    if classification != CLASSIFICATION:
        raise CoverageError("external classification identity missing or mismatched")


def verify_source_bytes(blobs: Mapping[str, bytes]) -> None:
    for pin in SOURCES:
        if pin.name not in blobs:
            raise CoverageError(f"source missing: {pin.name}")
        data = blobs[pin.name]
        if hashlib.sha256(data).hexdigest() != pin.sha256:
            raise CoverageError(f"source SHA256 mismatch: {pin.name}")
        blob_hash = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if pin.blob and blob_hash != pin.blob:
            raise CoverageError(f"source Git blob mismatch: {pin.name}")


def read_sources(root: Path) -> dict[str, bytes]:
    blobs: dict[str, bytes] = {}
    for pin in SOURCES:
        shown = subprocess.run(
            ["git", "show", f"{pin.commit}:{pin.path}"], cwd=root, capture_output=True, check=False
        )
        if shown.returncode:
            raise CoverageError(
                f"source missing or unreadable: {pin.name} at {pin.commit}:{pin.path}"
            )
        blobs[pin.name] = shown.stdout
    verify_source_bytes(blobs)
    for pin, module in zip(SOURCES[:3], (rigidity, engine, census), strict=True):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != pin.sha256:
            raise CoverageError(f"imported source mismatch: {pin.name}")
    return blobs


def reuse_rigidity() -> dict[str, object]:
    record = rigidity.certificate()
    rigidity.verify_certificate(record)
    if record["CERTIFICATE_SHA256"] != RIGIDITY_SHA256:
        raise CoverageError("rigidity certificate identity mismatch")
    if record["FROZEN_REFERENCES"] != rigidity.FROZEN_REFERENCES or (
        rigidity.FROZEN_REFERENCES["TWO_CELL_ENGINE_SHA256"] != SOURCES[1].sha256
        or rigidity.FROZEN_REFERENCES["CENSUS_ENGINE_SHA256"] != SOURCES[2].sha256
        or rigidity.FROZEN_REFERENCES["CELL_A_MODEL_PROTO_SHA256"]
        != engine.MODEL_PROTO_SHA256["CELL_A"]
    ):
        raise CoverageError("rigidity/engine/model binding mismatch")
    return record


class ConstructedClasses(Protocol):
    cyclic: Design
    noncyclic: Design


class Constructor(Protocol):
    FIXED_EIGHT_TICKETS: Portfolio

    def is_valid_sts13(self, blocks: Sequence[Block]) -> bool: ...
    def build_sts13_classes(self) -> ConstructedClasses: ...
    def portfolio_for_deleted_point(self, blocks: Design, deleted_point: int) -> Portfolio: ...


class PreservedSTS(Protocol):
    STS13_DESIGNS: dict[str, Design]
    STS13_DESIGNS_SHA256: str
    STS13_SOURCE: dict[str, str]

    def sts13_designs_sha256(self) -> str: ...
    def sts13_automorphisms(self, design: Design) -> tuple[Permutation, ...]: ...


CONSTRUCTOR_SYMBOLS = frozenset(
    {
        "POINT_COUNT",
        "FIXED_EIGHT_TICKETS",
        "Pair",
        "Block",
        "Design",
        "Ticket",
        "Portfolio",
        "PaschConfiguration",
        "PaschTrade",
        "STS13Classes",
        "_normalize_block",
        "is_valid_sts13",
        "_pasch_configurations",
        "pasch_count",
        "_cyclic_sts13",
        "_negative_pasches",
        "_valid_pasch_trades",
        "_completion_table",
        "_pasch_point_signature",
        "sts13_are_isomorphic",
        "build_sts13_classes",
        "_portfolio_for_deleted_point",
    }
)
STS_SYMBOLS = frozenset(
    {
        "POINT_COUNT",
        "Pair",
        "Block",
        "Design",
        "Permutation",
        "STS13_DESIGNS",
        "STS13_DESIGNS_SHA256",
        "STS13_SOURCE",
        "_sha256_json",
        "sts13_designs_sha256",
        "is_valid_sts13",
        "third_point_table",
        "_pair",
        "_compose",
        "_verify_group",
        "_close_point_map",
        "sts13_automorphisms",
    }
)
STANDARD_IMPORTS = frozenset(
    {
        "__future__",
        "hashlib",
        "itertools",
        "json",
        "collections",
        "collections.abc",
        "dataclasses",
        "functools",
        "math",
        "typing",
    }
)


def _load_symbols(data: bytes, pin: SourcePin, symbols: frozenset[str]) -> ModuleType:
    """Execute original, hash-checked construction functions only; no donor score APIs exist."""
    nodes: list[ast.stmt] = []
    found: set[str] = set()
    for node in ast.parse(data, filename=pin.path).body:
        if isinstance(node, ast.Import):
            if all(alias.name in STANDARD_IMPORTS for alias in node.names):
                nodes.append(node)
            continue
        if isinstance(node, ast.ImportFrom):
            if node.module in STANDARD_IMPORTS:
                nodes.append(node)
            continue
        name: str | None = None
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            name = node.name
        elif isinstance(node, ast.TypeAlias):
            name = node.name.id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                name = target.id
        if name in symbols:
            nodes.append(node)
            found.add(name)
    if found != set(symbols):
        raise CoverageError(f"source API missing in {pin.name}: {sorted(symbols - found)}")
    module_name = f"{__name__}._pinned_{pin.name}"
    module = ModuleType(module_name)
    sys.modules[module_name] = module  # Original dataclass decorators resolve their own module.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), pin.path, "exec"), module.__dict__)
    return module


def load_donors(blobs: Mapping[str, bytes]) -> tuple[Constructor, PreservedSTS]:
    verify_source_bytes(blobs)
    constructor_module = _load_symbols(blobs["constructor"], SOURCES[3], CONSTRUCTOR_SYMBOLS)
    # A public alias to the unchanged original function, rather than a new implementation.
    constructor_module.__dict__["portfolio_for_deleted_point"] = constructor_module.__dict__[
        "_portfolio_for_deleted_point"
    ]
    constructor = cast(Constructor, constructor_module)
    sts = cast(PreservedSTS, _load_symbols(blobs["sts"], SOURCES[4], STS_SYMBOLS))
    pin = SOURCES[3]
    expected_source = {
        "TASK_ID": "B649_K20_OVERLAP_BLOCK_REPARTITION_12_8_EXHAUSTIVE_R1",
        "COMMIT": pin.commit,
        "PATH": pin.path,
        "BLOB": pin.blob,
        "FUNCTION": "build_sts13_classes",
    }
    if expected_source != sts.STS13_SOURCE or (
        sts.sts13_designs_sha256() != sts.STS13_DESIGNS_SHA256
    ):
        raise CoverageError("preserved STS/constructor identity mismatch")
    classes = constructor.build_sts13_classes()
    expected_designs = {"CYCLIC": classes.cyclic, "NONCYCLIC": classes.noncyclic}
    if expected_designs != sts.STS13_DESIGNS:
        raise CoverageError("preserved STS designs differ from original constructor")
    return constructor, sts


def supports(tickets: Sequence[Sequence[int]]) -> census.Structure:
    """Retain model ticket indices and actual number labels; no degree-order normalization."""
    if len(tickets) != 20 or any(
        len(ticket) != 6
        or len(set(ticket)) != 6
        or any(type(n) is not int or not 1 <= n <= 49 for n in ticket)
        for ticket in tickets
    ):
        raise CoverageError("portfolio: require twenty tickets of six distinct numbers in 1..49")
    lines = tuple(tuple(v for v, ticket in enumerate(tickets) if n in ticket) for n in range(1, 50))
    if any(len(line) not in (2, 3) for line in lines):
        raise CoverageError("support model: every number must occur on two or three tickets")
    return census.Structure(
        tuple(sorted(line for line in lines if len(line) == 3)),
        tuple(sorted(line for line in lines if len(line) == 2)),
    )


def _u_edges() -> frozenset[census.Pair]:
    return frozenset(p for p in combinations(sorted(U), 2) if p != ZERO_U)


def u_partitions() -> tuple[tuple[Block, Block], ...]:
    """Choose the block containing 12 to remove the interchange of the two triples."""
    return tuple(
        (
            cast(Block, (12, *pair)),
            cast(Block, tuple(v for v in POSITIVE_U if v not in pair and v != 12)),
        )
        for pair in combinations(POSITIVE_U[1:], 2)
    )


def u_pairs(triples: Sequence[Block]) -> tuple[census.Pair, ...]:
    return tuple(sorted(_u_edges() - {p for t in triples for p in combinations(sorted(t), 2)}))


def u_mapping(triples: Sequence[Block], pairs: Sequence[census.Pair]) -> Permutation:
    """Full twenty-ticket permutation, fixing H, and sending this U to the fixed partition."""
    degree = Counter(v for t in triples for v in t)
    if len(triples) != 2 or any(len(set(t)) != 3 for t in triples) or degree != Counter(POSITIVE_U):
        raise CoverageError("U triple degree: six degree-one vertices and two degree-zero vertices")
    if len(pairs) != 21 or tuple(sorted(pairs)) != u_pairs(triples):
        raise CoverageError("U pair supports: require the unique remaining 21 edges")
    ordered = sorted(tuple(sorted(t)) for t in triples)
    mapping = list(range(20))
    for source, target in zip((*ordered[0], *ordered[1], *ZERO_U), sorted(U), strict=True):
        mapping[source] = target
    image_triples = {tuple(sorted(mapping[v] for v in t)) for t in triples}
    fixed = ((12, 13, 14), (15, 16, 17))
    image_pairs = {tuple(sorted(mapping[v] for v in p)) for p in pairs}
    if image_triples != set(fixed) or image_pairs != set(u_pairs(fixed)):
        raise CoverageError("U explicit map did not preserve complete supports")
    return tuple(mapping)


def check_structure(structure: census.Structure) -> None:
    lines = (*structure.triples, *structure.pairs)
    if any(set(line) & H and set(line) & U for line in lines):
        raise CoverageError("cross-component support forces a forbidden overlap cross edge")
    u_mapping(
        tuple(t for t in structure.triples if set(t) <= U),
        tuple(p for p in structure.pairs if set(p) <= U),
    )
    try:
        census.validate_structure(PROFILE, structure)
    except census.CensusError as error:
        raise CoverageError(f"CELL_A support/profile: {error}") from error
    if census.edges(structure) != set(combinations(sorted(H), 2)) | set(_u_edges()):
        raise CoverageError("structure does not realize the certified overlap graph at T=270")


def extend_h(structure: census.Structure, constructor: Constructor) -> Design:
    check_structure(structure)
    triples = tuple(t for t in structure.triples if set(t) <= H)
    pairs = tuple(p for p in structure.pairs if set(p) <= H)
    if len(triples) != 20 or len(pairs) != 6 or sorted(v for p in pairs for v in p) != sorted(H):
        raise CoverageError("H extension: require twenty triples and a six-edge perfect matching")
    blocks = tuple(sorted((*triples, *((a, b, 12) for a, b in pairs))))
    if not constructor.is_valid_sts13(blocks):
        raise CoverageError("H extension: pairs are not covered exactly once in an STS(13)")
    return blocks


def delete_h(design: Design, point: int, constructor: Constructor) -> Portfolio:
    if not 0 <= point < 13 or not constructor.is_valid_sts13(design):
        raise CoverageError("H deletion: require a valid pointed STS(13)")
    tickets = constructor.portfolio_for_deleted_point(design, point)
    check_structure(supports(tickets))
    return tickets


def verify_complete_keys(keys: Iterable[Key]) -> None:
    keys = tuple(keys)
    expected = {(name, p) for name in ("CYCLIC", "NONCYCLIC") for p in range(13)}
    if len(keys) != len(expected) or set(keys) != expected:
        raise CoverageError(
            f"pointed completeness: missing={sorted(expected - set(keys))}; "
            f"duplicate/foreign keys or cardinality={len(keys)}"
        )


def normalized_sha(tickets: Portfolio) -> str:
    """Sorted ticket bytes only. This is deliberately not an isomorphism-class identity."""
    return _sha(sorted(sorted(ticket) for ticket in tickets))


@dataclass(frozen=True, slots=True)
class SupportMap:
    tickets: Permutation  # source ticket -> target ticket (0-based)
    numbers: Permutation  # numbers[n-1] is source number n's target (1-based)


def verify_support_map(source: Portfolio, target: Portfolio, mapping: SupportMap) -> None:
    supports(source)
    supports(target)
    if sorted(mapping.tickets) != list(range(20)) or sorted(mapping.numbers) != list(range(1, 50)):
        raise CoverageError("support map: ticket and number maps must both be bijections")
    if any(
        {mapping.numbers[n - 1] for n in source[v]} != set(target[mapping.tickets[v]])
        for v in range(20)
    ):
        raise CoverageError("support map: complete number supports are not preserved")


def support_map(source: Portfolio, target: Portfolio, tickets: Permutation) -> SupportMap:
    if sorted(tickets) != list(range(20)) or any(
        PROFILE[v] != PROFILE[w] for v, w in enumerate(tickets)
    ):
        raise CoverageError("support map: ticket bijection must preserve triple degrees")
    target_labels = {tuple(v for v, t in enumerate(target) if n in t): n for n in range(1, 50)}
    if len(target_labels) != 49:
        raise CoverageError("support map: target number supports must be distinct")
    numbers: list[int] = []
    for n in range(1, 50):
        image = tuple(sorted(tickets[v] for v, t in enumerate(source) if n in t))
        if image not in target_labels:
            raise CoverageError(f"support map: number {n} has no matching full support")
        numbers.append(target_labels[image])
    mapping = SupportMap(tickets, tuple(numbers))
    verify_support_map(source, target, mapping)
    return mapping


def compose(first: SupportMap, second: SupportMap) -> SupportMap:
    return SupportMap(
        tuple(second.tickets[v] for v in first.tickets),
        tuple(second.numbers[n - 1] for n in first.numbers),
    )


@dataclass(frozen=True, slots=True)
class Candidate:
    key: Key
    tickets: Portfolio
    structure: census.Structure
    canonical: engine.CanonicalWitness


@dataclass(frozen=True, slots=True)
class Representative:
    class_id: str
    candidate: Candidate


@dataclass(frozen=True, slots=True)
class Coverage:
    constructor: Constructor
    sts: PreservedSTS
    candidates: tuple[Candidate, ...]
    representatives: tuple[Representative, ...]
    point_orbits: Mapping[str, tuple[tuple[int, ...], ...]]
    sts_forms: Mapping[str, engine.CanonicalForm]
    classification: ExternalClassification
    rigidity_record: Mapping[str, object]

    def representative(self, candidate: Candidate) -> Representative:
        matches = [
            r
            for r in self.representatives
            if r.candidate.canonical.structure == candidate.canonical.structure
        ]
        if len(matches) != 1:
            raise CoverageError(
                f"finite quotient: {candidate.key} has {len(matches)} representatives"
            )
        return matches[0]


def build_coverage(
    root: Path,
    *,
    profile_id: str = PROFILE_ID,
    t: int = TARGET_T,
    classification: ExternalClassification | None = CLASSIFICATION,
) -> Coverage:
    check_scope(profile_id, t, classification)
    blobs = read_sources(root)
    record = reuse_rigidity()
    constructor, sts = load_donors(blobs)
    forms = {name: engine.canonical_form(13, design) for name, design in sts.STS13_DESIGNS.items()}
    if len({form.lines for form in forms.values()}) != CLASSIFICATION.unpointed_classes:
        raise CoverageError("preserved unpointed STS representatives are not distinct")
    candidates: list[Candidate] = []
    representatives: list[Representative] = []
    for name, design in sts.STS13_DESIGNS.items():
        for point in range(13):
            tickets = delete_h(design, point, constructor)
            structure = supports(tickets)
            candidate = Candidate(
                (name, point), tickets, structure, engine.canonicalize(PROFILE, structure)
            )
            candidates.append(candidate)
            if all(
                candidate.canonical.structure != r.candidate.canonical.structure
                for r in representatives
            ):
                representatives.append(Representative(f"C{len(representatives) + 1}", candidate))
    verify_complete_keys(c.key for c in candidates)
    orbits: dict[str, tuple[tuple[int, ...], ...]] = {}
    for name, design in sts.STS13_DESIGNS.items():
        group = sts.sts13_automorphisms(design)
        orbits[name] = tuple(sorted({tuple(sorted({g[p] for g in group})) for p in range(13)}))
        if sorted(p for orbit in orbits[name] for p in orbit) != list(range(13)):
            raise CoverageError(f"point orbit partition is incomplete: {name}")
        for left, right in combinations((c for c in candidates if c.key[0] == name), 2):
            same_orbit = any(
                left.key[1] in orbit and right.key[1] in orbit for orbit in orbits[name]
            )
            if same_orbit != (left.canonical.structure == right.canonical.structure):
                raise CoverageError(
                    f"point orbit / exact support quotient disagree: {left.key}, {right.key}"
                )
    if len(representatives) != sum(map(len, orbits.values())) or len(representatives) != 5:
        raise CoverageError(
            "26 pointed keys do not yield exactly five classes matching point orbits"
        )
    for partition in u_partitions():
        u_mapping(partition, u_pairs(partition))
    if len(u_partitions()) != comb(len(POSITIVE_U), 3) // 2:
        raise CoverageError("U partition enumeration is incomplete")
    return Coverage(
        constructor,
        sts,
        tuple(candidates),
        tuple(representatives),
        orbits,
        forms,
        cast(ExternalClassification, classification),
        record,
    )


@dataclass(frozen=True, slots=True)
class ModelToRepresentative:
    key: Key
    class_id: str
    extension: Design
    sts_point_map: Permutation
    to_raw_key: SupportMap
    raw_to_representative: SupportMap
    composed: SupportMap


def cover_solution(
    tickets: Portfolio, coverage: Coverage, *, profile_id: str = PROFILE_ID, t: int = TARGET_T
) -> ModelToRepresentative:
    """Return the checked complete mapping chain for any actual fixed CELL_A model solution."""
    check_scope(profile_id, t, coverage.classification)
    rigidity.verify_certificate(coverage.rigidity_record)
    verify_complete_keys(c.key for c in coverage.candidates)
    structure = supports(tickets)
    extension = extend_h(structure, coverage.constructor)
    form = engine.canonical_form(13, extension)
    names = [name for name, other in coverage.sts_forms.items() if form.lines == other.lines]
    if len(names) != 1:
        raise CoverageError(
            "external-classification bridge: extension matches no unique preserved STS"
        )
    name = names[0]
    inverse = [0] * 13
    for v, label in enumerate(coverage.sts_forms[name].labeling):
        inverse[label] = v
    point_map = tuple(inverse[label] for label in form.labeling)
    design = coverage.sts.STS13_DESIGNS[name]
    if sorted(point_map) != list(range(13)) or {
        tuple(sorted(point_map[v] for v in block)) for block in extension
    } != set(design):
        raise CoverageError("H pointed isomorphism does not map all extension blocks")
    key = (name, point_map[12])
    raw = next(c for c in coverage.candidates if c.key == key)
    remaining = [v for v in range(13) if v != key[1]]
    ticket_map = list(
        u_mapping(
            tuple(t for t in structure.triples if set(t) <= U),
            tuple(p for p in structure.pairs if set(p) <= U),
        )
    )
    for v in H:
        ticket_map[v] = remaining.index(point_map[v])
    to_raw = support_map(tickets, raw.tickets, tuple(ticket_map))
    representative = coverage.representative(raw)
    raw_map = engine.isomorphism(
        raw.canonical,
        raw.structure,
        representative.candidate.canonical,
        representative.candidate.structure,
    )
    to_rep = support_map(raw.tickets, representative.candidate.tickets, raw_map)
    combined = compose(to_raw, to_rep)
    verify_support_map(tickets, representative.candidate.tickets, combined)
    return ModelToRepresentative(
        key, representative.class_id, extension, point_map, to_raw, to_rep, combined
    )


def certificate(coverage: Coverage) -> dict[str, object]:
    """Replay every finite-key arrow and serialize derived evidence; no expected PASS field."""
    check_scope(PROFILE_ID, TARGET_T, coverage.classification)
    verify_complete_keys(c.key for c in coverage.candidates)
    rows: list[dict[str, object]] = []
    for candidate in coverage.candidates:
        rep = coverage.representative(candidate)
        mapping = engine.isomorphism(
            candidate.canonical,
            candidate.structure,
            rep.candidate.canonical,
            rep.candidate.structure,
        )
        witness = support_map(candidate.tickets, rep.candidate.tickets, mapping)
        chain = cover_solution(candidate.tickets, coverage)
        if chain.class_id != rep.class_id:
            raise CoverageError("model chain and direct exact class map disagree")
        rows.append(
            {
                "KEY": candidate.key,
                "NORMALIZED_SHA256": normalized_sha(candidate.tickets),
                "CLASS_ID": rep.class_id,
                "CANONICAL_ID": candidate.canonical.witness_id,
                "TO_REPRESENTATIVE": asdict(witness),
                "MODEL_MAPPING_CHAIN": asdict(chain),
            }
        )
    record: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "PROFILE_ID": PROFILE_ID,
        "TARGET_T": TARGET_T,
        "SUPPORT_MODEL": "22 distinct F3 supports, 27 distinct F2 supports; degree d and 6-d; "
        "each ticket pair covered at most once; frozen open-wedge ceiling 6",
        "SOURCES": [asdict(pin) for pin in SOURCES],
        "RIGIDITY_CERTIFICATE_REUSED": coverage.rigidity_record,
        "EXTERNAL_CLASSIFICATION_DEPENDENCY": asdict(coverage.classification),
        "EXTERNAL_CLASSIFICATION_URL": CLASSIFICATION_URL,
        "H_EXTENSION_DELETION": "20 triples + infinity on 6 matching edges; pair-exact STS(13); "
        "point-preserving isomorphism restricts to both support types",
        "U_SIDE_UNIQUENESS": {
            "POSITIVE_VERTICES": POSITIVE_U,
            "ZERO_VERTICES": ZERO_U,
            "PARTITION_COUNT": len(u_partitions()),
            "OVERLAP_EDGE_COUNT": len(_u_edges()),
            "PAIR_SUPPORT_COUNT": len(u_pairs(u_partitions()[0])),
            "PARTITIONS_AND_MAPS": [
                {
                    "TRIPLES": part,
                    "PAIRS": u_pairs(part),
                    "TICKET_MAP": u_mapping(part, u_pairs(part)),
                }
                for part in u_partitions()
            ],
        },
        "POINT_ORBITS": dict(coverage.point_orbits),
        "RAW_KEYS": len(rows),
        "NORMALIZED_SHA_COUNT": len({r["NORMALIZED_SHA256"] for r in rows}),
        "ISOMORPHISM_CLASS_COUNT": len(coverage.representatives),
        "POINTED_KEYS": rows,
        "REPRESENTATIVES": [
            {
                "CLASS_ID": r.class_id,
                "KEY": r.candidate.key,
                "CANONICAL_ID": r.candidate.canonical.witness_id,
                "SUPPORTS": r.candidate.structure.as_json(),
            }
            for r in coverage.representatives
        ],
        "MODEL_TO_REPRESENTATIVE_COVERAGE": "conditional on external STS classification; "
        "rigidity -> component exclusion -> pointed H extension -> preserved STS/deletion "
        "key + explicit U map -> exact full-support class map; ticket and number bijections",
        "SUBSET_RESTRICTIONS": "lex-leaders and no-goods only remove covered solutions",
        "CELL_A_SCORE_CLOSURE": "NOT_CLAIMED_BY_THIS_TASK",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "OTHER_PROFILES_TARGETS_OR_SUPPORT_MODELS": "NOT_COVERED",
    }
    return {**record, "CERTIFICATE_SHA256": _sha(record)}


def verify_certificate(record: Mapping[str, object], coverage: Coverage) -> None:
    expected = certificate(coverage)
    if _sha(record) != _sha(expected):
        raise CoverageError("coverage certificate differs from replayed evidence")


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    print(json.dumps(certificate(build_coverage(root)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
