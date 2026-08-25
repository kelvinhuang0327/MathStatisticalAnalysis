# pyright: reportPrivateUsage=false

from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any, overload

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_profile_cluster_renyi2_regime_candidate_batch_r1 as candidate,
)

Draw = tuple[int, ...]
_PREDICTOR_NAME = (
    "predict_biglotto_l2_pairwise_profile_cluster_renyi2_regime_"
    "cluster_selection_weighted_score_100"
)
predict: Any = getattr(candidate, _PREDICTOR_NAME)


def _cyclic_draw(index: int) -> Draw:
    return tuple(sorted(((index + offset) % 49) + 1 for offset in range(6)))


def _synthetic_history(length: int, *, offset: int = 0) -> tuple[Draw, ...]:
    return tuple(_cyclic_draw(index + offset) for index in range(length))


def _constant_history(length: int, draw: Draw = (1, 2, 3, 4, 5, 6)) -> tuple[Draw, ...]:
    return (draw,) * length


def _zero_rates() -> candidate.WindowRates:
    return {
        window: {number: Fraction(0, 1) for number in candidate.NUMBER_DOMAIN}
        for window in candidate.PROFILE_WINDOWS
    }


def _zero_fraction_map() -> candidate.NumberFractions:
    return {number: Fraction(0, 1) for number in candidate.NUMBER_DOMAIN}


def test_minimum_history_boundary_and_complete_result() -> None:
    assert predict(_synthetic_history(750)) is None

    result = predict(_synthetic_history(751))
    assert result is not None
    assert len(result.final_clusters) == 6
    assert len(result.ticket) == 6


@pytest.mark.parametrize(
    "invalid_history",
    [
        None,
        "not-a-history",
        b"not-a-history",
        {0: (1, 2, 3, 4, 5, 6)},
        iter(((1, 2, 3, 4, 5, 6),)),
    ],
)
def test_invalid_outer_history_is_rejected(invalid_history: object) -> None:
    with pytest.raises(ValueError, match="finite ordered sequence"):
        predict(invalid_history)


@pytest.mark.parametrize(
    "invalid_draw",
    [
        (1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 6, 7),
        (1, 2, 3, 4, 5, 5),
        (1, 2, 3, 4, 5, 0),
        (1, 2, 3, 4, 5, 50),
        (1, 2, 3, 4, 5, True),
        (1, 2, 3, 4, 5, 6.0),
        (1, 2, 3, 4, 5, "6"),
        (1, 2, 3, 4, 5, None),
        {"numbers": (1, 2, 3, 4, 5, 6), "special": 7},
    ],
)
def test_invalid_draw_contract_is_rejected(invalid_draw: object) -> None:
    with pytest.raises(ValueError):
        predict((invalid_draw,))


def test_complete_history_is_validated_before_insufficient_fallback() -> None:
    history: tuple[object, ...] = (*_constant_history(749), (1, 2, 3, 4, 5, 5))
    with pytest.raises(ValueError, match="distinct"):
        predict(history)


def test_internal_draw_order_is_irrelevant_and_edge_numbers_are_valid() -> None:
    ascending = ((1, 2, 3, 4, 5, 49), (6, 7, 8, 9, 10, 11))
    reversed_draws = tuple(tuple(reversed(draw)) for draw in ascending)
    assert candidate._validated_history(ascending) == candidate._validated_history(reversed_draws)


def test_multiscale_profiles_use_each_exact_trailing_window() -> None:
    draws = list(_constant_history(100))
    for index in (0, 70, 90):
        draws[index] = (1, 2, 3, 4, 5, 49)

    counts = candidate._build_profile_counts(tuple(draws))
    rates = candidate._build_profile_rates(counts)

    assert (counts[10][49], counts[30][49], counts[100][49]) == (1, 2, 3)
    assert (counts[10][6], counts[30][6], counts[100][6]) == (9, 28, 97)
    assert (counts[10][1], counts[30][1], counts[100][1]) == (10, 30, 100)
    assert rates[10][49] == Fraction(1, 10)
    assert rates[30][49] == Fraction(1, 15)
    assert rates[100][49] == Fraction(3, 100)
    for window in candidate.PROFILE_WINDOWS:
        assert sum(counts[window].values()) == 6 * window
        assert sum(rates[window].values(), start=Fraction(0, 1)) == 6


def test_older_valid_history_is_accepted_but_not_scored() -> None:
    common_tail = _synthetic_history(100, offset=23)
    first_history = (*_constant_history(651), *common_tail)
    second_history = (*_constant_history(651, (44, 45, 46, 47, 48, 49)), *common_tail)

    first = predict(first_history)
    second = predict(second_history)
    assert first == second


class _HiddenFutureHistory(Sequence[Draw]):
    def __init__(self, completed: tuple[Draw, ...], hidden_target: Draw) -> None:
        self._completed = completed
        self._hidden_target = hidden_target
        self.target_read = False

    def __len__(self) -> int:
        return len(self._completed)

    @overload
    def __getitem__(self, index: int) -> Draw: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Draw, ...]: ...

    def __getitem__(self, index: int | slice) -> Draw | tuple[Draw, ...]:
        if isinstance(index, slice):
            return self._completed[index]
        if index == len(self._completed):
            self.target_read = True
            return self._hidden_target
        return self._completed[index]


def test_target_draw_and_future_suffix_are_never_read() -> None:
    history = _HiddenFutureHistory(
        _synthetic_history(751),
        hidden_target=(44, 45, 46, 47, 48, 49),
    )
    result = predict(history)
    assert result is not None
    assert not history.target_read


def test_exact_squared_profile_geometry_is_symmetric_with_zero_diagonal() -> None:
    rates = _zero_rates()
    rates[10][1] = Fraction(1, 2)
    rates[30][1] = Fraction(1, 3)
    rates[100][1] = Fraction(1, 4)
    distances = candidate._build_pairwise_distances(rates)

    expected = Fraction(1, 4) + Fraction(1, 9) + Fraction(1, 16)
    assert expected == Fraction(61, 144)
    assert candidate._distance(1, 2, distances) == expected
    assert candidate._distance(2, 1, distances) == expected
    assert all(candidate._distance(number, number, distances) == 0 for number in range(1, 50))
    assert all(distance >= 0 for distance in distances.values())


def test_average_linkage_is_the_exact_cross_pair_mean() -> None:
    distances = {
        (1, 3): Fraction(1, 4),
        (2, 3): Fraction(3, 4),
    }
    assert candidate._average_linkage((1, 2), (3,), distances) == Fraction(1, 2)


def test_zero_distance_cluster_ties_use_canonical_cluster_labels() -> None:
    distances = candidate._build_pairwise_distances(_zero_rates())
    clusters = candidate._agglomerative_clusters(distances)

    assert clusters == (
        tuple(range(1, 45)),
        (45,),
        (46,),
        (47,),
        (48,),
        (49,),
    )
    assert len(clusters) == 6
    assert tuple(number for cluster in clusters for number in cluster) == tuple(range(1, 50))


def test_medoid_loss_rank_normalization_and_singleton_fallback() -> None:
    distances = {
        (1, 1): Fraction(0, 1),
        (1, 2): Fraction(1, 1),
        (2, 2): Fraction(0, 1),
        (49, 49): Fraction(0, 1),
    }
    medoids, losses, ranks = candidate._cluster_components(((1, 2), (49,)), distances)

    assert medoids == (1, 49)
    assert losses == {1: Fraction(1, 2), 2: Fraction(1, 2), 49: Fraction(0, 1)}
    assert ranks == {1: Fraction(1, 1), 2: Fraction(0, 1), 49: Fraction(1, 1)}


def test_hand_calculable_renyi2_collision_and_probability_mass() -> None:
    counts = {number: (10 if number <= 6 else 0) for number in candidate.NUMBER_DOMAIN}
    probabilities = {number: Fraction(counts[number], 60) for number in candidate.NUMBER_DOMAIN}
    assert sum(probabilities.values(), start=Fraction(0, 1)) == 1
    assert candidate._renyi2_collision(counts, 10) == Fraction(1, 6)


def test_balanced_integer_counts_have_exact_renyi2_edge_value() -> None:
    counts = {number: (13 if number <= 12 else 12) for number in candidate.NUMBER_DOMAIN}
    assert sum(counts.values()) == 600
    independently_derived = Fraction(12 * 13**2 + 37 * 12**2, 600**2)
    assert candidate._renyi2_collision(counts, 100) == independently_derived


@pytest.mark.parametrize(
    ("collision_10", "collision_30", "collision_100", "expected_label", "active"),
    [
        (Fraction(3, 10), Fraction(1, 5), Fraction(1, 10), candidate.RECENT_CONCENTRATION, 10),
        (Fraction(1, 5), Fraction(1, 5), Fraction(1, 10), candidate.RECENT_CONCENTRATION, 10),
        (Fraction(1, 10), Fraction(1, 5), Fraction(3, 10), candidate.RECENT_DIFFUSION, 100),
        (Fraction(1, 10), Fraction(1, 5), Fraction(1, 5), candidate.RECENT_DIFFUSION, 100),
        (Fraction(1, 6), Fraction(1, 6), Fraction(1, 6), candidate.TRANSITIONAL_OR_STABLE, 30),
        (Fraction(1, 10), Fraction(3, 10), Fraction(1, 5), candidate.TRANSITIONAL_OR_STABLE, 30),
    ],
    ids=[
        "concentration-strict",
        "concentration-boundary",
        "diffusion-strict",
        "diffusion-boundary",
        "equal-stable",
        "nonmonotone",
    ],
)
def test_regime_assignment_boundaries(
    collision_10: Fraction,
    collision_30: Fraction,
    collision_100: Fraction,
    expected_label: candidate.RegimeLabel,
    active: int,
) -> None:
    assignment = candidate._assign_regime({10: collision_10, 30: collision_30, 100: collision_100})
    assert assignment == candidate.RegimeAssignment(expected_label, active)


def test_regime_ranking_is_total_exact_and_uses_the_complete_frequency_chain() -> None:
    rates = _zero_rates()
    rates[10][49] = Fraction(1, 1)
    rates[10][1] = Fraction(1, 2)
    rates[10][2] = Fraction(1, 2)
    rates[30][2] = Fraction(1, 1)

    ranks = candidate._regime_ranks(
        rates, candidate.RegimeAssignment(candidate.RECENT_CONCENTRATION, 10)
    )
    assert set(ranks) == set(range(1, 50))
    assert ranks[49] == 1
    assert ranks[2] == Fraction(47, 48)
    assert ranks[1] == Fraction(23, 24)
    assert ranks[48] == 0
    assert sorted(ranks.values()) == [Fraction(index, 48) for index in range(49)]


def test_symmetric_level2_fusion_is_exact_for_all_49_numbers() -> None:
    cluster_ranks = {number: Fraction(number - 1, 48) for number in candidate.NUMBER_DOMAIN}
    regime_ranks = {number: Fraction(49 - number, 48) for number in candidate.NUMBER_DOMAIN}
    fused = candidate._fused_scores(cluster_ranks, regime_ranks)
    assert set(fused) == set(range(1, 50))
    assert all(value == Fraction(1, 2) for value in fused.values())


@pytest.mark.parametrize(
    ("deciding_field", "expected"),
    [
        ("fused", 2),
        ("regime", 2),
        ("cluster", 2),
        ("loss", 2),
        ("active", 2),
        ("secondary", 2),
        ("tertiary", 2),
        ("number", 1),
    ],
)
def test_complete_cluster_winner_tie_chain(deciding_field: str, expected: int) -> None:
    fused = _zero_fraction_map()
    regime = _zero_fraction_map()
    cluster = _zero_fraction_map()
    losses = _zero_fraction_map()
    rates = _zero_rates()

    if deciding_field == "fused":
        fused[2] = Fraction(1, 1)
    elif deciding_field == "regime":
        regime[2] = Fraction(1, 1)
    elif deciding_field == "cluster":
        cluster[2] = Fraction(1, 1)
    elif deciding_field == "loss":
        losses[1] = Fraction(1, 1)
    elif deciding_field == "active":
        rates[30][2] = Fraction(1, 1)
    elif deciding_field == "secondary":
        rates[10][2] = Fraction(1, 1)
    elif deciding_field == "tertiary":
        rates[100][2] = Fraction(1, 1)

    winners = candidate._select_cluster_winners(
        ((1, 2),),
        fused,
        regime,
        cluster,
        losses,
        rates,
        candidate.RegimeAssignment(candidate.TRANSITIONAL_OR_STABLE, 30),
    )
    assert winners == (expected,)


def test_full_prediction_cardinality_cluster_coverage_and_deterministic_serialization() -> None:
    history = _constant_history(751)
    first = predict(history)
    second = predict(history)
    assert first is not None
    assert second is not None

    assert first.method_id == "BMSGV1_L2_PAIRWISE_950aa3b890915ed7"
    assert first.semantic_signature == (
        "8f2a36e3f33629455f0a08d13737eac21726ac04d999daa3cf0c93a39034c683"
    )
    assert len(first.final_clusters) == 6
    assert all(first.final_clusters)
    partition = tuple(number for cluster in first.final_clusters for number in cluster)
    assert partition == tuple(range(1, 50))
    assert len(first.cluster_winners) == 6
    assert all(
        winner in cluster
        for winner, cluster in zip(first.cluster_winners, first.final_clusters, strict=True)
    )
    assert first.ticket == tuple(sorted(first.cluster_winners))
    assert len(first.ticket) == len(set(first.ticket)) == 6
    assert all(1 <= number <= 49 for number in first.ticket)
    assert all(
        set(values) == set(range(1, 50))
        for values in (
            first.profile_counts[10],
            first.profile_counts[30],
            first.profile_counts[100],
            first.profile_rates[10],
            first.profile_rates[30],
            first.profile_rates[100],
            first.cluster_ranks,
            first.regime_ranks,
            first.fused_scores,
        )
    )
    assert 1 in partition and 49 in partition
    assert all(
        first.fused_scores[number] == (first.cluster_ranks[number] + first.regime_ranks[number]) / 2
        for number in candidate.NUMBER_DOMAIN
    )
    assert all(
        medoid in cluster
        for medoid, cluster in zip(first.medoids, first.final_clusters, strict=True)
    )
    assert first == second
    assert first.to_canonical_json() == second.to_canonical_json()
    serialized = json.loads(first.to_canonical_json())
    assert serialized["method_id"] == first.method_id
    assert serialized["ticket"] == list(first.ticket)


def test_prediction_module_has_only_frozen_standard_library_dependencies() -> None:
    module_path = Path(candidate.__file__)
    syntax = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert imported_modules <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "fractions",
        "json",
        "typing",
    }
    assert not imported_modules & {
        "datetime",
        "httpx",
        "numpy",
        "pandas",
        "random",
        "requests",
        "scipy",
        "secrets",
        "sklearn",
        "socket",
        "sqlite3",
        "time",
    }


def test_public_predictor_accepts_static_object_boundary() -> None:
    assert predict(()) is None
