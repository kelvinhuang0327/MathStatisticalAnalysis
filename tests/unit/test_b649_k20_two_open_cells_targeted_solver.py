"""Focused, non-heavy tests for the two-open-cell targeted K20 solver.

No target cell is solved: engine flows use an injected fake solver. CP-SAT runs the
one-variable worker probe, exhaustive enumerations of small synthetic members of the census
model family (n = 7 or 8 tickets of three numbers), and fixed-assignment membership checks on
the synthetic T = 255 cell. The two target cells' models are only built and checked. The
official evaluator recounts only the canonical start, its canonical relabelling and one
synthetic class. The synthetic same-T classes are pair-switches of the incumbent at T = 255,
built in pure Python.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from importlib import import_module
from itertools import combinations
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_refutation_overlay as overlay
from lottolab.research import b649_k20_two_open_cells_targeted_solver as two

ROOT = Path(__file__).resolve().parents[2]
CELL_A, CELL_B = two.TARGET_CELLS
DROP = object()
Script = Sequence[census.Structure | str]


class Interrupted(RuntimeError):
    """Simulated crash between durable writes."""


@pytest.fixture(autouse=True)
def single_thread_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in census.THREAD_ENV:
        monkeypatch.setenv(name, "1")


@pytest.fixture(scope="module")
def manifest() -> census.Manifest:
    return census.load_manifest()


@pytest.fixture(scope="module")
def loaded() -> overlay.Overlay:
    return overlay.load_overlay()


@pytest.fixture(scope="module")
def selected(manifest: census.Manifest, loaded: overlay.Overlay) -> tuple[two.SelectedCell, ...]:
    return two.select_cells(manifest, loaded)


@pytest.fixture(scope="module")
def sources(manifest: census.Manifest, loaded: overlay.Overlay) -> dict[str, object]:
    return two.verify_sources(manifest, loaded)


@pytest.fixture(scope="module")
def incumbent() -> census.Structure:
    tickets, _ = census.start_portfolio(ROOT)
    profile, structure = census.structure_from_tickets(tickets)
    assert census.profile_id(profile) == CELL_A.profile_id
    return structure


@pytest.fixture(scope="module")
def t255_classes(incumbent: census.Structure) -> list[census.Structure]:
    """One representative per isomorphism class among the incumbent's T = 255 pair-switches."""

    profile = CELL_A.profile
    found: dict[str, census.Structure] = {}
    pairs = incumbent.pairs
    for (i, (a, b)), (j, (c, d)) in combinations(enumerate(pairs), 2):
        for new in (((a, c), (b, d)), ((a, d), (b, c))):
            switched = tuple(cast(census.Pair, tuple(sorted(e))) for e in new)
            rest = [p for k, p in enumerate(pairs) if k not in (i, j)]
            candidate = census.Structure(incumbent.triples, tuple(sorted([*rest, *switched])))
            try:
                if census.realization(profile, candidate).triangles != 255:
                    continue
            except census.CensusError:
                continue
            found.setdefault(two.canonicalize(profile, candidate).witness_id, candidate)
    return list(found.values())


@pytest.fixture(scope="module")
def official() -> census.Evaluator:
    return two.exact_evaluator()


def block_shuffle(structure: census.Structure, seed: int) -> census.Structure:
    """A relabelling inside each equal-degree ticket block: same profile, same class."""

    rng = random.Random(seed)
    profile = CELL_A.profile
    perm = list(range(census.TICKET_COUNT))
    for degree in set(profile):
        block = [v for v in range(census.TICKET_COUNT) if profile[v] == degree]
        target = block[:]
        rng.shuffle(target)
        for v, w in zip(block, target, strict=True):
            perm[v] = w
    return two.relabel(structure, perm)


def relabelings(structure: census.Structure, count: int) -> list[census.Structure]:
    found: list[census.Structure] = []
    seed = 0
    while len(found) < count:
        candidate = block_shuffle(structure, seed)
        seed += 1
        if candidate != structure and candidate not in found:
            found.append(candidate)
    return found


class FakeSolver:
    """Serves a per-cell script: a structure is OPTIMAL, a string is that bare status."""

    def __init__(self, scripts: Mapping[str, Script], fail_at: int | None = None) -> None:
        self.scripts = scripts
        self.fail_at = fail_at
        self.calls: list[two.AttemptRequest] = []

    def __call__(self, request: two.AttemptRequest) -> census.SolveOutcome:
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise Interrupted("solver crash")
        self.calls.append(request)
        script = self.scripts.get(request.cell.name, ())
        item = script[request.attempt] if request.attempt < len(script) else two.UNKNOWN
        if isinstance(item, census.Structure):
            return census.SolveOutcome(two.OPTIMAL, item, 0.0)
        return census.SolveOutcome(item, None, 0.0)


class FakeEvaluator:
    def __init__(self, count: int = two.INCUMBENT_COUNT, fail_at: int | None = None) -> None:
        self.count = count
        self.fail_at = fail_at
        self.calls: list[census.Tickets] = []

    def __call__(self, tickets: census.Tickets) -> int:
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise Interrupted("evaluator crash")
        self.calls.append(tickets)
        return self.count - len(self.calls)


def write_grant(path: Path, **changes: object) -> Path:
    data: dict[str, object] = {
        "KIND": two.GRANT_KIND,
        "TASK_ID": two.TASK_ID,
        "GRANT_ID": "TEST-ONLY-GRANT",
        "GRANTED_BY": "OWNER",
        "ENGINE_SHA256": two.engine_sha256(),
        "TARGET_CELLS": [list(cell) for cell in two.TARGET_KEYS],
        "NUM_SEARCH_WORKERS": 4,
        "SOLVE_SECONDS": 30,
        "MAX_ATTEMPTS_PER_CELL": 8,
        "DISTINCT_WITNESS_CAP": 4,
        "WALL_BUDGET_SECONDS": 3600,
        "SYMMETRY_REDUCTION": two.SYMMETRY_NONE,
    }
    for name, value in changes.items():
        if value is DROP:
            del data[name]
        else:
            data[name] = value
    path.write_text(json.dumps(data))
    return path


def grant(tmp_path: Path, **changes: object) -> two.ResourceGrant:
    return two.load_grant(write_grant(tmp_path / "grant.json", **changes), cpu_count=8)


def engine(
    durable: Path,
    selected: Sequence[two.SelectedCell],
    sources: Mapping[str, object],
    resource: two.ResourceGrant,
    solve: two.Solver,
    evaluate: census.Evaluator,
    clock: Callable[[], float] = lambda: 0.0,
) -> two.TwoCellEngine:
    return two.TwoCellEngine(selected, sources, resource, durable, solve, evaluate, clock)


def records(log: census.DurableLog, kind: str, cell: str) -> dict[census.Key, dict[str, object]]:
    return {k: r for k, r in log.records.items() if k[:2] == (kind, cell)}


def cell_summary(summary: Mapping[str, object], name: str) -> dict[str, object]:
    cells = cast(list[dict[str, object]], summary["CELLS"])
    return next(c for c in cells if c["NAME"] == name)


# Exact two-cell selection and input source identity ------------------------------------------


def test_exactly_the_two_open_cells_are_selected(
    tmp_path: Path,
    manifest: census.Manifest,
    loaded: overlay.Overlay,
    selected: tuple[two.SelectedCell, ...],
    sources: dict[str, object],
) -> None:
    assert [s.cell.key for s in selected] == [
        ("55555555555511111100", 270),
        ("66665555555322000000", 266),
    ]
    assert [s.cell.upper_bound for s in selected] == [313_449_032, 313_453_272]
    assert [s.manifest_bound for s in selected] == [313_588_232, 313_582_744]
    for s in selected:
        assert s.as_json()["BOUND_ROLE"] == two.BOUND_ROLE
        chase = census.SolveRequest(s.cell.profile, s.cell.t, (), census.SOLVE_SECONDS)
        assert s.census_chase_request_sha256 == chase.digest()
    open_cells = {overlay.cell_of(r) for r in manifest.rows} - set(loaded.imports)
    assert open_cells == set(two.TARGET_KEYS)

    dropped = dict(loaded.imports)
    dropped.pop(next(iter(dropped)))
    with pytest.raises(two.TargetError):
        two.select_cells(manifest, replace(loaded, imports=dropped))
    extra = {**loaded.data, "NOT_IMPORTED": [*cast(list[object], loaded.data["NOT_IMPORTED"])]}
    cast(list[object], extra["NOT_IMPORTED"]).append(["66666665332221111111", 269, list[object]()])
    with pytest.raises(two.TargetError):
        two.select_cells(manifest, replace(loaded, data=extra))

    resource = grant(tmp_path)
    solve, evaluate = FakeSolver({}), FakeEvaluator()
    for cells in (selected[:1], selected[::-1], (*selected, selected[0])):
        with pytest.raises(two.TargetError):
            engine(tmp_path / "run", cells, sources, resource, solve, evaluate)
    other = replace(resource, target_cells=(two.TARGET_KEYS[0],))
    with pytest.raises(two.GrantError):
        engine(tmp_path / "run", selected, sources, other, solve, evaluate)
    assert not (tmp_path / "run").exists() and not solve.calls


@pytest.mark.parametrize(
    "pin",
    [
        "SOURCE_COMMIT",
        "CENSUS_ENGINE_SHA256",
        "MANIFEST_SHA256",
        "OVERLAY_SHA256",
        "R30_TASK_HEAD",
        "R30_RESULT_SHA256",
        "R30_PROOF_LOG_SHA256",
        "EVALUATOR_SHA256",
    ],
)
def test_every_source_identity_pin_is_load_bearing(
    pin: str, manifest: census.Manifest, loaded: overlay.Overlay, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert two.verify_sources(manifest, loaded)[pin] == getattr(two, pin)
    monkeypatch.setattr(two, pin, "0" * len(cast(str, getattr(two, pin))))
    with pytest.raises(two.SourceIdentityError):
        two.verify_sources(manifest, loaded)


def test_sources_cell_models_and_header_bind_the_frozen_inputs(
    tmp_path: Path,
    manifest: census.Manifest,
    loaded: overlay.Overlay,
    selected: tuple[two.SelectedCell, ...],
    sources: dict[str, object],
) -> None:
    assert sources["R30_RESULT_SHA256"] == (
        "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
    )
    assert sources["R30_PROOF_LOG_SHA256"] == (
        "4258c2c6a85bc4bdcbdee401ce83767fc03471d8853169f4fbf7f1603ccf3d26"
    )
    assert cast(str, sources["OVERLAY_SHA256"]).startswith("6c442007")
    assert sources["SOURCE_COMMIT"] == "4ff5fac583d86a61469b812397b064ba15532d95"
    r30 = {**cast(dict[str, object], loaded.data["R30"]), "PROOF_LOG_SHA256": "f" * 64}
    with pytest.raises(two.SourceIdentityError, match="R30 proof log"):
        two.verify_sources(manifest, replace(loaded, data={**loaded.data, "R30": r30}))

    assert two.verify_cell_models() == two.MODEL_PROTO_SHA256
    # The census pinned the incumbent profile's model at ceiling 6, which is CELL_A's ceiling.
    assert (CELL_A.profile_id, CELL_A.ceiling, two.MODEL_PROTO_SHA256["CELL_A"]) in (
        census.MODEL_PROBES
    )

    resource = grant(tmp_path)
    engine(tmp_path / "run", selected, sources, resource, FakeSolver({}), FakeEvaluator())
    moved = {**sources, "DONOR_COMMIT": "0" * 40}
    with pytest.raises(census.DurableLogError, match="header differs"):
        engine(tmp_path / "run", selected, moved, resource, FakeSolver({}), FakeEvaluator())


# Solver configuration and the Owner grant --------------------------------------------------


def test_solver_configuration_is_explicit_and_deterministic(tmp_path: Path) -> None:
    first, again = grant(tmp_path), grant(tmp_path)
    assert first == again and first.sha256 == again.sha256
    assert first.config == two.SolverConfig(4, 30.0)
    assert first.config.as_json() == {
        "NUM_SEARCH_WORKERS": 4,
        "NUM_WORKERS": "UNSET",
        "MAX_TIME_IN_SECONDS": 30.0,
        "RANDOM_SEED": 649,
        "LOG_SEARCH_PROGRESS": False,
    }
    assert first.config.digest() == two.SolverConfig(4, 30.0).digest()
    assert two.SolverConfig.from_json(first.config.as_json()) == first.config
    with pytest.raises(census.DurableLogError):
        two.SolverConfig.from_json({**first.config.as_json(), "NUM_WORKERS": 4})

    solver = two.configured_solver(first.config)
    assert solver.parameters.num_search_workers == 4
    assert solver.parameters.num_workers == 0  # unset: setting both is MODEL_INVALID
    assert solver.parameters.random_seed == 649
    assert solver.parameters.max_time_in_seconds == 30.0
    assert solver.parameters.log_search_progress is False

    request = two.AttemptRequest(CELL_B, 0, (), first.config)
    assert request.digest() == two.AttemptRequest(CELL_B, 0, (), two.SolverConfig(4, 30.0)).digest()
    for config in (two.SolverConfig(5, 30.0), two.SolverConfig(4, 31.0)):
        assert two.AttemptRequest(CELL_B, 0, (), config).digest() != request.digest()
    for workers, seconds in ((True, 30.0), (0, 30.0), (4, 30)):
        with pytest.raises(two.GrantError):
            two.SolverConfig(cast(int, workers), cast(float, seconds))

    # The original model's configuration and request digests are the baseline's, byte for byte.
    assert first.config.symmetry == two.SYMMETRY_NONE and first.config.digest() == (
        "4c8f9e226878583a92ff0c34407c83498dcba777a3c7b84bcd7a862ac0dedddb"
    )
    assert request.digest() == "218f0d229fb84009947ba197905325233abbe6ffe2b54077a1371baf39143c77"
    reduced = grant(tmp_path, SYMMETRY_REDUCTION=two.SYMMETRY_LEX_LEADER).config
    assert reduced == two.SolverConfig(4, 30.0, symmetry=two.SYMMETRY_LEX_LEADER)
    assert reduced.as_json() == {**first.config.as_json(), "SYMMETRY_REDUCTION": reduced.symmetry}
    assert two.SolverConfig.from_json(reduced.as_json()) == reduced
    assert two.AttemptRequest(CELL_B, 0, (), reduced).digest() != request.digest()
    with pytest.raises(census.DurableLogError):
        two.SolverConfig.from_json({**first.config.as_json(), "SYMMETRY_REDUCTION": "NONE"})
    with pytest.raises(two.GrantError, match="SYMMETRY_REDUCTION"):
        two.SolverConfig(4, 30.0, symmetry="LEX")


@pytest.mark.parametrize("workers", [1, 3])
def test_cp_sat_runs_exactly_the_configured_worker_count(workers: int) -> None:
    assert two.observed_search_workers(two.SolverConfig(workers, 5.0)) == workers


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"NUM_SEARCH_WORKERS": DROP}, "NUM_SEARCH_WORKERS"),
        ({"NUM_SEARCH_WORKERS": None}, "NUM_SEARCH_WORKERS"),
        ({"NUM_SEARCH_WORKERS": 0}, "NUM_SEARCH_WORKERS"),
        ({"NUM_SEARCH_WORKERS": -2}, "NUM_SEARCH_WORKERS"),
        ({"NUM_SEARCH_WORKERS": True}, "NUM_SEARCH_WORKERS"),
        ({"NUM_SEARCH_WORKERS": "4"}, "NUM_SEARCH_WORKERS"),
        ({"NUM_SEARCH_WORKERS": 2.0}, "NUM_SEARCH_WORKERS"),
        ({"NUM_SEARCH_WORKERS": 9}, "at most 8"),
        ({"SOLVE_SECONDS": DROP}, "SOLVE_SECONDS"),
        ({"SOLVE_SECONDS": 0}, "SOLVE_SECONDS"),
        ({"SOLVE_SECONDS": math.inf}, "SOLVE_SECONDS"),
        ({"SOLVE_SECONDS": math.nan}, "SOLVE_SECONDS"),
        ({"SOLVE_SECONDS": "60"}, "SOLVE_SECONDS"),
        ({"WALL_BUDGET_SECONDS": DROP}, "WALL_BUDGET_SECONDS"),
        ({"WALL_BUDGET_SECONDS": 29}, "at least one full attempt"),
        ({"MAX_ATTEMPTS_PER_CELL": 0}, "MAX_ATTEMPTS_PER_CELL"),
        ({"DISTINCT_WITNESS_CAP": DROP}, "DISTINCT_WITNESS_CAP"),
        ({"GRANTED_BY": "AGENT"}, "Owner grant"),
        ({"GRANT_ID": " "}, "Owner grant"),
        ({"KIND": "OTHER"}, "Owner grant"),
        ({"ENGINE_SHA256": "0" * 64}, "different engine"),
        ({"TARGET_CELLS": [list(two.TARGET_KEYS[1]), list(two.TARGET_KEYS[0])]}, "CELL_A"),
        ({"TARGET_CELLS": [["66666665332221111111", 269]]}, "CELL_A"),
        ({"EXTRA": 1}, "unknown"),
        ({"SYMMETRY_REDUCTION": DROP}, "SYMMETRY_REDUCTION"),
        ({"SYMMETRY_REDUCTION": None}, "SYMMETRY_REDUCTION"),
        ({"SYMMETRY_REDUCTION": "LEX_LEADER"}, "SYMMETRY_REDUCTION"),
        ({"SYMMETRY_REDUCTION": True}, "SYMMETRY_REDUCTION"),
    ],
)
def test_an_invalid_grant_is_refused(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(two.GrantError, match=message):
        grant(tmp_path, **changes)


def test_run_refuses_before_any_solve_without_a_valid_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def spy(*args: object) -> object:
        calls.append(args)
        raise AssertionError("nothing may run without a valid grant")

    monkeypatch.setattr(two, "cp_sat_solve", spy)
    monkeypatch.setattr(two, "observed_search_workers", spy)
    monkeypatch.setattr(two, "exact_evaluator", spy)
    monkeypatch.setattr(two, "prepared_inputs", spy)
    durable = tmp_path / "run"
    with pytest.raises(two.GrantError, match="required"):
        two.main(["run", "--durable", str(durable)])
    with pytest.raises(two.GrantError, match="does not exist"):
        two.main(["run", "--grant", str(tmp_path / "absent.json"), "--durable", str(durable)])
    missing = write_grant(tmp_path / "missing.json", NUM_SEARCH_WORKERS=DROP)
    with pytest.raises(two.GrantError, match="NUM_SEARCH_WORKERS"):
        two.main(["run", "--grant", str(missing), "--durable", str(durable)])
    with pytest.raises(two.GrantError, match="required"):
        two.load_grant(None)
    assert not calls and not durable.exists()
    assert not (ROOT / two.DURABLE_RELATIVE).exists()


# Witness validation ------------------------------------------------------------------------


def double_overlap(structure: census.Structure) -> census.Structure:
    """Switch pair lines (a, x), (b, y) to (a, b), (x, y) with a, b on one triple line: the
    profile and the fiber survive, but tickets a and b then share two numbers."""

    owner = {v: p for p in structure.pairs for v in p}
    for triple in structure.triples:
        for a, b in combinations(triple, 2):
            if a not in owner or b not in owner or owner[a] == owner[b]:
                continue
            x = next(v for v in owner[a] if v != a)
            y = next(v for v in owner[b] if v != b)
            if x == y:
                continue
            rest = [p for p in structure.pairs if p not in (owner[a], owner[b])]
            new = cast(list[census.Pair], [(a, b), tuple(sorted((x, y)))])
            return census.Structure(structure.triples, tuple(sorted([*rest, *new])))
    raise AssertionError("no double-overlap switch found")


def test_every_witness_is_checked_for_profile_t_and_pair_overlap(
    incumbent: census.Structure, t255_classes: list[census.Structure]
) -> None:
    assert two.validate_witness(CELL_A, incumbent).triangles == 270
    assert two.validate_witness(CELL_A, block_shuffle(incumbent, 1)).triangles == 270
    with pytest.raises(two.WitnessError, match="degree profile"):
        two.validate_witness(CELL_B, incumbent)
    with pytest.raises(two.WitnessError, match="255 triangles"):
        two.validate_witness(CELL_A, t255_classes[0])
    broken = double_overlap(incumbent)
    with pytest.raises(two.WitnessError, match="more than one number"):
        two.validate_witness(CELL_A, broken)

    # The ticket recount is independent of the census structure path.
    tickets = census.portfolio(incumbent)
    two.check_portfolio(CELL_A.profile, 270, tickets)
    with pytest.raises(two.WitnessError, match="more than one number"):
        two.check_portfolio(CELL_A.profile, 270, census.portfolio(broken))
    with pytest.raises(two.WitnessError, match="degree profile"):
        two.check_portfolio(CELL_B.profile, 270, tickets)
    with pytest.raises(two.WitnessError, match="not T = 269"):
        two.check_portfolio(CELL_A.profile, 269, tickets)
    with pytest.raises(two.WitnessError, match="six distinct"):
        two.check_portfolio(CELL_A.profile, 270, ((1, 1, 2, 3, 4, 5), *tickets[1:]))
    added = next(n for n in tickets[1] if n not in tickets[0])
    off = (tuple(sorted({*tickets[0][1:], added})), *tickets[1:])
    with pytest.raises(two.WitnessError):
        two.check_portfolio(CELL_A.profile, 270, off)


# Canonical form and isomorphism deduplication -------------------------------------------


def rook_and_shrikhande() -> tuple[list[two.Line], list[two.Line]]:
    rook = [(a, b) for a, b in combinations(range(16), 2) if a // 4 == b // 4 or a % 4 == b % 4]
    steps = {(0, 1), (0, 3), (1, 0), (3, 0), (1, 1), (3, 3)}
    shrikhande = [
        (a, b)
        for a, b in combinations(range(16), 2)
        if ((a // 4 - b // 4) % 4, (a % 4 - b % 4) % 4) in steps
    ]
    return rook, shrikhande


def test_canonical_form_is_exact_where_colour_refinement_is_lossy() -> None:
    rook, shrikhande = rook_and_shrikhande()
    c6 = [tuple(sorted((v, (v + 1) % 6))) for v in range(6)]
    two_c3 = [(0, 1), (0, 2), (1, 2), (3, 4), (3, 5), (4, 5)]
    for n, left, right in ((16, rook, shrikhande), (6, c6, two_c3)):
        for lines in (left, right):
            incidence = [[line for line in lines if v in line] for v in range(n)]
            assert two._refine([0] * n, incidence) == [0] * n  # pyright: ignore[reportPrivateUsage]
        assert two.canonical_form(n, left).lines != two.canonical_form(n, right).lines
        for seed in range(3):
            perm = list(range(n))
            random.Random(seed).shuffle(perm)
            moved = [tuple(sorted(perm[v] for v in line)) for line in left]
            assert two.canonical_form(n, moved).lines == two.canonical_form(n, left).lines
    with pytest.raises(two.CanonicalFormError, match="exceeded"):
        two.canonical_form(16, rook, node_limit=1)
    with pytest.raises(two.CanonicalFormError, match="distinct"):
        two.canonical_form(4, [(0, 1), (0, 1)])


def test_witness_identity_ignores_ticket_order_and_number_labels(
    incumbent: census.Structure,
) -> None:
    canonical = two.canonicalize(CELL_A.profile, incumbent)
    assert canonical.witness_id == two.INCUMBENT_WITNESS_ID
    tickets = census.portfolio(incumbent)
    rng = random.Random(649)
    for _ in range(8):
        numbers = list(range(1, 50))
        rng.shuffle(numbers)
        moved = [tuple(sorted(numbers[n - 1] for n in t)) for t in tickets]
        rng.shuffle(moved)
        profile, structure = census.structure_from_tickets(moved)
        assert two.canonicalize(profile, structure).witness_id == two.INCUMBENT_WITNESS_ID
    # The verified automorphisms generate the incumbent's full group of order 288.
    form = two.canonical_form(census.TICKET_COUNT, (*incumbent.triples, *incumbent.pairs))
    group = {tuple(range(census.TICKET_COUNT))}
    frontier = list(group)
    while frontier:
        grown: list[tuple[int, ...]] = []
        for h in frontier:
            for g in form.automorphism_generators:
                image = tuple(g[h[v]] for v in range(census.TICKET_COUNT))
                if image not in group:
                    group.add(image)
                    grown.append(image)
        frontier = grown
    assert len(group) == 288


def test_relabelled_copies_never_consume_the_distinct_witness_cap(
    tmp_path: Path,
    selected: tuple[two.SelectedCell, ...],
    sources: dict[str, object],
    incumbent: census.Structure,
) -> None:
    copies = relabelings(incumbent, 6)
    solve = FakeSolver({"CELL_A": [incumbent, *copies], "CELL_B": [two.UNKNOWN]})
    evaluate = FakeEvaluator()
    resource = grant(tmp_path, MAX_ATTEMPTS_PER_CELL=7, DISTINCT_WITNESS_CAP=2)
    run = engine(tmp_path / "run", selected, sources, resource, solve, evaluate)
    summary = run.run()
    a = cell_summary(summary, "CELL_A")
    assert a["DISTINCT_WITNESSES"] == 1 and a["ISOMORPHIC_DUPLICATES"] == 6
    assert a["SESSION_END"] == two.ATTEMPT_BUDGET_REACHED
    assert a["CELL_STATE"] == "REALIZED_SEARCH_OPEN"
    assert len(evaluate.calls) == 1
    accepted = records(run.log, "ACCEPTED", "CELL_A")
    assert [k[2] for k in accepted] == [two.INCUMBENT_WITNESS_ID]
    assert next(iter(accepted.values()))["IS_INCUMBENT_CLASS"] is True
    duplicates = records(run.log, "DUPLICATE", "CELL_A")
    assert [k[2] for k in duplicates] == list(range(1, 7))
    for key, body in duplicates.items():
        mapping = cast(list[int], body["ISOMORPHISM_TO_REPRESENTATIVE"])
        assert two.relabel(copies[cast(int, key[2]) - 1], mapping) == incumbent
        assert body["WITNESS_ID"] == two.INCUMBENT_WITNESS_ID
    # Every relabelled copy was excluded in turn, so later attempts carry all of them.
    assert solve.calls[-1].cell is CELL_A and len(solve.calls[-1].excluded) == 6


def test_distinct_classes_with_equal_lossy_invariants_are_all_retained(
    tmp_path: Path, t255_classes: list[census.Structure]
) -> None:
    cell = two.TargetCell("SYNTHETIC_T255", CELL_A.profile_id, 255, 10**12, False)
    invariants = {
        (r.triangles, r.k4_with_contained_triple, r.k4_without_contained_triple)
        for r in (census.realization(cell.profile, s) for s in t255_classes)
    }
    assert len(t255_classes) == 7 and len(invariants) == 1
    script: list[census.Structure | str] = []
    for structure in t255_classes:
        script += [structure, *relabelings(structure, 1)]
    script.append(two.INFEASIBLE)
    log = census.DurableLog(tmp_path / "log.jsonl", {"TEST": "SYNTHETIC"})
    search = two.CellSearch(cell, log, FakeSolver({cell.name: script}), FakeEvaluator())
    config = two.SolverConfig(2, 5.0)
    while search.terminal is None:
        search.next_attempt(config)
    assert search.terminal == two.LABELED_SPACE_EXHAUSTED
    assert len(search.classes) == 7 and len(search.duplicates) == 7
    assert sorted(search.duplicates) == list(range(1, 14, 2))
    assert len({c.canonical.structure for c in search.classes.values()}) == 7


# Exact evaluator binding ---------------------------------------------------------------


def test_exact_evaluator_agrees_on_the_incumbent_and_its_relabellings(
    tmp_path: Path,
    selected: tuple[two.SelectedCell, ...],
    sources: dict[str, object],
    incumbent: census.Structure,
    t255_classes: list[census.Structure],
    official: census.Evaluator,
) -> None:
    start, _ = census.start_portfolio(ROOT)
    canonical = two.canonicalize(CELL_A.profile, incumbent).structure
    assert official(start) == official(census.portfolio(canonical)) == two.INCUMBENT_COUNT
    synthetic = t255_classes[0]
    assert official(census.portfolio(synthetic)) == official(
        census.portfolio(relabelings(synthetic, 1)[0])
    )

    resource = grant(tmp_path, MAX_ATTEMPTS_PER_CELL=1)
    solve = FakeSolver({"CELL_A": [block_shuffle(incumbent, 5)], "CELL_B": [two.UNKNOWN]})
    run = engine(tmp_path / "run", selected, sources, resource, solve, official)
    summary = run.run()
    (record,) = records(run.log, "ACCEPTED", "CELL_A").values()
    assert record["EXACT_COUNT"] == two.INCUMBENT_COUNT and record["GAIN"] is False
    assert record["IS_INCUMBENT_CLASS"] is True
    assert record["CANONICAL_TICKETS"] == [list(t) for t in census.portfolio(canonical)]
    assert record["UPPER_BOUND"] == 313_449_032 and record["BOUND_ROLE"] == two.BOUND_ROLE
    assert summary["SCIENTIFIC_GAIN_FOUND"] is False
    assert summary["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    assert not two.is_gain(two.INCUMBENT_COUNT) and two.is_gain(313_263_889)


# Status semantics and resume -------------------------------------------------------------


def test_unknown_is_never_treated_as_infeasible(
    tmp_path: Path,
    selected: tuple[two.SelectedCell, ...],
    sources: dict[str, object],
    incumbent: census.Structure,
) -> None:
    durable = tmp_path / "run"
    resource = grant(tmp_path)
    first = FakeSolver({"CELL_A": [two.UNKNOWN], "CELL_B": [two.UNKNOWN]})
    summary = engine(durable, selected, sources, resource, first, FakeEvaluator()).run()
    for name in ("CELL_A", "CELL_B"):
        cell = cell_summary(summary, name)
        assert cell["SESSION_END"] == two.UNRESOLVED_UNKNOWN
        assert cell["CELL_STATE"] == "UNRESOLVED" and cell["REALIZED_AT_T"] is False
        assert cast(dict[str, int], cell["STATUS_COUNTS"])[two.UNKNOWN] == 1

    # A later session re-attempts both cells with the same (empty) exclusions.
    second = FakeSolver({"CELL_A": [two.UNKNOWN, incumbent], "CELL_B": [two.UNKNOWN, "INFEASIBLE"]})
    run = engine(durable, selected, sources, resource, second, FakeEvaluator())
    summary = run.run()
    assert [(c.cell.name, c.attempt, c.excluded) for c in second.calls[:2]] == [
        ("CELL_A", 1, ()),
        ("CELL_B", 1, ()),
    ]
    b = cell_summary(summary, "CELL_B")
    assert b["CELL_STATE"] == two.REFUTED_AT_T and b["SESSION_END"] == two.REFUTED_AT_T
    assert b["STATUS_COUNTS"] == {"OPTIMAL": 0, "FEASIBLE": 0, "INFEASIBLE": 1, "UNKNOWN": 1}
    assert cell_summary(summary, "CELL_A")["CELL_STATE"] == "REALIZED_SEARCH_OPEN"
    assert summary["SESSIONS"] == 2

    log = census.DurableLog(tmp_path / "x.jsonl", {"TEST": "STATUS"})
    contradiction = two.CellSearch(
        CELL_A, log, FakeSolver({"CELL_A": ["INFEASIBLE"]}), FakeEvaluator()
    )
    with pytest.raises(two.ContradictionError):
        contradiction.next_attempt(resource.config)
    invalid = two.CellSearch(
        CELL_B, log, FakeSolver({"CELL_B": ["MODEL_INVALID"]}), FakeEvaluator()
    )
    with pytest.raises(two.SolverContractError, match="MODEL_INVALID"):
        invalid.next_attempt(resource.config)
    assert ("ATTEMPT", "CELL_B", 0) not in log.records


def test_resume_never_accepts_a_witness_twice(
    tmp_path: Path, t255_classes: list[census.Structure]
) -> None:
    cell = two.TargetCell("SYNTHETIC_T255", CELL_A.profile_id, 255, 10**12, False)
    path = tmp_path / "log.jsonl"
    header = {"TEST": "RESUME"}
    rep0, rep1, rep2 = t255_classes[:3]
    script: list[census.Structure | str] = [
        rep0,
        rep1,
        *relabelings(rep0, 1),
        *relabelings(rep1, 1),
        rep2,
    ]
    config = two.SolverConfig(2, 5.0)
    crashing = FakeEvaluator(fail_at=1)
    first = two.CellSearch(
        cell, census.DurableLog(path, header), FakeSolver({cell.name: script}), crashing
    )
    first.next_attempt(config)
    with pytest.raises(Interrupted):
        first.next_attempt(config)  # rep1's attempt is logged; its exact count is not

    evaluate = FakeEvaluator()
    solve = FakeSolver({cell.name: script})
    second = two.CellSearch(cell, census.DurableLog(path, header), solve, evaluate)
    assert second.attempts == 2 and len(second.classes) == 2 and len(evaluate.calls) == 1
    for _ in range(3):
        second.next_attempt(config)
    assert len(second.classes) == 3 and second.duplicates == [2, 3]
    assert len(evaluate.calls) == 2 and [c.attempt for c in solve.calls] == [2, 3, 4]

    replay_eval, replay_solve = FakeEvaluator(), FakeSolver({})
    log = census.DurableLog(path, header)
    third = two.CellSearch(cell, log, replay_solve, replay_eval)
    assert not replay_eval.calls and not replay_solve.calls
    accepted = records(log, "ACCEPTED", cell.name)
    assert len(accepted) == 3 == len({k[2] for k in accepted})
    assert set(third.classes) == {k[2] for k in accepted}
    assert sorted(cast(int, r["CLASS_INDEX"]) for r in accepted.values()) == [0, 1, 2]
    with pytest.raises(census.DurableLogError, match="duplicate"):
        log.append(next(iter(accepted)), {})


def test_wall_budget_foreign_roots_and_single_writer(
    tmp_path: Path,
    selected: tuple[two.SelectedCell, ...],
    sources: dict[str, object],
) -> None:
    resource = grant(tmp_path, SOLVE_SECONDS=600, WALL_BUDGET_SECONDS=900)
    ticks = iter([0.0, 0.0, 400.0, 400.0])
    solve = FakeSolver({"CELL_A": [two.UNKNOWN], "CELL_B": [two.UNKNOWN]})
    summary = engine(
        tmp_path / "run", selected, sources, resource, solve, FakeEvaluator(), lambda: next(ticks)
    ).run()
    assert [c.cell.name for c in solve.calls] == ["CELL_A"]
    assert cell_summary(summary, "CELL_B")["SESSION_END"] == two.WALL_BUDGET_REACHED

    for name in two.FOREIGN_DURABLE_NAMES:
        with pytest.raises(two.TwoCellError, match="never opens"):
            engine(tmp_path / name, selected, sources, resource, solve, FakeEvaluator())
        assert not (tmp_path / name).exists()
    with (
        two.exclusive_lock(tmp_path / "locked"),
        pytest.raises(two.TwoCellError, match="holds the durable lock"),
        two.exclusive_lock(tmp_path / "locked"),
    ):
        pass


# Model symmetry and the optional lex-leader reduction -----------------------------------------

LEX = two.SYMMETRY_LEX_LEADER
T255 = two.TargetCell("SYNTHETIC_T255", CELL_A.profile_id, 255, 10**12, False)
Lines = dict[two.Line, Any]


def family_model(profile: Sequence[int], capacity: int, ceiling: int) -> tuple[Any, Lines, Lines]:
    """census.support_model for one profile, with ticket count and capacity as parameters.

    At 20 tickets of six numbers it is both pinned cell models byte for byte; small members
    are the synthetic instances.
    """

    n = len(profile)
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model: Any = cp_model.CpModel()
    degrees = [model.NewIntVar(profile[v], profile[v], f"d{v}") for v in range(n)]
    model.AddAllowedAssignments(degrees, (tuple(profile),))
    active = [v for v in range(n) if profile[v]]
    triples: Lines = {t: model.NewBoolVar(f"t{t}") for t in combinations(active, 3)}
    doubles: Lines = {p: model.NewBoolVar(f"b{p}") for p in combinations(range(n), 2)}
    by_pair: dict[two.Line, list[Any]] = {p: [] for p in doubles}
    for t, variable in triples.items():
        for pair in combinations(t, 2):
            by_pair[pair].append(variable)
    for v, degree in enumerate(degrees):
        model.Add(sum(x for t, x in triples.items() if v in t) == degree)
        model.Add(sum(x for p, x in doubles.items() if v in p) == capacity - degree)
    model.Add(sum(triples.values()) == sum(profile) // 3)
    model.Add(sum(doubles.values()) == (n * capacity - sum(profile)) // 2)
    edges: Lines = {}
    for p, double in doubles.items():
        model.Add(sum(by_pair[p]) + double <= 1)
        edges[p] = model.NewBoolVar(f"e{p}")
        model.Add(edges[p] == sum(by_pair[p]) + double)
    indicators: list[Any] = []
    by_ends: dict[two.Line, list[Any]] = {p: [] for p in doubles}
    for center in range(n):
        for a, b in combinations((v for v in range(n) if v != center), 2):
            x = model.NewBoolVar(f"o{center}_{a}_{b}")
            model.Add(
                x
                >= edges[(min(center, a), max(center, a))]
                + edges[(min(center, b), max(center, b))]
                - edges[(a, b)]
                - 1
            )
            indicators.append(x)
            by_ends[(a, b)].append(x)
    # A non-adjacent pair has at least (c + d_a) + (c + d_b) - (n - 2) common neighbours.
    offset = (n - 2) - 2 * capacity
    for (a, b), edge in edges.items():
        model.Add(sum(by_ends[(a, b)]) >= degrees[a] + degrees[b] - offset).OnlyEnforceIf(
            edge.Not()
        )
    model.Add(sum(indicators) <= ceiling)
    return model, triples, doubles


def proto_sha256(model: Any) -> str:
    return census.sha256_bytes(str(model.Proto()).encode())


def solve(model: Any) -> tuple[str, Any]:
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    solver: Any = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.random_seed = census.RANDOM_SEED
    return str(solver.StatusName(solver.Solve(model))), solver


def synthetic_model(
    profile: Sequence[int], t: int, *, reduce: bool, capacity: int = 3
) -> tuple[Any, Lines, Lines]:
    wedges = sum(math.comb(capacity + d, 2) for d in profile)
    model, triples, pairs = family_model(profile, capacity, wedges - 3 * t)
    if reduce:
        two.add_symmetry_reduction(model, triples, pairs, profile)
    return model, triples, pairs


def enumerate_structures(profile: Sequence[int], t: int, *, reduce: bool) -> list[census.Structure]:
    """Every labelled structure of a synthetic cell, by census no-goods until INFEASIBLE."""

    model, triples, pairs = synthetic_model(profile, t, reduce=reduce)
    found: list[census.Structure] = []
    while True:
        status, solver = solve(model)
        if status == two.INFEASIBLE:
            return found
        assert status in two.REALIZED  # an UNKNOWN never counts as exhaustion
        typed = cast(Mapping[census.Triple, Any], triples), cast(Mapping[census.Pair, Any], pairs)
        found.append(census.decode_structure(solver, *typed))
        census.add_nogood(model, *typed, found[-1])


def class_of(profile: Sequence[int], structure: census.Structure) -> tuple[two.Line, ...]:
    return two.canonical_form(len(profile), (*structure.triples, *structure.pairs)).lines


def lex_leader_representative(
    profile: Sequence[int], structure: census.Structure
) -> census.Structure:
    """Apply a violated generator until none is. Each step is strictly lex-larger, so this ends,
    inside the reduced region and inside the structure's class."""

    while (sigma := two.lex_leader_violation(profile, structure)) is not None:
        structure = two.relabel(structure, sigma)
    return structure


def test_synthetic_family_is_the_pinned_census_model_at_k20_parameters() -> None:
    for cell in two.TARGET_CELLS:
        model, _, _ = family_model(cell.profile, census.TICKET_CAPACITY, cell.ceiling)
        assert proto_sha256(model) == two.MODEL_PROTO_SHA256[cell.name]
    # Both reduced models: every generator verified on the pinned model, then pinned.
    assert two.verify_reduced_cell_models() == two.REDUCED_MODEL_PROTO_SHA256


def test_the_symmetry_group_is_exactly_the_degree_block_stabilizer() -> None:
    blocks = {
        "CELL_A": (tuple(range(12)), tuple(range(12, 18)), (18, 19)),
        "CELL_B": (tuple(range(4)), tuple(range(4, 11)), (11,), (12, 13), tuple(range(14, 20))),
    }
    orders = {"CELL_A": 689_762_304_000, "CELL_B": 174_182_400}
    crossings = {"CELL_A": ((11, 12), (17, 18), (0, 19)), "CELL_B": ((3, 4), (10, 11), (13, 14))}
    for cell in two.TARGET_CELLS:
        assert two.degree_blocks(cell.profile) == blocks[cell.name]
        assert math.prod(math.factorial(len(b)) for b in blocks[cell.name]) == orders[cell.name]
        generators = two.symmetry_generators(cell.profile)
        assert len(generators) == sum(len(b) - 1 for b in blocks[cell.name])
        # Adjacent transpositions inside a block generate that block's whole symmetric group.
        moved = [tuple(u for u in range(census.TICKET_COUNT) if s[u] != u) for s in generators]
        assert moved == [(b[i], b[i + 1]) for b in blocks[cell.name] for i in range(len(b) - 1)]

        model, _, _ = census.k20_model(cell.profile, cell.ceiling)
        form = two.ModelForm.of(model.Proto())
        for sigma in generators:
            form.automorphism(sigma)
        reverse = list(range(census.TICKET_COUNT))
        for block in blocks[cell.name]:
            for v, w in zip(block, reversed(block), strict=True):
                reverse[v] = w
        form.automorphism(reverse)  # a group element that is not a generator
        # Any move between blocks breaks the model, at the degree domains or the triple lines.
        for v, w in crossings[cell.name]:
            swap = list(range(census.TICKET_COUNT))
            swap[v], swap[w] = w, v
            with pytest.raises(two.SymmetryError, match=r"domains|outside the model"):
                form.automorphism(swap)


def test_the_automorphism_check_refuses_what_it_cannot_prove(incumbent: census.Structure) -> None:
    fano = (3,) * 7
    cp_model: Any = import_module("ortools.sat.python.cp_model")

    def built() -> tuple[Any, Lines, Lines]:
        return family_model(fano, 3, 0)

    model, triples, pairs = built()
    two.add_symmetry_reduction(model, triples, pairs, fano)
    with pytest.raises(two.SymmetryError, match="cannot be checked"):
        two.add_symmetry_reduction(model, triples, pairs, fano)  # never stacked or re-checked
    model, triples, pairs = built()
    model.Add(triples[(0, 1, 2)] == 1)
    with pytest.raises(two.SymmetryError, match="constraint set"):
        two.add_symmetry_reduction(model, triples, pairs, fano)
    model, triples, pairs = built()
    model.Minimize(triples[(0, 1, 2)])
    with pytest.raises(two.SymmetryError, match="objective"):
        two.add_symmetry_reduction(model, triples, pairs, fano)
    model, triples, pairs = built()
    model.AddAllDifferent([pairs[(0, 1)], pairs[(0, 2)]])
    with pytest.raises(two.SymmetryError, match="cannot be checked"):
        two.add_symmetry_reduction(model, triples, pairs, fano)
    model, triples, pairs = built()
    model.NewBoolVar("z")
    with pytest.raises(two.SymmetryError, match="no known relabelling"):
        two.add_symmetry_reduction(model, triples, pairs, fano)
    with pytest.raises(two.SymmetryError, match="line order"):
        two.add_symmetry_reduction(model, triples, pairs, (3, 3, 3, 3, 3, 3, 0))

    # Domains alone decide here: no constraint mentions either ticket.
    bare: Any = cp_model.CpModel()
    bare.NewIntVar(5, 5, "d0")
    bare.NewIntVar(1, 1, "d1")
    with pytest.raises(two.SymmetryError, match="domains"):
        two.ModelForm.of(bare.Proto()).automorphism((1, 0))
    two.ModelForm.of(bare.Proto()).automorphism((0, 1))

    # A no-good is not symmetric: the check runs on the bare model, before any exclusion.
    model, triples, pairs = census.k20_model(CELL_A.profile, CELL_A.ceiling)
    census.add_nogood(model, triples, pairs, incumbent)
    with pytest.raises(two.SymmetryError, match="constraint set"):
        two.add_symmetry_reduction(model, triples, pairs, CELL_A.profile)


SYNTHETIC_CELLS = [
    # profile, T, labelled structures, reduced structures, isomorphism classes
    ((2, 2, 2, 1, 1, 1, 0), 0, 84, 14, 4),
    ((2, 2, 2, 1, 1, 1, 0), 11, 78, 13, 3),
    ((2, 2, 2, 1, 1, 1, 0), 12, 0, 0, 0),
    ((3, 2, 2, 2, 1, 1, 1, 0), 0, 216, 36, 8),
    ((3, 2, 2, 2, 1, 1, 1, 0), 14, 96, 16, 4),
    ((1, 1, 1, 0, 0, 0, 0), 0, 228, 8, 5),
    ((3, 3, 3, 3, 3, 3, 3), 0, 30, 1, 1),
]


@pytest.mark.parametrize(("profile", "t", "labelled", "reduced", "classes"), SYNTHETIC_CELLS)
def test_reduction_keeps_every_isomorphism_class_of_exhaustive_synthetic_cells(
    profile: tuple[int, ...], t: int, labelled: int, reduced: int, classes: int
) -> None:
    base = enumerate_structures(profile, t, reduce=False)
    kept = enumerate_structures(profile, t, reduce=True)
    assert (len(base), len(kept)) == (labelled, reduced)
    assert len(set(base)) == len(base) and len(set(kept)) == len(kept)
    # The group maps the base solution set onto itself.
    generators = two.symmetry_generators(profile)
    assert {two.relabel(s, sigma) for s in base for sigma in generators} <= set(base)
    # Exactly the base structures inside the lex-leader region: no false infeasibility and no
    # structure the region excludes.
    assert set(kept) == {s for s in base if two.lex_leader_violation(profile, s) is None}
    base_classes = {class_of(profile, s) for s in base}
    assert {class_of(profile, s) for s in kept} == base_classes
    assert len(base_classes) == classes
    # Every labelled member reaches a kept representative of its own class.
    for structure in base:
        representative = lex_leader_representative(profile, structure)
        assert representative in kept
        assert class_of(profile, representative) == class_of(profile, structure)


@pytest.mark.parametrize("profile", [(2, 2, 2, 1, 1, 1, 0), (1, 1, 1, 0, 0, 0, 0), (3,) * 7])
def test_lex_auxiliaries_are_exactly_the_equal_prefix_indicators(
    profile: tuple[int, ...],
) -> None:
    """Fixing a kept structure fixes every lex auxiliary: no second completion exists."""

    for structure in enumerate_structures(profile, 0, reduce=True):
        model, triples, pairs = synthetic_model(profile, 0, reduce=True)
        present = {*structure.triples, *structure.pairs}
        for key, x in {**triples, **pairs}.items():
            model.Add(x == int(key in present))
        status, solver = solve(model)
        assert status in two.REALIZED
        names = [v.name for v in model.Proto().variables]
        aux = [model.GetBoolVarFromProtoIndex(i) for i, n in enumerate(names) if n[:3] == "lex"]
        assert aux
        model.AddBoolOr([x.Not() if solver.BooleanValue(x) else x for x in aux])
        assert solve(model)[0] == two.INFEASIBLE


def test_every_fixture_class_keeps_a_member_in_the_reduced_k20_model(
    incumbent: census.Structure,
    t255_classes: list[census.Structure],
    official: census.Evaluator,
) -> None:
    profile = T255.profile
    base, base_triples, base_pairs = census.k20_model(profile, T255.ceiling)
    reduced, triples, pairs = census.k20_model(profile, T255.ceiling)
    two.add_symmetry_reduction(reduced, triples, pairs, profile)

    def admits(model: Any, lines: Mapping[Any, Any], structure: census.Structure) -> bool:
        """Membership only: every triple and pair variable is fixed on a copy of the model."""

        present = {*structure.triples, *structure.pairs}
        fixed: Any = model.Clone()
        for key, x in lines.items():
            fixed.Add(fixed.GetBoolVarFromProtoIndex(x.Index()) == int(key in present))
        status, _ = solve(fixed)
        assert status != two.UNKNOWN
        return status in two.REALIZED

    base_lines = {**base_triples, **base_pairs}
    reduced_lines = {**triples, **pairs}
    representatives: list[census.Structure] = []
    outside = 0
    for structure in (incumbent, *t255_classes):
        canonical = two.canonicalize(profile, structure).structure
        for labelled in (structure, *relabelings(structure, 1)):
            representative = lex_leader_representative(profile, labelled)
            # The engine evaluates this canonical portfolio, so the exact count is unchanged.
            assert two.canonicalize(profile, representative).structure == canonical
            assert admits(base, base_lines, labelled)
            assert admits(reduced, reduced_lines, representative)
            inside = two.lex_leader_violation(profile, labelled) is None
            assert admits(reduced, reduced_lines, labelled) is inside
            outside += not inside
        representatives.append(lex_leader_representative(profile, structure))
    assert outside > 0
    # The incumbent class and the seven same-invariant classes all stay apart.
    identities = {two.canonicalize(profile, r).witness_id for r in representatives}
    assert len(identities) == 8 and two.INCUMBENT_WITNESS_ID in identities
    synthetic = representatives[1]
    assert official(census.portfolio(synthetic)) == official(census.portfolio(t255_classes[0]))


def test_reduced_attempts_end_on_classes_and_never_upgrade_unknown(
    tmp_path: Path, incumbent: census.Structure, t255_classes: list[census.Structure]
) -> None:
    profile = T255.profile
    leaders = [lex_leader_representative(profile, s) for s in t255_classes]
    script: list[census.Structure | str] = [two.UNKNOWN, *leaders, two.INFEASIBLE]
    reduced, base = two.SolverConfig(2, 5.0, symmetry=LEX), two.SolverConfig(2, 5.0)
    header = {"TEST": "REDUCED"}
    for config, terminal in (
        (reduced, two.CLASS_SPACE_EXHAUSTED),
        (base, two.LABELED_SPACE_EXHAUSTED),
    ):
        path = tmp_path / f"{terminal}.jsonl"
        search = two.CellSearch(
            T255, census.DurableLog(path, header), FakeSolver({T255.name: script}), FakeEvaluator()
        )
        assert search.next_attempt(config).status == two.UNKNOWN
        assert search.terminal is None and not search.classes and not search.excluded
        while search.terminal is None:
            search.next_attempt(config)
        assert search.terminal == terminal and search.summary()["CELL_STATE"] == terminal
        assert len(search.classes) == 7 and not search.duplicates
        replayed = FakeSolver({})
        again = two.CellSearch(T255, census.DurableLog(path, header), replayed, FakeEvaluator())
        assert again.terminal == terminal and set(again.classes) == set(search.classes)
        assert not replayed.calls

    # A reduced attempt may only return a member of its region; the original model may not care.
    outside = next(
        s for s in relabelings(t255_classes[0], 8) if two.lex_leader_violation(profile, s)
    )
    log = census.DurableLog(tmp_path / "outside.jsonl", header)
    strict = two.CellSearch(T255, log, FakeSolver({T255.name: [outside]}), FakeEvaluator())
    with pytest.raises(two.SolverContractError, match="outside its region"):
        strict.next_attempt(reduced)
    assert ("ATTEMPT", T255.name, 0) not in log.records
    loose = two.CellSearch(T255, log, FakeSolver({T255.name: [outside]}), FakeEvaluator())
    loose.next_attempt(base)
    assert len(loose.classes) == 1

    # INFEASIBLE with no exclusion still contradicts the incumbent in the reduced model.
    log = census.DurableLog(tmp_path / "cell-a.jsonl", header)
    contradiction = two.CellSearch(
        CELL_A, log, FakeSolver({"CELL_A": [two.INFEASIBLE]}), FakeEvaluator()
    )
    with pytest.raises(two.ContradictionError):
        contradiction.next_attempt(reduced)
    assert lex_leader_representative(CELL_A.profile, incumbent) != incumbent


def test_the_reduced_model_is_pinned_and_refused_before_any_solve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def spy(*args: object) -> object:
        calls.append(args)
        raise AssertionError("no solve may start")

    monkeypatch.setattr(two, "configured_solver", spy)
    request = two.AttemptRequest(CELL_B, 0, (), two.SolverConfig(1, 5.0, symmetry=LEX))
    with pytest.raises(AssertionError, match="no solve"):
        two.cp_sat_solve(request)  # the reduced model matches its pin and reaches the solver
    assert len(calls) == 1

    monkeypatch.setitem(two.REDUCED_MODEL_PROTO_SHA256, "CELL_B", "0" * 64)
    with pytest.raises(two.SourceIdentityError, match="reduced model"):
        two.cp_sat_solve(request)
    monkeypatch.setattr(two, "observed_search_workers", spy)
    monkeypatch.setattr(two, "exact_evaluator", spy)
    path = write_grant(tmp_path / "grant.json", SYMMETRY_REDUCTION=LEX)
    durable = tmp_path / "run"
    with pytest.raises(two.SourceIdentityError, match="reduced model"):
        two.main(["run", "--grant", str(path), "--durable", str(durable)])
    assert len(calls) == 1 and not durable.exists()
    assert two.grant_template()["SYMMETRY_REDUCTION"] is None
