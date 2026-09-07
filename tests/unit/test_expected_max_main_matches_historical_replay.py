"""Tests for the Expected-Max historical replay (seed vs. terminal, k=2/3/5/10)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from fractions import Fraction

import pytest

from lottolab.application.historical_success_random_baseline import (
    official_any_prize_probability,
)
from lottolab.domain.exact_native_replay import Draw
from lottolab.research.expected_max_main_matches_exact_1exchange_ascent import portfolio_sha256
from lottolab.research.expected_max_main_matches_historical_replay import (
    HistoricalReplayContractError,
    WindowKCell,
    as_portfolio,
    build_result,
    evaluate_window_k_cell,
    load_and_verify_portfolios,
    portfolio_official_any_prize,
    replay_portfolio_over_draws,
)

SEED_TICKET = (1, 2, 3, 4, 5, 6)
TERMINAL_TICKET = (20, 21, 22, 23, 24, 25)


def _draw(number: str, main_numbers: tuple[int, ...], special_number: int) -> Draw:
    return Draw(
        draw_number=number,
        draw_date=date(2020, 1, int(number)),
        main_numbers=main_numbers,
        special_number=special_number,
    )


# --- portfolio_official_any_prize / replay_portfolio_over_draws ------------


def test_portfolio_official_any_prize_true_on_exact_jackpot() -> None:
    draw = _draw("1", SEED_TICKET, 49)
    assert portfolio_official_any_prize((SEED_TICKET,), draw) is True


def test_portfolio_official_any_prize_true_on_lower_tier() -> None:
    # 3 main hits, special not in ticket -> GENERAL tier.
    draw = _draw("1", (1, 2, 3, 40, 41, 42), 43)
    assert portfolio_official_any_prize((SEED_TICKET,), draw) is True


def test_portfolio_official_any_prize_false_when_no_ticket_wins() -> None:
    draw = _draw("1", (30, 31, 32, 33, 34, 35), 49)
    assert portfolio_official_any_prize((SEED_TICKET, TERMINAL_TICKET), draw) is False


def test_replay_portfolio_over_draws_preserves_order() -> None:
    winning = _draw("1", SEED_TICKET, 49)
    losing = _draw("2", (30, 31, 32, 33, 34, 35), 49)
    assert replay_portfolio_over_draws((SEED_TICKET,), (winning, losing)) == (True, False)


# --- evaluate_window_k_cell -------------------------------------------------


def _four_bucket_draws() -> tuple[Draw, ...]:
    both = _draw("1", (1, 2, 3, 20, 21, 22), 49)
    only_seed = _draw("2", (1, 2, 3, 4, 30, 31), 49)
    only_terminal = _draw("3", (20, 21, 22, 23, 30, 31), 49)
    neither = _draw("4", (30, 31, 32, 33, 34, 35), 49)
    return (both, only_seed, only_terminal, neither)


def test_evaluate_window_k_cell_contingency_table() -> None:
    draws = _four_bucket_draws()
    cell = evaluate_window_k_cell(
        window_name="FULL",
        k=2,
        seed_portfolio=(SEED_TICKET,),
        terminal_portfolio=(TERMINAL_TICKET,),
        draws=draws,
    )
    assert cell.denominator == 4
    assert cell.seed_numerator == 2  # both + only_seed
    assert cell.terminal_numerator == 2  # both + only_terminal
    assert cell.both_success == 1
    assert cell.only_seed_success == 1
    assert cell.only_terminal_success == 1
    assert cell.neither_success == 1

    payload = cell.canonical_dict()
    assert payload["seed"]["rate_float"] == pytest.approx(0.5)
    assert payload["terminal"]["rate_float"] == pytest.approx(0.5)
    assert payload["terminal_minus_seed"]["rate_float"] == pytest.approx(0.0)
    assert payload["pairwise_same_draw_counts"] == {
        "both_success": 1,
        "only_terminal_success": 1,
        "only_seed_success": 1,
        "neither_success": 1,
    }
    baseline_probability = Fraction(
        payload["baseline"]["success_probability_exact"]["numerator"],
        payload["baseline"]["success_probability_exact"]["denominator"],
    )
    assert 0 < baseline_probability < 1


def test_evaluate_window_k_cell_identical_portfolios_never_split() -> None:
    draws = _four_bucket_draws()
    cell = evaluate_window_k_cell(
        window_name="FULL",
        k=2,
        seed_portfolio=(SEED_TICKET,),
        terminal_portfolio=(SEED_TICKET,),
        draws=draws,
    )
    assert cell.only_seed_success == 0
    assert cell.only_terminal_success == 0
    assert cell.seed_numerator == cell.terminal_numerator
    assert cell.both_success + cell.neither_success == cell.denominator


def test_evaluate_window_k_cell_rejects_inconsistent_manual_construction() -> None:
    with pytest.raises(HistoricalReplayContractError):
        WindowKCell(
            window_name="FULL",
            k=2,
            denominator=4,
            seed_numerator=2,
            terminal_numerator=2,
            both_success=1,
            only_terminal_success=1,
            only_seed_success=1,
            neither_success=0,  # wrong: should be 1 to sum to 4
            baseline_success_probability=official_any_prize_probability(2),
        )


# --- load_and_verify_portfolios ---------------------------------------------


def _entry(seed: tuple[tuple[int, ...], ...], terminal: tuple[tuple[int, ...], ...]) -> dict:
    return {
        "seed_portfolio": [list(ticket) for ticket in seed],
        "terminal_portfolio": [list(ticket) for ticket in terminal],
        "seed_portfolio_sha256": portfolio_sha256(seed),
        "terminal_portfolio_sha256": portfolio_sha256(terminal),
        "seed_expected_max": {"numerator": 1, "denominator": 2, "exact": "1/2"},
        "terminal_expected_max": {"numerator": 1, "denominator": 2, "exact": "1/2"},
        "delta_seed_to_terminal": {"numerator": 0, "denominator": 1, "exact": "0/1"},
    }


def _valid_artifact() -> dict:
    p2 = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))
    p3 = (*p2, (13, 14, 15, 16, 17, 18))
    p5 = (*p3, (19, 20, 21, 22, 23, 24), (25, 26, 27, 28, 29, 30))
    seed10 = (
        *p5,
        (31, 32, 33, 34, 35, 36),
        (37, 38, 39, 40, 41, 42),
        (43, 44, 45, 46, 47, 48),
        (2, 8, 14, 20, 26, 31),
        (1, 7, 13, 19, 25, 49),
    )
    terminal10 = (*seed10[:-1], (2, 8, 14, 20, 26, 49))
    return {
        "k_results": {
            "2": _entry(p2, p2),
            "3": _entry(p3, p3),
            "5": _entry(p5, p5),
            "10": _entry(seed10, terminal10),
        }
    }


def test_load_and_verify_portfolios_accepts_valid_artifact() -> None:
    verified = load_and_verify_portfolios(_valid_artifact())
    assert verified[2].seed_equals_terminal is True
    assert verified[3].seed_equals_terminal is True
    assert verified[5].seed_equals_terminal is True
    assert verified[10].seed_equals_terminal is False


def test_load_and_verify_portfolios_detects_hash_mismatch() -> None:
    artifact = _valid_artifact()
    artifact["k_results"]["2"]["seed_portfolio_sha256"] = "0" * 64
    with pytest.raises(HistoricalReplayContractError, match="does not reproduce"):
        load_and_verify_portfolios(artifact)


def test_load_and_verify_portfolios_requires_k235_seed_equals_terminal() -> None:
    artifact = _valid_artifact()
    different_seed = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 13))
    artifact["k_results"]["2"]["seed_portfolio"] = [list(t) for t in different_seed]
    artifact["k_results"]["2"]["seed_portfolio_sha256"] = portfolio_sha256(different_seed)
    with pytest.raises(HistoricalReplayContractError, match="expected seed==terminal"):
        load_and_verify_portfolios(artifact)


def test_load_and_verify_portfolios_rejects_wrong_ticket_count() -> None:
    artifact = _valid_artifact()
    truncated = tuple(as_portfolio(artifact["k_results"]["2"]["seed_portfolio"]))[:1]
    artifact["k_results"]["2"] = _entry(truncated, truncated)
    with pytest.raises(HistoricalReplayContractError, match="ticket count"):
        load_and_verify_portfolios(artifact)


# --- build_result end-to-end (tiny synthetic history) -----------------------


def _synthetic_history() -> tuple[Draw, ...]:
    numbers = [
        ((1, 2, 3, 4, 5, 6), 7),
        ((7, 8, 9, 10, 11, 12), 13),
        ((13, 14, 15, 16, 17, 18), 19),
        ((19, 20, 21, 22, 23, 24), 25),
        ((25, 26, 27, 28, 29, 30), 31),
        ((31, 32, 33, 34, 35, 36), 37),
        ((37, 38, 39, 40, 41, 42), 43),
        ((43, 44, 45, 46, 47, 48), 2),
    ]
    return tuple(_draw(str(i + 1), mains, special) for i, (mains, special) in enumerate(numbers))


def test_build_result_end_to_end_tiny_fixture() -> None:
    history = _synthetic_history()
    cutoff = history[5]  # draw "6": visible = draws 1..6, draws 7/8 excluded
    result = build_result(
        artifact=_valid_artifact(),
        input_artifact_path="docs/research/matrix-native-results/expected-max-exact-1exchange-ascent-r1-result.json",
        input_artifact_sha256="f" * 64,
        pinned_commit="0" * 40,
        pinned_tree="1" * 40,
        all_draws=history,
        draw_authority_metadata={"sha256_before": "a", "sha256_after": "a"},
        max_visible_draw=cutoff.draw_number,
        expected_main_numbers=cutoff.main_numbers,
        expected_special_number=cutoff.special_number,
        window_order=("FULL", "RECENT_2"),
        window_sizes={"FULL": None, "RECENT_2": 2},
        generated_at=datetime(2026, 9, 7, tzinfo=UTC),
    )

    assert result["draw_authority"]["later_draws_present_in_authority"] is True
    assert set(result["windows"]) == {"FULL", "RECENT_2"}
    assert result["windows"]["FULL"]["observations_required"] == 6
    assert result["windows"]["RECENT_2"]["observations_required"] == 2

    for k in (2, 3, 5, 10):
        assert set(result["results"][str(k)]) == {"FULL", "RECENT_2"}
        for window_name, required in (("FULL", 6), ("RECENT_2", 2)):
            cell = result["results"][str(k)][window_name]
            assert cell["denominator"] == required
            counts = cell["pairwise_same_draw_counts"]
            assert (
                counts["both_success"]
                + counts["only_terminal_success"]
                + counts["only_seed_success"]
                + counts["neither_success"]
                == required
            )

    identity = result["portfolio_identity_verification"]
    assert identity["2"]["seed_equals_terminal"] is True
    assert identity["3"]["seed_equals_terminal"] is True
    assert identity["5"]["seed_equals_terminal"] is True
    assert identity["10"]["seed_equals_terminal"] is False
    assert all(entry["hash_reproduced"] for entry in identity.values())

    # JSON-serializable end to end (Fraction/dataclass payloads must reduce to plain types).
    json.dumps(result)
