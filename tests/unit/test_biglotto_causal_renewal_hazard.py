from __future__ import annotations

import hashlib
import socket
import sqlite3
import subprocess
import urllib.request
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_causal_renewal_hazard as candidate
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
)

STRATEGY_VERSION = "FIXED_DISCRETE_RENEWAL_HAZARD_V1"
STRATEGIES_BY_K = {
    2: "research_causal_renewal_hazard_k2",
    3: "research_causal_renewal_hazard_k3",
    5: "research_causal_renewal_hazard_k5",
}
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "renewal_te_k235"
    / "renewal_te_k235_golden.npz"
)
FIXTURE_SHA256 = "e2cfd985fceae1baf7c1c7f2708736547ec091dc8e6759a6f60eb9f2a98c650b"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _fixture():
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
    return np.load(FIXTURE_PATH, allow_pickle=False)


def _causal_rows(mains: np.ndarray) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=f"D{index + 1:04d}",
            date=f"DATE-{index + 1:04d}",
            numbers=tuple(int(number) for number in row),
        )
        for index, row in enumerate(mains)
    )


def _adapter_outputs(mains: np.ndarray, ticket_count: int) -> tuple[tuple[int, ...], ...]:
    adapter_type = candidate.ADAPTER_TYPES_BY_K[ticket_count]
    return adapter_type().get_bets(_causal_rows(mains), LotteryType.BIG_LOTTO)


def test_runtime_loads_candidate_and_contract_from_project_relative_paths() -> None:
    base_module = __import__("lottolab.strategies.adapters.base", fromlist=["PortfolioBetAdapter"])
    assert (
        Path(candidate.__file__).resolve()
        == (
            PROJECT_ROOT / "src/lottolab/strategies/adapters/biglotto_causal_renewal_hazard.py"
        ).resolve()
    )
    assert (
        Path(base_module.__file__).resolve()
        == (PROJECT_ROOT / "src/lottolab/strategies/adapters/base.py").resolve()
    )
    assert all(
        issubclass(adapter_type, PortfolioBetAdapter)
        for adapter_type in candidate.ADAPTER_TYPES_BY_K.values()
    )


def test_candidate_model_uses_no_database_process_or_network_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny(*_args, **_kwargs):
        raise AssertionError("unexpected external side effect")

    monkeypatch.setattr(sqlite3, "connect", deny)
    monkeypatch.setattr(subprocess, "Popen", deny)
    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(urllib.request, "urlopen", deny)
    with _fixture() as fixture:
        mains = fixture["renewal_rolling_750_main"]
    assert len(_adapter_outputs(mains, 2)) == 2


def test_exact_model_values_rank_and_all_ticket_orders_match_fixed_donor_fixture() -> None:
    with _fixture() as fixture:
        mains = fixture["renewal_rolling_750_main"]
        expected = {
            name: fixture[f"renewal_rolling_750_{name}"]
            for name in (
                "risk",
                "events",
                "age_current",
                "frequency",
                "hazard",
                "frequency_score",
                "age_hazard",
                "score",
                "ranking",
            )
        }
        expected_tickets = {k: fixture[f"renewal_rolling_750_tickets_k{k}"] for k in (2, 3, 5)}
    model = candidate._analyze(_causal_rows(mains))
    assert model.risk == tuple(tuple(int(value) for value in row) for row in expected["risk"])
    assert model.events == tuple(tuple(int(value) for value in row) for row in expected["events"])
    assert model.age_current == tuple(
        None if int(value) == -1 else int(value) for value in expected["age_current"]
    )
    assert model.frequency == tuple(int(value) for value in expected["frequency"])
    assert model.hazards == tuple(
        tuple(Fraction(str(value)) for value in row) for row in expected["hazard"]
    )
    assert model.frequency_scores == tuple(
        Fraction(str(value)) for value in expected["frequency_score"]
    )
    assert model.age_hazards == tuple(Fraction(str(value)) for value in expected["age_hazard"])
    assert model.scores == tuple(Fraction(str(value)) for value in expected["score"])
    assert model.ranking == tuple(int(value) for value in expected["ranking"])
    for ticket_count in (2, 3, 5):
        assert _adapter_outputs(mains, ticket_count) == tuple(
            tuple(int(value) for value in row) for row in expected_tickets[ticket_count]
        )


def test_three_fixed_strategy_identities_use_canonical_portfolio_contract() -> None:
    expected_ids = {
        2: "research_causal_renewal_hazard_k2",
        3: "research_causal_renewal_hazard_k3",
        5: "research_causal_renewal_hazard_k5",
    }
    adapter_types = [candidate.ADAPTER_TYPES_BY_K[k] for k in (2, 3, 5)]
    assert all(issubclass(adapter_type, PortfolioBetAdapter) for adapter_type in adapter_types)
    assert len({adapter_type.implementation_identity for adapter_type in adapter_types}) == 3
    for ticket_count, adapter_type in candidate.ADAPTER_TYPES_BY_K.items():
        assert adapter_type.strategy_id == expected_ids[ticket_count]
        assert adapter_type.strategy_version == STRATEGY_VERSION
        assert adapter_type.implementation_identity.startswith(adapter_type.strategy_id)
        assert adapter_type.min_history == 750
        assert adapter_type.native_ticket_count == ticket_count
        assert adapter_type.supported_lottery_types == (LotteryType.BIG_LOTTO,)
        assert "execution_version" not in adapter_type.__dict__


def test_history_longer_than_750_uses_the_fixed_trailing_window() -> None:
    with _fixture() as fixture:
        mains = fixture["renewal_rolling_800_main"]
        expected = fixture["renewal_rolling_800_last750_k2_tickets"]
    assert _adapter_outputs(mains, 2) == tuple(
        tuple(int(value) for value in row) for row in expected
    )


def test_749_rows_raise_canonical_insufficient_history_without_fallback() -> None:
    with _fixture() as fixture:
        mains = fixture["renewal_rolling_750_main"][:-1]
    with pytest.raises(InsufficientHistory, match="needs 750 draws, got 749"):
        candidate.BigLottoCausalRenewalHazardK2Adapter().get_bets(
            _causal_rows(mains), LotteryType.BIG_LOTTO
        )


def test_never_hit_numbers_use_exact_p0_and_stable_small_number_ties() -> None:
    with _fixture() as fixture:
        mains = fixture["renewal_constant_750_main"]
        expected_frequency = fixture["renewal_constant_750_frequency"]
        expected_ages = fixture["renewal_constant_750_age_current"]
        expected_scores = fixture["renewal_constant_750_score"]
        expected_ranking = fixture["renewal_constant_750_ranking"]
    model = candidate._analyze(_causal_rows(mains))
    for index in range(6, 49):
        assert model.frequency[index] == int(expected_frequency[index]) == 0
        assert model.age_current[index] is None
        assert int(expected_ages[index]) == -1
        assert model.age_bucket[index] is None
        assert model.age_hazards[index] == candidate._P0
        assert model.scores[index] == Fraction(str(expected_scores[index]))
    assert [number for number in model.ranking if number >= 7] == list(range(7, 50))
    assert model.ranking == tuple(int(value) for value in expected_ranking)


def test_left_truncation_and_age_bucket_boundaries_match_fixed_donor_fixture() -> None:
    with _fixture() as fixture:
        sequence = tuple(int(value) for value in fixture["renewal_sequence_input"])
        expected_risk = tuple(int(value) for value in fixture["renewal_sequence_risk"])
        expected_events = tuple(int(value) for value in fixture["renewal_sequence_events"])
        expected_age_value = int(fixture["renewal_sequence_age"][0])
        expected_frequency = int(fixture["renewal_sequence_frequency"][0])
        expected_hazards = tuple(
            Fraction(str(value)) for value in fixture["renewal_sequence_hazards"]
        )
        boundaries = tuple(int(value) for value in fixture["renewal_age_boundaries"])
        expected_buckets = tuple(int(value) for value in fixture["renewal_age_boundary_buckets"])
    risk, events, age, frequency, hazards = candidate._risk_sequence(sequence)
    assert risk == expected_risk
    assert events == expected_events
    assert age == (None if expected_age_value == -1 else expected_age_value)
    assert frequency == expected_frequency
    assert hazards == expected_hazards
    assert sum(risk) == len(sequence) - 3
    assert sum(events) == 2
    assert tuple(candidate._age_bucket(value) for value in boundaries) == expected_buckets


def test_fixed_target_cutoff_excludes_target_and_later_rows() -> None:
    with _fixture() as fixture:
        mains = fixture["renewal_rolling_800_main"]
    captured: list[tuple[CausalDrawRow, ...]] = []

    class RecordingAdapter(candidate.BigLottoCausalRenewalHazardK2Adapter):
        def _predict_all(self, history, lottery_type):
            captured.append(history)
            return super()._predict_all(history, lottery_type)

    adapter = RecordingAdapter()
    prefix = _causal_rows(mains[:750])
    first = adapter.get_bets(prefix, LotteryType.BIG_LOTTO)
    changed_later = _causal_rows(mains[:750]) + _causal_rows(mains[750:])
    second = adapter.get_bets(changed_later[:750], LotteryType.BIG_LOTTO)
    assert first == second
    assert captured == [prefix, prefix]
    assert all(row.draw != "D0751" for row in captured[0])


def test_invalid_and_duplicate_primary_numbers_fail_closed() -> None:
    with _fixture() as fixture:
        mains = fixture["renewal_rolling_750_main"]
    valid = _causal_rows(mains)
    adapter = candidate.BigLottoCausalRenewalHazardK2Adapter()
    duplicate = list(valid)
    duplicate[0] = CausalDrawRow(
        draw=duplicate[0].draw, date=duplicate[0].date, numbers=(1, 1, 2, 3, 4, 5)
    )
    with pytest.raises(InvalidOutput, match="duplicate numbers"):
        adapter.get_bets(tuple(duplicate), LotteryType.BIG_LOTTO)
    illegal = list(valid)
    illegal[0] = CausalDrawRow(
        draw=illegal[0].draw, date=illegal[0].date, numbers=(0, 2, 3, 4, 5, 6)
    )
    with pytest.raises(InvalidOutput, match="out of range"):
        adapter.get_bets(tuple(illegal), LotteryType.BIG_LOTTO)


def test_each_k_emits_exactly_legal_tickets_and_repeats_deterministically() -> None:
    with _fixture() as fixture:
        mains = fixture["renewal_rolling_750_main"]
    for ticket_count, adapter_type in candidate.ADAPTER_TYPES_BY_K.items():
        adapter = adapter_type()
        first = adapter.get_bets(_causal_rows(mains), LotteryType.BIG_LOTTO)
        second = adapter.get_bets(_causal_rows(mains), LotteryType.BIG_LOTTO)
        assert first == second
        assert len(first) == ticket_count
        assert all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in first)
        assert all(
            type(number) is int and 1 <= number <= 49 for ticket in first for number in ticket
        )


def test_risk_sequence_rejects_nonbinary_or_noninteger_observations() -> None:
    for sequence in ((0, 2, 1), (0, True, 1), (0, "1", 1)):
        with pytest.raises(ValueError, match="exact binary integers"):
            candidate._risk_sequence(sequence)
