"""Universal applicability, independent Hunter algebra and complete family replay."""

from __future__ import annotations

import copy
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_type0_ge9_shared_hunter_family_r1 as cert

hunter = cert.hunter
PHI = (107_800, 574_000, 1_691_620, 3_451_651)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def vectors_of(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [v for m in result["MEMBER_CERTIFICATES"] for v in m["vector_certificates"]]


def test_complete_region_and_per_vector_applicability(result: dict[str, Any]) -> None:
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    members = cert.region_members()
    recovered = cert.region_vectors()
    rows = result["MEMBER_CERTIFICATES"]
    assert len(rows) == len({m["member_id"] for m in rows}) == len(members) == 989
    assert result["REGION_SHA256"] == cert.REGION_SHA256 == cert.catalog.region_fingerprint(members)
    assert sum(m.represented_vector_count for m in members) == 1072
    assert len(vectors_of(result)) == len({v["vector_id"] for v in vectors_of(result)}) == 1072
    for member, row in zip(members, rows, strict=True):
        vectors = tuple(hunter.dense(v["counts"]) for v in row["vector_certificates"])
        assert vectors == recovered[member.counts]
        assert len(vectors) == row["represented_vector_count"] == member.represented_vector_count
        assert min(vectors) == hunter.dense(row["witness_counts"]) == member.counts
        for vector, record in zip(vectors, row["vector_certificates"], strict=True):
            assert record["type0_count"] == vector[0]
            assert record["eligible"] == (vector[0] >= 9)
            assert record["pair_overlap_ceiling"] == hunter.family_pair_overlap_ceiling() == 3
            assert sum(vector) == 18
            assert record["uncorrected_anchor_bound"] == (
                record["anchor_union"] + record["residual_event_sum"]
            )
            assert record["residual_event_sum"] == sum(
                n * hunter.residual_event_size(i) for i, n in enumerate(vector)
            )
            if record["eligible"]:
                assert record["nine_event_indices"] == list(range(9))
                assert record["nine_event_types"] == [0] * 9
                assert record["outside_incidences"] == 54
                assert record["collision_mass_floor"] == 14
            else:
                assert record["nine_event_indices"] == record["nine_event_types"] == []
                assert record["corrections"]["NINE_EVENT_HUNTER"] == 0
                assert record["vector_new_bound"] == record["vector_prior_bound"]
        assert row["eligible"] == all(v[0] >= 9 for v in vectors)
    assert sum(r["eligible"] for r in rows) == result["ELIGIBLE_MEMBER_COUNT"] == 908
    assert sum(v["eligible"] for v in vectors_of(result)) == result["ELIGIBLE_VECTOR_COUNT"] == 988


def test_exact_pair_costs_and_residual_event_definition(result: dict[str, Any]) -> None:
    proof = result["NINE_EVENT_PROOF"]
    assert proof["residual_event_definition"] == hunter.RESIDUAL_EVENT_DEFINITION
    assert proof["type_cells"] == [0, 0, 0, 6]
    assert proof["pair_floors"] == list(PHI)
    assert len(proof["pair_rows"]) == 4
    for overlap, value in enumerate(PHI):
        tickets = hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), (0, 0, 0, overlap))
        assert hunter.outcome_count(tickets, (hunter.ANCHOR_A, hunter.ANCHOR_B)) == value
        assert hunter.six.residual_pair_intersection(0, 0, (0, 0, 0, overlap)) == value
        assert proof["pair_rows"][overlap] == [0, 0, 0, 0, 0, overlap, value]
    assert proof["residual_event_size"] == hunter.residual_event_size(0) == 18_405_317


def test_universal_nine_event_collision_and_all_threshold_cases(result: dict[str, Any]) -> None:
    proof = result["NINE_EVENT_PROOF"]
    assert proof["outside_incidences"] == 9 * 6 == 54
    assert proof["outside_label_count"] == 40
    assert proof["balanced_frequencies"] == [[1, 26], [2, 14]]
    assert sum(comb(d, 2) for d in [1] * 26 + [2] * 14) == 54 - 40 == 14
    assert all(comb(d, 2) >= d - 1 for d in range(10))
    cases = proof["threshold_cases"]
    assert [r["e1_lower_bound"] for r in cases] == [14, 7, 5]
    assert [r["rank_lower_bounds"] for r in cases] == [[5, 0, 0], [4, 1, 0], [3, 1, 1]]
    assert [r["hunter_floor"] for r in cases] == [3_193_400, 3_844_820, 5_138_651]
    count = 0
    for e1 in range(comb(9, 2) + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 14:
                    continue
                ranks = tuple(min(r for r in range(9) if comb(r + 1, 2) >= e) for e in (e1, e2, e3))
                case = cases[2 if e3 else 1 if e2 else 0]
                assert all(
                    r >= low for r, low in zip(ranks, case["rank_lower_bounds"], strict=True)
                )
                value = 8 * PHI[0] + sum((PHI[k] - PHI[k - 1]) * ranks[k - 1] for k in range(1, 4))
                assert value >= case["hunter_floor"] >= proof["hunter_floor"]
                count += 1
    assert count == proof["integer_minimizer"]["feasible_threshold_triples"] == 9016
    assert proof["integer_minimizer"]["edge_counts"] == [14, 0, 0]
    assert proof["floor_algebra"] == [862_400, 5, 466_200, 3_193_400]
    assert result["CORRECTION_FLOOR"] == 8 * PHI[0] + 5 * (PHI[1] - PHI[0]) == 3_193_400


def test_hunter_forest_rank_and_independent_rank_dual(result: dict[str, Any]) -> None:
    for a in range(9):
        for b in range(9 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    for e in range(comb(9, 2) + 1):
        rank = hunter.rank_floor(e)
        assert comb(rank + 1, 2) >= e
        assert rank == 0 or comb(rank, 2) < e
    assert hunter.verify_rank_floor_exhaustively(5) == 1024
    assert hunter.verify_threshold_tree_lemma(4) == 4096
    assert hunter.verify_hunter_exhaustively(3, 3) == 1536
    # Independent minimization over ranks, rather than the counter's edge triples.
    feasible = [
        8 * PHI[0] + sum((PHI[k] - PHI[k - 1]) * ranks[k - 1] for k in range(1, 4))
        for r1 in range(9)
        for r2 in range(r1 + 1)
        for r3 in range(r2 + 1)
        for ranks in [(r1, r2, r3)]
        if sum(comb(r + 1, 2) for r in ranks) >= 14
    ]
    assert min(feasible) == result["CORRECTION_FLOOR"]


def test_all_eligible_witnesses_validate_mass_ceiling_and_tree_extension(
    result: dict[str, Any],
) -> None:
    for row in vectors_of(result):
        if not row["eligible"]:
            continue
        counts = hunter.dense(row["counts"])
        support = tuple(tuple(t) for t in row["support_witness"])
        assert hunter.r8.validate_support_assignment(counts, support)
        assert hunter.digest(support) == row["support_sha256"]
        subset = tuple(frozenset(t) for t in support[:9])
        assert all(t <= set(hunter.CELL_LABELS[3]) and len(t) == 6 for t in subset)
        overlaps = {(a, b): len(subset[a] & subset[b]) for a, b in combinations(range(9), 2)}
        assert max(overlaps.values()) <= 3
        mass = sum(comb(sum(x in t for t in subset), 2) for x in hunter.CELL_LABELS[3])
        witness = row["witness_analysis"]
        assert mass == sum(overlaps.values()) == witness["collision_mass"] >= 14
        for k in range(1, 4):
            edges = [e for e, overlap in overlaps.items() if overlap >= k]
            assert hunter.graph_rank(9, edges) >= hunter.rank_floor(len(edges))
        assert witness["exact_tree_weight"] >= witness["phi_tree_weight"] >= 3_193_400
        assert len(witness["subset_tree"]) == hunter.graph_rank(9, witness["subset_tree"]) == 8
        assert (
            len(witness["extended_tree"]) == hunter.graph_rank(18, witness["extended_tree"]) == 17
        )
        assert (
            sum(PHI[overlaps[tuple(e)]] for e in witness["subset_tree"])
            == witness["phi_tree_weight"]
        )


def test_max_not_sum_and_all_compressed_members(result: dict[str, Any]) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        records = member["vector_certificates"]
        for row in records:
            corrections = row["corrections"]
            assert row["combined_correction"] == max(corrections.values())
            assert row["combined_correction"] != sum(corrections.values())
            assert row["prior_applied_correction"] == max(
                v for k, v in corrections.items() if k != "NINE_EVENT_HUNTER"
            )
            assert row["vector_prior_bound"] == member["member_prior_bound"]
            assert (
                row["vector_prior_bound"]
                == row["uncorrected_anchor_bound"] - row["prior_applied_correction"]
            )
            assert (
                row["vector_new_bound"]
                == row["uncorrected_anchor_bound"] - row["combined_correction"]
            )
        assert member["member_certified_correction"] == min(
            r["combined_correction"] for r in records
        )
        assert member["member_new_bound"] == max(r["vector_new_bound"] for r in records)
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_compressed_member_rejects_missing_duplicate_and_foreign_vectors(
    result: dict[str, Any],
) -> None:
    member = next(m for m in cert.region_members() if m.represented_vector_count > 1)
    vectors = cert.region_vectors()[member.counts]
    bound = next(
        r["member_prior_bound"]
        for r in result["MEMBER_CERTIFICATES"]
        if r["member_id"] == hunter.member_id(member.counts)
    )
    proof = cert.nine_event_proof()
    for bad in (vectors[:-1], (vectors[0],) * len(vectors), tuple(reversed(vectors))):
        with pytest.raises(AssertionError, match="all exact represented vectors"):
            cert.certify_member(member, bad, bound, proof)
    foreign = next(v for rows in cert.region_vectors().values() for v in rows if v not in vectors)
    with pytest.raises(AssertionError):
        cert.certify_vector(member, foreign, bound, proof)


def test_compressed_member_uses_weakest_ineligible_vector(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    member = next(m for m in cert.region_members() if m.represented_vector_count > 1)
    vectors = cert.region_vectors()[member.counts]
    row = next(
        r
        for r in result["MEMBER_CERTIFICATES"]
        if r["member_id"] == hunter.member_id(member.counts)
    )
    uncorrected = row["vector_certificates"][0]["uncorrected_anchor_bound"]
    bound = row["member_prior_bound"]

    def unequal(
        _m: cert.LedgerMember, vector: cert.CountVector, _b: int, _p: dict[str, Any]
    ) -> dict[str, Any]:
        eligible = vector != vectors[0]
        credit = uncorrected - bound + (100 if eligible else 0)
        return {
            "combined_correction": credit,
            "vector_new_bound": uncorrected - credit,
            "uncorrected_anchor_bound": uncorrected,
            "eligible": eligible,
        }

    monkeypatch.setattr(cert, "certify_vector", unequal)
    certificate = cert.certify_member(member, vectors, bound, cert.nine_event_proof())
    assert certificate["member_new_bound"] == bound
    assert certificate["member_certified_correction"] == uncorrected - bound
    assert certificate["eligible"] is False


def test_preserved_seven_and_945_unchanged_members(result: dict[str, Any]) -> None:
    authority = cert.source_authority()
    before = {r["member_id"]: r for r in authority["COMPLETE_REGION_MEMBERS"]}
    seven = {r["member_id"]: r for r in authority["MEMBER_CERTIFICATES"]}
    rows = result["MEMBER_CERTIFICATES"]
    assert len(seven) == result["PRESERVED_SEVEN_MEMBER_COUNT"] == 7
    assert result["PRESERVED_SEVEN_CERTIFICATES_SHA256"] == hunter.digest(
        authority["MEMBER_CERTIFICATES"]
    )
    assert result["PRESERVED_SEVEN_CORRECTION_FLOOR"] == 4_341_400
    for row in rows:
        old = before[row["member_id"]]
        assert row["member_prior_bound"] == old["final_bound"]
        assert row["member_raw_bound"] == old["raw_bound"]
        assert row["represented_vector_count"] == old["represented_vector_count"]
        if row["member_id"] in seven:
            assert row["member_new_bound"] == seven[row["member_id"]]["member_new_bound"]
            for vector in row["vector_certificates"]:
                assert vector["corrections"]["EXISTING_HUNTER"] == 4_341_400
                assert vector["combined_correction"] >= 4_341_400 > 3_193_400
    assert sum(r["improved"] for r in rows) == result["CHANGED_MEMBER_COUNT"] == 44
    assert sum(v["improved"] for v in vectors_of(result)) == result["CHANGED_VECTOR_COUNT"] == 48
    assert sum(not r["improved"] for r in rows) == result["UNCHANGED_MEMBER_COUNT"] == 945
    assert (
        sum(not v["improved"] for v in vectors_of(result))
        == result["UNCHANGED_VECTOR_COUNT"]
        == 1024
    )
    for row in rows:
        if not row["improved"]:
            assert row["member_new_bound"] == row["member_prior_bound"]
    assert max(r["member_new_bound"] for r in rows) == result["FINAL_STATE_BOUND"] == 355_499_536


def test_full_23_state_family_and_sealed_tail_aggregate(result: dict[str, Any]) -> None:
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_COMPLETE_R3_UB"] == 355_597_508
    assert after[cert.TARGET_STATE_ID] == 355_499_536
    assert result["NEXT_COMPETING_STATE"] == {
        "stable_id": "state:s2-13548976-s3-951748",
        "bound": 355_595_786,
    }
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    assert (
        result["FINAL_COMPLETE_R3_UB"]
        == max(max(after.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"])
        == 355_595_786
    )
    assert (
        result["REMAINING_GAP"]
        == result["FINAL_COMPLETE_R3_UB"] - result["CURRENT_INCUMBENT"]
        == 42_331_898
    )
    source = cert.source_authority()
    for key in ("TAIL_BOUND", "CLASSIFIED_AGGREGATE", "CLASSIFIED_MAX", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == source[key]
    assert result["START_STATE_TERMS"] == source["FINAL_STATE_TERMS"]
    replay = cert.recompute_family(result["FINAL_STATE_BOUND"])
    assert replay["final"] == result["FINAL_FAMILY_MAX_RECOMPUTATION"]
    assert result["FULL_23_STATE_RECOMPUTATION"] == "PASS"


def test_stored_result_exact_replay(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_text() == hunter.encode(result)
    assert cert.verify_result(result) == {"status": "PASS", "members": 989, "vectors": 1072}


@pytest.mark.parametrize(
    "mutation",
    [
        "pair",
        "floor",
        "rank",
        "mass",
        "eligibility",
        "selection",
        "ceiling",
        "missing_member",
        "duplicate_member",
        "vector",
        "max_sum",
        "stronger_seven",
        "witness",
        "digest",
        "unchanged",
        "family",
        "owner",
        "tail",
        "aggregate",
    ],
)
def test_certificate_tamper_rejection(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof = bad["NINE_EVENT_PROOF"]
    member = next(m for m in bad["MEMBER_CERTIFICATES"] if m["eligible"])
    vector = member["vector_certificates"][0]
    if mutation == "pair":
        proof["pair_rows"][0][6] += 1
    elif mutation == "floor":
        proof["hunter_floor"] += 1
    elif mutation == "rank":
        proof["threshold_cases"][0]["rank_lower_bounds"][0] -= 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "eligibility":
        vector["eligible"] = False
    elif mutation == "selection":
        vector["nine_event_types"][0] = 1
    elif mutation == "ceiling":
        vector["pair_overlap_ceiling"] = 4
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "vector":
        next(m for m in bad["MEMBER_CERTIFICATES"] if m["represented_vector_count"] > 1)[
            "vector_certificates"
        ].pop()
    elif mutation == "max_sum":
        vector["combined_correction"] = sum(vector["corrections"].values())
    elif mutation == "stronger_seven":
        next(v for v in vectors_of(bad) if v["corrections"]["EXISTING_HUNTER"])["corrections"][
            "EXISTING_HUNTER"
        ] = 3_193_400
    elif mutation == "witness":
        vector["support_witness"][0][0] = 99
    elif mutation == "digest":
        vector["support_sha256"] = "0" * 64
    elif mutation == "unchanged":
        next(m for m in bad["MEMBER_CERTIFICATES"] if not m["improved"])["member_new_bound"] -= 1
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [cert.TARGET_STATE_ID]
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

    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(AssertionError, match="fingerprint"):
        cert.build_result()


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver or official outcome enumeration")


def test_no_solver_or_census_with_cold_authority_caches(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hunter.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(hunter.r14, "owner_region", forbidden)
    monkeypatch.setattr(hunter.r14, "s4_child", forbidden)
    monkeypatch.setattr(hunter.r8, "support_model_status", forbidden)
    monkeypatch.setattr(hunter.r8, "solver_runtime_preflight", forbidden)
    monkeypatch.setattr(cert.r24, "run_chase", forbidden)
    cert.source_authority.cache_clear()
    cert.region_members.cache_clear()
    cert.region_vectors.cache_clear()
    cert.prior.source_authority.cache_clear()
    cert.prior.region_members.cache_clear()
    assert cert.build_result() == result
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"
