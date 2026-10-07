"""K20 fiber near-top-S3 band realization census engine (Slice 1).

On the minimum-S2 fiber every number lies on two or three tickets and two
tickets share at most one number. Up to relabelling the 49 numbers, a portfolio
is therefore its support structure: 22 triple lines and 27 pair lines over the
20 tickets. R30 bounds every triple-degree profile by its certified
graph-triangle cap. Its bound owner is the canonical incumbent's own profile
55555555555511111100, so no other profile reaches the incumbent's S3. A fiber
gain needs a realization with less slack.

This engine walks the frozen Slice-1 profiles in descending R30 bound order,
starting with the incumbent profile. For each profile it chases the maximum
realizable triangle count T inside the slice with R28's exact support model,
and extracts at most 16 distinct structures at that T. It ranks them by the
K4-quartet S4 proxy, maps each to a portfolio (triple line n -> number n+1,
then pair lines) and counts that portfolio with the official exact evaluator.
Only the exact count can accept a witness. A gain is a count of at least
313,263,889, strictly above the 313,263,888 start. The proxy orders the
evaluations and nothing else.

Slice 1 comes from the sealed R30 result's data and committed R28 bound code
alone. No R30 module is imported: the R30 producer module is unresolved and is
not an execution authority. Every authority is pinned by full SHA-256 in the
frozen manifest, and the manifest is pinned here. Every solve uses one CP-SAT
worker, a fixed seed and a 120 s native limit, with one 600 s retry after
UNKNOWN. Only INFEASIBLE refutes a T, and only FEASIBLE or OPTIMAL realizes one.
Every completed solve and witness is appended to a hash-chained, fsynced JSONL
log before it is used. A restarted run serves logged keys without solving. A
corrupt, reordered, truncated or duplicate line fails closed. Slice 2 is
disabled and cannot run.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from importlib import import_module
from itertools import combinations, pairwise
from math import comb
from pathlib import Path
from typing import Any, cast

TASK_ID = "B649_K20_FIBER_NEAR_TOP_S3_BAND_REALIZATION_CENSUS_R1"
PREP_TASK_ID = "B649_K20_FIBER_CENSUS_PREP_AUTHORITY_DECOUPLING_R1"
MANIFEST_RELATIVE = (
    "docs/research/matrix-native-results/b649-k20-fiber-near-top-s3-census-slice1-manifest.json"
)
MANIFEST_SHA256 = "4b1df0503ab0c4a780e56b6189821f1d2f9080c2124dc6951d8663580e79e64f"
DURABLE_RELATIVE = ".task-data/b649-k20-fiber-near-top-s3-census-r1"
PROOF_LOG = "proof-log.jsonl"
WITNESS_LEDGER = "witness-ledger.jsonl"
SUMMARY = "summary.json"
LOCK = "census.lock"

TICKET_COUNT = 20
TICKET_CAPACITY = 6
TRIPLE_LINES = 22
PAIR_LINES = 27
POOL_SIZE = 49
DEGREE_SUM = 3 * TRIPLE_LINES

START_COUNT = 313_263_888
STRICT_GAIN_THRESHOLD = START_COUNT + 1
SLICE1_FLOOR = 313_577_032
SLICE2_FLOOR = 313_540_184
WITNESS_CAP = 16
SOLVE_SECONDS = 120.0
RETRY_SECONDS = 600.0
RANDOM_SEED = 649
SEARCH_WORKERS = 1
THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
REALIZED = ("OPTIMAL", "FEASIBLE")
INFEASIBLE = "INFEASIBLE"
UNKNOWN = "UNKNOWN"
GENESIS = "0" * 64

R28_COMMIT = "155f6f1cc083f4dcd17918484e26be0810c08854"
R28_TREE = "548fdbe01805b52b447318f18fca4e83100dd0e2"
R28_BRANCH = "codex/b649-k20-min-s2-current-cursor-class-owner-chase-r28"
R28_MODULE_RELATIVE = (
    "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py"
)
R28_MODULE_SHA256 = "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0"
R28_RESULT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-current-cursor-class-owner-chase-r28-result.json"
)
R28_RESULT_SHA256 = "edf54e9f34d41f27440b603695076d378fa42ce47922d69e36f16cb2f5cd6dce"
R28_BOUND_MODULE_RELATIVE = (
    "src/lottolab/research/b649_k20_min_s2_resolved_above_cursor_owner_chase_r20.py"
)
R28_BOUND_MODULE_SHA256 = "b63081af598a6366ab9989f00f3e269052e8edbc41956a0771941dc03891b74e"
R28_SOURCE_PATHS = ("src/lottolab/__init__.py", "src/lottolab/research")
R30_ROOT = Path(__file__).resolve().parents[3]
R30_BRANCH = "codex/b649-k20-min-s2-current-cursor-dynamic-family-max-r30"
R30_BASE_HEAD = "cbea83281a9ea7959de584a6b66d500f7bd0e6e1"
R30_RESULT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
R30_RESULT_SHA256 = "5b7e5d10583d275409441c422e107994fb6058fae5060933c6c35c436481e777"
R30_LEDGER_SHA256 = "375ccbe04ac1e5216ef66d69e9d5576ce7e5bd0fb6813925f53af64301f359b0"
R30_MODULE_AUTHORITY_STATUS = "UNRESOLVED_NON_LOAD_BEARING"
R30_MODULE_AUTHORITY_REASON = (
    "The sealed R30 result is available and content-addressed. Slice 1 is derived from its data "
    "by committed R28 bound code; neither the freeze nor the census imports or loads R30 code. "
    "Four discovered R30 module versions replay the sealed result to the same ledger and the "
    "same 992-profile Slice-1 input, but none can be proven to be the producer. R30 module "
    "identity is therefore historical provenance, not execution authority, and no R30 module "
    "is bound."
)
EVALUATOR_RELATIVE = "src/lottolab/research/b649_official_any_prize_exact.py"
EVALUATOR_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
EVALUATOR_BLOB = "3d053b2d9bc2182fc00b22889e837be5d0ba10aa"
START_RELATIVE = (
    "docs/research/matrix-native-results/b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
START_FILE_SHA256 = "3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00"
START_FIELD = "SEARCH_START_TICKETS"
START_NORMALIZED_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
MODEL_PROBES = (
    (
        "66665555554440000000",
        30,
        "a3b4693b3711c28dfaedab0deac3e6cce30067c2baae2d46f08a96103d3c2eb0",
    ),
    ("55555555555511111100", 6, "381ee9ef753d6b1904fb7c5f8037a01eee0183f96963411e1eb56b303760fe89"),
)
PROXY_WEIGHTS = {"K4_WITH_CONTAINED_TRIPLE": 448, "K4_WITHOUT_CONTAINED_TRIPLE": 679}

Profile = tuple[int, ...]
Triple = tuple[int, int, int]
Pair = tuple[int, int]
Tickets = tuple[tuple[int, ...], ...]
Key = tuple[str | int, ...]
Evaluator = Callable[[Tickets], int]


class CensusError(RuntimeError):
    """Fail-closed census error: the run must stop."""


class ManifestError(CensusError):
    """The frozen manifest is missing, changed or invalid."""


class DurableLogError(CensusError):
    """A durable log line is corrupt, reordered, truncated or duplicated."""


class Slice2NotAuthorized(CensusError):
    """Only Slice 1 is authorized."""


class PreflightError(CensusError):
    """A launch preflight failed."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _obj(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ManifestError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ManifestError(f"{name} must be a list")
    return cast(list[object], value)


def _int(value: object, name: str) -> int:
    if type(value) is not int:
        raise ManifestError(f"{name} must be an integer")
    return value


def _str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"{name} must be a string")
    return value


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def engine_sha256() -> str:
    return sha256_bytes(Path(__file__).read_bytes())


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def compact_tickets_sha256(tickets: Sequence[Sequence[int]]) -> str:
    return sha256_bytes(json.dumps([list(t) for t in tickets], separators=(",", ":")).encode())


# Profiles, structures and their realizations -------------------------------------------


def decode_profile(value: str) -> Profile:
    if len(value) != TICKET_COUNT or not value.isdecimal():
        raise CensusError(f"malformed degree profile: {value!r}")
    profile = tuple(map(int, value))
    if (
        sum(profile) != DEGREE_SUM
        or tuple(sorted(profile, reverse=True)) != profile
        or any(d > TICKET_CAPACITY for d in profile)
    ):
        raise CensusError(f"invalid minimum-S2 degree profile: {value}")
    return profile


def profile_id(profile: Profile) -> str:
    return "".join(map(str, profile))


def wedge_count(profile: Profile) -> int:
    """W = sum C(6 + d, 2): every ticket has overlap degree 6 + d on the fiber."""

    return sum(comb(TICKET_CAPACITY + d, 2) for d in profile)


@dataclass(frozen=True, slots=True)
class Structure:
    """Sorted triple lines and pair lines over tickets 0..19."""

    triples: tuple[Triple, ...]
    pairs: tuple[Pair, ...]

    def as_json(self) -> dict[str, list[list[int]]]:
        return {"TRIPLES": [list(t) for t in self.triples], "PAIRS": [list(p) for p in self.pairs]}

    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.as_json()).encode())

    @staticmethod
    def from_json(value: object) -> Structure:
        data = _obj(value, "structure")
        triples = tuple(
            cast(Triple, tuple(_int(v, "triple") for v in _list(t, "triple")))
            for t in _list(data["TRIPLES"], "TRIPLES")
        )
        pairs = tuple(
            cast(Pair, tuple(_int(v, "pair") for v in _list(p, "pair")))
            for p in _list(data["PAIRS"], "PAIRS")
        )
        return Structure(triples, pairs)


@dataclass(frozen=True, slots=True)
class Realization:
    triangles: int
    open_wedges: int
    k4_with_contained_triple: int
    k4_without_contained_triple: int
    proxy_s4: int


def validate_structure(profile: Profile, structure: Structure) -> None:
    """Fail closed unless ``structure`` is a fiber support structure with this profile."""

    lines = (*structure.triples, *structure.pairs)
    if (
        len(structure.triples) != TRIPLE_LINES
        or len(structure.pairs) != PAIR_LINES
        or tuple(sorted(structure.triples)) != structure.triples
        or tuple(sorted(structure.pairs)) != structure.pairs
        or any(
            len(set(line)) != len(line)
            or tuple(sorted(line)) != line
            or not all(0 <= v < TICKET_COUNT for v in line)
            for line in lines
        )
    ):
        raise CensusError("structure is not 22 sorted triple lines and 27 sorted pair lines")
    for v in range(TICKET_COUNT):
        on_triples = sum(v in t for t in structure.triples)
        if on_triples != profile[v] or on_triples + sum(v in p for p in structure.pairs) != 6:
            raise CensusError("structure does not realize the degree profile")
    covered = [p for line in lines for p in combinations(line, 2)]
    if len(covered) != len(set(covered)):
        raise CensusError("two tickets share more than one number")


def edges(structure: Structure) -> set[Pair]:
    return {p for t in structure.triples for p in combinations(t, 2)} | set(structure.pairs)


def realization(profile: Profile, structure: Structure) -> Realization:
    """Exact triangle and K4 census of the overlap graph, and the K4-quartet S4 proxy."""

    validate_structure(profile, structure)
    adjacent: list[set[int]] = [set() for _ in range(TICKET_COUNT)]
    for a, b in edges(structure):
        adjacent[a].add(b)
        adjacent[b].add(a)
    if [len(n) for n in adjacent] != [TICKET_CAPACITY + d for d in profile]:
        raise CensusError("overlap degrees differ from 6 + triple degree")
    triangles = [
        (a, b, c)
        for a in range(TICKET_COUNT)
        for b in adjacent[a]
        if b > a
        for c in adjacent[a] & adjacent[b]
        if c > b
    ]
    lines = {frozenset(t) for t in structure.triples}
    with_triple = without_triple = 0
    for a, b, c in triangles:
        for d in adjacent[a] & adjacent[b] & adjacent[c]:
            if d > c:
                if any(frozenset(q) in lines for q in combinations((a, b, c, d), 3)):
                    with_triple += 1
                else:
                    without_triple += 1
    open_wedges = wedge_count(profile) - 3 * len(triangles)
    if open_wedges < 0:
        raise CensusError("triangle count exceeds the wedge identity")
    return Realization(
        triangles=len(triangles),
        open_wedges=open_wedges,
        k4_with_contained_triple=with_triple,
        k4_without_contained_triple=without_triple,
        proxy_s4=PROXY_WEIGHTS["K4_WITH_CONTAINED_TRIPLE"] * with_triple
        + PROXY_WEIGHTS["K4_WITHOUT_CONTAINED_TRIPLE"] * without_triple,
    )


def portfolio(structure: Structure) -> Tickets:
    """Triple line n is number n + 1; pair lines follow as numbers 23..49."""

    labels: list[tuple[int, ...]] = [*structure.triples, *structure.pairs]
    if len(labels) != POOL_SIZE:
        raise CensusError("a fiber structure uses all 49 numbers")
    tickets = tuple(
        tuple(n + 1 for n, label in enumerate(labels) if v in label) for v in range(TICKET_COUNT)
    )
    if any(len(t) != TICKET_CAPACITY for t in tickets):
        raise CensusError("structure-to-portfolio mapping must give six numbers per ticket")
    return tickets


def structure_from_tickets(tickets: Sequence[Sequence[int]]) -> tuple[Profile, Structure]:
    """The support structure of a fiber portfolio, tickets ordered by triple degree."""

    sets = [set(t) for t in tickets]
    if len(sets) != TICKET_COUNT or any(len(s) != TICKET_CAPACITY for s in sets):
        raise CensusError("a K20 portfolio has 20 tickets of six distinct numbers")
    holders = {n: tuple(i for i, s in enumerate(sets) if n in s) for n in range(1, POOL_SIZE + 1)}
    if any(len(h) not in (2, 3) for h in holders.values()):
        raise CensusError("portfolio is off the minimum-S2 fiber")
    degree = [sum(len(holders[n]) == 3 for n in s) for s in sets]
    order = sorted(range(TICKET_COUNT), key=lambda i: (-degree[i], i))
    position = {old: new for new, old in enumerate(order)}
    lines = [tuple(sorted(position[i] for i in h)) for h in holders.values()]
    structure = Structure(
        tuple(sorted(line for line in lines if len(line) == 3)),
        tuple(sorted(line for line in lines if len(line) == 2)),
    )
    profile = tuple(degree[i] for i in order)
    validate_structure(profile, structure)
    return profile, structure


# R28's exact support model and the single-worker solver ----------------------------------


def support_model(
    profiles: Sequence[Profile], ceiling: int
) -> tuple[Any, dict[Triple, Any], dict[Pair, Any], list[Any], list[Any]]:
    """R28 ``support_union_model`` at 155f6f1c, verbatim; its proto text is pinned.

    At most ``ceiling`` open wedges means at least (W - ceiling) / 3 graph triangles.
    """

    if not profiles or ceiling < 0:
        raise AssertionError("invalid group model")
    profiles = tuple(decode_profile(profile_id(p)) for p in profiles)
    if len({wedge_count(p) for p in profiles}) != 1:
        raise AssertionError("group lacks a shared wedge identity")
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model: Any = cp_model.CpModel()
    degrees = [
        model.NewIntVar(min(p[v] for p in profiles), max(p[v] for p in profiles), f"d{v}")
        for v in range(20)
    ]
    model.AddAllowedAssignments(degrees, profiles)
    active = [v for v in range(20) if any(p[v] for p in profiles)]
    triples = {t: model.NewBoolVar(f"t{t}") for t in combinations(active, 3)}
    doubles = {p: model.NewBoolVar(f"b{p}") for p in combinations(range(20), 2)}
    by_pair: dict[Pair, list[Any]] = {p: [] for p in doubles}
    for t, variable in triples.items():
        for pair in combinations(t, 2):
            by_pair[pair].append(variable)
    for v, degree in enumerate(degrees):
        model.Add(sum(x for t, x in triples.items() if v in t) == degree)
        model.Add(sum(x for p, x in doubles.items() if v in p) == 6 - degree)
    model.Add(sum(triples.values()) == 22)
    model.Add(sum(doubles.values()) == 27)
    edges_: dict[Pair, Any] = {}
    for p, double in doubles.items():
        model.Add(sum(by_pair[p]) + double <= 1)
        edges_[p] = model.NewBoolVar(f"e{p}")
        model.Add(edges_[p] == sum(by_pair[p]) + double)
    indicators: list[Any] = []
    by_ends: dict[Pair, list[Any]] = {p: [] for p in doubles}
    for center in range(20):
        for a, b in combinations((v for v in range(20) if v != center), 2):
            x = model.NewBoolVar(f"o{center}_{a}_{b}")
            model.Add(
                x
                >= edges_[(min(center, a), max(center, a))]
                + edges_[(min(center, b), max(center, b))]
                - edges_[(a, b)]
                - 1
            )
            indicators.append(x)
            by_ends[(a, b)].append(x)
    for (a, b), edge in edges_.items():
        model.Add(sum(by_ends[(a, b)]) >= degrees[a] + degrees[b] - 6).OnlyEnforceIf(edge.Not())
    model.Add(sum(indicators) <= ceiling)
    return model, triples, doubles, degrees, indicators


def model_proto_sha256(profile: str, ceiling: int) -> str:
    model: Any = support_model((decode_profile(profile),), ceiling)[0]
    return sha256_bytes(str(model.Proto()).encode())


def configured_solver(seconds: float) -> Any:
    """R26's solver settings with one worker. Setting num_workers as well is MODEL_INVALID."""

    cp_model: Any = import_module("ortools.sat.python.cp_model")
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = SEARCH_WORKERS
    solver.parameters.random_seed = RANDOM_SEED
    solver.parameters.log_search_progress = False
    return solver


def observed_search_workers() -> int:
    """Solve a one-variable model and read the worker count from CP-SAT's own log."""

    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model: Any = cp_model.CpModel()
    model.NewBoolVar("probe")
    solver = configured_solver(5.0)
    solver.parameters.log_search_progress = True
    solver.parameters.log_to_stdout = False
    lines: list[str] = []
    solver.log_callback = lines.append
    status = str(solver.StatusName(solver.Solve(model)))
    workers = [
        int(line.rsplit("with ", 1)[1].split()[0])
        for line in lines
        if line.startswith("Starting search at") and "workers" in line
    ]
    if status not in REALIZED or len(workers) != 1:
        raise PreflightError("CP-SAT did not report its search worker count")
    return workers[0]


def add_nogood(
    model: Any, triples: Mapping[Triple, Any], pairs: Mapping[Pair, Any], structure: Structure
) -> None:
    """Exclude exactly this structure: one of its 49 lines must be absent."""

    literals = [triples[t] for t in structure.triples] + [pairs[p] for p in structure.pairs]
    model.Add(sum(literals) <= len(literals) - 1)


def decode_structure(
    solver: Any, triples: Mapping[Triple, Any], pairs: Mapping[Pair, Any]
) -> Structure:
    return Structure(
        tuple(sorted(t for t, v in triples.items() if solver.BooleanValue(v))),
        tuple(sorted(p for p, v in pairs.items() if solver.BooleanValue(v))),
    )


@dataclass(frozen=True, slots=True)
class SolveRequest:
    """Realize at least ``triangles`` graph triangles, excluding earlier structures."""

    profile: Profile
    triangles: int
    excluded: tuple[Structure, ...]
    seconds: float

    @property
    def ceiling(self) -> int:
        return wedge_count(self.profile) - 3 * self.triangles

    def digest(self) -> str:
        return sha256_bytes(
            canonical_json(
                {
                    "PROFILE_ID": profile_id(self.profile),
                    "T": self.triangles,
                    "CEILING": self.ceiling,
                    "EXCLUDED": [s.digest() for s in self.excluded],
                    "SECONDS": self.seconds,
                    "RANDOM_SEED": RANDOM_SEED,
                    "SEARCH_WORKERS": SEARCH_WORKERS,
                }
            ).encode()
        )


@dataclass(frozen=True, slots=True)
class SolveOutcome:
    status: str
    structure: Structure | None
    wall_seconds: float


Solver = Callable[[SolveRequest], SolveOutcome]
ModelBuilder = Callable[[Profile, int], tuple[Any, Mapping[Triple, Any], Mapping[Pair, Any]]]


def k20_model(
    profile: Profile, ceiling: int
) -> tuple[Any, Mapping[Triple, Any], Mapping[Pair, Any]]:
    model, triples, pairs, _, _ = support_model((profile,), ceiling)
    return model, triples, pairs


def cp_sat_solve(request: SolveRequest, build: ModelBuilder = k20_model) -> SolveOutcome:
    model, triples, pairs = build(request.profile, request.ceiling)
    for structure in request.excluded:
        add_nogood(model, triples, pairs, structure)
    solver = configured_solver(request.seconds)
    status = str(solver.StatusName(solver.Solve(model)))
    structure = decode_structure(solver, triples, pairs) if status in REALIZED else None
    return SolveOutcome(status, structure, float(solver.WallTime()))


# Official evaluator and acceptance ---------------------------------------------------------


def official_evaluator() -> Evaluator:
    """Exact OFFICIAL_ANY_PRIZE outcome count by the pinned evaluator, one shared draw space."""

    from . import b649_official_any_prize_exact as exact

    draws = exact.all_main_draw_masks(exact.BIG_LOTTO_POOL_SIZE, exact.BIG_LOTTO_DRAW_SIZE)

    def evaluate(tickets: Tickets) -> int:
        return int(exact.evaluate_portfolio(tickets, draws=draws).official_any_prize_outcome_count)

    return evaluate


def is_gain(exact_count: int) -> bool:
    """The only acceptance rule: an exact count strictly above the 313,263,888 start."""

    return exact_count >= STRICT_GAIN_THRESHOLD


def k4_quartet_portfolios() -> dict[str, Tickets]:
    """The two K4 quartet profiles on the fiber, as four-ticket portfolios."""

    shapes = {
        # Number 1 lies on tickets 0, 1, 2; numbers 2, 3, 4 pair ticket 3 with each of them.
        "K4_WITH_CONTAINED_TRIPLE": ((1, 2), (1, 3), (1, 4), (2, 3, 4)),
        # Six pair numbers, one per ticket pair.
        "K4_WITHOUT_CONTAINED_TRIPLE": ((1, 2, 3), (1, 4, 5), (2, 4, 6), (3, 5, 6)),
    }
    portfolios: dict[str, Tickets] = {}
    for name, quartet in shapes.items():
        singles = iter(range(30, 50))
        portfolios[name] = tuple(
            tuple(sorted((*shared, *(next(singles) for _ in range(6 - len(shared))))))
            for shared in quartet
        )
    return portfolios


def quartet_all_win_count(tickets: Tickets, evaluate: Evaluator) -> int:
    """|A & B & C & D| by inclusion-exclusion over exact unions."""

    return sum(
        (-1) ** (size + 1) * evaluate(tuple(tickets[i] for i in subset))
        for size in range(1, 5)
        for subset in combinations(range(4), size)
    )


# Frozen manifest ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SliceRow:
    profile_id: str
    profile: Profile
    r30_bound: int
    cap: int
    band: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class Manifest:
    sha256: str
    data: Mapping[str, object]
    rows: tuple[SliceRow, ...]
    floor: int
    witness_cap: int
    threshold: int


def rows_sha256(rows: Sequence[object]) -> str:
    return sha256_bytes(canonical_json(list(rows)).encode())


def render_manifest(manifest: Mapping[str, object]) -> bytes:
    """Canonical bytes: sorted keys, one compact Slice-1 row per line."""

    slice1 = dict(_obj(manifest["SLICE1"], "SLICE1"))
    rows = _list(slice1["PROFILES"], "PROFILES")
    marker = "__SLICE1_PROFILES__"
    skeleton = {**manifest, "SLICE1": {**slice1, "PROFILES": marker}}
    body = ",\n".join("   " + json.dumps(row, separators=(",", ":")) for row in rows)
    text = json.dumps(skeleton, indent=1, sort_keys=True)
    if text.count(json.dumps(marker)) != 1:
        raise ManifestError("manifest marker collision")
    return (text.replace(json.dumps(marker), "[\n" + body + "\n  ]") + "\n").encode()


def _row(raw: object) -> SliceRow:
    fields = _list(raw, "Slice-1 row")
    if len(fields) != 4:
        raise ManifestError("Slice-1 rows are [profile, R30 bound, cap, band]")
    pid = _str(fields[0], "profile")
    band = tuple(
        (_int(_list(b, "band")[0], "T"), _int(_list(b, "band")[1], "bound"))
        for b in _list(fields[3], "band")
    )
    return SliceRow(
        pid, decode_profile(pid), _int(fields[1], "bound"), _int(fields[2], "cap"), band
    )


def validate_manifest(data: Mapping[str, object], sha: str) -> Manifest:
    """Every launch-relevant manifest value must equal the engine's pinned contract."""

    solver = _obj(data["SOLVER"], "SOLVER")
    witness = _obj(data["WITNESS"], "WITNESS")
    acceptance = _obj(data["ACCEPTANCE"], "ACCEPTANCE")
    slice1 = _obj(data["SLICE1"], "SLICE1")
    slice2 = _obj(data["SLICE2"], "SLICE2")
    start = _obj(_obj(data["AUTHORITIES"], "AUTHORITIES")["CANONICAL_START"], "CANONICAL_START")
    expected: list[tuple[object, object, str]] = [
        (data.get("SCHEMA_VERSION"), 1, "schema"),
        (data.get("TASK_ID"), TASK_ID, "task"),
        (solver.get("NUM_SEARCH_WORKERS"), SEARCH_WORKERS, "search workers"),
        (solver.get("RANDOM_SEED"), RANDOM_SEED, "seed"),
        (solver.get("SOLVE_SECONDS"), SOLVE_SECONDS, "solve timeout"),
        (solver.get("RETRY_SECONDS"), RETRY_SECONDS, "retry timeout"),
        (solver.get("THREAD_ENV"), dict.fromkeys(THREAD_ENV, "1"), "thread env"),
        (witness.get("CAP"), WITNESS_CAP, "witness cap"),
        (witness.get("PROXY_ROLE"), "RANK_ONLY", "proxy role"),
        (witness.get("PROXY_WEIGHTS"), PROXY_WEIGHTS, "proxy weights"),
        (acceptance.get("START_COUNT"), START_COUNT, "start count"),
        (acceptance.get("STRICT_GAIN_THRESHOLD"), STRICT_GAIN_THRESHOLD, "gain threshold"),
        (acceptance.get("EVALUATOR_SHA256"), EVALUATOR_SHA256, "evaluator"),
        (slice1.get("FLOOR"), SLICE1_FLOOR, "Slice-1 floor"),
        (slice2.get("ENABLED"), False, "Slice 2"),
        (slice2.get("FLOOR"), SLICE2_FLOOR, "Slice-2 floor"),
        (start.get("COUNT"), START_COUNT, "start count"),
        (start.get("NORMALIZED_SHA256"), START_NORMALIZED_SHA256, "start portfolio"),
    ]
    for observed, value, name in expected:
        if type(observed) is not type(value) or observed != value:
            raise ManifestError(f"manifest {name} differs from the engine contract")
    raw_rows = _list(slice1["PROFILES"], "PROFILES")
    rows = tuple(_row(r) for r in raw_rows)
    ids = [r.profile_id for r in rows]
    if (
        not rows
        or len(set(ids)) != len(ids)
        or slice1.get("PROFILE_COUNT") != len(rows)
        or slice1.get("PROFILES_SHA256") != rows_sha256(raw_rows)
        or slice1.get("INCUMBENT_FIRST_PROFILE") != rows[0].profile_id
        or start.get("PROFILE_ID") != rows[0].profile_id
        or any(a.r30_bound < b.r30_bound for a, b in pairwise(rows))
    ):
        raise ManifestError("Slice-1 rows are not the pinned descending incumbent-first list")
    for row in rows:
        ts = [t for t, _ in row.band]
        if (
            not row.band
            or row.band[0] != (row.cap, row.r30_bound)
            or ts != sorted(ts, reverse=True)
            or len(set(ts)) != len(ts)
            or any(bound <= SLICE1_FLOOR or bound > row.r30_bound for _, bound in row.band)
            or row.cap > (wedge_count(row.profile)) // 3
        ):
            raise ManifestError(f"row {row.profile_id} leaves Slice 1 or breaks its band")
    return Manifest(sha, data, rows, SLICE1_FLOOR, WITNESS_CAP, STRICT_GAIN_THRESHOLD)


def load_manifest(path: Path | None = None, expected_sha256: str = MANIFEST_SHA256) -> Manifest:
    raw = (path or repo_root() / MANIFEST_RELATIVE).read_bytes()
    sha = sha256_bytes(raw)
    if sha != expected_sha256:
        raise ManifestError("frozen manifest SHA-256 differs from the engine pin")
    data = _obj(json.loads(raw), "manifest")
    if render_manifest(data) != raw:
        raise ManifestError("manifest bytes are not canonical")
    return validate_manifest(data, sha)


# Durable logs ------------------------------------------------------------------------------


def _full_fsync(fd: int) -> None:
    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        fcntl.fcntl(fd, full)
    else:
        os.fsync(fd)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        _full_fsync(fd)
    finally:
        os.close(fd)


def _key(value: object) -> Key:
    items = _list(value, "KEY")
    if not items or any(type(i) not in (str, int) for i in items):
        raise DurableLogError("durable keys are non-empty lists of strings and integers")
    return tuple(cast(list[str | int], items))


class DurableLog:
    """Append-only JSONL; each line is chained to the previous line by SHA-256."""

    def __init__(self, path: Path, header: Mapping[str, object]) -> None:
        self.path = path
        self.records: dict[Key, dict[str, object]] = {}
        self.last = GENESIS
        if path.exists():
            self._load(header)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.append(("HEADER",), header)
            _fsync_directory(path.parent)

    def _load(self, header: Mapping[str, object]) -> None:
        raw = self.path.read_bytes()
        if not raw.endswith(b"\n"):
            raise DurableLogError(f"{self.path.name}: truncated last line")
        for number, line in enumerate(raw.split(b"\n")[:-1]):
            try:
                record = _obj(json.loads(line), "line")
            except (ValueError, ManifestError) as error:
                raise DurableLogError(f"{self.path.name}:{number}: unreadable line") from error
            if set(record) != {"KEY", "PREV_SHA256", "BODY", "LINE_SHA256"}:
                raise DurableLogError(f"{self.path.name}:{number}: wrong line fields")
            content = {k: record[k] for k in ("KEY", "PREV_SHA256", "BODY")}
            if (
                canonical_json(record).encode() != line
                or record["PREV_SHA256"] != self.last
                or record["LINE_SHA256"] != sha256_bytes(canonical_json(content).encode())
            ):
                raise DurableLogError(f"{self.path.name}:{number}: hash chain broken")
            key = _key(record["KEY"])
            if key in self.records:
                raise DurableLogError(f"{self.path.name}:{number}: duplicate durable key {key}")
            if (number == 0) != (key == ("HEADER",)):
                raise DurableLogError(f"{self.path.name}: the header must be the first line only")
            self.records[key] = _obj(record["BODY"], "BODY")
            self.last = cast(str, record["LINE_SHA256"])
        if self.records.get(("HEADER",)) != dict(header):
            raise DurableLogError(f"{self.path.name}: header differs (manifest or engine changed)")

    def get(self, key: Key) -> dict[str, object] | None:
        return self.records.get(key)

    def append(self, key: Key, body: Mapping[str, object]) -> dict[str, object]:
        if key in self.records:
            raise DurableLogError(f"duplicate durable key {key}")
        content: dict[str, object] = {
            "KEY": list(key),
            "PREV_SHA256": self.last,
            "BODY": dict(body),
        }
        line_sha = sha256_bytes(canonical_json(content).encode())
        line = canonical_json({**content, "LINE_SHA256": line_sha}).encode()
        with self.path.open("ab") as handle:
            handle.write(line + b"\n")
            handle.flush()
            _full_fsync(handle.fileno())
        stored = cast(dict[str, object], json.loads(canonical_json(dict(body))))
        self.records[key] = stored
        self.last = line_sha
        return stored


@contextmanager
def durable_lock(directory: Path) -> Generator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / LOCK).open("a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CensusError("another census writer holds the durable lock") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# Census ------------------------------------------------------------------------------------


def require_single_thread_env(environ: Mapping[str, str]) -> None:
    wrong = [name for name in THREAD_ENV if environ.get(name) != "1"]
    if wrong:
        raise PreflightError(f"numerical thread variables must be 1: {', '.join(wrong)}")


class Census:
    """One Slice-1 census over a durable directory; solver and evaluator are injected."""

    def __init__(
        self,
        manifest: Manifest,
        durable: Path,
        solve: Solver = cp_sat_solve,
        evaluate: Evaluator | None = None,
    ) -> None:
        require_single_thread_env(os.environ)
        self.manifest = manifest
        self.solve = solve
        self.evaluate = evaluate or official_evaluator()
        header: dict[str, object] = {
            "TASK_ID": TASK_ID,
            "MANIFEST_SHA256": manifest.sha256,
            "ENGINE_SHA256": engine_sha256(),
        }
        self.proof = DurableLog(durable / PROOF_LOG, {**header, "LOG": "PROOF"})
        self.witnesses = DurableLog(durable / WITNESS_LEDGER, {**header, "LOG": "WITNESS"})
        self.solver_calls = 0

    def logged_solve(self, key: Key, request: SolveRequest) -> SolveOutcome:
        record = self.proof.get(key)
        if record is None:
            self.solver_calls += 1
            outcome = self.solve(request)
            if outcome.status not in (*REALIZED, INFEASIBLE, UNKNOWN):
                raise CensusError(f"solver returned {outcome.status}")
            if (outcome.status in REALIZED) != (outcome.structure is not None):
                raise CensusError("a realized status must carry exactly one structure")
            record = self.proof.append(
                key,
                {
                    "REQUEST_SHA256": request.digest(),
                    "PROFILE_ID": profile_id(request.profile),
                    "T": request.triangles,
                    "CEILING": request.ceiling,
                    "EXCLUDED_COUNT": len(request.excluded),
                    "SECONDS": request.seconds,
                    "STATUS": outcome.status,
                    "STRUCTURE": None if outcome.structure is None else outcome.structure.as_json(),
                    "WALL_SECONDS": outcome.wall_seconds,
                },
            )
        if record.get("REQUEST_SHA256") != request.digest():
            raise DurableLogError(f"logged solve {key} does not match its request")
        raw = record["STRUCTURE"]
        return SolveOutcome(
            _str(record["STATUS"], "STATUS"),
            None if raw is None else Structure.from_json(raw),
            float(cast(float, record["WALL_SECONDS"])),
        )

    def solve_with_retry(self, key: Key, request: SolveRequest) -> SolveOutcome:
        first = self.logged_solve((*key, 0), request)
        if first.status != UNKNOWN:
            return first
        return self.logged_solve((*key, 1), replace(request, seconds=RETRY_SECONDS))

    def realized_at(self, row: SliceRow, t: int, structure: Structure) -> Realization:
        found = realization(row.profile, structure)
        if found.triangles != t:
            raise CensusError(
                f"{row.profile_id}: witness has {found.triangles} triangles where the "
                f"certified cap and refutations allow exactly {t}"
            )
        return found

    def collect(self, row: SliceRow, t: int, first: Structure) -> tuple[list[Structure], str]:
        found = [first]
        while len(found) < self.manifest.witness_cap:
            request = SolveRequest(row.profile, t, tuple(found), SOLVE_SECONDS)
            outcome = self.solve_with_retry(
                ("SOLVE", row.profile_id, t, "WITNESS", len(found)), request
            )
            if outcome.status == INFEASIBLE:
                return found, "STRUCTURE_SPACE_EXHAUSTED"
            if outcome.structure is None:
                return found, "WITNESS_SOLVE_UNRESOLVED_AFTER_RETRY"
            if outcome.structure in found:
                raise CensusError("solver repeated an excluded structure")
            self.realized_at(row, t, outcome.structure)
            found.append(outcome.structure)
        return found, "WITNESS_CAP_REACHED"

    def evaluate_witnesses(
        self, row: SliceRow, t: int, found: Sequence[Structure]
    ) -> list[dict[str, object]]:
        """Rank by the proxy, then count exactly; the exact count alone decides a gain."""

        scored = [(self.realized_at(row, t, s), index, s) for index, s in enumerate(found)]
        ranked = sorted(scored, key=lambda item: (item[0].proxy_s4, item[1]))
        records: list[dict[str, object]] = []
        for rank, (real, index, structure) in enumerate(ranked):
            key: Key = ("WITNESS", row.profile_id, t, index)
            record = self.witnesses.get(key)
            if record is None:
                tickets = portfolio(structure)
                count = self.evaluate(tickets)
                record = self.witnesses.append(
                    key,
                    {
                        "STRUCTURE_SHA256": structure.digest(),
                        "PROXY_RANK": rank,
                        "PROXY_S4": real.proxy_s4,
                        "K4_WITH_CONTAINED_TRIPLE": real.k4_with_contained_triple,
                        "K4_WITHOUT_CONTAINED_TRIPLE": real.k4_without_contained_triple,
                        "TRIANGLES": real.triangles,
                        "OPEN_WEDGES": real.open_wedges,
                        "TICKETS": [list(ticket) for ticket in tickets],
                        "NORMALIZED_SHA256": compact_tickets_sha256(tickets),
                        "EXACT_COUNT": count,
                        "GAIN": is_gain(count),
                    },
                )
            if (
                record.get("STRUCTURE_SHA256") != structure.digest()
                or record.get("PROXY_RANK") != rank
            ):
                raise DurableLogError(f"logged witness {key} does not match its structure")
            if record.get("GAIN") is not is_gain(_int(record["EXACT_COUNT"], "EXACT_COUNT")):
                raise DurableLogError(f"logged witness {key} gain differs from its exact count")
            records.append(record)
        return records

    def run_profile(self, row: SliceRow) -> dict[str, object]:
        done = self.proof.get(("PROFILE_DONE", row.profile_id))
        if done is not None:
            return done
        refuted: list[int] = []
        summary: dict[str, object] = {"STATUS": "NO_REALIZATION_IN_SLICE"}
        for t, bound in row.band:
            first = SolveRequest(row.profile, t, (), SOLVE_SECONDS)
            outcome = self.solve_with_retry(("SOLVE", row.profile_id, t, "CHASE", 0), first)
            if outcome.status == INFEASIBLE:
                refuted.append(t)
                continue
            if outcome.structure is None:
                summary = {"STATUS": "UNRESOLVED_AFTER_RETRY", "UNRESOLVED_T": t}
                break
            self.realized_at(row, t, outcome.structure)
            found, end = self.collect(row, t, outcome.structure)
            records = self.evaluate_witnesses(row, t, found)
            counts = [_int(r["EXACT_COUNT"], "EXACT_COUNT") for r in records]
            summary = {
                "STATUS": "REALIZED",
                "MAX_REALIZABLE_T": t,
                "BAND_BOUND_AT_T": bound,
                "WITNESS_COUNT": len(records),
                "WITNESS_END": end,
                "BEST_EXACT_COUNT": max(counts),
                "GAIN_COUNT": sum(map(is_gain, counts)),
            }
            break
        return self.proof.append(
            ("PROFILE_DONE", row.profile_id),
            {**summary, "REFUTED_T": refuted, "R30_BOUND": row.r30_bound},
        )

    def run(self, slice_number: int = 1, profile_limit: int | None = None) -> dict[str, object]:
        if (
            slice_number != 1
            or _obj(self.manifest.data["SLICE2"], "SLICE2").get("ENABLED") is not False
        ):
            raise Slice2NotAuthorized("only Slice 1 is authorized; Slice 2 is disabled")
        for row in self.manifest.rows:
            if any(bound <= self.manifest.floor for _, bound in row.band):
                raise Slice2NotAuthorized(f"{row.profile_id} lies outside Slice 1")
        summaries: list[dict[str, object]] = []
        started = 0
        for row in self.manifest.rows:
            fresh = self.proof.get(("PROFILE_DONE", row.profile_id)) is None
            if fresh and profile_limit is not None and started >= profile_limit:
                break
            summaries.append(self.run_profile(row))
            started += fresh
        return self.summary(summaries)

    def summary(self, summaries: Sequence[Mapping[str, object]]) -> dict[str, object]:
        witnesses = [r for k, r in self.witnesses.records.items() if k[0] == "WITNESS"]
        counts = [_int(r["EXACT_COUNT"], "EXACT_COUNT") for r in witnesses]
        statuses: dict[str, int] = {}
        for s in summaries:
            name = _str(s["STATUS"], "STATUS")
            statuses[name] = statuses.get(name, 0) + 1
        return {
            "TASK_ID": TASK_ID,
            "MANIFEST_SHA256": self.manifest.sha256,
            "SLICE": 1,
            "PROFILES_DONE": len(summaries),
            "PROFILES_TOTAL": len(self.manifest.rows),
            "COMPLETE": len(summaries) == len(self.manifest.rows),
            "STATUS_COUNTS": dict(sorted(statuses.items())),
            "WITNESSES_EVALUATED": len(witnesses),
            "BEST_EXACT_COUNT": max(counts, default=None),
            "STRICT_GAIN_THRESHOLD": self.manifest.threshold,
            "GAINS": [r for r in witnesses if is_gain(_int(r["EXACT_COUNT"], "EXACT_COUNT"))],
            "SOLVER_CALLS_THIS_PROCESS": self.solver_calls,
        }


# Freeze and launch preflight -----------------------------------------------------------------

SLICE1_DERIVATION_SCRIPT = r"""
import hashlib, json, sys
from pathlib import Path
tree, floor, sealed = Path(sys.argv[1]).resolve(), int(sys.argv[2]), Path(sys.argv[3])
raw = sealed.read_bytes()
if hashlib.sha256(raw).hexdigest() != sys.argv[4]:
    raise SystemExit("sealed R30 result SHA-256 changed")
import lottolab.research.b649_k20_min_s2_current_cursor_class_owner_chase_r28 as r28
loaded = {}
for name, module in sorted(sys.modules.items()):
    if name.split(".")[0] != "lottolab":
        continue
    file = getattr(module, "__file__", None)
    for path in (file, *getattr(module, "__path__", ())):
        if path is not None and not Path(path).resolve().is_relative_to(tree):
            raise SystemExit(f"{name} resolved outside the committed R28 tree")
    if file is not None:
        source = Path(file).resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        loaded[source.relative_to(tree).as_posix()] = digest
result = json.loads(raw)
ledger = {}
for row in result["FINAL_RESOLVED_LEDGER"]:
    if set(row) != {"PROFILE_ID", "CURRENT_BOUND"} or row["PROFILE_ID"] in ledger:
        raise SystemExit("sealed ledger row is malformed or repeated")
    ledger[row["PROFILE_ID"]] = row["CURRENT_BOUND"]
cursor = result["NEXT_ACTIVE_PROFILE"]
if (
    result["NEXT_ACTIVE_BOUND"] != floor
    or cursor in ledger
    or len(ledger) != result["RESOLVED_LEDGER_COUNT"]
):
    raise SystemExit("sealed cursor or ledger count disagrees with the Slice-1 floor")
plateaus = {c["PLATEAU_INDEX"]: c for c in result["PLATEAU_CERTIFICATES"]}
recorded = {}
for step in result["REFINEMENT_STEPS"]:
    if step["KIND"] == "CURSOR_PLATEAU_CLASS_CERTIFICATE":
        cert = plateaus[step["PLATEAU_INDEX"]]
        for pid in cert["PLATEAU_PROFILE_IDS"]:
            recorded[pid] = ("PLATEAU_CERTIFICATE", cert["GRAPH_TRIANGLE_UPPER_BOUND"], None)
    elif step["KIND"] == "OWNER_REFUTATION":
        recorded[step["PROFILE_ID"]] = ("OWNER_REFUTATION", step["TRIANGLE_CAP"], step["NEW_BOUND"])
    else:
        raise SystemExit("unknown sealed refinement step")
if not set(recorded) <= set(ledger):
    raise SystemExit("a sealed refinement step names a profile outside the ledger")


def cap_bound(profile, t):
    return r28.bound_from_cap(profile, t, r28.profile_s4_floor(profile))[1]


rows, evidence, at_floor = [], {}, 0
for pid, bound in ledger.items():
    p = r28.decode_profile(pid)
    caps = [t for t in range(22, r28.overlap_wedge_count(p) // 3 + 1) if cap_bound(p, t) == bound]
    if len(caps) != 1:
        raise SystemExit(f"{pid}: no unique R28 triangle cap gives the sealed bound")
    kind, cap, step_bound = recorded.get(pid, ("LEDGER_BOUND_ONLY", caps[0], None))
    if cap != caps[0] or step_bound not in (None, bound):
        raise SystemExit(f"{pid}: sealed refinement records disagree with the sealed ledger")
    at_floor += bound == floor
    if bound > floor:
        evidence[kind] = evidence.get(kind, 0) + 1
        band, t = [], cap
        while t >= 22 and cap_bound(p, t) > floor:
            band.append([t, cap_bound(p, t)])
            t -= 1
        rows.append([pid, bound, cap, band])
family = max([*ledger.values(), floor])
owners = sorted((p for p, b in ledger.items() if b == family), reverse=True)
competing = max([floor, *(b for p, b in ledger.items() if p not in owners)])
if (family, owners, competing) != (
    result["FAMILY_UPPER_BOUND"], result["FINAL_BOUND_OWNER_IDS"], result["NEXT_COMPETING_BOUND"]
):
    raise SystemExit("sealed family maximum, owners or competing bound disagree with the ledger")
print(json.dumps({
    "METHOD": "SEALED_R30_RESULT_DATA_WITH_COMMITTED_R28_BOUND_CODE",
    "R28_LOADED_MODULES": loaded,
    "R30_MODULES_LOADED": sorted(n for n in sys.modules if n.endswith(("_r29", "_r30"))),
    "SEALED_LEDGER_SHA256": result["FINAL_COMPLETE_LEDGER_SHA256"],
    "LEDGER_COUNT": len(ledger),
    "LEDGER_ROWS_AT_FLOOR": at_floor,
    "FAMILY_UPPER_BOUND": family,
    "OWNERS": owners,
    "NEXT_COMPETING_BOUND": competing,
    "NEXT_ACTIVE_PROFILE": cursor,
    "NEXT_ACTIVE_BOUND": floor,
    "SLICE1_CAP_EVIDENCE": dict(sorted(evidence.items())),
    "ROWS": rows,
}))
"""


def derive_slice1(sealed: Path, root: Path) -> dict[str, object]:
    """Slice 1 from the sealed R30 result's data, bounded by committed R28 code in a child.

    The child's only ``lottolab`` is the R28 commit unpacked from Git into a fresh
    directory. That tree has no R30 module, so no R30 code can load.
    """

    verify_r28(root)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", R28_COMMIT, *R28_SOURCE_PATHS],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="b649-r28-") as directory:
        tree = Path(directory).resolve()
        with tarfile.open(fileobj=io.BytesIO(archive)) as unpacked:
            unpacked.extractall(tree, filter="data")
        env = {
            **os.environ,
            **dict.fromkeys(THREAD_ENV, "1"),
            "PYTHONPATH": str(tree / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        argv = [
            sys.executable,
            "-c",
            SLICE1_DERIVATION_SCRIPT,
            str(tree),
            str(SLICE1_FLOOR),
            str(sealed.resolve()),
            R30_RESULT_SHA256,
        ]
        done = subprocess.run(argv, cwd=tree, env=env, capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise ManifestError(f"Slice-1 derivation failed: {done.stderr.strip()[-400:]}")
    derived = _obj(json.loads(done.stdout), "Slice-1 derivation")
    if (
        derived.get("SEALED_LEDGER_SHA256") != R30_LEDGER_SHA256
        or derived.get("R30_MODULES_LOADED") != []
    ):
        raise ManifestError("Slice-1 derivation left the pinned sealed R30 ledger")
    return derived


def git_show(root: Path, commit: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:{relative}"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout


def start_portfolio(root: Path) -> tuple[Tickets, bytes]:
    raw = (root / START_RELATIVE).read_bytes()
    tickets = tuple(
        tuple(_int(n, "number") for n in _list(t, "ticket"))
        for t in _list(_obj(json.loads(raw), "start")[START_FIELD], START_FIELD)
    )
    return tickets, raw


def verify_start(root: Path, evaluate: Evaluator) -> dict[str, object]:
    tickets, raw = start_portfolio(root)
    if (
        sha256_bytes(raw) != START_FILE_SHA256
        or compact_tickets_sha256(tickets) != START_NORMALIZED_SHA256
    ):
        raise PreflightError("canonical start portfolio changed")
    profile, structure = structure_from_tickets(tickets)
    count = evaluate(tickets)
    if count != START_COUNT:
        raise PreflightError("official evaluator no longer counts the start at 313,263,888")
    return {
        "PATH": START_RELATIVE,
        "FILE_SHA256": START_FILE_SHA256,
        "FIELD": START_FIELD,
        "NORMALIZED_SHA256": START_NORMALIZED_SHA256,
        "COUNT": count,
        "PROFILE_ID": profile_id(profile),
        "GRAPH_TRIANGLES": realization(profile, structure).triangles,
    }


def verify_evaluator(root: Path) -> dict[str, object]:
    from . import b649_official_any_prize_exact as exact

    path = Path(exact.__file__).resolve()
    data = path.read_bytes()
    if (
        path != (root / EVALUATOR_RELATIVE).resolve()
        or path.parent != Path(__file__).resolve().parent
        or sha256_bytes(data) != EVALUATOR_SHA256
        or git_blob_id(data) != EVALUATOR_BLOB
    ):
        raise PreflightError("official evaluator differs from the pinned authority")
    return {
        "PATH": EVALUATOR_RELATIVE,
        "SHA256": EVALUATOR_SHA256,
        "GIT_BLOB": EVALUATOR_BLOB,
        "FUNCTION": "evaluate_portfolio",
        "FIELD": "official_any_prize_outcome_count",
    }


def verify_model_identity() -> dict[str, object]:
    ortools: Any = import_module("ortools")
    digests = {f"{p}@{c}": model_proto_sha256(p, c) for p, c, _ in MODEL_PROBES}
    if digests != {f"{p}@{c}": d for p, c, d in MODEL_PROBES}:
        raise PreflightError("support model proto differs from the pinned R28 model")
    return {"ORTOOLS_VERSION": str(ortools.__version__), "MODEL_PROTO_TEXT_SHA256": digests}


def verify_proxy_weights(evaluate: Evaluator) -> dict[str, int]:
    weights = {n: quartet_all_win_count(t, evaluate) for n, t in k4_quartet_portfolios().items()}
    if weights != PROXY_WEIGHTS:
        raise PreflightError("K4 quartet weights differ from the official evaluator")
    return weights


def verify_r28(root: Path) -> dict[str, object]:
    module = git_show(root, R28_COMMIT, R28_MODULE_RELATIVE)
    bound = git_show(root, R28_COMMIT, R28_BOUND_MODULE_RELATIVE)
    result = git_show(root, R28_COMMIT, R28_RESULT_RELATIVE)
    tree = subprocess.run(
        ["git", "rev-parse", f"{R28_COMMIT}^{{tree}}"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    if (
        sha256_bytes(module) != R28_MODULE_SHA256
        or sha256_bytes(bound) != R28_BOUND_MODULE_SHA256
        or sha256_bytes(result) != R28_RESULT_SHA256
        or tree != R28_TREE
        or b"def support_union_model(" not in module
        or b"def profile_s4_floor(" not in module
        or b"def bound_from_cap(" not in bound
    ):
        raise PreflightError("R28 authority objects changed or are missing")
    return {
        "COMMIT": R28_COMMIT,
        "TREE": R28_TREE,
        "BRANCH": R28_BRANCH,
        "MODULE_PATH": R28_MODULE_RELATIVE,
        "MODULE_SHA256": R28_MODULE_SHA256,
        "BOUND_MODULE_PATH": R28_BOUND_MODULE_RELATIVE,
        "BOUND_MODULE_SHA256": R28_BOUND_MODULE_SHA256,
        "BOUND_SEMANTICS": "cap_bound(T) = "
        "bound_from_cap(profile, T, profile_s4_floor(profile))[1]",
        "RESULT_PATH": R28_RESULT_RELATIVE,
        "RESULT_SHA256": R28_RESULT_SHA256,
        "SUPPORT_MODEL": "support_union_model (ported verbatim; proto text pinned)",
        "MODEL_PROBES": [list(p) for p in MODEL_PROBES],
    }


def verify_r30_result() -> str:
    path = R30_ROOT / R30_RESULT_RELATIVE
    if path.is_file() and sha256_bytes(path.read_bytes()) == R30_RESULT_SHA256:
        return str(path)
    raise PreflightError("tracked sealed R30 result is unavailable or has changed")


def build_manifest(
    derivation: Mapping[str, object], authorities: Mapping[str, object]
) -> dict[str, object]:
    rows = sorted(
        (_list(r, "row") for r in _list(derivation["ROWS"], "ROWS")),
        key=lambda r: (-_int(r[1], "bound"), [-int(c) for c in _str(r[0], "profile")]),
    )
    sealed = {k: v for k, v in derivation.items() if k != "ROWS"}
    return {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "PREPARED_BY": PREP_TASK_ID,
        "AUTHORITIES": {
            **authorities,
            "R30": {
                "WORKTREE": str(R30_ROOT),
                "BRANCH": R30_BRANCH,
                "BASE_HEAD": R30_BASE_HEAD,
                "RESULT_PATH": R30_RESULT_RELATIVE,
                "RESULT_SHA256": R30_RESULT_SHA256,
                "RESULT_TRACKED": True,
                "RESULT_ROLE": "LOAD_BEARING_SEALED_DATA",
                "MODULE_AUTHORITY_STATUS": R30_MODULE_AUTHORITY_STATUS,
                "MODULE_AUTHORITY_REASON": R30_MODULE_AUTHORITY_REASON,
                "SEALED_DERIVATION": sealed,
            },
        },
        "PROFILE_FRONTIER": {
            "SOURCE": "sealed R30 result data only: FINAL_RESOLVED_LEDGER, NEXT_ACTIVE_PROFILE, "
            "NEXT_ACTIVE_BOUND, REFINEMENT_STEPS and PLATEAU_CERTIFICATES",
            "BOUND_CODE": "R28 commit unpacked from Git and run in a child; no R30 code",
            "CAP": "the unique T in [22, W // 3] with R28 cap_bound(T) equal to the sealed "
            "ledger bound; it must equal the profile's last sealed OWNER_REFUTATION or plateau "
            "certificate cap where one exists",
            "ORDER": "R30 bound descending, then profile digits descending",
            "BAND": "every T from the cap down while R28 cap_bound(T) > floor",
        },
        "SLICE1": {
            "FLOOR": SLICE1_FLOOR,
            "FLOOR_SEMANTICS": "EXCLUSIVE: (profile, T) with R30-envelope bound > FLOOR "
            "(FLOOR = R30 NEXT_ACTIVE_BOUND, so no unresolved profile enters)",
            "PROFILE_COUNT": len(rows),
            "PAIR_COUNT": sum(len(_list(r[3], "band")) for r in rows),
            "INCUMBENT_FIRST_PROFILE": rows[0][0],
            "PROFILES_SHA256": rows_sha256(rows),
            "ROW_FORMAT": "[PROFILE_ID, R30_BOUND, TRIANGLE_CAP, [[T, BOUND], ...]]",
            "PROFILES": rows,
        },
        "SLICE2": {"ENABLED": False, "FLOOR": SLICE2_FLOOR, "AUTHORIZATION": "NONE"},
        "SOLVER": {
            "MODEL": "R28 support_union_model, one profile, open-wedge ceiling W - 3T",
            "NUM_SEARCH_WORKERS": SEARCH_WORKERS,
            "WORKER_EVIDENCE": "preflight solves a probe and reads 'with 1 workers' from the "
            "CP-SAT log; num_workers stays unset (setting both is MODEL_INVALID in 9.15)",
            "RANDOM_SEED": RANDOM_SEED,
            "SOLVE_SECONDS": SOLVE_SECONDS,
            "RETRY_SECONDS": RETRY_SECONDS,
            "RETRY_RULE": "UNKNOWN at 120 s is retried once at 600 s; only INFEASIBLE refutes "
            "a T; FEASIBLE or OPTIMAL realizes it; UNKNOWN after the retry stops that profile",
            "THREAD_ENV": dict.fromkeys(THREAD_ENV, "1"),
        },
        "WITNESS": {
            "CAP": WITNESS_CAP,
            "DISTINCTNESS": "exact structure no-good: one of the 49 lines must differ",
            "PROXY": "K4-quartet S4: sum over overlap-graph K4 of its exact four-ticket weight",
            "PROXY_WEIGHTS": PROXY_WEIGHTS,
            "PROXY_ROLE": "RANK_ONLY",
            "MAPPING": "triple line n -> number n + 1 (n < 22), then pair lines -> 23..49",
        },
        "ACCEPTANCE": {
            "EVALUATOR_SHA256": EVALUATOR_SHA256,
            "START_COUNT": START_COUNT,
            "STRICT_GAIN_THRESHOLD": STRICT_GAIN_THRESHOLD,
            "RULE": "official exact OFFICIAL_ANY_PRIZE count >= 313263889 (> 313263888)",
        },
    }


def freeze_authorities(root: Path, evaluate: Evaluator) -> dict[str, object]:
    return {
        "R28": verify_r28(root),
        "EVALUATOR": verify_evaluator(root),
        "CANONICAL_START": verify_start(root, evaluate),
        "MODEL_IDENTITY": {
            **verify_model_identity(),
            "PROXY_WEIGHTS": verify_proxy_weights(evaluate),
        },
    }


def preflight(manifest: Manifest, root: Path, evaluate: Evaluator) -> dict[str, object]:
    """Launch gate: every pinned authority and runtime setting, without a census solve."""

    require_single_thread_env(os.environ)
    authorities = _obj(manifest.data["AUTHORITIES"], "AUTHORITIES")
    live = freeze_authorities(root, evaluate)
    for name, value in live.items():
        if authorities.get(name) != value:
            raise PreflightError(f"{name} authority differs from the frozen manifest")
    solver: Any = configured_solver(SOLVE_SECONDS)
    workers = observed_search_workers()
    if (
        solver.parameters.num_search_workers != 1
        or solver.parameters.random_seed != RANDOM_SEED
        or solver.parameters.max_time_in_seconds != SOLVE_SECONDS
        or workers != 1
    ):
        raise PreflightError("solver is not single-worker with the fixed seed")
    if manifest.rows[0].band[0][0] != _obj(live["CANONICAL_START"], "start")["GRAPH_TRIANGLES"]:
        raise PreflightError("incumbent profile row does not match the canonical start")
    return {
        "STATUS": "PASS",
        "MANIFEST_SHA256": manifest.sha256,
        "ENGINE_SHA256": engine_sha256(),
        "CP_SAT_WORKERS_OBSERVED": workers,
        "R30_RESULT_AT": verify_r30_result(),
        "SLICE1_PROFILE_COUNT": len(manifest.rows),
        "INCUMBENT_FIRST_PROFILE": manifest.rows[0].profile_id,
    }


def write_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        _full_fsync(handle.fileno())
    temporary.replace(path)
    _fsync_directory(path.parent)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    run = commands.add_parser("run")
    run.add_argument("--slice", type=int, default=1)
    run.add_argument("--profile-limit", type=int, default=None)
    run.add_argument("--durable", type=Path, default=None)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require_single_thread_env(os.environ)
    root = repo_root()
    if args.command == "freeze":
        evaluate = official_evaluator()
        base = {
            name: subprocess.run(
                ["git", "rev-parse", ref], cwd=root, capture_output=True, text=True, check=True
            ).stdout.strip()
            for name, ref in (("HEAD", "HEAD"), ("TREE", "HEAD^{tree}"))
        }
        authorities = {**freeze_authorities(root, evaluate), "PREPARED_AT_BASE": base}
        derivation = derive_slice1(Path(verify_r30_result()), root)
        data = render_manifest(build_manifest(derivation, authorities))
        write_atomic(args.output, data)
        print(json.dumps({"MANIFEST": str(args.output), "SHA256": sha256_bytes(data)}))
        return
    if args.command == "run" and args.slice != 1:
        raise Slice2NotAuthorized("only Slice 1 is authorized; Slice 2 is disabled")
    manifest = load_manifest()
    evaluate = official_evaluator()
    report = preflight(manifest, root, evaluate)
    if args.command == "preflight":
        print(json.dumps(report, indent=1))
        return
    durable = args.durable or root / DURABLE_RELATIVE
    with durable_lock(durable):
        summary = Census(manifest, durable, cp_sat_solve, evaluate).run(
            args.slice, args.profile_limit
        )
        write_atomic(durable / SUMMARY, (json.dumps(summary, indent=1) + "\n").encode())
    print(json.dumps({k: v for k, v in summary.items() if k != "GAINS"}, indent=1))


if __name__ == "__main__":
    main()
