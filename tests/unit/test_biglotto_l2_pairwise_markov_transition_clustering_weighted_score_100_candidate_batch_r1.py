"""Focused tests for the sealed W=100 Markov + clustering candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate_batch_r1,
)
from lottolab.research import (
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as markov_parent,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as cluster_parent,
)

batch = biglotto_l2_pairwise_markov_transition_clustering_weighted_score_100_candidate_batch_r1

Ticket = tuple[int, int, int, int, int, int]

_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 13, 14, 15, 16),
    (2, 8, 17, 18, 19, 20),
    (30, 31, 32, 33, 34, 35),
    (36, 37, 38, 39, 40, 41),
    (42, 43, 44, 45, 46, 47),
    (44, 45, 46, 47, 48, 49),
)
_FILLER: Ticket = (1, 2, 3, 4, 5, 6)
_ALTERNATE: Ticket = (7, 8, 9, 10, 11, 12)
_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_8E17E64BB96C93DE_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".task-data" / _AUTHORITY_ROOT_NAME
        if candidate.is_dir():
            return candidate
    pytest.fail("sealed completed_v1_semantics task-data root is unavailable")


def _authority() -> dict[str, object]:
    return json.loads(
        (_authority_root() / "completed_v1_semantics.json").read_text(
            encoding="utf-8"
        )
    )


def _reference_markov_scores(history: tuple[Ticket, ...]) -> tuple[Fraction, ...]:
    window_draws = history[-101:]
    counts = [[0] * 49 for _ in range(49)]
    for source_draw, destination_draw in pairwise(window_draws):
        for source_number in source_draw:
            for destination_number in destination_draw:
                counts[source_number - 1][destination_number - 1] += 1
    outgoing = tuple(sum(row) for row in counts)
    probabilities = tuple(
        tuple(
            Fraction(value, outgoing[source_index])
            if outgoing[source_index]
            else Fraction(0, 1)
            for value in row
        )
        for source_index, row in enumerate(counts)
    )
    scores = [Fraction(0, 1)] * 49
    for source_number in window_draws[-1]:
        for candidate_number, probability in enumerate(
            probabilities[source_number - 1], start=1
        ):
            scores[candidate_number - 1] += probability / 6
    return tuple(scores)


def _parent_partition_for_local_state(
    state: batch.TemporalProfileState,
) -> cluster_parent.ClusterPartition:
    parent_rates = tuple(
        (profile[0], Fraction(0, 1), Fraction(0, 1))
        for profile in state.PROFILES
    )
    parent_counts = tuple(
        (count, 0, 0) for count in state.OCCURRENCE_COUNTS
    )
    parent_state = cluster_parent.TemporalProfileState(
        OCCURRENCE_COUNTS=parent_counts,
        RATES=parent_rates,
        PAIRWISE_DISTANCES=state.PAIRWISE_DISTANCES,
    )
    return cluster_parent.perform_hierarchical_clustering(parent_state)


def test_authority_manifest_identity_and_signature_are_exact() -> None:
    authority_root = _authority_root()
    for line in (authority_root / "SHA256SUMS").read_text(
        encoding="utf-8"
    ).splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        path = authority_root / relative_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash

    authority = _authority()
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"

    signature_object = cast(dict[str, object], authority["DESIGN_SIGNATURE_OBJECT"])
    canonical = json.dumps(
        signature_object,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == batch.DESIGN_SIGNATURE_SHA256
    assert (
        batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS)
        == batch.DESIGN_SIGNATURE_SHA256
    )


def test_authority_controlled_semantics_are_reproduced() -> None:
    authority_value = cast(dict[str, object], _authority()["DESIGN_SIGNATURE_OBJECT"])
    required = (
        "PARENT_SOURCE_UNIVERSE_ID_1",
        "PARENT_SOURCE_UNIVERSE_ID_2",
        "PARENT_COMPONENT_RULE_1",
        "PARENT_COMPONENT_RULE_2",
        "PARENT_WINDOW_RULE_1",
        "PARENT_WINDOW_RULE_2",
        "MINIMUM_HISTORY",
        "COMPONENT_NORMALIZATION_RULE",
        "COMPONENT_SCORE_DOMAIN_1",
        "COMPONENT_SCORE_DOMAIN_2",
        "FUSION_WEIGHT_1",
        "FUSION_WEIGHT_2",
        "FUSION_FORMULA",
        "NUMBER_RANKING_RULE",
        "NUMBER_TIE_BREAK_RULE",
        "RANKED_POOL_DOMAIN",
        "RANKED_POOL_CARDINALITY",
        "CANDIDATE_CONSTRUCTION_RULE",
        "TICKET_CONSTRUCTION",
        "TICKET_SELECTION_RULE",
        "NATIVE_TICKET_COUNT",
        "CAUSAL_CUTOFF_RULE",
        "FALLBACK_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
    )
    for key in required:
        expected = authority_value[key]
        actual = batch.SOURCE_UNIVERSE_CONTRACT[key]
        if isinstance(expected, list):
            assert actual == tuple(cast(list[object], expected))
        else:
            assert actual == expected


def test_candidate_count_and_identity_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_d9930aebfbbee697"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.DESIGN_ID == batch.DESIGN_ID
    assert (
        batch.CANDIDATE_METADATA.DESIGN_SIGNATURE_SHA256
        == batch.DESIGN_SIGNATURE_SHA256
    )
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    identity = batch.derive_candidate_identity(batch.CANDIDATE_SEMANTICS)
    assert identity.CANDIDATE_ID == batch.CANDIDATE_ID
    assert identity.SIGNATURE_HASH == batch.DESIGN_SIGNATURE_SHA256
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_markov_w100_parent_parity_and_zero_outgoing_semantics() -> None:
    history = _history(751)
    assert batch.calculate_markov_raw_scores(history, 751) == _reference_markov_scores(
        history
    )

    window = history[-101:]
    counts = batch.build_transition_counts(window)
    assert sum(map(sum, counts)) == 100 * 36
    assert counts == markov_parent.build_transition_counts(window)
    probabilities = batch.calculate_conditional_transition_probabilities(counts)
    assert probabilities == markov_parent.calculate_conditional_transition_probabilities(
        counts
    )
    zero_counts = batch.build_transition_counts(tuple(_FILLER for _ in range(101)))
    zero_probabilities = batch.calculate_conditional_transition_probabilities(zero_counts)
    assert zero_probabilities[48] == (Fraction(0, 1),) * 49

    no_outgoing_anchor = (*(_FILLER for _ in range(750)), (43, 44, 45, 46, 47, 48))
    assert sum(batch.calculate_markov_raw_scores(no_outgoing_anchor, 751)) == Fraction(0, 1)


def test_clustering_w100_parent_algorithm_parity_is_exact() -> None:
    history = _history(751)
    state = batch.calculate_temporal_profiles(history, 751)
    expected_counts = [0] * 49
    for draw in history[-100:]:
        for number in draw:
            expected_counts[number - 1] += 1
    assert tuple(expected_counts) == state.OCCURRENCE_COUNTS
    assert all(
        profile == (Fraction(count, 100),)
        for count, profile in zip(expected_counts, state.PROFILES, strict=True)
    )

    local_partition = batch.perform_hierarchical_clustering(state)
    reference_partition = _parent_partition_for_local_state(state)
    assert local_partition.CLUSTERS == reference_partition.CLUSTERS
    assert local_partition.ORDERED_CLUSTERS == reference_partition.ORDERED_CLUSTERS
    assert local_partition.ORDERED_REPRESENTATIVES == reference_partition.ORDERED_REPRESENTATIVES
    assert local_partition.MEDOID_COSTS == reference_partition.MEDOID_COSTS
    assert local_partition.COMPACTNESS_SCORES == reference_partition.COMPACTNESS_SCORES
    assert batch.compute_point_distance((Fraction(1, 100),), (Fraction(3, 100),)) == Fraction(1, 50)
    assert cluster_parent.compute_point_distance(
        (Fraction(1, 100), Fraction(1, 100), Fraction(1, 100)),
        (Fraction(3, 100), Fraction(3, 100), Fraction(3, 100)),
    ) == Fraction(1, 50)


def test_minimum_history_malformed_history_and_causal_cutoff() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.calculate_pairwise_ranking(_history(750), 750)
    accepted = batch.calculate_pairwise_ranking(_history(751), 751)
    assert len(accepted.RANKED_NUMBERS) == batch.RANKED_POOL_CARDINALITY

    malformed = list(_history(751))
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 751)
    with pytest.raises(ValueError, match="exactly six"):
        batch.calculate_pairwise_ranking([(*_FILLER, 7)] * 751, 751)

    history = list(_history(751))
    snapshot = history.copy()
    expected = batch.produce_candidate_portfolio(history, 751)
    with_target_and_future = [*history, _ALTERNATE, object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected
    with_target_and_future[751] = (13, 14, 15, 16, 17, 18)
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected
    assert history == snapshot
    assert batch.produce_candidate_portfolio(iter(history), 751) == expected


def test_window_causality_is_exact_and_future_suffix_invariant() -> None:
    history = [_FILLER for _ in range(650)] + [_FILLER, _ALTERNATE]
    history.extend(_FILLER for _ in range(99))
    markov_baseline = batch.calculate_markov_raw_scores(history, 751)
    clustering_baseline = batch.calculate_clustering_ranking(history, 751)

    older_change = history.copy()
    older_change[649] = _ALTERNATE
    assert batch.calculate_markov_raw_scores(older_change, 751) == markov_baseline
    assert batch.calculate_clustering_ranking(older_change, 751) == clustering_baseline

    markov_window_change = history.copy()
    markov_window_change[650] = _ALTERNATE
    assert batch.calculate_markov_raw_scores(markov_window_change, 751) != markov_baseline
    assert batch.calculate_clustering_ranking(markov_window_change, 751) == clustering_baseline

    cluster_window_change = history.copy()
    cluster_window_change[651] = _FILLER
    assert batch.calculate_clustering_ranking(cluster_window_change, 751) != clustering_baseline


def test_component_normalization_is_exact_and_tie_deterministic() -> None:
    pool = tuple(range(1, 11))
    raw = [Fraction(0, 1)] * 49
    raw[0] = Fraction(1, 1)
    raw[1] = Fraction(1, 1)
    ranking = batch.rank_markov_scores(raw, pool)
    assert ranking.ORDERED_NUMBERS[:2] == (1, 2)
    assert ranking.position(1) == 1
    assert ranking.position(2) == 2
    assert ranking.normalized_rank(1) == Fraction(9, 9)
    assert ranking.normalized_rank(2) == Fraction(8, 9)
    assert ranking.normalized_rank(10) == Fraction(0, 1)
    assert ranking.POOL_NORMALIZED_RANKS == ranking.NORMALIZED_RANKS
    assert all(isinstance(value, Fraction) for value in ranking.NORMALIZED_RANKS)
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_markov_scores([0.1] + [Fraction(0, 1)] * 48, pool)


def test_fusion_weights_formula_and_pairwise_tie_break_are_exact() -> None:
    pool = tuple(range(1, 11))
    zeros = [Fraction(0, 1)] * 10
    markov = zeros.copy()
    clustering = zeros.copy()
    markov[0] = Fraction(3, 4)
    clustering[0] = Fraction(0, 1)
    markov[1] = Fraction(1, 2)
    clustering[1] = Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(markov, clustering, pool)
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert batch.FUSION_FORMULA == (
        "PAIRWISE_SCORE(m)=1/2*TRANSITION_MARKOV_NORMALIZED_RANK_10(m)+"
        "1/2*CLUSTERING_NORMALIZED_CLUSTER_ORDER_RANK_10(m);EXACT_RATIONAL"
    )

    tied_markov = [Fraction(0, 1)] * 10
    tied_clustering = [Fraction(0, 1)] * 10
    tied_markov[0], tied_clustering[0] = Fraction(1, 1), Fraction(0, 1)
    tied_markov[1], tied_clustering[1] = Fraction(3, 4), Fraction(1, 4)
    tied_markov[2], tied_clustering[2] = Fraction(1, 4), Fraction(3, 4)
    tied = batch.rank_pairwise_scores(tied_markov, tied_clustering, pool)
    assert tied.pairwise_score(1) == tied.pairwise_score(2)
    assert tied.RANKED_NUMBERS[:3] == (2, 3, 1)


def test_each_parent_can_change_fused_order_and_pair_is_not_singleton() -> None:
    pool = tuple(range(1, 11))
    zeros = [Fraction(0, 1)] * 10
    changed_markov = zeros.copy()
    changed_markov[4] = Fraction(1, 1)
    changed_clustering = zeros.copy()
    changed_clustering[6] = Fraction(1, 1)
    assert batch.rank_pairwise_scores(changed_markov, zeros, pool).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, changed_clustering, pool).RANKED_NUMBERS[0] == 7

    markov = zeros.copy()
    clustering = zeros.copy()
    markov[0], markov[2] = Fraction(1, 1), Fraction(3, 4)
    clustering[1], clustering[2] = Fraction(1, 1), Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(markov, clustering, pool)
    markov_only = batch.rank_pairwise_scores(markov, zeros, pool)
    clustering_only = batch.rank_pairwise_scores(zeros, clustering, pool)
    assert pairwise.RANKED_NUMBERS != markov_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != clustering_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_pool_ticket_shape_determinism_and_component_participation() -> None:
    history = _history(751)
    partition = batch.calculate_cluster_partition(history, 751)
    pool = partition.SOURCE_NUMBER_POOL
    assert len(pool) == batch.RANKED_POOL_CARDINALITY == 10
    assert len(set(pool)) == 10
    assert set(pool).issubset(set(range(1, 50)))

    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert pool == ranking.POOL_NUMBERS
    assert tuple(
        ranking.position(number) for number in ranking.RANKED_NUMBERS
    ) == tuple(range(1, 11))
    assert set(ranking.RANKED_NUMBERS) == set(pool)
    assert len(ranking.NATIVE_TICKET) == 6
    assert len(set(ranking.NATIVE_TICKET)) == 6
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert ranking.TICKETS == (ranking.NATIVE_TICKET,)
    assert batch.produce_candidate_portfolio(history, 751) == batch.produce_candidate_portfolio(
        history, 751
    )
    assert ranking.TRANSITION_MARKOV_COMPONENTS != ranking.CLUSTERING_COMPONENTS


def test_research_module_is_isolated_from_runtime_and_empirical_paths() -> None:
    source = Path(batch.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert not imported_roots.intersection(
        {"sqlite3", "socket", "subprocess", "time", "urllib", "requests", "random"}
    )
    assert "production_catalog" not in source
    assert "registry" not in source
    assert "replay" not in source
    assert "leaderboard" not in source
    assert "OFFICIAL_ANY_PRIZE" not in source
