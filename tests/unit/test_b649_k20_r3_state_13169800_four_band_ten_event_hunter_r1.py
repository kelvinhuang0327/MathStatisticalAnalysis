"""Independent complete-region, Hunter threshold and semantic mutation checks."""

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

from lottolab.research import b649_k20_r3_state_13169800_four_band_ten_event_hunter_r1 as cert

PHI = (107_800, 574_000, 1_691_620, 3_451_651)
FINAL_OWNER = "state:s2-12695020-s3-735532"


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_immutable_authority(result: dict[str, Any]) -> None:
    assert cert.verify_base_authority() == {
        "HEAD": "f991b8e7dcea4e58e9163199ada684a517b49f6f",
        "TREE": "735772cda190102898aa817dab59231577d8e031",
        "RESULT_SHA256": "3cc0148c29c9c0592868349aad5eee4ae715181bc85900f7346df04dcba8cfb5",
    }
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    assert (
        result["REGION_IDENTITY"]
        == result["REGION_SHA256"]
        == ("c183f8d2f93d3a695fcae3e2d2d280d40ffb1de3527eb43e61ce5321569dcde1")
    )
    assert sha256(cert.prior.RESULT_PATH.read_bytes()).hexdigest() == cert.BASE_RESULT_SHA256
    assert cert.source_authority()["FINAL_OWNER_IDS"] == [cert.TARGET_STATE_ID]


def test_complete_catalog_recovery_and_every_compression_signature(result: dict[str, Any]) -> None:
    members, recovered = cert.region_members(), cert.represented_vectors()
    assert len(members) == len(recovered) == len(result["COMPLETE_REGION_MEMBERS"]) == 989
    flat = [v for vectors in recovered.values() for v in vectors]
    assert len(flat) == len(set(flat)) == result["REGION_REPRESENTED_VECTOR_COUNT"] == 1072
    assert recovered == cert.region.region_vectors()
    assert cert.catalog.region_fingerprint(members) == cert.REGION_SHA256
    assert result["ALL_REPRESENTED_VECTORS_SHA256"] == cert.digest(
        tuple((m.counts, recovered[m.counts]) for m in members)
    )
    for member, row in zip(members, result["COMPLETE_REGION_MEMBERS"], strict=True):
        signature = cert.hunter.eleven.compression_signature(cert.catalog.rebuild_member(member))
        vectors = tuple(cert.dense(v) for v in row["represented_vectors"])
        assert vectors == recovered[member.counts]
        assert len(vectors) == row["represented_vector_count"] == member.represented_vector_count
        assert tuple(sorted(vectors)) == vectors and min(vectors) == member.counts
        assert cert.catalog.normalized(signature) == row["compression_signature"]
        for vector in vectors:
            state = cert.catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            assert cert.hunter.eleven.compression_signature(state) == signature
            assert cert.hunter.r14.raw_bound(state) == member.raw_bound == row["raw_bound"]
            assert len(vector) == 30 and sum(vector) == 18 and min(vector) >= 0


def test_all_four_highest_bands_are_recovered_before_parametric_check(
    result: dict[str, Any],
) -> None:
    bands = cert.target_bands(cert.region_members())
    recovered = cert.represented_vectors()
    assert result["FOUR_BAND_MEMBER_COUNT"] == result["FOUR_BAND_VECTOR_COUNT"] == 40
    assert len(result["MEMBER_CERTIFICATES"]) == 40
    assert result["FOUR_BAND_VECTOR_COUNTS"] == [10, 10, 10, 10]
    target_vectors: set[tuple[int, ...]] = set()
    for t, (bound, members) in enumerate(bands):
        assert bound == 355_499_536 - 448 * t
        expected: set[tuple[int, ...]] = set()
        for k in range(5):
            for j in (17, 19):
                vector = [0] * 30
                vector[0], vector[1], vector[4] = 10, k, 4 - k
                vector[5], vector[16], vector[j] = 3 - t, t, 1
                expected.add(tuple(vector))
        actual = {v for m in members for v in recovered[m.counts]}
        assert actual == expected and len(actual) == len(members) == 10
        assert not actual & target_vectors
        target_vectors.update(actual)
    assert len(target_vectors) == 40
    assert {cert.member_id(v) for v in target_vectors} == set(result["FOUR_BAND_MEMBER_IDS"])
    for band in bands:
        removed = band[1][0]
        with pytest.raises(AssertionError, match="four-band"):
            cert.target_bands(tuple(m for m in cert.region_members() if m != removed))


def test_recount_four_pair_costs_and_all_ten_event_applicability_gates(
    result: dict[str, Any],
) -> None:
    proof = result["TEN_EVENT_PROOF"]
    assert proof == cert.ten_event_proof()
    assert proof["type_cells"] == [0, 0, 0, 6]
    assert proof["pair_floors"] == list(PHI)
    assert proof["pair_overlap_ceiling"] == 3
    outside = set(range(49)) - (cert.hunter.ANCHOR_A | cert.hunter.ANCHOR_B)
    assert set(proof["outside_labels"]) == outside == set(cert.hunter.CELL_LABELS[3])
    assert len(outside) == proof["outside_label_count"] == 40
    for overlap, cost in enumerate(PHI):
        cells = (0, 0, 0, overlap)
        tickets = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert cert.six.residual_pair_intersection(0, 0, cells) == cost
        assert (
            cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)) == cost
        )
        assert proof["pair_rows"][overlap] == [0, 0, *cells, cost]
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            vector = cert.dense(row["counts"])
            assert vector[0] == row["type0_count"] == row["event_count"] == 10
            assert sum(vector) == 18
            assert row["selected_event_indices"] == list(range(10))
            assert row["selected_event_types"] == [0] * 10
            assert row["residual_event_definition"] == cert.RESIDUAL_EVENT_DEFINITION
            assert row["outside_incidences"] == 60 and row["collision_mass_floor"] == 20
            assert row["applicability_status"] == "PASS"


def test_collision_smoothing_rank_inequality_and_complete_threshold_minimum(
    result: dict[str, Any],
) -> None:
    proof = result["TEN_EVENT_PROOF"]
    assert proof["balanced_frequencies"] == [[1, 20], [2, 20]]
    assert proof["collision_mass_floor"] == 20 * comb(1, 2) + 20 * comb(2, 2) == 20
    for high in range(2, 11):
        for low in range(high - 1):
            assert comb(high, 2) + comb(low, 2) > comb(high - 1, 2) + comb(low + 1, 2)
    # Concentrating component ranks maximizes their edge capacity.
    for left in range(10):
        for right in range(10 - left):
            assert comb(left + 1, 2) + comb(right + 1, 2) <= comb(left + right + 1, 2)
    ranks = [min(r for r in range(10) if comb(r + 1, 2) >= e) for e in range(46)]
    best = None
    counts = [0, 0, 0]
    for e1 in range(46):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 20:
                    continue
                value = 9 * PHI[0] + sum(
                    (PHI[k + 1] - PHI[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                )
                assert value >= 3_767_400
                candidate = (value, (e1, e2, e3))
                best = candidate if best is None else min(best, candidate)
                counts[2 if e3 else int(e2 > 0)] += 1
    assert best == (3_767_400, (20, 0, 0))
    assert sum(counts) == proof["all_admissible_threshold_cases"] == 16_982
    assert counts == proof["admissible_case_counts"]
    assert proof["hunter_floor"] == result["HUNTER_FLOOR"] == 3_767_400
    assert proof["integer_minimizer"]["edge_counts"] == [20, 0, 0]
    assert proof["integer_minimizer"]["rank_floors"] == [6, 0, 0]
    assert proof["rank_algebra_rows"] == 46
    assert cert.prior.prior.ten_event_proof()["hunter_floor"] == 3_767_400


def test_max_correction_single_subtraction_for_every_band(result: dict[str, Any]) -> None:
    assert result["NEW_BAND_BOUNDS"] == [355_176_136, 355_175_688, 355_175_240, 355_174_792]
    for t, band in enumerate(result["FOUR_BANDS"]):
        members = [r for r in result["MEMBER_CERTIFICATES"] if r["member_id"] in band["member_ids"]]
        assert len(members) == 10
        for member in members:
            assert len(member["vector_certificates"]) == 1
            for row in member["vector_certificates"]:
                corrections = row["corrections"]
                assert corrections["FOREST"] == row["prior_applied_correction"] == 3_444_000
                assert corrections["EXISTING_R14"] == 0
                assert corrections["EXISTING_HUNTER"] == 3_193_400
                assert row["uncorrected_anchor_bound"] == 358_943_536 - 448 * t
                assert corrections["NEW_HUNTER"] == row["combined_correction"] == 3_767_400
                assert (
                    row["combined_correction"]
                    == max(corrections.values())
                    != sum(corrections.values())
                )
                assert (
                    row["vector_new_bound"]
                    == row["uncorrected_anchor_bound"] - row["combined_correction"]
                )
                assert member["member_prior_bound"] - row["vector_new_bound"] == 323_400
            assert member["member_new_bound"] == band["new_bound"]
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_all_forty_existing_supports_and_full_hunter_extensions(result: dict[str, Any]) -> None:
    original = {
        cert.dense(v["counts"]): v
        for m in cert.region_authority()["MEMBER_CERTIFICATES"]
        for v in m["vector_certificates"]
    }
    rows = [v for m in result["MEMBER_CERTIFICATES"] for v in m["vector_certificates"]]
    assert len(rows) == 40
    for row in rows:
        vector = cert.dense(row["counts"])
        support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
        assert row["support_witness"] == original[vector]["support_witness"]
        assert row["support_sha256"] == original[vector]["support_sha256"] == cert.digest(support)
        assert cert.hunter.r8.validate_support_assignment(vector, support)
        tickets = tuple(frozenset(t) for t in support)
        anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
        assert len(set((*anchors, *tickets))) == 20
        assert all(len(t) == 6 and t <= set(range(49)) for t in (*anchors, *tickets))
        assert max(len(a & b) for a, b in combinations((*anchors, *tickets), 2)) == 3
        subset = tickets[:10]
        assert all(t <= set(cert.hunter.CELL_LABELS[3]) for t in subset)
        mass = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
        overlaps = {(i, j): len(subset[i] & subset[j]) for i, j in combinations(range(10), 2)}
        witness = row["witness_analysis"]
        assert mass == sum(overlaps.values()) == witness["collision_mass"] >= 20
        tree = tuple((int(a), int(b)) for a, b in witness["subset_tree"])
        assert len(tree) == cert.hunter.graph_rank(10, tree) == 9
        for k in range(1, 4):
            graph = [e for e, v in overlaps.items() if v >= k]
            assert sum(overlaps[e] >= k for e in tree) == cert.hunter.graph_rank(10, graph)
        weight = sum(PHI[overlaps[e]] for e in tree)
        assert weight == witness["phi_tree_weight"] >= 3_767_400
        full = cast(list[tuple[int, int]], witness["extended_tree"])
        assert len(full) == cert.hunter.graph_rank(18, full) == 17
        types = tuple(i for i, n in enumerate(vector) for _ in range(n))
        full_weight = 0
        for left, right in full:
            cells = tuple(
                len(tickets[left] & tickets[right] & set(c)) for c in cert.hunter.CELL_LABELS
            )
            cost = cert.six.residual_pair_intersection(
                types[left], types[right], cast(tuple[int, int, int, int], cells)
            )
            assert cost >= 0
            full_weight += cost
        assert full_weight == witness["extended_tree_exact_weight"] >= weight
    assert (
        cert.digest(tuple((r["counts"], r["support_witness"]) for r in rows))
        == result["RECORDED_WITNESSES_SHA256"]
    )


def test_remainder_and_predecessor_certificates_are_preserved(result: dict[str, Any]) -> None:
    members = cert.region_members()
    targets = set(result["FOUR_BAND_MEMBER_IDS"])
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert {r["member_id"] for r in rows if r["final_bound"] != r["prior_bound"]} == targets
    for m, row in zip(members, rows, strict=True):
        assert row["raw_bound"] == m.raw_bound and row["prior_bound"] == m.final_bound
        if row["member_id"] not in targets:
            assert row["final_bound"] == m.final_bound
    remainder = [r for r in rows if r["member_id"] not in targets]
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 949
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 1032
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355_466_398
    )
    original = cert.source_authority()["MEMBER_CERTIFICATES"]
    assert len(original) == result["PREDECESSOR_MEMBER_COUNT"] == 21
    assert original == result["PREDECESSOR_MEMBER_CERTIFICATES"]
    assert cert.json_digest(original) == result["PREDECESSOR_CERTIFICATES_SHA256"]
    assert result["PREDECESSOR_STATE_BOUND"] == 355_374_810
    for record in original:
        for witness in record["vector_certificates"]:
            assert cert.hunter.r8.validate_support_assignment(
                cert.dense(witness["counts"]), tuple(tuple(t) for t in witness["support_witness"])
            )
    assert (
        cert.digest(
            tuple(
                (m.counts, m.represented_vector_count, m.raw_bound, m.final_bound)
                for m in members
                if cert.member_id(m.counts) not in targets
            )
        )
        == result["PRESERVED_MEMBER_BOUNDS_SHA256"]
    )
    for path, fingerprint in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == fingerprint


def test_complete_23_state_recomputation_and_correct_next_owner(result: dict[str, Any]) -> None:
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert result["START_STATE_TERMS"] == cert.source_authority()["FINAL_STATE_TERMS"]
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_COMPLETE_R3_UB"] == 355_499_536
    state = max(r["final_bound"] for r in result["COMPLETE_REGION_MEMBERS"])
    assert after[cert.TARGET_STATE_ID] == state == result["FINAL_TARGET_STATE_BOUND"] == 355_466_398
    classified = cert.six.classified_terms()
    assert len(classified) == result["CLASSIFIED_TERM_COUNT"] == 56550
    terms = [*after.items(), (cert.r24.TAIL_ID, result["TAIL_BOUND"]), *classified]
    maximum = max(b for _, b in terms)
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355_497_359
    assert [k for k, b in terms if b == maximum] == result["FINAL_OWNER_IDS"] == [FINAL_OWNER]
    assert result["REMAINING_GAP"] == maximum - 313_263_888 == 42_233_471
    assert result["FULL_23_STATE_RECOMPUTATION"] == "PASS"
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_AGGREGATE", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == cert.source_authority()[key]
    assert result["TAIL_BOUND"] == 354_039_277


def test_exact_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 40,
        "vectors": 40,
        "region_members": 989,
        "region_vectors": 1072,
    }
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"


def test_nested_forests_and_hunter_lemma_on_small_families() -> None:
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


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


def test_parsed_source_identity_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    read = Path.read_text

    def tamper(path: Path, *args: Any, **kwargs: Any) -> str:
        text = read(path, *args, **kwargs)
        if path == cert.REPO_ROOT / cert.prior.RESULT_RELATIVE:
            payload = json.loads(text)
            payload["TASK_ID"] = "FOREIGN_CERTIFICATE"
            return json.dumps(payload)
        return text

    cert.source_authority.cache_clear()
    monkeypatch.setattr(Path, "read_text", tamper)
    try:
        with pytest.raises(AssertionError, match="predecessor identity"):
            cert.source_authority()
    finally:
        cert.source_authority.cache_clear()


@pytest.mark.parametrize("target_only", [False, True])
def test_missing_recovered_vector_mutation_rejected(
    monkeypatch: pytest.MonkeyPatch, target_only: bool
) -> None:
    original = cert.catalog.r17.represented_vectors

    def missing(members: Any) -> dict[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        recovered = original(members)
        member = (
            cert.target_bands(cert.region_members())[0][1][0]
            if target_only
            else next(m for m in cert.region_members() if m.represented_vector_count == 2)
        )
        recovered[member.counts] = recovered[member.counts][:-1]
        return recovered

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
    monkeypatch.setattr(cert.r24, "run_chase", forbidden)
    cert.region_members.cache_clear()
    cert.represented_vectors.cache_clear()
    assert cert.build_result() == result
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0 and result["OUTCOME_ENUMERATION_USED"] is False
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"


@pytest.mark.parametrize("level", range(4))
def test_invalid_applicability_and_incomplete_target_vector_rejected(level: int) -> None:
    member = cert.target_bands(cert.region_members())[level][1][0]
    vectors, proof = cert.represented_vectors()[member.counts], cert.ten_event_proof()
    for invalid in ((), (vectors[0], vectors[0])):
        with pytest.raises(AssertionError, match="represented-vector"):
            cert.certify_member(member, invalid, proof)
    wrong = list(vectors[0])
    wrong[0] -= 1
    wrong[1] += 1
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(member, tuple(wrong), proof)
    bad = copy.deepcopy(proof)
    bad["residual_event_definition"] = "E_i"
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(member, member.counts, bad)


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "pair",
        "floor",
        "rank",
        "mass",
        "case_count",
        "event",
        "signature",
        "missing_member",
        "duplicate_member",
        "missing_vector",
        "missing_vector_row",
        "max_sum",
        "witness",
        "digest",
        "remainder",
        "region_vector",
        "sealed",
        "family",
        "owner",
        "tail",
        "aggregate",
        "classified_count",
        "predecessor_region",
        "witness_ledger",
    ],
)
def test_tampered_certificate_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof = bad["TEN_EVENT_PROOF"]
    member = bad["MEMBER_CERTIFICATES"][0]
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
    elif mutation == "case_count":
        proof["all_admissible_threshold_cases"] -= 1
    elif mutation == "event":
        row["selected_event_types"][0] = 1
    elif mutation == "signature":
        row["compression_signature"][0] = -1
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "missing_vector":
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
        next(
            r
            for r in bad["COMPLETE_REGION_MEMBERS"]
            if r["member_id"] not in bad["FOUR_BAND_MEMBER_IDS"]
        )["final_bound"] -= 1
    elif mutation == "region_vector":
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["represented_vector_count"] == 2)[
            "represented_vectors"
        ].pop()
    elif mutation == "sealed":
        bad["PREDECESSOR_CERTIFICATES_SHA256"] = "0" * 64
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [cert.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "aggregate":
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    elif mutation == "classified_count":
        bad["CLASSIFIED_TERM_COUNT"] -= 1
    elif mutation == "predecessor_region":
        bad["PREDECESSOR_REGION_BOUNDS_SHA256"] = "0" * 64
    else:
        bad["RECORDED_WITNESSES_SHA256"] = "0" * 64
    with pytest.raises(AssertionError):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "mutation",
    [
        "max_sum",
        "pair",
        "mass",
        "rank",
        "event",
        "signature",
        "threshold_tree",
        "threshold_census",
        "inflated_floor",
        "outside_universe",
        "family",
    ],
)
def test_semantic_algorithm_mutations_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    member = cert.target_bands(cert.region_members())[0][1][0]
    vector, proof = member.counts, cert.ten_event_proof()
    if mutation == "max_sum":

        def add(values: Mapping[str, int]) -> int:
            return sum(values.values())

        monkeypatch.setattr(cert.hunter, "combine_corrections", add)
    elif mutation == "pair":
        original_pair = cert.hunter.exact_pair_rows

        def wrong_pairs(pairs: tuple[tuple[int, int], ...]) -> tuple[tuple[int, ...], ...]:
            return tuple((*r[:6], r[6] + 1) for r in original_pair(pairs))

        monkeypatch.setattr(cert.hunter, "exact_pair_rows", wrong_pairs)
    elif mutation == "mass":
        original_mass = cert.hunter.balanced_collision_mass

        def undercount(incidences: int, labels: int) -> int:
            return original_mass(incidences, labels) - 1

        monkeypatch.setattr(cert.hunter, "balanced_collision_mass", undercount)
    elif mutation == "rank":
        original_rank = cert.hunter.rank_floor

        def lower_rank(edges: int) -> int:
            return max(0, original_rank(edges) - 1)

        monkeypatch.setattr(cert.hunter, "rank_floor", lower_rank)
    elif mutation == "event":
        monkeypatch.setattr(cert.hunter, "RESIDUAL_EVENT_DEFINITION", "E_i")
    elif mutation == "signature":
        serial = itertools.count()

        def drifting_signature(_state: object) -> tuple[int]:
            return (next(serial),)

        monkeypatch.setattr(cert.hunter.eleven, "compression_signature", drifting_signature)
    elif mutation == "threshold_tree":

        def empty_tree(
            _n: int, _weights: Mapping[tuple[int, int], int]
        ) -> tuple[tuple[int, int], ...]:
            return ()

        monkeypatch.setattr(cert.hunter, "threshold_tree", empty_tree)
    elif mutation == "threshold_census":
        original_minimum = cert.hunter.minimum_tree_correction

        def missing_case(floors: Any, mass: int, vertices: int) -> Any:
            row = original_minimum(floors, mass, vertices)
            return replace(row, census_size=row.census_size - 1)

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", missing_case)
    elif mutation == "inflated_floor":
        original_minimum = cert.hunter.minimum_tree_correction

        def weaker(floors: Any, mass: int, vertices: int) -> Any:
            row = original_minimum(floors, mass, vertices)
            return replace(row, correction=row.correction + 1)

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", weaker)
    elif mutation == "outside_universe":
        labels = cert.hunter.CELL_LABELS
        monkeypatch.setattr(cert.hunter, "CELL_LABELS", (*labels[:3], labels[3][:-1]))
    else:
        original_family = cert.six.tail.family_maximum

        def wrong_family(tail: int, states: Any, classified: Any) -> dict[str, Any]:
            family = original_family(tail, states, classified)
            return (
                {**family, "R3_BOUND": 1}
                if dict(states)[cert.TARGET_STATE_ID] == 355_466_398
                else family
            )

        monkeypatch.setattr(cert.six.tail, "family_maximum", wrong_family)
    if mutation == "family":
        with pytest.raises(AssertionError, match="independent full Family"):
            cert.recompute_family(355_466_398)
    else:
        with pytest.raises(AssertionError):
            cert.certify_vector(member, vector, proof)
