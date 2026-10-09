"""Targeted exact witness search for the two open K20 fiber Slice-1 cells.

The frozen Slice-1 census (manifest 4b1df050, engine 479f3163) has 992 cells, one degree profile
at one T each. The R30 overlay (6c442007) imports exact CP-SAT refutations for 990 of them. Two
cells remain open:

* CELL_A, the incumbent profile 55555555555511111100 at T = 270. The incumbent realizes it, and
  nothing beyond the incumbent is known there.
* CELL_B, 66665555555322000000 at T = 266. R30 returned UNKNOWN twice, and no realization is
  known.

This engine searches exactly those two cells and no other. Each attempt solves the census's own
single-profile support model (R28 ``support_union_model`` via ``census.support_model``) at the
cell's open-wedge ceiling W - 3T. It excludes every labelled structure already returned in that
cell, which is the census no-good. The model, its constraints and the exact objective are
unchanged. The model protos of the two cells are pinned.

The search differs from the census in four ways.

* CP-SAT's worker count and the per-attempt time limit come only from a separate Owner resource
  grant. The grant also fixes the attempt budget, the distinct-witness cap and the wall budget.
  Without a valid grant nothing is solved.
* Every realized structure is validated twice: through the census structure checks, and
  independently from its tickets. The checks cover the degree profile, T exactly, and at most
  one shared number per ticket pair.
* Witnesses are deduplicated up to exact hypergraph isomorphism, using the minimum-leaf
  certificate of an individualization-refinement search with automorphism pruning. Two
  witnesses are merged only when their canonical certificates are equal and the composed
  relabelling is verified to map one onto the other. A lossy invariant such as T, the K4 counts
  or colour refinement never merges anything. A relabelled copy is logged as a DUPLICATE, with
  its verified isomorphism. It consumes the raw attempt budget but never the distinct-witness
  cap.
* Each new class is scored once with the pinned official exact evaluator on its canonical
  portfolio. The exact count alone decides a gain: at least 313,263,889, strictly above the
  313,263,888 incumbent. The cells' mathematical upper bounds (CELL_A 313,449,032 and CELL_B
  313,453,272) are recorded as bounds only. Neither is a witness.

OPTIMAL, FEASIBLE, INFEASIBLE and UNKNOWN are recorded as returned. INFEASIBLE without
exclusions refutes the cell at T, and INFEASIBLE after exclusions proves the labelled
realization space exhausted. UNKNOWN only ends the current session's work on a cell; a later
session re-attempts it with the same exclusions. Every attempt, class and duplicate goes to one
hash-chained, fsynced JSONL log (``census.DurableLog``) before it is used. A resumed run replays
the log and recomputes every request digest and class identity. It completes any attempt left
unclassified by an interruption, and it never re-solves a logged attempt or accepts a class
twice.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import platform
import time
from collections import Counter
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib import import_module
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_refutation_overlay as overlay

TASK_ID = "B649_K20_TWO_OPEN_CELLS_TARGETED_SOLVER_PREP_R1"
DURABLE_RELATIVE = ".task-data/b649-k20-two-open-cells-targeted-solver-r1"
EVIDENCE_LOG = "evidence-log.jsonl"
SUMMARY = "summary.json"
LOCK = "two-cell.lock"
# The census RUN1 root and the certified successor's root are never opened.
FOREIGN_DURABLE_NAMES = (
    Path(census.DURABLE_RELATIVE).name,
    "b649-k20-fiber-slice1-r30-certified-successor-r1",
)

SOURCE_COMMIT = "4ff5fac583d86a61469b812397b064ba15532d95"
DONOR_COMMIT = "d2313db4ba0163f928b4cee0591ee625bee2dcbf"
DONOR_TREE = "5792183725be72550806f4beca010cfaabe92fe3"
CENSUS_ENGINE_SHA256 = "479f3163659a91234d23637b697527224e947ae3268e49515cd609ca82ca6276"
MANIFEST_SHA256 = "4b1df0503ab0c4a780e56b6189821f1d2f9080c2124dc6951d8663580e79e64f"
OVERLAY_SHA256 = "6c44200780ea742efadb1e5d161744a7665f99b13822b1613a07fc804d016b19"
R30_TASK_HEAD = "6ba4811304ec6528738a0c0b38969901b264d241"
R30_RESULT_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
R30_PROOF_LOG_SHA256 = "4258c2c6a85bc4bdcbdee401ce83767fc03471d8853169f4fbf7f1603ccf3d26"
EVALUATOR_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
SLICE1_CELL_COUNT = 992
IMPORTED_CELL_COUNT = 990

INCUMBENT_COUNT = 313_263_888
STRICT_GAIN_THRESHOLD = INCUMBENT_COUNT + 1
BOUND_ROLE = "MATHEMATICAL_UPPER_BOUND_ONLY_NOT_A_WITNESS"
CANONICAL_FORM = "INDIVIDUALIZATION_REFINEMENT_MIN_LEAF_CERTIFICATE_V1"
CANONICAL_NODE_LIMIT = 1_000_000

OPTIMAL = "OPTIMAL"
FEASIBLE = "FEASIBLE"
INFEASIBLE = "INFEASIBLE"
UNKNOWN = "UNKNOWN"
REALIZED = (OPTIMAL, FEASIBLE)
STATUSES = (OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN)

# Terminal cell states, and the reasons a session stops working on a cell.
REFUTED_AT_T = "REFUTED_AT_T"
LABELED_SPACE_EXHAUSTED = "LABELED_SPACE_EXHAUSTED"
UNRESOLVED_UNKNOWN = "UNRESOLVED_UNKNOWN_THIS_SESSION"
DISTINCT_CAP_REACHED = "DISTINCT_WITNESS_CAP_REACHED"
ATTEMPT_BUDGET_REACHED = "ATTEMPT_BUDGET_REACHED"
WALL_BUDGET_REACHED = "WALL_BUDGET_REACHED"

Cell = tuple[str, int]
Labeling = tuple[int, ...]
Line = tuple[int, ...]


class TwoCellError(census.CensusError):
    """Fail-closed two-cell engine error: the run must stop."""


class SourceIdentityError(TwoCellError):
    """A pinned input authority is missing or differs."""


class TargetError(TwoCellError):
    """Only the two exact open cells may be searched."""


class GrantError(TwoCellError):
    """No valid separate Owner resource grant: nothing may be solved."""


class WitnessError(TwoCellError):
    """A realized structure does not satisfy the cell's exact constraints."""


class CanonicalFormError(TwoCellError):
    """The canonical labelling could not be completed or verified."""


class SolverContractError(TwoCellError):
    """The solver broke its contract (status, structure or exclusions)."""


class ContradictionError(TwoCellError):
    """A result contradicts known evidence."""


# Target cells and input source identity ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class TargetCell:
    name: str
    profile_id: str
    t: int
    upper_bound: int
    realized_by_incumbent: bool

    @property
    def key(self) -> Cell:
        return self.profile_id, self.t

    @property
    def profile(self) -> census.Profile:
        return census.decode_profile(self.profile_id)

    @property
    def ceiling(self) -> int:
        return census.wedge_count(self.profile) - 3 * self.t


TARGET_CELLS = (
    TargetCell("CELL_A", "55555555555511111100", 270, 313_449_032, True),
    TargetCell("CELL_B", "66665555555322000000", 266, 313_453_272, False),
)
TARGET_KEYS: tuple[Cell, ...] = tuple(cell.key for cell in TARGET_CELLS)
# sha256 of str(Proto()) for census.support_model((profile,), W - 3T) with no exclusions.
MODEL_PROTO_SHA256 = {
    "CELL_A": "381ee9ef753d6b1904fb7c5f8037a01eee0183f96963411e1eb56b303760fe89",
    "CELL_B": "f2d5946a254086e26ea843da8b49f083947a2d6faf89ea85adad74f840a71600",
}
# The witness identity of the incumbent's isomorphism class (canonical start portfolio).
INCUMBENT_WITNESS_ID = "ef74855715fd27889606328cc6dedf48dfc77b7b7de228deaa8e1c477d753830"


@dataclass(frozen=True, slots=True)
class SelectedCell:
    cell: TargetCell
    manifest_bound: int
    census_chase_request_sha256: str

    def as_json(self) -> dict[str, object]:
        return {
            "NAME": self.cell.name,
            "PROFILE_ID": self.cell.profile_id,
            "T": self.cell.t,
            "CEILING": self.cell.ceiling,
            "UPPER_BOUND": self.cell.upper_bound,
            "BOUND_ROLE": BOUND_ROLE,
            "MANIFEST_R30_BAND_BOUND": self.manifest_bound,
            "REALIZED_BY_INCUMBENT": self.cell.realized_by_incumbent,
            "CENSUS_CHASE_REQUEST_SHA256": self.census_chase_request_sha256,
            "MODEL_PROTO_SHA256": MODEL_PROTO_SHA256[self.cell.name],
        }


def engine_sha256() -> str:
    return census.sha256_bytes(Path(__file__).read_bytes())


def evaluator_module_sha256() -> str:
    from . import b649_official_any_prize_exact as exact

    return census.sha256_bytes(Path(exact.__file__).read_bytes())


def verify_sources(manifest: census.Manifest, loaded: overlay.Overlay) -> dict[str, object]:
    """Every pinned authority, checked against the loaded bytes; returns the identity record."""

    r30 = cast(dict[str, object], loaded.data["R30"])
    pinned = cast(dict[str, object], loaded.data["CENSUS"])
    checks = (
        (census.engine_sha256(), CENSUS_ENGINE_SHA256, "census engine"),
        (manifest.sha256, MANIFEST_SHA256, "Slice-1 manifest"),
        (loaded.sha256, OVERLAY_SHA256, "R30 refutation overlay"),
        (pinned.get("SOURCE_COMMIT"), SOURCE_COMMIT, "frozen Slice-1 source commit"),
        (pinned.get("ENGINE_SHA256"), CENSUS_ENGINE_SHA256, "overlay census engine"),
        (pinned.get("MANIFEST_SHA256"), MANIFEST_SHA256, "overlay census manifest"),
        (r30.get("TASK_HEAD"), R30_TASK_HEAD, "R30 task head"),
        (r30.get("RESULT_SHA256"), R30_RESULT_SHA256, "R30 source result"),
        (r30.get("PROOF_LOG_SHA256"), R30_PROOF_LOG_SHA256, "R30 proof log"),
        (evaluator_module_sha256(), EVALUATOR_SHA256, "official exact evaluator"),
        (census.EVALUATOR_SHA256, EVALUATOR_SHA256, "census evaluator pin"),
    )
    for observed, expected, name in checks:
        if observed != expected:
            raise SourceIdentityError(f"{name} differs from its pin")
    return {
        "SOURCE_COMMIT": SOURCE_COMMIT,
        "DONOR_COMMIT": DONOR_COMMIT,
        "DONOR_TREE": DONOR_TREE,
        "CENSUS_ENGINE_SHA256": CENSUS_ENGINE_SHA256,
        "MANIFEST_SHA256": MANIFEST_SHA256,
        "OVERLAY_SHA256": OVERLAY_SHA256,
        "R30_TASK_HEAD": R30_TASK_HEAD,
        "R30_RESULT_SHA256": R30_RESULT_SHA256,
        "R30_PROOF_LOG_SHA256": R30_PROOF_LOG_SHA256,
        "EVALUATOR_SHA256": EVALUATOR_SHA256,
    }


def select_cells(manifest: census.Manifest, loaded: overlay.Overlay) -> tuple[SelectedCell, ...]:
    """The two target cells, and only them, bound to their frozen manifest rows."""

    rows = {row.profile_id: row for row in manifest.rows}
    cells = {overlay.cell_of(row) for row in manifest.rows}
    not_imported = {
        (str(entry[0]), cast(int, entry[1]))
        for entry in cast(list[list[object]], loaded.data["NOT_IMPORTED"])
    }
    if (
        len(manifest.rows) != SLICE1_CELL_COUNT
        or len(cells) != SLICE1_CELL_COUNT
        or len(loaded.imports) != IMPORTED_CELL_COUNT
        or not set(loaded.imports) <= cells
        or cells - set(loaded.imports) != set(TARGET_KEYS)
        or not_imported != set(TARGET_KEYS)
    ):
        raise TargetError("the open Slice-1 cells are not exactly CELL_A and CELL_B")
    selected: list[SelectedCell] = []
    for cell in TARGET_CELLS:
        row = rows[cell.profile_id]
        if (
            overlay.cell_of(row) != cell.key
            or not STRICT_GAIN_THRESHOLD <= cell.upper_bound <= row.r30_bound
        ):
            raise TargetError(f"{cell.name} differs from its frozen manifest row")
        chase = census.SolveRequest(row.profile, row.cap, (), census.SOLVE_SECONDS)
        selected.append(SelectedCell(cell, row.r30_bound, chase.digest()))
    return tuple(selected)


def verify_cell_models() -> dict[str, str]:
    """Each target cell's model is the census chase model, byte for byte."""

    observed = {
        cell.name: census.model_proto_sha256(cell.profile_id, cell.ceiling) for cell in TARGET_CELLS
    }
    if observed != MODEL_PROTO_SHA256:
        raise SourceIdentityError("a target cell's support model differs from its pin")
    return observed


# Solver configuration and the Owner resource grant -----------------------------------------


def _positive_int(value: object, name: str, maximum: int | None = None) -> int:
    if type(value) is not int or value < 1 or (maximum is not None and value > maximum):
        limit = "" if maximum is None else f" and at most {maximum}"
        raise GrantError(f"{name} must be an integer of at least 1{limit}")
    return value


def _positive_seconds(value: object, name: str) -> float:
    seconds = cast(float, value)
    if type(value) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise GrantError(f"{name} must be a finite positive number of seconds")
    return float(seconds)


@dataclass(frozen=True, slots=True)
class SolverConfig:
    """CP-SAT settings for one attempt. Only num_search_workers is set: both is MODEL_INVALID."""

    num_search_workers: int
    solve_seconds: float
    random_seed: int = census.RANDOM_SEED

    def __post_init__(self) -> None:
        _positive_int(self.num_search_workers, "NUM_SEARCH_WORKERS")
        if type(self.solve_seconds) is not float:
            raise GrantError("SOLVE_SECONDS must be stored as a float")
        _positive_seconds(self.solve_seconds, "SOLVE_SECONDS")
        if type(self.random_seed) is not int:
            raise GrantError("RANDOM_SEED must be an integer")

    def as_json(self) -> dict[str, object]:
        return {
            "NUM_SEARCH_WORKERS": self.num_search_workers,
            "NUM_WORKERS": "UNSET",
            "MAX_TIME_IN_SECONDS": self.solve_seconds,
            "RANDOM_SEED": self.random_seed,
            "LOG_SEARCH_PROGRESS": False,
        }

    def digest(self) -> str:
        return census.sha256_bytes(census.canonical_json(self.as_json()).encode())

    @staticmethod
    def from_json(value: object) -> SolverConfig:
        data = cast(dict[str, object], value)
        config = SolverConfig(
            cast(int, data["NUM_SEARCH_WORKERS"]),
            cast(float, data["MAX_TIME_IN_SECONDS"]),
            cast(int, data["RANDOM_SEED"]),
        )
        if config.as_json() != data:
            raise census.DurableLogError("logged solver configuration is not canonical")
        return config


def configured_solver(config: SolverConfig) -> Any:
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.solve_seconds
    solver.parameters.num_search_workers = config.num_search_workers
    solver.parameters.random_seed = config.random_seed
    solver.parameters.log_search_progress = False
    return solver


def observed_search_workers(config: SolverConfig) -> int:
    """Solve a one-variable model and read the worker count from CP-SAT's own log."""

    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model: Any = cp_model.CpModel()
    model.NewBoolVar("probe")
    solver = configured_solver(SolverConfig(config.num_search_workers, 5.0, config.random_seed))
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
        raise census.PreflightError("CP-SAT did not report its search worker count")
    return workers[0]


GRANT_KIND = "B649_K20_TWO_OPEN_CELLS_OWNER_RESOURCE_AND_EXECUTION_GRANT"
GRANT_FIELDS = (
    "KIND",
    "TASK_ID",
    "GRANT_ID",
    "GRANTED_BY",
    "ENGINE_SHA256",
    "TARGET_CELLS",
    "NUM_SEARCH_WORKERS",
    "SOLVE_SECONDS",
    "MAX_ATTEMPTS_PER_CELL",
    "DISTINCT_WITNESS_CAP",
    "WALL_BUDGET_SECONDS",
)


@dataclass(frozen=True, slots=True)
class ResourceGrant:
    """The protected execution inputs; they come from the Owner grant file and nowhere else."""

    sha256: str
    grant_id: str
    target_cells: tuple[Cell, ...]
    config: SolverConfig
    max_attempts_per_cell: int
    distinct_witness_cap: int
    wall_budget_seconds: float

    def as_json(self) -> dict[str, object]:
        return {
            "GRANT_SHA256": self.sha256,
            "GRANT_ID": self.grant_id,
            "TARGET_CELLS": [list(cell) for cell in self.target_cells],
            "SOLVER_CONFIG": self.config.as_json(),
            "SOLVER_CONFIG_SHA256": self.config.digest(),
            "MAX_ATTEMPTS_PER_CELL": self.max_attempts_per_cell,
            "DISTINCT_WITNESS_CAP": self.distinct_witness_cap,
            "WALL_BUDGET_SECONDS": self.wall_budget_seconds,
        }


def grant_template() -> dict[str, object]:
    """What the Owner must fill in; every null is required and has no default."""

    return {
        "KIND": GRANT_KIND,
        "TASK_ID": TASK_ID,
        "GRANT_ID": None,
        "GRANTED_BY": "OWNER",
        "ENGINE_SHA256": engine_sha256(),
        "TARGET_CELLS": [list(cell) for cell in TARGET_KEYS],
        "NUM_SEARCH_WORKERS": None,
        "SOLVE_SECONDS": None,
        "MAX_ATTEMPTS_PER_CELL": None,
        "DISTINCT_WITNESS_CAP": None,
        "WALL_BUDGET_SECONDS": None,
    }


def load_grant(path: Path | None, *, cpu_count: int | None = None) -> ResourceGrant:
    """Parse the Owner's grant file, or refuse. No field has a default."""

    if path is None:
        raise GrantError("a separate Owner resource grant (--grant) is required before any solve")
    if not path.is_file():
        raise GrantError(f"Owner resource grant {path} does not exist")
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise GrantError("Owner resource grant is not JSON") from error
    if not isinstance(data, dict):
        raise GrantError("Owner resource grant must be a JSON object")
    grant = cast(dict[str, object], data)
    missing = sorted(set(GRANT_FIELDS) - set(grant))
    unknown = sorted(set(grant) - set(GRANT_FIELDS))
    if missing or unknown:
        raise GrantError(f"grant fields missing {missing} or unknown {unknown}")
    if (
        grant["KIND"] != GRANT_KIND
        or grant["TASK_ID"] != TASK_ID
        or grant["GRANTED_BY"] != "OWNER"
        or not isinstance(grant["GRANT_ID"], str)
        or not grant["GRANT_ID"].strip()
    ):
        raise GrantError("grant kind, task, grantor or id is not this task's Owner grant")
    if grant["ENGINE_SHA256"] != engine_sha256():
        raise GrantError("grant names a different engine; the code changed since the grant")
    if grant["TARGET_CELLS"] != [list(cell) for cell in TARGET_KEYS]:
        raise GrantError("grant must name exactly CELL_A and CELL_B in order")
    cpus = cpu_count if cpu_count is not None else os.cpu_count() or 1
    config = SolverConfig(
        _positive_int(grant["NUM_SEARCH_WORKERS"], "NUM_SEARCH_WORKERS", cpus),
        _positive_seconds(grant["SOLVE_SECONDS"], "SOLVE_SECONDS"),
    )
    wall = _positive_seconds(grant["WALL_BUDGET_SECONDS"], "WALL_BUDGET_SECONDS")
    if wall < config.solve_seconds:
        raise GrantError("WALL_BUDGET_SECONDS must admit at least one full attempt")
    return ResourceGrant(
        census.sha256_bytes(raw),
        grant["GRANT_ID"],
        TARGET_KEYS,
        config,
        _positive_int(grant["MAX_ATTEMPTS_PER_CELL"], "MAX_ATTEMPTS_PER_CELL"),
        _positive_int(grant["DISTINCT_WITNESS_CAP"], "DISTINCT_WITNESS_CAP"),
        wall,
    )


# Exact canonical labelling of a hypergraph -------------------------------------------------


def _dense(keys: Sequence[Any]) -> list[int]:
    order = {key: index for index, key in enumerate(sorted(set(keys)))}
    return [order[key] for key in keys]


def _refine(colors: list[int], incidence: Sequence[Sequence[Line]]) -> list[int]:
    """Equitable colour refinement; a vertex's old colour leads its signature, so it only splits."""

    while True:
        signatures = [
            (
                colors[v],
                tuple(
                    sorted(
                        (len(line), tuple(sorted(colors[u] for u in line if u != v)))
                        for line in incidence[v]
                    )
                ),
            )
            for v in range(len(colors))
        ]
        refined = _dense(signatures)
        if max(refined) == max(colors):
            return refined
        colors = refined


def _certificate(lines: Iterable[Line], labeling: Sequence[int]) -> tuple[Line, ...]:
    relabeled = (tuple(sorted(labeling[v] for v in line)) for line in lines)
    return tuple(sorted(relabeled, key=lambda line: (-len(line), line)))


def _invert(labeling: Sequence[int]) -> list[int]:
    inverse = [0] * len(labeling)
    for vertex, label in enumerate(labeling):
        inverse[label] = vertex
    return inverse


def _root(parent: list[int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


@dataclass(frozen=True, slots=True)
class CanonicalForm:
    """``labeling[v]`` is v's canonical label; ``lines`` is the relabelled, sorted line list."""

    lines: tuple[Line, ...]
    labeling: Labeling
    nodes: int
    automorphism_generators: tuple[Labeling, ...]


@dataclass(slots=True)
class _Search:
    lines: tuple[Line, ...]
    line_set: frozenset[Line]
    incidence: list[list[Line]]
    node_limit: int
    nodes: int = 0
    first: tuple[tuple[Line, ...], Labeling] | None = None
    best: tuple[tuple[Line, ...], Labeling] | None = None
    generators: list[Labeling] = field(default_factory=list[Labeling])

    def automorphism(self, labeling: Labeling, reference: Labeling) -> None:
        inverse = _invert(reference)
        gamma = tuple(inverse[labeling[v]] for v in range(len(labeling)))
        if frozenset(tuple(sorted(gamma[v] for v in line)) for line in self.lines) != self.line_set:
            raise CanonicalFormError("an equal-certificate leaf pair is not an automorphism")
        if any(gamma[v] != v for v in range(len(gamma))):
            self.generators.append(gamma)

    def leaf(self, labeling: Labeling) -> None:
        certificate = _certificate(self.lines, labeling)
        if self.first is None or self.best is None:
            self.first = self.best = (certificate, labeling)
        elif certificate == self.first[0]:
            self.automorphism(labeling, self.first[1])
        elif certificate == self.best[0]:
            self.automorphism(labeling, self.best[1])
        elif certificate < self.best[0]:
            self.best = (certificate, labeling)

    def same_orbit(self, v: int, explored: Sequence[int], prefix: Sequence[int]) -> bool:
        """True when a found automorphism fixing ``prefix`` pointwise maps v onto an explored
        sibling; that subtree then carries exactly the same leaf certificates."""

        parent = list(range(len(self.incidence)))
        for gamma in self.generators:
            if all(gamma[p] == p for p in prefix):
                for x, y in enumerate(gamma):
                    a, b = _root(parent, x), _root(parent, y)
                    if a != b:
                        parent[a] = b
        return _root(parent, v) in {_root(parent, u) for u in explored}

    def search(self, colors: list[int], prefix: tuple[int, ...]) -> None:
        self.nodes += 1
        if self.nodes > self.node_limit:
            raise CanonicalFormError(f"canonical search exceeded {self.node_limit} nodes")
        n = len(colors)
        if max(colors) == n - 1:
            self.leaf(tuple(colors))
            return
        sizes = Counter(colors)
        target = min(color for color, size in sizes.items() if size > 1)
        explored: list[int] = []
        for v in (u for u in range(n) if colors[u] == target):
            if explored and self.same_orbit(v, explored, prefix):
                continue
            explored.append(v)
            keys = [
                (c, 0 if u == v else 1) if c == target else (c, 0) for u, c in enumerate(colors)
            ]
            self.search(_refine(_dense(keys), self.incidence), (*prefix, v))


def canonical_form(
    vertex_count: int, lines: Iterable[Line], node_limit: int = CANONICAL_NODE_LIMIT
) -> CanonicalForm:
    """Exact canonical form of a hypergraph up to vertex relabelling.

    Individualization-refinement: the target cell is the lowest non-singleton colour, every
    vertex in it is individualized in turn, and the canonical form is the minimum certificate
    over all leaves. Subtrees are pruned only through verified automorphisms that fix the
    individualized prefix pointwise, so the minimum is unchanged. Initial colours order vertices
    by descending line-size degree, so canonical labels respect that order.
    """

    frozen = tuple(tuple(sorted(line)) for line in lines)
    if any(
        len(set(line)) != len(line) or not 0 <= min(line) <= max(line) < vertex_count
        for line in frozen
    ) or len(set(frozen)) != len(frozen):
        raise CanonicalFormError("lines must be distinct sets of in-range vertices")
    incidence = [[line for line in frozen if v in line] for v in range(vertex_count)]
    sizes = sorted({len(line) for line in frozen}, reverse=True)
    initial = _dense(
        [
            tuple(-sum(len(line) == s for line in incidence[v]) for s in sizes)
            for v in range(vertex_count)
        ]
    )
    search = _Search(frozen, frozenset(frozen), incidence, node_limit)
    search.search(_refine(initial, incidence), ())
    if search.best is None:
        raise CanonicalFormError("canonical search found no leaf")
    certificate, labeling = search.best
    if _certificate(frozen, labeling) != certificate or sorted(labeling) != list(
        range(vertex_count)
    ):
        raise CanonicalFormError("canonical labelling does not reproduce its certificate")
    return CanonicalForm(certificate, labeling, search.nodes, tuple(search.generators))


# K20 witnesses: validation, canonical identity and isomorphism ----------------------------


def relabel(structure: census.Structure, labeling: Sequence[int]) -> census.Structure:
    triples = sorted(
        cast(census.Triple, tuple(sorted(labeling[v] for v in t))) for t in structure.triples
    )
    pairs = sorted(
        cast(census.Pair, tuple(sorted(labeling[v] for v in p))) for p in structure.pairs
    )
    return census.Structure(tuple(triples), tuple(pairs))


def check_portfolio(profile: census.Profile, t: int, tickets: census.Tickets) -> None:
    """Recount the fiber, the degree profile, the pair overlaps and T from the tickets alone."""

    sets = [frozenset(ticket) for ticket in tickets]
    if (
        len(sets) != census.TICKET_COUNT
        or any(len(ticket) != census.TICKET_CAPACITY for ticket in tickets)
        or any(len(s) != census.TICKET_CAPACITY for s in sets)
        or not all(1 <= n <= census.POOL_SIZE for s in sets for n in s)
    ):
        raise WitnessError("a K20 witness has 20 tickets of six distinct numbers in 1..49")
    holders = Counter(n for s in sets for n in s)
    if set(holders) != set(range(1, census.POOL_SIZE + 1)) or not set(holders.values()) <= {2, 3}:
        raise WitnessError("witness is off the minimum-S2 fiber")
    if tuple(sum(holders[n] == 3 for n in s) for s in sets) != profile:
        raise WitnessError("witness tickets do not carry the cell's degree profile")
    overlap = [[len(a & b) for b in sets] for a in sets]
    if any(overlap[i][j] > 1 for i, j in combinations(range(census.TICKET_COUNT), 2)):
        raise WitnessError("two witness tickets share more than one number")
    triangles = sum(
        overlap[i][j] == overlap[i][k] == overlap[j][k] == 1
        for i, j, k in combinations(range(census.TICKET_COUNT), 3)
    )
    if triangles != t:
        raise WitnessError(f"witness tickets have {triangles} overlap triangles, not T = {t}")


def validate_witness(cell: TargetCell, structure: census.Structure) -> census.Realization:
    """Both the census structure checks and the independent ticket recount must pass."""

    try:
        found = census.realization(cell.profile, structure)
    except census.CensusError as error:
        raise WitnessError(f"{cell.name}: {error}") from error
    if found.triangles != cell.t:
        raise WitnessError(
            f"{cell.name}: witness has {found.triangles} triangles where the cell is T = {cell.t}"
        )
    check_portfolio(cell.profile, cell.t, census.portfolio(structure))
    return found


@dataclass(frozen=True, slots=True)
class CanonicalWitness:
    structure: census.Structure
    labeling: Labeling
    nodes: int
    automorphism_generators: int

    @property
    def witness_id(self) -> str:
        return witness_id(self.structure)


def witness_id(canonical: census.Structure) -> str:
    """Deterministic class identity: independent of ticket order, number labels and discovery."""

    return census.sha256_bytes(
        census.canonical_json(
            {"CANONICAL_FORM": CANONICAL_FORM, "STRUCTURE": canonical.as_json()}
        ).encode()
    )


def canonicalize(profile: census.Profile, structure: census.Structure) -> CanonicalWitness:
    form = canonical_form(census.TICKET_COUNT, (*structure.triples, *structure.pairs))
    canonical = relabel(structure, form.labeling)
    if (*canonical.triples, *canonical.pairs) != form.lines:
        raise CanonicalFormError("canonical structure differs from the canonical certificate")
    try:
        census.validate_structure(profile, canonical)
    except census.CensusError as error:
        raise CanonicalFormError("canonical labels broke the degree-profile order") from error
    return CanonicalWitness(canonical, form.labeling, form.nodes, len(form.automorphism_generators))


def isomorphism(
    new: CanonicalWitness,
    source: census.Structure,
    representative: CanonicalWitness,
    target: census.Structure,
) -> Labeling:
    """The verified relabelling that maps ``source`` onto ``target`` (equal canonical forms)."""

    if new.structure != representative.structure:
        raise CanonicalFormError("only equal canonical forms are isomorphic")
    inverse = _invert(representative.labeling)
    mapping = tuple(inverse[new.labeling[v]] for v in range(census.TICKET_COUNT))
    if relabel(source, mapping) != target:
        raise CanonicalFormError(
            "composed canonical labellings do not map one witness onto the other"
        )
    return mapping


# Attempts, the CP-SAT solve and the exact evaluator --------------------------------------


@dataclass(frozen=True, slots=True)
class AttemptRequest:
    """Realize at least T triangles in ``cell``, excluding every structure returned so far."""

    cell: TargetCell
    attempt: int
    excluded: tuple[census.Structure, ...]
    config: SolverConfig

    def digest(self) -> str:
        return census.sha256_bytes(
            census.canonical_json(
                {
                    "TASK_ID": TASK_ID,
                    "CELL": self.cell.name,
                    "PROFILE_ID": self.cell.profile_id,
                    "T": self.cell.t,
                    "CEILING": self.cell.ceiling,
                    "ATTEMPT": self.attempt,
                    "EXCLUDED": [s.digest() for s in self.excluded],
                    "SOLVER_CONFIG": self.config.as_json(),
                }
            ).encode()
        )


Solver = Callable[[AttemptRequest], census.SolveOutcome]


def cp_sat_solve(request: AttemptRequest) -> census.SolveOutcome:
    """The census chase model plus the census no-goods, under the granted configuration."""

    model, triples, pairs = census.k20_model(request.cell.profile, request.cell.ceiling)
    for structure in request.excluded:
        census.add_nogood(model, triples, pairs, structure)
    solver = configured_solver(request.config)
    status = str(solver.StatusName(solver.Solve(model)))
    structure = census.decode_structure(solver, triples, pairs) if status in REALIZED else None
    return census.SolveOutcome(status, structure, float(solver.WallTime()))


def exact_evaluator() -> census.Evaluator:
    """The pinned official exact OFFICIAL_ANY_PRIZE evaluator, or refuse."""

    if evaluator_module_sha256() != EVALUATOR_SHA256:
        raise SourceIdentityError("official exact evaluator differs from its pin")
    return census.official_evaluator()


def is_gain(exact_count: int) -> bool:
    return exact_count >= STRICT_GAIN_THRESHOLD


# One cell's attempt sequence ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WitnessClass:
    attempt: int
    structure: census.Structure
    canonical: CanonicalWitness
    record: Mapping[str, object]


def _logged_count(record: Mapping[str, object]) -> int:
    count = record.get("EXACT_COUNT")
    if type(count) is not int:
        raise census.DurableLogError("a logged exact count must be an integer")
    return count


def _same(a: Mapping[str, object], b: Mapping[str, object]) -> bool:
    return census.canonical_json(dict(a)) == census.canonical_json(dict(b))


class CellSearch:
    """One cell's attempts, replayed from and appended to the shared evidence log."""

    def __init__(
        self,
        cell: TargetCell,
        log: census.DurableLog,
        solve: Solver,
        evaluate: census.Evaluator,
    ) -> None:
        self.cell = cell
        self.log = log
        self.solve = solve
        self.evaluate = evaluate
        self.excluded: list[census.Structure] = []
        self.classes: dict[str, WitnessClass] = {}
        self.duplicates: list[int] = []
        self.status_counts: dict[str, int] = dict.fromkeys(STATUSES, 0)
        self.terminal: str | None = None
        self.attempts = 0
        self.solver_calls = 0
        self.evaluator_calls = 0
        self._replay()

    def _replay(self) -> None:
        while (record := self.log.get(("ATTEMPT", self.cell.name, self.attempts))) is not None:
            if self.terminal is not None:
                raise census.DurableLogError(
                    f"{self.cell.name}: an attempt follows {self.terminal}"
                )
            config = SolverConfig.from_json(record["SOLVER_CONFIG"])
            request = AttemptRequest(self.cell, self.attempts, tuple(self.excluded), config)
            if record.get("REQUEST_SHA256") != request.digest():
                raise census.DurableLogError(
                    f"{self.cell.name}: logged attempt differs from its request"
                )
            raw = record["STRUCTURE"]
            outcome = census.SolveOutcome(
                str(record["STATUS"]),
                None if raw is None else census.Structure.from_json(raw),
                float(cast(float, record["WALL_SECONDS"])),
            )
            self._check_outcome(request, outcome)
            self.attempts += 1
            self._absorb(request.attempt, outcome)
        accepted = {k[2] for k in self.log.records if k[:2] == ("ACCEPTED", self.cell.name)}
        duplicated = {k[2] for k in self.log.records if k[:2] == ("DUPLICATE", self.cell.name)}
        if accepted != set(self.classes) or duplicated != set(self.duplicates):
            raise census.DurableLogError(
                f"{self.cell.name}: class records differ from the attempts"
            )

    def _check_outcome(self, request: AttemptRequest, outcome: census.SolveOutcome) -> None:
        if outcome.status not in STATUSES:
            raise SolverContractError(f"{self.cell.name}: solver returned {outcome.status}")
        if (outcome.status in REALIZED) != (outcome.structure is not None):
            raise SolverContractError("a realized status must carry exactly one structure")
        if outcome.structure is not None and outcome.structure in request.excluded:
            raise SolverContractError("solver returned an excluded structure")

    def next_attempt(self, config: SolverConfig) -> census.SolveOutcome:
        if self.terminal is not None:
            raise TwoCellError(f"{self.cell.name} is already {self.terminal}")
        request = AttemptRequest(self.cell, self.attempts, tuple(self.excluded), config)
        self.solver_calls += 1
        outcome = self.solve(request)
        self._check_outcome(request, outcome)
        self.log.append(
            ("ATTEMPT", self.cell.name, request.attempt),
            {
                "REQUEST_SHA256": request.digest(),
                "PROFILE_ID": self.cell.profile_id,
                "T": self.cell.t,
                "CEILING": self.cell.ceiling,
                "EXCLUDED_COUNT": len(request.excluded),
                "SOLVER_CONFIG": config.as_json(),
                "SOLVER_CONFIG_SHA256": config.digest(),
                "STATUS": outcome.status,
                "STRUCTURE": None if outcome.structure is None else outcome.structure.as_json(),
                "WALL_SECONDS": outcome.wall_seconds,
            },
        )
        self.attempts += 1
        self._absorb(request.attempt, outcome)
        return outcome

    def _absorb(self, attempt: int, outcome: census.SolveOutcome) -> None:
        self.status_counts[outcome.status] += 1
        if outcome.status == UNKNOWN:
            return
        if outcome.structure is None:
            if not self.excluded and self.cell.realized_by_incumbent:
                raise ContradictionError(
                    f"{self.cell.name}: INFEASIBLE although the incumbent realizes it"
                )
            self.terminal = LABELED_SPACE_EXHAUSTED if self.excluded else REFUTED_AT_T
            return
        self._classify(attempt, outcome.structure)
        self.excluded.append(outcome.structure)

    def _classify(self, attempt: int, structure: census.Structure) -> None:
        found = validate_witness(self.cell, structure)
        canonical = canonicalize(self.cell.profile, structure)
        wid = canonical.witness_id
        known = self.classes.get(wid)
        if known is not None:
            mapping = isomorphism(canonical, structure, known.canonical, known.structure)
            self._record(
                ("DUPLICATE", self.cell.name, attempt),
                {
                    "WITNESS_ID": wid,
                    "REPRESENTATIVE_ATTEMPT": known.attempt,
                    "LABELED_STRUCTURE_SHA256": structure.digest(),
                    "ISOMORPHISM_TO_REPRESENTATIVE": list(mapping),
                },
            )
            self.duplicates.append(attempt)
            return
        key = ("ACCEPTED", self.cell.name, wid)
        recorded = self.log.get(key)
        tickets = census.portfolio(canonical.structure)
        if recorded is None:
            self.evaluator_calls += 1
            count = int(self.evaluate(tickets))
        else:
            count = _logged_count(recorded)
        body: dict[str, object] = {
            "ATTEMPT": attempt,
            "CLASS_INDEX": len(self.classes),
            "WITNESS_ID": wid,
            "CANONICAL_FORM": CANONICAL_FORM,
            "LABELED_STRUCTURE_SHA256": structure.digest(),
            "CANONICAL_LABELING": list(canonical.labeling),
            "CANONICAL_STRUCTURE": canonical.structure.as_json(),
            "CANONICAL_SEARCH_NODES": canonical.nodes,
            "AUTOMORPHISM_GENERATORS_FOUND": canonical.automorphism_generators,
            "IS_INCUMBENT_CLASS": wid == INCUMBENT_WITNESS_ID,
            "TRIANGLES": found.triangles,
            "OPEN_WEDGES": found.open_wedges,
            "K4_WITH_CONTAINED_TRIPLE": found.k4_with_contained_triple,
            "K4_WITHOUT_CONTAINED_TRIPLE": found.k4_without_contained_triple,
            "CANONICAL_TICKETS": [list(ticket) for ticket in tickets],
            "NORMALIZED_SHA256": census.compact_tickets_sha256(tickets),
            "EXACT_COUNT": count,
            "STRICT_GAIN_THRESHOLD": STRICT_GAIN_THRESHOLD,
            "GAIN": is_gain(count),
            "UPPER_BOUND": self.cell.upper_bound,
            "BOUND_ROLE": BOUND_ROLE,
        }
        if count > self.cell.upper_bound:
            raise ContradictionError(
                f"{self.cell.name}: exact count exceeds the cell's upper bound"
            )
        record = self._record(key, body)
        self.classes[wid] = WitnessClass(attempt, structure, canonical, record)

    def _record(self, key: census.Key, body: Mapping[str, object]) -> Mapping[str, object]:
        recorded = self.log.get(key)
        if recorded is None:
            return self.log.append(key, body)
        if not _same(recorded, body):
            raise census.DurableLogError(f"logged {key} differs from its recomputation")
        return recorded

    def stop_reason(self, grant: ResourceGrant) -> str | None:
        if self.terminal is not None:
            return self.terminal
        if len(self.classes) >= grant.distinct_witness_cap:
            return DISTINCT_CAP_REACHED
        if self.attempts >= grant.max_attempts_per_cell:
            return ATTEMPT_BUDGET_REACHED
        return None

    def summary(self) -> dict[str, object]:
        counts = [_logged_count(c.record) for c in self.classes.values()]
        if self.terminal is not None:
            state = self.terminal
        else:
            state = "REALIZED_SEARCH_OPEN" if self.classes else "UNRESOLVED"
        return {
            "NAME": self.cell.name,
            "PROFILE_ID": self.cell.profile_id,
            "T": self.cell.t,
            "CELL_STATE": state,
            "REALIZED_AT_T": bool(self.classes),
            "ATTEMPTS": self.attempts,
            "STATUS_COUNTS": dict(self.status_counts),
            "DISTINCT_WITNESSES": len(self.classes),
            "ISOMORPHIC_DUPLICATES": len(self.duplicates),
            "WITNESS_IDS": list(self.classes),
            "BEST_EXACT_COUNT": max(counts, default=None),
            "GAIN_WITNESS_IDS": [
                w for w, c in self.classes.items() if c.record.get("GAIN") is True
            ],
            "UPPER_BOUND": self.cell.upper_bound,
            "BOUND_ROLE": BOUND_ROLE,
        }


# The two-cell engine and its protected entrypoint ----------------------------------------


def refuse_foreign_root(durable: Path) -> None:
    if durable.resolve().name in FOREIGN_DURABLE_NAMES:
        raise TwoCellError("the two-cell engine never opens the census or successor durable roots")


@contextmanager
def exclusive_lock(directory: Path) -> Generator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / LOCK).open("a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise TwoCellError("another two-cell writer holds the durable lock") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def evidence_header(
    selected: Sequence[SelectedCell], sources: Mapping[str, object]
) -> dict[str, object]:
    return {
        "TASK_ID": TASK_ID,
        "LOG": "EVIDENCE",
        "ENGINE_SHA256": engine_sha256(),
        "SOURCES": dict(sources),
        "CELLS": [s.as_json() for s in selected],
        "CANONICAL_FORM": CANONICAL_FORM,
        "INCUMBENT_COUNT": INCUMBENT_COUNT,
        "STRICT_GAIN_THRESHOLD": STRICT_GAIN_THRESHOLD,
        "INCUMBENT_WITNESS_ID": INCUMBENT_WITNESS_ID,
    }


class TwoCellEngine:
    """Exactly CELL_A and CELL_B, one attempt per cell per round, under one Owner grant."""

    def __init__(
        self,
        selected: Sequence[SelectedCell],
        sources: Mapping[str, object],
        grant: ResourceGrant,
        durable: Path,
        solve: Solver = cp_sat_solve,
        evaluate: census.Evaluator | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        refuse_foreign_root(durable)
        census.require_single_thread_env(os.environ)
        if tuple(s.cell for s in selected) != TARGET_CELLS:
            raise TargetError("the engine searches exactly CELL_A and CELL_B, in order")
        if grant.target_cells != TARGET_KEYS:
            raise GrantError("the grant does not name exactly CELL_A and CELL_B")
        self.grant = grant
        self.clock = clock
        self.log = census.DurableLog(durable / EVIDENCE_LOG, evidence_header(selected, sources))
        evaluator = evaluate or exact_evaluator()
        self.searches = tuple(CellSearch(s.cell, self.log, solve, evaluator) for s in selected)

    @property
    def sessions(self) -> int:
        return sum(key[0] == "SESSION" for key in self.log.records)

    def run(self) -> dict[str, object]:
        session = self.sessions
        started = self.clock()
        ortools_module: Any = import_module("ortools")
        self.log.append(
            ("SESSION", session),
            {
                "GRANT": self.grant.as_json(),
                "ORTOOLS_VERSION": str(ortools_module.__version__),
                "PYTHON_VERSION": platform.python_version(),
                "CPU_COUNT": os.cpu_count(),
                "RESUMED_ATTEMPTS": {s.cell.name: s.attempts for s in self.searches},
            },
        )
        ends: dict[str, str] = {}
        active = list(self.searches)
        while active:
            for search in tuple(active):
                reason = search.stop_reason(self.grant)
                elapsed = self.clock() - started
                if reason is None and elapsed + self.grant.config.solve_seconds > (
                    self.grant.wall_budget_seconds
                ):
                    reason = WALL_BUDGET_REACHED
                if reason is None and search.next_attempt(self.grant.config).status == UNKNOWN:
                    reason = UNRESOLVED_UNKNOWN
                if reason is not None:
                    ends[search.cell.name] = reason
                    active.remove(search)
        self.log.append(("SESSION_END", session), {"CELL_ENDS": ends})
        return self.summary(ends)

    def summary(self, ends: Mapping[str, str] | None = None) -> dict[str, object]:
        cells = [s.summary() for s in self.searches]
        for cell in cells:
            cell["SESSION_END"] = None if ends is None else ends.get(str(cell["NAME"]))
        return {
            "TASK_ID": TASK_ID,
            "SESSIONS": self.sessions,
            "CELLS": cells,
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
            "STRICT_GAIN_THRESHOLD": STRICT_GAIN_THRESHOLD,
            "SCIENTIFIC_GAIN_FOUND": any(c["GAIN_WITNESS_IDS"] for c in cells),
            "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
            "SOLVER_CALLS_THIS_PROCESS": sum(s.solver_calls for s in self.searches),
            "EVALUATOR_CALLS_THIS_PROCESS": sum(s.evaluator_calls for s in self.searches),
        }


def prepared_inputs() -> tuple[tuple[SelectedCell, ...], dict[str, object]]:
    """Pins, the two-cell selection and both pinned cell models; no solve, no evaluation."""

    manifest = census.load_manifest()
    loaded = overlay.load_overlay()
    sources = verify_sources(manifest, loaded)
    selected = select_cells(manifest, loaded)
    verify_cell_models()
    return selected, sources


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    run = commands.add_parser("run")
    run.add_argument("--grant", type=Path, default=None)
    run.add_argument("--durable", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "verify":
        selected, sources = prepared_inputs()
        print(
            json.dumps(
                {
                    "TASK_ID": TASK_ID,
                    "ENGINE_SHA256": engine_sha256(),
                    "SOURCES": sources,
                    "TARGET_CELLS": [s.as_json() for s in selected],
                    "RESOURCE_GRANT_REQUIRED": True,
                    "GRANT_TEMPLATE": grant_template(),
                },
                indent=1,
            )
        )
        return
    grant = load_grant(args.grant)
    census.require_single_thread_env(os.environ)
    selected, sources = prepared_inputs()
    if observed_search_workers(grant.config) != grant.config.num_search_workers:
        raise census.PreflightError("CP-SAT does not run the granted worker count")
    evaluate = exact_evaluator()
    census.verify_start(census.repo_root(), evaluate)
    durable: Path = args.durable or census.repo_root() / DURABLE_RELATIVE
    refuse_foreign_root(durable)
    with exclusive_lock(durable):
        engine = TwoCellEngine(selected, sources, grant, durable, cp_sat_solve, evaluate)
        summary = engine.run()
        census.write_atomic(durable / SUMMARY, (json.dumps(summary, indent=1) + "\n").encode())
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
