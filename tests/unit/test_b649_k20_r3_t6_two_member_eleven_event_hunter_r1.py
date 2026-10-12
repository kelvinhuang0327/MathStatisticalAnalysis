"""Exact two-member Hunter integration, independent arithmetic and semantic mutations."""

from __future__ import annotations

import copy
import itertools
import json
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_t6_two_member_eleven_event_hunter_r1 as cert

PHI = (107_800, 574_000, 1_691_620, 3_451_651)
OWNER = "state:s2-12695020-s3-735532"


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_immutable_authority_and_exact_highest_tie(result: dict[str, Any]) -> None:
    assert cert.verify_base_authority() == {
        "HEAD": "90bf41bc87500763f764c09cd1c90c0ea82e2023",
        "TREE": "a62938a80bbda1e2be33cd4631ba8599495579a4",
        "RESULT_SHA256": "60e44a40b5bcd6fb37256cd791e10c1c9c5d35cdd9bec5f5520ecaa5f35ba3df",
    }
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    assert result["REGION_SHA256"] == (
        "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
    )
    assert result["TIED_MEMBER_IDS"] == ["[0,11][4,1][16,6]", "[0,11][1,1][16,6]"]
    assert result["REPRESENTED_VECTOR_COVERAGE"] == [1, 1]
    members = cert.region_members()
    targets = cert.target_members(members)
    assert {m.counts for m in members if m.final_bound == max(x.final_bound for x in members)} == {
        m.counts for m in targets
    }
    with pytest.raises(AssertionError, match="two highest"):
        cert.target_members(tuple(m for m in members if m != targets[0]))
    with pytest.raises(AssertionError, match="two highest"):
        cert.target_members(
            tuple(replace(m, represented_vector_count=2) if m == targets[0] else m for m in members)
        )


def test_complete_region_and_every_represented_vector(result: dict[str, Any]) -> None:
    members, recovered = cert.region_members(), cert.represented_vectors()
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert len(members) == len(rows) == len(recovered) == 1427
    assert len({r["member_id"] for r in rows}) == 1427
    flat = [v for vectors in recovered.values() for v in vectors]
    assert len(flat) == len(set(flat)) == result["REGION_REPRESENTED_VECTOR_COUNT"] == 1543
    assert result["ALL_REPRESENTED_VECTORS_SHA256"] == cert.digest(
        tuple((m.counts, recovered[m.counts]) for m in members)
    )
    for member, row in zip(members, rows, strict=True):
        state = cert.catalog.rebuild_member(member)
        signature = cert.hunter.eleven.compression_signature(state)
        vectors = tuple(cert.dense(v) for v in row["represented_vectors"])
        assert vectors == recovered[member.counts]
        assert len(vectors) == row["represented_vector_count"] == member.represented_vector_count
        for vector in vectors:
            rebuilt = cert.catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            assert cert.hunter.eleven.compression_signature(rebuilt) == signature
            assert cert.hunter.r14.raw_bound(rebuilt) == row["raw_bound"]


def test_exact_residual_event_identity_and_four_pair_costs(result: dict[str, Any]) -> None:
    proof = result["ELEVEN_EVENT_PROOF"]
    assert proof == cert.theorem.eleven_event_proof()
    assert proof["residual_event_definition"] == cert.hunter.eleven.RESIDUAL_EVENT_DEFINITION
    assert proof["event_count"] == 11
    assert proof["type_cells"] == [0, 0, 0, 6]
    assert proof["pair_floors"] == list(PHI)
    assert len(proof["pair_rows"]) == 4
    for overlap, value in enumerate(PHI):
        cells = (0, 0, 0, overlap)
        tickets = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert (
            cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B))
            == value
        )
        assert cert.six.residual_pair_intersection(0, 0, cells) == value
        assert proof["pair_rows"][overlap] == [0, 0, *cells, value]
    assert cert.hunter.family_pair_overlap_ceiling() == 3
    for member in result["MEMBER_CERTIFICATES"]:
        row = member["vector_certificates"][0]
        vector = cert.dense(row["counts"])
        assert sum(vector) == 18 and vector[0] == row["type0_count"] == 11
        assert row["eleven_event_indices"] == list(range(11))
        assert row["eleven_event_types"] == [0] * 11
        assert row["pair_overlap_ceiling"] == 3
        assert row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
        assert row["residual_event_sum"] == sum(
            n * cert.hunter.residual_event_size(i) for i, n in enumerate(vector) if n
        )


def test_collision_and_independent_threshold_rank_relaxation(result: dict[str, Any]) -> None:
    proof = result["ELEVEN_EVENT_PROOF"]
    assert proof["outside_incidences"] == 66
    assert proof["outside_label_count"] == 40
    assert proof["balanced_frequencies"] == [[1, 14], [2, 26]]
    assert sum([1] * 14 + [2] * 26) == 66
    assert sum(comb(d, 2) for d in [1] * 14 + [2] * 26) == proof["collision_mass_floor"] == 26
    assert all(comb(d, 2) >= d - 1 for d in range(12))
    cases = proof["threshold_cases"]
    assert [r["e1_lower_bound"] for r in cases] == [26, 13, 9]
    assert [r["rank_lower_bounds"] for r in cases] == [[7, 0, 0], [5, 1, 0], [4, 1, 1]]
    assert [r["hunter_floor"] for r in cases] == [4_341_400, 4_526_620, 5_820_451]
    values: list[int] = []
    for r1 in range(11):
        for r2 in range(r1 + 1):
            for r3 in range(r2 + 1):
                ranks = (r1, r2, r3)
                if sum(comb(r + 1, 2) for r in ranks) >= 26:
                    values.append(
                        10 * PHI[0] + sum((PHI[k] - PHI[k - 1]) * ranks[k - 1] for k in range(1, 4))
                    )
    assert min(values) == result["HUNTER_FLOOR"] == 4_341_400
    assert proof["integer_minimizer"] == {
        "edge_counts": [26, 0, 0],
        "rank_floors": [7, 0, 0],
        "feasible_threshold_triples": 30_216,
    }
    for e1 in range(comb(11, 2) + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= 26:
                    ranks = tuple(cert.hunter.rank_floor(e) for e in (e1, e2, e3))
                    case = cases[2 if e3 else 1 if e2 else 0]
                    assert all(
                        a >= b for a, b in zip(ranks, case["rank_lower_bounds"], strict=True)
                    )
                    assert cert.hunter.tree_weight_floor(PHI, ranks, 11) >= case["hunter_floor"]


def test_forest_rank_and_pointwise_hunter_inequalities() -> None:
    for a in range(11):
        for b in range(11 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    for edges in range(comb(11, 2) + 1):
        rank = cert.hunter.rank_floor(edges)
        assert comb(rank + 1, 2) >= edges
        assert rank == 0 or comb(rank, 2) < edges
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_max_replaces_correction_and_member_bounds(result: dict[str, Any]) -> None:
    assert result["NEW_MEMBER_BOUNDS"] == [355_269_698, 355_269_698]
    for member in result["MEMBER_CERTIFICATES"]:
        row = member["vector_certificates"][0]
        corrections = row["corrections"]
        assert set(corrections) == {"R6_PAIR", "FOREST", "EXISTING_HUNTER", "ELEVEN_EVENT_HUNTER"}
        assert corrections["R6_PAIR"] == 1_830_840
        assert corrections["FOREST"] == row["prior_applied_correction"] == 4_018_000
        assert corrections["EXISTING_HUNTER"] == cert.prior.base.nine_event_proof()["hunter_floor"]
        assert corrections["ELEVEN_EVENT_HUNTER"] == 4_341_400
        assert row["combined_correction"] == max(corrections.values()) == 4_341_400
        assert row["combined_correction"] != sum(corrections.values())
        assert row["uncorrected_anchor_bound"] == 359_611_098
        assert row["uncorrected_anchor_bound"] - row["combined_correction"] == 355_269_698
        assert member["member_prior_bound"] == member["member_raw_bound"] == 355_593_098
        assert member["member_new_bound"] == row["vector_new_bound"] == 355_269_698
    assert result["DUPLICATE_CORRECTIONS"] == 0
    assert result["NO_DOUBLE_COUNT_STATUS"] == "PASS_MAX_SINGLE_REPLACEMENT"


def test_two_legal_witnesses_and_tree_extension(result: dict[str, Any]) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        row = member["vector_certificates"][0]
        vector = cert.dense(row["counts"])
        support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
        assert cert.hunter.r8.validate_support_assignment(vector, support)
        assert cert.digest(support) == row["support_sha256"]
        subset = tuple(frozenset(t) for t in support[:11])
        assert all(t <= set(cert.hunter.CELL_LABELS[3]) for t in subset)
        mass = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
        assert mass == sum(len(a & b) for a, b in combinations(subset, 2)) >= 26
        witness = row["witness_analysis"]
        assert mass == witness["collision_mass"]
        assert witness["exact_tree_weight"] >= witness["phi_tree_weight"] >= 4_341_400
        assert len(witness["subset_tree"]) == 10
        tree = cast(list[tuple[int, int]], witness["extended_tree"])
        assert len(tree) == cert.hunter.graph_rank(18, tree) == 17
        types = tuple(i for i, n in enumerate(vector) for _ in range(n))
        full_weight = 0
        for left, right in tree:
            overlaps = tuple(
                len(set(support[left]) & set(support[right]) & set(labels))
                for labels in cert.hunter.CELL_LABELS
            )
            value = cert.six.residual_pair_intersection(
                types[left], types[right], (overlaps[0], overlaps[1], overlaps[2], overlaps[3])
            )
            assert value >= 0
            full_weight += value
        assert full_weight >= witness["phi_tree_weight"]


def test_remainder_and_all_stronger_certificates_are_preserved(result: dict[str, Any]) -> None:
    authority = cert.source_authority()
    before = {r["member_id"]: r for r in authority["COMPLETE_REGION_MEMBERS"]}
    targets = set(cert.TARGET_IDS)
    rows = result["COMPLETE_REGION_MEMBERS"]
    changed = {r["member_id"] for r in rows if r["prior_bound"] != r["final_bound"]}
    assert changed == targets
    remainder = [r for r in rows if r["member_id"] not in targets]
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 1425
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 1541
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355_505_920
    )
    for row in rows:
        original = before[row["member_id"]]
        assert row["prior_bound"] == original["final_bound"]
        assert row["raw_bound"] == original["raw_bound"]
        assert row["represented_vector_count"] == original["represented_vector_count"]
        if row["member_id"] not in targets:
            assert row["final_bound"] == original["final_bound"]
    assert result["PREVIOUS_MEMBER_CERTIFICATES_SHA256"] == cert.prior.json_digest(
        authority["MEMBER_CERTIFICATES"]
    )
    assert (
        result["PREVIOUS_REGION_CERTIFICATES_SHA256"]
        == authority["PREVIOUS_REGION_CERTIFICATES_SHA256"]
    )
    assert (
        result["PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"]
        == authority["PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"]
    )
    for relative, fingerprint in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == fingerprint


def test_complete_family_recomputation_and_owner_transition(result: dict[str, Any]) -> None:
    authority = cert.source_authority()
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert result["START_STATE_TERMS"] == authority["FINAL_STATE_TERMS"]
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_COMPLETE_R3_UB"] == 355_593_098
    assert after[cert.TARGET_STATE_ID] == result["FINAL_TARGET_STATE_BOUND"] == 355_505_920
    assert after[OWNER] == result["FINAL_COMPLETE_R3_UB"] == 355_537_140
    assert result["FINAL_OWNER_IDS"] == [OWNER]
    assert (
        result["REMAINING_GAP"]
        == result["FINAL_COMPLETE_R3_UB"] - result["CURRENT_INCUMBENT"]
        == 42_273_252
    )
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_TERM_COUNT"] == len(cert.six.classified_terms()) == 56550
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_AGGREGATE", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == authority[key]
    family = cert.recompute_family(result["FINAL_TARGET_STATE_BOUND"])
    assert family["start"] == result["START_FAMILY_MAX_RECOMPUTATION"]
    assert family["final"] == result["FINAL_FAMILY_MAX_RECOMPUTATION"]
    assert result["FINAL_COMPLETE_R3_UB"] == max(
        max(after.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"]
    )


def test_invalid_or_missing_vector_and_event_proof_are_rejected() -> None:
    member = cert.target_members(cert.region_members())[0]
    proof = cert.eleven_event_proof()
    for vectors in ((), (member.counts, member.counts)):
        with pytest.raises(AssertionError, match="represented-vector"):
            cert.certify_member(member, vectors, proof)
    wrong = cert.dense([[0, 10], [4, 2], [16, 6]])
    with pytest.raises(AssertionError, match="source event identity"):
        cert.certify_vector(member, wrong, proof)
    bad = copy.deepcopy(proof)
    bad["residual_event_definition"] = "E_i"
    with pytest.raises(AssertionError, match="source event identity"):
        cert.certify_vector(member, member.counts, bad)


def test_exact_replay_and_stored_bytes(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 2,
        "vectors": 2,
        "region_members": 1427,
        "region_vectors": 1543,
    }
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "pair",
        "floor",
        "rank",
        "mass",
        "event",
        "signature",
        "missing_member",
        "duplicate_member",
        "vector",
        "missing_vector_row",
        "max_sum",
        "witness",
        "digest",
        "remainder",
        "region_vector",
        "family",
        "owner",
        "tail",
        "aggregate",
        "classified_count",
    ],
)
def test_tampered_certificates_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof, member = bad["ELEVEN_EVENT_PROOF"], bad["MEMBER_CERTIFICATES"][0]
    row = member["vector_certificates"][0]
    if mutation == "source":
        bad["BASE_TREE"] = "0" * 40
    elif mutation == "pair":
        proof["pair_rows"][0][6] += 1
    elif mutation == "floor":
        proof["hunter_floor"] += 1
    elif mutation == "rank":
        proof["threshold_cases"][0]["rank_lower_bounds"][0] -= 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "event":
        row["eleven_event_types"][0] = 1
    elif mutation == "signature":
        row["compression_signature"][0] = -1
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "vector":
        member["represented_vectors"].pop()
    elif mutation == "missing_vector_row":
        member["vector_certificates"].pop()
    elif mutation == "max_sum":
        row["combined_correction"] = sum(row["corrections"].values())
    elif mutation == "witness":
        row["support_witness"][0][0] = 99
    elif mutation == "digest":
        row["support_sha256"] = "0" * 64
    elif mutation == "remainder":
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["member_id"] not in cert.TARGET_IDS)[
            "final_bound"
        ] -= 1
    elif mutation == "region_vector":
        bad["COMPLETE_REGION_MEMBERS"][-1]["represented_vectors"].pop()
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [cert.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "aggregate":
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    else:
        bad["CLASSIFIED_TERM_COUNT"] -= 1
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


@pytest.mark.parametrize("relative", sorted(cert.UPSTREAM_SHA256))
def test_all_source_tampering_rejected_with_warm_caches(
    relative: str, monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    read = Path.read_bytes

    def tamper(path: Path) -> bytes:
        data = read(path)
        return data + b"\n" if path == cert.REPO_ROOT / relative else data

    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(AssertionError, match="fingerprint"):
        cert.build_result()
    assert result["TASK_STATUS"] == "SUCCESS"


def test_parsed_certificate_source_identity_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    read = Path.read_text

    def tamper(path: Path, *args: Any, **kwargs: Any) -> str:
        text = read(path, *args, **kwargs)
        if path == cert.REPO_ROOT / cert.prior.RESULT_RELATIVE:
            payload = json.loads(text)
            payload["TASK_ID"] = "FOREIGN_CERTIFICATE"
            return json.dumps(payload)
        return text

    monkeypatch.setattr(Path, "read_text", tamper)
    cert.source_authority.cache_clear()
    try:
        with pytest.raises(AssertionError, match="predecessor certificate identity"):
            cert.source_authority()
    finally:
        cert.source_authority.cache_clear()


def test_max_as_sum_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def add(values: Mapping[str, int]) -> int:
        return sum(values.values())

    member = cert.target_members(cert.region_members())[0]
    proof = cert.eleven_event_proof()
    monkeypatch.setattr(cert.hunter, "combine_corrections", add)
    with pytest.raises(AssertionError, match="max single correction"):
        cert.certify_member(member, (member.counts,), proof)


def test_pair_counter_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.hunter.exact_pair_rows

    def wrong(pairs: tuple[tuple[int, int], ...]) -> tuple[tuple[int, ...], ...]:
        return tuple((*r[:6], r[6] + 1) for r in original(pairs))

    monkeypatch.setattr(cert.hunter, "exact_pair_rows", wrong)
    with pytest.raises(AssertionError, match="inclusion/exclusion"):
        cert.eleven_event_proof()


def test_collision_floor_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.hunter.balanced_collision_mass

    def undercount(incidences: int, labels: int) -> int:
        return original(incidences, labels) - 1

    monkeypatch.setattr(cert.hunter, "balanced_collision_mass", undercount)
    with pytest.raises(AssertionError, match="collision floor"):
        cert.eleven_event_proof()


def test_rank_floor_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.hunter.rank_floor

    def lower_rank(edges: int) -> int:
        return max(0, original(edges) - 1)

    monkeypatch.setattr(cert.hunter, "rank_floor", lower_rank)
    with pytest.raises(AssertionError, match="least feasible forest rank"):
        cert.eleven_event_proof()


def test_event_definition_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cert.hunter, "RESIDUAL_EVENT_DEFINITION", "E_i")
    with pytest.raises(AssertionError, match="residual-event definition"):
        cert.eleven_event_proof()


def test_compression_signature_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    member = cert.target_members(cert.region_members())[0]
    proof = cert.eleven_event_proof()
    signatures = itertools.count()

    def drifting_signature(_state: object) -> tuple[int]:
        return (next(signatures),)

    monkeypatch.setattr(cert.hunter.eleven, "compression_signature", drifting_signature)
    with pytest.raises(AssertionError, match="compression signature"):
        cert.certify_vector(member, member.counts, proof)


def test_missing_recovered_vector_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.catalog.r17.represented_vectors

    def missing(members: Any) -> dict[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        vectors = original(members)
        vectors.pop(cert.TARGET_VECTORS[0])
        return vectors

    cert.represented_vectors.cache_clear()
    monkeypatch.setattr(cert.catalog.r17, "represented_vectors", missing)
    try:
        with pytest.raises(AssertionError, match="represented-vector coverage"):
            cert.represented_vectors()
    finally:
        cert.represented_vectors.cache_clear()


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, heavy refinement or full outcome enumeration")


def test_no_new_census_solver_or_heavy_route(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    monkeypatch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(cert.hunter.r14, "owner_region", forbidden)
    monkeypatch.setattr(cert.hunter.r14, "s4_child", forbidden)
    monkeypatch.setattr(cert.hunter.r8, "support_model_status", forbidden)
    monkeypatch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
    monkeypatch.setattr(cert.catalog.r24, "run_chase", forbidden)
    cert.region_members.cache_clear()
    cert.represented_vectors.cache_clear()
    assert cert.build_result() == result
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"
