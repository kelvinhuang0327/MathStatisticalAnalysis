"""Focused tests for the CELL_A complete-family score bound.

Nothing is solved and nothing is scored. CP-SAT's Solve, the census solve and evaluator entry
points, the engine's exact evaluator and both official evaluator functions are replaced by guards
that record and fail any call. Every pin is resolved through git, and each reused literal is
compared with its donor's bytes. Random CELL_A solutions are built from relabelled donor designs,
random deleted points, random U splits and random number labels. Each one is covered, and the
ticket and number maps are re-applied here. The helper's own automorphism code, loaded from its
pinned blob, must reproduce the automorphism groups that give the five classes.
"""

from __future__ import annotations

import ast
import itertools
import json
import random
import subprocess
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from importlib import import_module
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_cell_a_complete_family_score_bound_r1 as bound
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_two_open_cells_targeted_solver as engine
from lottolab.research import b649_official_any_prize_exact as exact

ROOT = Path(__file__).resolve().parents[2]
READ = bound.git_reader(ROOT)
CALLS: list[str] = []
PACKET_COMMITS = {
    "24ff183c68ac02ea497044921207913a16ec09bd",
    "03b5691fac02c3a125c91cf4120b6219c3143b5e",
    "82e88ada111bf6d0999ac9c0c167a160a6ae5df8",
    "7b573db44f56c49e2a0bbb7c002f092e5839d62b",
}

# A real fiber portfolio off the CELL_A profile: the 11+9 family winner, read from its blob.
OTHER_PROFILE_RESULT = (
    "7b573db44f56c49e2a0bbb7c002f092e5839d62b",
    "docs/research/matrix-native-results/"
    "b649-k20-11-9-single-bridge-sts13-family-exact-r1-result.json",
    "5552885602999274450b4e18fa2cb751c2b4531c",
)

Triple = census.Triple
Pair = census.Pair


@pytest.fixture(scope="module", autouse=True)
def no_solve_and_no_scoring() -> Iterator[None]:
    """Any CP-SAT solve or exact evaluation is recorded and fails the test that makes it."""

    def guard(name: str) -> Callable[..., NoReturn]:
        def refuse(*_: object, **__: object) -> NoReturn:
            CALLS.append(name)
            raise AssertionError(f"{name} was called")

        return refuse

    cp_model: Any = import_module("ortools.sat.python.cp_model")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cp_model.CpSolver, "Solve", guard("CpSolver.Solve"))
        patch.setattr(cp_model.CpSolver, "solve", guard("CpSolver.solve"))
        patch.setattr(census, "cp_sat_solve", guard("census.cp_sat_solve"))
        patch.setattr(census, "official_evaluator", guard("census.official_evaluator"))
        patch.setattr(engine, "exact_evaluator", guard("engine.exact_evaluator"))
        patch.setattr(exact, "evaluate_portfolio", guard("exact.evaluate_portfolio"))
        patch.setattr(exact, "all_main_draw_masks", guard("exact.all_main_draw_masks"))
        yield


@pytest.fixture(scope="module")
def record() -> dict[str, object]:
    return bound.certificate()


@pytest.fixture(scope="module")
def classes() -> tuple[bound.PointedClass, ...]:
    return bound.pointed_classes()


def _structure(
    triples: Sequence[Sequence[int]], pairs: Sequence[Sequence[int]]
) -> census.Structure:
    return census.Structure(
        tuple(sorted(cast(Triple, tuple(sorted(t))) for t in triples)),
        tuple(sorted(cast(Pair, tuple(sorted(p))) for p in pairs)),
    )


def _owner(classes: Sequence[bound.PointedClass], name: str, point: int) -> bound.PointedClass:
    return next(c for c in classes if c.design == name and point in c.points)


def _check_maps(cover: bound.Cover, structure: census.Structure) -> None:
    """Re-apply the cover's ticket and number maps to the solution, independently of ``cover``."""

    source = census.portfolio(structure)
    target = bound.pointed_portfolio(cover.design, cover.deleted_point)
    assert sorted(cover.tickets) == list(range(census.TICKET_COUNT))
    assert sorted(cover.numbers) == list(range(1, census.POOL_SIZE + 1))
    for v, ticket in enumerate(source):
        assert sorted(cover.numbers[n - 1] for n in ticket) == sorted(target[cover.tickets[v]])


def random_solution(rng: random.Random, name: str) -> tuple[census.Structure, int]:
    """A CELL_A structure from a relabelled donor design, a random deleted point and a random U
    split. Returns it with the donor point that became oo."""

    tau = list(range(bound.POINTS))
    rng.shuffle(tau)
    image = [tuple(sorted(tau[v] for v in b)) for b in bound.STS13_DESIGNS[name]]
    q = rng.randrange(bound.POINTS)
    labels = list(bound.H)
    rng.shuffle(labels)
    ticket = dict(zip((v for v in range(bound.POINTS) if v != q), labels, strict=True))
    triples = [[ticket[v] for v in b] for b in image if q not in b]
    pairs = [[ticket[v] for v in b if v != q] for b in image if q in b]
    positive = list(bound.POSITIVE_U)
    rng.shuffle(positive)
    split = (cast(Triple, tuple(sorted(positive[:3]))), cast(Triple, tuple(sorted(positive[3:]))))
    u_triples, u_pairs = bound.u_lines(split)
    return _structure([*triples, *u_triples], [*pairs, *u_pairs]), tau.index(q)


# Sources and reused evidence ---------------------------------------------------------------


def test_every_pin_resolves_and_every_reused_literal_matches_its_donor() -> None:
    assert bound.verify_sources(READ) == {pin.role: pin.blob for pin in bound.SOURCES}
    assert {pin.commit for pin in bound.SOURCES} == PACKET_COMMITS
    assert bound.BASE_COMMIT in PACKET_COMMITS
    evaluator = next(pin for pin in bound.SOURCES if pin.role == "EVALUATOR")
    assert census.git_blob_id(READ(bound.BASE_COMMIT, evaluator.path)) == evaluator.blob
    assert evaluator.blob == census.EVALUATOR_BLOB
    resolved = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--disambiguate=7b573db"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert resolved == ["7b573db44f56c49e2a0bbb7c002f092e5839d62b"]
    donor = next(pin for pin in bound.SOURCES if pin.role == "DONOR_RESULT")
    result = json.loads(READ(donor.commit, donor.path))
    assert not [key for key in result if "EVALUATOR" in key]  # the result carries no scorer hash
    assert bound.rows_sha256(bound.DONOR_ROWS) == bound.DONOR_ROWS_SHA256


def _with(index: int, *, sha: str | None = None, count: int | None = None) -> list[bound.ScoreRow]:
    changed = list(bound.DONOR_ROWS)
    name, point, old_sha, old_count = changed[index]
    changed[index] = (name, point, sha or old_sha, old_count if count is None else count)
    return changed


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        (_with(18, count=313_263_889), "pinned donor rows"),
        (_with(0, count=313_263_866), "pinned donor rows"),
        (list(bound.DONOR_ROWS[:25]), "exactly once"),
        (_with(3, sha=bound.DONOR_ROWS[4][2]), "PORTFOLIO_SHA256 differs"),
        # C5 is one row, so raising it keeps every class constant.
        (_with(19, count=313_263_999), "pinned donor rows"),
        (list(reversed(bound.DONOR_ROWS)), "pinned donor rows"),
    ],
    ids=["winner-raised", "cyclic-lowered", "row-dropped", "sha-swapped", "class-raised", "order"],
)
def test_changed_score_rows_are_refused(rows: Sequence[bound.ScoreRow], reason: str) -> None:
    with pytest.raises(bound.BoundError, match=reason):
        bound.pointed_classes(rows)
    with pytest.raises(bound.BoundError, match=reason):
        bound.certificate(rows=rows)


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        (_with(0, count=313_263_866), "not constant"),
        (_with(19, count=313_263_999), "class counts differ"),
    ],
    ids=["cyclic-lowered", "class-raised"],
)
def test_class_constancy_and_the_class_pin_are_further_barriers(
    rows: Sequence[bound.ScoreRow], reason: str
) -> None:
    """With the row pin moved onto the changed rows, the class checks still refuse them."""

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(bound, "DONOR_ROWS_SHA256", bound.rows_sha256(rows))
        with pytest.raises(bound.BoundError, match=reason):
            bound.pointed_classes(rows)


def test_a_changed_source_identity_is_refused() -> None:
    def tampered(commit: str, path: str) -> bytes:
        data = READ(commit, path)
        return data.replace(b"313263888", b"313263889") if path.endswith(".json") else data

    with pytest.raises(bound.BoundError, match="DONOR_RESULT"):
        bound.verify_sources(tampered)
    for index, field in ((5, "blob"), (3, "commit")):
        pins = list(bound.SOURCES)
        pins[index] = replace(pins[index], **{field: "0" * 40})
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(bound, "SOURCES", tuple(pins))
            with pytest.raises((bound.BoundError, subprocess.CalledProcessError)):
                bound.verify_sources(READ)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("CELL_A_EXACT_UPPER_BOUND", 313_263_889),
        ("STRICT_GAIN_THRESHOLD", 313_263_888),
        ("CLASS_SIZES", [13, 6, 3, 4]),
        ("DONOR_ROWS_SHA256", "0" * 64),
        ("SOURCES", []),
        ("REUSED_SCORE_PROVENANCE", {}),
        ("EXTERNAL_CLASSIFICATION", {"STATEMENT": "STS(13) has one class"}),
        ("CERTIFICATE_SHA256", "0" * 64),
    ],
)
def test_a_tampered_record_is_refused(record: dict[str, object], field: str, value: object) -> None:
    bound.verify_certificate(record)
    with pytest.raises(bound.BoundError, match=field):
        bound.verify_certificate({**record, field: value})


# Step 3: the U side ------------------------------------------------------------------------


def test_the_u_side_has_ten_splits_and_one_incidence_class() -> None:
    splits = bound.u_partitions()
    assert len(splits) == len(set(splits)) == comb(6, 3) // 2 == 10
    # Exhaustive: of all unordered pairs of distinct U triples, exactly the ten splits give the
    # six d = 1 tickets one triple each and the two d = 0 tickets none.
    forced = [
        tuple(sorted(pair))
        for pair in combinations(combinations(bound.U, 3), 2)
        if Counter(v for t in pair for v in t) == Counter(bound.POSITIVE_U)
    ]
    assert sorted(forced) == sorted(tuple(sorted(s)) for s in splits)
    donor = bound.u_lines(bound.DONOR_U_TRIPLES)
    k8_minus_e = {p for p in combinations(bound.U, 2) if p != bound.ZERO_U}
    for split in splits:
        triples, pairs = bound.u_lines(split)
        inside = {p for t in triples for p in combinations(t, 2)}
        assert len(pairs) == 21 and set(pairs) == k8_minus_e - inside
        mapping = bound.u_mapping(split)
        assert sorted(mapping) == sorted(mapping.values()) == list(bound.U)
        assert {mapping[v] for v in bound.ZERO_U} == set(bound.ZERO_U)
        image = sorted(tuple(sorted(mapping[v] for v in p)) for p in pairs)
        assert image == list(donor[1])


# Step 2: the H side ------------------------------------------------------------------------


def test_extension_and_deletion_are_inverse_on_every_pointed_construction() -> None:
    for name in bound.DESIGN_NAMES:
        for p in range(bound.POINTS):
            structure = bound.pointed_structure(name, p)
            design = bound.extend_h(structure)
            remaining, avoiding, through = bound.deletion(design, bound.OO)
            assert remaining == bound.H
            assert avoiding == tuple(t for t in structure.triples if set(t) <= bound.H_SET)
            assert through == tuple(q for q in structure.pairs if set(q) <= bound.H_SET)
            assert bound.sts_isomorphisms(design, bound.STS13_DESIGNS[name], first=True)


def test_extension_premises_and_deletion_inputs_fail_closed() -> None:
    structure = bound.pointed_structure("NONCYCLIC", 5)
    (a, _), *rest = [q for q in structure.pairs if set(q) <= bound.H_SET]
    broken = _structure(structure.triples, [(a, rest[0][0]), *rest[1:]])
    with pytest.raises(bound.BoundError, match="perfect matching"):
        bound.extend_h(broken)
    cyclic = bound.STS13_DESIGNS["CYCLIC"]
    with pytest.raises(bound.BoundError):
        bound.deletion(cyclic, bound.POINTS)
    with pytest.raises(bound.BoundError):
        bound.deletion(cyclic[1:], 0)


# Covering ----------------------------------------------------------------------------------


def test_every_pointed_construction_covers_to_its_own_class(
    classes: tuple[bound.PointedClass, ...],
) -> None:
    rows = {(name, point): count for name, point, _, count in bound.DONOR_ROWS}
    for name in bound.DESIGN_NAMES:
        for p in range(bound.POINTS):
            structure = bound.pointed_structure(name, p)
            cover = bound.cover(structure, classes=classes)
            assert cover.class_id == _owner(classes, name, p).class_id
            assert cover.count == rows[(name, p)]
            _check_maps(cover, structure)


@pytest.mark.parametrize("name", bound.DESIGN_NAMES)
def test_random_cell_a_solutions_are_covered_with_verified_maps(
    name: str, classes: tuple[bound.PointedClass, ...]
) -> None:
    rng = random.Random(f"b649-cell-a-{name}")
    for _ in range(20):
        structure, point = random_solution(rng, name)
        cover = bound.cover(structure, classes=classes)
        owner = _owner(classes, name, point)
        assert (cover.class_id, cover.design) == (owner.class_id, name)
        assert cover.deleted_point in owner.points and cover.count == owner.count
        _check_maps(cover, structure)
        # The same solution with random number labels and ticket order, read back from tickets.
        relabel = list(range(1, census.POOL_SIZE + 1))
        rng.shuffle(relabel)
        tickets = [tuple(sorted(relabel[n - 1] for n in t)) for t in census.portfolio(structure)]
        rng.shuffle(tickets)
        profile, read_back = census.structure_from_tickets(tickets)
        assert profile == bound.PROFILE
        again = bound.cover(read_back, classes=classes)
        assert again.class_id == owner.class_id
        _check_maps(again, read_back)


def test_the_external_classification_is_load_bearing(
    classes: tuple[bound.PointedClass, ...],
) -> None:
    """With only one donor class available, a solution of the other class is not covered."""

    structure = bound.pointed_structure("NONCYCLIC", 6)
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(bound.STS13_DESIGNS, "NONCYCLIC", bound.STS13_DESIGNS["CYCLIC"])
        with pytest.raises(bound.BoundError, match="external classification"):
            bound.cover(structure, classes=classes)


# Rejections --------------------------------------------------------------------------------


def _donor() -> census.Structure:
    return bound.pointed_structure("NONCYCLIC", 5)


def _swap_lines(
    structure: census.Structure, old: Sequence[Sequence[int]], new: Sequence[Sequence[int]]
) -> census.Structure:
    lines = [list(line) for line in (*structure.triples, *structure.pairs)]
    for line in old:
        lines.remove(sorted(line))
    lines += [sorted(line) for line in new]
    return _structure([q for q in lines if len(q) == 3], [q for q in lines if len(q) == 2])


def test_a_wrong_d_profile_is_rejected() -> None:
    commit, path, blob = OTHER_PROFILE_RESULT
    data = READ(commit, path)
    assert census.git_blob_id(data) == blob
    profile, structure = census.structure_from_tickets(json.loads(data)["BEST_PORTFOLIO"])
    assert census.profile_id(profile) == "64444444444332222222"
    with pytest.raises(bound.BoundError, match="not a CELL_A structure"):
        bound.cover(structure)
    with pytest.raises(bound.BoundError, match="covers only CELL_A"):
        bound.cover(_donor(), profile_id=census.profile_id(profile))
    with pytest.raises(bound.BoundError, match="covers only CELL_A"):
        bound.certificate(t=269)


def test_a_wrong_u_triple_incidence_is_rejected() -> None:
    donor = _donor()
    zero_in_triple = _swap_lines(donor, [(12, 13, 14)], [(12, 13, 18)])
    with pytest.raises(bound.BoundError, match="not a CELL_A structure"):
        bound.cover(zero_in_triple)
    resplit = _swap_lines(donor, [(12, 13, 14), (15, 16, 17)], [(12, 13, 15), (14, 16, 17)])
    with pytest.raises(bound.BoundError, match="not a CELL_A structure"):
        bound.cover(resplit)
    with pytest.raises(bound.BoundError, match="two disjoint triples"):
        bound.u_lines([(12, 13, 14), (14, 15, 16)])


def test_a_cross_component_line_is_rejected() -> None:
    donor = _donor()
    a, b = next(q for q in donor.pairs if set(q) <= bound.H_SET)
    crossed = _swap_lines(donor, [(a, b), (12, 15)], [(a, 12), (b, 15)])
    census.validate_structure(bound.PROFILE, crossed)  # degrees and single overlaps still hold
    with pytest.raises(bound.BoundError, match="crosses H and U"):
        bound.cover(crossed)
    with pytest.raises(bound.rigidity.CertificateError):
        bound.rigidity.structure_ledger(crossed.triples, crossed.pairs)


# Classes and the bound ---------------------------------------------------------------------


def _helper_automorphisms() -> Callable[[bound.Design], Sequence[bound.Permutation]]:
    """``sts13_automorphisms`` and its callees, compiled from the helper's pinned blob."""

    pin = next(pin for pin in bound.SOURCES if pin.role == "STS_AUTOMORPHISM_HELPER")
    wanted = {
        "_pair",
        "is_valid_sts13",
        "third_point_table",
        "_compose",
        "_verify_group",
        "_close_point_map",
        "sts13_automorphisms",
    }
    tree = ast.parse(READ(pin.commit, pin.path))
    nodes: list[ast.stmt] = [
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted
    ]
    assert {cast(ast.FunctionDef, n).name for n in nodes} == wanted
    future = ast.ImportFrom(module="__future__", names=[ast.alias("annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    namespace: dict[str, object] = {
        "itertools": itertools,
        "Counter": Counter,
        "comb": comb,
        "cast": cast,
        "Mapping": Mapping,
        "Sequence": Sequence,
        "Block": tuple,
        "POINT_COUNT": bound.POINTS,
    }
    exec(compile(module, f"<blob {pin.blob}>", "exec"), namespace)
    return cast(
        Callable[[bound.Design], Sequence[bound.Permutation]], namespace["sts13_automorphisms"]
    )


def test_the_helper_automorphisms_give_the_same_groups_and_orbits() -> None:
    helper = _helper_automorphisms()
    for name, order in (("CYCLIC", 39), ("NONCYCLIC", 6)):
        group = set(helper(bound.STS13_DESIGNS[name]))
        assert group == set(bound.automorphisms(name)) and len(group) == order
    assert bound.point_orbits("CYCLIC") == (tuple(range(13)),)
    assert bound.point_orbits("NONCYCLIC") == ((0, 1, 4, 8, 11, 12), (2, 7, 9), (3, 5, 10), (6,))
    assert not bound.sts_isomorphisms(
        bound.STS13_DESIGNS["CYCLIC"], bound.STS13_DESIGNS["NONCYCLIC"]
    )


def test_five_classes_cover_the_26_constructions_and_bound_cell_a(
    record: dict[str, object], classes: tuple[bound.PointedClass, ...]
) -> None:
    assert record["CLASS_SIZES"] == [13, 6, 3, 3, 1]
    assert sum(len(c.points) for c in classes) == record["POINTED_CONSTRUCTIONS"] == 26
    assert {c.class_id: c.count for c in classes} == {
        "C1": 313_263_867,
        "C2": 313_263_888,
        "C3": 313_263_881,
        "C4": 313_263_888,
        "C5": 313_263_881,
    }
    assert len({c.canonical_id for c in classes}) == 5
    assert record["CELL_A_EXACT_UPPER_BOUND"] == max(c.count for c in classes) == 313_263_888
    assert record["STRICT_GAIN_THRESHOLD"] == census.STRICT_GAIN_THRESHOLD == 313_263_889
    assert record["ATTAINING_CLASSES"] == ["C2", "C4"]
    assert _owner(classes, "NONCYCLIC", 5).class_id == "C4"
    assert record["PASCH_COUNTS"] == {"CYCLIC": 13, "NONCYCLIC": 8}
    assert record["AUTOMORPHISM_GROUP_ORDERS"] == {"CYCLIC": 39, "NONCYCLIC": 6}
    assert record["U_PARTITIONS"] == 10 and record["U_INCIDENCE_CLASSES"] == 1
    assert (
        record["RIGIDITY_CERTIFICATE_SHA256"] == bound.rigidity.certificate()["CERTIFICATE_SHA256"]
    )
    assert record["VERDICT"] == bound.VERDICT
    not_claimed = cast(dict[str, str], record["NOT_CLAIMED"])
    assert not_claimed["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    # Every construction lies in the original CELL_A domain: the four premises, T = 270.
    for name in bound.DESIGN_NAMES:
        for p in range(bound.POINTS):
            ledger = bound.check_cell_a(bound.pointed_structure(name, p))
            assert (ledger.triangles, ledger.open_wedges, ledger.cross_edges) == (270, 6, 0)


# No solve, no scoring ----------------------------------------------------------------------


def test_cp_sat_and_exact_scoring_calls_are_zero(
    record: dict[str, object], classes: tuple[bound.PointedClass, ...]
) -> None:
    before = len(CALLS)
    bound.verify_certificate(record)
    bound.verify_sources(READ)
    structure, _ = random_solution(random.Random(649), "NONCYCLIC")
    bound.cover(structure, classes=classes)
    bound.cover(bound.pointed_structure("CYCLIC", 3))
    assert len(CALLS) == before == 0
    assert (record["CP_SAT_CALLS"], record["NEW_EXACT_SCORING_CALLS"]) == (0, 0)


def test_the_solve_and_scoring_guards_are_live() -> None:
    before = len(CALLS)
    with pytest.raises(AssertionError):
        census.official_evaluator()
    with pytest.raises(AssertionError):
        exact.evaluate_portfolio(bound.pointed_portfolio("CYCLIC", 0))
    assert CALLS[before:] == ["census.official_evaluator", "exact.evaluate_portfolio"]
    del CALLS[before:]


def test_main_prints_the_certificate(
    record: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    bound.main()
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(json.dumps(record))
