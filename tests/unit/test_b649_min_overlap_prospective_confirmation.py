"""Focused acceptance for the B649 prospective confirmation freeze."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest

import lottolab.research.b649_min_overlap_prospective_confirmation as protocol
from lottolab.application.b649_k_dpp_portfolio_selector import (
    select_deterministic_min_overlap,
    select_raw_majority_top_k,
)
from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    build_portfolio,
)
from lottolab.strategies.adapters.base import CausalDrawRow


def _draw(number: str, day: str, seed: int) -> protocol.SourceDraw:
    main = tuple(((seed + offset - 1) % 49) + 1 for offset in range(6))
    return protocol.SourceDraw(number, day, main, 49, "h" * 64)


def _fixture_pool_builder(
    history: tuple[CausalDrawRow, ...], target_number: str, target_date: str
) -> tuple[StrategyCandidate, ...]:
    del history, target_number, target_date
    return tuple(
        StrategyCandidate(
            f"fixture-{index}",
            (tuple(((index + offset) % 49) + 1 for offset in range(6)),),
        )
        for index in range(20)
    )


def _fixture_history() -> tuple[CausalDrawRow, ...]:
    return (_draw("115000089", "2026-09-18", 1).history_row(),)


def test_discovery_prefix_sealing_reproduces_its_logical_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = (_draw("115000089", "2026-09-18", 1),)
    expected = protocol.digest([asdict(draw) for draw in prefix])
    monkeypatch.setattr(protocol, "DISCOVERY_DRAW_COUNT", 1)
    monkeypatch.setattr(protocol, "DISCOVERY_FIRST_DRAW", "115000089")
    monkeypatch.setattr(protocol, "DISCOVERY_LAST_DRAW", "115000089")
    monkeypatch.setattr(protocol, "DISCOVERY_LAST_DATE", date(2026, 9, 18))
    monkeypatch.setattr(protocol, "DISCOVERY_LOGICAL_SHA256", expected)

    assert protocol.verify_discovery_prefix(prefix) == expected


def test_confirmatory_start_excludes_the_entire_discovery_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = (
        protocol.DrawIndexRow("115000088", "2026-09-15"),
        protocol.DrawIndexRow("115000089", "2026-09-18"),
        protocol.DrawIndexRow("115000090", "2026-09-20"),
        protocol.DrawIndexRow("115000091", "2026-09-22"),
    )
    monkeypatch.setattr(protocol, "DISCOVERY_DRAW_COUNT", 2)

    summary = protocol.eligibility_summary(index, date(2026, 9, 21))

    assert summary["discovery_dataset_draw_count"] == 2
    assert summary["eligible_draw_count"] == 1
    assert summary["confirmatory_start_draw"] == "115000090"
    assert summary["confirmatory_start_draw_date"] == "2026-09-20"
    assert summary["excluded_future_dated"] == 1


def test_sealing_rejects_target_outcome_in_history_and_pairs_same_draw_at_both_k() -> None:
    history = _fixture_history()
    targets = (
        _draw("115000090", "2026-09-20", 2),
        _draw("115000091", "2026-09-21", 3),
    )

    with pytest.raises(ValueError, match="PRE_DRAW_CUTOFF_VIOLATION"):
        protocol.seal_target(
            (*history, targets[0].history_row()),
            targets[0],
            _fixture_pool_builder,
        )

    window = protocol.seal_window(
        tuple(_draw("115000089", "2026-09-18", 1) for _ in range(1)),
        targets,
        is_eligible=lambda draw: True,
        horizon=2,
        pool_builder=_fixture_pool_builder,
    )

    assert window.exclusions == ()
    assert window.eligible_seen == 2
    assert window.eligible_unprocessed == 0
    assert window.determinism_verified is True
    assert [draw.target.draw_number for draw in window.sealed] == [
        "115000090",
        "115000091",
    ]
    assert all(set(draw.tickets) == {10, 20} for draw in window.sealed)
    assert all(
        len(draw.tickets[k][protocol.INCUMBENT_ARM]) == k
        and len(draw.tickets[k][protocol.CANDIDATE_ARM]) == k
        for draw in window.sealed
        for k in protocol.CONFIRMATION_K
    )


def test_candidate_and_incumbent_are_the_frozen_selectors() -> None:
    history = _fixture_history()
    target = _draw("115000090", "2026-09-20", 2)
    pool = _fixture_pool_builder(history, target.draw_number, target.draw_date)
    sealed = protocol.seal_target(history, target, _fixture_pool_builder)

    assert isinstance(sealed, protocol.SealedDraw)
    source = protocol.source_identity(history, target, sealed.history_sha256)
    assert protocol.CANDIDATE_ARM == "MIN_OVERLAP"
    assert protocol.INCUMBENT_ARM == "RAW_MAJORITY"
    candidate_contract = cast(dict[str, object], protocol.PROTOCOL["candidate"])
    incumbent_contract = cast(dict[str, object], protocol.PROTOCOL["incumbent"])
    assert candidate_contract["method_id"] == protocol.MIN_OVERLAP_METHOD_ID
    assert candidate_contract["method_version"] == protocol.MIN_OVERLAP_METHOD_VERSION
    assert incumbent_contract["method_id"] == protocol.RAW_MAJORITY_METHOD_ID
    assert incumbent_contract["method_version"] == protocol.RAW_MAJORITY_METHOD_VERSION
    assert incumbent_contract["substitution"] == "FORBIDDEN"

    for k in protocol.CONFIRMATION_K:
        expected_candidate = select_deterministic_min_overlap(pool, source=source, k=k)
        expected_incumbent = select_raw_majority_top_k(pool, source=source, k=k)
        operational = build_portfolio(pool, {}, bucket_sizes=protocol.BUCKET_SIZES)[k]
        assert sealed.tickets[k][protocol.CANDIDATE_ARM] == expected_candidate.tickets
        assert sealed.tickets[k][protocol.INCUMBENT_ARM] == expected_incumbent.tickets
        assert list(sealed.tickets[k][protocol.INCUMBENT_ARM]) == list(operational)
        assert sealed.portfolio_sha256[k][protocol.CANDIDATE_ARM] == (
            expected_candidate.portfolio_sha256
        )
        assert sealed.portfolio_sha256[k][protocol.INCUMBENT_ARM] == (
            expected_incumbent.portfolio_sha256
        )


def test_below_horizon_assessment_stays_blinded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = (_draw("115000089", "2026-09-18", 1),)
    targets = (
        _draw("115000090", "2026-09-20", 2),
        _draw("115000091", "2026-09-21", 3),
    )
    index = tuple(
        protocol.DrawIndexRow(draw.draw_number, draw.draw_date) for draw in (*prefix, *targets)
    )
    monkeypatch.setattr(protocol, "DISCOVERY_DRAW_COUNT", 1)

    def forbidden_scoring(_: object) -> dict[int, list[dict[str, object]]]:
        raise AssertionError("confirmatory outcomes must remain unscored below the horizon")

    monkeypatch.setattr(protocol, "score_analysis", forbidden_scoring)
    state = protocol.assess(
        index,
        prefix,
        targets,
        as_of=date(2026, 9, 21),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
        pool_builder=_fixture_pool_builder,
        horizon=3,
    )

    assert state["confirmation_status"] == protocol.STATUS_INSUFFICIENT
    assert state["confirmatory_outcomes_inspected"] is False
    analysis = state["analysis"]
    assert isinstance(analysis, dict)
    assert analysis["performed"] is False
    assert analysis["paired_draws_available"] == 2
    assert analysis["remaining_paired_draws"] == 1
    by_k = cast(dict[str, dict[str, object]], state["by_k"])
    comparison_10 = cast(dict[str, object], by_k["10"]["outcome_comparison"])
    comparison_20 = cast(dict[str, object], by_k["20"]["outcome_comparison"])
    assert comparison_10["status"] == protocol.BLINDED
    assert comparison_20["status"] == protocol.BLINDED


def test_metadata_fixture_loader_never_selects_outcome_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    class Cursor:
        def __init__(self, rows: list[tuple[object, ...]]) -> None:
            self.rows = rows

        def fetchall(self) -> list[tuple[object, ...]]:
            return self.rows

    class Connection:
        def execute(self, sql: str, params: tuple[object, ...] = ()) -> Cursor:
            calls.append((sql, params))
            if sql.startswith("SELECT draw_number, draw_date FROM draws"):
                assert "main_numbers_json" not in sql
                assert "special_numbers_json" not in sql
                return Cursor(
                    [
                        ("115000089", "2026-09-18"),
                        ("115000090", "2026-09-19"),
                    ]
                )
            return Cursor([])

    @contextmanager
    def open_fixture(
        paths: object, *, read_only: bool = False
    ) -> Generator[Connection]:
        del paths
        assert read_only is True
        yield Connection()

    def schema_ok(paths: object) -> bool:
        del paths
        return True

    monkeypatch.setattr(protocol, "verify_schema_read_only", schema_ok)
    monkeypatch.setattr(protocol, "open_database", open_fixture)

    rows = protocol.load_draw_index(tmp_path / "fixture-lottolab.db")

    assert [(row.draw_number, row.draw_date) for row in rows] == [
        ("115000089", "2026-09-18"),
        ("115000090", "2026-09-19"),
    ]
    assert calls[0][0] == "PRAGMA query_only = ON"
    assert calls[1][0] == "BEGIN"
    assert calls[2][0] == protocol.DRAW_INDEX_SQL


def test_frozen_known_answer_checks_pass() -> None:
    protocol.verify_source_pins()
    protocol.verify_stream_identities()
    protocol.verify_metric_known_answers()
    protocol.verify_statistics_known_answers()
