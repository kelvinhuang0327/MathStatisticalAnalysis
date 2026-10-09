"""Focused, non-heavy tests for the two-open-cell targeted K20 solver.

No target cell is solved: engine flows use an injected fake solver. CP-SAT runs only the
one-variable worker probe. The official evaluator recounts only the canonical start, its
canonical relabelling and one synthetic class. The synthetic same-T classes are pair-switches
of the incumbent at T = 255, built in pure Python.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from itertools import combinations
from pathlib import Path
from typing import cast

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
