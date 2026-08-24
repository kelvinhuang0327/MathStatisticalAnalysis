"""Focused tests for the sealed HOT_COLD + ENTROPY pairwise candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1 as batch,
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
_AUTHORITY_ROOT_NAME = (
    "BIGLOTTO_L2_PAIRWISE_FRONTIER_ADVANCE_AFTER_E849A4B70DB5D01E_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".task-data" / _AUTHORITY_ROOT_NAME
        if candidate.is_dir():
            return candidate
    pytest.fail("sealed completed_v1_semantics task-data root is unavailable")


def _authority() -> dict[str, object]:
    path = _authority_root() / "completed_v1_semantics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _reference_hot_cold(history: tuple[Ticket, ...]) -> tuple[Fraction, ...]:
    recent = history[-50:]
    counts = Counter(number for draw in recent for number in draw)
    first_seen: dict[int, int] = {}
    observation_index = 0
    for draw in recent:
        for number in draw:
            first_seen.setdefault(number, observation_index)
            observation_index += 1
    hot_pool = sorted(
        (number for number, count in counts.items() if count > 0),
        key=lambda number: (-counts[number], first_seen[number]),
    )[:20]

    pair_counts: Counter[tuple[int, int]] = Counter()
    for draw in history[-100:]:
        for left, right in combinations(draw, 2):
            pair_counts[(left, right)] += 1
            pair_counts[(right, left)] += 1

    raw = [Fraction(0, 1)] * 49
    hot_pool_size = len(hot_pool)
    for index, number in enumerate(hot_pool):
        if hot_pool_size <= 1:
            cooccurrence_mean = Fraction(0, 1)
        else:
            cooccurrence_mean = sum(
                (
                    Fraction(pair_counts[(number, other)], 100)
                    for other in hot_pool
                    if other != number
                ),
                Fraction(0, 1),
            ) / (hot_pool_size - 1)
        raw[number - 1] = Fraction(7, 10) * Fraction(
            hot_pool_size - index, hot_pool_size
        ) + Fraction(3, 10) * cooccurrence_mean
    return tuple(raw)


def _reference_entropy(history: tuple[Ticket, ...]) -> tuple[Fraction, ...]:
    counts = Counter(number for draw in history[-50:] for number in draw)
    expected = Fraction(300, 49)
    return tuple(
        Fraction(1, 1)
        / (abs(Fraction(counts[number], 1) - expected) + Fraction(1, 10))
        for number in range(1, 50)
    )


def _component_fixture(
    hot_cold_number_1: Fraction = Fraction(0, 1),
    hot_cold_number_2: Fraction = Fraction(0, 1),
    entropy_number_1: Fraction = Fraction(0, 1),
    entropy_number_2: Fraction = Fraction(0, 1),
) -> tuple[list[Fraction], list[Fraction]]:
    hot_cold = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    hot_cold[0] = hot_cold_number_1
    hot_cold[1] = hot_cold_number_2
    entropy[0] = entropy_number_1
    entropy[1] = entropy_number_2
    return hot_cold, entropy


def test_frontier_checksum_and_exact_sealed_identity() -> None:
    authority_root = _authority_root()
    authority_path = authority_root / "completed_v1_semantics.json"
    checksum_path = authority_root / "SHA256SUMS"
    assert authority_path.is_file()
    expected_line = next(
        line
        for line in checksum_path.read_text(encoding="utf-8").splitlines()
        if line.endswith("completed_v1_semantics.json")
    )
    assert hashlib.sha256(authority_path.read_bytes()).hexdigest() == expected_line.split()[0]

    authority = _authority()
    assert authority["selected_gap_id"] == batch.SELECTED_GAP_ID
    assert authority["design_id"] == batch.DESIGN_ID
    assert authority["design_signature_sha256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["implementation_ready"] == "YES"
    assert authority["performance_roots_read"] == 0
    assert authority["performance_values_accessed"] == "NO"
    assert authority["replay_executed"] == "NO"

    semantics = authority["canonical_semantic_object"]
    assert isinstance(semantics, dict)
    assert semantics["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert semantics["DESIGN_ID"] == batch.DESIGN_ID
    assert semantics["IMPLEMENTATION_READY"] == "YES"


def test_candidate_count_and_identity_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_METADATA.CANDIDATE_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.DESIGN_ID == batch.DESIGN_ID
    assert (
        batch.CANDIDATE_METADATA.DESIGN_SIGNATURE_SHA256
        == batch.DESIGN_SIGNATURE_SHA256
    )
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    identity = batch.derive_candidate_identity(batch.CANDIDATE_SEMANTICS)
    assert identity.CANDIDATE_ID == batch.CANDIDATE_ID
    assert identity.SIGNATURE_HASH == batch.DESIGN_SIGNATURE_SHA256
    assert not batch.CANDIDATE_ID.endswith(batch.DESIGN_SIGNATURE_SHA256[:16])
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_parent_source_ids_windows_and_rules_are_frozen() -> None:
    authority = _authority()["canonical_semantic_object"]
    assert isinstance(authority, dict)
    assert authority["FEATURE_1"] == batch.FEATURE_1 == "HOT_COLD"
    assert authority["FEATURE_2"] == batch.FEATURE_2 == "ENTROPY"
    assert authority["WINDOW"] == batch.WINDOW == 50
    assert authority["MINIMUM_HISTORY"] == batch.MINIMUM_HISTORY == 100
    assert authority["PARENT_SOURCE_UNIVERSE_ID_1"] == batch.PARENT_SOURCE_UNIVERSE_ID_1
    assert authority["PARENT_SOURCE_UNIVERSE_ID_2"] == batch.PARENT_SOURCE_UNIVERSE_ID_2
    assert authority["PARENT_WINDOW_RULE_1"] == batch.PARENT_WINDOW_RULE_1
    assert authority["PARENT_WINDOW_RULE_2"] == batch.PARENT_WINDOW_RULE_2
    assert authority["HOT_COLD_SCORE_RULE"] == batch.HOT_COLD_SCORE_RULE
    assert authority["ENTROPY_SCORE_RULE"] == batch.ENTROPY_SCORE_RULE


def test_hot_cold_parent_component_matches_independent_sealed_reference() -> None:
    history = _history(100)
    raw = batch.calculate_hot_cold_raw_scores(history, 100)
    assert raw == _reference_hot_cold(history)
    assert all(isinstance(value, Fraction) for value in raw)
    assert all(Fraction(0, 1) <= value <= Fraction(1, 1) for value in raw)


def test_entropy_parent_component_matches_independent_sealed_reference() -> None:
    history = _history(100)
    raw = batch.calculate_entropy_raw_scores(history, 100)
    assert raw == _reference_entropy(history)
    assert all(isinstance(value, Fraction) for value in raw)
    assert all(value > 0 for value in raw)


def test_both_parent_windows_use_exact_w50_history() -> None:
    history = list(_history(100))
    baseline_entropy = batch.calculate_entropy_raw_scores(history, 100)
    history[0] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_entropy_raw_scores(history, 100) == baseline_entropy

    history = list(_history(100))
    baseline_hot_cold = batch.calculate_hot_cold_raw_scores(history, 100)
    history[50] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_hot_cold_raw_scores(history, 100) != baseline_hot_cold


def test_minimum_history_rejects_one_below_and_accepts_exact_boundary() -> None:
    with pytest.raises(batch.InsufficientHistoryError):
        batch.calculate_pairwise_ranking(_history(99), 99)
    accepted = batch.calculate_pairwise_ranking(_history(100), 100)
    assert len(accepted.RANKED_NUMBERS) == 49


def test_causality_excludes_target_and_future_suffix() -> None:
    prefix = _history(100)
    expected = batch.produce_candidate_portfolio(prefix, 100)
    with_target_and_future = (*prefix, (9, 10, 11, 12, 13, 14), object())
    assert batch.produce_candidate_portfolio(with_target_and_future, 100) == expected


def test_generator_history_and_caller_history_are_safe() -> None:
    history = list(_history(100))
    snapshot = history.copy()
    assert batch.produce_candidate_portfolio(iter(history), 100)
    batch.calculate_pairwise_ranking(history, 100)
    assert history == snapshot


def test_malformed_history_is_rejected_without_suffix_validation() -> None:
    malformed = list(_history(100))
    malformed[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="unique"):
        batch.calculate_pairwise_ranking(malformed, 100)

    prefix = _history(100)
    assert batch.produce_candidate_portfolio((*prefix, (1, 1, 1)), 100)


def test_component_rank_normalization_is_exact_and_tie_deterministic() -> None:
    raw = [Fraction(0, 1)] * 49
    raw[0] = Fraction(1, 1)
    raw[1] = Fraction(1, 1)
    ranking = batch.rank_hot_cold_scores(raw)
    assert ranking.ORDERED_NUMBERS[:2] == (1, 2)
    assert ranking.position(1) == 1
    assert ranking.position(2) == 2
    assert ranking.normalized_rank(1) == Fraction(48, 48)
    assert ranking.normalized_rank(2) == Fraction(47, 48)
    assert ranking.normalized_rank(49) == Fraction(0, 1)
    assert all(isinstance(value, Fraction) for value in ranking.NORMALIZED_RANKS)


def test_float_values_are_rejected_from_ranking_arithmetic() -> None:
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pairwise_scores(
            [0.1] + [Fraction(0, 1)] * 48,
            [Fraction(0, 1)] * 49,
        )


def test_fusion_weights_and_hand_computable_fixture_are_exact() -> None:
    hot_cold, entropy = _component_fixture(
        hot_cold_number_1=Fraction(3, 4),
        hot_cold_number_2=Fraction(1, 2),
        entropy_number_1=Fraction(0, 1),
        entropy_number_2=Fraction(1, 1),
    )
    ranking = batch.rank_pairwise_scores(hot_cold, entropy)
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert "EXACT_RATIONAL" in batch.FUSION_FORMULA


def test_final_tie_break_uses_minimum_then_parent_ranks_then_number() -> None:
    hot_cold = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    hot_cold[0], entropy[0] = Fraction(1, 1), Fraction(0, 1)
    hot_cold[1], entropy[1] = Fraction(3, 4), Fraction(1, 4)
    hot_cold[2], entropy[2] = Fraction(1, 4), Fraction(3, 4)
    ranking = batch.rank_pairwise_scores(hot_cold, entropy)
    assert ranking.pairwise_score(1) == ranking.pairwise_score(2)
    assert ranking.RANKED_NUMBERS[:3] == (2, 3, 1)


def test_changing_only_either_parent_can_change_fused_ordering() -> None:
    zeros = [Fraction(0, 1)] * 49
    hot_cold_changed = zeros.copy()
    hot_cold_changed[4] = Fraction(1, 1)
    entropy_changed = zeros.copy()
    entropy_changed[6] = Fraction(1, 1)
    baseline = batch.rank_pairwise_scores(zeros, zeros)
    assert batch.rank_pairwise_scores(hot_cold_changed, zeros).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, entropy_changed).RANKED_NUMBERS[0] == 7
    assert baseline.RANKED_NUMBERS[0] == 1


def test_pairwise_ranking_is_not_equivalent_to_either_single_parent() -> None:
    hot_cold = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    hot_cold[0] = Fraction(1, 1)
    hot_cold[2] = Fraction(3, 4)
    entropy[1] = Fraction(1, 1)
    entropy[2] = Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(hot_cold, entropy)
    hot_cold_only = batch.rank_pairwise_scores(hot_cold, [Fraction(0, 1)] * 49)
    entropy_only = batch.rank_pairwise_scores([Fraction(0, 1)] * 49, entropy)
    assert pairwise.RANKED_NUMBERS != hot_cold_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != entropy_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_callables_feed_the_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(100)
    hot_cold, entropy = _component_fixture(
        hot_cold_number_1=Fraction(1, 1), entropy_number_2=Fraction(1, 1)
    )
    calls: list[str] = []

    def fake_hot_cold(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("hot_cold")
        return tuple(hot_cold)

    def fake_entropy(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("entropy")
        return tuple(entropy)

    monkeypatch.setattr(batch, "calculate_hot_cold_components", fake_hot_cold)
    monkeypatch.setattr(batch, "calculate_entropy_components", fake_entropy)
    ranking = batch.calculate_pairwise_ranking(history, 100)
    assert calls == ["hot_cold", "entropy"]
    assert ranking.hot_cold_component(1) == Fraction(1, 1)
    assert ranking.entropy_component(2) == Fraction(1, 1)
    assert ranking.RANKED_NUMBERS[:2] == (1, 2)


def test_ranked_pool_and_ticket_shape_are_exact() -> None:
    hot_cold, entropy = _component_fixture(
        hot_cold_number_1=Fraction(1, 1),
        hot_cold_number_2=Fraction(3, 4),
    )
    entropy[2] = Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(hot_cold, entropy)
    assert len(ranking.RANKED_NUMBERS) == 49
    assert set(ranking.RANKED_NUMBERS) == set(range(1, 50))
    assert batch.RANKED_POOL_CARDINALITY == 49
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert len(ranking.NATIVE_TICKET) == 6
    assert len(set(ranking.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in ranking.NATIVE_TICKET)
    assert ranking.TICKETS == (ranking.NATIVE_TICKET,)
    assert batch.NATIVE_TICKET_COUNT == 1


def test_candidate_output_is_deterministic_and_one_native_ticket() -> None:
    history = _history(100)
    first = batch.produce_candidate_portfolio(history, 100)
    second = batch.produce_candidate_portfolio(history, 100)
    assert first == second
    assert len(first) == 1
    assert len(first[0]) == 6
    assert first[0] == tuple(sorted(first[0]))
    assert all(type(number) is int and 1 <= number <= 49 for number in first[0])


def test_public_metadata_freezes_required_semantics() -> None:
    contract = batch.SOURCE_UNIVERSE_CONTRACT
    assert contract["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert contract["DESIGN_ID"] == batch.DESIGN_ID
    assert contract["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert contract["FEATURE_1"] == "HOT_COLD"
    assert contract["FEATURE_2"] == "ENTROPY"
    assert contract["PARENT_SOURCE_UNIVERSE_ID_1"] == batch.PARENT_SOURCE_UNIVERSE_ID_1
    assert contract["PARENT_SOURCE_UNIVERSE_ID_2"] == batch.PARENT_SOURCE_UNIVERSE_ID_2
    assert contract["WINDOW"] == 50
    assert contract["MINIMUM_HISTORY"] == 100
    assert contract["RANKED_POOL_CARDINALITY"] == 49
    assert contract["NATIVE_TICKET_COUNT"] == 1
    assert contract["COMPONENT_NORMALIZATION_RULE"] == tuple(
        batch.COMPONENT_NORMALIZATION_RULE_LINES
    )
    assert contract["NUMBER_RANKING_RULE"] == tuple(batch.NUMBER_RANKING_RULE_LINES)
    assert contract["NUMBER_TIE_BREAK_RULE"] == tuple(batch.NUMBER_TIE_BREAK_RULE_LINES)
    assert getattr(batch, batch.IMPLEMENTATION_SYMBOL) is batch.produce_candidate_portfolio


def test_research_module_has_no_external_runtime_or_random_imports() -> None:
    source_path = Path(batch.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    forbidden_roots = {
        "sqlite3",
        "socket",
        "subprocess",
        "time",
        "urllib",
        "requests",
        "random",
    }
    assert not {
        module.split(".", 1)[0]
        for module in imported_modules
        if module.split(".", 1)[0] in forbidden_roots
    }
