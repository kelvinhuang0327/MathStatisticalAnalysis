"""Focused validation for the sealed HOT_COLD + BAYESIAN candidate."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path
from typing import cast

import pytest

batch = importlib.import_module(
    "lottolab.research."
    "biglotto_l2_pairwise_hot_cold_bayesian_probabilistic_weighted_score_50_candidate_batch_r1"
)
hot_cold_reference = importlib.import_module(
    "lottolab.research."
    "biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1"
)
bayes_parent = importlib.import_module(
    "lottolab.research."
    "biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1"
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
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_E00095F81602A581_R1"
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


def test_authority_identity_signature_paths_and_task_hashes_are_exact() -> None:
    root = _authority_root()
    handoff = _authority()
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        assert hashlib.sha256((root / relative_path).read_bytes()).hexdigest() == expected_hash

    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert handoff["IMPLEMENTATION_READY"] == "YES"
    assert handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert handoff["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.IMPLEMENTATION_SYMBOL
    assert handoff["EXPECTED_SOURCE_PATH"] == batch.EXPECTED_SOURCE_PATH
    assert handoff["EXPECTED_FOCUSED_TEST_MODULE"] == batch.EXPECTED_FOCUSED_TEST_MODULE

    authority_semantics = cast(dict[str, object], handoff["DESIGN_SIGNATURE_OBJECT"])
    assert batch.canonicalize_semantic_record(authority_semantics) == (
        batch.canonicalize_semantic_record(batch.CANDIDATE_SEMANTICS)
    )
    assert hashlib.sha256(
        batch.canonicalize_semantic_record(authority_semantics)
    ).hexdigest() == batch.DESIGN_SIGNATURE_SHA256


def test_frontier_next_semantics_are_reproduced_exactly() -> None:
    next_semantics = cast(
        dict[str, object],
        json.loads(
            (_authority_root() / "next_candidate_semantics.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    assert batch.canonicalize_semantic_record(next_semantics) == (
        batch.canonicalize_semantic_record(batch.CANDIDATE_SEMANTICS)
    )
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_candidate_identity_and_determinism_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_MODULE == batch.IMPLEMENTATION_MODULE
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_SYMBOL == batch.IMPLEMENTATION_SYMBOL
    assert batch.CANDIDATE_METADATA.NATIVE_TICKET_COUNT == 1
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_hot_cold_parent_primitive_parity_is_exact() -> None:
    history = _history(751)
    local_raw = batch.calculate_hot_cold_raw_scores(history, 751)
    reference_raw = hot_cold_reference.calculate_hot_cold_raw_scores(history, 751)
    assert local_raw == reference_raw
    local_ranking = batch.calculate_hot_cold_ranking(history, 751)
    reference_ranking = hot_cold_reference.calculate_hot_cold_ranking(history, 751)
    assert local_ranking.NORMALIZED_RANKS == reference_ranking.NORMALIZED_RANKS
    assert local_ranking.ORDERED_NUMBERS == reference_ranking.ORDERED_NUMBERS
    assert batch.calculate_hot_cold_components(history, 751) == local_ranking.NORMALIZED_RANKS


def test_bayesian_parent_window_and_fusion_parity_is_exact() -> None:
    history = _history(751)
    local_windows = batch.calculate_bayesian_window_rankings(history, 751)
    parent_windows = bayes_parent.calculate_window_rankings(history, 751)
    assert local_windows == parent_windows
    assert tuple(window.WINDOW for window in local_windows) == (50, 300, 750)

    one_window = batch.calculate_bayesian_window_ranking(history, 751, 50)
    assert one_window == parent_windows[0]
    assert bayes_parent.calculate_bma_scores(history, 751, 50) == one_window.BMA_PREDICTIVE

    local_fused = batch.calculate_fused_bayesian_ranking(history, 751)
    parent_fused = bayes_parent.fuse_window_rankings(parent_windows)
    assert local_fused == parent_fused
    assert batch.calculate_bayesian_components(history, 751) == local_fused.MEAN_RANKS


def test_final_fusion_is_exact_and_both_parent_components_participate() -> None:
    history = _history(751)
    result = batch.calculate_pairwise_ranking(history, 751)
    hot_cold = batch.calculate_hot_cold_components(history, 751)
    bayesian = batch.calculate_bayesian_components(history, 751)
    assert hot_cold != bayesian
    assert hot_cold == result.HOT_COLD_COMPONENTS
    assert bayesian == result.BAYESIAN_PROBABILISTIC_COMPONENTS

    for number in batch.LEGAL_NUMBERS:
        assert result.pairwise_score(number) == (
            hot_cold[number - 1] + bayesian[number - 1]
        ) / 2

    expected_order = tuple(
        sorted(
            batch.LEGAL_NUMBERS,
            key=lambda number: (
                -result.pairwise_score(number),
                -min(hot_cold[number - 1], bayesian[number - 1]),
                -hot_cold[number - 1],
                -bayesian[number - 1],
                number,
            ),
        )
    )
    assert expected_order == result.RANKED_NUMBERS


def test_exact_rank_pairwise_ties_and_ticket_shape() -> None:
    hot_cold = [cast(object, 0)] * 49
    bayesian = [cast(object, 0)] * 49
    from fractions import Fraction

    hot_cold[0] = Fraction(1, 1)
    bayesian[1] = Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(hot_cold, bayesian)
    assert ranking.RANKED_NUMBERS[:2] == (1, 2)
    assert ranking.pairwise_score(1) == Fraction(1, 2)
    assert ranking.pairwise_score(2) == Fraction(1, 2)
    assert ranking.NATIVE_TICKET == (1, 2, 3, 4, 5, 6)
    assert _legal_ticket(ranking.NATIVE_TICKET)
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pairwise_scores([0.1] + [Fraction(0, 1)] * 48, bayesian)


def test_history_minimum_malformed_and_causal_cutoff() -> None:
    history = _history(751)
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum"):
        batch.calculate_pairwise_ranking(history, 750)

    malformed = list(history)
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="duplicate number"):
        batch.calculate_pairwise_ranking(malformed, 751)

    prefix = list(history)
    snapshot = list(prefix)
    expected = batch.produce_candidate_portfolio(prefix, 751)
    with_target_and_future: list[object] = [*prefix, _ALTERNATE, object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected
    with_target_and_future[751] = (44, 45, 46, 47, 48, 49)
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected
    assert batch.produce_candidate_portfolio(iter(prefix), 751) == expected
    assert prefix == snapshot


def test_research_module_isolated_from_runtime_and_empirical_paths() -> None:
    source = Path(cast(str, batch.__file__)).read_text(encoding="utf-8")
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


def test_output_is_one_deterministic_native_ticket() -> None:
    history = _history(751)
    first = batch.produce_candidate_portfolio(history, 751)
    second = batch.produce_candidate_portfolio(history, 751)
    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert first == second == (ranking.NATIVE_TICKET,)
    assert len(first) == batch.NATIVE_TICKET_COUNT == 1
    assert _legal_ticket(first[0])
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert tuple(ranking.position(number) for number in ranking.RANKED_NUMBERS) == tuple(
        range(1, 50)
    )
