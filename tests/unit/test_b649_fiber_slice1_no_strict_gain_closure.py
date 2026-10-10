"""Focused tests for the frozen K20 fiber Slice-1 no-strict-gain closure.

No solver runs and nothing is searched. The STS(13) checks are exact, and the official
evaluator counts only the five class representatives and the canonical start. Tests that need
commits outside this branch's history (R30 task head, T270 archive, T266 source, R28) skip
when those objects are absent from the local object store.
"""

from __future__ import annotations

import json
import random
import subprocess
from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest

from lottolab.research import b649_fiber_slice1_no_strict_gain_closure as closure
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_refutation_overlay as overlay

ROOT = Path(__file__).resolve().parents[2]
RECORDED_COUNTS = {
    "CYCLIC/orbit0": 313_263_867,
    "NONCYCLIC/orbit0": 313_263_888,
    "NONCYCLIC/orbit2": 313_263_881,
    "NONCYCLIC/orbit3": 313_263_888,
    "NONCYCLIC/orbit6": 313_263_881,
}


def has_commit(commit: str) -> bool:
    probe = ["git", "cat-file", "-e", f"{commit}^{{commit}}"]
    return subprocess.run(probe, cwd=ROOT, capture_output=True).returncode == 0


EXTERNAL_COMMITS = (
    overlay.R30_TASK_HEAD,
    closure.T270_SOURCE_COMMIT,
    closure.T266_SOURCE_COMMIT,
    census.R28_COMMIT,
)
needs_objects = pytest.mark.skipif(
    not all(has_commit(c) for c in EXTERNAL_COMMITS),
    reason="R30, T270 archive, T266 source or R28 commits are not in the local object store",
)


@cache
def t270() -> dict[str, object]:
    return closure.load_t270(ROOT)[0]


@cache
def classes() -> dict[str, closure.StsClass]:
    reps = closure.recorded_representatives(t270())
    return {name: closure.sts_class(name, blocks) for name, blocks in reps.items()}


@cache
def evaluator() -> census.Evaluator:
    return census.official_evaluator()


def relabelled(tickets: census.Tickets, seed: int) -> census.Tickets:
    """The same portfolio up to Sym(49) on numbers and a shuffled ticket order."""

    rng = random.Random(seed)
    numbers = list(range(1, census.POOL_SIZE + 1))
    rng.shuffle(numbers)
    out = [tuple(sorted(numbers[n - 1] for n in t)) for t in tickets]
    rng.shuffle(out)
    return tuple(out)


# T270 authority -------------------------------------------------------------------------


def test_in_tree_t270_closure_is_the_pinned_bytes() -> None:
    data, raw = closure.load_t270(ROOT)
    assert census.sha256_bytes(raw) == closure.T270_RESULT_SHA256
    assert data["EXACT_CELL_MAX"] == closure.EXACT_CELL_MAX == census.START_COUNT


def test_t270_pin_and_statement_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = (ROOT / closure.T270_RESULT_RELATIVE).read_bytes()
    target = tmp_path / closure.T270_RESULT_RELATIVE
    target.parent.mkdir(parents=True)
    target.write_bytes(raw + b" ")
    with pytest.raises(closure.ClosureError, match="differs from its pin"):
        closure.load_t270(tmp_path)
    edited = raw.replace(b'"EXACT_CELL_MAX": 313263888', b'"EXACT_CELL_MAX": 313263889')
    assert edited != raw
    target.write_bytes(edited)
    monkeypatch.setattr(closure, "T270_RESULT_SHA256", census.sha256_bytes(edited))
    with pytest.raises(closure.ClosureError, match="does not state the pinned closure"):
        closure.load_t270(tmp_path)


@needs_objects
def test_in_tree_t270_copy_equals_the_archive_commit() -> None:
    _, raw = closure.load_t270(ROOT)
    archive = closure.t270_archive(ROOT, raw)
    assert archive["IN_TREE_COPY_BYTE_IDENTICAL"] is True
    with pytest.raises(closure.ClosureError, match="differs from archive"):
        closure.t270_archive(ROOT, raw + b" ")


# Forced graph ---------------------------------------------------------------------------


def test_structural_arithmetic_admits_only_t270_with_c_zero() -> None:
    profile = census.decode_profile(closure.INCUMBENT_PROFILE)
    report = closure.structural_arithmetic(profile, closure.INCUMBENT_T)
    assert report["W"] == 816
    assert report["HL_EDGE_TERM_LOWER_BOUND"] == 4
    assert report["REALIZABLE_T"] == [270]
    assert report["TRIANGLES_OF_K12_PLUS_K8_MINUS_E"] == 270
    assert report["T_TRACE"] == [
        {"T": 270, "OPEN_WEDGES": 6, "ADMITTED_C": [0]},
        {"T": 271, "OPEN_WEDGES": 3, "ADMITTED_C": []},
        {"T": 272, "OPEN_WEDGES": 0, "ADMITTED_C": []},
    ]
    with pytest.raises(closure.ClosureError, match="cap is not"):
        closure.structural_arithmetic(profile, closure.INCUMBENT_T + 1)
    with pytest.raises(closure.ClosureError, match="profile is not"):
        closure.structural_arithmetic(census.decode_profile("66665555555322000000"), 266)


# STS(13) classification -----------------------------------------------------------------


def test_representatives_have_the_recorded_groups_and_orbits() -> None:
    cyclic, noncyclic = classes()["CYCLIC"], classes()["NONCYCLIC"]
    assert (cyclic.automorphisms, cyclic.pasch) == (39, 13)
    assert cyclic.orbits == (tuple(range(13)),)
    assert (noncyclic.automorphisms, noncyclic.pasch) == (6, 8)
    assert noncyclic.orbits == ((0, 1, 4, 8, 11, 12), (2, 7, 9), (3, 5, 10), (6,))
    assert closure.isomorphisms(cyclic.blocks, noncyclic.blocks) == []


def test_isomorphism_search_finds_every_map_onto_a_relabelled_copy() -> None:
    blocks = classes()["NONCYCLIC"].blocks
    sigma = list(range(13))
    random.Random(649).shuffle(sigma)
    image = tuple(tuple(sorted(sigma[p] for p in block)) for block in blocks)
    maps = closure.isomorphisms(blocks, image)
    assert len(maps) == 6
    assert tuple(sigma) in maps


def test_is_sts13_rejects_broken_systems() -> None:
    blocks = classes()["CYCLIC"].blocks
    assert closure.is_sts13(blocks)
    assert not closure.is_sts13(blocks[1:])
    first = blocks[0]
    assert not closure.is_sts13(((first[0], first[1], (first[2] + 1) % 13), *blocks[1:]))


def test_labeled_mass_leaves_no_third_class() -> None:
    completions, labeled = closure.labeled_sts13_total()
    assert (completions, labeled) == (115_200, 1_197_504_000)
    reps = list(classes().values())
    masses = closure.classification_completeness(reps, labeled)
    assert masses == {"CYCLIC": 159_667_200, "NONCYCLIC": 1_037_836_800}
    with pytest.raises(closure.ClosureError, match="leaves room"):
        closure.classification_completeness(reps, labeled + 1)
    wrong = [replace(reps[0], automorphisms=78), reps[1]]
    with pytest.raises(closure.ClosureError, match="leaves room"):
        closure.classification_completeness(wrong, labeled)
    with pytest.raises(closure.ClosureError, match="Pasch"):
        closure.classification_completeness([reps[0], replace(reps[1], pasch=13)], labeled)


# Representatives and classification ------------------------------------------------------


def test_every_pointed_class_is_a_t270_structure_of_its_own_class() -> None:
    profile = census.decode_profile(closure.INCUMBENT_PROFILE)
    seen: list[str] = []
    for sts in classes().values():
        for orbit in sts.orbits:
            class_id = f"{sts.name}/orbit{orbit[0]}"
            for point in orbit[:2]:
                structure = closure.pointed_structure(sts.blocks, point)
                assert census.realization(profile, structure).triangles == 270
                assert closure.classify(structure, classes()) == class_id
            seen.append(class_id)
    assert seen == list(RECORDED_COUNTS)


def test_classification_is_invariant_under_relabelling() -> None:
    for sts in classes().values():
        for orbit in sts.orbits:
            tickets = census.portfolio(closure.pointed_structure(sts.blocks, orbit[-1]))
            for seed in range(3):
                profile, structure = census.structure_from_tickets(relabelled(tickets, seed))
                assert census.profile_id(profile) == closure.INCUMBENT_PROFILE
                assert closure.classify(structure, classes()) == f"{sts.name}/orbit{orbit[0]}"


def test_classify_fails_closed_outside_the_known_classes() -> None:
    structure = closure.pointed_structure(classes()["NONCYCLIC"].blocks, 6)
    with pytest.raises(closure.ClosureError, match="no representative class"):
        closure.classify(structure, {"CYCLIC": classes()["CYCLIC"]})
    with pytest.raises(census.CensusError):
        closure.classify(replace(structure, pairs=structure.pairs[:-1]), classes())


def test_five_representatives_and_the_start_have_the_recorded_exact_counts() -> None:
    rows = closure.representatives(classes(), evaluator())
    counts = {str(r["CLASS_ID"]): r["OFFICIAL_EXACT_COUNT"] for r in rows}
    assert counts == RECORDED_COUNTS
    assert max(RECORDED_COUNTS.values()) == census.START_COUNT < census.STRICT_GAIN_THRESHOLD
    tickets, _ = census.start_portfolio(ROOT)
    assert evaluator()(tickets) == census.START_COUNT
    _, structure = census.structure_from_tickets(tickets)
    assert closure.classify(structure, classes()) == closure.START_CLASS


# Binding the 992 cells -------------------------------------------------------------------


def test_partition_is_990_r30_plus_t266_plus_t270() -> None:
    manifest = census.load_manifest(ROOT / census.MANIFEST_RELATIVE)
    loaded = overlay.load_overlay(ROOT / overlay.OVERLAY_RELATIVE)
    split = closure.partition(manifest, loaded)
    assert (split["MANIFEST_CELLS"], split["R30_CP_SAT_INFEASIBLE"]) == (992, 990)
    assert (split["T266_MANIFEST_INDEX"], split["T270_MANIFEST_INDEX"]) == (522, 0)
    dropped = dict(loaded.imports)
    dropped.pop(next(iter(dropped)))
    with pytest.raises(closure.ClosureError, match="not 990"):
        closure.partition(manifest, replace(loaded, imports=dropped))
    realized = loaded.r30_realized | {closure.T266_CELL}
    with pytest.raises(closure.ClosureError, match="realized another cell"):
        closure.partition(manifest, replace(loaded, r30_realized=realized))


@needs_objects
def test_t266_theorem_certifies_exactly_its_cell() -> None:
    manifest = census.load_manifest(ROOT / census.MANIFEST_RELATIVE)
    body = closure.t266_certificate(manifest, ROOT)
    assert body["CELL"] == ["66665555555322000000", 266]
    assert (body["W"], body["OPEN_WEDGE_CEILING_AT_T"], body["OPEN_WEDGES_MIN"]) == (831, 33, 48)
    assert body["T_MAX"] == 261


@needs_objects
def test_t266_binding_refuses_a_theorem_that_certifies_another_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = census.load_manifest(ROOT / census.MANIFEST_RELATIVE)
    pinned = closure.t266.certificate

    def widened(
        m: census.Manifest, row: census.SliceRow, equivalence: str, root: Path
    ) -> dict[str, object] | None:
        if row.profile_id == closure.INCUMBENT_PROFILE:
            return {"CELL": "WIDENED"}
        return pinned(m, row, equivalence, root)

    monkeypatch.setattr(closure.t266, "certificate", widened)
    with pytest.raises(closure.ClosureError, match="exactly one cell"):
        closure.t266_certificate(manifest, ROOT)


@needs_objects
def test_t270_re_derivation_requires_the_start_in_its_recorded_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(closure, "START_CLASS", "NONCYCLIC/orbit0")
    with pytest.raises(closure.ClosureError, match="canonical start"):
        closure.t270_closure(ROOT, evaluator())


def test_disposition_is_strict_at_the_threshold() -> None:
    assert closure.disposition(census.START_COUNT) == "PROVED_NO_STRICT_GAIN"
    assert closure.disposition(census.STRICT_GAIN_THRESHOLD) == "STRICT_GAIN_FOUND"


# Durable result --------------------------------------------------------------------------


def test_committed_result_is_pinned_and_states_its_scope() -> None:
    raw = (ROOT / closure.RESULT_RELATIVE).read_bytes()
    assert census.sha256_bytes(raw) == closure.RESULT_SHA256
    result = json.loads(raw)
    assert result["SLICE1_SCIENTIFIC_NO_STRICT_GAIN"] == "PROVED"
    assert result["FROZEN_SLICE1_NO_STRICT_GAIN"] == "PASS"
    assert result["RUN1_EXECUTION_TERMINAL"] == "NOT_CLAIMED"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["MAX_OFFICIAL_EXACT_COUNT"] == 313_263_888
    assert result["STRICT_GAIN_THRESHOLD"] == 313_263_889
    assert result["EVIDENCE_BOUNDARY"]["CP_SAT_SOLVES"] == 0
    assert result["PARTITION"]["DISJOINT_AND_COVERING"] is True


def test_closure_never_reads_run1_or_builds_a_model() -> None:
    source = Path(str(closure.__file__)).read_text()
    for forbidden in (census.DURABLE_RELATIVE, "support_model", "cp_sat_solve", "ortools"):
        assert forbidden not in source


@needs_objects
def test_committed_result_is_its_exact_re_derivation() -> None:
    data = closure.render(closure.closure(ROOT, evaluator()))
    assert data == (ROOT / closure.RESULT_RELATIVE).read_bytes()
