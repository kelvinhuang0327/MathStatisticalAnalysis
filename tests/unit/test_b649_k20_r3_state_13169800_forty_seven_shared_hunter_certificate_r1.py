"""Independent F/G identities, complete proofs, replay and semantic rejection."""

from __future__ import annotations

import copy
import itertools
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import (
    b649_k20_r3_state_13169800_forty_seven_shared_hunter_certificate_r1 as cert,
)

PHI = (107_800, 574_000, 1_691_620, 3_451_651)


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, heavy refinement or full outcome enumeration")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    # Guard the entire cold-source replay, rather than only a warm build.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        return cert.build_result()


def test_immutable_authority_and_full_compression_replay(result: dict[str, Any]) -> None:
    assert cert.verify_base_authority() == {
        "HEAD": "5cfacd03b1026274577f6647083684b53b00bcae",
        "TREE": "fd5a8b3cf7aafe4617afad620ccfce196ee9b8ca",
        "RESULT_SHA256": "f059ab046a75a3c7790ae979a84ff323d44a8e7e605ee1a6042e206b6d34c06a",
    }
    assert sha256(cert.prior.RESULT_PATH.read_bytes()).hexdigest() == cert.BASE_RESULT_SHA256
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    members, recovered = cert.region_members(), cert.represented_vectors()
    flat = [v for vectors in recovered.values() for v in vectors]
    assert len(members) == len(recovered) == len(result["COMPLETE_REGION_MEMBERS"]) == 989
    assert len(flat) == len(set(flat)) == result["REGION_REPRESENTED_VECTOR_COUNT"] == 1072
    assert cert.catalog.region_fingerprint(members) == result["REGION_SHA256"]
    assert recovered == cert.prior.represented_vectors()
    for member, row in zip(members, result["COMPLETE_REGION_MEMBERS"], strict=True):
        vectors = tuple(cert.dense(v) for v in row["represented_vectors"])
        assert vectors == recovered[member.counts] and min(vectors) == member.counts
        assert len(vectors) == member.represented_vector_count == row["represented_vector_count"]
        signature = cert.hunter.eleven.compression_signature(cert.catalog.rebuild_member(member))
        assert cert.catalog.normalized(signature) == row["compression_signature"]
        for vector in vectors:
            state = cert.catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            assert cert.hunter.eleven.compression_signature(state) == signature
            assert cert.hunter.r14.raw_bound(state) == row["raw_bound"] == member.raw_bound
            assert len(vector) == 30 and sum(vector) == 18 and min(vector) >= 0


def test_exact_all_four_F_layers_and_seven_G_members(result: dict[str, Any]) -> None:
    families = cert.target_families(cert.region_members())
    expected_f: set[tuple[int, ...]] = set()
    expected_g: set[tuple[int, ...]] = set()
    for t, k, j in itertools.product(range(4), range(5), (6, 9)):
        vector = [0] * 30
        vector[0], vector[1], vector[4] = 10, k, 4 - k
        vector[5], vector[16], vector[j] = 3 - t, t, 1
        expected_f.add(tuple(vector))
    for t in range(7):
        vector = [0] * 30
        vector[0], vector[5], vector[16] = 12, 6 - t, t
        expected_g.add(tuple(vector))
    assert {m.counts for m in families["F"]} == expected_f
    assert {m.counts for m in families["G"]} == expected_g
    assert not expected_f & expected_g
    assert len(expected_f) == result["FAMILY_F_MEMBER_COUNT"] == 40
    assert len(expected_g) == result["FAMILY_G_MEMBER_COUNT"] == 7
    assert len(result["MEMBER_CERTIFICATES"]) == result["TARGET_MEMBER_COUNT"] == 47
    assert result["TARGET_VECTOR_COUNT"] == 47
    for key, rows in families.items():
        assert [cert.member_id(m.counts) for m in rows] == result["FAMILY_MEMBER_IDS"][key]
        for member in rows:
            assert cert.represented_vectors()[member.counts] == (member.counts,)
            t = member.counts[16]
            expected_prior = (355_466_398 if key == "F" else 355_464_676) - 448 * t
            assert member.final_bound == member.raw_bound == expected_prior
            with pytest.raises(AssertionError, match="F/G"):
                cert.target_families(tuple(m for m in cert.region_members() if m != member))
    duplicate = (*cert.region_members(), families["F"][0])
    with pytest.raises(AssertionError, match="F/G"):
        cert.target_families(duplicate)


@pytest.mark.parametrize(
    ("n", "mass", "cases", "floor", "rank"),
    [(10, 20, 16_982, 3_767_400, 6), (12, 32, 51_257, 4_915_400, 8)],
)
def test_complete_integer_threshold_minimization_independently(
    result: dict[str, Any], n: int, mass: int, cases: int, floor: int, rank: int
) -> None:
    proof = result["TEN_EVENT_PROOF" if n == 10 else "TWELVE_EVENT_PROOF"]
    assert proof == cert.hunter_proof(n)
    assert proof["pair_floors"] == list(PHI)
    assert proof["pair_rows"] == [[0, 0, 0, 0, 0, k, cost] for k, cost in enumerate(PHI)]
    assert proof["type_cells"] == [0, 0, 0, 6]
    outside = set(range(49)) - (cert.hunter.ANCHOR_A | cert.hunter.ANCHOR_B)
    assert set(proof["outside_labels"]) == outside == set(cert.hunter.CELL_LABELS[3])
    assert len(outside) == proof["outside_label_count"] == 40
    assert proof["outside_incidences"] == 6 * n
    assert proof["balanced_frequencies"] == [[1, 40 - mass], [2, mass]]
    assert proof["collision_mass_floor"] == mass == 6 * n - 40
    # A transfer from a larger frequency to a smaller one reduces collision mass.
    for high in range(2, n + 1):
        for low in range(high - 1):
            assert comb(high, 2) + comb(low, 2) > comb(high - 1, 2) + comb(low + 1, 2)
    for left in range(n):
        for right in range(n - left):
            assert comb(left + 1, 2) + comb(right + 1, 2) <= comb(left + right + 1, 2)
    capacity = comb(n, 2)
    ranks = [min(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(capacity + 1)]
    best = None
    case_counts = [0, 0, 0]
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < mass:
                    continue
                value = (n - 1) * PHI[0] + sum(
                    (PHI[k + 1] - PHI[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                )
                assert value >= floor
                candidate = (value, (e1, e2, e3))
                best = candidate if best is None else min(best, candidate)
                case_counts[2 if e3 else int(e2 > 0)] += 1
    assert best == (floor, (mass, 0, 0))
    assert sum(case_counts) == cases == proof["all_admissible_threshold_cases"]
    assert case_counts == proof["admissible_case_counts"]
    assert proof["integer_minimizer"]["rank_floors"] == [rank, 0, 0]
    assert proof["hunter_floor"] == floor
    assert proof["rank_algebra_rows"] == capacity + 1
    for overlap, cost in enumerate(PHI):
        cells = (0, 0, 0, overlap)
        tickets = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert cert.six.residual_pair_intersection(0, 0, cells) == cost
        assert (
            cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)) == cost
        )


def test_all_47_event_gates_max_once_and_legal_witnesses(result: dict[str, Any]) -> None:
    carried = cert.carried_vectors()
    rows = [v for m in result["MEMBER_CERTIFICATES"] for v in m["vector_certificates"]]
    assert len(rows) == 47
    for member in result["MEMBER_CERTIFICATES"]:
        assert len(member["vector_certificates"]) == member["represented_vector_count"] == 1
        row = member["vector_certificates"][0]
        vector = cert.dense(row["counts"])
        n, floor, mass = (10, 3_767_400, 20) if member["family"] == "F" else (12, 4_915_400, 32)
        assert vector[0] == row["type0_count"] == row["event_count"] == n
        assert row["selected_event_indices"] == list(range(n))
        assert row["selected_event_types"] == [0] * n
        assert row["outside_incidences"] == 6 * n and row["collision_mass_floor"] == mass
        assert row["residual_event_definition"] == cert.RESIDUAL_EVENT_DEFINITION
        corrections = row["corrections"]
        assert {k: v for k, v in corrections.items() if k != "NEW_HUNTER"} == carried[vector][
            "corrections"
        ]
        assert corrections["NEW_HUNTER"] == row["combined_correction"] == floor
        assert row["combined_correction"] == max(corrections.values()) != sum(corrections.values())
        assert row["vector_new_bound"] == row["uncorrected_anchor_bound"] - floor
        assert (
            row["prior_applied_correction"]
            == row["uncorrected_anchor_bound"] - member["member_prior_bound"]
        )
        expected = (355_142_998 if n == 10 else 355_141_276) - 448 * vector[16]
        assert row["vector_new_bound"] == member["member_new_bound"] == expected
        support = tuple(tuple(int(x) for x in ticket) for ticket in row["support_witness"])
        assert row["support_witness"] == carried[vector]["support_witness"]
        assert row["support_sha256"] == carried[vector]["support_sha256"] == cert.digest(support)
        assert cert.hunter.r8.validate_support_assignment(vector, support)
        tickets = tuple(frozenset(t) for t in support)
        all_tickets = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B, *tickets)
        assert len(set(all_tickets)) == 20
        assert all(len(t) == 6 and t <= set(range(49)) for t in all_tickets)
        assert max(len(a & b) for a, b in combinations(all_tickets, 2)) == 3
        subset = tickets[:n]
        assert all(t <= set(cert.hunter.CELL_LABELS[3]) for t in subset)
        overlaps = {(a, b): len(subset[a] & subset[b]) for a, b in combinations(range(n), 2)}
        collisions = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
        witness = row["witness_analysis"]
        assert collisions == sum(overlaps.values()) == witness["collision_mass"] >= mass
        tree = tuple((int(a), int(b)) for a, b in witness["subset_tree"])
        assert len(tree) == cert.hunter.graph_rank(n, tree) == n - 1
        for k in range(1, 4):
            edges = [edge for edge, overlap in overlaps.items() if overlap >= k]
            assert sum(overlaps[e] >= k for e in tree) == cert.hunter.graph_rank(n, edges)
        weight = sum(PHI[overlaps[e]] for e in tree)
        assert weight == witness["phi_tree_weight"] >= floor
        full = cast(list[tuple[int, int]], witness["extended_tree"])
        assert len(full) == cert.hunter.graph_rank(18, full) == 17
        types = tuple(i for i, count in enumerate(vector) for _ in range(count))
        full_weight = 0
        for a, b in full:
            cells = tuple(len(tickets[a] & tickets[b] & set(c)) for c in cert.hunter.CELL_LABELS)
            cost = cert.six.residual_pair_intersection(
                types[a], types[b], cast(tuple[int, int, int, int], cells)
            )
            assert cost >= 0
            full_weight += cost
        assert full_weight == witness["extended_tree_exact_weight"] >= weight
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_942_members_1025_vectors_and_previous_certificates_preserved(
    result: dict[str, Any],
) -> None:
    members = cert.region_members()
    targets = {r["member_id"] for r in result["MEMBER_CERTIFICATES"]}
    remainder: list[dict[str, Any]] = []
    for member, row in zip(members, result["COMPLETE_REGION_MEMBERS"], strict=True):
        assert row["prior_bound"] == member.final_bound
        if row["member_id"] not in targets:
            assert row["final_bound"] == member.final_bound
            remainder.append(row)
    changed = {
        r["member_id"]
        for r in result["COMPLETE_REGION_MEMBERS"]
        if r["final_bound"] != r["prior_bound"]
    }
    assert changed == targets and len(changed) == 47
    assert len(remainder) == result["PRESERVED_MEMBER_COUNT"] == 942
    assert (
        sum(r["represented_vector_count"] for r in remainder)
        == result["PRESERVED_VECTOR_COUNT"]
        == 1025
    )
    assert (
        max(r["final_bound"] for r in remainder) == result["PRESERVED_REMAINDER_MAX"] == 355_368_426
    )
    assert (
        result["PREDECESSOR_MEMBER_CERTIFICATES"] == cert.source_authority()["MEMBER_CERTIFICATES"]
    )
    originals = {
        "NINE_EVENT": cert.prior.region_authority()["MEMBER_CERTIFICATES"],
        "ELEVEN_EVENT": cert.prior.region.source_authority()["MEMBER_CERTIFICATES"],
        "TEN_EVENT": cert.source_authority()["MEMBER_CERTIFICATES"],
    }
    assert result["PREVIOUS_CERTIFICATE_COUNTS"] == {
        "NINE_EVENT": 989,
        "ELEVEN_EVENT": 7,
        "TEN_EVENT": 40,
    }
    for key, original in originals.items():
        assert cert.json_digest(original) == result["PREVIOUS_CERTIFICATES_SHA256"][key]
        for record in original:
            for row in record["vector_certificates"]:
                if "support_witness" in row:
                    assert cert.hunter.r8.validate_support_assignment(
                        cert.dense(row["counts"]), tuple(tuple(t) for t in row["support_witness"])
                    )
    for path, fingerprint in result["ALL_CARRIED_CERTIFICATES_SHA256"].items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == fingerprint
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0
    assert result["OUTCOME_ENUMERATION_USED"] is False
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"


def test_all_23_states_and_standalone_R3_accounting(result: dict[str, Any]) -> None:
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert result["START_STATE_TERMS"] == cert.source_authority()["FINAL_STATE_TERMS"]
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert {key for key in before if before[key] != after[key]} == {cert.TARGET_STATE_ID}
    assert before[cert.TARGET_STATE_ID] == result["START_STATE_BOUND"] == 355_466_398
    assert (
        max(r["member_new_bound"] for r in result["MEMBER_CERTIFICATES"])
        == result["TARGET_NEW_MEMBER_MAX"]
        == 355_142_998
    )
    assert (
        max(r["final_bound"] for r in result["COMPLETE_REGION_MEMBERS"])
        == after[cert.TARGET_STATE_ID]
        == result["FINAL_TARGET_STATE_UB"]
        == 355_368_426
    )
    classified = cert.six.classified_terms()
    assert len(classified) == result["CLASSIFIED_TERM_COUNT"] == 56_550
    assert cert.digest(classified) == result["CLASSIFIED_TERMS_SHA256"]
    terms = [*after.items(), (cert.r24.TAIL_ID, result["TAIL_BOUND"]), *classified]
    maximum = max(b for _, b in terms)
    assert (
        maximum
        == result["START_COMPLETE_R3_UB"]
        == result["FINAL_STANDALONE_COMPLETE_R3_UB"]
        == 355_497_359
    )
    assert (
        result["FINAL_OWNER_IDS"]
        == sorted(k for k, b in terms if b == maximum)
        == ["state:s2-12695020-s3-735532"]
    )
    for key in ("TAIL_BOUND", "CLASSIFIED_MAX", "CLASSIFIED_AGGREGATE", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == cert.source_authority()[key]
    assert (
        result["COMPLETE_UPDATED_BOUNDS_SHA256"]
        == ("9a32444dcdde9badb8896e23a4ea2c466757818d8e61d7892cad2f3a7551987d")
        == cert.digest(
            tuple(
                (m.counts, row["final_bound"])
                for m, row in zip(
                    cert.region_members(), result["COMPLETE_REGION_MEMBERS"], strict=True
                )
            )
        )
    )


def test_exact_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 47,
        "vectors": 47,
        "region_members": 989,
        "region_vectors": 1072,
    }
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"


@pytest.mark.parametrize("family", ["F", "G"])
def test_wrong_event_count_bad_proof_and_missing_member_vectors_rejected(family: str) -> None:
    member = cert.target_families(cert.region_members())[family][0]
    vector = member.counts
    proof = cert.hunter_proof(vector[0])
    for invalid in ((), (vector, vector)):
        with pytest.raises(AssertionError, match="represented-vector"):
            cert.certify_member(member, invalid, proof)
    wrong = list(vector)
    wrong[0] -= 1
    wrong[1] += 1
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(member, tuple(wrong), proof)
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(member, vector, cert.hunter_proof(12 if family == "F" else 10))
    bad = copy.deepcopy(proof)
    bad["residual_event_definition"] = "E_i"
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(member, vector, bad)
    with pytest.raises(AssertionError, match="unsupported"):
        cert.hunter_proof(11)


@pytest.mark.parametrize("relative", sorted(cert.UPSTREAM_SHA256))
def test_source_tampering_rejected_with_warm_caches(
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


@pytest.mark.parametrize("target_only", [False, True])
def test_missing_recovered_vector_rejected(
    monkeypatch: pytest.MonkeyPatch, target_only: bool
) -> None:
    original = cert.catalog.r17.represented_vectors

    def missing(members: Any) -> dict[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        recovered = original(members)
        member = (
            cert.target_families(cert.region_members())["F"][0]
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


@pytest.mark.parametrize(
    "mutation",
    [
        "base",
        "pair",
        "ten_floor",
        "twelve_floor",
        "mass",
        "rank",
        "cases",
        "event",
        "signature",
        "missing_member",
        "duplicate_member",
        "missing_vector",
        "missing_row",
        "max_sum",
        "witness",
        "witness_digest",
        "remainder",
        "region_vector",
        "digest",
        "previous",
        "state_terms",
        "standalone",
        "owner",
        "tail",
        "classified",
        "aggregate",
    ],
)
def test_tampered_certificate_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    member = bad["MEMBER_CERTIFICATES"][0]
    row = member["vector_certificates"][0]
    proof = bad["TEN_EVENT_PROOF"]
    if mutation == "base":
        bad["BASE_TREE"] = "0" * 40
    elif mutation == "pair":
        proof["pair_rows"][0][6] += 1
    elif mutation == "ten_floor":
        proof["hunter_floor"] += 1
    elif mutation == "twelve_floor":
        bad["TWELVE_EVENT_PROOF"]["hunter_floor"] += 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "rank":
        proof["integer_minimizer"]["rank_floors"][0] -= 1
    elif mutation == "cases":
        bad["TWELVE_EVENT_PROOF"]["all_admissible_threshold_cases"] -= 1
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
    elif mutation == "missing_row":
        member["vector_certificates"].pop()
    elif mutation == "max_sum":
        row["combined_correction"] = sum(row["corrections"].values())
    elif mutation == "witness":
        row["support_witness"][0][0] = 99
    elif mutation == "witness_digest":
        row["support_sha256"] = "0" * 64
    elif mutation == "remainder":
        targets = set(itertools.chain.from_iterable(bad["FAMILY_MEMBER_IDS"].values()))
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["member_id"] not in targets)[
            "final_bound"
        ] -= 1
    elif mutation == "region_vector":
        next(r for r in bad["COMPLETE_REGION_MEMBERS"] if r["represented_vector_count"] == 2)[
            "represented_vectors"
        ].pop()
    elif mutation == "digest":
        bad["COMPLETE_UPDATED_BOUNDS_SHA256"] = "0" * 64
    elif mutation == "previous":
        bad["PREVIOUS_CERTIFICATES_SHA256"]["ELEVEN_EVENT"] = "0" * 64
    elif mutation == "state_terms":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "standalone":
        bad["FINAL_STANDALONE_COMPLETE_R3_UB"] = 355_406_030
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [cert.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "classified":
        bad["CLASSIFIED_TERM_COUNT"] -= 1
    else:
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
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
        "carried_credit",
    ],
)
def test_non_equivalent_semantic_mutations_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str, result: dict[str, Any]
) -> None:
    member = cert.target_families(cert.region_members())["G"][0]
    proof = copy.deepcopy(cert.hunter_proof(12))
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
    elif mutation in ("threshold_census", "inflated_floor"):
        original_minimum = cert.hunter.minimum_tree_correction

        def wrong_minimum(floors: Any, mass: int, vertices: int) -> Any:
            row = original_minimum(floors, mass, vertices)
            return (
                replace(row, census_size=row.census_size - 1)
                if mutation == "threshold_census"
                else replace(row, correction=row.correction + 1)
            )

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", wrong_minimum)
    elif mutation == "outside_universe":
        labels = cert.hunter.CELL_LABELS
        monkeypatch.setattr(cert.hunter, "CELL_LABELS", (*labels[:3], labels[3][:-1]))
    elif mutation == "carried_credit":
        carried = copy.deepcopy(cert.carried_vectors())
        carried[member.counts]["combined_correction"] -= 1
        monkeypatch.setattr(cert, "carried_vectors", lambda: carried)
    else:
        original_family = cert.six.tail.family_maximum

        def wrong_family(tail: int, states: Any, classified: Any) -> dict[str, Any]:
            family = original_family(tail, states, classified)
            return (
                {**family, "R3_BOUND": 1}
                if dict(states)[cert.TARGET_STATE_ID] == 355_368_426
                else family
            )

        monkeypatch.setattr(cert.six.tail, "family_maximum", wrong_family)
    if mutation == "family":
        with pytest.raises(AssertionError, match="independent full Family"):
            cert.recompute_family(355_368_426)
    else:
        # Clear only the task's proof memo; mutated dependencies must be reobserved.
        cert.hunter_proof.cache_clear()
        try:
            with pytest.raises(AssertionError):
                cert.certify_vector(member, member.counts, proof)
        finally:
            cert.hunter_proof.cache_clear()
    assert result["TASK_STATUS"] == "SUCCESS"
