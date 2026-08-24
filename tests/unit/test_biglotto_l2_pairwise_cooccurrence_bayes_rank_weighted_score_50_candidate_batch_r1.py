"""Focused tests for the frozen BigLotto Level-2 pairwise candidate."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as cooccurrence_parent,
)
from lottolab.research import (
    biglotto_l2_pairwise_cooccurrence_bayes_rank_weighted_score_50_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as bayes_parent,
)

Ticket = tuple[int, int, int, int, int, int]

_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 13, 14, 15, 16),
    (2, 8, 17, 18, 19, 20),
    (30, 31, 32, 33, 34, 35),
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    root_name = (
        "BIGLOTTO_L2_PAIRWISE_FRONTIER_RECONSTRUCTION_AND_NEXT_DESIGN_FREEZE_R2"
    )
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".task-data" / root_name
        if candidate.is_dir():
            return candidate
    pytest.fail("completed design-authority task-data root is unavailable")


def _component_fixture(
    cooccurrence_number_1: Fraction = Fraction(0, 1),
    cooccurrence_number_2: Fraction = Fraction(0, 1),
    bayes_number_1: Fraction = Fraction(0, 1),
    bayes_number_2: Fraction = Fraction(0, 1),
) -> tuple[list[Fraction], list[Fraction]]:
    cooccurrence = [Fraction(0, 1)] * 49
    bayes = [Fraction(0, 1)] * 49
    cooccurrence[0] = cooccurrence_number_1
    cooccurrence[1] = cooccurrence_number_2
    bayes[0] = bayes_number_1
    bayes[1] = bayes_number_2
    return cooccurrence, bayes


def test_reconstruction_authority_checksum_and_exact_identity() -> None:
    authority_root = _authority_root()
    authority_path = authority_root / "completed_v1_semantics.json"
    checksum_path = authority_root / "SHA256SUMS"
    assert authority_path.is_file()
    expected_line = next(
        line
        for line in checksum_path.read_text(encoding="utf-8").splitlines()
        if line.endswith("completed_v1_semantics.json")
    )
    expected_hash = expected_line.split(maxsplit=1)[0]
    assert hashlib.sha256(authority_path.read_bytes()).hexdigest() == expected_hash

    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"
    assert authority["SEMANTIC_AUTHORITY"]["WINDOW"] == 50
    assert authority["SEMANTIC_AUTHORITY"]["MINIMUM_HISTORY"] == 751


def test_candidate_authority_is_exactly_one_and_identity_layers_are_preserved() -> None:
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


def test_parent_source_ids_and_w50_rules_are_frozen() -> None:
    assert (
        batch.PARENT_SOURCE_UNIVERSE_ID_1
        == cooccurrence_parent.SOURCE_UNIVERSE_ID
    )
    assert batch.PARENT_SOURCE_UNIVERSE_ID_2 == bayes_parent.SOURCE_UNIVERSE_ID
    assert batch.PARENT_SOURCE_UNIVERSE_VERSION_1 == "v1"
    assert batch.PARENT_SOURCE_UNIVERSE_VERSION_2 == "v1"
    assert batch.WINDOW == 50
    assert "history[T-51:T-1]" in batch.PARENT_WINDOW_RULE_1
    assert "history[T-50:T]" in batch.PARENT_WINDOW_RULE_2
    assert "TARGET_ROW=history[T] EXCLUDED" in batch.PARENT_WINDOW_RULE_2


def test_conditional_cooccurrence_parent_component_parity_is_exact() -> None:
    history = _history(756)
    candidate_components = batch.calculate_cooccurrence_components(history, 756)
    parent_ranking = cooccurrence_parent.rank_numbers_by_window(history, 756, 50)
    assert candidate_components == parent_ranking.NORMALIZED_RANKS
    assert all(isinstance(value, Fraction) for value in candidate_components)
    assert parent_ranking.WINDOW == 50
    assert parent_ranking.ESTIMATION_DRAW_COUNT == 50
    assert history[755] == parent_ranking.ANCHOR_DRAW


def test_bayesian_parent_component_parity_is_exact() -> None:
    history = _history(756)
    candidate_components = batch.calculate_bayes_components(history, 756)
    parent_ranking = bayes_parent.rank_numbers_by_window(history, 756, 50)
    assert candidate_components == parent_ranking.NORMALIZED_RANKS
    assert all(isinstance(value, Fraction) for value in candidate_components)
    assert parent_ranking.WINDOW == 50
    assert parent_ranking.WINDOW_DRAW_COUNT == 50
    assert parent_ranking.OLDER_DRAW_COUNT == 25
    assert parent_ranking.RECENT_DRAW_COUNT == 25


def test_minimum_history_rejects_750_and_accepts_exact_751_prior_draws() -> None:
    with pytest.raises(batch.InsufficientHistoryError):
        batch.calculate_pairwise_ranking(_history(750), 750)

    accepted = batch.calculate_pairwise_ranking(_history(751), 751)
    assert len(accepted.RANKED_NUMBERS) == 49


def test_causality_excludes_target_and_future_suffix() -> None:
    prefix = _history(751)
    expected = batch.produce_candidate_portfolio(prefix, 751)
    with_target_and_future = (*prefix, (43, 44, 45, 46, 47, 48), object())
    assert (
        batch.produce_candidate_portfolio(with_target_and_future, 751)
        == expected
    )


def test_generator_history_and_caller_history_are_safe() -> None:
    history = list(_history(751))
    snapshot = history.copy()
    assert batch.produce_candidate_portfolio(iter(history), 751)
    batch.calculate_pairwise_ranking(history, 751)
    assert history == snapshot


def test_malformed_prior_history_is_rejected() -> None:
    malformed = list(_history(751))
    malformed[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="unique"):
        batch.calculate_pairwise_ranking(malformed, 751)


def test_rank_normalization_is_exact_one_based_and_hand_computable() -> None:
    history = _history(756)
    cooccurrence = batch.calculate_cooccurrence_components(history, 756)
    bayes = batch.calculate_bayes_components(history, 756)
    cooccurrence_parent_ranking = cooccurrence_parent.rank_numbers_by_window(
        history, 756, 50
    )
    bayes_parent_ranking = bayes_parent.rank_numbers_by_window(history, 756, 50)
    for number in range(1, 50):
        assert cooccurrence[number - 1] == Fraction(
            49 - cooccurrence_parent_ranking.position(number), 48
        )
        assert bayes[number - 1] == Fraction(
            49 - bayes_parent_ranking.position(number), 48
        )

    fixture_cooccurrence = [Fraction(0, 1)] * 49
    fixture_bayes = [Fraction(0, 1)] * 49
    fixture_cooccurrence[0] = Fraction(48, 48)
    fixture_cooccurrence[1] = Fraction(47, 48)
    fixture_bayes[1] = Fraction(48, 48)
    ranking = batch.rank_pairwise_scores(fixture_cooccurrence, fixture_bayes)
    assert ranking.pairwise_score(1) == Fraction(1, 2)
    assert ranking.pairwise_score(2) == Fraction(95, 96)
    assert ranking.RANKED_NUMBERS[0] == 2


def test_fusion_weights_are_exact_one_half_plus_one_half() -> None:
    cooccurrence, bayes = _component_fixture(
        cooccurrence_number_1=Fraction(3, 4),
        cooccurrence_number_2=Fraction(1, 2),
        bayes_number_1=Fraction(0, 1),
        bayes_number_2=Fraction(1, 1),
    )
    ranking = batch.rank_pairwise_scores(cooccurrence, bayes)
    assert batch.COMPONENT_NORMALIZATION_CLASS == "EXACT_RATIONAL_RANK_NORMALIZATION"
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert "EXACT_RATIONAL" in batch.FUSION_FORMULA


def test_exact_ties_use_ascending_number_without_parent_preference() -> None:
    zeros = [Fraction(0, 1)] * 49
    ranking = batch.rank_pairwise_scores(zeros, zeros)
    assert tuple(range(1, 50)) == ranking.RANKED_NUMBERS
    assert tuple(range(1, 50)) == ranking.POSITIONS


def test_float_components_are_rejected_instead_of_used_for_ranking() -> None:
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pairwise_scores(
            [0.1] + [Fraction(0, 1)] * 48,
            [Fraction(0, 1)] * 49,
        )


def test_changing_only_either_parent_can_change_fused_ordering() -> None:
    zeros = [Fraction(0, 1)] * 49
    cooccurrence_changed = zeros.copy()
    cooccurrence_changed[4] = Fraction(1, 1)
    bayes_changed = zeros.copy()
    bayes_changed[6] = Fraction(1, 1)
    baseline = batch.rank_pairwise_scores(zeros, zeros)
    assert (
        batch.rank_pairwise_scores(cooccurrence_changed, zeros).RANKED_NUMBERS[0]
        == 5
    )
    assert (
        batch.rank_pairwise_scores(zeros, bayes_changed).RANKED_NUMBERS[0]
        == 7
    )
    assert baseline.RANKED_NUMBERS[0] == 1


def test_pairwise_ranking_is_not_equivalent_to_either_single_parent() -> None:
    cooccurrence = [Fraction(0, 1)] * 49
    bayes = [Fraction(0, 1)] * 49
    cooccurrence[0] = Fraction(1, 1)
    cooccurrence[2] = Fraction(3, 4)
    bayes[1] = Fraction(1, 1)
    bayes[2] = Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(cooccurrence, bayes)
    cooccurrence_only = batch.rank_pairwise_scores(
        cooccurrence, [Fraction(0, 1)] * 49
    )
    bayes_only = batch.rank_pairwise_scores(
        [Fraction(0, 1)] * 49, bayes
    )
    assert pairwise.RANKED_NUMBERS != cooccurrence_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != bayes_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_callables_feed_the_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(751)
    cooccurrence, bayes = _component_fixture(
        cooccurrence_number_1=Fraction(1, 1),
        bayes_number_2=Fraction(1, 1),
    )

    def fake_cooccurrence(
        _history: object, _target_index: int
    ) -> tuple[Fraction, ...]:
        return tuple(cooccurrence)

    def fake_bayes(
        _history: object, _target_index: int
    ) -> tuple[Fraction, ...]:
        return tuple(bayes)

    monkeypatch.setattr(batch, "calculate_cooccurrence_components", fake_cooccurrence)
    monkeypatch.setattr(batch, "calculate_bayes_components", fake_bayes)
    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert ranking.cooccurrence_component(1) == Fraction(1, 1)
    assert ranking.bayes_component(2) == Fraction(1, 1)
    assert ranking.RANKED_NUMBERS[:2] == (1, 2)


def test_ranked_pool_and_ticket_shape_are_exact() -> None:
    cooccurrence, bayes = _component_fixture(
        cooccurrence_number_1=Fraction(1, 1),
        cooccurrence_number_2=Fraction(3, 4),
    )
    bayes[2] = Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(cooccurrence, bayes)
    assert len(ranking.RANKED_NUMBERS) == 49
    assert set(ranking.RANKED_NUMBERS) == set(range(1, 50))
    assert batch.RANKED_POOL_CARDINALITY == 49
    assert batch.TICKET_SELECTION_RULE.startswith("TAKE_RANKED_POSITIONS_1_TO_6")
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert len(ranking.NATIVE_TICKET) == 6
    assert len(set(ranking.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in ranking.NATIVE_TICKET)
    assert ranking.TICKETS == (ranking.NATIVE_TICKET,)
    assert batch.NATIVE_TICKET_COUNT == 1


def test_candidate_output_is_deterministic_and_one_native_ticket() -> None:
    history = _history(751)
    first = batch.produce_candidate_portfolio(history, 751)
    second = batch.produce_candidate_portfolio(history, 751)
    assert first == second
    assert len(first) == 1
    assert len(first[0]) == 6
    assert first[0] == tuple(sorted(first[0]))
    assert all(isinstance(number, int) and 1 <= number <= 49 for number in first[0])


def test_public_metadata_freezes_required_semantics() -> None:
    contract = batch.SOURCE_UNIVERSE_CONTRACT
    assert contract["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert contract["DESIGN_ID"] == batch.DESIGN_ID
    assert contract["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert contract["FEATURE_1"] == "COOCCURRENCE"
    assert contract["FEATURE_2"] == "BAYESIAN_PROBABILISTIC"
    assert contract["PARENT_SOURCE_UNIVERSE_ID_1"] == batch.PARENT_SOURCE_UNIVERSE_ID_1
    assert contract["PARENT_SOURCE_UNIVERSE_ID_2"] == batch.PARENT_SOURCE_UNIVERSE_ID_2
    assert contract["WINDOW"] == 50
    assert contract["MINIMUM_HISTORY"] == 751
    assert contract["RANKED_POOL_CARDINALITY"] == 49
    assert contract["NATIVE_TICKET_COUNT"] == 1
    assert batch.IMPLEMENTATION_MODULE.endswith("candidate_batch_r1")
    assert getattr(batch, batch.IMPLEMENTATION_SYMBOL) is batch.produce_candidate_portfolio
