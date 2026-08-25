"""Focused tests for the sealed ENTROPY + CONSTRAINT candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_entropy_constraint_weighted_score_50_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1,
)

constraint_parent = (
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1
)

Ticket = tuple[int, int, int, int, int, int]

TASK_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_D8CD36C68F156EA5_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(
        cast(
            Ticket,
            tuple(((draw_index + offset) % 49) + 1 for offset in range(6)),
        )
        for draw_index in range(count)
    )


def _authority() -> dict[str, object]:
    return json.loads(
        (TASK_ROOT / "implementation_handoff.json").read_text(encoding="utf-8")
    )


def _independent_entropy(history: tuple[Ticket, ...], target_index: int) -> tuple[Fraction, ...]:
    draws = history[target_index - 50 : target_index]
    expected = Fraction(300, 49)
    epsilon = Fraction(1, 10)
    return tuple(
        Fraction(1, 1)
        / (
            abs(
                Fraction(
                    sum(number in draw for draw in draws),
                    1,
                )
                - expected
            )
            + epsilon
        )
        for number in batch.LEGAL_NUMBERS
    )


def _reference_constraint(ticket: Sequence[int]) -> bool:
    numbers = tuple(ticket)
    if len(numbers) != 6 or len(set(numbers)) != 6:
        return False
    if not 2 <= sum(number % 2 for number in numbers) <= 4:
        return False
    zones = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))
    if sum(any(low <= number <= high for number in numbers) for low, high in zones) < 3:
        return False
    if not 120 <= sum(numbers) <= 180:
        return False
    ordered = sorted(numbers)
    runs = [ordered[index + 1] - ordered[index] for index in range(5)]
    longest = 1
    current = 1
    for delta in runs:
        if delta == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest <= 2 and len({number % 10 for number in numbers}) >= 4


def test_authority_checksums_identity_and_semantics_are_exact() -> None:
    authority = _authority()
    semantics = json.loads(
        (TASK_ROOT / "completed_v1_semantics.json").read_text(encoding="utf-8")
    )
    assert semantics == json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS))
    assert authority["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["DESIGN_SIGNATURE_OBJECT"] == json.loads(
        batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)
    )
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )
    sums = (TASK_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    for line in sums:
        expected, filename = line.split("  ", 1)
        actual = hashlib.sha256((TASK_ROOT / filename).read_bytes()).hexdigest()
        assert actual == expected


def test_candidate_identity_is_exactly_one_and_deterministic() -> None:
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert tuple(batch.CANDIDATE_AUTHORITY) == (batch.CANDIDATE_ID,)
    metadata = batch.CANDIDATE_METADATA
    assert metadata.DESIGN_ID == "B649_PAIRWISE_ENTROPY_CONSTRAINT_WEIGHTED_SCORE_50_V1"
    assert metadata.FEATURE_1 == "ENTROPY"
    assert metadata.FEATURE_2 == "CONSTRAINT"
    assert metadata.WINDOW == 50
    assert metadata.MINIMUM_HISTORY == 751
    assert metadata.NATIVE_TICKET_COUNT == 1
    assert metadata.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
    assert batch.derive_candidate_identity(batch.CANDIDATE_SEMANTICS).SIGNATURE_HASH == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_entropy_parent_has_exact_w50_score_and_tie_parity() -> None:
    history = _history(751)
    statistics = batch.calculate_entropy_statistics(history, 751)
    assert statistics.POOL_NUMBERS == batch.LEGAL_NUMBERS
    assert _independent_entropy(history, 751) == statistics.RAW_SCORES
    ranking = batch.calculate_entropy_ranking(history, 751)
    assert tuple(
        sorted(batch.LEGAL_NUMBERS, key=lambda number: (-statistics.RAW_SCORES[number - 1], number))
    ) == ranking.ORDERED_NUMBERS
    tied = batch.rank_entropy_scores((Fraction(0, 1),) * 49)
    assert tied.ORDERED_NUMBERS == batch.LEGAL_NUMBERS
    assert tied.NORMALIZED_RANKS[0] == Fraction(48, 48)
    assert tied.NORMALIZED_RANKS[-1] == Fraction(0, 48)


def test_constraint_parent_predicate_and_support_are_exact() -> None:
    history = _history(751)
    assert all(
        batch.constraint_predicate(tuple(draw)) == _reference_constraint(tuple(draw))
        for draw in history[-30:]
    )
    assert batch.calculate_constraint_support_scores(history, 751) == (
        constraint_parent.calculate_constraint_support_scores(history, 751)
    )
    assert batch.rank_constraint_support_scores((0,) * 49).ORDERED_NUMBERS == (
        batch.LEGAL_NUMBERS
    )


def test_exact_rank_fusion_uses_both_components_and_final_ties() -> None:
    entropy = tuple(Fraction(48 - index, 48) for index in range(49))
    constraint = tuple(Fraction(index, 48) for index in range(49))
    ranking = batch.rank_pairwise_scores(entropy, constraint)
    assert entropy == ranking.ENTROPY_COMPONENTS
    assert constraint == ranking.CONSTRAINT_COMPONENTS
    assert ranking.PAIRWISE_SCORES[0] == Fraction(1, 2)
    assert ranking.PAIRWISE_SCORES[-1] == Fraction(1, 2)
    assert ranking.RANKED_NUMBERS[0] == 25
    assert ranking.RANKED_NUMBERS[-1] == 49
    assert tuple(sorted(ranking.NATIVE_TICKET)) == ranking.NATIVE_TICKET
    assert batch.constraint_predicate(ranking.NATIVE_TICKET)


def test_pairwise_calculation_calls_and_retains_both_component_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(751)
    entropy = tuple(Fraction(48 - index, 48) for index in range(49))
    constraint = tuple(Fraction(index, 48) for index in range(49))
    calls: list[str] = []

    def fake_entropy(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("entropy")
        return entropy

    def fake_constraint(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("constraint")
        return constraint

    monkeypatch.setattr(batch, "calculate_entropy_components", fake_entropy)
    monkeypatch.setattr(batch, "calculate_constraint_components", fake_constraint)
    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert calls == ["entropy", "constraint"]
    assert entropy == ranking.ENTROPY_COMPONENTS
    assert constraint == ranking.CONSTRAINT_COMPONENTS


def test_causal_cutoff_ignores_target_row_and_future_suffix() -> None:
    history = _history(753)
    changed = list(history)
    changed[751] = (7, 8, 9, 10, 11, 12)
    changed[752] = (37, 38, 39, 40, 41, 42)
    assert batch.produce_candidate_portfolio(history, 751) == (
        batch.produce_candidate_portfolio(tuple(changed), 751)
    )


def test_history_minimum_and_validation_fail_explicitly() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="at least 751 are required"):
        batch.produce_candidate_portfolio(_history(750), 750)
    malformed = list(_history(751))
    malformed[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.produce_candidate_portfolio(tuple(malformed), 751)
    with pytest.raises(ValueError, match="must not exceed"):
        batch.produce_candidate_portfolio(_history(751), 752)


def test_output_shape_search_and_source_isolation() -> None:
    history = _history(751)
    portfolio = batch.produce_candidate_portfolio(history, 751)
    assert len(portfolio) == 1
    assert batch.constraint_predicate(portfolio[0])
    assert batch.produce_candidate(history, 751) == portfolio
    assert batch.produce_source_ticket_universe(history, 751) == portfolio
    with pytest.raises(batch.ConstraintSearchExhaustedError):
        batch.select_first_admissible_ticket(batch.LEGAL_NUMBERS, lambda _ticket: False)

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
