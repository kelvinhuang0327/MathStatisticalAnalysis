"""Causality, bounded weighting, and K2/K3/K5 tests for adaptive stacking."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import ModuleType
from typing import cast

import pytest

from lottolab.research import (
    b649_unequal_weight_stacking_candidate_r1 as stacking,
)
from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as cooccurrence,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_network,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission,
)

type Ticket = tuple[int, int, int, int, int, int]

_PARENTS: tuple[tuple[str, ModuleType, str, int], ...] = (
    (
        "CONDITIONAL_COOCCURRENCE",
        cooccurrence,
        "produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k5",
        1,
    ),
    (
        "GRAPH_NETWORK",
        graph_network,
        "produce_b649_graph_network_multiticket_low_overlap_v1_k5",
        8,
    ),
    (
        "MULTISCALE_OMISSION_PRESSURE",
        omission,
        "produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k5",
        20,
    ),
)


def _ticket(start: int) -> Ticket:
    return cast(Ticket, tuple(range(start, start + 6)))


def _portfolios() -> dict[str, tuple[Ticket, ...]]:
    return {
        family_id: tuple(_ticket(start + offset) for offset in range(5))
        for family_id, _, _, start in _PARENTS
    }


def _signal(
    target_index: int,
    portfolios: Mapping[str, tuple[Ticket, ...]],
    *,
    outcome_numbers: Ticket | None = None,
    special: int = 49,
) -> stacking.FamilyReplaySignal:
    outcome = stacking.ReplayOutcome(
        target_index=target_index,
        main_numbers=_ticket(1) if outcome_numbers is None else outcome_numbers,
        special_number=special,
    )
    return stacking.FamilyReplaySignal(
        target_index=target_index,
        outcome=outcome,
        family_portfolios=portfolios,
    )


def _signals(
    portfolios: Mapping[str, tuple[Ticket, ...]],
) -> tuple[tuple[stacking.FamilyReplaySignal, ...], ...]:
    train = tuple(_signal(index, portfolios) for index in range(80))
    validation = tuple(_signal(index, portfolios) for index in range(80, 120))
    return train, validation


def _install_parents(
    monkeypatch: pytest.MonkeyPatch,
    portfolios: Mapping[str, tuple[Ticket, ...]],
) -> None:
    for family_id, module, producer_name, _ in _PARENTS:
        family_tickets = portfolios[family_id]

        def produce(
            history: Sequence[object],
            target_index: int,
            tickets: tuple[Ticket, ...] = family_tickets,
        ) -> tuple[Ticket, ...]:
            assert len(history) == target_index
            return tickets

        monkeypatch.setattr(module, producer_name, produce)


@pytest.mark.parametrize("ticket_budget", stacking.SUPPORTED_TICKET_BUDGETS)
def test_candidate_uses_bounded_non_equal_weights_for_k2_k3_k5(
    monkeypatch: pytest.MonkeyPatch,
    ticket_budget: int,
) -> None:
    portfolios = _portfolios()
    _install_parents(monkeypatch, portfolios)
    training, validation = _signals(portfolios)
    history = tuple(_ticket(1) for _ in range(872))

    plan = stacking.create_unequal_weight_fusion_plan(
        history,
        871,
        ticket_budget,
        training,
        validation,
    )

    assert len(plan.tickets) == ticket_budget
    assert len(set(plan.tickets)) == ticket_budget
    weights = dict(plan.family_weights)
    assert set(weights) == set(stacking.FAMILY_IDS)
    assert sum(weights.values()) == 1
    assert len(set(weights.values())) > 1
    assert weights["CONDITIONAL_COOCCURRENCE"] == pytest.approx(0.4)
    assert plan.profile_id == "SHARE_40_35_25"
    assert len(plan.ticket_origins) == ticket_budget


def test_target_and_future_history_outcomes_cannot_change_weights_or_tickets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolios = _portfolios()
    _install_parents(monkeypatch, portfolios)
    training, validation = _signals(portfolios)
    history = tuple(_ticket(1) for _ in range(874))
    changed_future = (*history[:871], _ticket(8), _ticket(20), _ticket(30))

    first = stacking.create_unequal_weight_fusion_plan(
        history, 871, 3, training, validation
    )
    second = stacking.create_unequal_weight_fusion_plan(
        changed_future, 871, 3, training, validation
    )

    assert first.tickets == second.tickets
    assert first.family_weights == second.family_weights
    assert first.weight_fit == second.weight_fit


def test_future_training_or_validation_signal_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolios = _portfolios()
    _install_parents(monkeypatch, portfolios)
    training, validation = _signals(portfolios)
    future = _signal(871, portfolios)

    with pytest.raises(ValueError, match="strictly before target_index"):
        stacking.produce_b649_unequal_weight_stacking_candidate_r1(
            tuple(_ticket(1) for _ in range(872)),
            871,
            2,
            training,
            (*validation, future),
        )


def test_training_and_validation_blocks_must_be_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolios = _portfolios()
    _install_parents(monkeypatch, portfolios)
    training, validation = _signals(portfolios)
    overlapping_validation = (training[-1], *validation[1:])

    with pytest.raises(ValueError, match="must not overlap"):
        stacking.produce_b649_unequal_weight_stacking_candidate_r1(
            tuple(_ticket(1) for _ in range(872)),
            871,
            2,
            training,
            overlapping_validation,
        )


def test_official_any_prize_definition_includes_special_number_tier() -> None:
    outcome = stacking.ReplayOutcome(
        target_index=0,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
    )

    assert stacking._signal_success((_ticket(1),), outcome)
    assert stacking._signal_success(((1, 2, 8, 9, 10, 7),), outcome)
    assert not stacking._signal_success(((8, 9, 10, 11, 12, 13),), outcome)


def test_backtest_emits_only_targets_after_causal_train_and_validation_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolios = _portfolios()
    _install_parents(monkeypatch, portfolios)
    outcomes = tuple(
        stacking.ReplayOutcome(index, _ticket(1), 49, f"T{index:04d}")
        for index in range(872)
    )

    records = stacking.walk_forward_backtest(outcomes, 2)

    assert len(records) == 1
    assert records[0].target_index == 871
    assert records[0].draw_number == "T0871"
    assert records[0].fusion_success
    assert records[0].causal_best_single_success
    assert records[0].weight_fit.training_target_range == (751, 830)
    assert records[0].weight_fit.validation_target_range == (831, 870)
