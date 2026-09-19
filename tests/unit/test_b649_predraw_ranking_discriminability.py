"""Focused tests for the outcome-blind structural discriminability comparison."""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from tools.b649_operational_prediction_loop import StrategyStream

from lottolab.application.b649_operational_portfolio_selector import Ticket
from lottolab.research import b649_predraw_ranking_discriminability as module
from lottolab.research.b649_predraw_ranking_discriminability import (
    DRAW_COLUMNS,
    DRAW_QUERY,
    REPLAY_WHITELIST,
    SelectionPair,
    build_pool,
    compare_target,
    crosscheck,
    digest,
    load_replay_crosscheck,
    summarize,
)
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

MODULE_PATH = Path("src/lottolab/research/b649_predraw_ranking_discriminability.py")

HISTORY: tuple[CausalDrawRow, ...] = tuple(
    CausalDrawRow(str(100 + i), f"2024-01-{i + 1:02d}", (1, 2, 3, 4, 5, 6)) for i in range(5)
)
TARGET = CausalDrawRow("105", "2024-01-06", (7, 8, 9, 10, 11, 12))


class _Stub:
    """Minimal single-ticket adapter stand-in; not a PortfolioBetAdapter."""

    min_history = 0

    def __init__(self, strategy_id: str, ticket: Ticket) -> None:
        self.strategy_id = strategy_id
        self.strategy_version = "v0.1"
        self._ticket = ticket

    def get_one_bet(self, history: object, lottery_type: object) -> tuple[Ticket, None]:
        return self._ticket, None


def stub_streams(tickets: tuple[Ticket, ...]) -> tuple[StrategyStream, ...]:
    def factory(index: int, ticket: Ticket) -> Callable[[], BetAdapter]:
        return cast("Callable[[], BetAdapter]", lambda: _Stub(f"stub{index}", ticket))

    return tuple(
        StrategyStream(
            strategy_id=f"stub{i}",
            strategy_version="v0.1",
            enabled=True,
            adapter_factory=factory(i, ticket),
            native_ticket_count=1,
        )
        for i, ticket in enumerate(tickets)
    )


def twenty_two_tickets() -> tuple[Ticket, ...]:
    tickets: list[Ticket] = [(1, 2, 3, 4, 5, 6 + i) for i in range(20)]
    tickets.append((38, 39, 40, 41, 42, 43))
    tickets.append((44, 45, 46, 47, 48, 49))
    return tuple(tickets)


# --------------------------------------------------------------------------
# Outcome-field non-consumption
# --------------------------------------------------------------------------


def test_projection_names_no_outcome_column() -> None:
    assert DRAW_COLUMNS == ("draw_number", "draw_date", "main_numbers_json")
    lowered = DRAW_QUERY.lower()
    for column in ("special_number", "prize", "winner", "hit", "bonus", "result"):
        assert column not in lowered


def test_replay_whitelist_excludes_the_scored_payloads() -> None:
    assert "baseline" not in REPLAY_WHITELIST
    assert "candidate" not in REPLAY_WHITELIST
    assert "candidate_tickets" not in REPLAY_WHITELIST
    assert "baseline_tickets" in REPLAY_WHITELIST


def test_module_reaches_no_outcome_evaluation_authority() -> None:
    source = MODULE_PATH.read_text()
    imported: set[str] = set()
    identifiers: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
    assert not any("prize_evaluation" in name or "prize" in name for name in imported)
    forbidden = ("prize", "winner", "any_prize", "max_hits", "evaluate_big_lotto")
    assert [
        name for name in sorted(identifiers) if any(bad in name.lower() for bad in forbidden)
    ] == []


def test_build_pool_rejects_history_reaching_the_target() -> None:
    leaked = (*HISTORY, TARGET)
    with pytest.raises(ValueError, match="PRE_DRAW_CUTOFF_VIOLATION"):
        build_pool(leaked, TARGET.draw, TARGET.date, ())


def test_build_pool_rejects_history_past_the_target() -> None:
    future = (*HISTORY, CausalDrawRow("106", "2024-01-07", (1, 2, 3, 4, 5, 7)))
    with pytest.raises(ValueError, match="PRE_DRAW_CUTOFF_VIOLATION"):
        build_pool(future, TARGET.draw, TARGET.date, ())


# --------------------------------------------------------------------------
# Comparison behaviour
# --------------------------------------------------------------------------


def test_compare_target_is_deterministic_and_nested() -> None:
    streams = stub_streams(twenty_two_tickets())
    first = compare_target(HISTORY, TARGET, streams)
    second = compare_target(HISTORY, TARGET, streams)
    assert first == second
    by_k = {pair.k: pair for pair in first}
    assert set(by_k) == {5, 10, 20}
    assert by_k[20].candidate[:5] == by_k[5].candidate
    assert by_k[20].incumbent[:10] == by_k[10].incumbent
    assert by_k[5].distinct_pool_size == 22
    assert by_k[5].pool_sha256 == digest(
        [(f"stub{i}", (t,)) for i, t in enumerate(twenty_two_tickets())]
    )


def test_compare_target_rejects_a_pool_below_k20() -> None:
    streams = stub_streams(twenty_two_tickets()[:19])
    with pytest.raises(ValueError, match="LT20_DISTINCT_TICKETS"):
        compare_target(HISTORY, TARGET, streams)


def pair(k: int, incumbent: tuple[Ticket, ...], candidate: tuple[Ticket, ...]) -> SelectionPair:
    return SelectionPair(
        target_draw="105",
        target_date="2024-01-06",
        cutoff_draw="104",
        history_count=5,
        pool_sha256="deadbeef",
        distinct_pool_size=22,
        k=k,
        incumbent=incumbent,
        candidate=candidate,
    )


A: Ticket = (1, 2, 3, 4, 5, 6)
B: Ticket = (1, 2, 3, 4, 5, 7)
C: Ticket = (10, 11, 12, 13, 14, 15)


def test_summarize_counts_set_order_and_top_rank_differences() -> None:
    identical = pair(2, (A, B), (A, B))
    order_only = pair(2, (A, B), (B, A))
    changed_set = pair(2, (A, B), (A, C))
    summary = summarize([identical, order_only, changed_set])
    assert summary["COMPARABLE_DRAWS"] == 3
    assert summary["SAME_SELECTION_DRAWS"] == 2
    assert summary["DIFFERENT_SELECTION_DRAWS"] == 1
    assert summary["SELECTION_DISAGREEMENT_RATE"] == pytest.approx(1 / 3)
    assert summary["ORDER_ONLY_DIFFERENCE_COUNT"] == 1
    assert summary["TOP_RANK_CHANGE_COUNT"] == 1
    overlap = cast(dict[str, object], summary["TICKET_SET_OVERLAP_SUMMARY"])
    assert overlap["distribution"] == {1: 1, 2: 2}
    assert overlap["min"] == 1
    assert overlap["mean_changed_tickets_per_differing_draw"] == pytest.approx(1.0)


def test_summarize_reports_zero_disagreement_for_identical_rankers() -> None:
    summary = summarize([pair(2, (A, B), (A, B)) for _ in range(4)])
    assert summary["DIFFERENT_SELECTION_DRAWS"] == 0
    assert summary["SELECTION_DISAGREEMENT_RATE"] == 0.0
    assert summary["ORDER_ONLY_DIFFERENCE_COUNT"] == 0


# --------------------------------------------------------------------------
# Same-pool / same-cutoff comparability
# --------------------------------------------------------------------------


def replay_document() -> dict[str, object]:
    row = {
        "target_draw": "105",
        "target_date": "2024-01-06",
        "cutoff_draw": "104",
        "cutoff_date": "2024-01-05",
        "history_count": 5,
        "history_sha256": "h",
        "pool_sha256": "deadbeef",
        "k": 2,
        "baseline_tickets": [list(A), list(B)],
        "baseline": {"official_any_prize": 1, "max_hits": 4},
        "candidate": {"official_any_prize": 0, "max_hits": 2},
    }
    return {"by_k": {"2": {"paired_draws": [row]}}}


def test_replay_loader_drops_scored_payloads(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(replay_document()))
    rows = load_replay_crosscheck(path)
    assert set(rows) == {("105", 2)}
    assert frozenset(rows[("105", 2)]) == REPLAY_WHITELIST


def test_replay_loader_fails_closed_on_schema_change(tmp_path: Path) -> None:
    document = replay_document()
    by_k = cast("dict[str, dict[str, list[dict[str, object]]]]", document["by_k"])
    del by_k["2"]["paired_draws"][0]["pool_sha256"]
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="REPLAY_ARTIFACT_SCHEMA_CHANGED"):
        load_replay_crosscheck(path)


def test_crosscheck_confirms_same_pool_cutoff_and_incumbent(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(replay_document()))
    replay = load_replay_crosscheck(path)
    result = crosscheck([pair(2, (A, B), (A, C))], replay)
    assert result["MATCHED_ROWS"] == 1
    assert result["SAME_POOL_SHA256"] == 1
    assert result["SAME_CUTOFF"] == 1
    assert result["SAME_INCUMBENT_SELECTION"] == 1
    assert result["COMPARABLE"] is True


def test_crosscheck_flags_a_different_pool(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(replay_document()))
    replay = load_replay_crosscheck(path)
    drifted = SelectionPair(
        target_draw="105",
        target_date="2024-01-06",
        cutoff_draw="104",
        history_count=5,
        pool_sha256="other",
        distinct_pool_size=22,
        k=2,
        incumbent=(A, B),
        candidate=(A, C),
    )
    result = crosscheck([drifted], replay)
    assert result["SAME_POOL_SHA256"] == 0
    assert result["COMPARABLE"] is False


def test_digest_matches_the_operational_replay_encoding() -> None:
    # Byte-identical canonical JSON, so pool hashes join across artifacts.
    assert digest([("a", ((1, 2),))]) == module.hashlib.sha256(b'[["a",[[1,2]]]]\n').hexdigest()
