"""Focused acceptance tests for the sealed GRAPH + CONSTRAINT candidate."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Sequence
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1,
    biglotto_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1,
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1,
)

graph_parent = biglotto_graph_network_multi_ticket_candidate_batch_r1
batch = biglotto_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1
constraint_parent = (
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1
)

Ticket = tuple[int, int, int, int, int, int]
_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_5F0C6FB3405F7F78_R2_FRESH_CONTEXT"
)
_TASK_DATA_ROOT_NAME = (
    "BIGLOTTO_L2_PAIRWISE_GRAPH_CONSTRAINT_WEIGHTED_SCORE_100_CANDIDATE_BATCH_R1"
)
_VALID_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 12, 23, 34, 45, 46),
    (2, 13, 24, 35, 46, 47),
    (3, 14, 25, 36, 47, 48),
    (4, 15, 26, 37, 48, 49),
)
_INVALID_DRAW: Ticket = (1, 2, 3, 4, 5, 6)


def _authority_root() -> Path:
    direct = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data") / _AUTHORITY_ROOT_NAME
    if direct.is_dir():
        return direct
    pytest.fail("clean R2 authority root is unavailable")


def _authority_file(name: str) -> object:
    return json.loads((_authority_root() / name).read_text(encoding="utf-8"))


def _task_data_root() -> Path:
    direct = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data") / _TASK_DATA_ROOT_NAME
    if direct.is_dir():
        return direct
    pytest.fail("candidate task-data root is unavailable")


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(
        _VALID_DRAW_TYPES[index % len(_VALID_DRAW_TYPES)]
        if index % 5
        else _INVALID_DRAW
        for index in range(count)
    )


def _always_true(_ticket: Sequence[int]) -> bool:
    return True


def _always_false(_ticket: Sequence[int]) -> bool:
    return False


def test_clean_r2_authority_checksum_identity_and_expected_paths_are_exact() -> None:
    authority_root = _authority_root()
    for line in (authority_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        actual_hash = hashlib.sha256((authority_root / relative_path).read_bytes()).hexdigest()
        assert actual_hash == expected_hash

    handoff = cast(dict[str, object], _authority_file("implementation_handoff.json"))
    semantics = cast(dict[str, object], _authority_file("completed_v1_semantics.json"))
    manifest = cast(dict[str, object], _authority_file("run_manifest.json"))
    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert semantics["IMPLEMENTATION_READY"] == "YES"
    assert handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert handoff["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.IMPLEMENTATION_SYMBOL
    assert handoff["EXPECTED_FOCUSED_TEST_MODULE"] == (
        "tests/unit/test_biglotto_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1.py"
    )
    assert manifest["FRESH_WORKER_CONTEXT"] == "YES"
    assert manifest["PREVIOUS_BLOCKED_RUN_REUSED"] == "NO"
    assert manifest["PREVIOUS_BLOCKED_RUN_ARTIFACTS_READ"] == "NO"
    assert manifest["BROAD_CONTENT_SEARCH_EXECUTED"] == "NO"
    assert manifest["PERFORMANCE_FIREWALL_VIOLATION_COUNT"] == 0
    assert manifest["PERFORMANCE_ROOTS_READ"] == 0
    assert manifest["PERFORMANCE_VALUES_ACCESSED"] == "NO"
    assert manifest["REPLAY_EXECUTED"] == "NO"

    signature_object = cast(dict[str, object], handoff["DESIGN_SIGNATURE_OBJECT"])
    assert json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)) == signature_object
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )
    assert hashlib.sha256(
        json.dumps(
            signature_object,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest() == batch.DESIGN_SIGNATURE_SHA256


def test_candidate_identity_is_exactly_one_and_sealed() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_7434ffb53674510d"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.DESIGN_ID == batch.DESIGN_ID
    assert batch.CANDIDATE_METADATA.DESIGN_SIGNATURE_SHA256 == batch.DESIGN_SIGNATURE_SHA256
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    identity = batch.derive_candidate_identity(batch.CANDIDATE_SEMANTICS)
    assert identity.CANDIDATE_ID == batch.CANDIDATE_ID
    assert identity.SIGNATURE_HASH == batch.DESIGN_SIGNATURE_SHA256
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_task_data_outputs_are_complete_and_checksum_verified() -> None:
    root = _task_data_root()
    required = (
        "source_universe_contract.json",
        "candidate_authority.csv",
        "candidate_validation_handoff.csv",
        "candidate_batch_manifest.json",
        "SHA256SUMS",
    )
    assert all((root / name).is_file() for name in required)
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        actual_hash = hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
        assert actual_hash == expected_hash

    authority_rows = list(
        csv.DictReader((root / "candidate_authority.csv").open(newline="", encoding="utf-8"))
    )
    assert len(authority_rows) == 1
    assert authority_rows[0]["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority_rows[0]["DESIGN_ID"] == batch.DESIGN_ID
    assert authority_rows[0]["NATIVE_TICKET_COUNT"] == "1"

    validation_rows = list(
        csv.DictReader(
            (root / "candidate_validation_handoff.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    assert len(validation_rows) == 1
    assert validation_rows[0]["TECHNICAL_IMPLEMENTATION_STATUS"] == (
        "TECHNICAL_IMPLEMENTATION_COMPLETE"
    )
    assert validation_rows[0]["CATALOG_STATUS"] == "NOT_CATALOG_WIRED"
    assert validation_rows[0]["PERFORMANCE_VALIDATION_STATUS"] == "NOT_RUN"
    assert validation_rows[0]["REPLAY_STATUS"] == "NOT_RUN"
    assert validation_rows[0]["PERFORMANCE_CONTAMINATION_STATUS"] == (
        "TASK_SPECIFIC_CLEAN_WITH_PREEXISTING_UNRELATED_CONTEXT"
    )

    manifest = cast(
        dict[str, object],
        json.loads((root / "candidate_batch_manifest.json").read_text(encoding="utf-8")),
    )
    assert manifest["CANDIDATE_COUNT"] == 1
    assert manifest["CANDIDATE_IDS"] == [batch.CANDIDATE_ID]
    assert manifest["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256


def test_graph_parent_parity_and_top_ten_pool_are_exact() -> None:
    history = _history(751)
    actual_windows = batch.calculate_graph_window_rankings(history, 751)
    expected_windows = graph_parent.calculate_window_rankings(history, 751)
    assert actual_windows == expected_windows

    actual_fused = batch.calculate_graph_parent_ranking(history, 751)
    expected_fused = graph_parent.calculate_fused_number_ranking(history, 751)
    assert actual_fused == expected_fused
    assert batch.produce_graph_traversal_pool(history, 751) == expected_fused.TOP_NUMBERS
    assert batch.produce_graph_source_ticket_universe(history, 751) == (
        graph_parent.produce_b649_multiscale_graph_pagerank_ranked_pool_v1(history, 751)
    )


def test_constraint_parent_parity_and_predicate_are_exact() -> None:
    history = _history(751)
    assert batch.calculate_constraint_support_scores(history, 751) == (
        constraint_parent.calculate_constraint_support_scores(history, 751)
    )
    assert batch.constraint_predicate is constraint_parent.constraint_predicate
    assert batch.constraint_predicate(_VALID_DRAW_TYPES[0])
    assert not batch.constraint_predicate(_INVALID_DRAW)

    expected = [0] * 49
    for draw in history[-30:]:
        if constraint_parent.constraint_predicate(draw):
            for number in draw:
                expected[number - 1] += 1
    assert batch.calculate_constraint_support_scores(history, 751) == tuple(expected)


def test_history_gate_target_exclusion_suffix_invariance_and_input_immutability() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="751"):
        batch.calculate_pairwise_ranking(_history(750), 750)
    accepted = batch.calculate_pairwise_ranking(_history(751), 751)
    assert len(accepted.RANKED_NUMBERS) == 10

    history = list(_history(751))
    snapshot = history.copy()
    baseline = batch.produce_candidate_portfolio(history, 751)
    with_target_and_future: list[object] = [*history, _VALID_DRAW_TYPES[0], object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == baseline
    with_target_and_future[751] = (2, 4, 6, 8, 10, 12)
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == baseline
    assert history == snapshot

    malformed = history.copy()
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 751)


def test_pool_normalization_and_raw_ties_are_exact() -> None:
    pool = tuple(range(1, 11))
    tied = batch.rank_pool_component_scores(pool, (0,) * 10)
    assert pool == tied.ORDERED_NUMBERS
    assert tied.position(1) == 1
    assert tied.position(10) == 10
    assert tied.normalized_rank(1) == Fraction(9, 9)
    assert tied.normalized_rank(10) == Fraction(0, 9)

    one_high = (0,) * 9 + (1,)
    ranked = batch.rank_pool_component_scores(pool, one_high)
    assert ranked.ORDERED_NUMBERS[:3] == (10, 1, 2)
    assert ranked.normalized_rank(10) == Fraction(9, 9)


def test_exact_equal_weight_fusion_and_pairwise_dependence() -> None:
    pool = tuple(range(1, 11))
    descending = tuple(Fraction(10 - position, 9) for position in range(1, 11))
    ascending = tuple(Fraction(position - 1, 9) for position in range(1, 11))
    all_zero = (Fraction(0, 1),) * 10
    ranking = batch.rank_pairwise_scores(
        descending,
        ascending,
        pool_numbers=pool,
        predicate=_always_true,
    )
    assert all(score == Fraction(1, 2) for score in ranking.PAIRWISE_SCORES)
    assert (
        batch.FUSION_WEIGHT_1 * descending[0]
        + batch.FUSION_WEIGHT_2 * ascending[0]
    ) == ranking.SCORES[0].PAIRWISE_SCORE
    assert all(isinstance(score, Fraction) for score in ranking.PAIRWISE_SCORES)

    graph_changed = list(descending)
    graph_changed[0], graph_changed[1] = graph_changed[1], graph_changed[0]
    assert batch.rank_pairwise_scores(
        descending, all_zero, pool_numbers=pool, predicate=_always_true
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        tuple(graph_changed), all_zero, pool_numbers=pool, predicate=_always_true
    ).RANKED_NUMBERS

    constraint_changed = list(ascending)
    constraint_changed[0], constraint_changed[1] = (
        constraint_changed[1],
        constraint_changed[0],
    )
    assert batch.rank_pairwise_scores(
        all_zero, ascending, pool_numbers=pool, predicate=_always_true
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        all_zero, tuple(constraint_changed), pool_numbers=pool, predicate=_always_true
    ).RANKED_NUMBERS

    graph_spike = tuple(Fraction(1 if number == 1 else 0, 1) for number in pool)
    constraint_spike = tuple(Fraction(1 if number == 10 else 0, 1) for number in pool)
    fused = batch.rank_pairwise_scores(
        graph_spike,
        constraint_spike,
        pool_numbers=pool,
        predicate=_always_true,
    )
    graph_only = tuple(sorted(pool, key=lambda number: (-graph_spike[number - 1], number)))
    constraint_only = tuple(
        sorted(pool, key=lambda number: (-constraint_spike[number - 1], number))
    )
    assert graph_only != fused.RANKED_NUMBERS
    assert constraint_only != fused.RANKED_NUMBERS


def test_full_candidate_pool_ticket_search_and_determinism_are_exact() -> None:
    history = _history(751)
    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert batch.RANKED_POOL_DOMAIN == (
        "TOP_10_GRAPH_PAGERANK_NUMBERS_FROM_ALL_LEGAL_NUMBERS_1_TO_49"
    )
    assert batch.RANKED_POOL_CARDINALITY == 10
    assert len(ranking.RANKED_NUMBERS) == 10
    assert len(set(ranking.RANKED_NUMBERS)) == 10
    assert set(ranking.RANKED_NUMBERS) == set(ranking.GRAPH_POOL)
    assert len(ranking.SOURCE_TICKETS) == 210
    assert len(ranking.TICKETS) == 1
    assert tuple(sorted(ranking.NATIVE_TICKET)) == ranking.NATIVE_TICKET
    assert len(set(ranking.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in ranking.NATIVE_TICKET)
    assert batch.constraint_predicate(ranking.NATIVE_TICKET)

    expected = next(
        tuple(sorted(candidate))
        for candidate in combinations(ranking.RANKED_NUMBERS, 6)
        if batch.constraint_predicate(candidate)
    )
    assert expected == ranking.NATIVE_TICKET
    assert batch.produce_candidate_portfolio(history, 751) == (ranking.NATIVE_TICKET,)
    assert batch.produce_candidate_portfolio(history, 751) == (
        batch.produce_candidate_portfolio(history, 751)[0],
    )

    with pytest.raises(batch.ConstraintSearchExhaustedError, match="no six-number"):
        batch.select_first_admissible_ticket(tuple(range(1, 11)), _always_false)


def test_research_only_deterministic_module_has_no_external_wiring() -> None:
    module_source = Path(batch.__file__).read_text(encoding="utf-8")
    assert "lottolab.strategies.catalog" not in module_source
    assert "sqlite" not in module_source.lower()
    assert "import random" not in module_source.lower()
    assert batch.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
