"""Independent Hunter arithmetic, complete compression coverage and semantic faults."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_state_12692531_top_band_eleven_event_hunter_r1 as cert

PHI = (107800, 574000, 1691620, 3451651)
TARGET_IDS = (
    "[0,11][4,2][5,4][8,1]",
    "[0,11][2,1][4,2][5,4]",
    "[0,11][1,1][4,1][5,4][8,1]",
    "[0,11][1,1][2,1][4,1][5,4]",
    "[0,11][1,2][2,1][5,4]",
)


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, predecessor rebuild, solver or owner chase")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cert.prior, "build_result", forbidden)
        patch.setattr(cert.prior.h0, "build_result", forbidden)
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        return cert.build_result()


def test_exact_authority_and_top_five(result: dict[str, Any]) -> None:
    assert result["BASE_HEAD"] == "e464631565f83e44b1ff6cbeeb1e9af64880939d"
    assert result["BASE_TREE"] == "25174405e76eb4350eb045a0c02c4f04901b776e"
    assert sha256(cert.prior.RESULT_PATH.read_bytes()).hexdigest() == (
        "40cdc624da9eef931f122cce03f28d326ec6a8a931c3039e8b0235dffef4818a"
    )
    assert result["SOURCE_AUTHORITY"] == cert.verify_source_authority()
    assert result["REGION_SHA256"] == (
        "132cef5c91f5d6cf4798c8d8f65dba98d3851f33ec3d45b5d37fb7f61145ef15"
    )
    assert [r["member_id"] for r in result["MEMBER_CERTIFICATES"]] == list(TARGET_IDS)
    assert (result["TARGET_MEMBER_COUNT"], result["TARGET_VECTOR_COUNT"]) == (5, 6)
    members = cert.region_members()
    targets = cert.target_members(members)
    assert {m.counts for m in members if m.final_bound == max(x.final_bound for x in members)} == {
        m.counts for m in targets
    }
    for bad in (
        tuple(m for m in members if m != targets[0]),
        tuple(replace(m, represented_vector_count=1) if m == targets[1] else m for m in members),
    ):
        with pytest.raises(AssertionError, match="five highest"):
            cert.target_members(bad)


def test_all_582_members_and_633_compression_signatures(result: dict[str, Any]) -> None:
    members, vectors = cert.region_members(), cert.represented_vectors()
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert len(members) == len(vectors) == len(rows) == 582
    flat = [v for vs in vectors.values() for v in vs]
    assert len(flat) == len(set(flat)) == result["REGION_REPRESENTED_VECTOR_COUNT"] == 633
    for member, row in zip(members, rows, strict=True):
        signature = cert.hunter.eleven.compression_signature(cert.catalog.rebuild_member(member))
        assert row["represented_vectors"] == [cert.sparse(v) for v in vectors[member.counts]]
        assert len(vectors[member.counts]) == member.represented_vector_count
        for vector in vectors[member.counts]:
            rebuilt = cert.catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            assert cert.hunter.eleven.compression_signature(rebuilt) == signature
            assert cert.hunter.r14.raw_bound(rebuilt) == member.raw_bound
    compressed = result["MEMBER_CERTIFICATES"][1]
    assert compressed["represented_vectors"] == [
        [[0, 11], [2, 1], [4, 2], [5, 4]],
        [[0, 11], [1, 2], [5, 4], [8, 1]],
    ]
    assert [r["vector_id"] for r in compressed["vector_certificates"]] == [
        TARGET_IDS[1],
        "[0,11][1,2][5,4][8,1]",
    ]


def test_exact_pairs_balancing_and_all_threshold_triples(result: dict[str, Any]) -> None:
    proof = result["ELEVEN_EVENT_PROOF"]
    assert proof["event_count"] == 11
    assert proof["type_cells"] == [0, 0, 0, 6]
    assert proof["outside_label_count"] == 40
    assert proof["outside_incidences"] == 66
    assert proof["balanced_frequencies"] == [[1, 14], [2, 26]]
    assert 14 * comb(1, 2) + 26 * comb(2, 2) == proof["collision_mass_floor"] == 26
    # Smoothing any nonbalanced pair decreases Q strictly, proving the minimum.
    for high in range(2, 12):
        for low in range(high - 1):
            decrease = comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
            assert decrease == high - low - 1 > 0
    assert proof["pair_floors"] == list(PHI)
    for overlap, cost in enumerate(PHI):
        cells = (0, 0, 0, overlap)
        assert proof["pair_rows"][overlap] == [0, 0, *cells, cost]
        assert cert.six.residual_pair_intersection(0, 0, cells) == cost
        left, right = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert len(left & right) == overlap
        assert (
            cert.hunter.outcome_count((left, right), (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B))
            == cost
        )
    ranks = [next(r for r in range(11) if comb(r + 1, 2) >= e) for e in range(56)]
    candidates: list[tuple[int, tuple[int, int, int]]] = []
    for e1 in range(56):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= 26:
                    value = 10 * PHI[0] + sum(
                        (PHI[k + 1] - PHI[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                    )
                    candidates.append((value, (e1, e2, e3)))
    assert len(candidates) == proof["all_admissible_threshold_cases"] == 30216
    assert min(candidates) == (4341400, (26, 0, 0))
    assert tuple(ranks[e] for e in (26, 0, 0)) == (7, 0, 0)
    assert proof["integer_minimizer"] == {"edge_counts": [26, 0, 0], "rank_floors": [7, 0, 0]}
    assert proof["hunter_floor"] == result["HUNTER_FLOOR"] == 4341400


def test_universal_rank_kruskal_and_pointwise_hunter() -> None:
    for a in range(11):
        for b in range(11 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_every_vector_max_credit_and_six_legal_supports(result: dict[str, Any]) -> None:
    assert result["TARGET_NEW_BOUNDS"] == [354951520] * 5
    for member in result["MEMBER_CERTIFICATES"]:
        assert member["member_prior_bound"] == member["member_raw_bound"] == 355274920
        assert member["member_new_bound"] == max(
            r["vector_new_bound"] for r in member["vector_certificates"]
        )
        assert member["member_certified_correction"] == min(
            r["combined_correction"] for r in member["vector_certificates"]
        )
        for row in member["vector_certificates"]:
            assert row["type0_count"] == len(row["eleven_event_indices"]) == 11
            assert row["eleven_event_types"] == [0] * 11
            assert row["residual_event_definition"] == "R_i = E_i \\ (E_A \u222a E_B)"
            credits = row["corrections"]
            assert 1822004 <= credits["R6_PAIR"] <= 1824711
            assert credits["EXISTING_R14"] == credits["EXISTING_HUNTER"] == 0
            assert (
                credits["FOREST"]
                == credits["SEALED_VALID"]
                == row["prior_applied_correction"]
                == 4018000
            )
            assert row["uncorrected_anchor_bound"] == 359292920
            assert row["combined_correction"] == max(credits.values()) == 4341400
            assert row["vector_new_bound"] == 359292920 - 4341400 == 354951520
            assert row["combined_correction"] != sum(credits.values())
            vector = cert.dense(row["counts"])
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            assert cert.hunter.r8.validate_support_assignment(vector, support)
            assert support == cert.prior.legal_support(vector)
            assert cert.digest(support) == row["support_sha256"]
            indices = cast(list[int], row["eleven_event_indices"])
            subset = tuple(frozenset(support[i]) for i in indices)
            assert all(len(t) == 6 and t <= set(cert.hunter.CELL_LABELS[3]) for t in subset)
            mass = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
            assert mass == sum(len(a & b) for a, b in combinations(subset, 2)) >= 26
            witness = row["witness_analysis"]
            assert mass == witness["collision_mass"]
            assert witness["extended_tree_exact_weight"] >= witness["phi_tree_weight"] >= 4341400
            assert len(witness["subset_tree"]) == 10
            tree = cast(list[tuple[int, int]], witness["extended_tree"])
            assert len(tree) == cert.hunter.graph_rank(18, tree) == 17
            types = tuple(i for i, count in enumerate(vector) for _ in range(count))
            weight = 0
            for a, b in tree:
                cells = cast(
                    cert.prior.Cells,
                    tuple(
                        len(set(support[a]) & set(support[b]) & set(c))
                        for c in cert.hunter.CELL_LABELS
                    ),
                )
                cost = cert.six.residual_pair_intersection(*sorted((types[a], types[b])), cells)
                assert cost >= 0
                weight += cost
            assert weight == witness["extended_tree_exact_weight"]


def test_all_remainder_members_and_ts106_h0_seals_preserved(result: dict[str, Any]) -> None:
    source = cert.source_authority()
    before = source["REGION"]["complete_region_members"]
    after = result["COMPLETE_REGION_MEMBERS"]
    changed = {r["member_id"] for r in after if r["final_bound"] != r["prior_bound"]}
    assert changed == set(TARGET_IDS)
    remainder = [r for r in after if r["member_id"] not in changed]
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 577
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 627
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355274472
    )
    for old, new in zip(before, after, strict=True):
        assert new["prior_bound"] == old["final_bound"]
        assert {k: new[k] for k in old if k != "final_bound"} == {
            k: v for k, v in old.items() if k != "final_bound"
        }
        if new["member_id"] not in changed:
            assert new["final_bound"] == old["final_bound"]
    assert (
        sha256(
            repr(
                tuple((cert.dense(r["witness_counts"]), r["final_bound"]) for r in remainder)
            ).encode("ascii")
        ).hexdigest()
        == result["PRESERVED_REMAINDER_SHA256"]
        == ("09b7371e67a6dbf3ae183b1701f3780ec2c901a4e385a5a9e3b8c39cc71b569e")
    )
    for relative, expected in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == expected
    assert result["TS106_CERTIFICATE_SHA256"] == cert.BASE_RESULT_SHA256
    assert source["TS106"] == json.loads(cert.prior.RESULT_PATH.read_bytes())


def test_complete_family_recomputed_and_22_states_preserved(result: dict[str, Any]) -> None:
    authority = cert.source_authority()["TS106"]
    before = {r["stable_id"]: r["bound"] for r in authority["FINAL_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == 23
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert after[cert.TARGET_STATE_ID] == result["FINAL_TARGET_STATE_UB"] == 355274472
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_TERM_COUNT", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == authority[key]
    assert result["TAIL_BOUND"] == 354039277
    assert result["CLASSIFIED_MAX"] == 355145504
    assert result["START_COMPLETE_R3_UB"] == 355274920
    assert (
        result["FINAL_COMPLETE_R3_UB"]
        == max(*after.values(), result["TAIL_BOUND"], result["CLASSIFIED_MAX"])
        == 355274472
    )
    assert result["FINAL_OWNER_IDS"] == ["state:s2-12692531-s3-681744"]
    assert result["RUNNER_UP"] == {"bound": 355274108, "owner_ids": ["state:s2-13169800-s3-789320"]}
    assert result["REMAINING_GAP"] == 355274472 - 313263888 == 42010584
    assert result["STRICT_GAIN"] == 355274920 - 355274472 == 448


MUTATIONS = (
    "source",
    "pair",
    "floor",
    "rank",
    "mass",
    "triple_count",
    "event_count",
    "event_type",
    "event_definition",
    "signature",
    "missing_member",
    "duplicate_member",
    "omitted_vector",
    "omitted_vector_row",
    "additive_credit",
    "double_subtraction",
    "witness",
    "remainder",
    "remainder_digest",
    "region_vector",
    "family",
    "owner",
    "runner_up",
    "tail",
    "classified",
    "numeric_type",
)


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_semantic_mutations_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof = bad["ELEVEN_EVENT_PROOF"]
    member = bad["MEMBER_CERTIFICATES"][1]
    row = member["vector_certificates"][0]
    if mutation == "source":
        bad["BASE_TREE"] = "0" * 40
    elif mutation == "pair":
        proof["pair_rows"][0][6] += 1
    elif mutation == "floor":
        proof["hunter_floor"] += 1
    elif mutation == "rank":
        proof["integer_minimizer"]["rank_floors"][0] -= 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "triple_count":
        proof["all_admissible_threshold_cases"] -= 1
    elif mutation == "event_count":
        row["type0_count"] = 10
    elif mutation == "event_type":
        row["eleven_event_types"][0] = 1
    elif mutation == "event_definition":
        row["residual_event_definition"] = "E_i"
    elif mutation == "signature":
        row["compression_signature"][0] = -1
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "omitted_vector":
        member["represented_vectors"].pop()
    elif mutation == "omitted_vector_row":
        member["vector_certificates"].pop()
    elif mutation == "additive_credit":
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
    elif mutation == "double_subtraction":
        row["vector_new_bound"] -= row["prior_applied_correction"]
    elif mutation == "witness":
        row["support_witness"][0][0] = 99
    elif mutation == "remainder":
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["member_id"] not in TARGET_IDS)[
            "final_bound"
        ] -= 1
    elif mutation == "remainder_digest":
        bad["PRESERVED_REMAINDER_SHA256"] = "0" * 64
    elif mutation == "region_vector":
        bad["COMPLETE_REGION_MEMBERS"][-1]["represented_vectors"].pop()
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = ["state:s2-13169800-s3-789320"]
    elif mutation == "runner_up":
        bad["RUNNER_UP"]["bound"] += 1
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "classified":
        bad["CLASSIFIED_MAX"] -= 1
    else:
        bad["HUNTER_FLOOR"] = float(bad["HUNTER_FLOOR"])
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


@pytest.mark.parametrize("relative", cert.source_paths())
def test_every_source_tamper_rejected_with_warm_caches(
    relative: str, monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    read = Path.read_bytes

    def tamper(path: Path) -> bytes:
        data = read(path)
        return data + b"\n" if path == cert.REPO_ROOT / relative else data

    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(AssertionError, match="immutable executing source or sealed input"):
        cert.build_result()
    assert result["TASK_STATUS"] == "SUCCESS"


def test_live_additive_credit_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def additive(credits: Mapping[str, int]) -> int:
        return sum(credits.values())

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "combine_corrections", additive)
        with pytest.raises(AssertionError, match="MAX-only"):
            cert.build_result()
    assert cert.build_result()["FINAL_COMPLETE_R3_UB"] == 355274472


def test_live_event_count_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(cert, "EVENT_COUNT", 10)
        with pytest.raises(AssertionError, match="eleven type-0"):
            cert.build_result()
    assert cert.build_result()["TARGET_VECTOR_COUNT"] == 6


def test_live_omitted_compressed_vector_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    recover = cert.catalog.r17.represented_vectors

    def omit(members: Any) -> dict[cert.CountVector, tuple[cert.CountVector, ...]]:
        recovered = recover(members)
        recovered[cert.TARGET_VECTORS[1]] = (cert.TARGET_VECTORS[1],)
        return recovered

    cert.represented_vectors.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(cert.catalog.r17, "represented_vectors", omit)
            with pytest.raises(AssertionError, match=r"represented-vector|compression"):
                cert.build_result()
    finally:
        cert.represented_vectors.cache_clear()
    assert len(cert.represented_vectors()[cert.TARGET_VECTORS[1]]) == 2


def test_incomplete_member_or_wrong_event_proof_rejected() -> None:
    member = cert.target_members(cert.region_members())[1]
    proof = cert.eleven_event_proof()
    with pytest.raises(AssertionError, match="represented-vector member coverage"):
        cert.certify_member(member, (member.counts,), proof)
    bad = copy.deepcopy(proof)
    bad["event_count"] = 10
    with pytest.raises(AssertionError, match="eleven-event applicability"):
        cert.certify_vector(member, member.counts, bad)


def test_exact_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 5,
        "vectors": 6,
        "region_members": 582,
        "region_vectors": 633,
        "state_terms": 23,
    }
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"
