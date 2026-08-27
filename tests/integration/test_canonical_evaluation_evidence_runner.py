"""Real-SQLite coverage for the whole V1C canonical evaluation vertical.

Nothing is simulated between the ends: the committed synthetic BIG_LOTTO
fixture seeds a task-owned temporary database, a real strategy adapter replays
real causal history, the unmodified evaluator produces the record, the V1B
materializer turns it into four canonical evidence documents, and the existing
validator is the gate they must pass.

Two claims get first-class tests because they are what "orchestration only"
actually means:

*Parity.* The runner's output is compared against the same chain composed by
hand -- session, then V1A, then V1B -- rather than against any formula restated
here. If the runner ever grew semantics of its own, that comparison breaks.

*Hermeticity.* Every outcome comes from the committed fixture and the dataset
snapshot built from it, never from a production draw database. One test
poisons ``resolve_local_data_paths`` so that reaching for the production
database would raise, and the vertical still completes; another snapshots every
table before and after to prove the whole path stays read-only.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictionsResult,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.evidence import canonical_json, validator
from lottolab.evidence.method_evaluation_materialization import (
    V1B_METRIC_IDS,
    EvidenceProducerIdentity,
    MethodEvaluationMaterializationError,
    load_metric_definition_bindings,
    materialize_method_evaluation_evidence,
)
from lottolab.evidence.models import (
    DatasetSnapshot,
    DrawEntry,
    EvidenceStatus,
    ExactRational,
    FindingCategory,
    OutcomeSource,
    RuleParameters,
    StrategyEvaluationEvidence,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.research import replay_research_session
from lottolab.interfaces.research.replay_research_session import ReplayResearchSession
from lottolab.research import canonical_evaluation_evidence_runner as runner_module
from lottolab.research.base_method_evaluation import (
    AVG_MATCH_ID,
    WINDOW_SIZES,
    MethodEvaluationRecord,
    ReplayStatus,
    WindowKind,
)
from lottolab.research.canonical_evaluation_evidence_runner import (
    EXPECTED_WINDOW_ORDER,
    CanonicalEvaluationEvidenceResult,
    CanonicalEvaluationEvidenceRunnerError,
    CanonicalEvaluationRequest,
    run_canonical_evaluation_evidence,
)
from lottolab.research.replay_method_evaluation import (
    ReplayMethodEvaluationError,
    ReplayTargetOutcome,
    evaluate_replayed_single_ticket_method,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_DATASET_ID = "SYNTHETIC_BIG_LOTTO_CANONICAL_EVALUATION_V1C"
_DATASET_VERSION = "1"
_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_STRATEGY_VERSION = "v0.1"
_METHOD_FAMILY = "SYNTHETIC_CANONICAL_EVALUATION_V1C"
_ARTIFACT_PREFIX = "SYNTHETIC_V1C_INTEGRATION"
_TARGET_DRAW_NUMBERS = tuple(str(1000100 + offset) for offset in range(10))
_TABLES = ("draws", "schema_migrations", "ingestion_runs", "ingestion_items")


# --------------------------------------------------------------------------
# Task-owned fixture, database and dataset snapshot
# --------------------------------------------------------------------------


def _task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "v1c-canonical-evaluation-sqlite")}
    )


def _fixture_rows() -> list[dict[str, Any]]:
    fixture: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast("list[dict[str, Any]]", fixture["history_rows"])


def _seed_canonical_draws(paths: LocalDataPaths) -> None:
    rows = [
        ",".join(
            (
                LotteryType.BIG_LOTTO.value,
                row["draw_number"],
                row["draw_date"],
                "|".join(str(number) for number in row["main_numbers"]),
                str(row["special_number"]),
                "synthetic-v1c-canonical-evaluation",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")), filename="synthetic-v1c-canonical-evaluation.csv"
    )
    assert document.is_valid, document.errors
    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)
    assert result.inserted_count == len(rows) == 110
    assert result.skipped_count == result.conflict_count == result.failed_count == 0


def _table_snapshot(paths: LocalDataPaths) -> dict[str, tuple[tuple[object, ...], ...]]:
    with open_database(paths, read_only=True) as connection:
        return {
            table: tuple(
                tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
            )
            for table in _TABLES
        }


def _rule_binding_payload() -> dict[str, Any]:
    contract = BIG_LOTTO_RULE_CONTRACT
    payload: dict[str, Any] = {
        "main_number_count": contract.main_number_count,
        "main_number_min": contract.main_number_min,
        "main_number_max": contract.main_number_max,
        "main_numbers_unique": contract.main_numbers_unique,
        "special_number_count": contract.special_number_count,
        "special_number_min": contract.special_number_min,
        "special_number_max": contract.special_number_max,
        "special_numbers_unique": contract.special_numbers_unique,
        "main_special_overlap_allowed": contract.main_special_overlap_allowed,
        "rule_contract_version": contract.contract_version,
    }
    payload["rule_parameters_sha256"] = canonical_json.self_key_removed_sha256(
        RuleParameters.model_validate(
            {**payload, "rule_parameters_sha256": "0" * 64}
        ).model_dump(mode="json", exclude_none=True),
        "rule_parameters_sha256",
    )
    return payload


def _dataset_from_draws(draws: tuple[DrawEntry, ...]) -> DatasetSnapshot:
    payload: dict[str, Any] = {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": _DATASET_ID,
        "dataset_version": _DATASET_VERSION,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "rule_binding": _rule_binding_payload(),
        "source_provenance": {
            "kind": "SYNTHETIC",
            "declared_description": "committed synthetic BIG_LOTTO causal-history fixture",
        },
        "draws": [draw.model_dump(mode="json", exclude_none=True) for draw in draws],
    }
    payload["dataset_sha256"] = canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))
    return DatasetSnapshot.model_validate(payload)


def _fixture_draws() -> tuple[DrawEntry, ...]:
    return tuple(
        DrawEntry(
            draw_id=row["draw_number"],
            draw_sequence=index,
            draw_date=date.fromisoformat(row["draw_date"]),
            main_numbers=tuple(row["main_numbers"]),
            special_numbers=(row["special_number"],),
        )
        for index, row in enumerate(_fixture_rows())
    )


def _dataset_snapshot() -> DatasetSnapshot:
    """The committed fixture rows, expressed as the authoritative snapshot."""

    return _dataset_from_draws(_fixture_draws())


def _dataset_with_replaced_draw(draw_id: str, replacement: DrawEntry) -> DatasetSnapshot:
    return _dataset_from_draws(
        tuple(
            replacement if draw.draw_id == draw_id else draw for draw in _fixture_draws()
        )
    )


def _dataset_without_draw(draw_id: str) -> DatasetSnapshot:
    kept = [draw for draw in _fixture_draws() if draw.draw_id != draw_id]
    assert len(kept) == len(_fixture_draws()) - 1
    return _dataset_from_draws(
        tuple(
            draw.model_copy(update={"draw_sequence": index})
            for index, draw in enumerate(kept)
        )
    )


def _producer() -> EvidenceProducerIdentity:
    definition = REPO_ROOT / "contracts/evidence/metric_definitions/avg_match.json"
    return EvidenceProducerIdentity(
        artifact_id_prefix=_ARTIFACT_PREFIX,
        evidence_status=EvidenceStatus.SYNTHETIC_TEST_ONLY,
        produced_at=datetime(2026, 8, 27, tzinfo=UTC),
        producer_name="lottolab-canonical-evaluation-evidence-runner",
        method_source_git_oid="c" * 40,
        feature_version="v1",
        feature_definition_path="contracts/evidence/metric_definitions/avg_match.json",
        feature_definition_sha256=canonical_json.sha256_hex(definition.read_bytes()),
    )


def _request(
    paths: LocalDataPaths, dataset: DatasetSnapshot, **overrides: Any
) -> CanonicalEvaluationRequest:
    fields: dict[str, Any] = {
        "database_paths": paths,
        "dataset": dataset,
        "repo_root": REPO_ROOT,
        "strategy_id": _STRATEGY_ID,
        "target_draw_numbers": _TARGET_DRAW_NUMBERS,
        "method_family": _METHOD_FAMILY,
        "replay_status": ReplayStatus.BASELINE_RECORDED,
        "producer": _producer(),
    }
    fields.update(overrides)
    return CanonicalEvaluationRequest(**fields)


def _seeded(tmp_path: Path) -> tuple[LocalDataPaths, DatasetSnapshot]:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    return paths, _dataset_snapshot()


def _run(
    tmp_path: Path,
) -> tuple[LocalDataPaths, DatasetSnapshot, CanonicalEvaluationEvidenceResult]:
    paths, dataset = _seeded(tmp_path)
    return paths, dataset, run_canonical_evaluation_evidence(_request(paths, dataset))


# --------------------------------------------------------------------------
# The manual composition the runner must be observationally equivalent to
# --------------------------------------------------------------------------


def _manual_replay(paths: LocalDataPaths) -> tuple[ReplayPredictionSnapshot, ...]:
    session = ReplayResearchSession(lottery_type=LotteryType.BIG_LOTTO, paths=paths)
    return session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=(_STRATEGY_ID,),
    ).snapshots


def _manual_composition(
    paths: LocalDataPaths, dataset: DatasetSnapshot
) -> tuple[
    tuple[ReplayPredictionSnapshot, ...],
    MethodEvaluationRecord,
    tuple[StrategyEvaluationEvidence, ...],
]:
    """Session + V1A + V1B, composed by hand exactly as V1B's own tests do."""

    snapshots = _manual_replay(paths)
    by_draw_id = {draw.draw_id: draw for draw in dataset.draws}
    outcomes = tuple(
        ReplayTargetOutcome(
            draw_number=snapshot.target_draw_number,
            draw_date=by_draw_id[snapshot.target_draw_number].draw_date,
            main_numbers=by_draw_id[snapshot.target_draw_number].main_numbers,
        )
        for snapshot in snapshots
    )
    evaluation = evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family=_METHOD_FAMILY,
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )
    documents = materialize_method_evaluation_evidence(
        dataset=dataset,
        snapshots=snapshots,
        evaluation=evaluation,
        metric_definitions=load_metric_definition_bindings(REPO_ROOT),
        producer=_producer(),
    )
    return snapshots, evaluation, documents


def _canonical_bytes(evidence: StrategyEvaluationEvidence) -> bytes:
    return canonical_json.canonical_file_bytes(evidence.model_dump(mode="json", exclude_none=True))


# --------------------------------------------------------------------------
# The vertical
# --------------------------------------------------------------------------


def test_runner_emits_four_validated_artifacts_in_evaluator_window_order(
    tmp_path: Path,
) -> None:
    _, _, result = _run(tmp_path)

    assert len(result.artifacts) == 4
    assert result.window_kinds == EXPECTED_WINDOW_ORDER
    assert result.window_kinds == (
        WindowKind.WINDOW_50,
        WindowKind.WINDOW_300,
        WindowKind.WINDOW_750,
        WindowKind.FULL_HISTORY,
    )
    assert [artifact.evidence.artifact_id for artifact in result.artifacts] == [
        f"{_ARTIFACT_PREFIX}_{kind.value}" for kind, _ in WINDOW_SIZES
    ]

    for artifact in result.artifacts:
        assert artifact.validation.schema_valid
        assert artifact.validation.findings == (), (
            artifact.window_kind,
            artifact.validation.findings,
        )
        assert artifact.evidence.strategy_id == _STRATEGY_ID
        assert artifact.evidence.strategy_version == _STRATEGY_VERSION
        assert artifact.evidence.method_id == _STRATEGY_ID
        assert len(artifact.evidence.records) == len(_TARGET_DRAW_NUMBERS)
        assert [result_.metric_id for result_ in artifact.evidence.metric_results] == list(
            V1B_METRIC_IDS
        )


def test_runner_output_equals_the_manual_v1a_v1b_composition(tmp_path: Path) -> None:
    paths, dataset = _seeded(tmp_path)

    result = run_canonical_evaluation_evidence(_request(paths, dataset))
    manual_snapshots, manual_evaluation, manual_documents = _manual_composition(paths, dataset)

    assert result.snapshots == manual_snapshots
    assert result.evaluation == manual_evaluation
    assert len(result.artifacts) == len(manual_documents)
    for artifact, manual in zip(result.artifacts, manual_documents, strict=True):
        assert artifact.evidence == manual
        assert artifact.canonical_bytes == _canonical_bytes(manual)
        assert artifact.artifact_content_sha256 == manual.artifact_content_sha256


def test_runner_artifacts_load_and_validate_from_disk_exactly_as_returned(
    tmp_path: Path,
) -> None:
    """The runner's in-memory gate is the same gate an external reader applies."""

    _, dataset, result = _run(tmp_path)

    dataset_path = tmp_path / "dataset_snapshot.json"
    dataset_path.write_bytes(
        canonical_json.canonical_file_bytes(dataset.model_dump(mode="json", exclude_none=True))
    )

    for artifact in result.artifacts:
        evidence_path = tmp_path / f"{artifact.evidence.artifact_id}.json"
        evidence_path.write_bytes(artifact.canonical_bytes)

        report = validator.validate_evidence_file(
            evidence_path, repo_root=REPO_ROOT, dataset_path=dataset_path
        )
        assert report.schema_valid
        assert report.findings == ()
        assert report == artifact.validation

        reloaded, load_findings = validator.load_evidence(evidence_path)
        assert load_findings == []
        assert reloaded is not None
        assert _canonical_bytes(reloaded) == artifact.canonical_bytes


def test_runner_is_deterministic_across_identical_runs(tmp_path: Path) -> None:
    paths, dataset = _seeded(tmp_path)

    first = run_canonical_evaluation_evidence(_request(paths, dataset))
    second = run_canonical_evaluation_evidence(_request(paths, dataset))

    assert first.artifact_content_sha256s == second.artifact_content_sha256s
    for left, right in zip(first.artifacts, second.artifacts, strict=True):
        assert left.canonical_bytes == right.canonical_bytes
        assert left.evidence == right.evidence


def test_exact_rational_metric_values_survive_end_to_end(tmp_path: Path) -> None:
    _, _, result = _run(tmp_path)

    compared = 0
    average_match_denominators: list[int] = []
    for artifact in result.artifacts:
        block = result.evaluation.windows[artifact.window_kind]
        for metric_result in artifact.evidence.metric_results:
            assert isinstance(metric_result.value, ExactRational)
            observed = block.metrics[metric_result.metric_id].observed_value
            assert observed is not None
            assert (
                Fraction(metric_result.value.numerator, metric_result.value.denominator)
                == observed
            )
            if metric_result.metric_id == AVG_MATCH_ID:
                average_match_denominators.append(metric_result.value.denominator)
            compared += 1

    assert compared == 4 * len(V1B_METRIC_IDS)
    # A decimal-coerced pipeline would have nothing left to prove here: at least
    # one exact value must be a genuine fraction, not an integer in disguise.
    assert any(denominator != 1 for denominator in average_match_denominators)


# --------------------------------------------------------------------------
# Hermeticity: no production database is reachable, and nothing is written
# --------------------------------------------------------------------------


def test_runner_never_resolves_the_production_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Poison the production-path resolver; a hermetic run must not notice."""

    def _explode(*args: object, **kwargs: object) -> LocalDataPaths:
        raise AssertionError("the runner reached for the production database")

    monkeypatch.setattr(replay_research_session, "resolve_local_data_paths", _explode)

    paths, dataset = _seeded(tmp_path)
    result = run_canonical_evaluation_evidence(_request(paths, dataset))

    assert len(result.artifacts) == 4


def test_the_whole_vertical_is_read_only(tmp_path: Path) -> None:
    paths, dataset = _seeded(tmp_path)

    before = _table_snapshot(paths)
    run_canonical_evaluation_evidence(_request(paths, dataset))
    after = _table_snapshot(paths)

    assert after == before, "the evaluation vertical must never write to the draw database"


def test_actual_outcomes_come_from_the_dataset_not_the_replay_database(
    tmp_path: Path,
) -> None:
    """The database keeps the fixture's outcome; the dataset says something else.

    Only one of the two can reach the artifact, and the contract says it is the
    dataset snapshot -- which is also the document the validator cross-checks.
    """

    paths, _ = _seeded(tmp_path)
    target = _TARGET_DRAW_NUMBERS[-1]
    original = next(draw for draw in _fixture_draws() if draw.draw_id == target)
    rewritten = original.model_copy(update={"main_numbers": (2, 13, 21, 34, 38, 47)})
    assert rewritten.main_numbers != original.main_numbers
    dataset = _dataset_with_replaced_draw(target, rewritten)

    result = run_canonical_evaluation_evidence(_request(paths, dataset))

    for artifact in result.artifacts:
        record = next(
            record for record in artifact.evidence.records if record.target.draw_id == target
        )
        assert record.actual_main_numbers == rewritten.main_numbers
        assert record.actual_special_numbers == original.special_numbers
        assert record.outcome_source is OutcomeSource.DATASET_SNAPSHOT
        assert artifact.validation.findings == ()


# --------------------------------------------------------------------------
# Fail-closed boundaries, all exercised through the real replay stack
# --------------------------------------------------------------------------


def test_a_failed_replay_step_never_becomes_a_zero_hit_observation(tmp_path: Path) -> None:
    """Demanding more causal history than exists closes the step, not the score."""

    paths, dataset = _seeded(tmp_path)
    request = _request(paths, dataset, minimum_history_draws=500)

    with pytest.raises(ReplayMethodEvaluationError, match="is not evaluable"):
        run_canonical_evaluation_evidence(request)


def test_an_outcome_dated_differently_from_the_replay_target_fails_closed(
    tmp_path: Path,
) -> None:
    """V1A is the earlier gate here, and it closes before V1B is ever reached."""

    paths, _ = _seeded(tmp_path)
    target = _TARGET_DRAW_NUMBERS[0]
    original = next(draw for draw in _fixture_draws() if draw.draw_id == target)
    dataset = _dataset_with_replaced_draw(
        target, original.model_copy(update={"draw_date": date(2019, 12, 31)})
    )

    with pytest.raises(
        ReplayMethodEvaluationError,
        match=f"outcome for draw {target} has draw_date 2019-12-31 but the snapshot targets",
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_a_cutoff_dated_differently_from_the_replay_cutoff_fails_closed(
    tmp_path: Path,
) -> None:
    paths, _ = _seeded(tmp_path)
    cutoff_draw_id = "1000099"
    assert cutoff_draw_id not in _TARGET_DRAW_NUMBERS
    original = next(draw for draw in _fixture_draws() if draw.draw_id == cutoff_draw_id)
    dataset = _dataset_with_replaced_draw(
        cutoff_draw_id, original.model_copy(update={"draw_date": date(2019, 12, 30)})
    )

    with pytest.raises(
        MethodEvaluationMaterializationError, match="but the snapshot declares"
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_a_cutoff_absent_from_the_dataset_fails_closed(tmp_path: Path) -> None:
    paths, _ = _seeded(tmp_path)
    dataset = _dataset_without_draw("1000099")

    with pytest.raises(
        MethodEvaluationMaterializationError,
        match="cutoff draw 1000099 is absent from the dataset snapshot",
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_a_strategy_version_mismatch_fails_closed(tmp_path: Path) -> None:
    paths, dataset = _seeded(tmp_path)
    request = _request(paths, dataset, expected_strategy_version="v9.9")

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError, match="replay resolved strategy version"
    ):
        run_canonical_evaluation_evidence(request)

    assert (
        run_canonical_evaluation_evidence(
            _request(paths, dataset, expected_strategy_version=_STRATEGY_VERSION)
        ).evaluation.identity.method_version
        == _STRATEGY_VERSION
    )


def test_a_dataset_replayed_under_another_identity_fails_closed(tmp_path: Path) -> None:
    """V1B rejects snapshots whose dataset identity is not the supplied snapshot's."""

    paths, dataset = _seeded(tmp_path)
    snapshots = _manual_replay(paths)
    other = _dataset_from_draws(_fixture_draws()).model_copy(
        update={"dataset_version": "2"}
    )
    assert other.dataset_version != dataset.dataset_version

    with pytest.raises(MethodEvaluationMaterializationError, match="was replayed against dataset"):
        materialize_method_evaluation_evidence(
            dataset=other,
            snapshots=snapshots,
            evaluation=_manual_composition(paths, dataset)[1],
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


# --------------------------------------------------------------------------
# The runner's own gates reject, rather than merely passing on a good day
# --------------------------------------------------------------------------


def test_a_semantic_validation_finding_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation is a gate, not a report the runner attaches and ignores."""

    paths, dataset = _seeded(tmp_path)
    finding = validator.Finding(
        FindingCategory.HASH_MISMATCH,
        "SYNTHETIC_INJECTED_FINDING",
        "/records/0",
        "injected by test",
    )

    def _finds_something(*args: object, **kwargs: object) -> validator.ValidationReport:
        return validator.ValidationReport(
            schema_valid=True,
            findings=(finding,),
            hash_checks=(),
            trust_classification=None,
            structurally_valid=False,
            canonical_gate_passed=False,
        )

    monkeypatch.setattr(validator, "validate_evidence_artifact", _finds_something)

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match="failed existing semantic validation",
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_a_schema_invalid_artifact_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, dataset = _seeded(tmp_path)

    def _schema_invalid(*args: object, **kwargs: object) -> validator.ValidationReport:
        return validator.ValidationReport(
            schema_valid=False,
            findings=(),
            hash_checks=(),
            trust_classification=None,
            structurally_valid=False,
            canonical_gate_passed=False,
        )

    monkeypatch.setattr(validator, "validate_evidence_artifact", _schema_invalid)

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError, match="failed existing schema validation"
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_replay_output_that_loses_caller_ordering_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering is re-asserted, not assumed, because the whole record depends on it."""

    paths, dataset = _seeded(tmp_path)
    original = ReplayResearchSession.replay_targets

    def _reversed(
        self: ReplayResearchSession, **kwargs: Any
    ) -> ReplayHistoricalPredictionsResult:
        result = original(self, **kwargs)
        return ReplayHistoricalPredictionsResult(snapshots=tuple(reversed(result.snapshots)))

    monkeypatch.setattr(ReplayResearchSession, "replay_targets", _reversed)

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError, match="replay ordering was not preserved"
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_replay_returning_the_wrong_snapshot_count_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, dataset = _seeded(tmp_path)
    original = ReplayResearchSession.replay_targets

    def _truncated(
        self: ReplayResearchSession, **kwargs: Any
    ) -> ReplayHistoricalPredictionsResult:
        result = original(self, **kwargs)
        return ReplayHistoricalPredictionsResult(snapshots=result.snapshots[:-1])

    monkeypatch.setattr(ReplayResearchSession, "replay_targets", _truncated)

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match=r"replay returned 9 snapshots for 10 targets",
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


# --------------------------------------------------------------------------
# The runner's defensive V1B-contract assertions are load-bearing, not decorative
#
# These three guards exist so a future change to the materializer's contract
# cannot silently reach a caller. A correct V1B never trips them, so nothing
# else in this file would notice if they were deleted -- which is exactly why
# each one is neutralised here directly.
# --------------------------------------------------------------------------


def _materializing(
    documents: tuple[StrategyEvaluationEvidence, ...],
) -> Callable[..., tuple[StrategyEvaluationEvidence, ...]]:
    def _fixed(*args: object, **kwargs: object) -> tuple[StrategyEvaluationEvidence, ...]:
        return documents

    return _fixed


def test_materialized_artifacts_out_of_window_order_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, dataset = _seeded(tmp_path)
    documents = _manual_composition(paths, dataset)[2]

    monkeypatch.setattr(
        runner_module,
        "materialize_method_evaluation_evidence",
        _materializing(tuple(reversed(documents))),
    )

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match="is not the WINDOW_50 artifact the evaluator's window order requires",
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_a_short_materialization_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, dataset = _seeded(tmp_path)
    documents = _manual_composition(paths, dataset)[2]

    monkeypatch.setattr(
        runner_module,
        "materialize_method_evaluation_evidence",
        _materializing(documents[:-1]),
    )

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match="materialization returned 3 artifacts, expected 4",
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))


def test_an_artifact_that_does_not_survive_a_canonical_round_trip_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reload returns a different document than the bytes that were written."""

    paths, dataset = _seeded(tmp_path)
    documents = _manual_composition(paths, dataset)[2]
    substitute = documents[1]
    assert substitute.artifact_id != documents[0].artifact_id

    class _AlwaysReloadsSomethingElse:
        @staticmethod
        def model_validate(value: object) -> StrategyEvaluationEvidence:
            return substitute

    monkeypatch.setattr(
        runner_module, "StrategyEvaluationEvidence", _AlwaysReloadsSomethingElse
    )

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match="WINDOW_50 artifact does not survive a canonical serialize/load round trip",
    ):
        run_canonical_evaluation_evidence(_request(paths, dataset))
