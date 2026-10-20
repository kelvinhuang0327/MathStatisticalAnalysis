"""Falsifiable synthetic checks for the fixed offline K235 experiment."""

from __future__ import annotations

import copy
import math
import random
from datetime import date, timedelta
from typing import Any

import pytest

from lottolab.research import b649_k235_shared_evaluation as study
from lottolab.strategies.adapters.base import CausalDrawRow, InsufficientHistory


def snapshot(n: int = 525) -> list[dict[str, Any]]:
    return [
        {
            "draw": str(100000000 + i),
            "date": (date(2000, 1, 1) + timedelta(days=i)).isoformat(),
            "numbers": sorted({(i * 7 + j * 8) % 49 + 1 for j in range(6)}),
            "special": next(
                v for v in range(1, 50) if v not in {(i * 7 + j * 8) % 49 + 1 for j in range(6)}
            ),
        }
        for i in range(n)
    ]


@pytest.mark.parametrize("model", study.MODELS)
def test_causal_future_target_invariance_and_determinism(model: str) -> None:
    data = snapshot()
    target = {"draw": data[520]["draw"], "date": data[520]["date"]}
    generate = study.generator(study.native_adapters())
    original = study.causal_history(data[:521], target)
    changed = copy.deepcopy(data)
    changed[520]["numbers"] = [40, 41, 42, 43, 44, 45]
    changed[520]["special"] = 49
    changed_history = study.causal_history(changed, target)
    assert original == changed_history
    assert len(original) == 520 and original[-1].draw == data[519]["draw"]
    for k in study.K_VALUES:
        tickets = generate(model, k, original)
        assert tickets == generate(model, k, changed_history)
        assert study.evaluate_candidate_quality(tickets, k).is_valid
    # A same-date earlier period is deliberately withheld too.
    changed[519]["date"] = target["date"]
    assert len(study.causal_history(changed, target)) == 519


@pytest.mark.parametrize("k", study.K_VALUES)
def test_round_robin_quality_and_duplicate_rejection(k: int) -> None:
    tickets = study.assemble([0.0] * 49, k)
    assert tickets == tuple(tuple(range(i + 1, 6 * k + 1, k)) for i in range(k))
    assert len({j for t in tickets for j in t}) == 6 * k
    corrupted = (tickets[0], tickets[0], *tickets[2:])
    quality = study.evaluate_candidate_quality(corrupted, k)
    assert not quality.is_valid and quality.exact_numerator is None
    within = ((1, 1, 2, 3, 4, 5), *tickets[1:])
    assert not study.evaluate_candidate_quality(within, k).is_valid


def test_fixed_score_formulas_and_edge_histories() -> None:
    for model in study.MODELS[1:]:
        with pytest.raises(InsufficientHistory):
            study.scores(model, ())
    row = CausalDrawRow("1", "2000-01-01", (1, 2, 3, 4, 5, 6))
    alpha = 1 - 2 ** (-1 / 50)
    assert study.scores("M1", (row,))[:7] == (1, 1, 1, 1, 1, 1, 0)
    ewma = study.scores("M2", (row,))
    assert ewma[0] == pytest.approx(alpha + (1 - alpha) * 6 / 49)
    assert ewma[6] == pytest.approx((1 - alpha) * 6 / 49)
    assert study.scores("M3", (row,)) == pytest.approx([6 / 49] * 49)
    other = CausalDrawRow("2", "2000-01-02", (7, 8, 9, 10, 11, 12))
    history = (row, other, row)
    markov = study.scores("M3", history)
    assert markov[0] == pytest.approx((50 * 6 / 49) / 51)  # 1 -> 0
    assert markov[6] == pytest.approx((1 + 50 * 6 / 49) / 51)  # 0 -> 1
    long = tuple(CausalDrawRow(str(i), "2000-01-01", other.numbers) for i in range(800))
    assert study.scores("M2", (row, *long)) == study.scores("M2", long[-750:])
    assert study.scores("M3", (row, *long)) == study.scores("M3", long[-750:])
    history2 = (row,) * 700 + (other,) * 50
    value = study.scores("M1", history2)
    assert value[0] == pytest.approx(0.3 * 250 / 300 + 0.2 * 700 / 750)
    assert value[6] == pytest.approx(0.5 + 0.3 * 50 / 300 + 0.2 * 50 / 750)
    assert study.effective_windows("M1", 2, 7) == {"50": 7, "300": 7, "750": 7}
    assert study.effective_windows("M3", 2, 1) == {"draws": 1, "transitions": 0}


@pytest.mark.parametrize(
    ("ticket", "winner", "tier"),
    [
        ((1, 2, 3, 4, 5, 6), True, "FIRST"),
        ((1, 2, 3, 4, 5, 7), True, "SECOND"),
        ((1, 2, 3, 4, 5, 8), True, "THIRD"),
        ((1, 2, 3, 4, 7, 8), True, "FOURTH"),
        ((1, 2, 3, 4, 8, 9), True, "FIFTH"),
        ((1, 2, 3, 7, 8, 9), True, "SIXTH"),
        ((1, 2, 7, 8, 9, 10), True, "SEVENTH"),
        ((1, 2, 3, 8, 9, 10), True, "GENERAL"),
        ((1, 2, 8, 9, 10, 11), False, None),
        ((1, 7, 8, 9, 10, 11), False, None),
    ],
)
def test_official_prize_adjacent_special_boundaries(
    ticket: tuple[int, ...], winner: bool, tier: str | None
) -> None:
    evaluations, success = study.score_tickets(
        (ticket,), {"numbers": [1, 2, 3, 4, 5, 6], "special": 7}
    )
    assert success == winner
    assert evaluations[0]["prize_tier"] == tier


def test_failure_missing_invalid_accounting_and_ticket_only_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = snapshot(3)
    targets = [{"draw": r["draw"], "date": r["date"]} for r in data]
    missing = {"draw": "100000003", "date": "2000-01-04"}
    targets.append(missing)

    def generate(model: str, k: int, history: tuple[CausalDrawRow, ...]) -> study.Tickets:
        if model == "M1":
            raise RuntimeError("injected technical fault")
        if model == "M2":
            return ((1, 1, 2, 3, 4, 5),) * k
        if model == "M3" and not history:
            raise InsufficientHistory("injected no history")
        return study.assemble([0.0] * 49, k)

    rows = [
        study.observation(data, t, m, k, "snapshot", generate)
        for t in targets
        for m in study.MODELS
        for k in study.K_VALUES
    ]
    monkeypatch.setattr(study, "native_adapters", lambda: pytest.fail("strategy replayed"))
    summary = study.verify_records(data, targets, rows, "snapshot")
    assert summary["record_n"] == 48
    assert summary["metrics"]["M1_K2"]["technical_failure_n"] == 4
    assert summary["metrics"]["M2_K2"]["invalid_ticket_n"] == 4
    assert summary["metrics"]["M1_K2"]["known_outcome_n"] == 3
    assert summary["metrics"]["M1_K2"]["usable_rate"] == 0
    assert summary["metrics"]["M1_K2"]["missing_outcome_n"] == 1
    assert all(r["official_any_prize"] is None for r in rows if r["model_id"] == "M1")
    assert all(c["paired_target_n"] == 3 for c in summary["comparisons"])
    assert len(summary["comparisons"]) == 9
    for corrupted in (rows[:-1], [*rows, rows[0]]):
        with pytest.raises(ValueError, match="Missing, duplicate"):
            study.summarize(corrupted, targets)
    altered = copy.deepcopy(rows)
    altered[0]["official_any_prize"] = not altered[0]["official_any_prize"]
    with pytest.raises(ValueError, match="scoring mismatch"):
        study.verify_records(data, targets, altered, "snapshot")


def test_paired_counts_units_direction_correction_and_fair_fractions() -> None:
    def rows(wins: set[int]) -> list[dict[str, Any]]:
        return [
            {
                "target_draw": str(i),
                "official_outcome": {},
                "official_any_prize": i in wins,
                "generation_status": "OK",
            }
            for i in range(40)
        ]

    result = study.paired(rows({0, 1, 2, 3, 4}), rows({4}))
    assert result["paired_target_n"] == 40
    assert (result["b"], result["c"], result["both_success_n"], result["both_failure_n"]) == (
        4,
        0,
        1,
        35,
    )
    assert result["delta_pp"] == 10
    assert result["p_pair"] == pytest.approx(1 / 16)
    assert result["p_adjusted"] == pytest.approx(9 / 16)
    reversed_pair = study.paired(rows({4}), rows({0, 1, 2, 3, 4}))
    assert reversed_pair["delta_pp"] == -10 and reversed_pair["p_pair"] == 1
    assert study.paired(rows(set()), rows(set()))["p_pair"] == 1
    assert study.FAIR_DRAW_EXACT_COVERAGE_FRACTIONS == {
        2: (5302152, 85900584),
        3: (7930128, 85900584),
        5: (13139880, 85900584),
    }
    assert study.circular_interval([0] * 40)["degeneracy"]
    assert "FEWER_THAN_TWO_FULL_BLOCKS" in study.circular_interval([1, 0])["degeneracy"]


def test_binomial_and_two_sided_exact_interval_against_closed_forms() -> None:
    for n in (1, 10, 40):
        for p in (0.1, 0.5, 0.9):
            for s in (0, 1, n):
                expected = sum(math.comb(n, j) * p**j * (1 - p) ** (n - j) for j in range(s, n + 1))
                assert study.binomial_tail(s, n, p) == pytest.approx(expected, abs=1e-12)
    assert study.exact_ci(0, 10) == pytest.approx([0, 1 - 0.025**0.1])
    assert study.exact_ci(10, 10) == pytest.approx([0.025**0.1, 1])


def test_circular_bootstrap_matches_explicit_synchronized_indices() -> None:
    d = [1, 0, -1, 0, 1, 0, 0] * 6 + [1]
    rng = random.Random(20261020)
    means: list[float] = []
    for _ in range(101):
        indices: list[int] = []
        for _ in range(math.ceil(len(d) / 20)):
            start = rng.randrange(len(d))
            indices.extend((start + j) % len(d) for j in range(20))
        means.append(100 * sum(d[i] for i in indices[: len(d)]) / len(d))
    means.sort()
    # (101-1)*.025=2.5 and *.975=97.5: independently derived interpolation.
    result = study.circular_interval(d, replicates=101)
    assert result["ci95_pp"] == pytest.approx(
        [(means[2] + means[3]) / 2, (means[97] + means[98]) / 2]
    )
