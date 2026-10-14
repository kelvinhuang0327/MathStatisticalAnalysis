"""Independent mathematical recomputation, complete coverage and semantic faults."""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Mapping
from hashlib import sha256
from itertools import combinations, product
from math import comb
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_three_state_h0_seventy_member_certificate_r1 as cert

PHI = (107800, 574000, 1691620, 3451651)
EXPECTED = {
    cert.joint.TARGET_STATE_ID: (1222, 1325, 40, 1182, 1285, 355366249),
    cert.s141.TARGET_STATE_ID: (214, 221, 12, 202, 209, 355186748),
    cert.s135.TARGET_STATE_ID: (1427, 1543, 18, 1409, 1525, 355337794),
}


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden solver, census, chase or full official-outcome enumeration")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        patch.setattr(cert.hunter.r14, "owner_region", forbidden)
        patch.setattr(cert.hunter.r14, "s4_child", forbidden)
        patch.setattr(cert.hunter.r8, "support_model_status", forbidden)
        patch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        patch.setattr(cert.r24, "run_chase", forbidden)
        return cert.build_result()


def test_exact_immutable_base_and_predecessor_byte_replays(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert result["SOURCE_AUTHORITY"] == authority
    assert authority["HEAD"] == "561983514cb3cfd9b9bab03ed13c0e4722dd747b"
    assert authority["TREE"] == "0cd09e9ab6b2a223b6d6c0a0263a9203c362f5db"
    assert (
        authority["RESULT_SHA256"]
        == "5cfcc058fa5bedaebf9f136491ff55961009fd28f800c59495a6f5b1858bff95"
    )
    for path, fingerprint in authority["upstream_sha256"].items():
        immutable = subprocess.check_output(
            ["git", "-C", str(cert.REPO_ROOT), "show", f"{cert.BASE_HEAD}:{path}"]
        )
        assert (cert.REPO_ROOT / path).read_bytes() == immutable
        assert sha256(immutable).hexdigest() == fingerprint
    for module in cert.SOURCE_MODULES:
        assert (
            module.RESULT_PATH.read_bytes()
            == module.encode(cert.source_results()[module.TARGET_STATE_ID]).encode()
        )


@pytest.mark.parametrize("state_id", tuple(EXPECTED))
def test_complete_regions_exact_targets_and_unchanged_compressed_remainder(
    result: dict[str, Any], state_id: str
) -> None:
    region = next(r for r in result["REGIONS"] if r["state_id"] == state_id)
    members, recovered = cert.region_members(state_id), cert.represented_vectors(state_id)
    member_count, vector_count, target_count, preserved_count, preserved_vectors, bound = EXPECTED[
        state_id
    ]
    targets = cert.target_members(state_id, members)
    expected: set[tuple[int, ...]] = set()
    # Build the Packet's exact vectors independently from the implementation.
    if state_id == cert.joint.TARGET_STATE_ID:
        for j, t, extra in product(range(4), range(5), (2, 8)):
            expected.add(
                tuple(
                    dict({0: 10, 1: j, 4: 3 - j, 5: 4 - t, 16: t, extra: 1}).get(i, 0)
                    for i in range(30)
                )
            )
    elif state_id == cert.s141.TARGET_STATE_ID:
        for j, extra in product(range(6), (5, 16)):
            expected.add(
                tuple({0: 11, 1: j, 4: 5 - j, extra: 1, 25: 1}.get(i, 0) for i in range(30))
            )
    else:
        for j in range(4):
            expected.add(tuple({0: 14, 1: j, 4: 3 - j, 25: 1}.get(i, 0) for i in range(30)))
        for j, extra in product(range(7), (5, 16)):
            expected.add(
                tuple({0: 10, 1: j, 4: 6 - j, extra: 1, 20: 1}.get(i, 0) for i in range(30))
            )
    assert {m.counts for m in targets} == expected
    assert (
        region["target_member_count"]
        == region["target_vector_count"]
        == len(targets)
        == target_count
    )
    assert region["region_member_count"] == len(members) == len(recovered) == member_count
    flat = [v for group in recovered.values() for v in group]
    assert region["region_vector_count"] == len(flat) == len(set(flat)) == vector_count
    assert region["preserved_member_count"] == preserved_count
    assert region["preserved_vector_count"] == preserved_vectors
    assert region["final_state_bound"] == bound
    previous = {
        cert.dense(r["witness_counts"]): r
        for r in cert.source_results()[state_id]["COMPLETE_REGION_MEMBERS"]
    }
    remainder: list[tuple[tuple[int, ...], int]] = []
    for member, row in zip(members, region["complete_region_members"], strict=True):
        assert cert.dense(row["witness_counts"]) == member.counts
        assert tuple(cert.dense(v) for v in row["represented_vectors"]) == recovered[member.counts]
        assert row["raw_bound"] == previous[member.counts]["raw_bound"]
        assert row["prior_bound"] == previous[member.counts]["final_bound"] == member.final_bound
        if member.counts not in expected:
            assert row["final_bound"] == member.final_bound
            remainder.append((member.counts, member.final_bound))
        else:
            assert recovered[member.counts] == (member.counts,)
    assert cert.digest(tuple(remainder)) == region["preserved_member_bounds_sha256"]
    with pytest.raises(AssertionError, match="target member coverage"):
        cert.target_members(state_id, tuple(m for m in members if m != targets[0]))
    with pytest.raises(AssertionError, match="target member coverage"):
        cert.target_members(state_id, (*members, targets[0]))


@pytest.mark.parametrize(
    "n,mass,census,floor,frequencies",
    (
        (10, 20, 16982, 3767400, [[1, 20], [2, 20]]),
        (11, 26, 30216, 4341400, [[1, 14], [2, 26]]),
        (14, 48, 130472, 6063400, [[2, 36], [3, 4]]),
    ),
)
def test_independent_balanced_collisions_and_complete_threshold_minima(
    n: int, mass: int, census: int, floor: int, frequencies: list[list[int]]
) -> None:
    proof = cert.hunter_proof(n)
    assert proof["pair_rows"] == [[0, 0, 0, 0, 0, k, cost] for k, cost in enumerate(PHI)]
    assert proof["outside_incidences"] == 6 * n and proof["outside_label_count"] == 40
    assert proof["balanced_frequencies"] == frequencies
    assert proof["collision_mass_floor"] == mass
    for high in range(2, n + 1):
        for low in range(high - 1):
            assert (
                comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
                == high - low - 1
                > 0
            )
    ranks = [min(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(comb(n, 2) + 1)]
    best: tuple[int, tuple[int, int, int]] | None = None
    cases = [0, 0, 0]
    for e1 in range(comb(n, 2) + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < mass:
                    continue
                weight = (n - 1) * PHI[0] + sum(
                    (PHI[k + 1] - PHI[k]) * ranks[e] for k, e in enumerate((e1, e2, e3))
                )
                assert weight >= floor
                candidate = weight, (e1, e2, e3)
                best = candidate if best is None else min(best, candidate)
                cases[2 if e3 else int(e2 > 0)] += 1
    assert best == (floor, (mass, 0, 0))
    assert sum(cases) == proof["all_admissible_threshold_cases"] == census
    assert cases == proof["admissible_case_counts"]
    assert proof["hunter_floor"] == floor
    for k, cost in enumerate(PHI):
        cells = (0, 0, 0, k)
        assert cert.six.residual_pair_intersection(0, 0, cells) == cost
        pair = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert cert.hunter.outcome_count(pair, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)) == cost
    for a, b in product(range(n), repeat=2):
        assert comb(a + 1, 2) + comb(b + 1, 2) <= comb(a + b + 1, 2)
    if n == 14:
        assert proof["simple_incidence_minus_labels"] == 44 < mass


def test_universal_threshold_kruskal_and_pointwise_hunter_inequality() -> None:
    # Synthetic four-event graphs/atoms only; no official outcome enumeration.
    edges = tuple(combinations(range(4), 2))
    for values in product(range(4), repeat=len(edges)):
        overlaps = dict(zip(edges, values, strict=True))
        tree = cert.hunter.threshold_tree(4, overlaps)
        assert len(tree) == cert.hunter.graph_rank(4, tree) == 3
        for k in range(1, 4):
            graph = [e for e in edges if overlaps[e] >= k]
            assert sum(overlaps[e] >= k for e in tree) == cert.hunter.graph_rank(4, graph)
        weight = sum(PHI[overlaps[e]] for e in tree)
        threshold_floor = 3 * PHI[0] + sum(
            (PHI[k] - PHI[k - 1]) * cert.hunter.rank_floor(sum(v >= k for v in values))
            for k in range(1, 4)
        )
        assert weight >= threshold_floor
        for atom_mask in range(16):
            present = {i for i in range(4) if atom_mask & (1 << i)}
            induced = sum(left in present and right in present for left, right in tree)
            assert int(bool(present)) <= len(present) - induced


def test_all_seventy_events_credits_bounds_and_legal_witnesses(result: dict[str, Any]) -> None:
    total = 0
    event_counts: dict[int, int] = {}
    for region in result["REGIONS"]:
        state_id = region["state_id"]
        members = {m.counts: m for m in cert.region_members(state_id)}
        for record in region["member_certificates"]:
            vector = cert.dense(record["witness_counts"])
            member = members[vector]
            row = record["vector_certificates"][0]
            n = vector[0]
            proof = cert.hunter_proof(n)
            assert row["type0_count"] == row["event_count"] == n
            assert row["selected_event_indices"] == list(range(n))
            assert row["selected_event_types"] == [0] * n
            existing = cert.existing_corrections(state_id, member)
            assert row["prior_applied_correction"] == max(existing.values())
            assert row["corrections"] == {**existing, "TYPE0_HUNTER": proof["hunter_floor"]}
            assert row["combined_correction"] == max(row["corrections"].values())
            assert row["combined_correction"] < sum(row["corrections"].values())
            assert (
                row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
            )
            bound = min(
                member.final_bound,
                row["uncorrected_anchor_bound"] - max(row["corrections"].values()),
            )
            assert (
                row["vector_new_bound"] == record["member_new_bound"] == bound < member.final_bound
            )
            support = tuple(tuple(t) for t in row["support_witness"])
            assert cert.hunter.r8.validate_support_assignment(vector, support)
            assert cert.digest(support) == row["support_sha256"]
            subset = [set(t) for t in support[:n]]
            assert all(t <= set(proof["outside_labels"]) for t in subset)
            mass = sum(comb(sum(x in t for t in subset), 2) for x in proof["outside_labels"])
            assert mass == sum(len(a & b) for a, b in combinations(subset, 2))
            assert (
                mass == row["witness_analysis"]["collision_mass"] >= proof["collision_mass_floor"]
            )
            tree = tuple(tuple(e) for e in row["witness_analysis"]["extended_tree"])
            assert len(tree) == cert.hunter.graph_rank(18, tree) == 17
            assert (
                row["witness_analysis"]["extended_tree_exact_weight"]
                >= row["witness_analysis"]["phi_tree_weight"]
                >= proof["hunter_floor"]
            )
            total += 1
            event_counts[n] = event_counts.get(n, 0) + 1
    assert total == result["TARGET_MEMBER_COUNT"] == result["TARGET_VECTOR_COUNT"] == 70
    assert event_counts == {10: 54, 11: 12, 14: 4}


def test_full_twenty_three_state_family_classified_tail_and_owner(result: dict[str, Any]) -> None:
    source = cert.source_results()[cert.joint.TARGET_STATE_ID]
    before = {r["stable_id"]: r["bound"] for r in source["FINAL_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    for state_id, bound in after.items():
        assert bound == result["NEW_STATE_BOUNDS"].get(state_id, before[state_id])
    assert (
        after["state:s2-13169800-s3-789320"] == before["state:s2-13169800-s3-789320"] == 355368426
    )
    classified = [(r["stable_id"], r["bound"]) for r in source["FINAL_CLASSIFIED_TERMS"]]
    assert result["CLASSIFIED_TERM_COUNT"] == len(classified) == 56550
    assert result["CLASSIFIED_TERMS_SHA256"] == cert.digest(tuple(classified))
    assert result["CLASSIFIED_MAX"] == max(b for _, b in classified) == 355145504
    assert result["TAIL_BOUND"] == source["TAIL_BOUND"] == 354039277
    all_terms = [*after.items(), *classified, (cert.r24.TAIL_ID, result["TAIL_BOUND"])]
    maximum = max(b for _, b in all_terms)
    assert result["FINAL_COMPLETE_R3_UB"] == maximum == 355368426
    assert (
        result["FINAL_OWNER_IDS"]
        == sorted(k for k, b in all_terms if b == maximum)
        == ["state:s2-13169800-s3-789320"]
    )
    assert result["START_COMPLETE_R3_UB"] == source["FINAL_COMPLETE_R3_UB"] == 355406030
    assert result["STRICT_GAIN"] == result["START_COMPLETE_R3_UB"] - maximum == 37604
    assert result["REMAINING_GAP"] == maximum - 313263888 == 42104538


@pytest.mark.parametrize(
    "fault",
    (
        "missing_member",
        "missing_vector",
        "pair_floor",
        "weak_q14",
        "threshold_census",
        "rank_minimizer",
        "additive_credit",
        "lost_credit",
        "event_count",
        "event_type",
        "selected_event",
        "illegal_support",
        "support_hash",
        "witness_collision",
        "non_target_bound",
        "non_target_vector",
        "state_missing",
        "preserved_state",
        "classified_hash",
        "tail",
        "family_bound",
        "owner",
        "member_bound",
        "base_identity",
    ),
)
def test_semantic_mutations_are_rejected(result: dict[str, Any], fault: str) -> None:
    mutated = copy.deepcopy(result)
    region = mutated["REGIONS"][0]
    record = region["member_certificates"][0]
    row = record["vector_certificates"][0]
    if fault == "missing_member":
        region["member_certificates"].pop()
    elif fault == "missing_vector":
        record["vector_certificates"].clear()
    elif fault == "pair_floor":
        mutated["TYPE0_HUNTER_PROOFS"][0]["pair_floors"][0] += 1
    elif fault == "weak_q14":
        mutated["TYPE0_HUNTER_PROOFS"][2]["collision_mass_floor"] = 44
    elif fault == "threshold_census":
        mutated["TYPE0_HUNTER_PROOFS"][1]["all_admissible_threshold_cases"] -= 1
    elif fault == "rank_minimizer":
        mutated["TYPE0_HUNTER_PROOFS"][2]["integer_minimizer"]["rank_floors"][0] -= 1
    elif fault == "additive_credit":
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
        record["member_new_bound"] = row["vector_new_bound"]
    elif fault == "lost_credit":
        row["corrections"]["SEALED_VALID"] = 0
    elif fault == "event_count":
        row["type0_count"] -= 1
    elif fault == "event_type":
        row["selected_event_types"][0] = 1
    elif fault == "selected_event":
        row["selected_event_indices"][0] = 17
    elif fault == "illegal_support":
        row["support_witness"][0] = row["support_witness"][1]
    elif fault == "support_hash":
        row["support_sha256"] = "0" * 64
    elif fault == "witness_collision":
        row["witness_analysis"]["collision_mass"] -= 1
    elif fault in ("non_target_bound", "non_target_vector"):
        non_target = next(
            r for r in region["complete_region_members"] if r["represented_vector_count"] > 1
        )
        if fault == "non_target_bound":
            non_target["final_bound"] -= 1
        else:
            non_target["represented_vectors"].pop()
    elif fault == "state_missing":
        mutated["FINAL_STATE_TERMS"].pop()
    elif fault == "preserved_state":
        next(
            r
            for r in mutated["FINAL_STATE_TERMS"]
            if r["stable_id"] == "state:s2-13169800-s3-789320"
        )["bound"] -= 1
    elif fault == "classified_hash":
        mutated["CLASSIFIED_TERMS_SHA256"] = "0" * 64
    elif fault == "tail":
        mutated["TAIL_BOUND"] -= 1
    elif fault == "family_bound":
        mutated["FINAL_COMPLETE_R3_UB"] -= 1
    elif fault == "owner":
        mutated["FINAL_OWNER_IDS"] = [cert.joint.TARGET_STATE_ID]
    elif fault == "member_bound":
        record["member_new_bound"] -= 1
    elif fault == "base_identity":
        mutated["BASE_HEAD"] = "0" * 40
    else:
        pytest.fail("unknown semantic mutation")
    with pytest.raises(AssertionError):
        cert.verify_result(mutated)


def test_live_additive_combination_mutation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    state_id = cert.joint.TARGET_STATE_ID
    member = cert.target_members(state_id, cert.region_members(state_id))[0]

    def additive(credits: Mapping[str, int]) -> int:
        return sum(credits.values())

    monkeypatch.setattr(cert.hunter, "combine_corrections", additive)
    with pytest.raises(AssertionError, match="correction recovery"):
        cert.certify_member(state_id, member, (member.counts,), cert.hunter_proof(10))


def test_live_weaker_n14_collision_mutation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.hunter.balanced_collision_mass

    def weak_mass(incidences: int, labels: int) -> int:
        return incidences - labels

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "balanced_collision_mass", weak_mass)
        cert.hunter_proof.cache_clear()
        with pytest.raises(AssertionError, match="n=14 requires Q=48"):
            cert.hunter_proof(14)
    cert.hunter_proof.cache_clear()
    assert cert.hunter.balanced_collision_mass is original
    assert cert.hunter_proof(14)["collision_mass_floor"] == 48


def test_exact_result_semantic_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result)["status"] == "PASS"
    stored = cert.RESULT_PATH.read_bytes()
    assert stored == cert.encode(result).encode()
    assert json.loads(stored) == result
    assert cert.verify_stored_result()["status"] == "PASS"


@pytest.mark.parametrize("field", ("BASE_TREE", "BASE_RESULT_SHA256"))
def test_immutable_authority_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    monkeypatch.setattr(cert, field, "0" * len(getattr(cert, field)))
    with pytest.raises(AssertionError, match="BASE_HEAD/TREE/result SHA"):
        cert.verify_source_authority()


def test_warm_cache_cannot_hide_changed_sealed_input(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    original = Path.read_bytes

    def changed_bytes(path: Path) -> bytes:
        content = original(path)
        return content + b" " if path == cert.joint.RESULT_PATH else content

    monkeypatch.setattr(Path, "read_bytes", changed_bytes)
    with pytest.raises(AssertionError, match="immutable executing source or sealed input changed"):
        cert.verify_result(result)
