"""Focused tests for the sealed CLUSTERING + COVERAGE candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_clustering_coverage_weighted_score_100_candidate_batch_r1 as batch,
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
_ALTERNATE: Ticket = (7, 8, 9, 10, 11, 12)
_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_2939296CE8A4507C_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    for directory in (repo_root, *repo_root.parents):
        candidate = directory / ".task-data" / _AUTHORITY_ROOT_NAME
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


def _independent_coverage(
    history: tuple[Ticket, ...], pool: tuple[int, ...]
) -> tuple[
    tuple[tuple[Fraction, ...], ...],
    tuple[tuple[tuple[int, ...], ...], ...],
    tuple[tuple[int, ...], ...],
    tuple[Fraction, ...],
    tuple[int, ...],
    tuple[int, ...],
]:
    window_rates: list[tuple[Fraction, ...]] = []
    window_presence: list[tuple[tuple[int, ...], ...]] = []
    window_occurrences: list[tuple[int, ...]] = []
    for window in (50, 300, 750):
        draws = history[-window:]
        block_size = window // 5
        blocks = tuple(
            draws[index * block_size : (index + 1) * block_size]
            for index in range(5)
        )
        rates: list[Fraction] = []
        presence_for_window: list[tuple[int, ...]] = []
        occurrences_for_window: list[int] = []
        for number in pool:
            presence = tuple(
                int(any(number in draw for draw in block)) for block in blocks
            )
            rates.append(Fraction(sum(presence), 5))
            presence_for_window.append(presence)
            occurrences_for_window.append(
                sum(number in draw for block in blocks for draw in block)
            )
        window_rates.append(tuple(rates))
        window_presence.append(tuple(presence_for_window))
        window_occurrences.append(tuple(occurrences_for_window))
    multiscale = tuple(
        sum((window_rates[index][pool_index] for index in range(3)), Fraction(0, 1))
        / 3
        for pool_index in range(10)
    )
    total_blocks = tuple(
        sum(
            window_presence[window_index][pool_index][block_index]
            for window_index in range(3)
            for block_index in range(5)
        )
        for pool_index in range(10)
    )
    total_occurrences = tuple(
        sum(window_occurrences[window_index][pool_index] for window_index in range(3))
        for pool_index in range(10)
    )
    return (
        tuple(window_rates),
        tuple(window_presence),
        tuple(window_occurrences),
        multiscale,
        total_blocks,
        total_occurrences,
    )


def test_authority_identity_signature_and_sealed_paths_are_exact() -> None:
    root = _authority_root()
    handoff = _authority()
    checksums = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    checksum_line = next(
        line for line in checksums if line.endswith("implementation_handoff.json")
    )
    expected_hash, relative_path = checksum_line.split(maxsplit=1)
    assert relative_path == "implementation_handoff.json"
    assert hashlib.sha256((root / relative_path).read_bytes()).hexdigest() == expected_hash

    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert handoff["IMPLEMENTATION_READY"] == "YES"
    assert handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert (
        handoff["EXPECTED_FOCUSED_TEST_MODULE"]
        == "tests/unit/"
        "test_biglotto_l2_pairwise_clustering_coverage_weighted_score_100_candidate_batch_r1.py"
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
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_1a5809093dc8c94c"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_MODULE == batch.IMPLEMENTATION_MODULE
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_SYMBOL == batch.IMPLEMENTATION_SYMBOL
    assert batch.CANDIDATE_METADATA.NATIVE_TICKET_COUNT == 1
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_clustering_parent_parity_is_exact_and_parent_is_not_mutated() -> None:
    history = _history(750)
    before = cluster_parent.calculate_temporal_profiles(history, 750)
    local_partition = batch.calculate_cluster_partition(history, 750)
    parent_partition = cluster_parent.calculate_cluster_partition(history, 750)
    assert local_partition == parent_partition
    assert batch.calculate_temporal_profiles(history, 750) == before
    assert batch.TemporalProfileState is cluster_parent.TemporalProfileState
    assert batch.ClusterPartition is cluster_parent.ClusterPartition
    assert batch.compute_point_distance is cluster_parent.compute_point_distance


def test_coverage_uses_exact_five_block_multiscale_definition_and_ties() -> None:
    history = _history(750)
    pool = batch.calculate_cluster_partition(history, 750).SOURCE_NUMBER_POOL
    expected = _independent_coverage(history, pool)
    statistics = batch.calculate_coverage_statistics(history, 750, pool)
    assert expected[0] == statistics.WINDOW_COVERAGE_RATES
    assert expected[1] == statistics.WINDOW_BLOCK_PRESENCE
    assert expected[2] == statistics.WINDOW_OCCURRENCE_COUNTS
    assert expected[3] == statistics.MULTISCALE_COVERAGE_SCORES
    assert expected[4] == statistics.TOTAL_BLOCK_PRESENCE
    assert expected[5] == statistics.TOTAL_OCCURRENCE_COUNTS

    ranking = batch.calculate_coverage_ranking(history, 750)
    assert pool == ranking.POOL_NUMBERS
    assert expected[3] == ranking.RAW_SCORES
    expected_order = tuple(
        sorted(
            pool,
            key=lambda number: (
                -expected[3][pool.index(number)],
                -expected[4][pool.index(number)],
                -expected[5][pool.index(number)],
                number,
            ),
        )
    )
    assert expected_order == ranking.ORDERED_NUMBERS
    assert ranking.NORMALIZED_RANKS[pool.index(expected_order[0])] == Fraction(1, 1)
    assert ranking.NORMALIZED_RANKS[pool.index(expected_order[-1])] == Fraction(0, 1)

    tied = batch.rank_coverage_scores(
        [Fraction(0, 1)] * 10,
        [3, 3, 2, 0, 0, 0, 0, 0, 0, 0],
        [4, 5, 4, 0, 0, 0, 0, 0, 0, 0],
        tuple(range(1, 11)),
    )
    assert tied.ORDERED_NUMBERS[:3] == (2, 1, 3)
    assert tied.normalized_rank(2) == Fraction(1, 1)
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_coverage_scores(
            [0.1] + [Fraction(0, 1)] * 9,
            [0] * 10,
            [0] * 10,
            tuple(range(1, 11)),
        )


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
    snapshot = list(prefix)
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


def test_exact_fusion_weights_ties_and_pairwise_dependence() -> None:
    pool = tuple(range(1, 11))
    zeros = [Fraction(0, 1)] * 10
    clustering = zeros.copy()
    coverage = zeros.copy()
    clustering[0], coverage[0] = Fraction(3, 4), Fraction(0, 1)
    clustering[1], coverage[1] = Fraction(1, 2), Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(clustering, coverage, pool)
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert batch.FUSION_FORMULA == (
        "PAIRWISE_SCORE(m)=1/2*CLUSTERING_NORMALIZED_CLUSTER_ORDER_RANK_10(m)+"
        "1/2*COVERAGE_NORMALIZED_MULTISCALE_BLOCK_SPREAD_RANK_10(m);EXACT_RATIONAL"
    )

    tied_clustering = [Fraction(0, 1)] * 10
    tied_coverage = [Fraction(0, 1)] * 10
    tied_clustering[0], tied_coverage[0] = Fraction(1, 1), Fraction(0, 1)
    tied_clustering[1], tied_coverage[1] = Fraction(3, 4), Fraction(1, 4)
    tied_clustering[2], tied_coverage[2] = Fraction(1, 4), Fraction(3, 4)
    tied = batch.rank_pairwise_scores(tied_clustering, tied_coverage, pool)
    assert tied.RANKED_NUMBERS[:3] == (2, 3, 1)

    changed_clustering = zeros.copy()
    changed_clustering[4] = Fraction(1, 1)
    changed_coverage = zeros.copy()
    changed_coverage[6] = Fraction(1, 1)
    assert batch.rank_pairwise_scores(changed_clustering, zeros, pool).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, changed_coverage, pool).RANKED_NUMBERS[0] == 7

    pairwise = batch.rank_pairwise_scores(
        [Fraction(1, 1), Fraction(0, 1), Fraction(3, 4), *zeros[3:]],
        [Fraction(0, 1), Fraction(1, 1), Fraction(3, 4), *zeros[3:]],
        pool,
    )
    clustering_only = batch.rank_pairwise_scores(
        [Fraction(1, 1), Fraction(0, 1), Fraction(3, 4), *zeros[3:]],
        zeros,
        pool,
    )
    coverage_only = batch.rank_pairwise_scores(
        zeros,
        [Fraction(0, 1), Fraction(1, 1), Fraction(3, 4), *zeros[3:]],
        pool,
    )
    assert pairwise.RANKED_NUMBERS != clustering_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != coverage_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_component_callables_feed_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(750)
    pool = batch.calculate_cluster_partition(history, 750).SOURCE_NUMBER_POOL
    clustering = [Fraction(0, 1)] * 10
    coverage = [Fraction(0, 1)] * 10
    clustering[0] = Fraction(1, 1)
    coverage[1] = Fraction(1, 1)
    calls: list[str] = []

    def fake_clustering(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("clustering")
        return tuple(clustering)

    def fake_coverage(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("coverage")
        return tuple(coverage)

    monkeypatch.setattr(batch, "calculate_clustering_components", fake_clustering)
    monkeypatch.setattr(batch, "calculate_coverage_components", fake_coverage)
    result = batch.calculate_pairwise_ranking(history, 750)
    assert calls == ["clustering", "coverage"]
    assert result.clustering_component(pool[0]) == Fraction(1, 1)
    assert result.coverage_component(pool[1]) == Fraction(1, 1)


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
    assert tuple(ranking.position(number) for number in ranking.RANKED_NUMBERS) == tuple(
        range(1, 11)
    )
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert ranking.CLUSTERING_COMPONENTS != ranking.COVERAGE_COMPONENTS


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
