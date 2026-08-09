# pyright: reportUnknownMemberType=false
# pyright: reportUnknownParameterType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

from fractions import Fraction

from fastapi.testclient import TestClient

from lottolab.application.historical_success_random_baseline import (
    HistoricalSuccessExactRational,
    binomial_upper_tail,
)
from lottolab.application.multiwindow_success_windows import (
    ExactRational,
    MultiWindowSource,
    StrategySource,
    TargetOutcome,
    WindowKind,
    WindowStatus,
    analyze_multiwindow_success_windows,
    exact_binomial_upper_tail,
    source_with_default_null_contract,
)
from lottolab.interfaces.api.app import create_app


def _source(
    lottery_type: str,
    observation_count: int,
    *,
    native_ticket_count: int = 1,
    winning_positions: frozenset[int] = frozenset(),
):
    observations = tuple(
        TargetOutcome(
            target_id=str(index + 1),
            target_date=f"2020-01-{(index % 28) + 1:02d}",
            cutoff_draw_id=None if index == 0 else str(index),
            cutoff_draw_date=None if index == 0 else "2020-01-01",
            target_order=index,
            cutoff_order=None if index == 0 else index - 1,
            native_ticket_count=native_ticket_count,
            ticket_count=native_ticket_count,
            winning_ticket_count=1 if index in winning_positions else 0,
            tier_counts=(
                (("THIRD", 3, 1),)
                if lottery_type == "DAILY_539" and index in winning_positions
                else (("EIGHTH", 8, 1),)
                if lottery_type == "POWER_LOTTO" and index in winning_positions
                else ()
            ),
        )
        for index in range(observation_count)
    )
    strategy = StrategySource(
        strategy_id="test_strategy",
        strategy_version="v1",
        native_ticket_count=native_ticket_count,
        min_history=0,
        observations=observations,
    )
    return source_with_default_null_contract(
        lottery_type=lottery_type,
        run_id="TEST_RUN",
        schema_version="test-schema",
        source_sha256="source-sha",
        source_commit="source-commit",
        strategy_set_fingerprint="strategy-fingerprint",
        status="COMPLETE",
        draw_count=observation_count,
        strategies=(strategy,),
        source_authority="TEST_READ_ONLY_SOURCE",
    )


def test_null_oracles_match_exact_game_combinatorics() -> None:
    t539 = analyze_multiwindow_success_windows(_source("DAILY_539", 1)).null_contract
    p638 = analyze_multiwindow_success_windows(_source("POWER_LOTTO", 1)).null_contract

    assert (t539.legal_ticket_count, t539.any_prize_ticket_count) == (575_757, 65_621)
    assert (
        t539.single_ticket_any_prize_probability.numerator,
        t539.single_ticket_any_prize_probability.denominator,
    ) == (65_621, 575_757)
    assert (p638.legal_ticket_count, p638.any_prize_ticket_count) == (22_085_448, 2_602_320)
    assert (
        p638.single_ticket_any_prize_probability.numerator,
        p638.single_ticket_any_prize_probability.denominator,
    ) == (15_490, 131_461)


def test_recurrence_tail_is_exactly_equal_to_reference_tail() -> None:
    for observation_count in range(1, 16):
        for observed_success_count in range(observation_count + 1):
            probability = Fraction(3, 11)
            optimized = exact_binomial_upper_tail(
                observation_count,
                observed_success_count,
                ExactRational.from_fraction(probability),
            )
            reference = binomial_upper_tail(
                observation_count,
                observed_success_count,
                HistoricalSuccessExactRational.from_fraction(probability),
            )
            assert optimized.as_fraction() == reference.as_fraction()


def test_windows_use_latest_targets_and_mark_short_history_explicitly() -> None:
    analysis = analyze_multiwindow_success_windows(
        _source("DAILY_539", 800, winning_positions=frozenset({799}))
    )
    rows = {row.window_kind: row for row in analysis.rows}

    assert analysis.family_size == 4
    assert rows[WindowKind.FULL_HISTORY].actual_target_count == 800
    assert rows[WindowKind.LONG_750].actual_target_count == 750
    assert rows[WindowKind.MEDIUM_300].actual_target_count == 300
    assert rows[WindowKind.SHORT_50].actual_target_count == 50
    assert rows[WindowKind.SHORT_50].first_target_id == "751"
    assert rows[WindowKind.SHORT_50].last_target_id == "800"
    assert rows[WindowKind.SHORT_50].status is WindowStatus.COMPLETE
    assert rows[WindowKind.SHORT_50].observed_winning_target_count == 1
    assert all(row.by_adjusted_p_value is not None for row in analysis.rows)

    short_history = analyze_multiwindow_success_windows(_source("DAILY_539", 40))
    short_rows = {row.window_kind: row for row in short_history.rows}
    assert short_rows[WindowKind.FULL_HISTORY].status is WindowStatus.COMPLETE
    assert short_rows[WindowKind.LONG_750].status is WindowStatus.INSUFFICIENT_WINDOW_HISTORY
    assert short_rows[WindowKind.MEDIUM_300].status is WindowStatus.INSUFFICIENT_WINDOW_HISTORY
    assert short_rows[WindowKind.SHORT_50].status is WindowStatus.INSUFFICIENT_WINDOW_HISTORY
    assert short_rows[WindowKind.SHORT_50].raw_p_value is None
    assert short_rows[WindowKind.SHORT_50].by_adjusted_p_value is not None
    assert all(item.relation.value == "UNAVAILABLE" for item in short_history.stability)


class _FakeReader:
    def __init__(self, source: MultiWindowSource) -> None:
        self.source = source

    def load_source(self, run_id: str) -> MultiWindowSource | None:
        return self.source if run_id == self.source.run_id else None


def test_api_exposes_lazy_200_404_and_503_routes() -> None:
    source = _source("DAILY_539", 55)
    app = create_app(
        t539_multiwindow_success_source_reader_factory=lambda: _FakeReader(source),
    )
    client = TestClient(app)

    response = client.get("/api/v1/t539-historical/runs/TEST_RUN/success-windows")
    assert response.status_code == 200
    payload = response.json()
    assert payload["event"] == "OFFICIAL_ANY_PRIZE_TARGET_SUCCESS"
    assert payload["family_size"] == 4
    assert payload["promotion_allowed"] is False
    assert payload["rows"][0]["status"] == "COMPLETE"
    assert isinstance(payload["rows"][0]["null_portfolio_probability"]["numerator"], str)

    assert (
        client.get("/api/v1/t539-historical/runs/UNKNOWN/success-windows").status_code == 404
    )
    assert (
        TestClient(create_app())
        .get("/api/v1/p638-historical/current-runs/TEST_RUN/success-windows")
        .status_code
        == 503
    )


def test_openapi_declares_both_success_window_paths_without_calling_factories() -> None:
    def fail_factory():
        raise AssertionError("reader factory must stay lazy")

    app = create_app(
        t539_multiwindow_success_source_reader_factory=fail_factory,
        p638_multiwindow_success_source_reader_factory=fail_factory,
    )
    paths = app.openapi()["paths"]
    assert "/api/v1/t539-historical/runs/{run_id}/success-windows" in paths
    assert "/api/v1/p638-historical/current-runs/{run_id}/success-windows" in paths
