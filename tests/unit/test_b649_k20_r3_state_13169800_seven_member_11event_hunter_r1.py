"""Exact seven-member coverage, Hunter proof and complete immutable R3 replay."""

from __future__ import annotations

import copy
from dataclasses import replace
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_state_13169800_seven_member_11event_hunter_r1 as cert

hunter = cert.hunter
PHI = (107_800, 574_000, 1_691_620, 3_451_651)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def vectors_of(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for m in result["MEMBER_CERTIFICATES"] for r in m["vector_certificates"]]


def test_exact_seven_member_and_vector_coverage(result: dict[str, Any]) -> None:
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    members = cert.region_members()
    assert len(members) == result["REGION_COMPRESSED_MEMBER_COUNT"] == 989
    assert sum(m.represented_vector_count for m in members) == 1072
    assert result["SEVEN_MEMBER_COVERAGE"] == [7, 7]
    expected = {
        hunter.member_id(hunter.dense([[i, n] for i, n in counts if n]))
        for a in range(7)
        for counts in [[(0, 11), (1, a), (4, 6 - a), (20, 1)]]
    }
    rows = result["MEMBER_CERTIFICATES"]
    assert len(rows) == len({r["member_id"] for r in rows}) == 7
    assert {r["member_id"] for r in rows} == expected
    assert len(vectors_of(result)) == 7
    assert {r["vector_id"] for r in vectors_of(result)} == expected
    recovered = cert.catalog.r17.represented_vectors(
        tuple(cert.catalog.rebuild_member(m) for m in cert.seven_members(members))
    )
    for row in rows:
        assert row["represented_vector_count"] == 1
        assert (
            tuple(hunter.dense(v) for v in row["represented_vectors"])
            == recovered[hunter.dense(row["witness_counts"])]
        )
    with pytest.raises(AssertionError, match="coverage"):
        cert.seven_members(
            tuple(m for m in members if m.counts != cert.seven_members(members)[0].counts)
        )


def test_eleven_event_identity_and_exact_pairs(result: dict[str, Any]) -> None:
    proof = result["ELEVEN_EVENT_PROOF"]
    assert proof["type_cells"] == [0, 0, 0, 6]
    assert proof["pair_floors"] == list(PHI)
    rows = hunter.exact_pair_rows(((0, 0),))
    assert len(rows) == 4 and proof["pair_rows"] == [list(r) for r in rows]
    for overlap, cost in enumerate(PHI):
        assert (
            hunter.outcome_count(
                hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), (0, 0, 0, overlap)),
                (hunter.ANCHOR_A, hunter.ANCHOR_B),
            )
            == cost
        )
        assert hunter.six.residual_pair_intersection(0, 0, (0, 0, 0, overlap)) == cost
    for row in vectors_of(result):
        counts = hunter.dense(row["counts"])
        assert counts[0] == proof["event_count"] == 11
        assert sum(counts) == 18
        assert row["eleven_event_indices"] == list(range(11))
        assert row["eleven_event_types"] == [0] * 11
        assert row["outside_incidences"] == 66
        assert row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
        assert row["residual_event_sum"] == sum(
            n * hunter.residual_event_size(i) for i, n in enumerate(counts) if n
        )
    assert proof["residual_event_size"] == hunter.residual_event_size(0)


def test_collision_mass_and_threshold_cases(result: dict[str, Any]) -> None:
    proof = result["ELEVEN_EVENT_PROOF"]
    assert proof["outside_incidences"] == 66 and proof["outside_label_count"] == 40
    assert proof["balanced_frequencies"] == [[1, 14], [2, 26]]
    frequencies = [1] * 14 + [2] * 26
    assert sum(frequencies) == 66
    assert sum(comb(d, 2) for d in frequencies) == proof["collision_mass_floor"] == 26
    # Every frequency d has C(d,2) >= d-1; summing gives Q >= 66-40.
    assert all(comb(d, 2) >= d - 1 for d in range(12))
    cases = cert.prior.threshold_cases(PHI, 26, 11)
    assert cases == proof["threshold_cases"]
    assert [r["e1_lower_bound"] for r in cases] == [26, 13, 9]
    assert [r["rank_lower_bounds"] for r in cases] == [[7, 0, 0], [5, 1, 0], [4, 1, 1]]
    assert [r["hunter_floor"] for r in cases] == [4_341_400, 4_526_620, 5_820_451]
    for e1 in range(comb(11, 2) + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 26:
                    continue
                case = cases[2 if e3 else 1 if e2 else 0]
                ranks = tuple(hunter.rank_floor(e) for e in (e1, e2, e3))
                assert all(
                    r >= floor for r, floor in zip(ranks, case["rank_lower_bounds"], strict=True)
                )
                assert hunter.tree_weight_floor(PHI, ranks, 11) >= case["hunter_floor"]


def test_hunter_rank_inequality_and_independent_dual(result: dict[str, Any]) -> None:
    # For components of ranks a,b, merging adds ab to maximum edge capacity.
    for a in range(11):
        for b in range(11 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    for e in range(comb(11, 2) + 1):
        rank = hunter.rank_floor(e)
        assert comb(rank + 1, 2) >= e
        assert rank == 0 or comb(rank, 2) < e
    assert hunter.verify_rank_floor_exhaustively(5) == 1024
    assert hunter.verify_threshold_tree_lemma(4) == 4096
    assert hunter.verify_hunter_exhaustively(3, 3) == 1536
    # Independent relaxation over ranks, not the production edge-count triples.
    feasible = [
        10 * PHI[0] + sum((PHI[k] - PHI[k - 1]) * ranks[k - 1] for k in range(1, 4))
        for r1 in range(11)
        for r2 in range(r1 + 1)
        for r3 in range(r2 + 1)
        for ranks in [(r1, r2, r3)]
        if sum(comb(r + 1, 2) for r in ranks) >= 26
    ]
    assert min(feasible) == result["HUNTER_FLOOR"] == 4_341_400
    tree = hunter.minimum_tree_correction(PHI, 26, 11)
    assert tree.correction == 10 * PHI[0] + 7 * (PHI[1] - PHI[0])
    assert tree.edge_counts == (26, 0, 0) and tree.rank_floors == (7, 0, 0)
    assert (
        tree.census_size
        == result["ELEVEN_EVENT_PROOF"]["integer_minimizer"]["feasible_threshold_triples"]
        == 30_216
    )


def test_max_single_replacement(result: dict[str, Any]) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            corrections = row["corrections"]
            assert row["combined_correction"] == max(corrections.values()) == 4_341_400
            assert row["combined_correction"] != sum(corrections.values())
            assert (
                row["prior_applied_correction"]
                == max(corrections["R6_PAIR"], corrections["FOREST"])
                == 4_018_000
            )
            assert corrections["EXISTING_R14"] == 0
            assert row["vector_new_bound"] == row["uncorrected_anchor_bound"] - max(
                corrections.values()
            )
            assert (
                member["member_prior_bound"]
                == row["uncorrected_anchor_bound"] - row["prior_applied_correction"]
            )
        assert member["member_new_bound"] == max(
            r["vector_new_bound"] for r in member["vector_certificates"]
        )
        assert member["member_certified_correction"] == min(
            r["combined_correction"] for r in member["vector_certificates"]
        )
    assert result["NEW_SEVEN_MEMBER_MAX"] == 355_305_069
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_witness_validity_and_full_tree_extension(result: dict[str, Any]) -> None:
    for row in vectors_of(result):
        counts = hunter.dense(row["counts"])
        support = tuple(tuple(t) for t in row["support_witness"])
        assert hunter.r8.validate_support_assignment(counts, support)
        assert hunter.digest(support) == row["support_sha256"]
        subset = tuple(frozenset(t) for t in support[:11])
        assert all(t <= set(hunter.CELL_LABELS[3]) for t in subset)
        label_mass = sum(comb(sum(x in t for t in subset), 2) for x in hunter.CELL_LABELS[3])
        pair_mass = sum(len(a & b) for a, b in combinations(subset, 2))
        witness = row["witness_analysis"]
        assert label_mass == pair_mass == witness["collision_mass"] >= 26
        assert witness["exact_tree_weight"] >= witness["phi_tree_weight"] >= result["HUNTER_FLOOR"]
        assert len(witness["subset_tree"]) == 10
        assert (
            len(witness["extended_tree"]) == hunter.graph_rank(18, witness["extended_tree"]) == 17
        )
        types = tuple(i for i, n in enumerate(counts) for _ in range(n))
        full_weight = 0
        for left, right in witness["extended_tree"]:
            left_index, right_index = int(left), int(right)
            cells = tuple(
                len(set(support[left_index]) & set(support[right_index]) & set(labels))
                for labels in hunter.CELL_LABELS
            )
            value = hunter.six.residual_pair_intersection(
                types[left_index], types[right_index], (cells[0], cells[1], cells[2], cells[3])
            )
            assert value >= 0
            full_weight += value
        assert full_weight >= witness["phi_tree_weight"]


def test_complete_preserved_remainder(result: dict[str, Any]) -> None:
    stored = cert.catalog.r24_authority()
    region = next(
        r for r in stored["STATE_REGION_CERTIFICATES"] if r["owner_id"] == cert.TARGET_STATE_ID
    )
    old = {
        hunter.member_id(hunter.dense(r["witness_counts"])): r
        for r in region["complete_region_members"]
    }
    targets = {r["member_id"] for r in result["MEMBER_CERTIFICATES"]}
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert len(rows) == len({r["member_id"] for r in rows}) == 989
    remainder = [r for r in rows if r["member_id"] not in targets]
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 982
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 1065
    )
    for row in rows:
        original = old[row["member_id"]]
        assert row["prior_bound"] == original["final_bound"]
        assert row["raw_bound"] == original["raw_bound"]
        assert row["represented_vector_count"] == original["represented_vector_count"]
        assert cert.catalog.rebuild_member(
            cert.catalog.LedgerMember(
                hunter.dense(row["witness_counts"]),
                row["represented_vector_count"],
                row["raw_bound"],
                row["prior_bound"],
            )
        ).witness_counts == hunter.dense(row["witness_counts"])
        if row["member_id"] not in targets:
            assert row["final_bound"] == row["prior_bound"]
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355_597_508
    )
    assert max(r["final_bound"] for r in rows) == result["FINAL_STATE_BOUND"] == 355_597_508


def test_complete_23_state_family(result: dict[str, Any]) -> None:
    source = cert.source_authority()
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert {key for key in before if before[key] != after[key]} == {cert.TARGET_STATE_ID}
    assert result["START_R3_UB"] == max(before.values()) == 355_628_469
    assert (
        result["FINAL_R3_UB"]
        == max(max(after.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"])
        == 355_597_508
    )
    assert result["FINAL_OWNER_IDS"] == [cert.TARGET_STATE_ID]
    assert (
        result["REMAINING_GAP"] == result["FINAL_R3_UB"] - result["CURRENT_INCUMBENT"] == 42_333_620
    )
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_AGGREGATE", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == source[key]
    assert result["START_STATE_TERMS"] == source["FINAL_STATE_TERMS"]
    family = cert.recompute_family(result["FINAL_STATE_BOUND"])
    assert family["start"] == result["START_FAMILY_MAX_RECOMPUTATION"]
    assert family["final"] == result["FINAL_FAMILY_MAX_RECOMPUTATION"]


def test_compressed_vector_completeness(result: dict[str, Any]) -> None:
    member = cert.seven_members(cert.region_members())[0]
    proof = cert.eleven_event_proof()
    for vectors in ((), (member.counts, member.counts)):
        with pytest.raises(AssertionError, match="represented vectors"):
            cert.certify_member(member, vectors, proof)
    wrong = hunter.dense([[0, 10], [4, 7], [20, 1]])
    with pytest.raises(AssertionError):
        cert.certify_vector(member, wrong, proof)
    with pytest.raises(AssertionError, match="coverage"):
        members = cert.region_members()
        cert.seven_members(
            tuple(replace(m, represented_vector_count=2) if m == member else m for m in members)
        )


def test_stored_result_and_replay(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_text() == hunter.encode(result)
    assert cert.verify_result(result) == {"status": "PASS", "certificates": 7, "vectors": 7}


@pytest.mark.parametrize(
    "mutation",
    [
        "pair",
        "floor",
        "rank",
        "mass",
        "event",
        "missing_member",
        "duplicate_member",
        "vector",
        "max_sum",
        "witness",
        "digest",
        "remainder",
        "family",
        "owner",
        "tail",
        "aggregate",
    ],
)
def test_tampered_certificate_rejection(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof = bad["ELEVEN_EVENT_PROOF"]
    member = bad["MEMBER_CERTIFICATES"][0]
    vector = member["vector_certificates"][0]
    if mutation == "pair":
        proof["pair_rows"][0][6] += 1
    elif mutation == "floor":
        proof["hunter_floor"] += 1
    elif mutation == "rank":
        proof["threshold_cases"][0]["rank_lower_bounds"][0] -= 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "event":
        vector["eleven_event_types"][0] = 1
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "vector":
        member["represented_vectors"].pop()
    elif mutation == "max_sum":
        vector["combined_correction"] = sum(vector["corrections"].values())
    elif mutation == "witness":
        vector["support_witness"][0][0] = 99
    elif mutation == "digest":
        vector["support_sha256"] = "0" * 64
    elif mutation == "remainder":
        targets = {r["member_id"] for r in bad["MEMBER_CERTIFICATES"]}
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["member_id"] not in targets)[
            "final_bound"
        ] -= 1
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [hunter.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    else:
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    with pytest.raises(AssertionError, match=r"witness|replay"):
        cert.verify_result(bad)


@pytest.mark.parametrize("relative", sorted(cert.UPSTREAM_SHA256))
def test_all_immutable_source_tampering_rejected(
    relative: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = Path.read_bytes

    def tamper(path: Path) -> bytes:
        data = read(path)
        return data + b"\n" if path == cert.REPO_ROOT / relative else data

    # The build must recheck fingerprints even with all authority caches warm.
    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(AssertionError, match="fingerprint"):
        cert.build_result()


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver or official outcome enumeration")


def test_no_solver_or_full_census(result: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hunter.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(hunter.r14, "owner_region", forbidden)
    monkeypatch.setattr(hunter.r14, "s4_child", forbidden)
    monkeypatch.setattr(hunter.r8, "support_model_status", forbidden)
    monkeypatch.setattr(hunter.r8, "solver_runtime_preflight", forbidden)
    monkeypatch.setattr(cert.r24, "run_chase", forbidden)
    cert.source_authority.cache_clear()
    cert.region_members.cache_clear()
    cert.eleven_event_proof.cache_clear()
    assert cert.build_result() == result
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"
