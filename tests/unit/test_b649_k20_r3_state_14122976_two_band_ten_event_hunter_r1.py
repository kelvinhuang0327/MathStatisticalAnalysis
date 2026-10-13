"""Independent region replay, ten-event arithmetic and semantic fault checks."""

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

from lottolab.research import b649_k20_r3_state_14122976_two_band_ten_event_hunter_r1 as cert

PHI = (107_800, 574_000, 1_691_620, 3_451_651)
FINAL_OWNER = "state:s2-13548976-s3-951748"
# Record the fourteen independently constructed legal supports before certification.
SUPPORT_HASHES = (
    "cc9552f06fffb61ee807d136b0cad0eb3b2cd9b31c4f41f0554c308553598899",
    "32d17958e8ac33670d8e706fe7f475365dd5681436aea43dc4431fa7b1fa5134",
    "f40fe4c63a7be6ba17400484476c188216368134a973adcbc9e0bee3b6e25a7e",
    "886300d6a2e75b403e12bb2c71b36066b9d1abd3938c1fc9d4d817c2cd652589",
    "a78091ea8584778a95cc10f87e52ddbeed0f292dd16b068055eb1b2f6d227e1c",
    "82d62d61ae8304eada09a4797bc7524cf248d0fcf21ca9aea6a74f1542bc69c7",
    "ef4e9229eccae20808e6f4c99d62b7bf806ddc6e36c90b3d3436dc0741647c2b",
    "01fd64039a1346a1516b2fa84c48a0ae161148bcbe6c8ae456d3d276179439ac",
    "da22e89c73019b94df90461ced8b33ba6d3d30b8f947cd2993297ea39882aaae",
    "48d56879ae780e8d35b731a1447fe231fd50f7af09f45c8ec467f07051307c0c",
    "26aa2eb22130f476a08df7cf3887569e3360de23cd921db0d41da06faa0cf244",
    "37f9fc446c0408843d91a5ebb4c52703507f5fe8887fcf7c0d7a80bb81a35885",
    "531e670ab72282fe62e73cb83fa421b8f4c173f63109d23ab0ee44e502274da8",
    "c7ad1d167789fc6642275d2355304548e5f8a720bff26cbc0db434ca0715221d",
)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_immutable_authority(result: dict[str, Any]) -> None:
    assert cert.verify_base_authority() == {
        "HEAD": "5fb3bd25b45f640cdc09bb2ab192134baa1e6436",
        "TREE": "2d0e6e879cc2875e2f3232155072ef9238ffd72d",
        "RESULT_SHA256": "5bac36ad9c9458e98a45770fa379457df95f0287e3105ac1ae8406fb5d910bb7",
    }
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    assert (
        result["REGION_IDENTITY"]
        == result["REGION_SHA256"]
        == ("785409687cbaca559e536cf63ff87fb0e5f972796025ef03743e13ba5a88555e")
    )
    identity, source = cert.top16_authority()
    assert identity["head"] == cert.top16.TOP16_DONOR_HEAD
    assert identity["result_sha256"] == cert.top16.SOURCE_PINS["TOP16"][3]
    assert source["STATE_ID"] == cert.TARGET_STATE_ID
    assert cert.source_authority()["FINAL_OWNER_IDS"] == [cert.TARGET_STATE_ID]
    assert (
        sha256((cert.REPO_ROOT / cert.prior.RESULT_RELATIVE).read_bytes()).hexdigest()
        == cert.BASE_RESULT_SHA256
    )


def test_complete_region_vectors_and_compression_signatures(result: dict[str, Any]) -> None:
    members, recovered = cert.region_members(), cert.represented_vectors()
    source = cert.top16_authority()[1]
    assert len(members) == len(recovered) == len(result["COMPLETE_REGION_MEMBERS"]) == 214
    flat = [v for vectors in recovered.values() for v in vectors]
    assert len(flat) == len(set(flat)) == result["REGION_REPRESENTED_VECTOR_COUNT"] == 221
    assert sum(m.represented_vector_count == 2 for m in members) == 7
    assert cert.catalog.region_fingerprint(members) == cert.REGION_SHA256
    assert result["ALL_REPRESENTED_VECTORS_SHA256"] == cert.digest(
        tuple((m.counts, recovered[m.counts]) for m in members)
    )
    for member, row, original in zip(
        members, result["COMPLETE_REGION_MEMBERS"], source["COMPLETE_REGION_MEMBERS"], strict=True
    ):
        signature = cert.hunter.eleven.compression_signature(cert.catalog.rebuild_member(member))
        vectors = tuple(cert.dense(v) for v in row["represented_vectors"])
        assert (
            vectors
            == recovered[member.counts]
            == tuple(cert.dense(v) for v in original["represented_vectors"])
        )
        assert len(vectors) == row["represented_vector_count"] == member.represented_vector_count
        assert tuple(sorted(vectors)) == vectors and min(vectors) == member.counts
        assert cert.catalog.normalized(signature) == row["compression_signature"]
        for vector in vectors:
            rebuilt = cert.catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            assert cert.hunter.eleven.compression_signature(rebuilt) == signature
            assert cert.hunter.r14.raw_bound(rebuilt) == member.raw_bound == row["raw_bound"]
            assert 951_748 < rebuilt.joint_s3 <= 1_005_536 and rebuilt.joint_s2 >= 14_122_976


def test_exact_two_bands_and_all_fourteen_target_identities(result: dict[str, Any]) -> None:
    bands = cert.target_bands(cert.region_members())
    recovered = cert.represented_vectors()
    assert result["TWO_BAND_MEMBER_COUNT"] == result["TWO_BAND_VECTOR_COUNT"] == 14
    expected_ids: list[str] = []
    for selector, (bound, members) in zip((5, 16), bands, strict=True):
        assert bound == (355_510_148 if selector == 5 else 355_509_700)
        expected: set[tuple[int, ...]] = set()
        for k in range(7):
            vector = [0] * 30
            vector[0], vector[1], vector[4], vector[selector], vector[25] = 10, k, 6 - k, 1, 1
            expected.add(tuple(vector))
            expected_ids.append(cert.member_id(tuple(vector)))
        assert {v for m in members for v in recovered[m.counts]} == expected
        assert len(members) == 7 and all(m.represented_vector_count == 1 for m in members)
    assert result["TWO_BAND_MEMBER_IDS"] == expected_ids
    assert [r["member_id"] for r in result["MEMBER_CERTIFICATES"]] == expected_ids
    member = bands[0][1][0]
    with pytest.raises(AssertionError, match="two-band"):
        cert.target_bands(tuple(m for m in cert.region_members() if m != member))


def test_exact_residual_pairs_outside_universe_and_ten_event_identity(
    result: dict[str, Any],
) -> None:
    proof = result["TEN_EVENT_PROOF"]
    assert proof == cert.ten_event_proof()
    assert proof["type_cells"] == [0, 0, 0, 6]
    assert proof["pair_floors"] == list(PHI)
    assert proof["pair_overlap_ceiling"] == cert.hunter.family_pair_overlap_ceiling() == 3
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
            assert sum(vector) == 18 and vector[0] == row["type0_count"] == 10
            assert (
                row["ten_event_indices"] == list(range(10)) and row["ten_event_types"] == [0] * 10
            )
            assert row["residual_event_definition"] == cert.RESIDUAL_EVENT_DEFINITION
            assert row["outside_incidences"] == 60 and row["collision_mass_floor"] == 20
            assert row["applicability_status"] == "PASS"


def test_collision_convexity_and_every_admissible_threshold_triple(result: dict[str, Any]) -> None:
    proof = result["TEN_EVENT_PROOF"]
    assert proof["balanced_frequencies"] == [[1, 20], [2, 20]]
    assert proof["collision_mass_floor"] == 20 * comb(1, 2) + 20 * comb(2, 2) == 20
    # Smoothing any two frequencies differing by at least two reduces collisions.
    for high in range(2, 11):
        for low in range(high - 1):
            assert comb(high, 2) + comb(low, 2) > comb(high - 1, 2) + comb(low + 1, 2)
    assert [c["hunter_floor"] for c in proof["threshold_cases"]] == [
        3_767_400,
        3_952_620,
        5_712_651,
    ]
    assert [c["e1_lower_bound"] for c in proof["threshold_cases"]] == [20, 10, 7]
    assert [c["rank_lower_bounds"] for c in proof["threshold_cases"]] == [
        [6, 0, 0],
        [4, 1, 0],
        [4, 1, 1],
    ]
    ranks = [min(r for r in range(10) if comb(r + 1, 2) >= e) for e in range(46)]
    counts = [0, 0, 0]
    minimum = None
    for e1 in range(46):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 20:
                    continue
                value = 9 * PHI[0] + sum(
                    (PHI[k + 1] - PHI[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                )
                case = 2 if e3 else int(e2 > 0)
                assert value >= proof["threshold_cases"][case]["hunter_floor"] >= 3_767_400
                minimum = value if minimum is None else min(minimum, value)
                counts[case] += 1
    assert sum(counts) == proof["all_admissible_threshold_cases"] == 16_982
    assert counts == proof["admissible_case_counts"]
    assert minimum == proof["hunter_floor"] == result["HUNTER_CORRECTION_FLOOR"] == 3_767_400
    assert proof["floor_algebra"] == [970_200, 6, 466_200, 3_767_400]
    assert 9 * PHI[0] + 6 * (PHI[1] - PHI[0]) == minimum
    assert proof["integer_minimizer"]["edge_counts"] == [20, 0, 0]
    assert proof["integer_minimizer"]["rank_floors"] == [6, 0, 0]
    assert proof["rank_algebra_rows"] == 46


def test_nested_forests_and_hunter_lemma_on_small_families() -> None:
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_max_replacement_and_both_expected_band_bounds(result: dict[str, Any]) -> None:
    assert result["NEW_BAND_BOUNDS"] == [355_186_748, 355_186_300]
    for t, band in enumerate(result["TWO_BANDS"]):
        members = [r for r in result["MEMBER_CERTIFICATES"] if r["member_id"] in band["member_ids"]]
        assert len(members) == 7
        for member in members:
            assert len(member["vector_certificates"]) == 1
            for row in member["vector_certificates"]:
                corrections = row["corrections"]
                assert corrections["FOREST"] == row["prior_applied_correction"] == 3_444_000
                assert row["uncorrected_anchor_bound"] == 358_954_148 - 448 * t
                assert corrections["TEN_EVENT_HUNTER"] == row["combined_correction"] == 3_767_400
                assert (
                    row["combined_correction"]
                    == max(corrections.values())
                    != sum(corrections.values())
                )
                assert (
                    row["vector_new_bound"]
                    == row["uncorrected_anchor_bound"] - row["combined_correction"]
                )
            assert member["member_new_bound"] == band["new_bound"]
            assert member["member_certified_correction"] == 3_767_400
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_fourteen_recorded_supports_collisions_and_full_tree_extensions(
    result: dict[str, Any],
) -> None:
    rows = [row for r in result["MEMBER_CERTIFICATES"] for row in r["vector_certificates"]]
    assert tuple(row["support_sha256"] for row in rows) == SUPPORT_HASHES
    for row in rows:
        vector = cert.dense(row["counts"])
        support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
        assert cert.hunter.r8.validate_support_assignment(vector, support)
        assert cert.digest(support) == row["support_sha256"]
        tickets = tuple(frozenset(t) for t in support)
        anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
        assert len(set((*anchors, *tickets))) == 20
        assert all(len(t) == 6 and t <= set(range(49)) for t in (*anchors, *tickets))
        assert max(len(a & b) for a, b in combinations((*anchors, *tickets), 2)) == 3
        subset = tickets[:10]
        assert all(t <= set(cert.hunter.CELL_LABELS[3]) for t in subset)
        mass = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
        witness = row["witness_analysis"]
        overlaps = {(i, j): len(subset[i] & subset[j]) for i, j in combinations(range(10), 2)}
        assert mass == sum(overlaps.values()) == witness["collision_mass"] >= 20
        tree = tuple((int(a), int(b)) for a, b in witness["subset_tree"])
        assert len(tree) == cert.hunter.graph_rank(10, tree) == 9
        for k in range(1, 4):
            graph = [edge for edge, value in overlaps.items() if value >= k]
            assert sum(overlaps[edge] >= k for edge in tree) == cert.hunter.graph_rank(10, graph)
        weight = sum(PHI[overlaps[edge]] for edge in tree)
        assert weight == witness["phi_tree_weight"] >= 3_767_400
        full = cast(list[tuple[int, int]], witness["extended_tree"])
        assert len(full) == cert.hunter.graph_rank(18, full) == 17
        types = tuple(i for i, n in enumerate(vector) for _ in range(n))
        full_weight = 0
        for left, right in full:
            cells = tuple(
                len(tickets[left] & tickets[right] & set(c)) for c in cert.hunter.CELL_LABELS
            )
            value = cert.six.residual_pair_intersection(
                types[left], types[right], cast(tuple[int, int, int, int], cells)
            )
            assert value >= 0
            full_weight += value
        assert full_weight == witness["extended_tree_exact_weight"] >= weight
    assert (
        cert.digest(tuple((row["counts"], row["support_witness"]) for row in rows))
        == result["RECORDED_WITNESSES_SHA256"]
    )


def test_untouched_200_members_207_vectors_and_all_sixteen_top16_certificates(
    result: dict[str, Any],
) -> None:
    members = cert.region_members()
    targets = set(result["TWO_BAND_MEMBER_IDS"])
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert {r["member_id"] for r in rows if r["final_bound"] != r["prior_bound"]} == targets
    for m, row in zip(members, rows, strict=True):
        assert row["raw_bound"] == m.raw_bound and row["prior_bound"] == m.final_bound
        if row["member_id"] not in targets:
            assert row["final_bound"] == m.final_bound
    remainder = [r for r in rows if r["member_id"] not in targets]
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 200
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 207
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355_379_038
    )
    original = cert.top16_authority()[1]["NEW_MEMBER_CERTIFICATES"]
    assert len(original) == result["PREVIOUS_SEALED_MEMBER_COUNT"] == 16
    assert cert.digest(original) == result["PREVIOUS_SEALED_CERTIFICATES_SHA256"]
    bounds = {cert.dense(r["witness_counts"]): r["final_bound"] for r in rows}
    for record in original:
        vector = cert.dense(record["member"]["witness_counts"])
        assert cert.member_id(vector) not in targets
        assert bounds[vector] == record["member_new_bound"]
        for witness in record["support_witnesses"]:
            cert.top16.validate_support(cert.dense(witness["counts"]), witness)
    assert all(bounds[v] == b for v, b in cert.carried_certificates())
    assert (
        cert.digest(
            tuple(
                (m.counts, m.represented_vector_count, m.raw_bound, bounds[m.counts])
                for m in members
                if cert.member_id(m.counts) not in targets
            )
        )
        == result["PRESERVED_MEMBER_BOUNDS_SHA256"]
    )
    for path, fingerprint in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == fingerprint


def test_independent_complete_23_state_and_family_owner_transition(result: dict[str, Any]) -> None:
    authority = cert.source_authority()
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert result["START_STATE_TERMS"] == authority["FINAL_STATE_TERMS"]
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_COMPLETE_R3_UB"] == 355_510_148
    state = max(r["final_bound"] for r in result["COMPLETE_REGION_MEMBERS"])
    assert after[cert.TARGET_STATE_ID] == state == result["FINAL_TARGET_STATE_BOUND"] == 355_379_038
    classified = cert.six.classified_terms()
    assert len(classified) == result["CLASSIFIED_TERM_COUNT"] == 56550
    terms = [*after.items(), (cert.r24.TAIL_ID, result["TAIL_BOUND"]), *classified]
    maximum = max(b for _, b in terms)
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355_505_920
    assert [k for k, b in terms if b == maximum] == result["FINAL_OWNER_IDS"] == [FINAL_OWNER]
    assert result["START_FAMILY_MAX_RECOMPUTATION"]["OWNER_IDS"] == [cert.TARGET_STATE_ID]
    assert result["REMAINING_GAP"] == maximum - 313_263_888 == 42_242_032
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_AGGREGATE", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == authority[key]
    assert result["CLASSIFIED_MAX"] == max(b for _, b in classified)
    assert result["TAIL_BOUND"] == 354_039_277


def test_invalid_applicability_and_incomplete_target_vector_rejected() -> None:
    member = cert.target_bands(cert.region_members())[0][1][0]
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


def test_exact_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 14,
        "vectors": 14,
        "region_members": 214,
        "region_vectors": 221,
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
        "source_top16",
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
        proof["threshold_cases"][0]["rank_lower_bounds"][0] -= 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "case_count":
        proof["all_admissible_threshold_cases"] -= 1
    elif mutation == "event":
        row["ten_event_types"][0] = 1
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
            if r["member_id"] not in bad["TWO_BAND_MEMBER_IDS"]
        )["final_bound"] -= 1
    elif mutation == "region_vector":
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["represented_vector_count"] == 2)[
            "represented_vectors"
        ].pop()
    elif mutation == "sealed":
        bad["PREVIOUS_SEALED_CERTIFICATES_SHA256"] = "0" * 64
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
    elif mutation == "source_top16":
        bad["TOP16_SOURCE_IDENTITY"]["result_sha256"] = "0" * 64
    else:
        bad["RECORDED_WITNESSES_SHA256"] = "0" * 64
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


def test_immutable_top16_donor_tampering_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.top16.object_bytes
    relative = cert.top16.source_paths("TOP16")[1]

    def wrong(head: str, path: str) -> bytes:
        data = original(head, path)
        return data + b"\n" if head == cert.top16.TOP16_DONOR_HEAD and path == relative else data

    cert.top16_authority.cache_clear()
    monkeypatch.setattr(cert.top16, "object_bytes", wrong)
    try:
        with pytest.raises(AssertionError, match="SHA mismatch"):
            cert.top16_authority()
    finally:
        cert.top16_authority.cache_clear()


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
    elif mutation == "outside_universe":
        labels = cert.hunter.CELL_LABELS
        monkeypatch.setattr(cert.hunter, "CELL_LABELS", (*labels[:3], labels[3][:-1]))
    else:
        original_family = cert.six.tail.family_maximum

        def wrong_family(tail: int, states: Any, classified: Any) -> dict[str, Any]:
            family = original_family(tail, states, classified)
            return (
                {**family, "R3_BOUND": 1}
                if dict(states)[cert.TARGET_STATE_ID] == 355_379_038
                else family
            )

        monkeypatch.setattr(cert.six.tail, "family_maximum", wrong_family)
    if mutation == "family":
        with pytest.raises(AssertionError, match="independent full Family"):
            cert.recompute_family(355_379_038)
    else:
        with pytest.raises(AssertionError):
            cert.certify_vector(member, vector, proof)


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
