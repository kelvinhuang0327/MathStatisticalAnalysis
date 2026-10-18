"""Exact Classified R12 accounting, independent proofs and semantic fault checks."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from math import comb
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import (
    b649_k20_r3_classified_r12_five_level_nine_event_certificate_r1 as cert,
)

PHI = (107_800, 574_000, 1_691_620, 3_451_651)
ORDINALS = (25, 26, 27, 30, 32)
BOUNDS = (355_145_504, 355_145_056, 355_144_608, 355_144_160, 355_143_712)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("forbidden cold-replay census, solver or new classification")

    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
        guard.setattr(cert.r6, "iter_type_count_vectors", forbidden)
        guard.setattr(cert.r12, "tail_level_census", forbidden)
        guard.setattr(cert.r12, "canonical_uncorrected_baseline", forbidden)
        guard.setattr(cert.r12, "classify_vector", forbidden)
        guard.setattr(cert.r24, "run_chase", forbidden)
        guard.setattr(cert.hunter.r8, "support_model_status", forbidden)
        guard.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
        return cert.build_result()


def test_immutable_base_and_all_sealed_sources(result: dict[str, Any]) -> None:
    assert cert.verify_base_authority() == {
        "HEAD": "5cfacd03b1026274577f6647083684b53b00bcae",
        "TREE": "fd5a8b3cf7aafe4617afad620ccfce196ee9b8ca",
        "RESULT_SHA256": "f059ab046a75a3c7790ae979a84ff323d44a8e7e605ee1a6042e206b6d34c06a",
    }
    assert result["UPSTREAM_FINGERPRINTS_SHA256"] == cert.verify_upstream_fingerprints()
    for path, expected in cert.UPSTREAM_SHA256.items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == expected
    assert cert.source_authority()["FINAL_FAMILY_MAX_RECOMPUTATION"]["R3_BOUND"] == 355_497_359


def test_complete_aggregate_recovery_and_exact_fifteen_targets(result: dict[str, Any]) -> None:
    sealed = json.loads((cert.REPO_ROOT / cert.r24.R12_RESULT_RELATIVE).read_text())
    levels = cert.aggregate_levels()
    targets = cert.target_levels(levels)
    flat = [v for level in levels for v in level.vectors]
    assert len(levels) == result["AGGREGATE_LEVEL_COUNT"] == 29
    assert len(flat) == len(set(flat)) == result["AGGREGATE_VECTOR_COUNT"] == 183
    assert {r.ordinal for r in levels} == set(range(1, 33)) - {1, 2, 24}
    assert tuple(r.ordinal for r in targets) == ORDINALS
    assert result["TARGET_VECTOR_COUNT"] == 15
    assert result["AGGREGATE_VECTORS_SHA256"] == cert.digest(
        tuple((r.ordinal, r.vectors) for r in levels)
    )
    losses = cert.r6.local_losses(cert.r5.anchor_incidence_profiles())
    assert cert.canonical_baseline() == 33_752_922 + 18 * 18_405_317 == 365_048_628
    for level in levels:
        assert level.source_row == sealed["LOSS_LEVEL_ROWS"][level.ordinal - 1]
        independently_recovered = tuple(
            sorted(cert.r16.iter_interval_vectors(losses, 18, level.loss, level.loss))
        )
        assert independently_recovered == level.vectors
        assert len(level.vectors) == level.source_row["vector_count"]
        assert max(level.prior_bounds) == level.source_row["maximum_vector_bound"]
        assert min(level.prior_corrections) == level.source_row["minimum_correction"]
        for vector, correction, bound in zip(
            level.vectors, level.prior_corrections, level.prior_bounds, strict=True
        ):
            assert len(vector) == 30 and min(vector) >= 0 and sum(vector) == 18
            assert sum(n * loss for n, loss in zip(vector, losses, strict=True)) == level.loss
            envelope = cert.r6.type_count_envelope(vector)
            assert correction == max(envelope.pair_union_penalty, envelope.prior_forest_penalty)
            assert bound == 365_048_628 - level.loss - correction
    for k, level in enumerate(targets):
        expected: set[tuple[int, ...]] = set()
        for a in range(3):
            vector = [0] * 30
            vector[0], vector[1], vector[4], vector[5], vector[16] = 9, a, 2 - a, 7 - k, k
            expected.add(tuple(vector))
        assert set(level.vectors) == expected
        assert level.loss == 6_709_724 + 448 * k
        assert level.prior_corrections == (2_870_000,) * 3


def test_independent_exact_residual_pairs_collision_and_threshold_minimum(
    result: dict[str, Any],
) -> None:
    proof = result["NINE_EVENT_PROOF"]
    assert proof["pair_floors"] == list(PHI)
    assert proof["event_count"] == 9 and proof["pair_overlap_ceiling"] == 3
    assert proof["residual_event_definition"] == "R_i = E_i \\ (E_A \u222a E_B)"
    assert proof["type_cells"] == [0, 0, 0, 6]
    for overlap, expected in enumerate(PHI):
        cells = (0, 0, 0, overlap)
        tickets = cert.hunter.realize_pair((0, 0, 0, 6), (0, 0, 0, 6), cells)
        assert cert.six.residual_pair_intersection(0, 0, cells) == expected
        assert (
            cert.hunter.outcome_count(tickets, (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B))
            == expected
        )
        assert proof["pair_rows"][overlap] == [0, 0, *cells, expected]
    outside = set(range(49)) - set(cert.hunter.ANCHOR_A | cert.hunter.ANCHOR_B)
    assert set(proof["outside_labels"]) == outside and len(outside) == 40
    assert proof["outside_incidences"] == 54
    assert proof["balanced_frequencies"] == [[1, 26], [2, 14]]
    assert proof["collision_mass_floor"] == 26 * comb(1, 2) + 14 * comb(2, 2) == 54 - 40
    rho = [next(r for r in range(9) if comb(r + 1, 2) >= e) for e in range(37)]
    assert [cert.hunter.rank_floor(e) for e in range(37)] == rho
    for a in range(9):
        for b in range(9 - a):
            assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)
    candidates: list[tuple[int, tuple[int, int, int]]] = []
    for e1 in range(37):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= 14:
                    value = 8 * PHI[0] + sum(
                        (PHI[k] - PHI[k - 1]) * rho[e] for k, e in enumerate((e1, e2, e3), start=1)
                    )
                    candidates.append((value, (e1, e2, e3)))
    assert len(candidates) == proof["all_admissible_threshold_cases"] == 9016
    assert min(candidates) == (3_193_400, (14, 0, 0))
    assert proof["integer_minimizer"]["rank_floors"] == [5, 0, 0]
    assert [r["hunter_floor"] for r in proof["threshold_cases"]] == [
        3_193_400,
        3_844_820,
        5_138_651,
    ]
    assert result["HUNTER_CORRECTION_FLOOR"] == 8 * PHI[0] + 5 * (PHI[1] - PHI[0]) == 3_193_400
    # Bounded graph/event universes validate the rank, Kruskal and pointwise lemmas.
    assert cert.hunter.verify_rank_floor_exhaustively(5) == 1024
    assert cert.hunter.verify_threshold_tree_lemma(4) == 4096
    assert cert.hunter.verify_hunter_exhaustively(3, 3) == 1536


def test_max_single_replacement_and_five_new_bounds(result: dict[str, Any]) -> None:
    assert result["NEW_CLASSIFIED_LEVEL_BOUNDS"] == list(BOUNDS)
    for k, level in enumerate(result["LEVEL_CERTIFICATES"]):
        assert level["ordinal"] == ORDINALS[k]
        assert len(level["vector_certificates"]) == level["represented_vector_count"] == 3
        for row in level["vector_certificates"]:
            vector = cert.dense(row["counts"])
            assert vector[0] == row["type0_count"] == 9
            assert row["nine_event_indices"] == list(range(9))
            assert row["nine_event_types"] == [0] * 9
            assert row["applicability_status"] == "PASS"
            assert row["exact_loss"] == level["exact_loss"] == 6_709_724 + 448 * k
            assert row["uncorrected_anchor_bound"] == 358_338_904 - 448 * k
            assert row["corrections"]["FOREST"] == row["prior_applied_correction"] == 2_870_000
            assert row["combined_correction"] == max(row["corrections"].values()) == 3_193_400
            assert row["combined_correction"] != sum(row["corrections"].values())
            assert row["vector_new_bound"] == row["uncorrected_anchor_bound"] - 3_193_400
        assert level["level_certified_correction"] == 3_193_400
        assert (
            level["level_new_bound"]
            == max(v["vector_new_bound"] for v in level["vector_certificates"])
            == BOUNDS[k]
        )
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_all_fifteen_legal_supports_and_full_tree_extensions(result: dict[str, Any]) -> None:
    seen: set[tuple[int, ...]] = set()
    for level in result["LEVEL_CERTIFICATES"]:
        for row in level["vector_certificates"]:
            vector = cert.dense(row["counts"])
            assert vector not in seen
            seen.add(vector)
            tickets = tuple(frozenset(t) for t in row["support_witness"])
            support = tuple(tuple(t) for t in row["support_witness"])
            anchors = (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B)
            assert cert.hunter.r8.validate_support_assignment(vector, support)
            assert len(set((*anchors, *tickets))) == 20
            assert all(len(a & b) <= 3 for a, b in combinations((*anchors, *tickets), 2))
            assert cert.digest(support) == row["support_sha256"]
            subset = tickets[:9]
            assert all(t <= set(result["NINE_EVENT_PROOF"]["outside_labels"]) for t in subset)
            witness = row["witness_analysis"]
            mass = sum(comb(sum(x in t for t in subset), 2) for x in cert.hunter.CELL_LABELS[3])
            assert mass == sum(len(a & b) for a, b in combinations(subset, 2))
            assert mass == witness["collision_mass"] and mass >= 14
            overlaps = {(i, j): len(subset[i] & subset[j]) for i, j in combinations(range(9), 2)}
            tree = tuple((int(a), int(b)) for a, b in witness["subset_tree"])
            assert len(tree) == cert.hunter.graph_rank(9, tree) == 8
            for k in range(1, 4):
                graph = [edge for edge, value in overlaps.items() if value >= k]
                assert sum(overlaps[e] >= k for e in tree) == cert.hunter.graph_rank(9, graph)
            weight = sum(PHI[overlaps[e]] for e in tree)
            assert weight == witness["phi_tree_weight"] >= 3_193_400
            full = cast(list[tuple[int, int]], witness["extended_tree"])
            assert len(full) == cert.hunter.graph_rank(18, full) == 17
            types = tuple(i for i, n in enumerate(vector) for _ in range(n))
            total = 0
            for left, right in full:
                cells = tuple(
                    len(tickets[left] & tickets[right] & set(c)) for c in cert.hunter.CELL_LABELS
                )
                cost = cert.six.residual_pair_intersection(
                    types[left], types[right], cast(tuple[int, int, int, int], cells)
                )
                assert cost >= 0
                total += cost
            assert total == witness["extended_tree_exact_weight"] >= weight
    assert len(seen) == 15


def test_preserved_aggregate_levels_explicit_terms_states_and_tail(result: dict[str, Any]) -> None:
    levels = result["COMPLETE_AGGREGATE_LEVELS"]
    assert {
        r["ordinal"] for r in levels if r["level_final_bound"] != r["level_prior_bound"]
    } == set(ORDINALS)
    remainder = [r for r in levels if r["ordinal"] not in ORDINALS]
    assert len(remainder) == result["PRESERVED_AGGREGATE_LEVEL_COUNT"] == 24
    assert sum(r["represented_vector_count"] for r in remainder) == 168
    assert all(r["level_final_bound"] == r["level_prior_bound"] for r in remainder)
    assert max(r["level_final_bound"] for r in remainder) == result["PRESERVED_AGGREGATE_MAX"]
    assert result["PRESERVED_AGGREGATE_MAX"] == 354_333_735
    assert max(r["level_final_bound"] for r in levels) == result["FINAL_R12_AGGREGATE_MAX"]
    assert result["FINAL_R12_AGGREGATE_MAX"] == 355_145_504
    classified = cert.six.classified_terms()
    updated = cert.replace_aggregate(classified, result["FINAL_R12_AGGREGATE_MAX"])
    assert len(classified) == len(updated) == result["CLASSIFIED_TERMS_ACCOUNTED"] == 56_550
    explicit = tuple((k, b) for k, b in classified if k != cert.r24.AGGREGATE_ID)
    assert len(explicit) == result["PRESERVED_EXPLICIT_CLASSIFIED_TERM_COUNT"] == 56_549
    assert explicit == tuple((k, b) for k, b in updated if k != cert.r24.AGGREGATE_ID)
    assert cert.digest(explicit) == result["START_EXPLICIT_CLASSIFIED_TERMS_SHA256"]
    assert cert.digest(explicit) == result["FINAL_EXPLICIT_CLASSIFIED_TERMS_SHA256"]
    assert cert.digest(updated) == result["FINAL_CLASSIFIED_TERMS_SHA256"]
    assert result["CLASSIFIED_TERMS_CHANGED"] == 1
    assert max(b for _, b in explicit) == result["NEXT_EXPLICIT_CLASSIFIED_MAX"] == 354_800_665
    assert max(b for _, b in updated) == result["FINAL_CLASSIFIED_MAX"] == 355_145_504
    source = cert.source_authority()
    assert result["START_STATE_TERMS"] == result["FINAL_STATE_TERMS"] == source["FINAL_STATE_TERMS"]
    states = tuple((r["stable_id"], r["bound"]) for r in result["FINAL_STATE_TERMS"])
    assert len(states) == len(dict(states)) == 23
    assert result["TAIL_BOUND"] == source["TAIL_BOUND"] == 354_039_277
    terms = (*states, (cert.r24.TAIL_ID, result["TAIL_BOUND"]), *updated)
    maximum = max(b for _, b in terms)
    assert result["START_COMPLETE_R3_UB"] == result["FINAL_STANDALONE_COMPLETE_R3_UB"] == maximum
    assert maximum == 355_497_359
    assert result["FINAL_OWNER_IDS"] == [k for k, b in terms if b == maximum]
    assert result["FINAL_OWNER_IDS"] == ["state:s2-12695020-s3-735532"]


def test_missing_duplicate_wrong_level_and_invalid_applicability_rejected() -> None:
    level = cert.target_levels(cert.aggregate_levels())[0]
    proof = cert.nine_event_proof()
    for invalid in ((), level.vectors[:2], (level.vectors[0],) * 3, tuple(reversed(level.vectors))):
        with pytest.raises(AssertionError, match="represented-vector"):
            cert.certify_level(level, invalid, proof)
    for invalid in (replace(level, ordinal=26), replace(level, loss=level.loss + 1)):
        with pytest.raises(AssertionError, match="applicability"):
            cert.certify_vector(invalid, level.vectors[0], proof)
    wrong = list(level.vectors[0])
    wrong[0] -= 1
    wrong[1] += 1
    with pytest.raises(AssertionError, match="applicability"):
        cert.certify_vector(level, tuple(wrong), proof)
    with pytest.raises(AssertionError, match="five target"):
        cert.target_levels(tuple(r for r in cert.aggregate_levels() if r != level))


@pytest.mark.parametrize(
    "mutation",
    (
        "identity",
        "pair",
        "rank",
        "mass",
        "floor",
        "missing_level",
        "missing_vector",
        "duplicate_vector",
        "wrong_level",
        "wrong_loss",
        "duplicate_credit",
        "witness",
        "digest",
        "remainder",
        "explicit",
        "state",
        "tail",
        "family",
        "owner",
        "count",
    ),
)
def test_tampered_certificate_rejected(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    level, proof = bad["LEVEL_CERTIFICATES"][0], bad["NINE_EVENT_PROOF"]
    row = level["vector_certificates"][0]
    if mutation == "identity":
        bad["BASE_TREE"] = "0" * 40
    elif mutation == "pair":
        proof["pair_rows"][0][-1] += 1
    elif mutation == "rank":
        proof["integer_minimizer"]["rank_floors"][0] -= 1
    elif mutation == "mass":
        proof["collision_mass_floor"] -= 1
    elif mutation == "floor":
        proof["hunter_floor"] += 1
    elif mutation == "missing_level":
        bad["LEVEL_CERTIFICATES"].pop()
    elif mutation == "missing_vector":
        level["vector_certificates"].pop()
    elif mutation == "duplicate_vector":
        level["vector_certificates"][1] = copy.deepcopy(row)
    elif mutation == "wrong_level":
        level["ordinal"] = 26
    elif mutation == "wrong_loss":
        row["exact_loss"] += 1
    elif mutation == "duplicate_credit":
        row["combined_correction"] = sum(row["corrections"].values())
        row["vector_new_bound"] = row["uncorrected_anchor_bound"] - row["combined_correction"]
    elif mutation == "witness":
        row["support_witness"][0] = row["support_witness"][1]
    elif mutation == "digest":
        row["support_sha256"] = "0" * 64
    elif mutation == "remainder":
        bad["COMPLETE_AGGREGATE_LEVELS"][0]["level_final_bound"] -= 1
    elif mutation == "explicit":
        bad["FINAL_EXPLICIT_CLASSIFIED_TERMS_SHA256"] = "0" * 64
    elif mutation == "state":
        bad["FINAL_STATE_TERMS"][0]["bound"] -= 1
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "family":
        bad["FINAL_STANDALONE_COMPLETE_R3_UB"] = 355_466_398
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [cert.r24.AGGREGATE_ID]
    else:
        bad["CLASSIFIED_TERM_COUNT"] -= 1
    with pytest.raises(AssertionError, match="stored"):
        cert.verify_result(bad)


@pytest.mark.parametrize("mutation", ("sum", "pair", "rank", "mass", "floor", "missing", "loss"))
def test_non_equivalent_semantic_mutations_killed(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """Mutate executing arithmetic/recovery seams, beyond changing stored output."""

    level = cert.target_levels(cert.aggregate_levels())[0]
    proof = cert.nine_event_proof()
    if mutation == "sum":

        def additive(values: Mapping[str, int]) -> int:
            return sum(values.values())

        monkeypatch.setattr(cert.hunter, "combine_corrections", additive)
    elif mutation == "pair":
        original_pair = cert.six.residual_pair_intersection

        def wrong_pair(a: int, b: int, cells: tuple[int, int, int, int]) -> int:
            return original_pair(a, b, cells) + int(a == b == 0)

        monkeypatch.setattr(cert.six, "residual_pair_intersection", wrong_pair)
    elif mutation == "rank":
        original_rank = cert.hunter.rank_floor

        def wrong_rank(edges: int) -> int:
            return original_rank(edges) - int(edges > 0)

        monkeypatch.setattr(cert.hunter, "rank_floor", wrong_rank)
    elif mutation == "mass":
        original_mass = cert.hunter.balanced_collision_mass

        def wrong_mass(incidences: int, labels: int) -> int:
            return original_mass(incidences, labels) - 1

        monkeypatch.setattr(cert.hunter, "balanced_collision_mass", wrong_mass)
    elif mutation == "floor":
        original_minimum = cert.hunter.minimum_tree_correction

        def wrong_minimum(floors: tuple[int, int, int, int], mass: int, n: int = 18) -> Any:
            value = original_minimum(floors, mass, n)
            return replace(value, correction=value.correction + 1)

        monkeypatch.setattr(cert.hunter, "minimum_tree_correction", wrong_minimum)
    elif mutation == "missing":
        original_iterator = cert.r16.iter_interval_vectors

        def missing_vector(
            losses: Sequence[int], tickets: int, lower: int, upper: int
        ) -> Iterator[tuple[int, ...]]:
            values = tuple(original_iterator(losses, tickets, lower, upper))
            yield from values[1:] if lower == level.loss else values

        monkeypatch.setattr(cert.r16, "iter_interval_vectors", missing_vector)
    else:
        original_loss = cert.r12.local_loss

        def wrong_loss(vector: tuple[int, ...], losses: Sequence[int]) -> int:
            return original_loss(vector, losses) + 1

        monkeypatch.setattr(cert.r12, "local_loss", wrong_loss)
    try:
        if mutation in ("missing", "loss"):
            cert.aggregate_levels.cache_clear()
            with pytest.raises(AssertionError, match="coverage"):
                cert.aggregate_levels()
        else:
            with pytest.raises(AssertionError):
                cert.certify_vector(level, level.vectors[0], proof)
    finally:
        monkeypatch.undo()
        cert.aggregate_levels.cache_clear()
    assert cert.build_result() == result


def test_warm_cache_source_identity_tampering_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cert.build_result() == result
    monkeypatch.setattr(cert, "BASE_TREE", "0" * 40)
    with pytest.raises(AssertionError, match="HEAD/TREE"):
        cert.build_result()
    monkeypatch.undo()
    monkeypatch.setitem(cert.UPSTREAM_SHA256, cert.prior.RESULT_RELATIVE, "0" * 64)
    with pytest.raises(AssertionError, match="fingerprint"):
        cert.build_result()


def test_forbidden_census_solver_and_reclassification_never_called(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("forbidden census, solver or new classification invoked")

    monkeypatch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(cert.r6, "iter_type_count_vectors", forbidden)
    monkeypatch.setattr(cert.r12, "tail_level_census", forbidden)
    monkeypatch.setattr(cert.r12, "canonical_uncorrected_baseline", forbidden)
    monkeypatch.setattr(cert.r12, "classify_vector", forbidden)
    monkeypatch.setattr(cert.r24, "run_chase", forbidden)
    monkeypatch.setattr(cert.hunter.r8, "support_model_status", forbidden)
    monkeypatch.setattr(cert.hunter.r8, "solver_runtime_preflight", forbidden)
    cert.aggregate_levels.cache_clear()
    assert cert.build_result() == result
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["OUTCOME_ENUMERATION_USED"] is False
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"


def test_exact_result_and_byte_replay(result: dict[str, Any]) -> None:
    assert cert.verify_result(result) == {
        "status": "PASS",
        "levels": 5,
        "vectors": 15,
        "classified_terms": 56_550,
    }
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_stored_result()["status"] == "PASS"
