"""Non-heavy contract tests for the K20 fiber near-top-S3 Slice-1 census engine.

No real Slice-1 profile is searched: CP-SAT runs only on a tiny synthetic model,
census flows use an injected fake solver and evaluator, and the official
evaluator only recounts the canonical start and the two K4 quartet shapes.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from importlib import import_module
from itertools import combinations
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_fiber_near_top_s3_census as census

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / census.MANIFEST_RELATIVE
INCUMBENT = "55555555555511111100"
OTHER_A = "66666665332221111111"
OTHER_B = "66666665322222211110"
# The R30 module name and every R30 module SHA-256 prefix seen so far; none may be bound.
R30_MODULE_MARKERS = (
    b"dynamic_family_max_r30",
    b"4f2385bd",
    b"17b836f5",
    b"230cb455",
    b"795f16da",
    b"174568b2",
)
SYNTHETIC_ROWS: list[object] = [
    [INCUMBENT, 313_588_232, 270, [[270, 313_588_232]]],
    [OTHER_A, 313_587_560, 269, [[269, 313_587_560]]],
    [OTHER_B, 313_587_560, 269, [[269, 313_587_560]]],
]


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
def incumbent() -> tuple[census.Profile, census.Structure]:
    tickets, _ = census.start_portfolio(ROOT)
    return census.structure_from_tickets(tickets)


@pytest.fixture(scope="module")
def official() -> census.Evaluator:
    return census.official_evaluator()


def relabel(structure: census.Structure, perm: Sequence[int]) -> census.Structure:
    triples = sorted(
        cast(census.Triple, tuple(sorted(perm[v] for v in t))) for t in structure.triples
    )
    pairs = sorted(cast(census.Pair, tuple(sorted(perm[v] for v in p))) for p in structure.pairs)
    return census.Structure(tuple(triples), tuple(pairs))


def variants(structure: census.Structure, count: int) -> list[census.Structure]:
    """Distinct relabellings inside the degree-5 block: same profile, same 270 triangles."""

    found = [structure]
    for i, j in combinations(range(12), 2):
        perm = list(range(census.TICKET_COUNT))
        perm[i], perm[j] = j, i
        candidate = relabel(structure, perm)
        if candidate not in found:
            found.append(candidate)
        if len(found) == count:
            return found
    raise AssertionError("not enough distinct relabellings")


class FakeSolver:
    """Serves each profile's structures in order, honouring the request's no-goods."""

    def __init__(
        self,
        structures: Mapping[str, Sequence[census.Structure]],
        unknown: frozenset[str] = frozenset(),
        fail_at: int | None = None,
    ) -> None:
        self.structures = structures
        self.unknown = unknown
        self.fail_at = fail_at
        self.calls: list[census.SolveRequest] = []

    def __call__(self, request: census.SolveRequest) -> census.SolveOutcome:
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise Interrupted("solver crash")
        self.calls.append(request)
        pid = census.profile_id(request.profile)
        if pid in self.unknown:
            return census.SolveOutcome("UNKNOWN", None, 0.0)
        for structure in self.structures.get(pid, ()):
            if structure not in request.excluded:
                return census.SolveOutcome("FEASIBLE", structure, 0.0)
        return census.SolveOutcome("INFEASIBLE", None, 0.0)


class FakeEvaluator:
    def __init__(self, counts: Callable[[census.Tickets], int], fail_at: int | None = None) -> None:
        self.counts = counts
        self.fail_at = fail_at
        self.calls: list[census.Tickets] = []

    def __call__(self, tickets: census.Tickets) -> int:
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise Interrupted("evaluator crash")
        self.calls.append(tickets)
        return self.counts(tickets)


def synthetic_manifest(
    tmp_path: Path,
    rows: Sequence[object] | None = None,
    edit: Callable[[dict[str, Any]], None] | None = None,
) -> census.Manifest:
    data = cast(dict[str, Any], json.loads(MANIFEST.read_bytes()))
    rows = list(SYNTHETIC_ROWS if rows is None else rows)
    data["SLICE1"].update(
        PROFILES=rows,
        PROFILE_COUNT=len(rows),
        PAIR_COUNT=len(rows),
        PROFILES_SHA256=census.rows_sha256(rows),
        INCUMBENT_FIRST_PROFILE=cast(list[object], rows[0])[0],
    )
    if edit is not None:
        edit(data)
    raw = census.render_manifest(data)
    path = tmp_path / f"manifest-{hashlib.sha256(raw).hexdigest()[:8]}.json"
    path.write_bytes(raw)
    return census.load_manifest(path, hashlib.sha256(raw).hexdigest())


def below_start(_: census.Tickets) -> int:
    return census.START_COUNT - 7


def logs(directory: Path) -> tuple[bytes, bytes]:
    return (
        (directory / census.PROOF_LOG).read_bytes(),
        (directory / census.WITNESS_LEDGER).read_bytes(),
    )


def hex_strings(value: object) -> Iterator[str]:
    """Every hex-only string in the manifest: a digest, a Git id or a leftover prefix."""

    if isinstance(value, dict):
        for item in cast(dict[str, object], value).values():
            yield from hex_strings(item)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            yield from hex_strings(item)
    elif isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,}", value):
        yield value


# Manifest and authority ----------------------------------------------------------------------


def test_manifest_is_pinned_canonical_and_rebuilds_byte_identically(
    manifest: census.Manifest,
) -> None:
    raw = MANIFEST.read_bytes()
    assert Path(census.__file__).resolve().is_relative_to(ROOT)
    assert hashlib.sha256(raw).hexdigest() == census.MANIFEST_SHA256 == manifest.sha256
    data = cast(dict[str, Any], json.loads(raw))
    assert census.render_manifest(data) == raw
    authorities = {k: v for k, v in data["AUTHORITIES"].items() if k != "R30"}
    derivation = {
        **data["AUTHORITIES"]["R30"]["SEALED_DERIVATION"],
        "ROWS": list(reversed(data["SLICE1"]["PROFILES"])),
    }
    assert census.render_manifest(census.build_manifest(derivation, authorities)) == raw


def test_slice1_refreezes_byte_identically_from_the_sealed_result(
    manifest: census.Manifest,
) -> None:
    """Deterministic freeze: derive Slice 1 twice from the sealed data, rebuild the bytes."""

    sealed = Path(census.verify_r30_result())
    first = census.derive_slice1(sealed, ROOT)
    assert census.derive_slice1(sealed, ROOT) == first
    data = cast(dict[str, Any], manifest.data)
    authorities = {k: v for k, v in data["AUTHORITIES"].items() if k != "R30"}
    assert authorities["R28"] == census.verify_r28(ROOT)
    assert sorted(cast(list[Any], first["ROWS"])) == sorted(data["SLICE1"]["PROFILES"])
    rebuilt = census.render_manifest(census.build_manifest(first, authorities))
    assert rebuilt == MANIFEST.read_bytes()


def test_slice1_needs_only_sealed_data_and_committed_r28_code(
    tmp_path: Path, manifest: census.Manifest
) -> None:
    """No R30 module is load-bearing: a lone copy of the sealed result rebuilds Slice 1."""

    isolated = tmp_path / "sealed-r30-result.json"
    isolated.write_bytes(Path(census.verify_r30_result()).read_bytes())
    derived = census.derive_slice1(isolated, ROOT)
    data = cast(dict[str, Any], manifest.data)
    sealed = {k: v for k, v in derived.items() if k != "ROWS"}
    assert sealed == data["AUTHORITIES"]["R30"]["SEALED_DERIVATION"]
    assert sorted(cast(list[Any], derived["ROWS"])) == sorted(data["SLICE1"]["PROFILES"])
    # The child ran committed R28 blobs only; the R28 tree has no R29 or R30 module at all.
    loaded = cast(dict[str, str], derived["R28_LOADED_MODULES"])
    assert derived["R30_MODULES_LOADED"] == []
    for path, digest in loaded.items():
        assert hashlib.sha256(census.git_show(ROOT, census.R28_COMMIT, path)).hexdigest() == digest
    tree = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", census.R28_COMMIT, "src"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert set(loaded) <= set(tree)
    assert not [p for p in tree if re.search(r"_r(29|30)\.py$", p)]
    for blob in (MANIFEST.read_bytes(), Path(census.__file__).read_bytes()):
        assert not [m for m in R30_MODULE_MARKERS if m in blob]
    # The sealed data is content-addressed: one changed byte stops the derivation.
    isolated.write_bytes(isolated.read_bytes() + b" ")
    with pytest.raises(census.ManifestError, match="SHA-256 changed"):
        census.derive_slice1(isolated, ROOT)


def test_manifest_changes_fail_closed(tmp_path: Path) -> None:
    raw = MANIFEST.read_bytes()
    edited = tmp_path / "edited.json"
    edited.write_bytes(raw.replace(b'"CAP": 16', b'"CAP": 17'))
    with pytest.raises(census.ManifestError, match="SHA-256 differs"):
        census.load_manifest(edited)
    with pytest.raises(census.ManifestError, match="witness cap"):
        census.load_manifest(edited, hashlib.sha256(edited.read_bytes()).hexdigest())
    spaced = tmp_path / "spaced.json"
    spaced.write_bytes(raw.replace(b'"CAP": 16', b'"CAP":  16'))
    with pytest.raises(census.ManifestError, match="not canonical"):
        census.load_manifest(spaced, hashlib.sha256(spaced.read_bytes()).hexdigest())


def test_authorities_are_full_hashes_bound_to_r28_r30_and_the_evaluator(
    manifest: census.Manifest,
) -> None:
    authorities = cast(dict[str, Any], manifest.data["AUTHORITIES"])
    # 20-digit strings are degree profiles; every other hex-only string is a full digest.
    digests = [h for h in hex_strings(manifest.data) if not (len(h) == 20 and h.isdecimal())]
    assert len(digests) == 37
    assert all(len(d) in (40, 64) for d in digests), "a SHA prefix was left in the manifest"
    r30 = authorities["R30"]
    assert r30["RESULT_SHA256"] == (
        "5b7e5d10583d275409441c422e107994fb6058fae5060933c6c35c436481e777"
    )
    # The R30 producer module is unresolved and bound nowhere: no path, no SHA, no prefix.
    assert r30["MODULE_AUTHORITY_STATUS"] == "UNRESOLVED_NON_LOAD_BEARING"
    assert r30["RESULT_ROLE"] == "LOAD_BEARING_SEALED_DATA" and r30["RESULT_TRACKED"] is True
    assert r30["WORKTREE"] == str(ROOT)
    assert r30["RESULT_PATH"] == census.R30_RESULT_RELATIVE
    assert "RESULT_SEGMENT1_COPY_PATH" not in r30
    assert (
        Path(census.verify_r30_result()).resolve()
        == (ROOT / census.R30_RESULT_RELATIVE).resolve()
    )
    assert not [k for k in r30 if k.startswith(("MODULE_PATH", "MODULE_SHA", "OLD_MODULE"))]
    assert not [m for m in R30_MODULE_MARKERS if m in MANIFEST.read_bytes()]
    sealed = r30["SEALED_DERIVATION"]
    assert sealed["METHOD"] == "SEALED_R30_RESULT_DATA_WITH_COMMITTED_R28_BOUND_CODE"
    assert sealed["R30_MODULES_LOADED"] == []
    assert sealed["SEALED_LEDGER_SHA256"] == census.R30_LEDGER_SHA256
    assert sealed["LEDGER_COUNT"] == 1399 and sealed["LEDGER_ROWS_AT_FLOOR"] == 0
    assert sealed["OWNERS"] == [INCUMBENT]
    assert sealed["FAMILY_UPPER_BOUND"] == 313_588_232
    assert sealed["NEXT_ACTIVE_BOUND"] == census.SLICE1_FLOOR == manifest.floor
    assert sealed["NEXT_COMPETING_BOUND"] == manifest.rows[1].r30_bound
    assert sum(sealed["SLICE1_CAP_EVIDENCE"].values()) == len(manifest.rows)
    r28 = authorities["R28"]
    assert re.fullmatch(r"[0-9a-f]{40}", r28["COMMIT"]) and r28["COMMIT"].startswith("155f6f1c")
    loaded = sealed["R28_LOADED_MODULES"]
    assert loaded[r28["MODULE_PATH"]] == r28["MODULE_SHA256"]
    assert loaded[r28["BOUND_MODULE_PATH"]] == r28["BOUND_MODULE_SHA256"]
    evaluator = (ROOT / census.EVALUATOR_RELATIVE).read_bytes()
    assert hashlib.sha256(evaluator).hexdigest() == authorities["EVALUATOR"]["SHA256"]
    acceptance = cast(dict[str, Any], manifest.data["ACCEPTANCE"])
    assert authorities["EVALUATOR"]["SHA256"] == acceptance["EVALUATOR_SHA256"]
    assert census.git_blob_id(evaluator) == authorities["EVALUATOR"]["GIT_BLOB"]
    assert census.verify_evaluator(ROOT) == authorities["EVALUATOR"]
    start = (ROOT / census.START_RELATIVE).read_bytes()
    assert hashlib.sha256(start).hexdigest() == authorities["CANONICAL_START"]["FILE_SHA256"]
    assert authorities["CANONICAL_START"]["NORMALIZED_SHA256"] == (
        "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
    )


def test_ported_support_model_reproduces_the_pinned_r28_proto(manifest: census.Manifest) -> None:
    data = cast(dict[str, Any], manifest.data)
    pins = data["AUTHORITIES"]["MODEL_IDENTITY"]["MODEL_PROTO_TEXT_SHA256"]
    for pid, ceiling, digest in census.MODEL_PROBES:
        assert census.model_proto_sha256(pid, ceiling) == digest == pins[f"{pid}@{ceiling}"]
    # The R30 result's own MODEL_IDENTITY probe digest.
    assert pins["66665555554440000000@30"] == (
        "a3b4693b3711c28dfaedab0deac3e6cce30067c2baae2d46f08a96103d3c2eb0"
    )


def test_incumbent_profile_is_first_and_every_row_lies_in_slice1(
    manifest: census.Manifest, incumbent: tuple[census.Profile, census.Structure]
) -> None:
    profile, structure = incumbent
    rows = manifest.rows
    assert rows[0].profile_id == census.profile_id(profile) == INCUMBENT
    assert rows[0].band == ((270, 313_588_232),)
    assert census.realization(profile, structure).triangles == rows[0].cap == 270
    assert rows[0].r30_bound > rows[1].r30_bound
    assert len(rows) == cast(dict[str, Any], manifest.data["SLICE1"])["PROFILE_COUNT"] == 992
    assert [r.r30_bound for r in rows] == sorted((r.r30_bound for r in rows), reverse=True)
    assert all(b > census.SLICE1_FLOOR for r in rows for _, b in r.band)


def test_incumbent_first_is_enforced(tmp_path: Path) -> None:
    reordered = [SYNTHETIC_ROWS[1], SYNTHETIC_ROWS[0], SYNTHETIC_ROWS[2]]
    with pytest.raises(census.ManifestError, match="incumbent-first"):
        synthetic_manifest(tmp_path, reordered)


# Structures, mapping, proxy --------------------------------------------------------------------


def test_triple_and_pair_lines_map_to_an_exactly_equal_portfolio(
    incumbent: tuple[census.Profile, census.Structure], official: census.Evaluator
) -> None:
    profile, structure = incumbent
    tickets = census.portfolio(structure)
    for n, line in enumerate((*structure.triples, *structure.pairs)):
        assert {v for v, t in enumerate(tickets) if n + 1 in t} == set(line)
    assert all(len(t) == 6 for t in tickets)
    assert sorted(n for t in tickets for n in t) == sorted(
        n for n in range(1, 50) for _ in range(3 if n <= 22 else 2)
    )
    assert census.structure_from_tickets(tickets) == (profile, structure)
    start, _ = census.start_portfolio(ROOT)
    assert official(tickets) == official(start) == census.START_COUNT


def test_off_fiber_and_double_overlap_structures_are_rejected(
    incumbent: tuple[census.Profile, census.Structure],
) -> None:
    profile, structure = incumbent
    start, _ = census.start_portfolio(ROOT)
    assert start[0] == (1, 2, 3, 4, 5, 21)
    broken = [list(t) for t in start]
    broken[0] = [1, 2, 3, 4, 5, 22]  # 21 keeps one holder, 22 gains a third
    with pytest.raises(census.CensusError, match="off the minimum-S2 fiber"):
        census.structure_from_tickets(broken)
    # Swap the ends of two pair lines so that every degree is kept but one ticket pair
    # is covered twice.
    covered = census.edges(structure)
    swapped = next(
        (p, q, (min(p[0], q[1]), max(p[0], q[1])), (min(q[0], p[1]), max(q[0], p[1])))
        for p, q in combinations(structure.pairs, 2)
        if len({*p, *q}) == 4 and (min(p[0], q[1]), max(p[0], q[1])) in covered
    )
    p, q, new_a, new_b = swapped
    pairs = tuple(sorted({*structure.pairs} - {p, q} | {new_a, new_b}))
    with pytest.raises(census.CensusError, match="more than one number"):
        census.validate_structure(profile, census.Structure(structure.triples, pairs))


def test_k4_proxy_weights_are_exact_four_ticket_counts(
    incumbent: tuple[census.Profile, census.Structure], official: census.Evaluator
) -> None:
    weights = census.verify_proxy_weights(official)
    assert (
        weights
        == census.PROXY_WEIGHTS
        == {
            "K4_WITH_CONTAINED_TRIPLE": 448,
            "K4_WITHOUT_CONTAINED_TRIPLE": 679,
        }
    )
    real = census.realization(*incumbent)
    assert real.k4_with_contained_triple + real.k4_without_contained_triple == 550
    assert real.open_wedges == 6
    assert real.proxy_s4 == 448 * real.k4_with_contained_triple + 679 * (
        real.k4_without_contained_triple
    )


# Acceptance --------------------------------------------------------------------------------------


def test_exact_count_threshold_is_strictly_above_the_start(
    tmp_path: Path, manifest: census.Manifest
) -> None:
    assert census.STRICT_GAIN_THRESHOLD == 313_263_889 == census.START_COUNT + 1
    assert manifest.threshold == 313_263_889
    assert not census.is_gain(313_263_888)
    assert census.is_gain(313_263_889)

    def weaken(data: dict[str, Any]) -> None:
        data["ACCEPTANCE"]["STRICT_GAIN_THRESHOLD"] = 313_263_888

    with pytest.raises(census.ManifestError, match="gain threshold"):
        synthetic_manifest(tmp_path, edit=weaken)


def test_proxy_only_ranks_and_cannot_accept(
    tmp_path: Path,
    incumbent: tuple[census.Profile, census.Structure],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The best-proxy witness misses; the worst-proxy witness is the only gain."""

    _, structure = incumbent
    pool = variants(structure, 4)
    digests = [s.digest() for s in pool]
    real = census.realization

    def run(proxies: Sequence[int], directory: Path) -> tuple[list[Any], FakeEvaluator]:
        def fake_realization(p: census.Profile, s: census.Structure) -> census.Realization:
            return replace(real(p, s), proxy_s4=proxies[digests.index(s.digest())])

        monkeypatch.setattr(census, "realization", fake_realization)
        winner = census.compact_tickets_sha256(census.portfolio(pool[2]))

        def counts(tickets: census.Tickets) -> int:
            return 313_263_889 if census.compact_tickets_sha256(tickets) == winner else 313_263_888

        evaluator = FakeEvaluator(counts)
        manifest = synthetic_manifest(tmp_path, SYNTHETIC_ROWS[:1])
        summary = census.Census(manifest, directory, FakeSolver({INCUMBENT: pool}), evaluator).run()
        return cast(list[Any], summary["GAINS"]), evaluator

    gains, evaluator = run([5, 10, 10**9, -(10**9)], tmp_path / "a")
    # Evaluation order follows the proxy: index 3, 0, 1, 2.
    order = [census.portfolio(pool[i]) for i in (3, 0, 1, 2)]
    assert evaluator.calls == order
    assert [g["STRUCTURE_SHA256"] for g in gains] == [digests[2]]
    assert gains[0]["PROXY_RANK"] == 3 and gains[0]["EXACT_COUNT"] == 313_263_889
    flipped, _ = run([-(10**9), 10**9, -5, 7], tmp_path / "b")
    assert [g["STRUCTURE_SHA256"] for g in flipped] == [digests[2]]
    ledger = [json.loads(line) for line in logs(tmp_path / "a")[1].splitlines()[1:]]
    assert all(r["BODY"]["GAIN"] is (r["BODY"]["EXACT_COUNT"] >= 313_263_889) for r in ledger)
    assert sum(r["BODY"]["GAIN"] for r in ledger) == 1


# Census flow, cap, retry, workers ----------------------------------------------------------------


def test_chase_extracts_at_most_16_witnesses_and_records_each_outcome(
    tmp_path: Path, incumbent: tuple[census.Profile, census.Structure]
) -> None:
    _, structure = incumbent
    solver = FakeSolver({INCUMBENT: variants(structure, 20)}, unknown=frozenset({OTHER_B}))
    run = census.Census(
        synthetic_manifest(tmp_path), tmp_path / "d", solver, FakeEvaluator(below_start)
    )
    summary = run.run()
    done = {k[1]: v for k, v in run.proof.records.items() if k[0] == "PROFILE_DONE"}
    assert done[INCUMBENT]["STATUS"] == "REALIZED"
    assert done[INCUMBENT]["MAX_REALIZABLE_T"] == 270
    assert done[INCUMBENT]["WITNESS_COUNT"] == census.WITNESS_CAP == 16
    assert done[INCUMBENT]["WITNESS_END"] == "WITNESS_CAP_REACHED"
    assert done[OTHER_A]["STATUS"] == "NO_REALIZATION_IN_SLICE"
    assert done[OTHER_A]["REFUTED_T"] == [269]
    assert done[OTHER_B]["STATUS"] == "UNRESOLVED_AFTER_RETRY"
    assert summary["COMPLETE"] is True and summary["GAINS"] == []
    assert summary["WITNESSES_EVALUATED"] == 16
    assert (
        [c.seconds for c in solver.calls if census.profile_id(c.profile) == OTHER_B]
        == [
            census.SOLVE_SECONDS,
            census.RETRY_SECONDS,
        ]
        == [120.0, 600.0]
    )
    assert (("SOLVE", OTHER_B, 269, "CHASE", 0, 1)) in run.proof.records
    assert max(len(c.excluded) for c in solver.calls) == 15
    assert all(c.ceiling == census.wedge_count(c.profile) - 3 * c.triangles for c in solver.calls)

    small = FakeSolver({INCUMBENT: variants(structure, 5)})
    rows = SYNTHETIC_ROWS[:1]
    exhausted = census.Census(
        synthetic_manifest(tmp_path, rows), tmp_path / "e", small, FakeEvaluator(below_start)
    )
    exhausted.run()
    done = exhausted.proof.records[("PROFILE_DONE", INCUMBENT)]
    assert done["WITNESS_END"] == "STRUCTURE_SPACE_EXHAUSTED"
    assert done["WITNESS_COUNT"] == 5
    assert len(small.calls) == 6 and small.calls[-1].excluded == tuple(variants(structure, 5))


def test_witness_above_the_certified_cap_or_repeated_fails_closed(
    tmp_path: Path, incumbent: tuple[census.Profile, census.Structure]
) -> None:
    _, structure = incumbent
    capped = [[INCUMBENT, 313_587_000, 269, [[269, 313_587_000]]]]
    run = census.Census(
        synthetic_manifest(tmp_path, capped),
        tmp_path / "a",
        FakeSolver({INCUMBENT: [structure]}),
        FakeEvaluator(below_start),
    )
    with pytest.raises(census.CensusError, match="270 triangles"):
        run.run()

    def repeating(request: census.SolveRequest) -> census.SolveOutcome:
        return census.SolveOutcome("FEASIBLE", structure, 0.0)

    run = census.Census(
        synthetic_manifest(tmp_path, SYNTHETIC_ROWS[:1]), tmp_path / "b", repeating, below_start
    )
    with pytest.raises(census.CensusError, match="repeated an excluded structure"):
        run.run()


def test_single_worker_fixed_seed_and_thread_env_are_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    solver = census.configured_solver(census.SOLVE_SECONDS)
    assert solver.parameters.num_search_workers == 1
    assert solver.parameters.num_workers == 0  # unset: setting both is MODEL_INVALID
    assert census.observed_search_workers() == 1
    assert solver.parameters.random_seed == census.RANDOM_SEED == 649
    assert solver.parameters.max_time_in_seconds == 120.0

    def two_workers(data: dict[str, Any]) -> None:
        data["SOLVER"]["NUM_SEARCH_WORKERS"] = 2

    with pytest.raises(census.ManifestError, match="search workers"):
        synthetic_manifest(tmp_path, edit=two_workers)
    manifest = synthetic_manifest(tmp_path)
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(census.PreflightError, match="OMP_NUM_THREADS"):
        census.Census(manifest, tmp_path / "x", FakeSolver({}), below_start)
    monkeypatch.delenv("VECLIB_MAXIMUM_THREADS")
    with pytest.raises(census.PreflightError, match="VECLIB_MAXIMUM_THREADS"):
        census.main(["preflight"])
    assert not (tmp_path / "x").exists()


def test_no_good_extraction_on_a_tiny_cp_sat_model_is_complete_and_deterministic() -> None:
    def tiny(profile: census.Profile, ceiling: int) -> tuple[Any, Any, Any]:
        cp_model: Any = import_module("ortools.sat.python.cp_model")
        model: Any = cp_model.CpModel()
        triples = {t: model.NewBoolVar(f"t{t}") for t in combinations(range(4), 3)}
        pairs = {p: model.NewBoolVar(f"b{p}") for p in combinations(range(4), 2)}
        model.Add(sum(triples.values()) == 1)
        model.Add(sum(pairs.values()) == 1)
        return model, triples, pairs

    def extract() -> list[census.Structure]:
        found: list[census.Structure] = []
        probe = census.decode_profile("66665555554440000000")
        while True:
            request = census.SolveRequest(probe, 0, tuple(found), 5.0)
            outcome = census.cp_sat_solve(request, tiny)
            if outcome.status == "INFEASIBLE":
                return found
            assert outcome.status in census.REALIZED and outcome.structure is not None
            assert outcome.structure not in found
            found.append(outcome.structure)

    first = extract()
    assert len(first) == len(set(first)) == 4 * 6
    assert extract() == first


def test_k20_model_with_no_goods_is_valid_without_solving(
    incumbent: tuple[census.Profile, census.Structure],
) -> None:
    profile, structure = incumbent
    model, triples, pairs = census.k20_model(profile, census.wedge_count(profile) - 3 * 270)
    for excluded in variants(structure, 3):
        census.add_nogood(model, triples, pairs, excluded)
    assert model.Validate() == ""


# Durability: resume, corruption, duplicates, lock ----------------------------------------------


def test_resume_serves_every_durable_key_without_resolving(
    tmp_path: Path, incumbent: tuple[census.Profile, census.Structure]
) -> None:
    _, structure = incumbent
    pool = {INCUMBENT: variants(structure, 6)}
    manifest = synthetic_manifest(tmp_path)

    full = FakeSolver(pool)
    census.Census(manifest, tmp_path / "full", full, FakeEvaluator(below_start)).run()
    expected = logs(tmp_path / "full")

    crashed = FakeSolver(pool, fail_at=4)
    with pytest.raises(Interrupted):
        census.Census(manifest, tmp_path / "resume", crashed, FakeEvaluator(below_start)).run()
    logged = {
        json.loads(line)["BODY"].get("REQUEST_SHA256")
        for line in logs(tmp_path / "resume")[0].splitlines()[1:]
    }
    assert len(logged) == 4
    rest = FakeSolver(pool)
    census.Census(manifest, tmp_path / "resume", rest, FakeEvaluator(below_start)).run()
    assert not {c.digest() for c in rest.calls} & logged
    assert len(crashed.calls) + len(rest.calls) == len(full.calls)
    assert logs(tmp_path / "resume") == expected

    bad_eval = FakeEvaluator(below_start, fail_at=3)
    with pytest.raises(Interrupted):
        census.Census(manifest, tmp_path / "eval", FakeSolver(pool), bad_eval).run()
    again = FakeEvaluator(below_start)
    census.Census(manifest, tmp_path / "eval", FakeSolver(pool), again).run()
    assert len(again.calls) == 6 - 3
    assert logs(tmp_path / "eval") == expected

    idle_solver, idle_eval = FakeSolver(pool), FakeEvaluator(below_start)
    summary = census.Census(manifest, tmp_path / "full", idle_solver, idle_eval).run()
    assert idle_solver.calls == [] and idle_eval.calls == []
    assert summary["COMPLETE"] is True and summary["SOLVER_CALLS_THIS_PROCESS"] == 0
    assert logs(tmp_path / "full") == expected


def rechain(lines: Sequence[dict[str, Any]]) -> bytes:
    previous = census.GENESIS
    out: list[bytes] = []
    for record in lines:
        content = {"KEY": record["KEY"], "PREV_SHA256": previous, "BODY": record["BODY"]}
        previous = census.sha256_bytes(census.canonical_json(content).encode())
        out.append(census.canonical_json({**content, "LINE_SHA256": previous}).encode())
    return b"\n".join(out) + b"\n"


def test_corrupt_reordered_truncated_and_duplicate_logs_fail_closed(
    tmp_path: Path, incumbent: tuple[census.Profile, census.Structure]
) -> None:
    _, structure = incumbent
    pool = {INCUMBENT: variants(structure, 3)}
    manifest = synthetic_manifest(tmp_path)
    good = tmp_path / "good"
    census.Census(manifest, good, FakeSolver(pool), FakeEvaluator(below_start)).run()
    proof, _ = logs(good)
    lines = proof.splitlines()
    records = [cast(dict[str, Any], json.loads(line)) for line in lines]

    def attempt(name: str, data: bytes, match: str) -> None:
        directory = tmp_path / name
        directory.mkdir()
        (directory / census.PROOF_LOG).write_bytes(data)
        (directory / census.WITNESS_LEDGER).write_bytes(logs(good)[1])
        with pytest.raises(census.DurableLogError, match=match):
            census.Census(manifest, directory, FakeSolver(pool), FakeEvaluator(below_start)).run()

    attempt("flip", proof.replace(b'"STATUS":"FEASIBLE"', b'"STATUS":"FEASIBLX"', 1), "hash chain")
    attempt("torn", proof[:-15], "truncated")
    attempt("reorder", b"\n".join([lines[0], lines[2], lines[1], *lines[3:]]) + b"\n", "hash chain")
    attempt("duplicate", rechain([*records, records[1]]), "duplicate durable key")
    attempt("header", rechain([records[1], *records[1:]]), "duplicate|header")
    # A re-chained log whose solve record answers a different request: served, then refused.
    forged = [dict(r) for r in records[:3]]
    forged[1] = {**forged[1], "BODY": {**forged[1]["BODY"], "REQUEST_SHA256": "f" * 64}}
    attempt("forged", rechain(forged), "does not match its request")
    other = synthetic_manifest(tmp_path, SYNTHETIC_ROWS[:2])
    with pytest.raises(census.DurableLogError, match="header differs"):
        census.Census(other, good, FakeSolver(pool), FakeEvaluator(below_start))
    log = census.DurableLog(tmp_path / "unit.jsonl", {"H": 1})
    log.append(("A", 1), {"x": 1})
    with pytest.raises(census.DurableLogError, match="duplicate durable key"):
        log.append(("A", 1), {"x": 2})


def test_durable_lock_admits_one_writer(tmp_path: Path) -> None:
    with (
        census.durable_lock(tmp_path),
        pytest.raises(census.CensusError, match="durable lock"),
        census.durable_lock(tmp_path),
    ):
        pass
    with census.durable_lock(tmp_path):
        pass


# Slice 2 ---------------------------------------------------------------------------------------


def test_slice2_cannot_run(tmp_path: Path, manifest: census.Manifest) -> None:
    assert manifest.data["SLICE2"] == {
        "AUTHORIZATION": "NONE",
        "ENABLED": False,
        "FLOOR": census.SLICE2_FLOOR,
    }
    solver = FakeSolver({})
    run = census.Census(synthetic_manifest(tmp_path), tmp_path / "a", solver, below_start)
    with pytest.raises(census.Slice2NotAuthorized):
        run.run(slice_number=2)
    assert solver.calls == []
    with pytest.raises(census.Slice2NotAuthorized):
        census.main(["run", "--slice", "2"])

    def enable(data: dict[str, Any]) -> None:
        data["SLICE2"]["ENABLED"] = True

    with pytest.raises(census.ManifestError, match="Slice 2"):
        synthetic_manifest(tmp_path, edit=enable)
    slice2_row = [
        *SYNTHETIC_ROWS[:1],
        ["66666662222222222211", 313_577_032, 266, [[266, 313_577_032]]],
    ]
    with pytest.raises(census.ManifestError, match="leaves Slice 1"):
        synthetic_manifest(tmp_path, slice2_row)
    smuggled = replace(
        run.manifest,
        rows=(*run.manifest.rows, replace(run.manifest.rows[-1], band=((268, 313_577_032),))),
    )
    with pytest.raises(census.Slice2NotAuthorized, match="outside Slice 1"):
        census.Census(smuggled, tmp_path / "b", solver, below_start).run()
    assert solver.calls == []
