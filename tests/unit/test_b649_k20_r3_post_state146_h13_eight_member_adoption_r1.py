"""Independent arithmetic, complete accounting, and falsifiable H13 controls."""

from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_post_state146_h13_eight_member_adoption_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, owner_region, TS53 17/18 subset validator, or solver")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module, names in (
            (cert.ts53, ("validate_subset", "subset_proof", "build_result")),
            (cert.hunter.r7, ("joint_residual_census", "_joint_residual_states")),
            (cert.hunter.r14, ("owner_region", "s4_child", "run_chase")),
            (cert.hunter.r6, ("iter_type_count_vectors", "candidate_type_count_vectors")),
            (cert.hunter.r8, ("support_model_status", "solver_runtime_preflight")),
        ):
            for name in names:
                if hasattr(module, name):
                    patch.setattr(module, name, forbidden)
        return cert.build_result()


def test_exact_base_donor_and_executing_import_closure(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert result["SOURCE_AUTHORITY"] == authority
    assert authority["BASE"] == {
        "HEAD": "c7a8b87bd844afa87893d588b76de71096750a76",
        "TREE": "7ca8d8f8840bad846e3f5fbca4c948e6f499d5ce",
        "RESULT_SHA256": "2680e9b1f396991336690ee7660998c4a010c6f14efef40c77e601e3d3280834",
    }
    assert authority["TS53_DONOR"] == {
        "HEAD": "3212e448cbe0a9a150d9705ae95dc68669a3106a",
        "TREE": "ac60557c255a88e933502c8ed2ded6d84062752e",
        "RESULT_SHA256": "3c9583835d5e9f72c21d1ecf09065b1e89bda0e4bd5e18e798b9eb7645d20e31",
    }
    for relative, expected in authority["upstream_sha256"].items():
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == expected
    for relative in (cert.SOURCE_RELATIVE, cert.TEST_RELATIVE):
        assert (
            authority["implementation_sha256"][relative]
            == sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest()
        )
    assert (
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py"
        in authority["upstream_sha256"]
    )


def test_full_ledger_selection_all_signatures_and_single_vector_targets(
    result: dict[str, Any],
) -> None:
    original = cert.sealed(cert.ts53.RESULT_RELATIVE)["COMPLETE_REGION_MEMBERS"]
    members, vectors = result["COMPLETE_REGION_MEMBERS"], result["COMPLETE_VECTOR_BOUNDS"]
    assert len(members) == len({r["member_id"] for r in members}) == 1427
    assert len(vectors) == len({cert.dense(r["counts"]) for r in vectors}) == 1543
    selected = [r for r in original if r["final_bound"] > 355112590]
    expected = {
        "[0,13][1,1][4,2][5,1][25,1]",
        "[0,13][1,2][4,1][5,1][25,1]",
        "[0,13][1,3][5,1][25,1]",
        "[0,13][4,3][5,1][25,1]",
        "[0,13][1,1][4,2][16,1][25,1]",
        "[0,13][1,2][4,1][16,1][25,1]",
        "[0,13][1,3][16,1][25,1]",
        "[0,13][4,3][16,1][25,1]",
    }
    assert {r["member_id"] for r in selected} == expected
    assert {r["member_id"] for r in result["MEMBER_CERTIFICATES"]} == expected
    assert all(r["represented_vector_count"] == 1 for r in selected)
    assert cert.region_vectors() == cert.ts53.represented_vectors()
    for old, new in zip(original, members, strict=True):
        assert new["represented_vectors"] == old["represented_vectors"]
        assert new["compression_signature"] == old["compression_signature"]
        assert new["member_id"] == old["member_id"]
        assert new["raw_bound"] == old["raw_bound"]
        assert new["prior_bound"] == old["final_bound"]


def test_h13_bounded_applicability_and_ts53_negative_control(result: dict[str, Any]) -> None:
    core = (13, *([0] * 29))
    for record in result["MEMBER_CERTIFICATES"]:
        v = cert.dense(record["counts"])
        assert sum(v) == 18 and v[0] == 13
        assert record["selected_subset_counts"] == [[0, 13]]
        cert.validate_h13_subset(v, core)
        with pytest.raises(AssertionError, match="17/18"):
            cert.ts53.validate_subset(v, core)
    v = cert.dense(result["MEMBER_CERTIFICATES"][0]["counts"])
    for bad_v, bad_u in (
        (v[:-1], core),
        (v, core[:-1]),
        (v, (14, *([0] * 29))),
        (v, (12, 1, *([0] * 28))),
        (v, (13.0, *([0] * 29))),
        (v, (13, -1, 1, *([0] * 27))),
        (v, v),
        ((12, v[1] + 1, *v[2:]), core),
    ):
        with pytest.raises(AssertionError, match="H13 requires"):
            cert.validate_h13_subset(cast(cert.CountVector, bad_v), cast(cert.CountVector, bad_u))


def test_four_exact_residual_pair_floors_and_raw_intersections(result: dict[str, Any]) -> None:
    proof = result["H13_PROOF"]
    assert proof["pair_floors"] == [107800, 574000, 1691620, 3451651]
    assert [r[:6] for r in proof["pair_rows"]] == [[0, 0, 0, 0, 0, z] for z in range(4)]
    for row in proof["pair_recount"]:
        z = row["outside_overlap"]
        assert (
            row["raw_E"] - row["triple_A"] - row["triple_B"] + row["quadruple"]
            == (proof["pair_floors"][z])
            == row["residual_R"]
        )
        assert cert.hunter.six.residual_pair_intersection(0, 0, (0, 0, 0, z)) == row["residual_R"]
    rows = cert.hunter.exact_pair_rows(((0, 0),))
    for i in range(4):
        invalid = tuple(f + int(i == j) for j, f in enumerate(cert.FLOORS))
        with pytest.raises(AssertionError):
            cert.validate_pair_floors(cast(cert.hunter.Cells, invalid), rows)
    with pytest.raises(AssertionError):
        cert.validate_pair_floors(cert.FLOORS, rows[:-1])


def test_balanced_collision_and_independent_complete_threshold_minimum(
    result: dict[str, Any],
) -> None:
    proof = result["H13_PROOF"]
    assert proof["outside_labels"] == 40 and proof["outside_incidences"] == 78
    assert proof["balanced_frequencies"] == [[1, 2], [2, 38]]
    assert 2 * comb(1, 2) + 38 * comb(2, 2) == proof["collision_floor"] == 38
    for high in range(2, 79):
        for low in range(high - 1):
            assert comb(high, 2) + comb(low, 2) > comb(high - 1, 2) + comb(low + 1, 2)
    rho = [next(rank for rank in range(13) if comb(rank + 1, 2) >= e) for e in range(79)]
    assert proof["rank_floor_table"] == rho
    cases = 0
    best: tuple[int, tuple[int, int, int]] | None = None
    for e1 in range(79):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 38:
                    continue
                value = 12 * 107800 + 466200 * rho[e1] + 1117620 * rho[e2] + 1760031 * rho[e3]
                candidate = (value, (e1, e2, e3))
                best = candidate if best is None else min(best, candidate)
                cases += 1
    assert cases == proof["threshold_cases"] == 83479
    assert best == (5489400, (38, 0, 0))
    assert proof["minimizer"] == [38, 0, 0] and proof["ranks"] == [9, 0, 0]
    assert proof["hunter_floor"] == 12 * 107800 + 9 * (574000 - 107800) == 5489400


def test_universal_rank_nested_kruskal_and_pointwise_full_tree_hunter() -> None:
    assert cert.hunter.verify_rank_floor_algebra(13) == 79
    assert cert.hunter.verify_threshold_tree_lemma() > 0
    indices = tuple(reversed(range(5, 18)))
    core = tuple((indices[0], j) for j in indices[1:])
    leaves = tuple((indices[0], j) for j in range(5))
    full = cert.validate_tree_extension(indices, core, leaves)
    assert len(full) == cert.hunter.graph_rank(18, full) == 17
    # Event-presence Boolean lemma, not enumeration of lottery outcomes.
    edge_masks = tuple((1 << a) | (1 << b) for a, b in full)
    for mask in range(1 << 18):
        present_edges = sum(mask & edge == edge for edge in edge_masks)
        assert int(mask != 0) <= mask.bit_count() - present_edges
    for bad in (leaves[:-1], (core[0], *leaves[1:]), ((indices[0], 18), *leaves[1:])):
        with pytest.raises(AssertionError, match="18-vertex"):
            cert.validate_tree_extension(indices, core, bad)
    with pytest.raises(AssertionError, match="18-vertex"):
        cert.validate_tree_extension(indices, (*core[:-1], core[0]), leaves)


def test_max_only_credits_eight_bounds_and_sound_witnesses(result: dict[str, Any]) -> None:
    bounds: list[int] = []
    for record in result["MEMBER_CERTIFICATES"]:
        v = cert.dense(record["counts"])
        bound = 354793418 if v[5] else 354792970
        prior = 355116818 if v[5] else 355116370
        assert record["member_prior_bound"] == record["vector_prior_bound"] == prior
        assert record["existing_applied_credit"] == 5166000
        assert record["new_credit"] == max(record["corrections"].values()) == 5489400
        assert record["vector_new_bound"] == record["member_new_bound"] == bound
        assert bound == record["uncorrected_bound"] - 5489400
        assert record["uncorrected_bound"] == record["anchor_union"] + record["residual_event_sum"]
        witness = record["witness_analysis"]
        support = tuple(tuple(t) for t in witness["support_witness"])
        assert cert.hunter.r8.validate_support_assignment(v, support)
        assert witness["observed"]["collision_mass"] >= 38
        assert witness["observed"]["exact_tree_weight"] >= 5489400
        bad = (support[1], *support[1:])
        assert not cert.hunter.r8.validate_support_assignment(v, bad)
        bounds.append(bound)
    assert bounds.count(354793418) == bounds.count(354792970) == 4
    assert cert.apply_credit(100, 60, {"stronger_existing": 50, "H13": 30}) == (50, 50)
    assert cert.apply_credit(100, 40, {"existing": 60, "H13": 30}) == (60, 40)


def test_preserve_every_untouched_member_and_vector_and_recompute_all_terms(
    result: dict[str, Any],
) -> None:
    targets = set(result["NEW_TARGET_BOUNDS"])
    members = result["COMPLETE_REGION_MEMBERS"]
    vectors = result["COMPLETE_VECTOR_BOUNDS"]
    remainder = [r for r in members if r["member_id"] not in targets]
    untouched = [r for r in vectors if r["member_id"] not in targets]
    assert len(remainder) == 1419 and len(untouched) == 1535
    assert all(r["prior_bound"] == r["final_bound"] for r in (*remainder, *untouched))
    assert sum(r["prior_bound"] != r["final_bound"] for r in members) == 8
    assert sum(r["prior_bound"] != r["final_bound"] for r in vectors) == 8
    assert max(r["final_bound"] for r in remainder) == 355110434
    assert max(r["final_bound"] for r in members) == result["NEW_STATE_13548976_UB"] == 355110434
    before = cert.family_terms()
    after = tuple((k, 355110434 if k == cert.STATE_ID else b) for k, b in before)
    assert len(before) == len(after) == len(dict(after)) == 56574
    assert sum(a != b for a, b in zip(before, after, strict=True)) == 1
    assert after[23:] == before[23:]
    assert len(result["FINAL_STATE_TERMS"]) == 23
    assert dict(after)["state:s2-14696976-s3-1059324"] == 354603232
    ordered = sorted(after, key=lambda r: (-r[1], r[0]))
    assert ordered[:2] == [
        ("state:s2-13169800-s3-789320", 355112590),
        ("state:s2-12695020-s3-735532", 355111939),
    ]
    assert result["FINAL_OWNER"] == ordered[0][0]
    assert result["RUNNER_UP"] == {"stable_id": ordered[1][0], "bound": ordered[1][1]}
    assert max(b for _, b in after) == result["FINAL_COMPLETE_R3_UB"] == 355112590
    assert max(b for _, b in before) == result["START_COMPLETE_R3_UB"] == 355116818
    assert max(b for _, b in after[23:-1]) == 354800665
    assert after[-1] == ("unclassified-tail", 354039277)
    assert result["STRICT_GAIN"] == 4228 and result["REMAINING_GAP"] == 41848702
    assert cert.family_digest(after) == result["FAMILY_RECOMPUTATION"]["new_sha256"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_member",
        "missing_vector",
        "wrong_signature",
        "subset",
        "floor",
        "collision",
        "cases",
        "minimum",
        "attachment",
        "SUM_credit",
        "bound",
        "untouched_member",
        "untouched_vector",
        "state146",
        "missing_state",
        "classified",
        "tail",
        "owner",
        "gap",
        "illegal_witness",
    ],
)
def test_semantic_result_mutations_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    record = bad["MEMBER_CERTIFICATES"][0]
    proof = bad["H13_PROOF"]
    if mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "missing_vector":
        record["represented_vectors"].pop()
    elif mutation == "wrong_signature":
        record["compression_signature"][0] += 1
    elif mutation == "subset":
        record["selected_subset_counts"][0][1] = 14
    elif mutation == "floor":
        proof["pair_floors"][1] += 1
    elif mutation == "collision":
        proof["collision_floor"] -= 1
    elif mutation == "cases":
        proof["threshold_cases"] -= 1
    elif mutation == "minimum":
        proof["hunter_floor"] += 1
    elif mutation == "attachment":
        proof["tree_attachments"][0] = proof["tree_core"][0]
    elif mutation == "SUM_credit":
        record["new_credit"] = sum(record["corrections"].values())
        record["vector_new_bound"] = record["uncorrected_bound"] - record["new_credit"]
    elif mutation == "bound":
        record["vector_new_bound"] -= 1
    elif mutation in ("untouched_member", "untouched_vector"):
        rows = bad[
            "COMPLETE_REGION_MEMBERS"
            if mutation == "untouched_member"
            else "COMPLETE_VECTOR_BOUNDS"
        ]
        next(r for r in rows if r["member_id"] not in bad["NEW_TARGET_BOUNDS"])["final_bound"] -= 1
    elif mutation == "state146":
        bad["NEW_STATE_14696976_UB"] -= 1
    elif mutation == "missing_state":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "classified":
        bad["FAMILY_RECOMPUTATION"]["classified_max"] -= 1
    elif mutation == "tail":
        bad["FAMILY_RECOMPUTATION"]["tail"] -= 1
    elif mutation == "owner":
        bad["FINAL_OWNER"] = cert.STATE_ID
    elif mutation == "gap":
        bad["REMAINING_GAP"] -= 1
    else:
        support = record["witness_analysis"]["support_witness"]
        support[0] = support[1]
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


def test_live_overstrong_floor_threshold_and_family_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cert.h13_proof.cache_clear()
    original = cert.hunter.minimum_tree_correction

    def overstrong(phi: cert.hunter.Cells, mass: int, k: int = 18) -> cert.hunter.TreeMinimum:
        return replace(original(phi, mass, k), correction=5489401)

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "minimum_tree_correction", overstrong)
        with pytest.raises(AssertionError, match="threshold"):
            cert.h13_proof()
    cert.h13_proof.cache_clear()
    assert cert.h13_proof()["hunter_floor"] == 5489400
    for bad in (
        cert.family_terms()[:-2] + cert.family_terms()[-1:],
        ((cert.family_terms()[0][0], 1), *cert.family_terms()[1:]),
    ):
        with pytest.raises(AssertionError, match="preserved"):
            cert.recompute_family(bad, 355110434)


@pytest.mark.parametrize(
    "relative",
    [
        cert.BASE_RESULT,
        cert.ts53.RESULT_RELATIVE,
        "src/lottolab/__init__.py",
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py",
        cert.SOURCE_RELATIVE,
        cert.TEST_RELATIVE,
    ],
)
def test_source_tampering_rejected_after_warm_caches(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    original = Path.read_bytes

    def tampered(path: Path) -> bytes:
        data = original(path)
        return data + b"\n" if path == cert.REPO_ROOT / relative else data

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", tampered)
        with pytest.raises(AssertionError, match=r"identity|source binding"):
            cert.verify_result(result)
    assert cert.verify_result(result)["status"] == "PASS"


@pytest.mark.parametrize(
    "old,new",
    [
        ("new_credit = max(credits.values())", "new_credit = sum(credits.values())"),
        (
            "min(prior_bound, uncorrected - new_credit)",
            "min(prior_bound, uncorrected - 2 * new_credit)",
        ),
    ],
)
def test_actual_credit_source_mutants_killed(old: str, new: str) -> None:
    source = inspect.getsource(cert.apply_credit)
    assert source.count(old) == 1
    namespace = dict(vars(cert))
    exec(compile(source.replace(old, new), "<targeted-credit-mutant>", "exec"), namespace)
    mutant = cast(Callable[..., tuple[int, int]], namespace["apply_credit"])
    args = (100, 80, {"existing": 20, "H13": 30})
    assert cert.apply_credit(*args) == (30, 70)
    with pytest.raises(AssertionError):
        assert mutant(*args) == (30, 70)
    assert cert.apply_credit(*args) == (30, 70)


def test_stored_bytes_replay_and_no_prohibited_work(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert json.loads(cert.RESULT_PATH.read_bytes()) == result
    assert cert.verify_stored_result()["status"] == "PASS"
    assert result["OWNER_REGION_CALLS"] == result["R7_CENSUS_CALLS"] == 0
    assert result["HEAVY_SOLVER_USED"] is result["OFFICIAL_OUTCOME_ENUMERATION_USED"] is False
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"
