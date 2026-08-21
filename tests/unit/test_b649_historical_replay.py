"""Focused acceptance tests for the Owner-authorized B649 replay core."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from gzip import open as gzip_open
from pathlib import Path

from lottolab.application.use_cases.b649_historical_replay import (
    B649HistoricalReplayRequest,
    B649HistoricalReplayUseCase,
    B649IdentityStatus,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    ReplayCellStatus,
    ReplayDraw,
    ReplaySourceSnapshot,
    ReplayStoredTarget,
    ReplayStoredTicket,
)
from lottolab.strategies.catalog import production_catalog

RAW_ONLY_ID = "legacy_biglotto__backtest_cluster_pivot_biglotto__b28957a6433e"
CURRENT_ID = "legacy_biglotto__graph_predictor__cd70713a5709"
KEEP_UNRESOLVED_ID = (
    "legacy_biglotto__big649_no_db_strategy_output_adapter__6da3a06f4377"
)
RAW_HISTORY_NOT_FOUND_IDS = frozenset(
    {
        "legacy_biglotto__backtest_biglotto_5bet_ts3markov__25760472baa0",
        "legacy_biglotto__predict_biglotto_triple_strike__236fe529c01f",
    }
)


def _draw(number: int, *, main_numbers: tuple[int, ...], special: int) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 100000001),
        main_numbers=main_numbers,
        special_number=special,
    )


def _source_root(tmp_path: Path) -> Path:
    root = tmp_path / "b649-foundation"
    (root / "raw_records").mkdir(parents=True)
    return root


def _write_identity_file_stems(root: Path) -> None:
    full_catalog = load_full_strategy_catalog()
    current_ids = {
        descriptor.strategy_id
        for descriptor in production_catalog().list(lottery_type=LotteryType.BIG_LOTTO)
        if any(
            provenance == f"full_strategy_catalog_id:{descriptor.strategy_id}"
            for provenance in descriptor.provenance
        )
    }
    for record in full_catalog.records:
        if (
            record.reproduction_status is ReproductionStatus.BACKTESTED
            and record.strategy_id not in current_ids
            and record.strategy_id not in RAW_HISTORY_NOT_FOUND_IDS
        ):
            (root / "raw_records" / f"{record.strategy_id}.jsonl.gz").touch()


def _write_raw_portfolio(root: Path, *, ticket_count: int = 25) -> None:
    record = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == RAW_ONLY_ID
    )
    history = _draw(100000001, main_numbers=(7, 8, 9, 10, 11, 12), special=13)
    target = _draw(100000002, main_numbers=(1, 2, 3, 4, 5, 6), special=7)
    path = root / "raw_records" / f"{RAW_ONLY_ID}.jsonl.gz"
    with gzip_open(path, "wt", encoding="utf-8") as handle:
        for position in range(1, ticket_count + 1):
            handle.write(
                json.dumps(
                    {
                        "actual_main_numbers": list(target.main_numbers),
                        "actual_special_number": target.special_number,
                        "canonical_strategy_id": RAW_ONLY_ID,
                        "historical_input_cutoff_date": history.draw_date.isoformat(),
                        "historical_input_cutoff_draw": history.draw_number,
                        "lottery_type": LotteryType.BIG_LOTTO.value,
                        "native_ticket_count": ticket_count,
                        "predicted_numbers": list(target.main_numbers),
                        "replay_status": "EXACT_PRESERVED_OUTPUT_RECOVERED",
                        "strategy_version": record.strategy_version,
                        "target_draw_date": target.draw_date.isoformat(),
                        "target_draw_number": target.draw_number,
                        "ticket_position": position,
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )


def test_b649_identity_accounting_covers_all_221_identities(tmp_path: Path) -> None:
    root = _source_root(tmp_path)
    _write_identity_file_stems(root)

    use_case = B649HistoricalReplayUseCase(root)
    counts = Counter(identity.status for identity in use_case.identity_accounts)

    assert len(use_case.identity_accounts) == 221
    assert counts == Counter(
        {
            # The reconciled preceding batch made 5 catalog identities among
            # these 221 executable; SELECTED_INTAKE_SET03_R1 added 2 more
            # (verify_markov_vs_triple_2bet, backtest_biglotto_coldpool_15).
            # Together they move 7 from HISTORICAL_RAW_ONLY to
            # CURRENTLY_REPLAYABLE: 52->59, 81->74.
            B649IdentityStatus.CURRENTLY_REPLAYABLE: 59,
            B649IdentityStatus.HISTORICAL_RAW_ONLY: 74,
            B649IdentityStatus.TERMINAL_UNAVAILABLE: 76,
            B649IdentityStatus.RESOLVED_ALIAS: 9,
            B649IdentityStatus.KEEP_UNRESOLVED_ALIAS: 3,
        }
    )


def test_b649_current_catalog_binding_reaches_controller_and_prize_evaluation(
    tmp_path: Path,
) -> None:
    use_case = B649HistoricalReplayUseCase(_source_root(tmp_path))
    history = _draw(100000001, main_numbers=(7, 8, 9, 10, 11, 12), special=13)
    target = _draw(100000002, main_numbers=(1, 2, 3, 4, 5, 6), special=7)
    request = B649HistoricalReplayRequest(
        source=ReplaySourceSnapshot(
            lottery_type=LotteryType.BIG_LOTTO,
            historical_draws=(history, target),
        ),
        mode=HistoricalReplayMode.FULL_REPLAY,
        strategy_id=CURRENT_ID,
        cutoff_draw_number=target.draw_number,
    )

    item = next(use_case.execute(request).iter_strategy_results())

    assert item.identity.status is B649IdentityStatus.CURRENTLY_REPLAYABLE
    assert item.blocked_reason is None
    assert item.replay is not None
    record = item.replay.records[-1]
    assert record.status is ReplayCellStatus.COMPLETE
    assert len(record.tickets) == 1
    assert len(record.evaluations) == 1
    assert record.causal_history == (history,)


def test_b649_raw_only_stream_preserves_every_position_and_causal_cutoff(
    tmp_path: Path,
) -> None:
    root = _source_root(tmp_path)
    _write_raw_portfolio(root, ticket_count=25)
    history = _draw(100000001, main_numbers=(7, 8, 9, 10, 11, 12), special=13)
    target = _draw(100000002, main_numbers=(1, 2, 3, 4, 5, 6), special=7)
    request = B649HistoricalReplayRequest(
        source=ReplaySourceSnapshot(
            lottery_type=LotteryType.BIG_LOTTO,
            historical_draws=(history, target),
        ),
        mode=HistoricalReplayMode.FULL_REPLAY,
        strategy_id=RAW_ONLY_ID,
        cutoff_draw_number=target.draw_number,
    )

    item = next(B649HistoricalReplayUseCase(root).execute(request).iter_strategy_results())

    assert item.identity.status is B649IdentityStatus.HISTORICAL_RAW_ONLY
    assert item.blocked_reason is None
    assert item.replay is not None
    record = item.replay.records[-1]
    assert record.status is ReplayCellStatus.COMPLETE
    assert record.causal_history == (history,)
    assert tuple(ticket.ticket_position for ticket in record.tickets) == tuple(range(1, 26))
    assert len(record.evaluations) == 25
    assert record.evaluations[0].is_winner is True
    assert record.evaluations[0].prize_tier == "FIRST"
    assert item.replay.typed_closure_count == 1
    assert item.replay.failed_count == 0


def test_b649_raw_only_reconcile_uses_target_specific_native_count(tmp_path: Path) -> None:
    root = _source_root(tmp_path)
    _write_raw_portfolio(root, ticket_count=25)
    history = _draw(100000001, main_numbers=(7, 8, 9, 10, 11, 12), special=13)
    target = _draw(100000002, main_numbers=(1, 2, 3, 4, 5, 6), special=7)
    record = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == RAW_ONLY_ID
    )
    stored_target = ReplayStoredTarget(
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
        strategy_id=RAW_ONLY_ID,
        strategy_version=record.strategy_version,
        expected_ticket_count=25,
        status=ReplayCellStatus.COMPLETE,
        strategy_fingerprint=record.source_sha256,
    )
    stored_tickets = tuple(
        ReplayStoredTicket(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number=target.draw_number,
            strategy_id=RAW_ONLY_ID,
            strategy_version=record.strategy_version,
            ticket_position=position,
            main_numbers=target.main_numbers,
        )
        for position in range(1, 26)
    )
    request = B649HistoricalReplayRequest(
        source=ReplaySourceSnapshot(
            lottery_type=LotteryType.BIG_LOTTO,
            historical_draws=(history, target),
            stored_targets=(stored_target,),
            stored_tickets=stored_tickets,
        ),
        mode=HistoricalReplayMode.RECONCILE,
        strategy_id=RAW_ONLY_ID,
        cutoff_draw_number=target.draw_number,
    )

    item = next(B649HistoricalReplayUseCase(root).execute(request).iter_strategy_results())

    assert item.replay is not None
    assert item.replay.deterministic_mismatch_count == 0
    assert item.replay.native_ticket_count == 25
    assert item.replay.expected_native_ticket_count == 26
    assert item.replay.partial_count == 0
    assert item.replay.missing_count == 1


def test_b649_alias_and_terminal_identities_are_not_fabricated(tmp_path: Path) -> None:
    use_case = B649HistoricalReplayUseCase(_source_root(tmp_path))
    source = ReplaySourceSnapshot(lottery_type=LotteryType.BIG_LOTTO, historical_draws=())

    alias_item = next(
        use_case.execute(
            B649HistoricalReplayRequest(source=source, strategy_id=KEEP_UNRESOLVED_ID)
        ).iter_strategy_results()
    )
    terminal_id = next(
        identity.strategy_id
        for identity in use_case.identity_accounts
        if identity.status is B649IdentityStatus.TERMINAL_UNAVAILABLE
    )
    terminal_item = next(
        use_case.execute(
            B649HistoricalReplayRequest(source=source, strategy_id=terminal_id)
        ).iter_strategy_results()
    )

    assert alias_item.identity.status is B649IdentityStatus.KEEP_UNRESOLVED_ALIAS
    assert alias_item.replay is None
    assert alias_item.blocked_reason is not None
    assert alias_item.blocked_reason.startswith("OWNER_KEEP_UNRESOLVED:")
    assert terminal_item.identity.status is B649IdentityStatus.TERMINAL_UNAVAILABLE
    assert terminal_item.replay is None
    assert terminal_item.blocked_reason is not None
