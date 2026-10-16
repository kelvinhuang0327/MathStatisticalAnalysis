"""Independent exact arithmetic and falsifiable fourteen-member adoption controls."""

from __future__ import annotations

import copy
import inspect
import runpy
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_post_h13_two_state_h11_h16_14_member_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor rebuild, census, owner_region, or solver")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    from lottolab.research import b649_k20_r3_state_14696976_universal_hunter_certificate_r1 as s146

    with pytest.MonkeyPatch.context() as patch:
        for module, names in (
            (cert.h13, ("build_result", "h13_proof")),
            (s146, ("build_result", "core_proof", "certificate_rows", "root_pair_proof")),
            (cert.root65, ("build_result", "core_proof", "root_pair_proof")),
            (cert.root65.ts153, ("build_result", "subset_proof")),
            (cert.hunter.r7, ("joint_residual_census", "_joint_residual_states")),
            (cert.hunter.r14, ("owner_region", "s4_child", "run_chase")),
            (cert.hunter.r6, ("iter_type_count_vectors", "candidate_type_count_vectors")),
            (cert.hunter.r8, ("support_model_status", "solver_runtime_preflight")),
        ):
            for name in names:
                if hasattr(module, name):
                    patch.setattr(module, name, forbidden)
        return cert.build_result()


def test_fixed_authority_and_transitive_source_bytes(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert authority == result["SOURCE_AUTHORITY"]
    assert (authority["HEAD"], authority["TREE"], authority["RESULT_SHA256"]) == (
        "15d1630c1c096efe63897b7094b75c31b888cb2a",
        "c1cc447e2e0e658f351e432da4052704c178ef71",
        "a22b87d1954f92f4ffef90c45dae51ee7ff74a093244bfe37c831166f5e47adb",
    )
    for path, expected in {
        **authority["upstream_sha256"],
        **authority["implementation_sha256"],
    }.items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == expected
    for path in (
        cert.BASE_RESULT,
        cert.root65.RESULT_RELATIVE,
        cert.root65.ts153.RESULT_RELATIVE,
        cert.root65.r12.RESULT_RELATIVE,
        cert.h13.BASE_RESULT,
    ):
        assert path in authority["upstream_sha256"]
    assert (
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py"
        in authority["upstream_sha256"]
    )


@pytest.mark.parametrize(
    "state,mc,vc,tc,n", [(cert.STATE_A, 989, 1072, 2, 16), (cert.STATE_B, 1222, 1325, 12, 11)]
)
def test_full_regions_aliases_and_exact_single_vector_target_selection(
    result: dict[str, Any],
    state: str,
    mc: int,
    vc: int,
    tc: int,
    n: int,
) -> None:
    region = next(r for r in result["REGIONS"] if r["state_id"] == state)
    rows = region["complete_region_members"]
    assert len(rows) == len({r["member_id"] for r in rows}) == mc
    vectors = [v for r in rows for v in r["represented_vector_bounds"]]
    assert len(vectors) == len({cert.dense(v["counts"]) for v in vectors}) == vc
    if state == cert.STATE_A:
        expected = {"[0,16][1,1][25,1]", "[0,16][4,1][25,1]"}
    else:
        expected = {
            "[0,11]" + (f"[1,{j}]" if j else "") + (f"[4,{5 - j}]" if j < 5 else "") + tail
            for j in range(6)
            for tail in ("[5,1][10,1]", "[10,1][16,1]")
        }
    records = region["member_certificates"]
    assert len(records) == tc and {r["member_id"] for r in records} == expected
    for record in records:
        v = cert.dense(record["counts"])
        assert sum(v) == 18 and v[0] == n
        assert record["represented_vector_count"] == 1
        assert record["represented_vectors"] == [cert.sparse(v)]
        assert cert.region_vectors(state)[v] == (v,)
        cert.validate_subset(v, cert.dense(record["selected_subset_counts"]), n)
    for old, new in zip(cert.region_rows(state), rows, strict=True):
        for key in (
            "member_id",
            "witness_counts",
            "represented_vectors",
            "compression_signature",
            "raw_bound",
        ):
            assert new[key] == old[key]
        assert new["prior_bound"] == old["final_bound"]
        assert new["final_bound"] == max(v["final_bound"] for v in new["represented_vector_bounds"])


@pytest.mark.parametrize(
    "n,incidences,q,cases,rank,floor",
    [
        (11, 66, 26, 30216, 7, 4341400),
        (16, 96, 72, 291143, 12, 7211400),
    ],
)
def test_independent_complete_integer_threshold_minimum(
    result: dict[str, Any],
    n: int,
    incidences: int,
    q: int,
    cases: int,
    rank: int,
    floor: int,
) -> None:
    proof = result["CORE_PROOFS"][f"H{n}"]
    assert proof["outside_incidences"] == incidences and proof["outside_labels"] == 40
    a, b = divmod(incidences, 40)
    assert proof["balanced_frequencies"] == [[a, 40 - b], [a + 1, b]]
    assert (40 - b) * comb(a, 2) + b * comb(a + 1, 2) == q == proof["collision_floor"]
    capacity = comb(n, 2)
    rho = [next(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(capacity + 1)]
    assert proof["rank_floor_table"] == rho
    best: tuple[int, tuple[int, int, int]] | None = None
    count = 0
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < q:
                    continue
                value = (n - 1) * 107800 + 466200 * rho[e1] + 1117620 * rho[e2] + 1760031 * rho[e3]
                candidate = (value, (e1, e2, e3))
                best = candidate if best is None else min(best, candidate)
                count += 1
    assert count == cases == proof["threshold_cases"]
    assert best == (floor, (q, 0, 0))
    assert proof["ranks"] == [rank, 0, 0] and proof["minimizer"] == [q, 0, 0]
    assert proof["hunter_floor"] == floor == (n - 1) * 107800 + rank * (574000 - 107800)
    assert proof["attachment_credit"] == 0


def test_exact_residual_floors_and_mixed_raw_pair_negative_controls(result: dict[str, Any]) -> None:
    proof = result["PAIR_PROOF"]
    assert proof["pair_floors"] == [107800, 574000, 1691620, 3451651]
    assert [r[:6] for r in proof["pair_rows"]] == [[0, 0, 0, 0, 0, z] for z in range(4)]
    for r in proof["recount"]:
        assert r["raw_E"] - r["triple_A"] - r["triple_B"] + r["quadruple"] == r["residual_R"]
        assert r["residual_R"] == proof["pair_floors"][r["overlap"]]
    rows = cert.hunter.exact_pair_rows(((0, 0),))
    raw = cast(cert.hunter.Cells, tuple(r["raw_E"] for r in proof["recount"]))
    with pytest.raises(AssertionError):
        cert.validate_pair_floors(raw, rows)
    with pytest.raises(AssertionError, match="mixed pairs"):
        cert.validate_pair_floors(cert.FLOORS, cert.hunter.exact_pair_rows(((0, 1),)))
    with pytest.raises(AssertionError):
        cert.validate_pair_floors(cert.FLOORS, rows[:-1])


def test_universal_smoothing_rank_nested_kruskal_and_pointwise_hunter() -> None:
    for high in range(2, 97):
        for low in range(high - 1):
            assert (
                comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
                == high - low - 1
                > 0
            )
    for n in (11, 16):
        assert cert.hunter.verify_rank_floor_algebra(n) == comb(n, 2) + 1
        indices = tuple(reversed(range(18 - n, 18)))
        core = tuple((indices[0], j) for j in indices[1:])
        leaves = tuple((indices[0], j) for j in range(18 - n))
        full = cert.validate_tree_extension(indices, core, leaves)
        assert len(full) == cert.hunter.graph_rank(18, full) == 17
        edge_masks = tuple((1 << a) | (1 << b) for a, b in full)
        # All event-presence masks, not lottery official outcomes.
        for mask in range(1 << 18):
            assert int(mask != 0) <= mask.bit_count() - sum(mask & e == e for e in edge_masks)
        for bad in (leaves[:-1], (core[0], *leaves[1:]), ((indices[0], 18), *leaves[1:])):
            with pytest.raises(AssertionError, match="18-vertex"):
                cert.validate_tree_extension(indices, core, bad)
        with pytest.raises(AssertionError):
            cert.validate_tree_extension(indices, (*core[:-1], core[0]), leaves)
    assert cert.hunter.verify_threshold_tree_lemma() == 4096


def test_illegal_subsets(result: dict[str, Any]) -> None:
    for region in result["REGIONS"]:
        record = region["member_certificates"][0]
        v = cert.dense(record["counts"])
        n = v[0]
        core = (n, *([0] * 29))
        for bad_v, bad_u, bad_n in (
            (v[:-1], core, n),
            (v, core[:-1], n),
            (v, (n - 1, 1, *([0] * 28)), n),
            (v, (float(n), *([0] * 29)), n),
            (v, (n, -1, 1, *([0] * 27)), n),
            ((n - 1, v[1] + 1, *v[2:]), core, n),
            (v, core, 13),
        ):
            with pytest.raises(AssertionError, match="H11/H16"):
                cert.validate_subset(
                    cast(cert.CountVector, bad_v), cast(cert.CountVector, bad_u), bad_n
                )


def test_all_target_bounds_max_only_and_sound_witnesses(result: dict[str, Any]) -> None:
    bounds: list[int] = []
    for region in result["REGIONS"]:
        for r in region["member_certificates"]:
            v = cert.dense(r["counts"])
            a = region["state_id"] == cert.STATE_A
            expected = 354789190 if a else (354788539 if v[5] else 354788091)
            assert r["existing_applied_credit"] == (6888000 if a else 4018000)
            assert r["new_credit"] == max(r["corrections"].values()) == (7211400 if a else 4341400)
            assert r["vector_new_bound"] == r["member_new_bound"] == expected
            assert expected == r["uncorrected_bound"] - r["new_credit"]
            assert r["uncorrected_bound"] == r["anchor_union"] + r["residual_event_sum"]
            witness = r["witness_analysis"]
            support = tuple(tuple(t) for t in witness["support_witness"])
            assert cert.hunter.r8.validate_support_assignment(v, support)
            assert not cert.hunter.r8.validate_support_assignment(v, (support[1], *support[1:]))
            assert witness["observed"]["exact_tree_weight"] >= r["new_credit"]
            bounds.append(expected)
    assert (bounds.count(354789190), bounds.count(354788539), bounds.count(354788091)) == (2, 6, 6)
    assert cert.apply_credit(100, 60, {"existing": 50, "H11": 30}) == (50, 50)
    assert cert.apply_credit(100, 40, {"existing": 20, "H16": 30}) == (30, 40)
    assert cert.member_bound((40, 60)) == 60


def test_every_untouched_bound_and_complete_family_recomputation(result: dict[str, Any]) -> None:
    for region in result["REGIONS"]:
        state = region["state_id"]
        target_ids = {r["member_id"] for r in region["member_certificates"]}
        remainder = [
            r for r in region["complete_region_members"] if r["member_id"] not in target_ids
        ]
        vectors = [v for r in remainder for v in r["represented_vector_bounds"]]
        expected = (987, 1070, 355016928) if state == cert.STATE_A else (1210, 1313, 355107928)
        assert (len(remainder), len(vectors), max(r["final_bound"] for r in remainder)) == expected
        assert all(r["final_bound"] == r["prior_bound"] for r in (*remainder, *vectors))
        old = {r["member_id"]: r for r in cert.region_rows(state)}
        for r in remainder:
            assert r["final_bound"] == old[r["member_id"]]["final_bound"]
            for x, y in zip(
                r["represented_vector_bounds"],
                old[r["member_id"]]["represented_vector_bounds"],
                strict=True,
            ):
                assert x["counts"] == y["counts"] and x["final_bound"] == y["final_bound"]
    before = cert.family_terms()
    bounds = {r["state_id"]: r["new_state_bound"] for r in result["REGIONS"]}
    after = tuple((k, bounds.get(k, b)) for k, b in before)
    assert len(before) == len(after) == len(dict(after)) == 56574
    assert sum(x != y for x, y in zip(before, after, strict=True)) == 2
    assert after[23:] == before[23:]
    assert dict(after)[cert.h13.STATE_ID] == 355110434
    assert dict(after)["state:s2-14696976-s3-1059324"] == 354603232
    ordered = sorted(after, key=lambda r: (-r[1], r[0]))
    assert ordered[:2] == [(cert.h13.STATE_ID, 355110434), (cert.STATE_B, 355107928)]
    assert result["FINAL_OWNER"] == ordered[0][0]
    assert result["RUNNER_UP"] == {"stable_id": ordered[1][0], "bound": ordered[1][1]}
    assert max(b for _, b in after) == result["FINAL_COMPLETE_R3_UB"] == 355110434
    assert not [r for r in after if r[1] > 355110434]
    assert max(b for _, b in before) == result["START_COMPLETE_R3_UB"] == 355112590
    assert len(after[23:-1]) == 56550 and max(b for _, b in after[23:-1]) == 354800665
    assert after[-1] == ("unclassified-tail", 354039277)
    assert result["STRICT_GAIN"] == 2156 and result["REMAINING_GAP"] == 41846546
    assert cert.family_digest(after) == result["FAMILY_RECOMPUTATION"]["new_sha256"]
    with pytest.raises(AssertionError):
        cert.recompute_family(before[:-2] + before[-1:], bounds)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_A",
        "missing_B",
        "missing_alias",
        "mixed_pair",
        "Q11",
        "Q16",
        "H11",
        "H16",
        "subset",
        "extension",
        "SUM",
        "member_MIN",
        "untouched_member",
        "untouched_vector",
        "owner",
        "runner_up",
        "state135",
        "state146",
        "classified",
        "tail",
        "witness",
        "source_hash",
    ],
)
def test_semantic_result_mutations_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    a, b = bad["REGIONS"]
    record = a["member_certificates"][0]
    if mutation.startswith("missing_") and mutation != "missing_alias":
        (a if mutation == "missing_A" else b)["member_certificates"].pop()
    elif mutation == "missing_alias":
        next(r for r in a["complete_region_members"] if r["represented_vector_count"] > 1)[
            "represented_vectors"
        ].pop()
    elif mutation == "mixed_pair":
        bad["PAIR_PROOF"]["pair_rows"][0][1] = 1
    elif mutation in ("Q11", "Q16"):
        bad["CORE_PROOFS"]["H" + mutation[1:]]["collision_floor"] -= 1
    elif mutation in ("H11", "H16"):
        bad["CORE_PROOFS"][mutation]["hunter_floor"] += 1
    elif mutation == "subset":
        record["selected_subset_counts"][0][1] += 1
    elif mutation == "extension":
        proof = bad["CORE_PROOFS"]["H16"]
        proof["tree_attachments"][0] = proof["tree_core"][0]
    elif mutation == "SUM":
        record["new_credit"] = sum(record["corrections"].values())
        record["vector_new_bound"] = record["uncorrected_bound"] - record["new_credit"]
    elif mutation == "member_MIN":
        row = next(
            r
            for r in b["complete_region_members"]
            if len({v["final_bound"] for v in r["represented_vector_bounds"]}) > 1
        )
        row["final_bound"] = min(v["final_bound"] for v in row["represented_vector_bounds"])
    elif mutation in ("untouched_member", "untouched_vector"):
        targets = {r["member_id"] for r in a["member_certificates"]}
        row = next(r for r in a["complete_region_members"] if r["member_id"] not in targets)
        (row if mutation == "untouched_member" else row["represented_vector_bounds"][0])[
            "final_bound"
        ] -= 1
    elif mutation in ("owner", "runner_up"):
        if mutation == "owner":
            bad["FINAL_OWNER"] = cert.STATE_A
        else:
            bad["RUNNER_UP"]["stable_id"] = cert.STATE_A
    elif mutation in ("state135", "state146"):
        state = cert.h13.STATE_ID if mutation == "state135" else "state:s2-14696976-s3-1059324"
        next(r for r in bad["FINAL_STATE_TERMS"] if r["stable_id"] == state)["bound"] -= 1
    elif mutation in ("classified", "tail"):
        bad["FAMILY_RECOMPUTATION"]["classified_max" if mutation == "classified" else "tail"] -= 1
    elif mutation == "witness":
        support = record["witness_analysis"]["support_witness"]
        support[0] = support[1]
    else:
        bad["SOURCE_AUTHORITY"]["implementation_sha256"][cert.SOURCE_RELATIVE] = "0" * 64
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


@pytest.mark.parametrize("n", [11, 16])
def test_live_overstrong_minimum_and_wrong_collision_rejected(
    monkeypatch: pytest.MonkeyPatch, n: int
) -> None:
    original = cert.hunter.minimum_tree_correction
    cert.core_proof.cache_clear()

    def overstrong(phi: cert.hunter.Cells, mass: int, k: int = 18) -> cert.hunter.TreeMinimum:
        r = original(phi, mass, k)
        return replace(r, correction=r.correction + 1)

    def wrong_collision(_incidences: int, _labels: int) -> int:
        return 0

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "minimum_tree_correction", overstrong)
        with pytest.raises(AssertionError, match="threshold"):
            cert.core_proof(n)
    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "balanced_collision_mass", wrong_collision)
        with pytest.raises(AssertionError, match="collision"):
            cert.core_proof(n)
    cert.core_proof.cache_clear()
    assert cert.core_proof(n)["hunter_floor"] == (4341400 if n == 11 else 7211400)


@pytest.mark.parametrize(
    "relative",
    [
        cert.BASE_RESULT,
        cert.root65.RESULT_RELATIVE,
        cert.root65.ts153.RESULT_RELATIVE,
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py",
        cert.SOURCE_RELATIVE,
        cert.TEST_RELATIVE,
    ],
)
def test_live_source_result_tampering_after_warm_caches(
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


@pytest.mark.parametrize(
    "function,old,new,args,expected",
    [
        (
            "apply_credit",
            "credit = max(credits.values())",
            "credit = sum(credits.values())",
            (100, 80, {"old": 20, "H11": 30}),
            (30, 70),
        ),
        (
            "apply_credit",
            "uncorrected - credit",
            "uncorrected - 2 * credit",
            (100, 80, {"old": 20, "H16": 30}),
            (30, 70),
        ),
        ("member_bound", "return max(bounds)", "return min(bounds)", ((40, 60),), 60),
    ],
)
def test_non_equivalent_actual_source_mutants_killed(
    function: str,
    old: str,
    new: str,
    args: tuple[Any, ...],
    expected: object,
) -> None:
    original = cast(Callable[..., object], getattr(cert, function))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace = dict(vars(cert))
    exec(compile(source.replace(old, new), "<semantic-source-mutant>", "exec"), namespace)
    mutant = cast(Callable[..., object], namespace[function])
    assert original(*args) == expected
    with pytest.raises(AssertionError):
        assert mutant(*args) == expected
    assert original(*args) == expected


def test_stored_replay_and_prohibited_work_gates(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"
    assert result["OWNER_REGION_CALLS"] == result["R7_CENSUS_CALLS"] == 0
    assert result["STATE146_CERTIFICATE_REBUILD_CALLS"] == 0
    assert (
        result["NEW_HEAVY_SOLVER_STARTED"] is result["OFFICIAL_OUTCOME_ENUMERATION_USED"] is False
    )
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"


@pytest.mark.parametrize(
    "module,relative,name",
    [
        (
            cert.h13.SOURCE_RELATIVE,
            cert.BASE_RESULT,
            "test_exact_base_donor_and_executing_import_closure",
        ),
        (
            cert.h13.SOURCE_RELATIVE,
            cert.BASE_RESULT,
            "test_max_only_credits_eight_bounds_and_sound_witnesses",
        ),
        (
            cert.h13.SOURCE_RELATIVE,
            cert.BASE_RESULT,
            "test_preserve_every_untouched_member_and_vector_and_recompute_all_terms",
        ),
        (
            cert.root65.SOURCE_RELATIVE,
            cert.root65.RESULT_RELATIVE,
            "test_all_members_vectors_aliases_and_65_actual_identities",
        ),
        (
            cert.root65.SOURCE_RELATIVE,
            cert.root65.RESULT_RELATIVE,
            "test_max_only_credits_and_strongest_untouched_vector_bounds",
        ),
        (
            "src/lottolab/research/b649_k20_r3_state_14696976_universal_hunter_certificate_r1.py",
            cert.h13.BASE_RESULT,
            "test_complete_family_only_one_state_changes_and_max_only",
        ),
        (
            "src/lottolab/research/b649_k20_r3_ts153_four_state_wall_adoption_r2.py",
            cert.root65.ts153.RESULT_RELATIVE,
            "test_immutable_authority_complete_regions_and_target_digests",
        ),
        (
            "src/lottolab/research/b649_k20_r3_ts153_four_state_wall_adoption_r2.py",
            cert.root65.ts153.RESULT_RELATIVE,
            "test_max_once_credits_preserved_and_compressed_max",
        ),
        (
            "src/lottolab/research/b649_k20_r3_ts153_four_state_wall_adoption_r2.py",
            cert.root65.ts153.RESULT_RELATIVE,
            "test_untouched_remainder_family_and_witness_soundness",
        ),
    ],
)
def test_relevant_predecessor_checks_without_certificate_rebuild(
    module: str,
    relative: str,
    name: str,
) -> None:
    path = "tests/unit/test_" + Path(module).name
    assert (cert.REPO_ROOT / path).read_bytes() == cert.frozen_blob(path)
    namespace = runpy.run_path(str(cert.REPO_ROOT / path))
    check = cast(Callable[[dict[str, Any]], None], namespace[name])
    check(cert.sealed(relative))
