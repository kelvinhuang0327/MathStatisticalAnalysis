"""Focused tests for the sealed CLUSTERING + BAYESIAN_PROBABILISTIC candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_clustering_bayesian_probabilistic_weighted_score_100_candidate_batch_r1 as batch,  # noqa: E501
)
from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as bayes_parent,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as cluster_parent,
)

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
_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_ALTERNATE: Ticket = (7, 8, 9, 10, 11, 12)
_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_7434FFB53674510D_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".task-data" / _AUTHORITY_ROOT_NAME
        if candidate.is_dir():
            return candidate
    pytest.fail("sealed predecessor authority root is unavailable")


def _authority() -> dict[str, object]:
    return json.loads(
        (_authority_root() / "implementation_handoff.json").read_text(
            encoding="utf-8"
        )
    )


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    values = cast(tuple[object, ...], ticket)
    return (
        len(values) == 6
        and all(type(number) is int and 1 <= number <= 49 for number in values)
        and len(set(values)) == 6
        and tuple(sorted(cast(tuple[int, ...], values))) == values
    )


def test_authority_identity_signature_and_corrected_paths_are_exact() -> None:
    root = _authority_root()
    handoff = _authority()
    checksum_line = next(
        line
        for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        if line.endswith("implementation_handoff.json")
    )
    expected_hash, relative_path = checksum_line.split(maxsplit=1)
    assert relative_path == "implementation_handoff.json"
    assert hashlib.sha256((root / relative_path).read_bytes()).hexdigest() == expected_hash

    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert handoff["IMPLEMENTATION_READY"] == "YES"
    assert (
        handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    )
    assert (
        handoff["EXPECTED_FOCUSED_TEST_MODULE"]
        == "tests/unit/"
        "test_biglotto_l2_pairwise_clustering_bayesian_probabilistic_weighted_score_100_candidate_batch_r1.py"
    )

    signature_object = cast(dict[str, object], handoff["DESIGN_SIGNATURE_OBJECT"])
    canonical = json.dumps(
        signature_object,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == batch.DESIGN_SIGNATURE_SHA256
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_authority_controlled_semantics_are_reproduced() -> None:
    authority = cast(dict[str, object], _authority()["DESIGN_SIGNATURE_OBJECT"])
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
        expected = authority[key]
        actual = batch.SOURCE_UNIVERSE_CONTRACT[key]
        if isinstance(expected, list):
            assert actual == tuple(cast(list[object], expected))
        else:
            assert actual == expected


def test_candidate_identity_and_determinism_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_2939296ce8a4507c"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_MODULE == batch.IMPLEMENTATION_MODULE
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_SYMBOL == batch.IMPLEMENTATION_SYMBOL
    assert batch.CANDIDATE_METADATA.NATIVE_TICKET_COUNT == 1
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_clustering_parent_parity_is_exact() -> None:
    history = _history(750)
    local = batch.calculate_cluster_partition(history, 750)
    parent = cluster_parent.calculate_cluster_partition(history, 750)
    assert local.CLUSTERS == parent.CLUSTERS
    assert local.ORDERED_CLUSTERS == parent.ORDERED_CLUSTERS
    assert local.ORDERED_REPRESENTATIVES == parent.ORDERED_REPRESENTATIVES
    assert local.MEDOID_COSTS == parent.MEDOID_COSTS
    assert local.COMPACTNESS_SCORES == parent.COMPACTNESS_SCORES
    assert batch.TemporalProfileState is cluster_parent.TemporalProfileState
    assert batch.ClusterPartition is cluster_parent.ClusterPartition
    state = batch.calculate_temporal_profiles(history, 750)
    assert state == cluster_parent.calculate_temporal_profiles(history, 750)


def test_bayesian_parent_windows_and_pool_local_ties_are_exact() -> None:
    history = _history(750)
    pool = batch.calculate_cluster_partition(history, 750).SOURCE_NUMBER_POOL
    local_windows = batch.calculate_bayesian_window_rankings(history, 750)
    parent_windows = bayes_parent.calculate_window_rankings(history, 750)
    assert tuple(window.WINDOW for window in parent_windows) == (50, 300, 750)
    assert len(local_windows) == len(parent_windows) == 3
    for local, parent in zip(local_windows, parent_windows, strict=True):
        expected_raw = tuple(parent.bma_predictive(number) for number in pool)
        assert expected_raw == local.RAW_SCORES
        expected_order = tuple(
            sorted(
                pool,
                key=lambda number: (
                    -parent.bma_predictive(number),
                    -parent.posterior_m1(number),
                    -parent.predictive_m1(number),
                    number,
                ),
            )
        )
        assert expected_order == local.ORDERED_NUMBERS
        assert local.NORMALIZED_RANKS[
            local.POOL_NUMBERS.index(expected_order[0])
        ] == Fraction(1, 1)
        assert local.NORMALIZED_RANKS[
            local.POOL_NUMBERS.index(expected_order[-1])
        ] == Fraction(0, 1)

    raw = [Fraction(0, 1)] * 10
    posterior = [Fraction(0, 1)] * 10
    predictive = [Fraction(0, 1)] * 10
    raw[0] = raw[1] = Fraction(1, 1)
    posterior[0], posterior[1] = Fraction(1, 4), Fraction(3, 4)
    ranking = batch.rank_bayesian_scores(raw, posterior, predictive, tuple(range(1, 11)))
    assert ranking.ORDERED_NUMBERS[:2] == (2, 1)
    assert ranking.normalized_rank(1) == Fraction(8, 9)
    assert ranking.normalized_rank(10) == Fraction(0, 1)
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_bayesian_scores(
            [0.1] + [Fraction(0, 1)] * 9,
            posterior,
            predictive,
            tuple(range(1, 11)),
        )


def test_multiscale_bayesian_fusion_uses_exact_mean_and_robustness() -> None:
    history = _history(750)
    final = batch.calculate_bayesian_ranking(history, 750)
    local_windows = batch.calculate_bayesian_window_rankings(history, 750)
    pool = final.POOL_NUMBERS
    for index, number in enumerate(pool):
        window_ranks = tuple(window.normalized_rank(number) for window in local_windows)
        assert final.NORMALIZED_RANKS[index] == sum(window_ranks, Fraction(0, 1)) / 3
        assert final.ROBUSTNESS[index] == tuple(sorted(window_ranks))

    expected_order = tuple(
        sorted(
            pool,
            key=lambda number: (
                -final.normalized_rank(number),
                -final.robustness(number)[0],
                -final.robustness(number)[1],
                -final.robustness(number)[2],
                number,
            ),
        )
    )
    assert expected_order == final.ORDERED_NUMBERS
    assert all(isinstance(score, Fraction) for score in final.RAW_SCORES)


def test_history_minimum_malformed_and_causal_cutoff() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required"):
        batch.calculate_pairwise_ranking(_history(749), 749)
    accepted = batch.calculate_pairwise_ranking(_history(750), 750)
    assert len(accepted.RANKED_NUMBERS) == batch.RANKED_POOL_CARDINALITY

    malformed = list(_history(750))
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="duplicate number"):
        batch.calculate_pairwise_ranking(malformed, 750)
    malformed[10] = (1, 2, 3, 4, 5, 50)
    with pytest.raises(ValueError, match=r"1\.\.49"):
        batch.calculate_pairwise_ranking(malformed, 750)

    prefix = list(_history(750))
    snapshot = [draw for draw in prefix]
    expected = batch.produce_candidate_portfolio(prefix, 750)
    with_target_and_future = [*prefix, _ALTERNATE, object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == expected
    with_target_and_future[750] = (44, 45, 46, 47, 48, 49)
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == expected
    assert batch.produce_candidate_portfolio(iter(prefix), 750) == expected
    assert prefix == snapshot

    longer = list(_history(751))
    baseline = batch.produce_candidate_portfolio(longer, 751)
    longer[0] = _ALTERNATE
    assert batch.produce_candidate_portfolio(longer, 751) == baseline


def test_exact_fusion_weights_ties_and_both_parent_dependence() -> None:
    pool = tuple(range(1, 11))
    zeros = [Fraction(0, 1)] * 10
    clustering = zeros.copy()
    bayesian = zeros.copy()
    clustering[0], bayesian[0] = Fraction(3, 4), Fraction(0, 1)
    clustering[1], bayesian[1] = Fraction(1, 2), Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(clustering, bayesian, pool)
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert batch.FUSION_FORMULA == (
        "PAIRWISE_SCORE(m)=1/2*CLUSTERING_NORMALIZED_CLUSTER_ORDER_RANK_10(m)+"
        "1/2*BAYESIAN_PROBABILISTIC_NORMALIZED_BMA_RANK_10(m);EXACT_RATIONAL"
    )

    tied_clustering = [Fraction(0, 1)] * 10
    tied_bayesian = [Fraction(0, 1)] * 10
    tied_clustering[0], tied_bayesian[0] = Fraction(1, 1), Fraction(0, 1)
    tied_clustering[1], tied_bayesian[1] = Fraction(3, 4), Fraction(1, 4)
    tied_clustering[2], tied_bayesian[2] = Fraction(1, 4), Fraction(3, 4)
    tied = batch.rank_pairwise_scores(tied_clustering, tied_bayesian, pool)
    assert tied.RANKED_NUMBERS[:3] == (2, 3, 1)

    changed_clustering = zeros.copy()
    changed_clustering[4] = Fraction(1, 1)
    changed_bayesian = zeros.copy()
    changed_bayesian[6] = Fraction(1, 1)
    assert batch.rank_pairwise_scores(changed_clustering, zeros, pool).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, changed_bayesian, pool).RANKED_NUMBERS[0] == 7

    clustering = zeros.copy()
    bayesian = zeros.copy()
    clustering[0], clustering[2] = Fraction(1, 1), Fraction(3, 4)
    bayesian[1], bayesian[2] = Fraction(1, 1), Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(clustering, bayesian, pool)
    clustering_only = batch.rank_pairwise_scores(clustering, zeros, pool)
    bayesian_only = batch.rank_pairwise_scores(zeros, bayesian, pool)
    assert pairwise.RANKED_NUMBERS != clustering_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != bayesian_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_callables_feed_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(750)
    pool = batch.calculate_cluster_partition(history, 750).SOURCE_NUMBER_POOL
    clustering = [Fraction(0, 1)] * 10
    bayesian = [Fraction(0, 1)] * 10
    clustering[0] = Fraction(1, 1)
    bayesian[1] = Fraction(1, 1)
    calls: list[str] = []

    def fake_clustering(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("clustering")
        return tuple(clustering)

    def fake_bayesian(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("bayesian")
        return tuple(bayesian)

    monkeypatch.setattr(batch, "calculate_clustering_components", fake_clustering)
    monkeypatch.setattr(batch, "calculate_bayesian_components", fake_bayesian)
    result = batch.calculate_pairwise_ranking(history, 750)
    assert calls == ["clustering", "bayesian"]
    assert result.clustering_component(pool[0]) == Fraction(1, 1)
    assert result.bayesian_probabilistic_component(pool[1]) == Fraction(1, 1)


def test_pool_ticket_shape_determinism_and_component_participation() -> None:
    history = _history(750)
    partition = batch.calculate_cluster_partition(history, 750)
    pool = partition.SOURCE_NUMBER_POOL
    assert len(pool) == batch.RANKED_POOL_CARDINALITY == 10
    assert len(set(pool)) == 10
    assert set(pool).issubset(set(range(1, 50)))

    first = batch.produce_candidate_portfolio(history, 750)
    second = batch.produce_candidate_portfolio(history, 750)
    ranking = batch.calculate_pairwise_ranking(history, 750)
    assert first == second == (ranking.NATIVE_TICKET,)
    assert len(first) == batch.NATIVE_TICKET_COUNT == 1
    assert _legal_ticket(first[0])
    assert set(ranking.RANKED_NUMBERS) == set(pool)
    assert tuple(
        ranking.position(number) for number in ranking.RANKED_NUMBERS
    ) == tuple(range(1, 11))
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert ranking.CLUSTERING_COMPONENTS != ranking.BAYESIAN_PROBABILISTIC_COMPONENTS


def test_research_module_isolated_from_runtime_and_empirical_paths() -> None:
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
