"""Portable fixed-fixture regression for the named EH02 donor implementation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_conditional_te as candidate
from lottolab.strategies.adapters.base import CausalDrawRow, InsufficientHistory, InvalidOutput

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "renewal_te_k235"
    / "renewal_te_k235_golden.npz"
)
FIXTURE_SHA256 = "e2cfd985fceae1baf7c1c7f2708736547ec091dc8e6759a6f60eb9f2a98c650b"
DONOR_SHA256 = "9a8337e10986594f28e58034549c2c119a298b6bedd8ca7843836dc40cf197e1"
STRATEGIES = (
    candidate.BigLottoConditionalTEK2Adapter,
    candidate.BigLottoConditionalTEK3Adapter,
    candidate.BigLottoConditionalTEK5Adapter,
)


def _fixture():
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
    return np.load(FIXTURE_PATH, allow_pickle=False)


def _rows(y: np.ndarray, *, start: int = 0) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            str(start + index),
            "2026-01-01",
            tuple(int(number + 1) for number in np.flatnonzero(row)),
        )
        for index, row in enumerate(y)
    )


@pytest.mark.parametrize("kind", ["sparse", "constant", "cyclic"])
def test_fixed_fixture_matches_counts_scores_rankings_and_ticket_orders(kind: str) -> None:
    with _fixture() as fixture:
        y = fixture[f"te_{kind}_input"]
        expected_arrays = {
            name: fixture[f"te_{kind}_{name}"]
            for name in (
                "joint_counts",
                "own_counts",
                "joint",
                "conditional",
                "marginal",
                "raw_te",
                "te",
                "weight",
                "residual",
                "signal",
                "raw_te_model",
                "score_main",
                "score_markov_control",
                "score_freq_control",
            )
        }
        expected_tickets = {k: fixture[f"te_{kind}_tickets_k{k}"] for k in (2, 3, 5)}
    counts, own, model = candidate.score_history(y, 750)
    np.testing.assert_array_equal(counts, expected_arrays["joint_counts"])
    np.testing.assert_array_equal(own, expected_arrays["own_counts"])
    info = candidate.smoothed_information(counts)
    for name, actual in zip(("joint", "conditional", "marginal", "raw_te"), info, strict=True):
        np.testing.assert_array_equal(actual, expected_arrays[name])
    for name, actual in zip(
        ("te", "weight", "residual", "signal", "raw_te_model"),
        model[1:],
        strict=True,
    ):
        np.testing.assert_array_equal(actual, expected_arrays[name])
    for name in ("MAIN", "MARKOV_CONTROL", "FREQ_CONTROL"):
        np.testing.assert_array_equal(model[0][name], expected_arrays[f"score_{name.lower()}"])

    main = model[0]["MAIN"]
    ranking = sorted(range(1, 50), key=lambda number: (-float(main[number - 1]), number))
    for adapter_type, ticket_count in zip(STRATEGIES, (2, 3, 5), strict=True):
        assert candidate.tickets_from_score(main, ticket_count) == [
            [int(number) for number in row] for row in expected_tickets[ticket_count]
        ]
        actual = adapter_type().get_bets(_rows(y), LotteryType.BIG_LOTTO)
        assert len(actual) == ticket_count
        assert tuple(actual) == tuple(
            tuple(int(number) for number in row) for row in expected_tickets[ticket_count]
        )
        assert all(
            len(ticket) == 6 and len(set(ticket)) == 6 and tuple(sorted(ticket)) == ticket
            for ticket in actual
        )
        assert all(1 <= number <= 49 for ticket in actual for number in ticket)
    assert ranking[0] in range(1, 50)


def test_fixed_identity_ties_and_near_ties_keep_number_order() -> None:
    assert [
        (
            adapter.strategy_id,
            adapter.strategy_version,
            adapter.native_ticket_count,
            adapter.min_history,
        )
        for adapter in STRATEGIES
    ] == [(f"research_conditional_transfer_entropy_k{k}", "EH02_V1", k, 750) for k in (2, 3, 5)]
    assert candidate.IMPLEMENTATION_IDENTITY != "EH02_V1"
    cases = (
        (np.ones(49), list(range(1, 50))),
        (
            np.array([1.0, np.nextafter(1.0, 2.0)] + [1.0] * 47),
            [2, 1, *range(3, 50)],
        ),
    )
    for scores, ranking in cases:
        for ticket_count in (2, 3, 5):
            expected = [
                sorted(ranking[offset : offset + 6]) for offset in range(0, ticket_count * 6, 6)
            ]
            assert candidate.tickets_from_score(scores, ticket_count) == expected


def test_clipping_and_significant_negative_guard_use_fixed_donor_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _fixture() as fixture:
        y = fixture["te_constant_input"]
        counts = fixture["te_constant_joint_counts"]
        self_counts = fixture["te_constant_own_counts"]
        expected_info = tuple(
            fixture[f"te_constant_{name}"]
            for name in ("joint", "conditional", "marginal", "raw_te")
        )
    current = y[-1]
    frequency = y.sum(axis=0)
    real = candidate.smoothed_information
    for negative in (-1e-16, -1e-6):
        fake: candidate.SmoothedInformation = (
            expected_info[0],
            expected_info[1],
            expected_info[2],
            np.full_like(expected_info[3], negative),
        )

        def replacement_smoothed_information(
            _counts: candidate.IntArray,
            value: candidate.SmoothedInformation = fake,
        ) -> candidate.SmoothedInformation:
            return value

        monkeypatch.setattr(candidate, "smoothed_information", replacement_smoothed_information)
        if negative == -1e-16:
            output = candidate.conditional_model(counts, self_counts, current, frequency)
            assert (output[1] == 0).all() and (output[2] == 0).all()
        else:
            with pytest.raises(AssertionError, match="SIGNIFICANT_NEGATIVE_TE_STOP"):
                candidate.conditional_model(counts, self_counts, current, frequency)
    monkeypatch.setattr(candidate, "smoothed_information", real)


def test_causal_window_and_short_history_contract() -> None:
    with _fixture() as fixture:
        cyclic = fixture["te_cyclic_input"]
        constant = fixture["te_constant_input"][:20]
    history = _rows(cyclic)
    prefix = _rows(constant, start=1000)
    for adapter_type in STRATEGIES:
        adapter = adapter_type()
        with pytest.raises(InsufficientHistory):
            adapter.get_bets(history[:-1], LotteryType.BIG_LOTTO)
        expected = adapter.get_bets(history, LotteryType.BIG_LOTTO)
        assert adapter.get_bets(prefix + history, LotteryType.BIG_LOTTO) == expected
        assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == expected


def test_seventh_number_is_not_silently_treated_as_main() -> None:
    with _fixture() as fixture:
        hist = _rows(fixture["te_cyclic_input"])
    invalid = (*hist[:-1], CausalDrawRow("bad", "2026-01-01", (1, 2, 3, 4, 5, 6, 7)))
    with pytest.raises(InvalidOutput):
        STRATEGIES[0]().get_bets(invalid, LotteryType.BIG_LOTTO)
