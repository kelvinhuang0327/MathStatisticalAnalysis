"""Independent five-band arithmetic, complete coverage and semantic fault checks."""

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

from lottolab.research import b649_k20_r3_state_12695020_five_band_nine_event_certificate_r1 as cert

PHI = (107_800, 574_000, 1_691_620, 3_451_651)
OWNER = "state:s2-14122976-s3-1005536"


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_immutable_authority(result: dict[str, Any]) -> None:
    assert cert.verify_base_authority() == {
        "HEAD": "cda19c6da7d9a93fd120df6797652700e2893a21",
        "TREE": "8eab0f498383beb5ad6cb3ffe1d73067d41fa885",
        "RESULT_SHA256": "56d48e21ce83f62da991c6b98f8d1d1b1970755fd1fb66e417acaa030bd77e96",
    }
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    assert (
        result["REGION_IDENTITY"]
        == result["REGION_SHA256"]
        == ("46023fc93f2fd7d9b211d29494d05d8f6bfd4867992b0121cd8db0b7def5cd5b")
    )
    assert cert.source_authority()["FINAL_OWNER_IDS"] == [cert.TARGET_STATE_ID]


def test_complete_region_vectors_and_compression_signatures(result: dict[str, Any]) -> None:
    members, recovered = cert.region_members(), cert.represented_vectors()
    assert len(members) == len(recovered) == len(result["COMPLETE_REGION_MEMBERS"]) == 1222
    flat = [v for vectors in recovered.values() for v in vectors]
    assert len(flat) == len(set(flat)) == result["REGION_REPRESENTED_VECTOR_COUNT"] == 1325
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
            rebuilt = cert.catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            assert cert.hunter.eleven.compression_signature(rebuilt) == signature
            assert cert.hunter.r14.raw_bound(rebuilt) == member.raw_bound == row["raw_bound"]


def test_all_five_bands_and_exact_fifty_vector_identities(result: dict[str, Any]) -> None:
    bands = cert.target_bands(cert.region_members())
    recovered = cert.represented_vectors()
    assert result["FIVE_BAND_MEMBER_COUNT"] == 45
    assert result["FIVE_BAND_VECTOR_COUNT"] == 50
    assert len(result["DOUBLE_VECTOR_MEMBER_IDS"]) == 5
    records = {r["member_id"]: r for r in result["MEMBER_CERTIFICATES"]}
    for t, (bound, members) in enumerate(bands):
        assert bound == 355_537_140 - 448 * t
        assert len(members) == 9 and sum(m.represented_vector_count for m in members) == 10
        actual = {v for m in members for v in recovered[m.counts]}
        expected: set[tuple[int, ...]] = set()
        for k in range(5):
            for selector in (2, 8):
                counts = [0] * 30
                counts[0], counts[1], counts[4] = 9, k, 4 - k
                counts[selector], counts[5], counts[16] = 1, 4 - t, t
                expected.add(tuple(counts))
        assert actual == expected
        double = [m for m in members if m.represented_vector_count == 2]
        assert len(double) == 1
        assert len(recovered[double[0].counts]) == 2
        assert double[0].counts[1:5] == (1, 1, 0, 3)
        for m in members:
            record = records[cert.member_id(m.counts)]
            assert (
                tuple(cert.dense(v) for v in record["represented_vectors"]) == recovered[m.counts]
            )
            assert len(record["vector_certificates"]) == m.represented_vector_count
    member = bands[0][1][0]
    with pytest.raises(AssertionError, match="five-band"):
        cert.target_bands(tuple(m for m in cert.region_members() if m != member))


def test_four_exact_pairs_residual_definition_and_applicability(result: dict[str, Any]) -> None:
    proof = result["NINE_EVENT_PROOF"]
    assert proof == cert.shared.nine_event_proof() == cert.nine_event_proof()
    assert proof["type_cells"] == [0, 0, 0, 6]
    assert proof["pair_floors"] == list(PHI)
    assert proof["pair_overlap_ceiling"] == cert.hunter.family_pair_overlap_ceiling() == 3
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
            assert sum(vector) == 18 and vector[0] == row["type0_count"] == 9
            assert row["nine_event_indices"] == list(range(9))
            assert row["nine_event_types"] == [0] * 9
            assert row["residual_event_definition"] == cert.RESIDUAL_EVENT_DEFINITION
            assert row["outside_incidences"] == 54 and row["collision_mass_floor"] == 14
            assert row["applicability_status"] == "PASS"


def test_independent_collision_threshold_rank_and_tree_proofs(result: dict[str, Any]) -> None:
    proof = result["NINE_EVENT_PROOF"]
    assert proof["outside_label_count"] == 40
    assert proof["balanced_frequencies"] == [[1, 26], [2, 14]]
    assert sum(count * frequency for frequency, count in proof["balanced_frequencies"]) == 54
    assert (
        sum(count * comb(frequency, 2) for frequency, count in proof["balanced_frequencies"]) == 14
    )
    assert proof["collision_mass_floor"] == 54 - 40 == 14
    for a in range(9):
        for b in range(9 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    rho = [next(r for r in range(9) if comb(r + 1, 2) >= e) for e in range(37)]
    assert rho == [cert.hunter.rank_floor(e) for e in range(37)]
    cases: list[tuple[int, tuple[int, int, int]]] = []
    for e1 in range(37):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < 14:
                    continue
                ranks = (rho[e1], rho[e2], rho[e3])
                value = 8 * PHI[0] + sum((PHI[k] - PHI[k - 1]) * ranks[k - 1] for k in range(1, 4))
                cases.append((value, (e1, e2, e3)))
    assert len(cases) == proof["integer_minimizer"]["feasible_threshold_triples"] == 9016
    assert min(cases) == (3_193_400, (14, 0, 0))
    assert proof["integer_minimizer"]["rank_floors"] == [5, 0, 0]
    assert [r["hunter_floor"] for r in proof["threshold_cases"]] == [
        3_193_400,
        3_844_820,
        5_138_651,
    ]
    assert result["HUNTER_CORRECTION_FLOOR"] == 8 * PHI[0] + 5 * (PHI[1] - PHI[0]) == 3_193_400
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_max_replacement_and_all_expected_band_bounds(result: dict[str, Any]) -> None:
    assert result["NEW_FIVE_BAND_BOUNDS"] == [355_213_740 - 448 * t for t in range(5)]
    assert result["NEW_FIVE_BAND_MAX"] == 355_213_740
    for t, band in enumerate(result["FIVE_BANDS"]):
        members = [r for r in result["MEMBER_CERTIFICATES"] if r["member_id"] in band["member_ids"]]
        assert len(members) == 9
        for member in members:
            rows = member["vector_certificates"]
            for row in rows:
                corrections = row["corrections"]
                assert corrections["FOREST"] == row["prior_applied_correction"] == 2_870_000
                assert row["uncorrected_anchor_bound"] == 358_407_140 - 448 * t
                assert corrections["NINE_EVENT_HUNTER"] == 3_193_400
                assert row["combined_correction"] == max(corrections.values()) == 3_193_400
                assert row["combined_correction"] != sum(corrections.values())
                assert (
                    row["vector_new_bound"]
                    == row["uncorrected_anchor_bound"] - row["combined_correction"]
                )
            assert member["member_certified_correction"] == min(
                r["combined_correction"] for r in rows
            )
            assert (
                member["member_new_bound"]
                == max(r["vector_new_bound"] for r in rows)
                == band["new_bound"]
            )
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_fifty_legal_supports_collisions_nested_forests_and_extension(
    result: dict[str, Any],
) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            vector = cert.dense(row["counts"])
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            assert cert.hunter.r8.validate_support_assignment(vector, support)
            assert cert.digest(support) == row["support_sha256"]
            tickets = tuple(frozenset(t) for t in support)
            anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
            assert len(set((*anchors, *tickets))) == 20
            assert max(len(a & b) for a, b in combinations((*anchors, *tickets), 2)) == 3
            subset = tickets[:9]
            assert all(t <= set(cert.hunter.CELL_LABELS[3]) for t in subset)
            mass = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
            witness = row["witness_analysis"]
            assert (
                mass
                == sum(len(a & b) for a, b in combinations(subset, 2))
                == witness["collision_mass"]
            )
            assert mass >= 14
            overlaps = {(i, j): len(subset[i] & subset[j]) for i, j in combinations(range(9), 2)}
            tree = tuple((int(a), int(b)) for a, b in witness["subset_tree"])
            assert len(tree) == cert.hunter.graph_rank(9, tree) == 8
            for k in range(1, 4):
                graph = [edge for edge, value in overlaps.items() if value >= k]
                assert sum(overlaps[edge] >= k for edge in tree) == cert.hunter.graph_rank(9, graph)
            weight = sum(PHI[overlaps[edge]] for edge in tree)
            assert weight == witness["phi_tree_weight"] >= 3_193_400
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


def test_all_1177_untouched_bounds_and_335_sealed_certificates(result: dict[str, Any]) -> None:
    members = cert.region_members()
    targets = {r["member_id"] for r in result["MEMBER_CERTIFICATES"]}
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert {r["member_id"] for r in rows if r["final_bound"] != r["prior_bound"]} == targets
    for m, row in zip(members, rows, strict=True):
        assert row["raw_bound"] == m.raw_bound and row["prior_bound"] == m.final_bound
        if row["member_id"] not in targets:
            assert row["final_bound"] == m.final_bound
    remainder = [r for r in rows if r["member_id"] not in targets]
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 1177
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 1275
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355_497_359
    )
    sealed = cert.carried_certificates()
    assert len(sealed) == result["PREVIOUS_SEALED_MEMBER_COUNT"] == 335
    assert cert.digest(sealed) == result["PREVIOUS_SEALED_CERTIFICATES_SHA256"]
    bounds = {cert.dense(r["witness_counts"]): r["final_bound"] for r in rows}
    assert all(bounds[v] == b for _, v, b, _ in sealed)
    assert not {v for _, v, _, _ in sealed} & {
        cert.dense(r["witness_counts"]) for r in result["MEMBER_CERTIFICATES"]
    }
    for path, fingerprint in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == fingerprint


def test_independent_complete_state_and_family_owner_recomputation(result: dict[str, Any]) -> None:
    authority = cert.source_authority()
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert result["START_STATE_TERMS"] == authority["FINAL_STATE_TERMS"]
    assert {k for k in before if before[k] != after[k]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_COMPLETE_R3_UB"] == 355_537_140
    state = max(r["final_bound"] for r in result["COMPLETE_REGION_MEMBERS"])
    assert after[cert.TARGET_STATE_ID] == state == result["FINAL_TARGET_STATE_UB"] == 355_497_359
    classified = cert.six.classified_terms()
    assert len(classified) == result["CLASSIFIED_TERM_COUNT"] == 56550
    terms = [*after.items(), (cert.r24.TAIL_ID, result["TAIL_BOUND"]), *classified]
    maximum = max(b for _, b in terms)
    assert maximum == result["FINAL_COMPLETE_R3_UB"] == 355_510_148
    assert [k for k, b in terms if b == maximum] == result["FINAL_OWNER_IDS"] == [OWNER]
    assert result["REMAINING_GAP"] == maximum - 313_263_888 == 42_246_260
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_AGGREGATE", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == authority[key]
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_MAX"] == max(b for _, b in classified)


def test_invalid_applicability_signature_and_incomplete_double_vector_rejected() -> None:
    member = next(
        m
        for _, rows in cert.target_bands(cert.region_members())
        for m in rows
        if m.represented_vector_count == 2
    )
    vectors, proof = cert.represented_vectors()[member.counts], cert.nine_event_proof()
    for invalid in ((), vectors[:1], (vectors[0], vectors[0]), tuple(reversed(vectors))):
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
        "members": 45,
        "vectors": 50,
        "region_members": 1222,
        "region_vectors": 1325,
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
        "double_vector",
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
    ],
)
def test_tampered_certificate_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    proof = bad["NINE_EVENT_PROOF"]
    member = next(r for r in bad["MEMBER_CERTIFICATES"] if r["represented_vector_count"] == 2)
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
        row["nine_event_types"][0] = 1
    elif mutation == "signature":
        row["compression_signature"][0] = -1
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "double_vector":
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
            if r["member_id"] not in {r["member_id"] for r in bad["MEMBER_CERTIFICATES"]}
        )["final_bound"] -= 1
    elif mutation == "region_vector":
        bad["COMPLETE_REGION_MEMBERS"][-1]["represented_vectors"].pop()
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


@pytest.mark.parametrize(
    "mutation",
    ["max_sum", "pair", "mass", "rank", "event", "signature", "threshold_tree", "family"],
)
def test_semantic_algorithm_mutations_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    member = cert.target_bands(cert.region_members())[0][1][0]
    vector, proof = member.counts, cert.nine_event_proof()
    if mutation == "max_sum":

        def add(values: Mapping[str, int]) -> int:
            return sum(values.values())

        monkeypatch.setattr(cert.hunter, "combine_corrections", add)
    elif mutation == "pair":
        original_pair = cert.hunter.exact_pair_rows

        def wrong(pairs: tuple[tuple[int, int], ...]) -> tuple[tuple[int, ...], ...]:
            return tuple((*r[:6], r[6] + 1) for r in original_pair(pairs))

        monkeypatch.setattr(cert.hunter, "exact_pair_rows", wrong)
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
    else:
        original_family = cert.six.tail.family_maximum

        def wrong_family(tail: int, states: Any, classified: Any) -> dict[str, Any]:
            family = original_family(tail, states, classified)
            return (
                {**family, "R3_BOUND": 1}
                if dict(states)[cert.TARGET_STATE_ID] == 355_497_359
                else family
            )

        monkeypatch.setattr(cert.six.tail, "family_maximum", wrong_family)
    if mutation == "family":
        with pytest.raises(AssertionError, match="independent full Family"):
            cert.recompute_family(355_497_359)
    else:
        with pytest.raises(AssertionError):
            cert.certify_vector(member, vector, proof)


def test_missing_second_recovered_vector_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.catalog.r17.represented_vectors

    def missing(members: Any) -> dict[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        recovered = original(members)
        key = next(
            m.counts
            for _, rows in cert.target_bands(cert.region_members())
            for m in rows
            if m.represented_vector_count == 2
        )
        recovered[key] = recovered[key][:1]
        return recovered

    cert.represented_vectors.cache_clear()
    monkeypatch.setattr(cert.catalog.r17, "represented_vectors", missing)
    try:
        with pytest.raises(AssertionError, match="represented-vector coverage"):
            cert.represented_vectors()
    finally:
        cert.represented_vectors.cache_clear()


def test_strongest_vector_mutation_rejected(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    member = next(
        m
        for _, rows in cert.target_bands(cert.region_members())
        for m in rows
        if m.represented_vector_count == 2
    )
    record = next(
        r for r in result["MEMBER_CERTIFICATES"] if r["member_id"] == cert.member_id(member.counts)
    )
    rows = copy.deepcopy(record["vector_certificates"])
    rows[1]["combined_correction"] -= 1
    rows[1]["vector_new_bound"] += 1
    available = {cert.dense(row["counts"]): row for row in rows}

    def unequal(_m: Any, v: tuple[int, ...], _proof: Any) -> dict[str, Any]:
        return available[v]

    monkeypatch.setattr(cert, "certify_vector", unequal)
    vectors, proof = cert.represented_vectors()[member.counts], cert.nine_event_proof()
    assert (
        cert.certify_member(member, vectors, proof)["member_new_bound"]
        == record["member_new_bound"] + 1
    )
    monkeypatch.setattr(cert.hunter, "member_correction", max)
    with pytest.raises(AssertionError, match="weakest vector"):
        cert.certify_member(member, vectors, proof)


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
