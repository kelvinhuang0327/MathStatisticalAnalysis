"""Independent Root65 arithmetic, complete ledgers, preservation and defect probes."""

from __future__ import annotations

import copy
import inspect
import json
import runpy
from collections.abc import Callable, Mapping
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_r12_root65_joint_certificate_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden historical rebuild, census, chase or heavy solver")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module in (
            cert.ts153,
            cert.ts153.ts61,
            cert.ts153.joint,
            cert.ts153.ts53,
            cert.ts153.prior,
            cert.ts153.h11,
            cert.r12.nine,
        ):
            patch.setattr(module, "build_result", forbidden)
            patch.setattr(module, "verify_stored_result", forbidden)
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.r12.r6, "iter_type_count_vectors", forbidden)
        patch.setattr(cert.r12.r12, "tail_level_census", forbidden)
        patch.setattr(cert.r12.r12, "classify_vector", forbidden)
        patch.setattr(cert.r12.r24, "run_chase", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        minimum = cert.hunter.minimum_tree_correction

        def bounded(phi: cert.Cells, q: int, n: int = 18) -> Any:
            assert n in (9, 10, 11), "TS153's 19933125 threshold cases must never run"
            return minimum(phi, q, n)

        patch.setattr(cert.hunter, "minimum_tree_correction", bounded)
        return cert.build_result()


def test_base_donor_objects_blobs_and_complete_r12(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert result["SOURCE_AUTHORITY"] == authority
    assert authority["base"]["HEAD"] == "b25f5b17440b8eb3e344f6c2567473081995646c"
    assert authority["base"]["TREE"] == "7ef64b1c6071c53e6612872009f07134aff4af9a"
    assert authority["base"]["RESULT_SHA256"] == cert.BASE_RESULT_SHA256
    assert authority["donor_head"] == "88f7347f84c4497267c8f7871c9da9a09292c728"
    assert authority["donor_tree"] == "88a874df8fb8817b48e8c770772b01c9bd09bde9"
    assert authority["donor_parent"] == cert.BASE_HEAD
    for path, expected_blob in cert.DONOR_BLOBS.items():
        actual = (cert.REPO_ROOT / path).read_bytes()
        frozen = cert.r12.git_bytes("show", f"{cert.DONOR_HEAD}:{path}")
        assert actual == frozen
        git_hash = sha256(actual).hexdigest()
        assert authority["donor_blobs"][path] == {"git_blob": expected_blob, "sha256": git_hash}
    assert authority["donor_blobs"][cert.r12.RESULT_RELATIVE]["sha256"] == (
        "e38e08887221616ce11db5f819941f73a8df267d2758769ff62b78b161cd4659"
    )
    assert authority["donor_judge_status"] == "NOT_PROVIDED; SELF_CHECK_PASS_ONLY"
    donor = cert.adopted_r12()
    levels = donor["COMPLETE_AGGREGATE_LEVELS"]
    assert len(levels) == result["R12_LEVEL_COVERAGE"] == 29
    assert (
        sum(r["represented_vector_count"] for r in levels) == result["R12_VECTOR_COVERAGE"] == 183
    )
    assert result["R12_TARGET_LEVELS"] == [25, 26, 27, 30, 32]
    assert result["R12_TARGET_VECTOR_COUNT"] == 15
    assert result["R12_H10"] == 3750600
    assert donor["NEW_AGGREGATE_MAX"] == 354588304
    assert result["R12_CLASSIFIED_MAX"] == 354800665
    assert result["R12_CLASSIFIED_DIGEST"] == (
        "c5e05f33c98da7ec83bd5cef319a23929600be16df7cbaad36d7a032126acbeb"
    )


def test_all_members_vectors_aliases_and_65_actual_identities(result: dict[str, Any]) -> None:
    expected: dict[str, set[cert.CountVector]] = {"A40": set(), "A7": set(), "B18": set()}
    for j in range(5):
        for k in range(4):
            for t in (6, 9):
                expected["A40"].add(
                    tuple(
                        {0: 10, 1: j, 4: 4 - j, 5: 3 - k, 16: k, t: 1}.get(i, 0) for i in range(30)
                    )
                )
    for k in range(7):
        expected["A7"].add(tuple({0: 12, 5: 6 - k, 16: k}.get(i, 0) for i in range(30)))
    for j in range(6):
        for k in range(3):
            expected["B18"].add(
                tuple({0: 11, 1: j, 4: 5 - j, 17: k, 19: 2 - k}.get(i, 0) for i in range(30))
            )
    observed: dict[str, set[cert.CountVector]] = {n: set() for n in expected}
    all_members = all_vectors = target_count = alias_count = 0
    for region in result["REGIONS"]:
        sid = region["state_id"]
        members = cert.complete_members(sid)
        recovered = cert.ts153.represented_vectors(sid)
        assert len(members) == region["region_member_count"]
        assert len({m.counts for m in members}) == len(members)
        assert sum(len(vs) for vs in recovered.values()) == region["region_vector_count"]
        flat: set[cert.CountVector] = set()
        for member, row in zip(
            members, cert.source_region(sid)["complete_region_members"], strict=True
        ):
            vs = recovered[member.counts]
            signature = cert.hunter.eleven.compression_signature(
                cert.catalog.rebuild_member(member)
            )
            assert row["compression_signature"] == cert.catalog.normalized(signature)
            assert row["represented_vectors"] == [cert.sparse(v) for v in vs]
            assert member.counts == min(vs)
            assert not flat.intersection(vs)
            flat.update(vs)
            alias_count += len(vs) > 1
        for row in region["member_certificates"]:
            v = cert.dense(row["counts"])
            assert recovered[v] == (v,)
            assert next(m for m in members if m.counts == v).represented_vector_count == 1
            assert v in expected[row["cohort"]]
            observed[row["cohort"]].add(v)
            target_count += 1
        all_members += len(members)
        all_vectors += len(flat)
    assert observed == expected
    assert [len(observed[n]) for n in ("A40", "A7", "B18")] == [40, 7, 18]
    assert (all_members, all_vectors, target_count) == (2211, 2397, 65)
    assert alias_count > 0
    assert result["ROOT65_TARGET_MEMBER_COUNT"] == result["ROOT65_TARGET_VECTOR_COUNT"] == 65


def test_36_root_residual_rows_two_exact_counters_and_inclusion_exclusion(
    result: dict[str, Any],
) -> None:
    expected = {
        0: (107800, 574000, 1691620, 3451651),
        1: (107800, 571200, 1679692, 3428908),
        4: (107800, 571200, 1679692, 3428908),
        5: (107800, 568610, 1667932, 3406165),
        6: (105560, 557200, 1649508, 3383814),
        9: (105560, 557200, 1649508, 3383814),
        16: (107800, 568680, 1669066, 3408685),
        17: (105560, 557480, 1650810, 3386334),
        19: (105560, 557480, 1650810, 3386334),
    }
    rows = result["ROOT_PAIR_PROOF"]["rows"]
    assert rows == [
        [0, t, 0, 0, 0, k, cost] for t, costs in expected.items() for k, cost in enumerate(costs)
    ]
    for _, t, *rest in rows:
        cells = cast(cert.Cells, tuple(rest[:4]))
        value = rest[4]
        assert cert.hunter.feasible_cell_overlaps(
            cert.hunter.type_cells(0), cert.hunter.type_cells(t)
        ) == ((0, 0, 0, 0), (0, 0, 0, 1), (0, 0, 0, 2), (0, 0, 0, 3))
        tickets = cert.hunter.realize_pair(
            cert.hunter.type_cells(0), cert.hunter.type_cells(t), cells
        )
        assert (
            tuple(len(tickets[0] & tickets[1] & set(c)) for c in cert.hunter.CELL_LABELS) == cells
        )
        anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
        raw = cert.hunter.outcome_count(tickets)
        ie = raw - sum(cert.hunter.outcome_count((*tickets, a)) for a in anchors)
        ie += cert.hunter.outcome_count((*tickets, *anchors))
        assert ie == cert.six.residual_pair_intersection(0, t, cells) == value
        assert 7 * cert.hunter.count_seven_sets(tickets, anchors) == value >= 105560
    assert len(rows) == 36
    assert min(r[6] for r in rows) == result["ROOT_RESIDUAL_FLOOR"] == 105560
    special = result["ROOT_PAIR_PROOF"]["special_type0_type6_overlap0"]
    assert special["raw_E_pair"] == 107800
    assert special["residual_R_pair"] == 105560
    assert special["triple_A"] + special["triple_B"] - special["quadruple"] == 2240
    for unsafe in (107800, 105561):
        with pytest.raises(AssertionError, match="true residual"):
            cert.require_root_floor(unsafe, tuple(tuple(r) for r in rows))


@pytest.mark.parametrize(
    "n,incidences,mass,cases,floor", [(9, 54, 14, 9016, 3193400), (11, 66, 26, 30216, 4341400)]
)
def test_independent_exact_core_threshold_minima(
    result: dict[str, Any], n: int, incidences: int, mass: int, cases: int, floor: int
) -> None:
    proof = next(p for p in result["CORE_PROOFS"] if p["event_count"] == n)
    q, rem = divmod(incidences, 40)
    assert (40 - rem) * comb(q, 2) + rem * comb(q + 1, 2) == mass
    phi = (107800, 574000, 1691620, 3451651)
    ranks = [next(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(comb(n, 2) + 1)]
    candidates = [
        (
            (n - 1) * phi[0]
            + sum((phi[k + 1] - phi[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))),
            (e1, e2, e3),
        )
        for e1 in range(comb(n, 2) + 1)
        for e2 in range(e1 + 1)
        for e3 in range(e2 + 1)
        if e1 + e2 + e3 >= mass
    ]
    assert len(candidates) == proof["threshold_cases"] == cases
    assert min(candidates)[0] == proof["hunter_floor"] == floor
    assert list(min(candidates)[1]) == proof["minimizer_edges"]
    assert proof["rank_floor_table"] == ranks
    assert proof["outside_incidences"] == incidences
    assert proof["collision_mass_floor"] == mass
    for high in range(2, n + 1):
        for low in range(high - 1):
            assert (
                comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
                == high - low - 1
                > 0
            )
    for a in range(n):
        for b in range(n):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)


def test_all_65_legal_witnesses_nested_graphs_and_one_extended_tree(result: dict[str, Any]) -> None:
    total = 0
    for region in result["REGIONS"]:
        for row in region["member_certificates"]:
            total += 1
            v = cert.dense(row["counts"])
            witness = row["witness_analysis"]
            support = tuple(tuple(t) for t in witness["support_witness"])
            assert cert.hunter.r8.validate_support_assignment(v, support)
            assert cert.digest(support) == witness["support_sha256"]
            tickets = cast(tuple[frozenset[int], ...], tuple(frozenset(t) for t in support))
            anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
            assert len(set((*anchors, *tickets))) == 20
            assert all(len(a & b) <= 3 for a, b in combinations((*anchors, *tickets), 2))
            core = tuple(tuple(e) for e in witness["core_tree"])
            attachments = tuple(tuple(e) for e in witness["attachment_edges"])
            indices = tuple(int(j) for j in witness["core_indices"])
            tree = cert.validate_tree_extension(indices, core, attachments)
            assert list(map(list, tree)) == witness["extended_tree"]
            assert len(tree) == cert.hunter.graph_rank(18, tree) == 17
            assert not {frozenset(e) for e in core}.intersection(frozenset(e) for e in attachments)
            assert {b for _, b in attachments} == set(range(18)) - set(indices)
            n = row["core_event_count"]
            overlaps = {(a, b): len(tickets[a] & tickets[b]) for a, b in combinations(indices, 2)}
            for k in range(1, 4):
                graph = [e for e, w in overlaps.items() if w >= k]
                assert sum(overlaps[e] >= k for e in core) == cert.hunter.graph_rank(18, graph)
            costs = witness["edge_costs"]
            assert sum(costs[: n - 1]) == witness["core_exact_weight"] >= row["core_floor"]
            assert min(costs[n - 1 :]) >= 105560
            assert sum(costs) == witness["extended_exact_weight"] >= row["tree_floor"]
            assert row["tree_floor"] == row["core_floor"] + (18 - n) * 105560
            assert row["tree_floor"] == (5080320 if row["cohort"] == "A7" else 4143440)
    assert total == 65


def test_max_only_credits_and_strongest_untouched_vector_bounds(result: dict[str, Any]) -> None:
    for region in result["REGIONS"]:
        sid = region["state_id"]
        changed = {cert.dense(r["counts"]): r for r in region["member_certificates"]}
        originals = cert.complete_members(sid)
        untouched_members = untouched_vectors = 0
        for old, row in zip(originals, region["complete_region_members"], strict=True):
            vs = cert.ts153.represented_vectors(sid)[old.counts]
            safe: list[int] = []
            for v, vr in zip(vs, row["represented_vector_bounds"], strict=True):
                prior = min(
                    [old.final_bound, *(b for _, b in cert.sealed_vector_bounds().get(v, ()))]
                )
                assert vr["prior_bound"] == prior
                if v in changed:
                    record = changed[v]
                    credits = record["corrections"]
                    unc = record["uncorrected_anchor_bound"]
                    assert (
                        credits["SEALED_MEMBER"]
                        == {"A40": 3767400, "A7": 4915400, "B18": 4018000}[record["cohort"]]
                    )
                    assert record["combined_correction"] == max(credits.values())
                    assert record["vector_new_bound"] == min(prior, unc - max(credits.values()))
                    assert unc - sum(credits.values()) < record["vector_new_bound"]
                    assert vr["final_bound"] == record["vector_new_bound"]
                else:
                    assert vr["final_bound"] == prior
                    untouched_vectors += 1
                assert vr["final_bound"] <= prior
                safe.append(vr["final_bound"])
            assert row["final_bound"] == max(safe)
            if old.counts not in changed:
                untouched_members += 1
                assert row["final_bound"] == old.final_bound
        assert untouched_members == region["preserved_member_count"]
        assert untouched_vectors == region["preserved_vector_count"]
        assert (
            max(r["final_bound"] for r in region["complete_region_members"])
            == region["new_state_bound"]
        )
    assert result["STATE_A_NEW_UB"] == 355112590
    assert result["STATE_B_NEW_UB"] == 355111939
    assert [(r["target_cohort_max"], r["preserved_remainder_max"]) for r in result["REGIONS"]] == [
        (354976356, 355112590),
        (355015626, 355111939),
    ]


def test_three_complete_family_scenarios_derive_max_owner_and_runner_up(
    result: dict[str, Any],
) -> None:
    states, classified, updated, tail = cert.family_inputs()
    final_states = tuple((r["stable_id"], r["bound"]) for r in result["FINAL_STATE_TERMS"])
    final_classified = tuple((r["stable_id"], r["bound"]) for r in result["FINAL_CLASSIFIED_TERMS"])
    assert final_classified == updated
    prior_states, prior_classified = dict(states), dict(classified)
    assert {k for k, b in final_states if b != prior_states[k]} == {cert.STATE_A, cert.STATE_B}
    assert {k for k, b in updated if b != prior_classified[k]} == {cert.r12.r24.AGGREGATE_ID}
    for name, ss, cc, bound in (
        ("ROOT65_ONLY", final_states, classified, 355145504),
        ("R12_ONLY", states, updated, 355142998),
        ("JOINT", final_states, updated, 355121046),
    ):
        terms = (*ss, *cc, (cert.r12.r24.TAIL_ID, tail))
        maximum = max(b for _, b in terms)
        assert len(terms) == len(dict(terms)) == 56574
        assert maximum == result["SCENARIOS"][name]["maximum"] == bound
        assert cert.digest(terms) == result["SCENARIOS"][name]["terms_sha256"]
    assert dict(final_states)["state:s2-14696976-s3-1059324"] == 355121046
    assert dict(final_states)["state:s2-13548976-s3-951748"] == 355116818
    assert result["FINAL_OWNER"] == "state:s2-14696976-s3-1059324"
    assert result["FINAL_RUNNER_UP"] == {
        "bound": 355116818,
        "owner_ids": ["state:s2-13548976-s3-951748"],
    }
    assert result["ROOT_ONLY_FAMILY_GAIN"] == 0
    assert result["STRICT_GAIN_FROM_BASE"] == 24458
    assert result["STRICT_GAIN_VS_R12_DONOR"] == 21952
    assert result["INCUMBENT"] == 313263888
    assert result["REMAINING_GAP"] == 41857158
    assert result["TAIL_BOUND"] == 354039277
    assert result["PREDECESSOR_THRESHOLD_REBUILD_CALLS"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "raw_E_floor",
        "raised_floor",
        "duplicate_edge",
        "wrong_tree",
        "missing_target",
        "sum_credits",
        "compressed_min",
        "missing_classified",
        "missing_state",
        "source_sha",
    ],
)
def test_semantic_result_mutations_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    if mutation in ("raw_E_floor", "raised_floor"):
        bad["ROOT_RESIDUAL_FLOOR"] = 107800 if mutation == "raw_E_floor" else 105561
    elif mutation in ("duplicate_edge", "wrong_tree"):
        witness = bad["REGIONS"][0]["member_certificates"][0]["witness_analysis"]
        if mutation == "duplicate_edge":
            witness["attachment_edges"][0] = witness["core_tree"][0]
        else:
            witness["extended_tree"].pop()
    elif mutation == "missing_target":
        bad["REGIONS"][0]["member_certificates"].pop()
    elif mutation == "sum_credits":
        row = bad["REGIONS"][0]["member_certificates"][0]
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
    elif mutation == "compressed_min":
        row = next(
            r
            for r in bad["REGIONS"][0]["complete_region_members"]
            if r["represented_vector_count"] > 1
        )
        row["final_bound"] -= 1
    elif mutation == "missing_classified":
        bad["FINAL_CLASSIFIED_TERMS"].pop()
    elif mutation == "missing_state":
        bad["FINAL_STATE_TERMS"].pop()
    else:
        bad["SOURCE_AUTHORITY"]["implementation_sha256"][cert.SOURCE_RELATIVE] = "0" * 64
    with pytest.raises(AssertionError, match="deterministic replay/source binding"):
        cert.verify_result(bad)


def test_live_tree_edge_duplicates_and_wrong_vertices_rejected(result: dict[str, Any]) -> None:
    w = result["REGIONS"][0]["member_certificates"][0]["witness_analysis"]
    indices = tuple(w["core_indices"])
    core = tuple(tuple(e) for e in w["core_tree"])
    attachments = tuple(tuple(e) for e in w["attachment_edges"])
    assert len(cert.validate_tree_extension(indices, core, attachments)) == 17
    for wrong in (
        (core[0], *attachments[1:]),
        attachments[:-1],
        ((indices[0], 18), *attachments[1:]),
    ):
        with pytest.raises(AssertionError, match="disjoint 18-event tree"):
            cert.validate_tree_extension(indices, core, wrong)


def test_live_missing_vector_and_sum_credit_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = cert.STATE_A
    member = cert.target_members(sid)[0]
    recovered = dict(cert.ts153.represented_vectors(sid))
    recovered[member.counts] = ()
    original = cert.ts153.represented_vectors
    with monkeypatch.context() as patch:

        def incomplete(s: str) -> dict[cert.CountVector, tuple[cert.CountVector, ...]]:
            return recovered if s == sid else original(s)

        patch.setattr(cert.ts153, "represented_vectors", incomplete)
        with pytest.raises(AssertionError, match="target member/vector identities"):
            cert.target_members(sid)
    with monkeypatch.context() as patch:

        def summed(credits: Mapping[str, int]) -> int:
            return sum(credits.values())

        patch.setattr(cert.hunter, "combine_corrections", summed)
        with pytest.raises(AssertionError, match="MAX-only"):
            cert.certify_vector(sid, member, member.counts)
    assert cert.certify_vector(sid, member, member.counts)["vector_new_bound"] < member.final_bound


def test_non_equivalent_compressed_max_source_mutant(result: dict[str, Any]) -> None:
    region = result["REGIONS"][0]
    row = next(r for r in region["complete_region_members"] if r["represented_vector_count"] > 1)
    # Real recovered aliases; loosening one legal upper bound remains safe and
    # makes MAX->MIN observable even if the sealed bounds originally tie.
    actual = tuple(int(r["final_bound"]) for r in row["represented_vector_bounds"])
    safe = (actual[0], max(actual) + 1, *actual[2:])
    expected = max(safe)
    assert len(safe) == row["represented_vector_count"] and min(safe) < expected
    assert cert.compressed_bound(safe) == expected
    source = inspect.getsource(cert.compressed_bound)
    assert source.count("return max(bounds)") == 1
    namespace = dict(vars(cert))
    exec(
        compile(
            source.replace("return max(bounds)", "return min(bounds)"),
            "<compressed-MIN-mutant>",
            "exec",
        ),
        namespace,
    )
    mutant = cast(Callable[[tuple[int, ...]], int], namespace["compressed_bound"])
    with pytest.raises(AssertionError):
        assert mutant(safe) == expected
    assert cert.compressed_bound(safe) == expected


@pytest.mark.parametrize("relative", [*cert.DONOR_BLOBS, cert.SOURCE_RELATIVE, cert.TEST_RELATIVE])
def test_live_blob_or_implementation_tampering_after_warm_caches(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    original = Path.read_bytes
    target = cert.REPO_ROOT / relative

    def tampered(path: Path) -> bytes:
        data = original(path)
        return data + b"\n" if path == target else data

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", tampered)
        with pytest.raises(AssertionError, match=r"byte identity|source binding"):
            cert.verify_result(result)
    assert cert.verify_result(result)["status"] == "PASS"


@pytest.mark.parametrize(
    "name",
    [
        "test_immutable_authority_complete_regions_and_target_digests",
        "test_max_once_credits_preserved_and_compressed_max",
        "test_untouched_remainder_family_and_witness_soundness",
    ],
)
def test_relevant_ts153_checks_against_immutable_result_without_threshold_rebuild(
    name: str,
) -> None:
    path = cert.REPO_ROOT / "tests/unit/test_b649_k20_r3_ts153_four_state_wall_adoption_r2.py"
    namespace = runpy.run_path(str(path))
    check = cast(Callable[[dict[str, Any]], None], namespace[name])
    check(cert.base_result())


def test_stored_result_byte_replay_and_source_sha(result: dict[str, Any]) -> None:
    stored = cert.RESULT_PATH.read_bytes()
    assert stored == cert.encode(result).encode()
    assert json.loads(stored) == result
    for relative, expected in result["SOURCE_AUTHORITY"]["implementation_sha256"].items():
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == expected
    assert cert.verify_stored_result()["status"] == "PASS"
