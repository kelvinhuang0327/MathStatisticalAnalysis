"""Focused acceptance for the sealed CLUSTERING + REGIME_STATE candidate."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterator, Sequence
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_clustering_regime_state_weighted_score_100_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as regime_parent,
)

clustering_parent = biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1

Ticket = tuple[int, int, int, int, int, int]
_AUTHORITY_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_67E4BB1A0CA281FE_R1"
)
_TASK_DATA_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "BIGLOTTO_L2_PAIRWISE_CLUSTERING_REGIME_STATE_WEIGHTED_SCORE_100_"
    "CANDIDATE_BATCH_R1"
)
_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (7, 8, 9, 10, 11, 12),
    (13, 14, 15, 16, 17, 18),
    (19, 20, 21, 22, 23, 24),
    (25, 26, 27, 28, 29, 30),
    (31, 32, 33, 34, 35, 36),
    (37, 38, 39, 40, 41, 42),
    (43, 44, 45, 46, 47, 48),
    (1, 10, 20, 30, 40, 49),
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((_AUTHORITY_ROOT / "implementation_handoff.json").read_text(encoding="utf-8")),
    )


def _reference_collision(history: Sequence[Ticket], window: int) -> Fraction:
    counts = [0] * 49
    for draw in history[-window:]:
        for number in draw:
            counts[number - 1] += 1
    return sum(
        (Fraction(count * count, (6 * window) * (6 * window)) for count in counts),
        Fraction(0, 1),
    )


def test_authority_checksum_identity_signature_and_paths_are_exact() -> None:
    for line in (_AUTHORITY_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        actual_hash = hashlib.sha256((_AUTHORITY_ROOT / relative_path).read_bytes()).hexdigest()
        assert actual_hash == expected_hash

    authority = _authority()
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"
    assert authority["EXPECTED_IMPLEMENTATION_MODULE"] == (batch.IMPLEMENTATION_MODULE)
    assert authority["EXPECTED_IMPLEMENTATION_SYMBOL"] == (batch.IMPLEMENTATION_SYMBOL)
    assert authority["EXPECTED_FOCUSED_TEST_MODULE"] == (batch.EXPECTED_FOCUSED_TEST_MODULE)
    assert batch.EXPECTED_SOURCE_PATH == (
        "src/lottolab/research/"
        "biglotto_l2_pairwise_clustering_regime_state_weighted_score_100_"
        "candidate_batch_r1.py"
    )
    signature_object = {key: authority[key] for key in batch.CANDIDATE_SEMANTICS}
    assert json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)) == (
        signature_object
    )
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )
    assert (
        hashlib.sha256((_AUTHORITY_ROOT / "implementation_handoff.json").read_bytes()).hexdigest()
        == batch.DESIGN_AUTHORITY_SHA256
    )


def test_candidate_count_and_all_authority_fields_are_exact() -> None:
    authority = _authority()
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_950aa3b890915ed7"
    assert batch.FEATURE_1 == "CLUSTERING"
    assert batch.FEATURE_2 == "REGIME_STATE"
    assert batch.WINDOW == 100
    assert batch.WINDOWS == (50, 300, 750)
    assert batch.MINIMUM_HISTORY == 751
    assert batch.RANKED_POOL_CARDINALITY == 10
    assert batch.FUSION == "WEIGHTED_SCORE"
    for key in batch.CANDIDATE_SEMANTICS:
        expected = authority[key]
        actual = batch.SOURCE_UNIVERSE_CONTRACT[key]
        if isinstance(expected, list):
            assert actual == tuple(cast(list[object], expected))
        else:
            assert actual == expected


def test_clustering_parent_profiles_partition_medoid_and_order_parity() -> None:
    history = _history(751)
    profiles = batch.calculate_temporal_profiles(history, 751)
    assert profiles == clustering_parent.calculate_temporal_profiles(history, 751)
    for number in (1, 10, 25, 42, 49):
        counts = tuple(
            sum(number in draw for draw in history[-window:]) for window in batch.WINDOWS
        )
        assert profiles.OCCURRENCE_COUNTS[number - 1] == counts
        assert profiles.RATES[number - 1] == tuple(
            Fraction(count, window) for count, window in zip(counts, batch.WINDOWS, strict=True)
        )

    partition = batch.calculate_cluster_partition(history, 751)
    expected = clustering_parent.calculate_cluster_partition(history, 751)
    assert partition == expected
    assert batch.perform_hierarchical_clustering(profiles) == partition
    assert len(partition.ORDERED_CLUSTERS) == 10
    assert sorted(number for cluster in partition.ORDERED_CLUSTERS for number in cluster) == list(
        range(1, 50)
    )
    for cluster, medoid, cost in zip(
        partition.ORDERED_CLUSTERS,
        partition.ORDERED_REPRESENTATIVES,
        partition.MEDOID_COSTS,
        strict=True,
    ):
        assert medoid in cluster
        costs = {
            number: sum(
                (profiles.profile_distance(number, member) for member in cluster),
                Fraction(0, 1),
            )
            for number in cluster
        }
        assert (cost, medoid) == min(
            (candidate_cost, number) for number, candidate_cost in costs.items()
        )
    records = tuple(
        (
            -len(cluster),
            compactness,
            medoid_cost,
            medoid,
        )
        for cluster, compactness, medoid_cost, medoid in zip(
            partition.ORDERED_CLUSTERS,
            partition.COMPACTNESS_SCORES,
            partition.MEDOID_COSTS,
            partition.ORDERED_REPRESENTATIVES,
            strict=True,
        )
    )
    assert records == tuple(sorted(records))


def test_regime_state_collision_source_and_medoid_support_parent_parity() -> None:
    history = _history(751)
    actual_state = batch.calculate_regime_state(history, 751)
    expected_state = regime_parent.calculate_regime_state(history, 751)
    assert actual_state == expected_state
    assert _reference_collision(history, 50) == actual_state.COLLISION_50
    assert _reference_collision(history, 300) == actual_state.COLLISION_300
    assert _reference_collision(history, 750) == actual_state.COLLISION_750
    assert (
        actual_state.REFERENCE_COLLISION
        == (actual_state.COLLISION_300 + actual_state.COLLISION_750) / 2
    )
    assert (
        regime_parent.classify_regime(Fraction(1, 2), Fraction(1, 2))
        == regime_parent.RECENT_DIFFUSE_HIGH_RENYI2
    )

    source = batch.produce_regime_source_ticket_universe(history, 751)
    expected_source = regime_parent.produce_b649_renyi2_regime_switched_ranked_pool_v1(history, 751)
    assert source == expected_source
    assert len(source) == 210
    pool = batch.calculate_cluster_medoid_pool(history, 751)
    expected_support = tuple(sum(number in ticket for ticket in expected_source) for number in pool)
    assert batch.calculate_regime_state_support_scores(history, 751) == (expected_support)


def test_same_medoid_conditioning_and_pool_local_support_ranking() -> None:
    pool = (41, 3, 29, 5, 17, 11, 47, 23, 37, 31)
    scores = {
        41: 3,
        3: 7,
        29: 7,
        5: 2,
        17: 6,
        11: 6,
        47: 1,
        23: 4,
        37: 0,
        31: 5,
    }
    ranking = batch.rank_regime_state_support_scores(scores, pool)
    assert pool == ranking.POOL_NUMBERS
    assert set(ranking.ORDERED_NUMBERS) == set(pool)
    assert ranking.ORDERED_NUMBERS[:4] == (3, 29, 11, 17)
    assert tuple(ranking.normalized_rank(number) for number in pool) == ranking.NORMALIZED_RANKS
    with pytest.raises(ValueError, match="ten pool numbers"):
        batch.rank_regime_state_support_scores({number: number for number in range(1, 50)}, pool)


def test_history_750_rejected_751_accepted_and_causality_is_exact() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="751"):
        batch.calculate_pairwise_ranking(_history(750), 750)
    accepted = batch.calculate_pairwise_ranking(_history(751), 751)
    assert len(accepted.RANKED_NUMBERS) == 10

    history = list(_history(751))
    snapshot = history.copy()
    baseline = batch.produce_candidate_portfolio(history, 751)
    with_target_and_future: list[object] = [*history, object(), object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == baseline
    with_target_and_future[751] = (1, 1, 1, 1, 1, 1)
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == baseline
    assert history == snapshot

    malformed = cast(list[object], history.copy())
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match=r"duplicate|unique"):
        batch.calculate_pairwise_ranking(malformed, 751)
    malformed[10] = (1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match=r"six|6"):
        batch.calculate_pairwise_ranking(malformed, 751)


def test_iterable_history_reads_only_the_causal_prefix() -> None:
    class PrefixOnly:
        def __iter__(self) -> Iterator[object]:
            yield from _history(751)
            raise AssertionError("future suffix was consumed")

    result = batch.produce_candidate_portfolio(PrefixOnly(), 751)
    assert len(result) == 1
    assert len(result[0]) == 6


def test_exact_normalization_and_hand_computable_equal_fusion() -> None:
    pool = tuple(range(1, 11))
    clustering = tuple(Fraction(10 - position, 9) for position in range(1, 11))
    regime = tuple(Fraction(position - 1, 9) for position in range(1, 11))
    ranking = batch.rank_pairwise_scores(clustering, regime, pool)
    assert all(score == Fraction(1, 2) for score in ranking.PAIRWISE_SCORES)
    assert clustering == ranking.CLUSTERING_COMPONENTS
    assert regime == ranking.REGIME_STATE_COMPONENTS
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert all(isinstance(score, Fraction) for score in ranking.PAIRWISE_SCORES)

    all_tied = batch.rank_regime_state_support_scores((0,) * 10, pool)
    assert pool == all_tied.ORDERED_NUMBERS
    assert all_tied.normalized_rank(1) == Fraction(1, 1)
    assert all_tied.normalized_rank(10) == Fraction(0, 1)


def test_both_components_change_output_and_fusion_is_not_parent_only() -> None:
    pool = tuple(range(1, 11))
    zeros = (Fraction(0, 1),) * 10
    clustering_one = tuple(Fraction(1 if number == 1 else 0, 1) for number in pool)
    clustering_two = tuple(Fraction(1 if number == 2 else 0, 1) for number in pool)
    assert (
        batch.rank_pairwise_scores(clustering_one, zeros, pool).RANKED_NUMBERS
        != batch.rank_pairwise_scores(clustering_two, zeros, pool).RANKED_NUMBERS
    )

    regime_nine = tuple(Fraction(1 if number == 9 else 0, 1) for number in pool)
    regime_ten = tuple(Fraction(1 if number == 10 else 0, 1) for number in pool)
    assert (
        batch.rank_pairwise_scores(zeros, regime_nine, pool).RANKED_NUMBERS
        != batch.rank_pairwise_scores(zeros, regime_ten, pool).RANKED_NUMBERS
    )

    fused = batch.rank_pairwise_scores(clustering_one, regime_ten, pool)
    clustering_only = tuple(
        sorted(
            pool,
            key=lambda number: (-clustering_one[number - 1], number),
        )
    )
    regime_only = tuple(
        sorted(
            pool,
            key=lambda number: (-regime_ten[number - 1], number),
        )
    )
    assert clustering_only != fused.RANKED_NUMBERS
    assert regime_only != fused.RANKED_NUMBERS


def test_medoid_pool_ticket_shape_parent_isolation_and_determinism() -> None:
    history = list(_history(751))
    history_snapshot = history.copy()
    parent_paths = (
        Path(clustering_parent.__file__),
        Path(regime_parent.__file__),
    )
    parent_hashes = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in parent_paths)
    first = batch.calculate_pairwise_ranking(history, 751)
    second = batch.calculate_pairwise_ranking(history, 751)
    pool = batch.calculate_cluster_medoid_pool(history, 751)
    parent_partition = clustering_parent.calculate_cluster_partition(history, 751)

    assert first == second
    assert pool == parent_partition.ORDERED_REPRESENTATIVES
    assert pool == first.CLUSTER_MEDOID_POOL == first.POOL_NUMBERS
    assert len(pool) == len(set(pool)) == 10
    assert len(first.REGIME_SOURCE_TICKETS) == 210
    assert len(first.RANKED_NUMBERS) == len(set(first.RANKED_NUMBERS)) == 10
    assert len(first.TICKETS) == batch.NATIVE_TICKET_COUNT == 1
    assert tuple(sorted(first.RANKED_NUMBERS[:6])) == first.NATIVE_TICKET
    assert len(first.NATIVE_TICKET) == len(set(first.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in first.NATIVE_TICKET)
    assert batch.produce_candidate_portfolio(history, 751) == (first.NATIVE_TICKET,)
    assert history == history_snapshot
    assert (
        tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in parent_paths)
        == parent_hashes
    )


def test_research_only_no_rng_no_catalog_registry_db_or_replay() -> None:
    assert batch.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})
    source = Path(batch.__file__).read_text(encoding="utf-8")
    assert "lottolab.strategies.catalog" not in source
    assert "lottolab.strategies.registry" not in source
    assert "sqlite" not in source.lower()
    assert "random." not in source.lower()
    assert "replay_" not in source.lower()


def test_task_data_outputs_are_exactly_one_clean_unvalidated_candidate() -> None:
    required = (
        "source_universe_contract.json",
        "candidate_authority.csv",
        "candidate_validation_handoff.csv",
        "candidate_batch_manifest.json",
        "SHA256SUMS",
    )
    assert all((_TASK_DATA_ROOT / name).is_file() for name in required)
    for line in (_TASK_DATA_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        actual_hash = hashlib.sha256((_TASK_DATA_ROOT / relative_path).read_bytes()).hexdigest()
        assert actual_hash == expected_hash

    contract = cast(
        dict[str, object],
        json.loads((_TASK_DATA_ROOT / "source_universe_contract.json").read_text()),
    )
    assert contract["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert contract["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256

    authority_rows = list(
        csv.DictReader(
            (_TASK_DATA_ROOT / "candidate_authority.csv").open(newline="", encoding="utf-8")
        )
    )
    assert len(authority_rows) == 1
    assert authority_rows[0]["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority_rows[0]["DESIGN_ID"] == batch.DESIGN_ID
    assert authority_rows[0]["NATIVE_TICKET_COUNT"] == "1"

    validation_rows = list(
        csv.DictReader(
            (_TASK_DATA_ROOT / "candidate_validation_handoff.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    assert len(validation_rows) == 1
    row = validation_rows[0]
    assert row["TECHNICAL_IMPLEMENTATION_STATUS"] == ("TECHNICAL_IMPLEMENTATION_COMPLETE")
    assert row["CATALOG_STATUS"] == "NOT_CATALOG_WIRED"
    assert row["PERFORMANCE_VALIDATION_STATUS"] == "NOT_RUN"
    assert row["REPLAY_STATUS"] == "NOT_RUN"
    assert row["PERFORMANCE_CONTAMINATION_STATUS"] == (
        "TASK_SPECIFIC_CLEAN_WITH_PREEXISTING_UNRELATED_CONTEXT"
    )

    manifest = cast(
        dict[str, object],
        json.loads((_TASK_DATA_ROOT / "candidate_batch_manifest.json").read_text()),
    )
    assert manifest["CANDIDATE_COUNT"] == 1
    assert manifest["CANDIDATE_IDS"] == [batch.CANDIDATE_ID]
    assert manifest["LIVE_MAIN_EXACT_DUPLICATE_COUNT"] == 0
    assert manifest["OPEN_PR_EXACT_DUPLICATE_COUNT"] == 0
    assert manifest["CONTAMINATED_R1_ARTIFACTS_READ"] == "NO"
    assert manifest["BROAD_CONTENT_SEARCH_EXECUTED"] == "NO"
    assert manifest["TASK_SPECIFIC_EMPIRICAL_VALUES_ACCESSED"] == "NO"
    assert manifest["TASK_SPECIFIC_EMPIRICAL_ARTIFACTS_READ"] == "NO"
    assert manifest["EMPIRICAL_VALUES_USED_FOR_PARAMETER_SELECTION"] == "NO"
    assert manifest["REPLAY_EXECUTED"] == "NO"
    assert manifest["DB_ACCESS"] == "NO"
    assert manifest["DB_MUTATION"] == "NO"
