"""Focused tests for the redundancy-pruned cross-family ensemble V1 batch."""

from __future__ import annotations

import ast
import json
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any, Final, cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as cooccurrence,
)
from lottolab.research import (
    biglotto_cross_family_redundancy_pruned_ensemble_v1_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_network,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission,
)

type Ticket = tuple[int, int, int, int, int, int]

FIXTURE: Final[Path] = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "biglotto_retained_family_producers"
    / "parity_v1.json"
)

CANDIDATES: Final[tuple[tuple[str, str, int], ...]] = (
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5",
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
        5,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k10",
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
        10,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k20",
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
        20,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k5",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
        5,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k10",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
        10,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k20",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
        20,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k5",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
        5,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k10",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
        10,
    ),
    (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k20",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
        20,
    ),
)

FAMILY_MODULES: Final[tuple[tuple[str, ModuleType, str], ...]] = (
    ("CONDITIONAL_COOCCURRENCE", cooccurrence, "conditional_cooccurrence"),
    ("GRAPH_NETWORK", graph_network, "graph_network"),
    ("MULTISCALE_OMISSION_PRESSURE", omission, "multiscale_omission_pressure"),
)
CONSTRUCTOR_SLUGS: Final[dict[str, str]] = {
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
}


@cache
def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text()))


def _history() -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(draw) for draw in _payload()["history"])


def _ticket(start: int) -> Ticket:
    return cast(Ticket, tuple(range(start, start + 6)))


def _tickets(start: int, count: int) -> tuple[Ticket, ...]:
    return tuple(_ticket(start + index) for index in range(count))


def _serialize(portfolio: object) -> bytes:
    return json.dumps(portfolio, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _producer(symbol: str) -> Callable[[object, int], tuple[Ticket, ...]]:
    return cast(Callable[[object, int], tuple[Ticket, ...]], getattr(batch, symbol))


def _stub_parent(tickets: tuple[Ticket, ...]) -> Callable[[object, int], tuple[Ticket, ...]]:
    def producer(history: object, target_index: int) -> tuple[Ticket, ...]:
        del history, target_index
        return tickets

    return producer


def _parent_symbol(family_slug: str, constructor_id: str, budget: int) -> str:
    return (
        f"produce_b649_{family_slug}_multiticket_"
        f"{CONSTRUCTOR_SLUGS[constructor_id]}_v1_k{budget}"
    )


def _expected_union(constructor_id: str, budget: int) -> tuple[Ticket, ...]:
    payload = _payload()
    seen: set[Ticket] = set()
    union: list[Ticket] = []
    for family_id, _, _ in FAMILY_MODULES:
        for raw_ticket in payload["expected"][f"{family_id}|{constructor_id}|{budget}"]:
            ticket = cast(Ticket, tuple(raw_ticket))
            if ticket in seen:
                continue
            seen.add(ticket)
            union.append(ticket)
    return tuple(union)


def test_exact_nine_implementation_symbols_exist_and_are_callable() -> None:
    symbols = tuple(symbol for symbol, _, _ in CANDIDATES)
    assert len(symbols) == 9
    assert len(set(symbols)) == 9
    assert symbols == batch.IMPLEMENTATION_SYMBOLS
    assert batch.RETAINED_FAMILY_IDS == (
        "CONDITIONAL_COOCCURRENCE",
        "GRAPH_NETWORK",
        "MULTISCALE_OMISSION_PRESSURE",
    )
    assert batch.PRUNED_FAMILY_ID == "MULTISCALE_FREQUENCY"
    assert tuple(sorted(batch.RETAINED_FAMILY_IDS)) == batch.RETAINED_FAMILY_IDS
    for symbol, _, _ in CANDIDATES:
        producer = getattr(batch, symbol)
        assert callable(producer)


@pytest.mark.parametrize(("symbol", "constructor_id", "budget"), CANDIDATES)
def test_same_input_twice_is_byte_identical(
    symbol: str, constructor_id: str, budget: int
) -> None:
    producer = _producer(symbol)
    history = _history()
    target_index = _payload()["target_index"]
    first = producer(history, target_index)
    second = producer(history, target_index)
    assert _serialize(first) == _serialize(second)
    assert first == _expected_union(constructor_id, budget)
    assert len(first) == len(set(first))
    assert budget <= len(first) <= budget * 3


@pytest.mark.parametrize(("symbol", "constructor_id", "budget"), CANDIDATES)
def test_matched_constructor_budget_selects_all_three_retained_parents(
    monkeypatch: pytest.MonkeyPatch, symbol: str, constructor_id: str, budget: int
) -> None:
    calls: list[tuple[str, str, int, int]] = []

    offsets = {
        "CONDITIONAL_COOCCURRENCE": 1,
        "GRAPH_NETWORK": 8,
        "MULTISCALE_OMISSION_PRESSURE": 20,
    }

    def install(family_id: str, module: ModuleType, family_slug: str) -> None:
        for _other_constructor, other_slug in CONSTRUCTOR_SLUGS.items():
            for other_budget in batch.TICKET_BUDGETS:
                name = (
                    f"produce_b649_{family_slug}_multiticket_"
                    f"{other_slug}_v1_k{other_budget}"
                )
                offset = offsets[family_id]

                def fake(
                    history: object,
                    target_index: int,
                    *,
                    _family: str = family_id,
                    _name: str = name,
                    _budget: int = other_budget,
                    _offset: int = offset,
                ) -> tuple[Ticket, ...]:
                    calls.append((_family, _name, _budget, target_index))
                    assert len(tuple(cast(tuple[object, ...], history))) == target_index
                    return _tickets(_offset, _budget)

                monkeypatch.setattr(module, name, fake)

    for family_id, module, family_slug in FAMILY_MODULES:
        install(family_id, module, family_slug)

    result = _producer(symbol)(((1, 2, 3, 4, 5, 6),) * 8, 8)
    expected_calls = [
        (
            family_id,
            _parent_symbol(family_slug, constructor_id, budget),
            budget,
            8,
        )
        for family_id, _, family_slug in FAMILY_MODULES
    ]
    assert calls == expected_calls
    assert result == batch.union_retained_native_tickets_at_matched_budget(
        {
            "CONDITIONAL_COOCCURRENCE": _tickets(1, budget),
            "GRAPH_NETWORK": _tickets(8, budget),
            "MULTISCALE_OMISSION_PRESSURE": _tickets(20, budget),
        },
        budget,
    )


def test_family_union_order_is_retained_id_ascending_then_native_parent_order() -> None:
    cooccurrence_tickets = _tickets(1, 5)
    graph_tickets = _tickets(10, 5)
    omission_tickets = _tickets(20, 5)
    union = batch.union_retained_native_tickets_at_matched_budget(
        {
            "MULTISCALE_OMISSION_PRESSURE": omission_tickets,
            "GRAPH_NETWORK": graph_tickets,
            "CONDITIONAL_COOCCURRENCE": cooccurrence_tickets,
        },
        5,
    )
    assert union == cooccurrence_tickets + graph_tickets + omission_tickets
    assert union[:5] == cooccurrence_tickets
    assert union[5:10] == graph_tickets
    assert union[10:] == omission_tickets


def test_duplicate_ticket_across_parents_keeps_first_occurrence() -> None:
    shared = _ticket(7)
    cooccurrence_tickets = (_ticket(1), shared, _ticket(13), _ticket(19), _ticket(25))
    graph_tickets = (shared, _ticket(31), _ticket(8), _ticket(9), _ticket(10))
    omission_tickets = (_ticket(31), _ticket(14), shared, _ticket(15), _ticket(16))
    union = batch.union_retained_native_tickets_at_matched_budget(
        {
            "CONDITIONAL_COOCCURRENCE": cooccurrence_tickets,
            "GRAPH_NETWORK": graph_tickets,
            "MULTISCALE_OMISSION_PRESSURE": omission_tickets,
        },
        5,
    )
    assert union.count(shared) == 1
    assert union.index(shared) == 1
    assert union == (
        _ticket(1),
        shared,
        _ticket(13),
        _ticket(19),
        _ticket(25),
        _ticket(31),
        _ticket(8),
        _ticket(9),
        _ticket(10),
        _ticket(14),
        _ticket(15),
        _ticket(16),
    )


def test_pruned_family_is_never_imported_or_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path(batch.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    assert all("multiscale_frequency" not in name for name in imported)
    assert "produce_b649_multiscale_frequency" not in source
    assert batch.PRUNED_FAMILY_ID not in batch.RETAINED_FAMILY_IDS

    result = batch.union_retained_native_tickets_at_matched_budget(
        {
            "CONDITIONAL_COOCCURRENCE": _tickets(1, 5),
            "GRAPH_NETWORK": _tickets(10, 5),
            "MULTISCALE_OMISSION_PRESSURE": _tickets(20, 5),
            "MULTISCALE_FREQUENCY": _tickets(30, 5),
        },
        5,
    )
    assert all(ticket not in result for ticket in _tickets(30, 5))

    offsets = {
        "CONDITIONAL_COOCCURRENCE": 1,
        "GRAPH_NETWORK": 8,
        "MULTISCALE_OMISSION_PRESSURE": 20,
    }
    for family_id, module, family_slug in FAMILY_MODULES:
        monkeypatch.setattr(
            module,
            _parent_symbol(family_slug, "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 5),
            _stub_parent(_tickets(offsets[family_id], 5)),
        )
    _producer(CANDIDATES[0][0])(((1, 2, 3, 4, 5, 6),) * 8, 8)
    assert not any("multiscale_frequency" in name for name in sys.modules)


def test_missing_retained_parent_fails_closed_without_substitution() -> None:
    with pytest.raises(batch.RequiredParentUnavailableError, match="GRAPH_NETWORK"):
        batch.union_retained_native_tickets_at_matched_budget(
            {
                "CONDITIONAL_COOCCURRENCE": _tickets(1, 5),
                "MULTISCALE_OMISSION_PRESSURE": _tickets(20, 5),
                "MULTISCALE_FREQUENCY": _tickets(30, 5),
            },
            5,
        )


def test_wrong_retained_parent_output_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy_history = ((1, 2, 3, 4, 5, 6),) * 8
    monkeypatch.setattr(
        cooccurrence,
        "produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k5",
        _stub_parent(_tickets(1, 5)),
    )
    monkeypatch.setattr(
        graph_network,
        "produce_b649_graph_network_multiticket_low_overlap_v1_k5",
        _stub_parent(_tickets(10, 4)),
    )
    monkeypatch.setattr(
        omission,
        "produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k5",
        _stub_parent(_tickets(20, 5)),
    )
    with pytest.raises(ValueError, match="GRAPH_NETWORK"):
        batch.produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5(
            dummy_history, 8
        )

    monkeypatch.delattr(
        omission,
        "produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k5",
    )
    monkeypatch.setattr(
        graph_network,
        "produce_b649_graph_network_multiticket_low_overlap_v1_k5",
        _stub_parent(_tickets(10, 5)),
    )
    with pytest.raises(batch.RequiredParentUnavailableError, match="MULTISCALE_OMISSION_PRESSURE"):
        batch.produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5(
            dummy_history, 8
        )


def test_minimum_history_is_enforced_by_parent_contract() -> None:
    history = _history()[:750]
    with pytest.raises(cooccurrence.InsufficientHistoryError):
        batch.produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5(
            history, 750
        )


def test_causal_target_boundary_is_enforced_by_parent_contracts() -> None:
    history = _history()
    target_index = _payload()["target_index"]
    producer = batch.produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5
    baseline = producer(history, target_index)
    poisoned = (*history, object(), (1, 2, 3, 4, 5, True))
    assert producer(poisoned, target_index) == baseline
    assert producer(iter(history), target_index) == baseline
    assert baseline == _expected_union("B649_CANDIDATE_SET_LOW_OVERLAP_V1", 5)
