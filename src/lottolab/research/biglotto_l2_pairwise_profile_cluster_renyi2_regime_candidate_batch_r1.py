"""Frozen fourth Level-2 Pairwise Big Lotto research candidate.

This standalone module implements only the sealed multiscale-profile,
average-linkage clustering, Renyi-2 collision-regime, and one-winner-per-
cluster semantics for ``BMSGV1_L2_PAIRWISE_950aa3b890915ed7``.  It is pure
standard-library math: no persistence, replay, registry, network, clock, or
randomness participates in prediction.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal, cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_950aa3b890915ed7"
DESIGN_NAME = (
    "B649_PAIRWISE_MULTISCALE_PROFILE_CLUSTER_RENYI2_REGIME_CLUSTER_SELECTION_WEIGHTED_SCORE_100_V1"
)
SEMANTIC_SIGNATURE = "8f2a36e3f33629455f0a08d13737eac21726ac04d999daa3cf0c93a39034c683"

MIN_HISTORY = 751
PROFILE_WINDOWS = (10, 30, 100)
NUMBER_DOMAIN = tuple(range(1, 50))
FINAL_CLUSTER_COUNT = 6

RECENT_CONCENTRATION = "RECENT_CONCENTRATION"
RECENT_DIFFUSION = "RECENT_DIFFUSION"
TRANSITIONAL_OR_STABLE = "TRANSITIONAL_OR_STABLE"

RegimeLabel = Literal[
    "RECENT_CONCENTRATION",
    "RECENT_DIFFUSION",
    "TRANSITIONAL_OR_STABLE",
]
Draw = tuple[int, ...]
Cluster = tuple[int, ...]
NumberCounts = dict[int, int]
WindowCounts = dict[int, NumberCounts]
NumberFractions = dict[int, Fraction]
WindowRates = dict[int, NumberFractions]
PairwiseDistances = dict[tuple[int, int], Fraction]


@dataclass(frozen=True, slots=True)
class RegimeAssignment:
    """The exact collision-regime label and its frozen active window."""

    label: RegimeLabel
    active_window: int


@dataclass(frozen=True, slots=True)
class ProfileClusterRenyi2Prediction:
    """Complete deterministic result for one supplied completed-draw history."""

    method_id: str
    design_name: str
    semantic_signature: str
    profile_counts: WindowCounts
    profile_rates: WindowRates
    collision_values: NumberFractions
    regime_state: RegimeAssignment
    final_clusters: tuple[Cluster, ...]
    medoids: tuple[int, ...]
    cluster_ranks: NumberFractions
    regime_ranks: NumberFractions
    fused_scores: NumberFractions
    cluster_winners: tuple[int, ...]
    ticket: tuple[int, ...]

    def to_canonical_json(self) -> str:
        """Serialize the complete result deterministically, preserving rationals."""

        payload: dict[str, object] = {
            "cluster_ranks": _number_fraction_payload(self.cluster_ranks),
            "cluster_winners": list(self.cluster_winners),
            "collision_values": {
                str(window): _fraction_payload(self.collision_values[window])
                for window in PROFILE_WINDOWS
            },
            "design_name": self.design_name,
            "final_clusters": [list(cluster) for cluster in self.final_clusters],
            "fused_scores": _number_fraction_payload(self.fused_scores),
            "medoids": list(self.medoids),
            "method_id": self.method_id,
            "profile_counts": {
                str(window): {
                    str(number): self.profile_counts[window][number] for number in NUMBER_DOMAIN
                }
                for window in PROFILE_WINDOWS
            },
            "profile_rates": {
                str(window): _number_fraction_payload(self.profile_rates[window])
                for window in PROFILE_WINDOWS
            },
            "regime_ranks": _number_fraction_payload(self.regime_ranks),
            "regime_state": {
                "active_window": self.regime_state.active_window,
                "label": self.regime_state.label,
            },
            "semantic_signature": self.semantic_signature,
            "ticket": list(self.ticket),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {"denominator": value.denominator, "numerator": value.numerator}


def _number_fraction_payload(values: Mapping[int, Fraction]) -> dict[str, dict[str, int]]:
    return {str(number): _fraction_payload(values[number]) for number in NUMBER_DOMAIN}


def _ordered_sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{label} must be a finite ordered sequence")
    return cast(Sequence[object], value)


def _validated_history(history: object) -> tuple[Draw, ...]:
    supplied = _ordered_sequence(history, label="history")
    validated: list[Draw] = []
    for draw_index in range(len(supplied)):
        draw = _ordered_sequence(supplied[draw_index], label=f"history[{draw_index}]")
        if len(draw) != 6:
            raise ValueError(f"history[{draw_index}] must contain exactly six numbers")

        numbers: list[int] = []
        for position in range(6):
            number = draw[position]
            if type(number) is not int:
                raise ValueError(f"history[{draw_index}][{position}] must be a non-bool integer")
            integer = number
            if integer < 1 or integer > 49:
                raise ValueError(f"history[{draw_index}][{position}] must lie in 1..49")
            numbers.append(integer)
        if len(set(numbers)) != 6:
            raise ValueError(f"history[{draw_index}] must contain six distinct numbers")
        validated.append(tuple(sorted(numbers)))
    return tuple(validated)


def _build_profile_counts(history: Sequence[Draw]) -> WindowCounts:
    history_length = len(history)
    counts_by_window: WindowCounts = {}
    for window in PROFILE_WINDOWS:
        counts = {number: 0 for number in NUMBER_DOMAIN}
        for draw_index in range(history_length - window, history_length):
            for number in history[draw_index]:
                counts[number] += 1
        counts_by_window[window] = counts
    return counts_by_window


def _build_profile_rates(profile_counts: Mapping[int, Mapping[int, int]]) -> WindowRates:
    return {
        window: {
            number: Fraction(profile_counts[window][number], window) for number in NUMBER_DOMAIN
        }
        for window in PROFILE_WINDOWS
    }


def _squared_profile_distance(
    left: int,
    right: int,
    profile_rates: Mapping[int, Mapping[int, Fraction]],
) -> Fraction:
    distance = Fraction(0, 1)
    for window in PROFILE_WINDOWS:
        difference = profile_rates[window][left] - profile_rates[window][right]
        distance += difference * difference
    return distance


def _build_pairwise_distances(
    profile_rates: Mapping[int, Mapping[int, Fraction]],
) -> PairwiseDistances:
    distances: PairwiseDistances = {}
    for left in NUMBER_DOMAIN:
        for right in range(left, 50):
            distances[(left, right)] = _squared_profile_distance(left, right, profile_rates)
    return distances


def _distance(
    left: int,
    right: int,
    pairwise_distances: Mapping[tuple[int, int], Fraction],
) -> Fraction:
    pair = (left, right) if left <= right else (right, left)
    return pairwise_distances[pair]


def _canonical_cluster_pair(left: Cluster, right: Cluster) -> tuple[Cluster, Cluster]:
    return (left, right) if left < right else (right, left)


def _average_linkage(
    left: Cluster,
    right: Cluster,
    pairwise_distances: Mapping[tuple[int, int], Fraction],
) -> Fraction:
    total = Fraction(0, 1)
    for left_number in left:
        for right_number in right:
            total += _distance(left_number, right_number, pairwise_distances)
    return total / (len(left) * len(right))


def _agglomerative_clusters(
    pairwise_distances: Mapping[tuple[int, int], Fraction],
) -> tuple[Cluster, ...]:
    clusters: list[Cluster] = [(number,) for number in NUMBER_DOMAIN]
    while len(clusters) > FINAL_CLUSTER_COUNT:
        best_key: tuple[Fraction, tuple[Cluster, Cluster]] | None = None
        best_indexes: tuple[int, int] | None = None
        for left_index in range(len(clusters) - 1):
            for right_index in range(left_index + 1, len(clusters)):
                left = clusters[left_index]
                right = clusters[right_index]
                canonical_pair = _canonical_cluster_pair(left, right)
                candidate_key = (
                    _average_linkage(left, right, pairwise_distances),
                    canonical_pair,
                )
                if best_key is None or candidate_key < best_key:
                    best_key = candidate_key
                    best_indexes = (left_index, right_index)

        if best_indexes is None:  # pragma: no cover - 49 singletons make this unreachable
            raise RuntimeError("no agglomerative merge pair available")
        left_index, right_index = best_indexes
        merged = tuple(sorted((*clusters[left_index], *clusters[right_index])))
        clusters = [cluster for index, cluster in enumerate(clusters) if index not in best_indexes]
        clusters.append(merged)
        clusters.sort(key=lambda cluster: (cluster[0], cluster))
    return tuple(clusters)


def _cluster_components(
    clusters: Sequence[Cluster],
    pairwise_distances: Mapping[tuple[int, int], Fraction],
) -> tuple[tuple[int, ...], NumberFractions, NumberFractions]:
    medoids: list[int] = []
    losses: NumberFractions = {}
    ranks: NumberFractions = {}
    for cluster in clusters:
        cluster_size = len(cluster)
        for number in cluster:
            total = Fraction(0, 1)
            for member in cluster:
                total += _distance(number, member, pairwise_distances)
            losses[number] = total / cluster_size

        ordered = tuple(sorted(cluster, key=lambda number: (losses[number], number)))
        medoids.append(ordered[0])
        if cluster_size == 1:
            ranks[ordered[0]] = Fraction(1, 1)
            continue
        for position, number in enumerate(ordered, start=1):
            ranks[number] = Fraction(cluster_size - position, cluster_size - 1)
    return tuple(medoids), losses, ranks


def _renyi2_collision(counts: Mapping[int, int], window: int) -> Fraction:
    collision = Fraction(0, 1)
    mass_denominator = 6 * window
    for number in NUMBER_DOMAIN:
        probability = Fraction(counts[number], mass_denominator)
        collision += probability * probability
    return collision


def _renyi2_collisions(profile_counts: Mapping[int, Mapping[int, int]]) -> NumberFractions:
    return {window: _renyi2_collision(profile_counts[window], window) for window in PROFILE_WINDOWS}


def _assign_regime(collisions: Mapping[int, Fraction]) -> RegimeAssignment:
    short = collisions[10]
    medium = collisions[30]
    long = collisions[100]
    if short >= medium >= long and short > long:
        return RegimeAssignment(RECENT_CONCENTRATION, 10)
    if short <= medium <= long and short < long:
        return RegimeAssignment(RECENT_DIFFUSION, 100)
    return RegimeAssignment(TRANSITIONAL_OR_STABLE, 30)


def _state_frequency_windows(label: RegimeLabel) -> tuple[int, int, int]:
    if label == RECENT_CONCENTRATION:
        return (10, 30, 100)
    if label == RECENT_DIFFUSION:
        return (100, 30, 10)
    if label == TRANSITIONAL_OR_STABLE:
        return (30, 10, 100)
    raise ValueError(f"unknown regime label: {label}")


def _regime_ranks(
    profile_rates: Mapping[int, Mapping[int, Fraction]],
    assignment: RegimeAssignment,
) -> NumberFractions:
    first, second, third = _state_frequency_windows(assignment.label)
    ordered = tuple(
        sorted(
            NUMBER_DOMAIN,
            key=lambda number: (
                -profile_rates[first][number],
                -profile_rates[second][number],
                -profile_rates[third][number],
                number,
            ),
        )
    )
    return {number: Fraction(49 - position, 48) for position, number in enumerate(ordered, start=1)}


def _fused_scores(
    cluster_ranks: Mapping[int, Fraction],
    regime_ranks: Mapping[int, Fraction],
) -> NumberFractions:
    return {number: (cluster_ranks[number] + regime_ranks[number]) / 2 for number in NUMBER_DOMAIN}


def _select_cluster_winners(
    clusters: Sequence[Cluster],
    fused_scores: Mapping[int, Fraction],
    regime_ranks: Mapping[int, Fraction],
    cluster_ranks: Mapping[int, Fraction],
    losses: Mapping[int, Fraction],
    profile_rates: Mapping[int, Mapping[int, Fraction]],
    assignment: RegimeAssignment,
) -> tuple[int, ...]:
    active, second, third = _state_frequency_windows(assignment.label)
    if active != assignment.active_window:  # pragma: no cover - frozen assignments are total
        raise RuntimeError("regime label and active window disagree")

    winners: list[int] = []
    for cluster in clusters:
        winner = min(
            cluster,
            key=lambda number: (
                -fused_scores[number],
                -regime_ranks[number],
                -cluster_ranks[number],
                losses[number],
                -profile_rates[active][number],
                -profile_rates[second][number],
                -profile_rates[third][number],
                number,
            ),
        )
        winners.append(winner)
    return tuple(winners)


def predict_biglotto_l2_pairwise_profile_cluster_renyi2_regime_cluster_selection_weighted_score_100(
    history: object,
) -> ProfileClusterRenyi2Prediction | None:
    """Predict one six-number ticket from completed draws, oldest to newest.

    The entire supplied sequence is validated first.  A valid history shorter
    than 751 draws returns ``None``; malformed input always raises
    ``ValueError`` before any partial prediction or fallback is produced.
    """

    validated_history = _validated_history(history)
    if len(validated_history) < MIN_HISTORY:
        return None

    profile_counts = _build_profile_counts(validated_history)
    profile_rates = _build_profile_rates(profile_counts)
    pairwise_distances = _build_pairwise_distances(profile_rates)
    final_clusters = _agglomerative_clusters(pairwise_distances)
    medoids, losses, cluster_ranks = _cluster_components(final_clusters, pairwise_distances)
    collision_values = _renyi2_collisions(profile_counts)
    regime_state = _assign_regime(collision_values)
    regime_ranks = _regime_ranks(profile_rates, regime_state)
    fused_scores = _fused_scores(cluster_ranks, regime_ranks)
    cluster_winners = _select_cluster_winners(
        final_clusters,
        fused_scores,
        regime_ranks,
        cluster_ranks,
        losses,
        profile_rates,
        regime_state,
    )
    ticket = tuple(sorted(cluster_winners))

    return ProfileClusterRenyi2Prediction(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        semantic_signature=SEMANTIC_SIGNATURE,
        profile_counts=profile_counts,
        profile_rates=profile_rates,
        collision_values=collision_values,
        regime_state=regime_state,
        final_clusters=final_clusters,
        medoids=medoids,
        cluster_ranks=cluster_ranks,
        regime_ranks=regime_ranks,
        fused_scores=fused_scores,
        cluster_winners=cluster_winners,
        ticket=ticket,
    )
