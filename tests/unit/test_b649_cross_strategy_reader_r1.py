from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import pytest

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.research import (
    ResearchExecutionStatus,
    ResearchRunKind,
)
from lottolab.infrastructure.persistence.research_repository import (
    B649CandidateCursor,
    B649CandidatePage,
    B649CrossStrategyCandidateRow,
    B649OutcomeCursor,
    B649OutcomeDrawBinding,
    B649OutcomePage,
    B649TargetOutcomeRow,
    ClosureInput,
    DrawBindingInput,
    ResearchConflictError,
    ResearchRepositoryError,
    SQLiteResearchRepository,
    StrategySnapshotInput,
    TargetCommitInput,
    TicketInput,
    TicketResultInput,
    fetch_b649_cross_strategy_candidate_rows,
    fetch_b649_target_outcome_rows,
    fetch_historical_replay_discovery_corpus_rows,
)
from lottolab.infrastructure.persistence.research_schema import (
    RESEARCH_DATABASE_FILENAME,
    V2_TABLE_NAMES,
    ResearchDataPaths,
    open_database,
)


def _paths(tmp_path: Path) -> ResearchDataPaths:
    directory = tmp_path.resolve() / "research-data"
    return ResearchDataPaths(directory, directory / RESEARCH_DATABASE_FILENAME)


def _digest(char: str) -> str:
    return char * 64


def _draw(
    draw_number: str,
    draw_date: str,
    *,
    digest_char: str,
    main_numbers_json: str = "[1,2,3,4,5,6]",
    special_numbers_json: str = "[7]",
    draw_data_version: str = "draw-v1",
    draw_sha256: str | None = None,
) -> DrawBindingInput:
    return DrawBindingInput(
        lottery_type="BIG_LOTTO",
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers_json=main_numbers_json,
        special_numbers_json=special_numbers_json,
        draw_sha256=draw_sha256 or _digest(digest_char),
        draw_data_version=draw_data_version,
    )


def _tickets(count: int = 3, *, offset: int = 0) -> tuple[TicketInput, ...]:
    values: list[TicketInput] = []
    for position in range(1, count + 1):
        num = position + offset
        main = [1, 2, 3, 4, 5, (num % 44) + 6]
        canonical = (
            f'{{"main_numbers":[{",".join(str(v) for v in main)}],'
            f'"special_numbers":[7]}}'
        )
        values.append(
            TicketInput(
                native_position=position,
                ordered_portfolio_position=position,
                canonical_ticket_json=canonical,
            )
        )
    return tuple(values)


def _bootstrap_run_and_strategy(
    repository: SQLiteResearchRepository,
    *,
    suffix: str,
    strategy_id: str,
    strategy_version: str = "1",
    replicate: int = 1,
    expected_target_count: int = 2,
) -> tuple[str, str]:
    contract_id = repository.register_rule_contract(
        BIG_LOTTO_RULE_CONTRACT,
        idempotency_key=f"{suffix}-rule",
    )
    run_id = repository.create_run(
        run_kind=ResearchRunKind.HISTORICAL_BACKTEST,
        rule_contract_id=contract_id,
        input_dataset_identity=f"dataset-{suffix}",
        input_dataset_sha256=_digest("a"),
        expected_target_count=expected_target_count,
        producer_identity="pytest",
        execution_code_version="test-v1",
        source_commit_oid="9b0dc98",
        idempotency_key=f"{suffix}-run",
    )
    snapshot_id = repository.register_strategy_snapshot(
        run_id,
        StrategySnapshotInput(
            lottery_type="BIG_LOTTO",
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            source_commit_oid="9b0dc98",
            strategy_source_sha256=_digest("b"),
            producer_identity="pytest",
            producer_version="1",
            runtime_fingerprint="python-test",
            parameters_json="{}",
            seed_protocol="DETERMINISTIC",
            replicate=replicate,
            execution_code_version="test-v1",
            governance_status="CANDIDATE",
            lifecycle_status="RESEARCH",
        ),
        idempotency_key=f"{suffix}-strategy",
    )
    return run_id, snapshot_id


def _make_target(
    run_id: str,
    strategy_id: str,
    *,
    target_order: int = 0,
    target_draw: DrawBindingInput,
    history_cutoff: DrawBindingInput,
    input_dataset_identity: str = "dataset",
    history_draw_count: int = 1,
    causal_eligible: bool = True,
    execution_status: ResearchExecutionStatus = ResearchExecutionStatus.OK,
    tickets: tuple[TicketInput, ...] = (),
    closure: ClosureInput | None = None,
) -> TargetCommitInput:
    return TargetCommitInput(
        run_id=run_id,
        strategy_snapshot_id=strategy_id,
        target_order=target_order,
        input_dataset_identity=input_dataset_identity,
        input_dataset_sha256=_digest("a"),
        history_cutoff=history_cutoff,
        history_draw_count=history_draw_count,
        source_history_order="DRAW_DATE_ASC,DRAW_NUMBER_ASC",
        target_draw=target_draw,
        causal_eligible=causal_eligible,
        candidate_k=12,
        combination_count=924,
        ticket_count_prefix=5,
        tickets=tickets,
        execution_status=execution_status,
        closure=closure,
    )


def test_01_single_run_valid_tickets_readable(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t01", strategy_id="strat-alpha"
    )

    cutoff_draw = _draw("0001", "2026-01-01", digest_char="1")
    target_draw = _draw("0002", "2026-01-08", digest_char="2")

    target_input = _make_target(
        run_id,
        strategy_id,
        target_order=0,
        history_cutoff=cutoff_draw,
        target_draw=target_draw,
        tickets=_tickets(count=3),
    )
    repository.commit_target(target_input, idempotency_key="t01-commit")

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_cross_strategy_candidate_rows(conn)

    assert isinstance(page, B649CandidatePage)
    assert len(page.items) == 3
    assert page.next_cursor is None

    for idx, row in enumerate(page.items, start=1):
        assert isinstance(row, B649CrossStrategyCandidateRow)
        assert row.run_id == run_id
        assert row.target_id
        assert row.input_dataset_identity == "dataset"
        assert row.input_dataset_sha256 == _digest("a")
        assert row.strategy_id == "strat-alpha"
        assert row.strategy_version == "1"
        assert row.replicate == 1
        assert row.target_draw_number == "0002"
        assert row.target_draw_date == "2026-01-08"
        assert row.history_cutoff_draw_number == "0001"
        assert row.history_cutoff_draw_date == "2026-01-01"
        assert row.target_draw_binding_id.startswith("draw-")
        assert row.target_draw_data_version == "draw-v1"
        assert row.target_draw_sha256 == _digest("2")
        assert row.history_cutoff_draw_binding_id.startswith("draw-")
        assert row.history_cutoff_draw_data_version == "draw-v1"
        assert row.history_cutoff_draw_sha256 == _digest("1")
        assert row.native_position == idx
        assert row.ordered_portfolio_position == idx
        assert row.execution_status == "OK"
        assert row.causal_eligible == 1
        assert len(row.main_numbers) == 6


def test_02_cross_run_cross_strategy_merge_on_same_target(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)

    run_a, strat_a = _bootstrap_run_and_strategy(
        repository, suffix="t02a", strategy_id="strategy-A"
    )
    run_b, strat_b = _bootstrap_run_and_strategy(
        repository, suffix="t02b", strategy_id="strategy-B"
    )

    cutoff_draw = _draw("0001", "2026-01-01", digest_char="1")
    target_draw = _draw("0002", "2026-01-08", digest_char="2")

    target_a = _make_target(
        run_a,
        strat_a,
        target_order=0,
        history_cutoff=cutoff_draw,
        target_draw=target_draw,
        tickets=_tickets(count=2, offset=0),
    )
    repository.commit_target(target_a, idempotency_key="t02a-commit")

    target_b = _make_target(
        run_b,
        strat_b,
        target_order=0,
        history_cutoff=cutoff_draw,
        target_draw=target_draw,
        tickets=_tickets(count=3, offset=10),
    )
    repository.commit_target(target_b, idempotency_key="t02b-commit")

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_cross_strategy_candidate_rows(conn)

    assert len(page.items) == 5
    strats = [r.strategy_id for r in page.items]
    assert strats.count("strategy-A") == 2
    assert strats.count("strategy-B") == 3
    assert all(r.target_draw_number == "0002" for r in page.items)


def test_03_partial_target_presence_not_lost(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)

    run_a, strat_a = _bootstrap_run_and_strategy(
        repository, suffix="t03a", strategy_id="strat-omnipresent"
    )
    run_b, strat_b = _bootstrap_run_and_strategy(
        repository, suffix="t03b", strategy_id="strat-partial"
    )

    draw_1 = _draw("0001", "2026-01-01", digest_char="1")
    draw_2 = _draw("0002", "2026-01-08", digest_char="2")
    draw_3 = _draw("0003", "2026-01-15", digest_char="3")

    repository.commit_target(
        _make_target(
            run_a,
            strat_a,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=2),
        ),
        idempotency_key="t03a-target2",
    )
    repository.commit_target(
        _make_target(
            run_a,
            strat_a,
            target_order=1,
            history_cutoff=draw_2,
            target_draw=draw_3,
            tickets=_tickets(count=2),
        ),
        idempotency_key="t03a-target3",
    )

    repository.commit_target(
        _make_target(
            run_b,
            strat_b,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=3),
        ),
        idempotency_key="t03b-target2",
    )

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_cross_strategy_candidate_rows(conn)

    targets_present = {r.target_draw_number for r in page.items}
    assert targets_present == {"0002", "0003"}
    draw_3_items = [r for r in page.items if r.target_draw_number == "0003"]
    assert len(draw_3_items) == 2
    assert all(r.strategy_id == "strat-omnipresent" for r in draw_3_items)


@pytest.mark.parametrize("conflict", ["date", "main", "special"])
def test_04_conflicting_canonical_draw_outcome_rejected(
    tmp_path: Path, conflict: str
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)

    run_a, strat_a = _bootstrap_run_and_strategy(
        repository, suffix="t04a", strategy_id="strat-A"
    )
    run_b, strat_b = _bootstrap_run_and_strategy(
        repository, suffix="t04b", strategy_id="strat-B"
    )

    cutoff_draw = _draw("0001", "2026-01-01", digest_char="1")
    target_draw_a = _draw("0002", "2026-01-08", digest_char="2")
    if conflict == "date":
        target_draw_b = _draw(
            "0002",
            "2026-01-09",
            digest_char="9",
            draw_data_version="draw-v2-conflicted",
        )
    elif conflict == "main":
        target_draw_b = _draw(
            "0002",
            "2026-01-08",
            digest_char="9",
            main_numbers_json="[1,2,3,4,5,8]",
            draw_data_version="draw-v2-conflicted",
        )
    else:
        target_draw_b = _draw(
            "0002",
            "2026-01-08",
            digest_char="9",
            special_numbers_json="[8]",
            draw_data_version="draw-v2-conflicted",
        )

    repository.commit_target(
        _make_target(
            run_a,
            strat_a,
            target_order=0,
            history_cutoff=cutoff_draw,
            target_draw=target_draw_a,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t04a-target",
    )

    repository.commit_target(
        _make_target(
            run_b,
            strat_b,
            target_order=0,
            history_cutoff=cutoff_draw,
            target_draw=target_draw_b,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t04b-target",
    )

    with open_database(paths, read_only=True) as conn:
        with pytest.raises(ResearchConflictError, match="conflicting target draw outcome"):
            fetch_b649_cross_strategy_candidate_rows(conn)

        with pytest.raises(ResearchConflictError, match="conflicting draw outcome"):
            fetch_b649_target_outcome_rows(conn)


def test_05_cutoff_not_strictly_earlier_excluded(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t05", strategy_id="strat-cutoff"
    )

    draw_1 = _draw("0001", "2026-01-01", digest_char="1")
    draw_2 = _draw("0002", "2026-01-08", digest_char="2")

    # Valid target: cutoff 0001 < target 0002
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=2),
        ),
        idempotency_key="t05-valid",
    )

    # Cutoff draw number >= target draw number
    # (draw 0005 date 2026-01-02, target 0003 date 2026-01-10)
    draw_5 = _draw("0005", "2026-01-02", digest_char="5")
    draw_3 = _draw("0003", "2026-01-10", digest_char="3")

    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=1,
            history_cutoff=draw_5,
            target_draw=draw_3,
            tickets=_tickets(count=2),
        ),
        idempotency_key="t05-invalid-cutoff-order",
    )

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_cross_strategy_candidate_rows(conn)

    assert all(r.target_draw_number == "0002" for r in page.items)
    assert len(page.items) == 2


def test_06_non_ok_status_and_ineligible_excluded(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t06", strategy_id="strat-status"
    )

    draw_1 = _draw("0001", "2026-01-01", digest_char="1")
    draw_2 = _draw("0002", "2026-01-08", digest_char="2")
    draw_3 = _draw("0003", "2026-01-15", digest_char="3")
    draw_4 = _draw("0004", "2026-01-22", digest_char="4")

    # Valid target
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            causal_eligible=True,
            execution_status=ResearchExecutionStatus.OK,
            tickets=_tickets(count=2),
        ),
        idempotency_key="t06-ok",
    )

    # Ineligible (causal_eligible = False)
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=1,
            history_cutoff=draw_2,
            target_draw=draw_3,
            causal_eligible=False,
            execution_status=ResearchExecutionStatus.OK,
            tickets=_tickets(count=2),
        ),
        idempotency_key="t06-ineligible",
    )

    # Non-OK status (INSUFFICIENT_HISTORY)
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=2,
            history_cutoff=draw_3,
            target_draw=draw_4,
            causal_eligible=True,
            execution_status=ResearchExecutionStatus.INSUFFICIENT_HISTORY,
            closure=ClosureInput(
                closure_type=ResearchExecutionStatus.INSUFFICIENT_HISTORY,
                reason_code="MIN_HISTORY_50",
            ),
            tickets=_tickets(count=0),
        ),
        idempotency_key="t06-insufficient",
    )

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_cross_strategy_candidate_rows(conn)

    assert len(page.items) == 2
    assert all(r.target_draw_number == "0002" for r in page.items)


def test_07_deterministic_ordering_and_provenance(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)

    run_1, strat_1 = _bootstrap_run_and_strategy(
        repository, suffix="t07a", strategy_id="strat-Z", replicate=2
    )
    run_2, strat_2 = _bootstrap_run_and_strategy(
        repository, suffix="t07b", strategy_id="strat-A", replicate=1
    )

    draw_1 = _draw("0001", "2026-01-01", digest_char="1")
    draw_2 = _draw("0002", "2026-01-08", digest_char="2")

    repository.commit_target(
        _make_target(
            run_1,
            strat_1,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=3),
        ),
        idempotency_key="t07a-target",
    )
    repository.commit_target(
        _make_target(
            run_2,
            strat_2,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=3),
        ),
        idempotency_key="t07b-target",
    )

    with open_database(paths, read_only=True) as conn:
        page1 = fetch_b649_cross_strategy_candidate_rows(conn)
        page2 = fetch_b649_cross_strategy_candidate_rows(conn)

    assert len(page1.items) == 6
    assert page1.items == page2.items

    assert page1.items[0].strategy_id == "strat-A"
    assert page1.items[0].native_position == 1
    assert page1.items[1].strategy_id == "strat-A"
    assert page1.items[1].native_position == 2
    assert page1.items[2].strategy_id == "strat-A"
    assert page1.items[2].native_position == 3

    assert page1.items[3].strategy_id == "strat-Z"
    assert page1.items[3].replicate == 2
    assert page1.items[3].native_position == 1


def test_08_identical_ticket_across_strategies_retains_provenance(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)

    run_a, strat_a = _bootstrap_run_and_strategy(
        repository, suffix="t08a", strategy_id="strat-alpha"
    )
    run_b, strat_b = _bootstrap_run_and_strategy(
        repository, suffix="t08b", strategy_id="strat-beta"
    )

    draw_1 = _draw("0001", "2026-01-01", digest_char="1")
    draw_2 = _draw("0002", "2026-01-08", digest_char="2")

    identical_ticket = TicketInput(
        native_position=1,
        ordered_portfolio_position=1,
        canonical_ticket_json='{"main_numbers":[1,2,3,4,5,6],"special_numbers":[7]}',
    )

    repository.commit_target(
        _make_target(
            run_a,
            strat_a,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=(identical_ticket,),
        ),
        idempotency_key="t08a-target",
    )
    repository.commit_target(
        _make_target(
            run_b,
            strat_b,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=(identical_ticket,),
        ),
        idempotency_key="t08b-target",
    )

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_cross_strategy_candidate_rows(conn)

    assert len(page.items) == 2
    assert page.items[0].strategy_id == "strat-alpha"
    assert page.items[1].strategy_id == "strat-beta"
    assert page.items[0].ticket_sha256 == page.items[1].ticket_sha256
    assert page.items[0].main_numbers == page.items[1].main_numbers == (1, 2, 3, 4, 5, 6)


def test_09_outcome_reader_valid_main_and_special_numbers(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t09", strategy_id="strat-outcome"
    )

    draw_1 = _draw(
        "0001",
        "2026-01-01",
        digest_char="1",
        main_numbers_json="[1,2,3,4,5,6]",
        special_numbers_json="[7]",
    )
    draw_2 = _draw(
        "0002",
        "2026-01-08",
        digest_char="2",
        main_numbers_json="[6,12,18,24,30,36]",
        special_numbers_json="[42]",
    )

    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t09-target",
    )

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_target_outcome_rows(conn)

    assert isinstance(page, B649OutcomePage)
    assert len(page.items) == 2
    outcome_2 = next(r for r in page.items if r.target_draw_number == "0002")
    assert isinstance(outcome_2, B649TargetOutcomeRow)
    assert outcome_2.target_draw_number == "0002"
    assert outcome_2.target_draw_date == "2026-01-08"
    assert outcome_2.winning_main_numbers == (6, 12, 18, 24, 30, 36)
    assert outcome_2.winning_special_number == 42
    assert outcome_2.target_draw_sha256 == _digest("2")


def test_10_invalid_or_conflicting_special_numbers_rejected(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t10", strategy_id="strat-invalid-outcome"
    )

    cutoff = _draw("0001", "2026-01-01", digest_char="1")

    # 10a: empty special numbers
    draw_empty_sp = _draw(
        "0002",
        "2026-01-08",
        digest_char="2",
        special_numbers_json="[]",
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=0,
            history_cutoff=cutoff,
            target_draw=draw_empty_sp,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t10-empty",
    )
    with (
        open_database(paths, read_only=True) as conn,
        pytest.raises(ResearchRepositoryError, match="exactly one integer"),
    ):
        fetch_b649_target_outcome_rows(conn, target_draw_numbers=["0002"])

    # 10b: multiple special numbers
    draw_multi_sp = _draw(
        "0003",
        "2026-01-15",
        digest_char="3",
        special_numbers_json="[7,8]",
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=1,
            history_cutoff=cutoff,
            target_draw=draw_multi_sp,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t10-multi",
    )
    with (
        open_database(paths, read_only=True) as conn,
        pytest.raises(ResearchRepositoryError, match="exactly one integer"),
    ):
        fetch_b649_target_outcome_rows(conn, target_draw_numbers=["0003"])

    # 10c: special number out of range (50)
    draw_out_of_range = _draw(
        "0004",
        "2026-01-22",
        digest_char="4",
        special_numbers_json="[50]",
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=2,
            history_cutoff=cutoff,
            target_draw=draw_out_of_range,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t10-range",
    )
    with (
        open_database(paths, read_only=True) as conn,
        pytest.raises(ResearchRepositoryError, match=r"in range 1\.\.49"),
    ):
        fetch_b649_target_outcome_rows(conn, target_draw_numbers=["0004"])

    # 10d: special number conflicts with main numbers (special 6 in main [1,2,3,4,5,6])
    draw_conflict_sp = _draw(
        "0005",
        "2026-01-29",
        digest_char="5",
        main_numbers_json="[1,2,3,4,5,6]",
        special_numbers_json="[6]",
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=3,
            history_cutoff=cutoff,
            target_draw=draw_conflict_sp,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t10-conflict",
    )
    with (
        open_database(paths, read_only=True) as conn,
        pytest.raises(ResearchRepositoryError, match="conflicts with main numbers"),
    ):
        fetch_b649_target_outcome_rows(conn, target_draw_numbers=["0005"])


@pytest.mark.parametrize(
    ("special_numbers_json", "error_pattern"),
    [
        ("{}", "must be a JSON array"),
        ("[7.0]", "items must be integers"),
    ],
)
def test_10e_malformed_special_number_shapes_rejected(
    tmp_path: Path, special_numbers_json: str, error_pattern: str
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t10e", strategy_id="strat-malformed-special"
    )
    cutoff = _draw("0001", "2026-01-01", digest_char="1")
    target = _draw(
        "0002",
        "2026-01-08",
        digest_char="2",
        special_numbers_json=special_numbers_json,
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            history_cutoff=cutoff,
            target_draw=target,
            tickets=(),
        ),
        idempotency_key="t10e-target",
    )

    with (
        open_database(paths, read_only=True) as conn,
        pytest.raises(ResearchRepositoryError, match=error_pattern),
    ):
        fetch_b649_target_outcome_rows(conn, target_draw_numbers=["0002"])


@pytest.mark.parametrize(
    ("main_numbers_json", "error_pattern"),
    [
        ("[1,2,3,4,5]", "must decode to 6 integers"),
        ("[1,2,3,4,5,5]", "must contain 6 unique integers"),
        ("[1,2,3,4,5,50]", r"in range 1\.\.49"),
    ],
)
def test_10f_invalid_main_number_shapes_rejected(
    tmp_path: Path, main_numbers_json: str, error_pattern: str
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t10f", strategy_id="strat-invalid-main"
    )
    cutoff = _draw("0001", "2026-01-01", digest_char="1")
    target = _draw(
        "0002",
        "2026-01-08",
        digest_char="2",
        main_numbers_json=main_numbers_json,
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            history_cutoff=cutoff,
            target_draw=target,
            tickets=(),
        ),
        idempotency_key="t10f-target",
    )

    with (
        open_database(paths, read_only=True) as conn,
        pytest.raises(ResearchRepositoryError, match=error_pattern),
    ):
        fetch_b649_target_outcome_rows(conn, target_draw_numbers=["0002"])


def test_11_candidate_reader_does_not_expose_post_draw_outcomes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t11", strategy_id="strat-isolation"
    )

    cutoff = _draw("0001", "2026-01-01", digest_char="1")
    target = _draw("0002", "2026-01-08", digest_char="2")

    target_res = repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=0,
            history_cutoff=cutoff,
            target_draw=target,
            tickets=_tickets(count=2),
        ),
        idempotency_key="t11-target",
    )

    # Commit post-draw results
    repository.commit_ticket_results(
        target_res.target_id,
        target,
        [
            TicketResultInput(
                ticket_native_position=1,
                ticket_count_prefix=5,
                main_hit_count=6,
                special_hit_count=0,
                prize_tier_id="TIER_1",
            ),
            TicketResultInput(
                ticket_native_position=2,
                ticket_count_prefix=5,
                main_hit_count=0,
                special_hit_count=0,
                prize_tier_id=None,
            ),
        ],
        idempotency_key="t11-results",
    )

    with open_database(paths, read_only=True) as conn:
        page = fetch_b649_cross_strategy_candidate_rows(conn)

    assert len(page.items) == 2
    for candidate in page.items:
        assert not hasattr(candidate, "main_hit_count")
        assert not hasattr(candidate, "special_hit_count")
        assert not hasattr(candidate, "prize_tier_id")
        assert not hasattr(candidate, "hit_numbers_json")
        assert not hasattr(candidate, "result_sha256")
        assert not hasattr(candidate, "rank")


def test_12_read_only_connection_no_writes_permitted(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t12", strategy_id="strat-readonly"
    )

    cutoff = _draw("0001", "2026-01-01", digest_char="1")
    target = _draw("0002", "2026-01-08", digest_char="2")

    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=0,
            history_cutoff=cutoff,
            target_draw=target,
            tickets=_tickets(count=3),
        ),
        idempotency_key="t12-target",
    )

    def get_store_signature() -> tuple[dict[str, int], int, tuple[tuple[object, ...], ...]]:
        with open_database(paths, read_only=True) as c:
            row_counts = {
                table: cast(int, c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in V2_TABLE_NAMES
            }
            user_version = int(c.execute("PRAGMA user_version").fetchone()[0])
            schema_rows = tuple(
                tuple(row)
                for row in c.execute(
                    "SELECT type, name, sql FROM sqlite_master "
                    "WHERE type IN ('table', 'index', 'trigger', 'view') "
                    "ORDER BY type, name"
                ).fetchall()
            )
            return row_counts, user_version, schema_rows

    store_before = get_store_signature()

    with open_database(paths, read_only=True) as conn:
        assert int(conn.execute("PRAGMA query_only").fetchone()[0]) == 1
        cand_page = fetch_b649_cross_strategy_candidate_rows(conn)
        assert len(cand_page.items) == 3
        out_page = fetch_b649_target_outcome_rows(conn)
        assert len(out_page.items) == 2

        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO research_runs (id) VALUES ('fail')")

    store_after = get_store_signature()
    assert store_before == store_after


def test_13_pagination_across_target_boundaries_no_leak_or_loss(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strategy_id = _bootstrap_run_and_strategy(
        repository, suffix="t13", strategy_id="strat-paging"
    )

    cutoff = _draw("0001", "2026-01-01", digest_char="1")
    draw_2 = _draw("0002", "2026-01-08", digest_char="2")
    draw_3 = _draw("0003", "2026-01-15", digest_char="3")
    draw_4 = _draw("0004", "2026-01-22", digest_char="4")

    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=0,
            history_cutoff=cutoff,
            target_draw=draw_2,
            tickets=_tickets(count=4, offset=0),
        ),
        idempotency_key="t13-target2",
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=1,
            history_cutoff=draw_2,
            target_draw=draw_3,
            tickets=_tickets(count=4, offset=10),
        ),
        idempotency_key="t13-target3",
    )
    repository.commit_target(
        _make_target(
            run_id,
            strategy_id,
            target_order=2,
            history_cutoff=draw_3,
            target_draw=draw_4,
            tickets=_tickets(count=4, offset=20),
        ),
        idempotency_key="t13-target4",
    )
    alternate_run_id, alternate_strategy_id = _bootstrap_run_and_strategy(
        repository,
        suffix="t13-alt",
        strategy_id="strat-paging-alt",
        expected_target_count=1,
    )
    alternate_draw_2 = _draw(
        "0002",
        "2026-01-08",
        digest_char="9",
        draw_data_version="draw-v2-equivalent",
    )
    repository.commit_target(
        _make_target(
            alternate_run_id,
            alternate_strategy_id,
            target_order=0,
            history_cutoff=cutoff,
            target_draw=alternate_draw_2,
            tickets=_tickets(count=1, offset=30),
        ),
        idempotency_key="t13-equivalent-target2",
    )

    with open_database(paths, read_only=True) as conn:
        all_candidates = fetch_b649_cross_strategy_candidate_rows(conn).items
        assert len(all_candidates) == 13

        collected: list[B649CrossStrategyCandidateRow] = []
        cursor: B649CandidateCursor | None = None
        pages_count = 0

        while True:
            pages_count += 1
            page = fetch_b649_cross_strategy_candidate_rows(conn, limit=5, after=cursor)
            collected.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                break

    assert pages_count == 3  # 5 + 5 + 3 = 13 items
    assert len(collected) == 13
    assert collected == list(all_candidates)

    identities = [
        (r.run_id, r.strategy_snapshot_id, r.target_draw_number, r.native_position)
        for r in collected
    ]
    assert len(set(identities)) == 13
    assert [r.native_position for r in collected if r.run_id == run_id] == [
        1,
        2,
        3,
        4,
    ] * 3

    with open_database(paths, read_only=True) as conn:
        out_page1 = fetch_b649_target_outcome_rows(conn, limit=2)
        assert len(out_page1.items) == 2
        assert isinstance(out_page1.next_cursor, B649OutcomeCursor)
        out_page2 = fetch_b649_target_outcome_rows(
            conn, limit=2, after=out_page1.next_cursor
        )
        assert len(out_page2.items) == 2
        assert out_page2.next_cursor is None
        assert [r.target_draw_number for r in out_page1.items] == ["0001", "0002"]
        assert [r.target_draw_number for r in out_page2.items] == ["0003", "0004"]
        equivalent_outcome = next(
            row for row in out_page1.items if row.target_draw_number == "0002"
        )
        assert len(equivalent_outcome.source_bindings) == 2
        assert set(equivalent_outcome.source_draw_sha256s) == {
            _digest("2"),
            _digest("9"),
        }


def test_14_legacy_discovery_reader_contract_unchanged(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_id, strat_1 = _bootstrap_run_and_strategy(
        repository, suffix="t14a", strategy_id="strat-1"
    )
    strat_2 = repository.register_strategy_snapshot(
        run_id,
        StrategySnapshotInput(
            lottery_type="BIG_LOTTO",
            strategy_id="strat-2",
            strategy_version="1",
            source_commit_oid="9b0dc98",
            strategy_source_sha256=_digest("b"),
            producer_identity="pytest",
            producer_version="1",
            runtime_fingerprint="python-test",
            parameters_json="{}",
            seed_protocol="DETERMINISTIC",
            replicate=1,
            execution_code_version="test-v1",
            governance_status="CANDIDATE",
            lifecycle_status="RESEARCH",
        ),
        idempotency_key="t14-strat2",
    )

    draw_1 = _draw("0001", "2026-01-01", digest_char="1")
    draw_2 = _draw("0002", "2026-01-08", digest_char="2")

    t1_res = repository.commit_target(
        _make_target(
            run_id,
            strat_1,
            target_order=0,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t14-t1",
    )
    t2_res = repository.commit_target(
        _make_target(
            run_id,
            strat_2,
            target_order=1,
            history_cutoff=draw_1,
            target_draw=draw_2,
            tickets=_tickets(count=1),
        ),
        idempotency_key="t14-t2",
    )

    repository.commit_ticket_results(
        t1_res.target_id,
        draw_2,
        [
            TicketResultInput(
                ticket_native_position=1,
                ticket_count_prefix=5,
                main_hit_count=6,
                special_hit_count=0,
                prize_tier_id="TIER_1",
            )
        ],
        idempotency_key="t14-res1",
    )
    repository.commit_ticket_results(
        t2_res.target_id,
        draw_2,
        [
            TicketResultInput(
                ticket_native_position=1,
                ticket_count_prefix=5,
                main_hit_count=6,
                special_hit_count=0,
                prize_tier_id="TIER_1",
            )
        ],
        idempotency_key="t14-res2",
    )

    with open_database(paths, read_only=True) as conn:
        conn.row_factory = sqlite3.Row
        discovery_rows = fetch_historical_replay_discovery_corpus_rows(
            conn,
            source_run_id=run_id,
            last_target_draw_date="2026-01-08",
            last_target_draw_number=2,
        )

    assert discovery_rows.source_metadata is not None
    assert len(discovery_rows.strategy_rows) == 2
    assert len(discovery_rows.common_rows) == 2


def test_15_conflicting_target_cutoff_outcomes_still_rejected(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_a, strat_a = _bootstrap_run_and_strategy(
        repository, suffix="t15a", strategy_id="strat-cutoff-a", expected_target_count=1
    )
    run_b, strat_b = _bootstrap_run_and_strategy(
        repository, suffix="t15b", strategy_id="strat-cutoff-b", expected_target_count=1
    )

    cutoff_a = _draw("0001", "2026-01-01", digest_char="1")
    cutoff_b = _draw(
        "0001",
        "2026-01-01",
        digest_char="9",
        special_numbers_json="[8]",
        draw_data_version="draw-v2-conflicting-cutoff",
    )
    target = _draw("0003", "2026-01-15", digest_char="3")
    for run_id, strategy_id, cutoff, suffix in (
        (run_a, strat_a, cutoff_a, "a"),
        (run_b, strat_b, cutoff_b, "b"),
    ):
        repository.commit_target(
            _make_target(
                run_id,
                strategy_id,
                history_cutoff=cutoff,
                target_draw=target,
                tickets=_tickets(count=1),
            ),
            idempotency_key=f"t15-target-{suffix}",
        )

    with open_database(paths, read_only=True) as conn:
        with pytest.raises(
            ResearchConflictError, match="conflicting history cutoff draw outcome"
        ):
            fetch_b649_cross_strategy_candidate_rows(conn)
        with pytest.raises(ResearchConflictError, match="conflicting draw outcome"):
            fetch_b649_target_outcome_rows(conn, target_draw_numbers=["0001"])


def test_16_114000064_equivalent_source_bindings_are_preserved(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    run_a, strat_a = _bootstrap_run_and_strategy(
        repository,
        suffix="t16-r3",
        strategy_id="strat-r3",
        strategy_version="3",
        replicate=1,
        expected_target_count=1,
    )
    run_b, strat_b = _bootstrap_run_and_strategy(
        repository,
        suffix="t16-legacy",
        strategy_id="strat-legacy",
        strategy_version="legacy-1",
        replicate=2,
        expected_target_count=1,
    )

    cutoff = _draw(
        "114000063",
        "2025-06-17",
        digest_char="1",
        main_numbers_json="[1,2,3,4,5,6]",
        special_numbers_json="[7]",
        draw_data_version="shared-cutoff-v1",
    )
    source_a = _draw(
        "114000064",
        "2025-06-24",
        digest_char="2",
        main_numbers_json="[3,8,20,37,45,49]",
        special_numbers_json="[21]",
        draw_data_version="R3",
        draw_sha256="3274765b0dca3b575d633b3fb902d0bf77d853e102d33a7169883f724fe65d2e",
    )
    source_b = _draw(
        "114000064",
        "2025-06-24",
        digest_char="9",
        main_numbers_json="[49,45,37,20,8,3]",
        special_numbers_json="[21]",
        draw_data_version="LOTTOLAB_LEGACY_REFERENCE_CORPUS_V1",
        draw_sha256="5c2d0c1f25056883487359c21c9a1a87449d76ef63924c4ddee6fdcb72a09725",
    )

    repository.commit_target(
        _make_target(
            run_a,
            strat_a,
            history_cutoff=cutoff,
            target_draw=source_a,
            input_dataset_identity="dataset-t16-r3",
            tickets=_tickets(count=2),
        ),
        idempotency_key="t16-source-a",
    )
    with open_database(paths, read_only=True) as conn:
        candidates_before_b = fetch_b649_cross_strategy_candidate_rows(
            conn, target_draw_numbers=["114000064"]
        ).items

    repository.commit_target(
        _make_target(
            run_b,
            strat_b,
            history_cutoff=cutoff,
            target_draw=source_b,
            input_dataset_identity="dataset-t16-legacy",
            tickets=_tickets(count=2, offset=10),
        ),
        idempotency_key="t16-source-b",
    )

    with open_database(paths, read_only=True) as conn:
        candidate_page = fetch_b649_cross_strategy_candidate_rows(
            conn, target_draw_numbers=["114000064"]
        )
        outcome_page = fetch_b649_target_outcome_rows(
            conn, target_draw_numbers=["114000064"]
        )
        cutoff_page = fetch_b649_target_outcome_rows(
            conn, target_draw_numbers=["114000063"]
        )

    assert len(candidates_before_b) == 2
    candidates_a_after_b = tuple(
        row for row in candidate_page.items if row.run_id == run_a
    )
    candidates_b = tuple(row for row in candidate_page.items if row.run_id == run_b)
    assert candidates_a_after_b == candidates_before_b
    assert [row.native_position for row in candidates_a_after_b] == [1, 2]
    assert [row.native_position for row in candidates_b] == [1, 2]
    assert {row.target_draw_sha256 for row in candidates_a_after_b} == {
        source_a.draw_sha256
    }
    assert {row.target_draw_sha256 for row in candidates_b} == {source_b.draw_sha256}
    assert {row.target_draw_data_version for row in candidates_a_after_b} == {"R3"}
    assert {
        row.target_draw_data_version for row in candidates_b
    } == {"LOTTOLAB_LEGACY_REFERENCE_CORPUS_V1"}
    assert {row.target_draw_binding_id for row in candidates_a_after_b} == {
        row.target_draw_binding_id for row in candidates_before_b
    }
    assert {row.input_dataset_identity for row in candidate_page.items} == {
        "dataset-t16-r3",
        "dataset-t16-legacy",
    }
    assert {row.input_dataset_sha256 for row in candidate_page.items} == {_digest("a")}
    assert all(row.target_id for row in candidate_page.items)
    assert len(
        {row.history_cutoff_draw_binding_id for row in candidate_page.items}
    ) == 1
    assert {
        row.history_cutoff_draw_data_version for row in candidate_page.items
    } == {"shared-cutoff-v1"}
    assert {row.history_cutoff_draw_sha256 for row in candidate_page.items} == {
        cutoff.draw_sha256
    }

    assert len(outcome_page.items) == 1
    outcome = outcome_page.items[0]
    assert outcome.target_draw_number == "114000064"
    assert outcome.target_draw_date == "2025-06-24"
    assert outcome.winning_main_numbers == (3, 8, 20, 37, 45, 49)
    assert outcome.winning_special_number == 21
    assert outcome.target_draw_sha256 is None
    assert set(outcome.source_draw_sha256s) == {source_a.draw_sha256, source_b.draw_sha256}
    assert len(outcome.source_bindings) == 2
    assert all(isinstance(binding, B649OutcomeDrawBinding) for binding in outcome.source_bindings)
    binding_identities = {
        (binding.binding_id, binding.draw_sha256, binding.draw_data_version)
        for binding in outcome.source_bindings
    }
    assert binding_identities == {
        (candidates_a_after_b[0].target_draw_binding_id, source_a.draw_sha256, "R3"),
        (
            candidates_b[0].target_draw_binding_id,
            source_b.draw_sha256,
            "LOTTOLAB_LEGACY_REFERENCE_CORPUS_V1",
        ),
    }
    source_provenance = {
        (
            provenance.run_id,
            provenance.strategy_id,
            provenance.strategy_version,
            provenance.replicate,
            provenance.input_dataset_identity,
        )
        for binding in outcome.source_bindings
        for provenance in binding.provenance
        if provenance.source_role == "TARGET"
    }
    assert source_provenance == {
        (run_a, "strat-r3", "3", 1, "dataset-t16-r3"),
        (run_b, "strat-legacy", "legacy-1", 2, "dataset-t16-legacy"),
    }
    assert len(cutoff_page.items) == 1
    assert len(cutoff_page.items[0].source_bindings) == 1
    cutoff_provenance = {
        provenance.run_id
        for binding in cutoff_page.items[0].source_bindings
        for provenance in binding.provenance
        if provenance.source_role == "HISTORY_CUTOFF"
    }
    assert cutoff_provenance == {run_a, run_b}
