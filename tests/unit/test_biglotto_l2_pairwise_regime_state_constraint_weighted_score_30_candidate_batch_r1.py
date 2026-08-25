"""Focused acceptance tests for the sealed W=30 pairwise candidate."""

from __future__ import annotations

import csv
import hashlib
import json
from fractions import Fraction
from itertools import combinations, pairwise
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as regime_parent,
)

batch = (
    biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1
)

Ticket = tuple[int, int, int, int, int, int]

_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_D9930AEBFBBEE697_R1"
)
_TASK_DATA_ROOT_NAME = (
    "BIGLOTTO_L2_PAIRWISE_REGIME_STATE_CONSTRAINT_WEIGHTED_SCORE_30_CANDIDATE_BATCH_R1"
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
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".task-data" / _AUTHORITY_ROOT_NAME
        if candidate.is_dir():
            return candidate
    pytest.fail("sealed predecessor task-data root is unavailable")


def _authority_file(name: str) -> object:
    return json.loads((_authority_root() / name).read_text(encoding="utf-8"))


def _task_data_root() -> Path:
    direct = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data") / _TASK_DATA_ROOT_NAME
    if direct.is_dir():
        return direct
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".task-data" / _TASK_DATA_ROOT_NAME
        if candidate.is_dir():
            return candidate
    pytest.fail("fresh candidate task-data root is unavailable")


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(
        _VALID_DRAW_TYPES[index % len(_VALID_DRAW_TYPES)]
        if index % 5
        else _INVALID_DRAW
        for index in range(count)
    )


def _reference_constraint(ticket: Ticket) -> bool:
    numbers = tuple(ticket)
    if len(numbers) != 6 or len(set(numbers)) != 6:
        return False
    if any(not 1 <= number <= 49 for number in numbers):
        return False
    if not 2 <= sum(number % 2 == 1 for number in numbers) <= 4:
        return False
    zones = {
        zone
        for number in numbers
        for zone, (low, high) in enumerate(((1, 10), (11, 20), (21, 30), (31, 40), (41, 49)))
        if low <= number <= high
    }
    if len(zones) < 3 or not 120 <= sum(numbers) <= 180:
        return False
    ordered = sorted(numbers)
    runs: list[int] = [1]
    for previous, current in pairwise(ordered):
        runs.append(runs[-1] + 1 if current == previous + 1 else 1)
    if max(runs) > 2:
        return False
    return len({number % 10 for number in numbers}) >= 4


def test_authority_manifest_checksum_identity_and_expected_paths_are_exact() -> None:
    authority_root = _authority_root()
    for line in (authority_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        actual_hash = hashlib.sha256((authority_root / relative_path).read_bytes()).hexdigest()
        assert actual_hash == expected_hash

    handoff = cast(dict[str, object], _authority_file("implementation_handoff.json"))
    semantics = cast(dict[str, object], _authority_file("completed_v1_semantics.json"))
    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert semantics["IMPLEMENTATION_READY"] == "YES"
    assert semantics["IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert handoff["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.IMPLEMENTATION_SYMBOL
    assert handoff["EXPECTED_FOCUSED_TEST_MODULE"] == (
        "tests/unit/test_biglotto_l2_pairwise_regime_state_constraint_weighted_score_30_candidate_batch_r1.py"
    )
    assert handoff["PERFORMANCE_ROOTS_READ"] == 0
    assert handoff["PERFORMANCE_VALUES_ACCESSED"] == "NO"
    assert handoff["EMPIRICAL_VALUES_USED_FOR_PARAMETER_SELECTION"] == "NO"
    assert handoff["REPLAY_EXECUTED"] == "NO"

    signature_object = cast(dict[str, object], handoff["DESIGN_SIGNATURE_OBJECT"])
    assert json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)) == signature_object
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )
    assert hashlib.sha256(
        json.dumps(
            signature_object,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest() == batch.DESIGN_SIGNATURE_SHA256


def test_candidate_identity_is_exactly_one_and_sealed() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_5f0c6fb3405f7f78"
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


def test_fresh_task_data_outputs_are_complete_and_checksum_verified() -> None:
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

    manifest = cast(
        dict[str, object],
        json.loads((root / "candidate_batch_manifest.json").read_text()),
    )
    assert manifest["CANDIDATE_COUNT"] == 1
    assert manifest["CANDIDATE_IDS"] == [batch.CANDIDATE_ID]


def test_regime_state_parent_and_selected_source_parity_are_exact() -> None:
    history = _history(751)
    actual_state = batch.calculate_regime_state(history, 751)
    expected_state = regime_parent.calculate_regime_state(history, 751)
    assert actual_state == expected_state
    assert regime_parent.calculate_collision_concentration(
        history, 751, 50
    ) == actual_state.COLLISION_50
    assert regime_parent.calculate_reference_collision(
        actual_state.COLLISION_300,
        actual_state.COLLISION_750,
    ) == actual_state.REFERENCE_COLLISION
    assert regime_parent.classify_regime(
        actual_state.COLLISION_50,
        actual_state.REFERENCE_COLLISION,
    ) == actual_state.REGIME
    assert regime_parent.classify_regime(Fraction(1, 2), Fraction(1, 2)) == (
        regime_parent.RECENT_DIFFUSE_HIGH_RENYI2
    )

    source = batch.produce_regime_source_ticket_universe(history, 751)
    expected_source = regime_parent.produce_b649_renyi2_regime_switched_ranked_pool_v1(
        history, 751
    )
    assert source == expected_source
    assert len(source) == 210
    expected_support = [0] * 49
    for ticket in expected_source:
        for number in ticket:
            expected_support[number - 1] += 1
    assert batch.calculate_regime_state_support_scores(history, 751) == tuple(expected_support)


@pytest.mark.parametrize(
    ("ticket", "expected"),
    (
        ((_VALID_DRAW_TYPES[0]), True),
        ((2, 12, 23, 34, 44, 46), False),
        ((1, 4, 11, 14, 21, 28), False),
        ((6, 7, 8, 18, 35, 46), False),
        ((1, 12, 21, 32, 41, 42), False),
    ),
)
def test_constraint_parent_predicate_matches_independent_frozen_oracle(
    ticket: Ticket, expected: bool
) -> None:
    assert batch.constraint_predicate(ticket) == expected
    assert batch.constraint_predicate(ticket) == _reference_constraint(ticket)


def test_constraint_support_window_and_valid_draw_semantics_are_exact() -> None:
    history = (_INVALID_DRAW,) * 722 + _VALID_DRAW_TYPES * 7 + (_VALID_DRAW_TYPES[0],)
    assert len(history) == 751
    expected = [0] * 49
    for draw in history[-30:]:
        if _reference_constraint(draw):
            for number in draw:
                expected[number - 1] += 1
    assert batch.calculate_constraint_support_scores(history, 751) == tuple(expected)


def test_minimum_history_target_exclusion_suffix_invariance_and_input_immutability() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="751"):
        batch.calculate_constraint_support_scores(_history(750), 750)
    accepted = batch.calculate_constraint_support_scores(_history(751), 751)
    assert len(accepted) == 49

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


def test_component_normalization_is_exact_and_raw_ties_are_number_ascending() -> None:
    all_tied = batch.rank_component_scores((0,) * 49)
    assert tuple(range(1, 50)) == all_tied.ORDERED_NUMBERS
    assert all_tied.position(1) == 1
    assert all_tied.position(49) == 49
    assert all_tied.normalized_rank(1) == Fraction(48, 48)
    assert all_tied.normalized_rank(49) == Fraction(0, 48)

    one_high = [0] * 49
    one_high[48] = 1
    ranked = batch.rank_component_scores(one_high)
    assert ranked.ORDERED_NUMBERS[:3] == (49, 1, 2)
    assert ranked.normalized_rank(49) == Fraction(48, 48)


def test_exact_weighted_fusion_has_hand_computable_rational_scores() -> None:
    regime = tuple(Fraction(49 - number, 48) for number in range(1, 50))
    constraint = tuple(Fraction(number - 1, 48) for number in range(1, 50))
    ranking = batch.rank_pairwise_scores(regime, constraint)
    assert ranking.PAIRWISE_SCORES[0] == Fraction(1, 2)
    assert ranking.PAIRWISE_SCORES[48] == Fraction(1, 2)
    assert all(score == Fraction(1, 2) for score in ranking.PAIRWISE_SCORES)
    assert (
        batch.FUSION_WEIGHT_1 * regime[0] + batch.FUSION_WEIGHT_2 * constraint[0]
    ) == ranking.score(1).PAIRWISE_SCORE
    assert all(isinstance(score, Fraction) for score in ranking.PAIRWISE_SCORES)


def test_both_components_can_change_fused_order_and_fused_is_not_parent_only() -> None:
    descending = tuple(Fraction(49 - number, 48) for number in range(1, 50))
    ascending = tuple(Fraction(number - 1, 48) for number in range(1, 50))
    zeros = (Fraction(0, 1),) * 49

    regime_changed = list(descending)
    regime_changed[0], regime_changed[1] = regime_changed[1], regime_changed[0]
    baseline_regime = batch.rank_pairwise_scores(descending, zeros)
    changed_regime = batch.rank_pairwise_scores(tuple(regime_changed), zeros)
    assert changed_regime.RANKED_NUMBERS != baseline_regime.RANKED_NUMBERS

    constraint_changed = list(ascending)
    constraint_changed[0], constraint_changed[1] = constraint_changed[1], constraint_changed[0]
    baseline_constraint = batch.rank_pairwise_scores(zeros, ascending)
    changed_constraint = batch.rank_pairwise_scores(zeros, tuple(constraint_changed))
    assert changed_constraint.RANKED_NUMBERS != baseline_constraint.RANKED_NUMBERS

    regime_spike = tuple(Fraction(1 if number == 1 else 0, 1) for number in range(1, 50))
    constraint_spike = tuple(Fraction(1 if number == 49 else 0, 1) for number in range(1, 50))
    fused = batch.rank_pairwise_scores(regime_spike, constraint_spike)
    regime_only = tuple(
        sorted(range(1, 50), key=lambda number: (-regime_spike[number - 1], number))
    )
    constraint_only = tuple(
        sorted(range(1, 50), key=lambda number: (-constraint_spike[number - 1], number))
    )
    assert regime_only != fused.RANKED_NUMBERS
    assert constraint_only != fused.RANKED_NUMBERS


def test_full_pool_candidate_search_ticket_shape_and_lexicographic_selection() -> None:
    history = _history(751)
    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert batch.RANKED_POOL_DOMAIN == "ALL_LEGAL_NUMBERS_1_TO_49"
    assert batch.RANKED_POOL_CARDINALITY == 49
    assert len(ranking.RANKED_NUMBERS) == 49
    assert set(ranking.RANKED_NUMBERS) == set(range(1, 50))
    assert len(ranking.SOURCE_TICKETS) == 210
    assert len(ranking.TICKETS) == 1
    assert tuple(sorted(ranking.NATIVE_TICKET)) == ranking.NATIVE_TICKET
    assert len(set(ranking.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in ranking.NATIVE_TICKET)
    assert batch.constraint_predicate(ranking.NATIVE_TICKET)

    expected = next(
        tuple(sorted(candidate))
        for candidate in combinations(ranking.RANKED_NUMBERS, 6)
        if _reference_constraint(cast(Ticket, candidate))
    )
    assert expected == ranking.NATIVE_TICKET
    assert batch.produce_candidate_portfolio(history, 751) == (ranking.NATIVE_TICKET,)

    with pytest.raises(batch.ConstraintSearchExhaustedError, match="no six-number"):
        batch.select_first_admissible_ticket(tuple(range(1, 50)), lambda _ticket: False)


def test_repeated_execution_is_deterministic_and_module_is_research_only() -> None:
    history = _history(751)
    first = batch.produce_candidate_portfolio(history, 751)
    second = batch.produce_candidate_portfolio(history, 751)
    assert first == second
    assert batch.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None

    module_source = Path(batch.__file__).read_text(encoding="utf-8")
    assert "lottolab.strategies.catalog" not in module_source
    assert "sqlite" not in module_source.lower()
    assert "replay" not in module_source.lower()
