"""Focused tests for the sealed ENTROPY + CLUSTERING candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_entropy_clustering_weighted_score_100_candidate_batch_r1 as batch,
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


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    root_name = "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_E121053C05D1FDFA_R1"
    for directory in (repo_root, *repo_root.parents):
        candidate = directory / ".task-data" / root_name
        if candidate.is_dir():
            return candidate
    pytest.fail("sealed predecessor authority root is unavailable")


def _authority() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (_authority_root() / "implementation_handoff.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _independent_entropy(
    history: tuple[Ticket, ...], pool: tuple[int, ...]
) -> tuple[tuple[int, ...], tuple[Fraction, ...]]:
    counts = tuple(
        sum(number in draw for draw in history[-50:]) for number in pool
    )
    raw_scores = tuple(
        Fraction(1, 1)
        / (abs(Fraction(count, 1) - Fraction(300, 49)) + Fraction(1, 10))
        for count in counts
    )
    return counts, raw_scores


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


def test_authority_checksums_identity_and_paths_are_exact() -> None:
    root = _authority_root()
    checksums = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    for line in checksums:
        expected_hash, relative_path = line.split(maxsplit=1)
        assert hashlib.sha256((root / relative_path).read_bytes()).hexdigest() == expected_hash

    handoff = _authority()
    assert handoff["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert handoff["IMPLEMENTATION_READY"] == "YES"
    assert handoff["IMPLEMENTATION_NOT_EXECUTED"] == "YES"
    assert handoff["IMPLEMENTATION_PATHS_FROZEN_EXACTLY"] == "YES"
    assert handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.EXPECTED_IMPLEMENTATION_MODULE
    assert handoff["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.EXPECTED_IMPLEMENTATION_SYMBOL
    assert handoff["EXPECTED_SOURCE_PATH"] == batch.EXPECTED_SOURCE_PATH
    assert handoff["EXPECTED_FOCUSED_TEST_MODULE"] == batch.EXPECTED_FOCUSED_TEST_MODULE

    repo_root = Path(__file__).resolve().parents[2]
    assert Path(batch.__file__).resolve() == repo_root / batch.EXPECTED_SOURCE_PATH
    assert Path(__file__).resolve() == repo_root / batch.EXPECTED_FOCUSED_TEST_MODULE

    completed = cast(
        dict[str, object],
        json.loads((root / "completed_v1_semantics.json").read_text(encoding="utf-8")),
    )
    assert completed == json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS))
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
    actual = json.loads(batch.canonical_semantic_json(batch.SOURCE_UNIVERSE_CONTRACT))
    assert actual == authority
    assert len(actual) == 39
    assert batch.PARENT_SOURCE_PATH_1 == "src/lottolab/strategies/adapters/biglotto_wave4.py"
    assert batch.PARENT_SOURCE_SYMBOL_1 == "_entropy_scores"
    assert batch.PARENT_SOURCE_SYMBOL_2 == "calculate_cluster_partition"


def test_candidate_identity_is_exactly_one_and_deterministic() -> None:
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_d8cd36c68f156ea5"
    assert batch.DESIGN_ID == "B649_PAIRWISE_ENTROPY_CLUSTERING_WEIGHTED_SCORE_100_V1"
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_MODULE == batch.IMPLEMENTATION_MODULE
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_SYMBOL == batch.IMPLEMENTATION_SYMBOL
    assert batch.CANDIDATE_METADATA.NATIVE_TICKET_COUNT == 1
    assert batch.RNG is None
    assert batch.RNG_SEMANTICS == "NONE"
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_clustering_parent_parity_and_parent_identity_are_exact() -> None:
    history = _history(750)
    assert batch.calculate_temporal_profiles(history, 750) == (
        cluster_parent.calculate_temporal_profiles(history, 750)
    )
    assert batch.calculate_cluster_partition(history, 750) == (
        cluster_parent.calculate_cluster_partition(history, 750)
    )
    partition = batch.calculate_cluster_partition(history, 750)
    assert len(partition.ORDERED_REPRESENTATIVES) == 10
    assert len(set(partition.ORDERED_REPRESENTATIVES)) == 10
    assert batch.TemporalProfileState is cluster_parent.TemporalProfileState
    assert batch.ClusterPartition is cluster_parent.ClusterPartition
    assert batch.compute_point_distance is cluster_parent.compute_point_distance
    assert batch.perform_hierarchical_clustering is cluster_parent.perform_hierarchical_clustering


def test_entropy_parent_has_exact_w50_count_score_and_tie_parity() -> None:
    history = _history(750)
    pool = batch.calculate_cluster_partition(history, 750).ORDERED_REPRESENTATIVES
    expected_counts, expected_raw = _independent_entropy(history, pool)
    statistics = batch.calculate_entropy_statistics(history, 750, pool)
    assert pool == statistics.POOL_NUMBERS
    assert expected_counts == statistics.COUNTS_50
    assert expected_raw == statistics.RAW_SCORES

    ranking = batch.calculate_entropy_ranking(history, 750, pool)
    expected_order = tuple(
        sorted(pool, key=lambda number: (-expected_raw[pool.index(number)], number))
    )
    assert expected_order == ranking.ORDERED_NUMBERS
    assert expected_raw == ranking.RAW_SCORES
    assert ranking.NORMALIZED_RANKS[pool.index(expected_order[0])] == Fraction(1, 1)
    assert ranking.NORMALIZED_RANKS[pool.index(expected_order[-1])] == Fraction(0, 1)

    tied_pool = tuple(range(49, 39, -1))
    tied = batch.rank_entropy_scores([Fraction(0, 1)] * 10, tied_pool)
    assert tuple(range(40, 50)) == tied.ORDERED_NUMBERS


def test_pairwise_fusion_is_exact_equal_weight_and_depends_on_both_components() -> None:
    pool = tuple(range(1, 11))
    entropy = tuple(Fraction(9 - index, 9) for index in range(10))
    clustering = entropy
    ranking = batch.rank_pairwise_scores(entropy, clustering, pool)
    assert tuple(
        (left + right) / 2 for left, right in zip(entropy, clustering, strict=True)
    ) == ranking.PAIRWISE_SCORES
    assert tuple(range(1, 11)) == ranking.RANKED_NUMBERS
    assert ranking.NATIVE_TICKET == (1, 2, 3, 4, 5, 6)

    entropy_changed = tuple(
        Fraction(1, 1) if index == 9 else Fraction(0, 1) for index in range(10)
    )
    clustering_changed = tuple(
        Fraction(1, 1) if index == 4 else Fraction(0, 1) for index in range(10)
    )
    assert batch.rank_pairwise_scores(
        entropy_changed, clustering, pool
    ).RANKED_NUMBERS != ranking.RANKED_NUMBERS
    assert batch.rank_pairwise_scores(
        entropy, clustering_changed, pool
    ).RANKED_NUMBERS != ranking.RANKED_NUMBERS


def test_pairwise_calculation_calls_and_retains_both_component_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(750)
    entropy = tuple(Fraction(9 - index, 9) for index in range(10))
    clustering = tuple(Fraction(index, 9) for index in range(10))
    calls: list[str] = []

    def fake_entropy(
        _history_input: object,
        _target_index: int,
        _pool_numbers: object = None,
    ) -> tuple[Fraction, ...]:
        calls.append("entropy")
        return entropy

    def fake_clustering(
        _history_input: object, _target_index: int
    ) -> tuple[Fraction, ...]:
        calls.append("clustering")
        return clustering

    monkeypatch.setattr(batch, "calculate_entropy_components", fake_entropy)
    monkeypatch.setattr(batch, "calculate_clustering_components", fake_clustering)
    ranking = batch.calculate_pairwise_ranking(history, 750)
    assert calls == ["entropy", "clustering"]
    assert entropy == ranking.ENTROPY_COMPONENTS
    assert clustering == ranking.CLUSTERING_COMPONENTS


def test_causal_cutoff_ignores_target_row_and_future_suffix() -> None:
    history = _history(752)
    changed = list(history)
    changed[750] = (7, 8, 9, 10, 11, 12)
    changed[751] = (37, 38, 39, 40, 41, 42)
    assert batch.produce_candidate_portfolio(history, 750) == (
        batch.produce_candidate_portfolio(tuple(changed), 750)
    )


def test_history_minimum_and_validation_fail_explicitly() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum 750"):
        batch.produce_candidate_portfolio(_history(749), 749)
    malformed = list(_history(750))
    malformed[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="duplicate"):
        batch.produce_candidate_portfolio(tuple(malformed), 750)
    with pytest.raises(ValueError, match="must not exceed"):
        batch.produce_candidate_portfolio(_history(750), 751)


def test_output_shape_is_one_sorted_native_ticket_and_source_is_isolated() -> None:
    history = _history(750)
    portfolio = batch.produce_candidate_portfolio(history, 750)
    assert len(portfolio) == 1
    assert _legal_ticket(portfolio[0])
    assert batch.produce_candidate(history, 750) == portfolio
    assert batch.produce_source_ticket_universe(history, 750) == portfolio

    tree = ast.parse(Path(batch.__file__).read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if node.module is not None
    )
    assert not any(
        forbidden in module_name
        for module_name in imported_modules
        for forbidden in ("random", "sqlite", "numpy", "pandas", "backtest", "catalog")
    )
