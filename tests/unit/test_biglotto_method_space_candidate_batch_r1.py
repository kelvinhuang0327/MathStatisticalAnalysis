from __future__ import annotations

import builtins
import socket
import sqlite3
from typing import NoReturn

import pytest

from lottolab.research.biglotto_method_space_candidate_batch_r1 import (
    CANDIDATE_SPECS,
    SELECTED_CANDIDATE_IDS,
    candidate_spec,
    produce_candidate,
)
from lottolab.strategies.adapters.base import CausalDrawRow, InsufficientHistory
from lottolab.strategies.catalog import production_catalog


def _history(count: int, *, offset: int = 0) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(offset + index + 1),
            date=f"2026-01-{(index % 28) + 1:02d}",
            numbers=tuple(range(1 + (index % 6), 7 + (index % 6))),
        )
        for index in range(count)
    )


def _distinct_history(count: int) -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for index in range(count):
        base = (index * 7) % 20 + 1
        numbers = tuple(sorted({base, base + 1, base + 3, base + 8, base + 15, base + 24}))
        rows.append(
            CausalDrawRow(
                draw=str(index + 1),
                date=f"2026-02-{(index % 28) + 1:02d}",
                numbers=numbers,
            )
        )
    return tuple(rows)


def test_frozen_identity_and_signature_hashes_match_authority() -> None:
    expected = {
        "BMSGV1_L1_WINDOW_0020015a3ded8fa2": (
            "0020015a3ded8fa2fc63abd6a2475d2630b83457c0f392880dbf34d6ffbfc422",
            30,
        ),
        "BMSGV1_L1_WINDOW_0cd43605af011f7f": (
            "0cd43605af011f7fdd6b96bf3b9fdfa5fe0512e22094fd651770e647d8e94633",
            20,
        ),
        "BMSGV1_L1_WINDOW_657395aa27e25467": (
            "657395aa27e25467e18a0475a96bf12a881fa55068906d6bb447b623778930ed",
            750,
        ),
    }
    assert tuple(expected) == SELECTED_CANDIDATE_IDS
    assert len(CANDIDATE_SPECS) == 3
    for candidate_id, (signature_hash, window) in expected.items():
        spec = candidate_spec(candidate_id)
        assert spec.signature_hash == signature_hash
        assert spec.window == window
        assert spec.hypothesis_version == "BIGLOTTO_MSG_V1_R1"
        assert spec.method_space_grammar_version == "BIGLOTTO_MSG_V1"
        assert spec.method_family == "METHOD_SPACE_GAP_CANDIDATE"


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATE_IDS)
def test_minimum_history_boundary(candidate_id: str) -> None:
    with pytest.raises(InsufficientHistory, match="needs 50 causal draws"):
        produce_candidate(candidate_id, _history(49))
    assert len(produce_candidate(candidate_id, _history(50))) == 6


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATE_IDS)
def test_ordinary_history_is_legal_and_has_exact_native_ticket_count(candidate_id: str) -> None:
    ticket = produce_candidate(candidate_id, _distinct_history(90))
    spec = candidate_spec(candidate_id)
    assert spec.native_ticket_count == 1
    assert spec.output_shape == "SINGLE_TICKET"
    assert len(ticket) == 6
    assert len(set(ticket)) == 6
    assert all(1 <= number <= 49 for number in ticket)


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATE_IDS)
def test_repeated_invocation_and_ticket_order_are_deterministic(candidate_id: str) -> None:
    history = _distinct_history(100)
    first = produce_candidate(candidate_id, history)
    second = produce_candidate(candidate_id, history)
    assert first == second
    assert first == tuple(sorted(first))


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATE_IDS)
def test_tie_break_uses_first_appearance_then_number(candidate_id: str) -> None:
    spec = candidate_spec(candidate_id)
    recent_size = min(spec.window, 50)
    prefix = _history(50 - recent_size)
    first_group = CausalDrawRow(
        draw="9001", date="2026-05-01", numbers=(44, 45, 46, 47, 48, 49)
    )
    second_group = CausalDrawRow(
        draw="9002", date="2026-05-02", numbers=(1, 2, 3, 4, 5, 6)
    )
    recent = (first_group,) * (recent_size // 2) + (second_group,) * (recent_size // 2)
    rows = tuple(
        CausalDrawRow(draw=str(index + 1), date="2026-05-03", numbers=row.numbers)
        for index, row in enumerate(prefix + recent)
    )
    ticket = produce_candidate(candidate_id, rows)
    assert ticket == (44, 45, 46, 47, 48, 49)


def test_fallback_is_explicit_insufficient_history_failure() -> None:
    with pytest.raises(InsufficientHistory):
        produce_candidate(SELECTED_CANDIDATE_IDS[1], _history(0))
    assert candidate_spec(SELECTED_CANDIDATE_IDS[1]).fallback_rule == (
        "RAISE_INSUFFICIENT_HISTORY_BELOW_50;NO_NUMBER_PADDING"
    )


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATE_IDS)
def test_input_history_is_not_mutated(candidate_id: str) -> None:
    history = list(_distinct_history(75))
    before = tuple(history)
    produce_candidate(candidate_id, history)
    assert tuple(history) == before


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATE_IDS)
def test_strictly_prior_cutoff_excludes_target_and_future_suffix(candidate_id: str) -> None:
    causal = _distinct_history(80)
    target = CausalDrawRow(draw="81", date="2026-04-01", numbers=(44, 45, 46, 47, 48, 49))
    future = CausalDrawRow(draw="82", date="2026-04-02", numbers=(1, 2, 3, 4, 5, 6))
    prediction = produce_candidate(candidate_id, (*causal, target), target_cutoff=80)
    with_future_suffix = produce_candidate(
        candidate_id, (*causal, target, future), target_cutoff=80
    )
    assert prediction == produce_candidate(candidate_id, causal)
    assert with_future_suffix == prediction


def test_duplicate_selected_candidate_signatures_are_absent() -> None:
    signatures = [spec.signature_hash for spec in CANDIDATE_SPECS.values()]
    assert len(signatures) == len(set(signatures))


def test_candidates_are_not_registered_in_production_catalog() -> None:
    catalog_ids = {descriptor.strategy_id for descriptor in production_catalog()}
    assert not catalog_ids.intersection(SELECTED_CANDIDATE_IDS)


def test_producer_contract_does_not_read_files_network_clock_or_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"file access is forbidden: {args!r} {kwargs!r}")

    def fail_getenv(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"environment access is forbidden: {args!r} {kwargs!r}")

    monkeypatch.setattr(builtins, "open", fail_open)
    monkeypatch.setattr("os.getenv", fail_getenv)
    monkeypatch.setattr("time.time", fail_getenv)
    monkeypatch.setattr(socket, "socket", fail_open)
    monkeypatch.setattr(sqlite3, "connect", fail_open)
    ticket = produce_candidate(SELECTED_CANDIDATE_IDS[2], _distinct_history(80))
    assert len(ticket) == 6
