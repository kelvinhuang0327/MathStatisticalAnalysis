from __future__ import annotations

import dataclasses
import threading
from pathlib import Path

import pytest
from tests.fixtures.legacy_reference_corpus import build_legacy_reference_corpus

from lottolab.application.legacy_reference_import import (
    BigLottoLegacyReferenceImporter,
    prepare_legacy_corpus,
)
from lottolab.application.research_store import TicketInput
from lottolab.domain.research import ResearchRunStatus
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    RESEARCH_DATABASE_FILENAME,
    ResearchDataPaths,
    open_database,
)


def test_resume_idempotency_atomic_results_and_reference_exclusion(
    tmp_path: Path,
) -> None:
    corpus_root = build_legacy_reference_corpus(tmp_path)
    data_directory = tmp_path / "research-data"
    data_directory.mkdir(mode=0o700)
    paths = ResearchDataPaths(
        data_directory=data_directory,
        database=data_directory / RESEARCH_DATABASE_FILENAME,
    )
    repository = SQLiteResearchRepository(paths)
    importer = BigLottoLegacyReferenceImporter(repository)
    stop = threading.Event()
    stop.set()

    paused = importer.execute(
        corpus_root,
        source_commit_oid="a" * 40,
        stop_requested=stop,
        observe_reader_wait=False,
    )

    assert paused.status is ResearchRunStatus.PAUSED
    assert paused.interrupted is True
    assert paused.completed_target_count == 1
    assert paused.expected_target_count == 2
    with open_database(paths, read_only=True) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM research_prediction_targets"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_prediction_tickets"
        ).fetchone() == (250,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_ticket_results"
        ).fetchone() == (250,)

    resumed = importer.execute(
        corpus_root,
        source_commit_oid="a" * 40,
        observe_reader_wait=False,
    )
    before_no_op = repository.verify_store().row_counts
    repeated = importer.execute(
        corpus_root,
        source_commit_oid="a" * 40,
        observe_reader_wait=False,
    )
    after_no_op = repository.verify_store().row_counts

    assert resumed.status is ResearchRunStatus.COMPLETED
    assert resumed.targets_created == 1
    assert resumed.tickets_created == resumed.results_created == 250
    assert resumed.completed_target_count == 2
    assert repeated.idempotent_no_op is True
    assert repeated.targets_created == repeated.tickets_created == 0
    assert before_no_op == after_no_op
    assert repository.coverage().items == ()
    assert len(
        repository.coverage(include_reference_baselines=True).items
    ) == 1
    assert repository.rankings().items == ()
    assert len(
        repository.rankings(include_reference_baselines=True).items
    ) == 1
    assert repository.verify_store().healthy is True

    with open_database(paths, read_only=True) as connection:
        positions = connection.execute(
            """
            SELECT native_position, native_duplicate_of_position,
                   legacy_provenance_hash, legacy_provenance_source
            FROM research_prediction_tickets
            WHERE target_id = (
                SELECT id FROM research_prediction_targets
                ORDER BY target_order, id LIMIT 1
            )
            ORDER BY native_position
            """
        ).fetchall()
        assert [row[0] for row in positions] == list(range(1, 251))
        assert positions[0][1] is None
        assert all(row[1] == 1 for row in positions[1:])
        assert all(row[2] is not None for row in positions)
        assert all(row[3] == "synthetic-legacy-source" for row in positions)


def test_changed_completed_target_raises_instead_of_being_ignored(
    tmp_path: Path,
) -> None:
    corpus_root = build_legacy_reference_corpus(tmp_path)
    data_directory = tmp_path / "research-data"
    data_directory.mkdir(mode=0o700)
    paths = ResearchDataPaths(
        data_directory=data_directory,
        database=data_directory / RESEARCH_DATABASE_FILENAME,
    )
    repository = SQLiteResearchRepository(paths)
    importer = BigLottoLegacyReferenceImporter(repository)
    result = importer.execute(
        corpus_root,
        source_commit_oid="b" * 40,
        observe_reader_wait=False,
    )
    prepared = prepare_legacy_corpus(corpus_root)
    original = importer.build_target_commit_input(
        result.run_id,
        prepared,
        prepared.targets[0],
    )
    first = original.tickets[0]
    changed_ticket = TicketInput(
        native_position=first.native_position,
        ordered_portfolio_position=first.ordered_portfolio_position,
        canonical_ticket_json='{"main_numbers":[1,2,3,4,5,7],"special_numbers":[]}',
        legacy_record_json=first.legacy_record_json,
        legacy_provenance_hash=first.legacy_provenance_hash,
        legacy_provenance_source=first.legacy_provenance_source,
    )
    changed = dataclasses.replace(
        original,
        tickets=(changed_ticket, *original.tickets[1:]),
    )

    with pytest.raises(ResearchConflictError, match="conflicts"):
        repository.commit_target(
            changed,
            idempotency_key="deliberately-altered-completed-target",
        )
