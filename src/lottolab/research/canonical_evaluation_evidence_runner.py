"""Run one hermetic canonical evaluation end to end: replay -> V1A -> V1B -> validated.

The V1C vertical, and nothing more. This module owns no replay engine, no
evaluator, no scoring table, no window semantics, no evidence envelope, no
canonical-JSON authority, no persistence and no ranking. It composes the four
already-canonical seams in their existing order:

1. :class:`~lottolab.interfaces.research.replay_research_session.ReplayResearchSession`
   produces the causal :class:`~lottolab.domain.replay_predictions.ReplayPredictionSnapshot`
   sequence;
2. :func:`~lottolab.research.replay_method_evaluation.evaluate_replayed_single_ticket_method`
   (V1A) turns those snapshots plus the dataset's realized outcomes into one
   :class:`~lottolab.research.base_method_evaluation.MethodEvaluationRecord`;
3. ``materialize_method_evaluation_evidence`` in
   :mod:`~lottolab.evidence.method_evaluation_materialization`
   (V1B) turns that record into exactly four
   :class:`~lottolab.evidence.models.StrategyEvaluationEvidence` documents, in
   the evaluator's own ``WINDOW_SIZES`` order;
4. :func:`~lottolab.evidence.validator.validate_evidence_artifact` is the gate
   every returned artifact must pass.

Calling this runner is therefore observationally equivalent to composing those
seams by hand for the same inputs -- which is exactly what its tests assert,
rather than restating any formula here.

Four properties are worth stating explicitly, because each is a place where an
orchestrator could quietly become a fiction:

*Hermetic inputs only.* ``ReplayResearchSession`` defaults ``paths`` to the
resolved production database. This runner never uses that default: a
:class:`~lottolab.infrastructure.persistence.draw_schema.LocalDataPaths` is a
required field, and the referenced database file must already exist, so there
is no code path on which a caller who forgot to point at a task-owned database
silently replays production draws instead.

*Identity comes from the replay.* ``method_id``/``method_version`` are whatever
V1A resolved from the replay catalog. ``strategy_id`` and the optional
``expected_strategy_version`` are assertions the run must satisfy, never inputs
the record is built from: a disagreement fails closed instead of relabelling
the record.

*Outcomes come from the dataset.* Realized main and special numbers are read
out of the supplied ``DatasetSnapshot`` only. V1B independently rebuilds those
same outcomes and re-runs the evaluator over them, requiring exact equality
before it writes anything, so a record that did not come from these snapshots
and this dataset can never be materialized.

*Failure is never an observation.* A replay step whose causal history or
prediction did not close ``OK`` raises out of V1A. It is never filtered out,
and never recorded as a zero-hit draw.

This runner records. It never persists to the ResearchStore or the canonical
evidence registry, never writes to any database, and takes no position on
whether the strategy it evaluated is any good.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.domain.strategies import ResponseShape, StrategyDescriptor
from lottolab.evidence import canonical_json, validator
from lottolab.evidence.method_evaluation_materialization import (
    EvidenceProducerIdentity,
    MetricDefinitionBinding,
    load_metric_definition_bindings,
    materialize_method_evaluation_evidence,
)
from lottolab.evidence.models import DatasetSnapshot, DrawEntry, StrategyEvaluationEvidence
from lottolab.evidence.validator import ValidationReport
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.interfaces.research.replay_research_session import ReplayResearchSession
from lottolab.research.base_method_evaluation import (
    BIG_LOTTO_MATCH_CONTRACT,
    WINDOW_SIZES,
    LotteryMatchContract,
    MethodEvaluationRecord,
    ReplayStatus,
    WindowKind,
)
from lottolab.research.replay_method_evaluation import (
    ReplayTargetOutcome,
    evaluate_replayed_single_ticket_method,
)
from lottolab.strategies.catalog import (
    StrategyCatalog,
    UnknownStrategyError,
    production_catalog,
)

#: V1C evaluates exactly one BIG_LOTTO strategy per invocation.
RUNNER_LOTTERY_TYPE = LotteryType.BIG_LOTTO

#: The one match contract this runner composes V1A and V1B with.
RUNNER_MATCH_CONTRACT: LotteryMatchContract = BIG_LOTTO_MATCH_CONTRACT

#: The evaluator's own window order, which V1B materializes in and this runner
#: re-asserts rather than assumes: WINDOW_50, WINDOW_300, WINDOW_750, FULL_HISTORY.
EXPECTED_WINDOW_ORDER: tuple[WindowKind, ...] = tuple(kind for kind, _ in WINDOW_SIZES)

#: One artifact per evaluator window, always.
EXPECTED_ARTIFACT_COUNT = len(EXPECTED_WINDOW_ORDER)

class CanonicalEvaluationEvidenceRunnerError(ValueError):
    """Closed-contract failure while running the canonical evaluation vertical."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanonicalEvaluationEvidenceRunnerError(message)


@dataclass(frozen=True, slots=True)
class CanonicalEvaluationRequest:
    """Every input one hermetic invocation needs, supplied explicitly.

    ``database_paths`` is required and never defaulted: see the module
    docstring on why a production-database fallback must not exist here.
    ``expected_strategy_version``, when supplied, is a fail-closed assertion
    about the version the replay catalog resolves -- not a value any part of
    the resulting record is built from.
    """

    database_paths: LocalDataPaths
    dataset: DatasetSnapshot
    repo_root: Path
    strategy_id: str
    target_draw_numbers: tuple[str, ...]
    method_family: str
    replay_status: ReplayStatus
    producer: EvidenceProducerIdentity
    expected_strategy_version: str | None = None
    maximum_history_draws: int | None = None
    minimum_history_draws: int | None = None

    def __post_init__(self) -> None:
        _require(bool(self.strategy_id.strip()), "strategy_id must be a non-empty string")
        _require(bool(self.method_family.strip()), "method_family must be a non-empty string")
        _require(len(self.target_draw_numbers) > 0, "target_draw_numbers must not be empty")
        _require(
            all(bool(number.strip()) for number in self.target_draw_numbers),
            "target_draw_numbers must not contain a blank draw number",
        )
        duplicates = sorted(
            {
                number
                for number in self.target_draw_numbers
                if self.target_draw_numbers.count(number) > 1
            }
        )
        _require(
            not duplicates,
            f"target_draw_numbers contain duplicates: {', '.join(duplicates)}",
        )
        _require(
            self.expected_strategy_version is None
            or bool(self.expected_strategy_version.strip()),
            "expected_strategy_version must be omitted or a non-empty string",
        )


@dataclass(frozen=True, slots=True)
class CanonicalEvaluationArtifact:
    """One validated evidence document, with the exact bytes it was validated as."""

    window_kind: WindowKind
    evidence: StrategyEvaluationEvidence
    canonical_bytes: bytes
    artifact_content_sha256: str
    validation: ValidationReport


@dataclass(frozen=True, slots=True)
class CanonicalEvaluationEvidenceResult:
    """The whole vertical's observable output for one invocation.

    ``snapshots`` and ``evaluation`` are returned unchanged so a caller (or a
    test) can re-run the manual composition against them and compare.
    """

    snapshots: tuple[ReplayPredictionSnapshot, ...]
    evaluation: MethodEvaluationRecord
    artifacts: tuple[CanonicalEvaluationArtifact, ...]

    @property
    def window_kinds(self) -> tuple[WindowKind, ...]:
        return tuple(artifact.window_kind for artifact in self.artifacts)

    @property
    def evidence_documents(self) -> tuple[StrategyEvaluationEvidence, ...]:
        return tuple(artifact.evidence for artifact in self.artifacts)

    @property
    def artifact_content_sha256s(self) -> tuple[str, ...]:
        return tuple(artifact.artifact_content_sha256 for artifact in self.artifacts)


def resolve_single_ticket_descriptor(
    strategy_id: str, *, catalog: StrategyCatalog | None = None
) -> StrategyDescriptor:
    """Resolve ``strategy_id`` as one BIG_LOTTO SINGLE_TICKET strategy, or fail closed.

    Resolved through the same ``production_catalog()`` the replay stack itself
    injects, so this gate can never admit a strategy the replay would then
    resolve differently. A PORTFOLIO strategy and a strategy not registered for
    BIG_LOTTO are both rejected here rather than being partially evaluated as
    if they were single-ticket methods.

    Ticket count needs no gate of its own: ``StrategyDescriptor`` already
    refuses to exist as SINGLE_TICKET unless its native ticket bounds are
    exactly ``(1, 1)``, which is the invariant V1A's one-ticket exposure rests
    on.
    """

    resolved = production_catalog() if catalog is None else catalog
    try:
        descriptor = resolved.get(strategy_id)
    except UnknownStrategyError as exc:
        raise CanonicalEvaluationEvidenceRunnerError(
            f"strategy {strategy_id!r} is not registered in the replay catalog"
        ) from exc
    _require(
        RUNNER_LOTTERY_TYPE in descriptor.lottery_types,
        f"strategy {strategy_id!r} is not registered for {RUNNER_LOTTERY_TYPE.value}",
    )
    _require(
        descriptor.response_shape is ResponseShape.SINGLE_TICKET,
        f"strategy {strategy_id!r} has response_shape "
        f"{descriptor.response_shape.value}; this vertical evaluates "
        f"{ResponseShape.SINGLE_TICKET.value} strategies only",
    )
    return descriptor


def _index_dataset_draws(dataset: DatasetSnapshot) -> dict[str, DrawEntry]:
    """Index the dataset by ``draw_id``, refusing a snapshot that repeats one."""

    indexed: dict[str, DrawEntry] = {}
    for draw in dataset.draws:
        _require(
            draw.draw_id not in indexed,
            f"dataset snapshot contains a duplicate draw {draw.draw_id}",
        )
        indexed[draw.draw_id] = draw
    return indexed


def _outcomes_from_dataset(
    snapshots: Sequence[ReplayPredictionSnapshot], draws_by_id: Mapping[str, DrawEntry]
) -> tuple[ReplayTargetOutcome, ...]:
    """Read each replayed target's realized outcome out of the dataset snapshot.

    Deliberately built the same way V1B rebuilds it internally: V1B re-runs the
    evaluator over its own reconstruction and requires exact equality, so any
    divergence here would fail closed there rather than reach an artifact.
    """

    outcomes: list[ReplayTargetOutcome] = []
    for snapshot in snapshots:
        draw = draws_by_id.get(snapshot.target_draw_number)
        _require(
            draw is not None,
            f"target draw {snapshot.target_draw_number} is absent from the dataset snapshot",
        )
        assert draw is not None  # narrowed by the check above
        outcomes.append(
            ReplayTargetOutcome(
                draw_number=draw.draw_id,
                draw_date=draw.draw_date,
                main_numbers=draw.main_numbers,
            )
        )
    return tuple(outcomes)


def _replay_single_strategy(
    request: CanonicalEvaluationRequest,
) -> tuple[ReplayPredictionSnapshot, ...]:
    """Replay the request's targets through the existing session, hermetically.

    The session is constructed with the request's own ``LocalDataPaths``, so
    ``ReplayResearchSession``'s production-database default is never reached.
    Exactly one ``strategy_id`` is replayed, which makes the result's
    target-major ordering a one-snapshot-per-target sequence in caller order --
    re-asserted below rather than assumed.
    """

    session = ReplayResearchSession(
        lottery_type=RUNNER_LOTTERY_TYPE, paths=request.database_paths
    )
    result = session.replay_targets(
        dataset_id=request.dataset.dataset_id,
        dataset_version=request.dataset.dataset_version,
        target_draw_numbers=request.target_draw_numbers,
        strategy_ids=(request.strategy_id,),
        maximum_history_draws=request.maximum_history_draws,
        minimum_history_draws=request.minimum_history_draws,
    )
    snapshots = result.snapshots
    _require(
        len(snapshots) == len(request.target_draw_numbers),
        f"replay returned {len(snapshots)} snapshots for "
        f"{len(request.target_draw_numbers)} targets",
    )
    for snapshot, expected_draw_number in zip(
        snapshots, request.target_draw_numbers, strict=True
    ):
        _require(
            snapshot.target_draw_number == expected_draw_number,
            f"replay returned a snapshot for draw {snapshot.target_draw_number} where "
            f"{expected_draw_number} was requested; replay ordering was not preserved",
        )
        _require(
            snapshot.strategy_id == request.strategy_id,
            f"replay returned a snapshot for strategy {snapshot.strategy_id!r}, "
            f"not {request.strategy_id!r}",
        )
    return snapshots


def _validated_artifact(
    window_kind: WindowKind,
    evidence: StrategyEvaluationEvidence,
    *,
    request: CanonicalEvaluationRequest,
) -> CanonicalEvaluationArtifact:
    """Serialize, reload and validate one artifact through the existing authorities.

    The document is canonicalized to LCJ-1 bytes, loaded back through the same
    parse-and-model path an external reader uses, and required to re-serialize
    to identical bytes before it is validated -- so what this runner returns is
    what a reader would actually load, not merely what was built in memory.
    """

    raw = canonical_json.canonical_file_bytes(evidence.model_dump(mode="json", exclude_none=True))
    reloaded = StrategyEvaluationEvidence.model_validate(canonical_json.loads_canonical(raw))
    _require(
        canonical_json.canonical_file_bytes(reloaded.model_dump(mode="json", exclude_none=True))
        == raw,
        f"{window_kind.value} artifact does not survive a canonical serialize/load round trip",
    )
    report = validator.validate_evidence_artifact(
        reloaded, repo_root=request.repo_root, dataset=request.dataset
    )
    _require(
        report.schema_valid,
        f"{window_kind.value} artifact failed existing schema validation: "
        f"{[finding.code for finding in report.findings]}",
    )
    _require(
        report.findings == (),
        f"{window_kind.value} artifact failed existing semantic validation: "
        f"{[(finding.code, finding.pointer) for finding in report.findings]}",
    )
    return CanonicalEvaluationArtifact(
        window_kind=window_kind,
        evidence=reloaded,
        canonical_bytes=raw,
        artifact_content_sha256=reloaded.artifact_content_sha256,
        validation=report,
    )


def run_canonical_evaluation_evidence(
    request: CanonicalEvaluationRequest,
    *,
    metric_definitions: Mapping[str, MetricDefinitionBinding] | None = None,
) -> CanonicalEvaluationEvidenceResult:
    """Run one BIG_LOTTO SINGLE_TICKET strategy's whole evaluation vertical.

    Returns exactly four validated evidence artifacts in the evaluator's window
    order. Raises :class:`CanonicalEvaluationEvidenceRunnerError` -- before any
    artifact is returned -- on any dataset, replay, strategy, version, history,
    cutoff or outcome disagreement, and never converts a failed replay step
    into an observation.

    The strategy gate resolves through ``production_catalog()`` only: unlike
    :func:`resolve_single_ticket_descriptor`, no catalog can be injected here,
    so this gate can never admit a strategy the injected replay stack would
    then resolve differently.
    """

    _require(
        request.dataset.lottery_type is RUNNER_LOTTERY_TYPE,
        f"dataset snapshot is {request.dataset.lottery_type.value}; this vertical evaluates "
        f"{RUNNER_LOTTERY_TYPE.value} only",
    )
    _require(
        request.repo_root.is_dir(),
        f"repo_root {request.repo_root} is not a readable directory",
    )
    _require(
        request.database_paths.database.is_file(),
        f"no task-owned draw database exists at {request.database_paths.database}; this "
        "runner never falls back to the production database",
    )
    resolve_single_ticket_descriptor(request.strategy_id)

    draws_by_id = _index_dataset_draws(request.dataset)
    missing_targets = [
        draw_number
        for draw_number in request.target_draw_numbers
        if draw_number not in draws_by_id
    ]
    _require(
        not missing_targets,
        f"target draws are absent from the dataset snapshot: {', '.join(missing_targets)}",
    )

    snapshots = _replay_single_strategy(request)

    # V1A owns outcome binding, fail-closed replay-status handling and ordering.
    evaluation = evaluate_replayed_single_ticket_method(
        snapshots,
        _outcomes_from_dataset(snapshots, draws_by_id),
        method_family=request.method_family,
        replay_status=request.replay_status,
        contract=RUNNER_MATCH_CONTRACT,
    )
    _require(
        evaluation.identity.method_id == request.strategy_id,
        f"replay resolved method identity {evaluation.identity.method_id!r}, "
        f"not the requested {request.strategy_id!r}",
    )
    _require(
        request.expected_strategy_version is None
        or evaluation.identity.method_version == request.expected_strategy_version,
        f"replay resolved strategy version {evaluation.identity.method_version!r}, "
        f"not the expected {request.expected_strategy_version!r}",
    )

    # V1B owns the evidence envelope, the four windows and their order.
    documents = materialize_method_evaluation_evidence(
        dataset=request.dataset,
        snapshots=snapshots,
        evaluation=evaluation,
        metric_definitions=(
            load_metric_definition_bindings(request.repo_root)
            if metric_definitions is None
            else metric_definitions
        ),
        producer=request.producer,
        contract=RUNNER_MATCH_CONTRACT,
    )
    _require(
        len(documents) == EXPECTED_ARTIFACT_COUNT,
        f"materialization returned {len(documents)} artifacts, expected "
        f"{EXPECTED_ARTIFACT_COUNT}",
    )

    artifacts: list[CanonicalEvaluationArtifact] = []
    for window_kind, document in zip(EXPECTED_WINDOW_ORDER, documents, strict=True):
        _require(
            document.artifact_id
            == f"{request.producer.artifact_id_prefix}_{window_kind.value}",
            f"artifact {document.artifact_id!r} is not the {window_kind.value} artifact the "
            "evaluator's window order requires at this position",
        )
        artifacts.append(_validated_artifact(window_kind, document, request=request))

    return CanonicalEvaluationEvidenceResult(
        snapshots=snapshots,
        evaluation=evaluation,
        artifacts=tuple(artifacts),
    )


__all__ = [
    "EXPECTED_ARTIFACT_COUNT",
    "EXPECTED_WINDOW_ORDER",
    "RUNNER_LOTTERY_TYPE",
    "RUNNER_MATCH_CONTRACT",
    "CanonicalEvaluationArtifact",
    "CanonicalEvaluationEvidenceResult",
    "CanonicalEvaluationEvidenceRunnerError",
    "CanonicalEvaluationRequest",
    "resolve_single_ticket_descriptor",
    "run_canonical_evaluation_evidence",
]
