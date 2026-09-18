"""Load-bearing outcome, prefix, incumbent and paired-inference contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import pytest
from tools.b649_operational_prediction_loop import STRATEGY_STREAMS

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.research import b649_loo_oos_validation as validation
from lottolab.strategies.adapters.base import CausalDrawRow

A: Ticket = (1, 2, 3, 4, 5, 6)
B: Ticket = (7, 8, 9, 10, 11, 12)


def pool() -> tuple[StrategyCandidate, ...]:
    tickets = tuple((1, 2, 3, 4, 5, n) for n in range(6, 28))
    return (StrategyCandidate("a", tickets[:11]), StrategyCandidate("b", tickets[11:]))


def outcome() -> validation.SourceDraw:
    return validation.SourceDraw("201", "2020-07-19", A, 7, "a" * 64)


def test_exact_upstream_identity() -> None:
    hashes = validation.verify_authority(Path(__file__).resolve().parents[2])
    assert len(hashes) == 2
    assert validation.CANDIDATE_TREE == "903345ea425bb39bb49ae167caf6d855473ce7d2"


@pytest.mark.parametrize(
    "rows",
    [
        (CausalDrawRow("201", "2020-07-19", A),),
        (CausalDrawRow("202", "2020-07-20", A),),
        (CausalDrawRow("199", "2020-07-17", A), CausalDrawRow("198", "2020-07-16", A)),
        (CausalDrawRow("199", "2020-07-17", A), CausalDrawRow("199", "2020-07-17", A)),
    ],
)
def test_future_target_unordered_and_duplicate_history_rejected(
    rows: tuple[CausalDrawRow, ...],
) -> None:
    with pytest.raises(ValueError, match="PRE_DRAW_CUTOFF_VIOLATION"):
        validation.build_pool(rows, "201", "2020-07-19", ())


def test_exact_stream_identity_must_match_factory() -> None:
    wrong = replace(STRATEGY_STREAMS[0], strategy_version="wrong-version")
    with pytest.raises(ValueError, match="BASELINE_STREAM_IDENTITY_MISMATCH"):
        validation.build_pool((CausalDrawRow("1", "2020-01-01", A),), "201", "2020-07-19", (wrong,))


def test_incumbent_is_same_empty_quality_selector_and_exact_same_k() -> None:
    pairs = validation.paired_tickets(pool())
    assert set(pairs) == {5, 10, 20}
    for k, (baseline, candidate) in pairs.items():
        assert baseline == tuple(build_portfolio(pool(), {}, bucket_sizes=(k,))[k])
        assert len(set(baseline)) == len(set(candidate)) == k
    assert pairs == validation.paired_tickets(tuple(reversed(pool())))


def test_operational_joint_eligibility_does_not_silently_retain_small_k() -> None:
    with pytest.raises(ValueError, match="K20"):
        validation.paired_tickets((StrategyCandidate("a", pool()[0].tickets),))


def test_official_prize_differs_from_three_main_hits() -> None:
    two_plus_special = (1, 2, 7, 20, 21, 22)
    scored = validation.score((two_plus_special,), outcome(), 1)
    assert scored["max_hits"] == 2
    assert scored["official_any_prize"] == 1
    assert scored["p_max_hits_ge_3"] == scored["p_max_hits_ge_4"] == 0
    all_hits = validation.score((A, B, two_plus_special), outcome(), 3)
    assert all_hits["ticket_hits"] == [6, 0, 2]
    assert all_hits["winning_ticket_count"] == 2
    assert all_hits["official_any_prize"] == all_hits["p_max_hits_ge_4"] == 1


@pytest.mark.parametrize("tickets,k", [((A,), 2), ((A, A), 2)])
def test_unequal_or_duplicate_ticket_budget_rejected(tickets: tuple[Ticket, ...], k: int) -> None:
    with pytest.raises(ValueError, match="SAME_K_PAIRING_VIOLATION"):
        validation.score(tickets, outcome(), k)


def test_paired_bootstrap_uses_draw_deltas_not_independent_ticket_samples() -> None:
    assert validation.bootstrap_interval([0] * 20) == [0.0, 0.0]
    assert validation.bootstrap_interval([1] * 20) == [1.0, 1.0]
    mixed = validation.bootstrap_interval([-1] * 10 + [1] * 10)
    assert mixed is not None and mixed[0] < 0 < mixed[1]
    assert mixed == validation.bootstrap_interval([-1] * 10 + [1] * 10)
    rows: list[dict[str, object]] = [
        {
            "baseline": validation.score((A,), outcome(), 1),
            "candidate": validation.score((A,), outcome(), 1),
        }
        for _ in range(20)
    ]
    summary = validation.summarize(rows)
    assert summary["primary_discordant_draw_count"] == 0
    assert summary["primary_exact_p_value"] == 1.0
    assert summary["baseline_ticket_hit_distribution"] == [0, 0, 0, 0, 0, 0, 20]
    assert validation.verdict([summary] * 3, identical_tickets=False) == "INSUFFICIENT_EVIDENCE"
    assert validation.verdict([summary] * 3, identical_tickets=True) == "NO_LIFT"


def test_verdict_never_promotes_unpaired_sparse_or_conflicting_evidence() -> None:
    def summary(low: float, high: float, p: float = 0.001) -> dict[str, object]:
        return {
            "paired_draw_count": 100,
            "primary_discordant_draw_count": 20,
            "primary_exact_p_value": p,
            "primary_familywise_interval": [low, high],
        }

    positive, negative, uncertain = summary(0.1, 0.3), summary(-0.3, -0.1), summary(-0.1, 0.1, 1)
    assert validation.verdict([positive, uncertain, uncertain], identical_tickets=False) == (
        "POSITIVE_LIFT_VALIDATED"
    )
    assert validation.verdict([negative, uncertain, uncertain], identical_tickets=False) == (
        "NEGATIVE_LIFT"
    )
    assert validation.verdict([positive, negative, uncertain], identical_tickets=False) == (
        "UNSTABLE_OR_INCONCLUSIVE"
    )
    assert validation.verdict([], identical_tickets=True) == "INSUFFICIENT_EVIDENCE"
    sparse = {**positive, "paired_draw_count": 5}
    assert validation.verdict([sparse] * 3, identical_tickets=False) == "INSUFFICIENT_EVIDENCE"


def test_temporal_replay_pairs_same_draw_and_cutoff_before_joining_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[int, str]] = []

    def predraw_pool(
        history: tuple[CausalDrawRow, ...],
        number: str,
        day: str,
        streams: object = None,
    ) -> tuple[StrategyCandidate, ...]:
        del streams
        assert all((row.date, int(row.draw)) < (day, int(number)) for row in history)
        seen.append((len(history), number))
        return pool()

    monkeypatch.setattr(validation, "build_pool", predraw_pool)
    monkeypatch.setattr(validation, "BOOTSTRAP_REPLICATES", 100)
    draws = tuple(
        validation.SourceDraw(
            str(i + 1), (date(2020, 1, 1) + timedelta(days=i)).isoformat(), A, 7, "a" * 64
        )
        for i in range(202)
    )
    report = validation.evaluate(draws)
    by_k = cast(dict[str, dict[str, object]], report["by_k"])
    for k in validation.SUPPORTED_K:
        rows = cast(list[dict[str, object]], by_k[str(k)]["paired_draws"])
        assert [(r["target_draw"], r["cutoff_draw"], r["k"]) for r in rows] == [
            ("201", "200", k),
            ("202", "201", k),
        ]
        assert by_k[str(k)]["valid_paired_draws"] == 2
        assert by_k[str(k)]["excluded_draws"] == 200
    # Changing target 202's outcome cannot change its construction or any earlier selection.
    changed = validation.evaluate(
        (*draws[:-1], replace(draws[-1], main_numbers=B, special_number=13))
    )
    changed_k = cast(dict[str, dict[str, object]], changed["by_k"])
    for k in validation.SUPPORTED_K:
        before = cast(list[dict[str, object]], by_k[str(k)]["paired_draws"])
        after = cast(list[dict[str, object]], changed_k[str(k)]["paired_draws"])
        assert [r["selection_sha256"] for r in before] == [r["selection_sha256"] for r in after]
    assert all(n < int(target) for n, target in seen)
    assert validation.encoded(report) == validation.encoded(json.loads(validation.encoded(report)))
