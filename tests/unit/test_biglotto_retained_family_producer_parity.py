"""Parity tests for the three retained cross-family producers landed on main.

These modules were previously reachable only from sibling task worktrees, which made
every downstream frozen hypothesis point at ephemeral code. They are landed here byte
for byte; provenance of the source blobs is recorded in the landing task report.

The golden fixture is repo-owned and self-contained: it embeds the 751-draw causal
history slice ending at draw 115000073 together with the expected portfolio for all 27
parent configurations (3 retained families x 3 constructors x budgets 5/10/20). Nothing
here reads a worktree, the canonical CSV, or a database, so the sibling-worktree
dependency is fully cut.

A failure means the landed producers no longer reproduce the behaviour that the
redundancy/complementarity matrix actually measured, which would silently invalidate
the frozen pruning decision that dropped MULTISCALE_FREQUENCY.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as cooccurrence,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_network,
)
from lottolab.research import biglotto_multi_ticket_constructors_r1 as constructors
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission,
)

FIXTURE: Final[Path] = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "biglotto_retained_family_producers"
    / "parity_v1.json"
)

FAMILY_SLUGS: Final[dict[str, tuple[Any, str]]] = {
    "CONDITIONAL_COOCCURRENCE": (cooccurrence, "conditional_cooccurrence"),
    "GRAPH_NETWORK": (graph_network, "graph_network"),
    "MULTISCALE_OMISSION_PRESSURE": (omission, "multiscale_omission_pressure"),
}
CONSTRUCTOR_SLUGS: Final[dict[str, str]] = {
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
}
BUDGETS: Final[tuple[int, int, int]] = (5, 10, 20)
PRUNED_FAMILY: Final[str] = "MULTISCALE_FREQUENCY"


def _load() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def _history(payload: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(draw) for draw in payload["history"])


def _producer(family: str, constructor_id: str, budget: int) -> Any:
    module, family_slug = FAMILY_SLUGS[family]
    constructor_slug = CONSTRUCTOR_SLUGS[constructor_id]
    name = f"produce_b649_{family_slug}_multiticket_{constructor_slug}_v1_k{budget}"
    return getattr(module, name)


CONFIGURATIONS: Final[list[tuple[str, str, int]]] = [
    (family, constructor_id, budget)
    for family in FAMILY_SLUGS
    for constructor_id in CONSTRUCTOR_SLUGS
    for budget in BUDGETS
]


def test_fixture_covers_every_parent_configuration() -> None:
    payload = _load()
    assert len(CONFIGURATIONS) == 27
    assert set(payload["expected"]) == {
        f"{family}|{constructor_id}|{budget}"
        for family, constructor_id, budget in CONFIGURATIONS
    }


def test_fixture_is_self_contained() -> None:
    raw = FIXTURE.read_text()
    for leaked in ("/Users/", ".worktrees", ".task-data"):
        assert leaked not in raw, f"fixture leaks an external path: {leaked}"
    payload = _load()
    assert len(payload["history"]) == payload["minimum_history"] == 751
    assert payload["target_index"] == 751
    assert payload["data_cutoff"] == 115000073


@pytest.mark.parametrize(("family", "constructor_id", "budget"), CONFIGURATIONS)
def test_producer_matches_frozen_golden(family: str, constructor_id: str, budget: int) -> None:
    payload = _load()
    history = _history(payload)
    golden = payload["expected"][f"{family}|{constructor_id}|{budget}"]
    expected = [tuple(ticket) for ticket in golden]
    produced = _producer(family, constructor_id, budget)(history, payload["target_index"])
    assert list(produced) == expected


@pytest.mark.parametrize(("family", "constructor_id", "budget"), CONFIGURATIONS)
def test_producer_is_deterministic(family: str, constructor_id: str, budget: int) -> None:
    payload = _load()
    history = _history(payload)
    producer = _producer(family, constructor_id, budget)
    first = producer(history, payload["target_index"])
    second = producer(history, payload["target_index"])
    assert first == second


@pytest.mark.parametrize(("family", "constructor_id", "budget"), CONFIGURATIONS)
def test_budget_controls_ticket_count(family: str, constructor_id: str, budget: int) -> None:
    payload = _load()
    produced = _producer(family, constructor_id, budget)(_history(payload), payload["target_index"])
    assert len(produced) == budget


@pytest.mark.parametrize(("family", "constructor_id", "budget"), CONFIGURATIONS)
def test_tickets_are_legal_and_ordered(family: str, constructor_id: str, budget: int) -> None:
    payload = _load()
    produced = _producer(family, constructor_id, budget)(_history(payload), payload["target_index"])
    for ticket in produced:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert list(ticket) == sorted(ticket)
        assert all(1 <= number <= 49 for number in ticket)
    assert len(set(produced)) == len(produced)


def test_history_is_causal_only() -> None:
    """Truncating history below the target index must change nothing downstream of it."""
    payload = _load()
    history = _history(payload)
    producer = _producer("GRAPH_NETWORK", "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 5)
    baseline = producer(history, payload["target_index"])
    extended = producer((*history, (1, 2, 3, 4, 5, 6)), payload["target_index"])
    assert baseline == extended


def test_all_three_constructors_are_registered() -> None:
    assert set(CONSTRUCTOR_SLUGS) <= set(constructors.CONSTRUCTORS)
    assert constructors.SUPPORTED_TICKET_COUNTS == BUDGETS


def test_pruned_family_is_not_required() -> None:
    """The frozen authority drops MULTISCALE_FREQUENCY; nothing landed may depend on it."""
    for module, _ in FAMILY_SLUGS.values():
        source = Path(module.__file__).read_text()
        assert PRUNED_FAMILY.lower() not in source.lower()


@pytest.mark.parametrize("constructor_id", sorted(CONSTRUCTOR_SLUGS))
@pytest.mark.parametrize("unsupported_budget", [0, 1, 4, 6, 7, 15, 21, 100, -5])
def test_constructors_reject_unsupported_budgets(
    constructor_id: str, unsupported_budget: int
) -> None:
    """Budgets outside the frozen 5/10/20 set must fail closed, never silently degrade."""
    payload = _load()
    pool = _producer("GRAPH_NETWORK", constructor_id, 20)(
        _history(payload), payload["target_index"]
    )
    with pytest.raises(ValueError):
        constructors.CONSTRUCTORS[constructor_id](pool, unsupported_budget)


@pytest.mark.parametrize("constructor_id", sorted(CONSTRUCTOR_SLUGS))
def test_constructors_reject_bool_disguised_as_budget(constructor_id: str) -> None:
    """bool is an int subclass; the frozen budget guard must still reject it."""
    payload = _load()
    pool = _producer("GRAPH_NETWORK", constructor_id, 20)(
        _history(payload), payload["target_index"]
    )
    with pytest.raises(ValueError):
        constructors.CONSTRUCTORS[constructor_id](pool, True)
