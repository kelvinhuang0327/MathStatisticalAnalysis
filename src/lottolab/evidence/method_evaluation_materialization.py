"""Materialize one base-method evaluation into canonical evidence artifacts.

The V1B bridge and nothing more: an existing
:class:`~lottolab.research.base_method_evaluation.MethodEvaluationRecord`,
the :class:`~lottolab.domain.replay_predictions.ReplayPredictionSnapshot`
sequence it was computed from, and the authoritative
:class:`~lottolab.evidence.models.DatasetSnapshot` become exactly four
validated :class:`~lottolab.evidence.models.StrategyEvaluationEvidence`
documents -- one per existing evaluator window, in the evaluator's own order.

This module owns no metric mathematics, no window semantics, no replay
engine, no ranking, no storage and no registry. Every number it writes is
either copied from that evaluator or recomputed from the supplied dataset
snapshot, and it re-runs the evaluator over its own reconstructed inputs and
requires exact equality before writing anything, so a record that did not
come from these snapshots and this dataset can never be materialized.

Three points deserve emphasis, because each one is a place where evidence
could otherwise become a fiction:

*Outcomes come from the dataset, never from the caller.* The realized main
and special numbers are read out of the supplied ``DatasetSnapshot``, which
is the same document the semantic validator later cross-checks against.

*Metric values stay exact.* The evaluator computes in ``Fraction``; a value
such as ``36/49`` has no lossless canonical decimal, so each observed value
is written as an :class:`~lottolab.evidence.models.ExactRational` and
survives model -> LCJ-1 -> load unchanged. ``random_reference`` and
``delta_vs_random`` remain evaluator-internal comparison semantics and are
deliberately not persisted as separate metric identities.

*A BIG_LOTTO ticket declares no special number.* The single-ticket replay
contract produces main numbers only, so the ticket shape here is zero and
``ticket.special_numbers`` is empty -- never a fabricated pick. ``special_hit``
is therefore decided by the committed domain scoring authority
(:func:`~lottolab.domain.lottery_rules.score_big_lotto_ticket`), which is the
same authority the validator recomputes against; this module defines no
second prize or scoring table.

``parameters`` carries the evaluator's semantic version rather than strategy
tuning knobs: these replayed strategies are deterministic functions of their
causal history and expose no tunable parameter through a replay snapshot, so
the evaluator identity is the honest thing for ``parameters_sha256`` -- and
binding it there makes a change in evaluator semantics visible to the
comparability contract instead of silently reinterpreted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import LOTTERY_RULE_CONTRACTS as _RULE_CONTRACTS
from lottolab.domain.lottery_rules import (
    LotteryRuleContract,
    resolve_lottery_rule_contract,
    score_big_lotto_ticket,
)
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.evidence import canonical_json
from lottolab.evidence.models import (
    DatasetReference,
    DatasetSnapshot,
    DrawEntry,
    DrawRef,
    DuplicateDrawPolicy,
    EvaluationMode,
    EvaluationProtocol,
    EvaluationRecord,
    EvaluationWindows,
    EvidenceStatus,
    ExactRational,
    MetricDefinition,
    MetricResult,
    MetricValueStatus,
    MissingDrawPolicy,
    OutcomeSource,
    ParameterSelectionMode,
    RuleParameters,
    SampleUnit,
    SequenceWindow,
    StrategyEvaluationEvidence,
    Ticket,
)
from lottolab.research.base_method_evaluation import (
    AVG_MATCH_ID,
    BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
    BIG_LOTTO_MATCH_CONTRACT,
    WINDOW_SIZES,
    LotteryMatchContract,
    MethodDrawObservation,
    MethodEvaluationRecord,
    MetricCell,
    WindowKind,
    evaluate_method,
)
from lottolab.research.replay_method_evaluation import (
    ReplayTargetOutcome,
    build_method_draw_observations,
    build_single_ticket_identity,
)

#: Evidence schema version. V1B adds only optional keys, so every document
#: written before it stays byte-identical and this stays put.
EVIDENCE_SCHEMA_VERSION = "1.0.0"

#: The five observed base-method metrics V1B persists, in canonical order.
V1B_METRIC_IDS: tuple[str, ...] = ("M1_PLUS", "M2_PLUS", "M3_PLUS", "M4_PLUS", AVG_MATCH_ID)

#: Repository-relative home of the committed V1B metric definitions.
METRIC_DEFINITION_DIRECTORY = "contracts/evidence/metric_definitions"

#: A single-ticket replay predicts main numbers only, so its ticket shape
#: declares no special number at all -- see the module docstring.
REPLAY_TICKET_SPECIAL_NUMBER_COUNT = 0

_PLACEHOLDER_SHA256 = "0" * 64


class MethodEvaluationMaterializationError(ValueError):
    """Closed-contract failure while materializing evaluation evidence."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MethodEvaluationMaterializationError(message)


@dataclass(frozen=True, slots=True)
class MetricDefinitionBinding:
    """One committed metric definition, bound by path and exact file hash."""

    metric_id: str
    metric_version: str
    definition_path: str
    definition_sha256: str
    sample_unit: SampleUnit
    aggregation: str


@dataclass(frozen=True, slots=True)
class EvidenceProducerIdentity:
    """Non-derivable provenance the caller alone can supply."""

    artifact_id_prefix: str
    evidence_status: EvidenceStatus
    produced_at: datetime
    producer_name: str
    method_source_git_oid: str
    feature_version: str
    feature_definition_path: str
    feature_definition_sha256: str
    producer_git_oid: str | None = None


def load_metric_definition_bindings(
    repo_root: Path, *, metric_ids: Sequence[str] = V1B_METRIC_IDS
) -> dict[str, MetricDefinitionBinding]:
    """Read the committed metric definitions and bind them by exact file bytes.

    ``metric_version``, ``sample_unit`` and ``aggregation`` are taken from the
    definition document itself rather than from a caller argument, so a
    materialized result can never disagree with the definition the validator
    will later resolve and hash.
    """

    bindings: dict[str, MetricDefinitionBinding] = {}
    for metric_id in metric_ids:
        relative = f"{METRIC_DEFINITION_DIRECTORY}/{metric_id.lower()}.json"
        path = repo_root / relative
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise MethodEvaluationMaterializationError(
                f"committed metric definition for {metric_id} is not readable at {relative}"
            ) from exc
        definition = MetricDefinition.model_validate(canonical_json.loads_canonical(raw))
        _require(
            definition.metric_id == metric_id,
            f"{relative} declares metric_id {definition.metric_id!r}, expected {metric_id!r}",
        )
        bindings[metric_id] = MetricDefinitionBinding(
            metric_id=metric_id,
            metric_version=definition.metric_version,
            definition_path=relative,
            definition_sha256=canonical_json.sha256_hex(raw),
            sample_unit=definition.sample_unit,
            aggregation=definition.aggregation,
        )
    return bindings


def _rule_parameters_for(contract: LotteryRuleContract) -> RuleParameters:
    """Bind the committed domain rule contract, with the replay's ticket shape."""

    payload: dict[str, object] = {
        "main_number_count": contract.main_number_count,
        "main_number_min": contract.main_number_min,
        "main_number_max": contract.main_number_max,
        "main_numbers_unique": contract.main_numbers_unique,
        "special_number_count": contract.special_number_count,
        "special_number_min": contract.special_number_min,
        "special_number_max": contract.special_number_max,
        "special_numbers_unique": contract.special_numbers_unique,
        "main_special_overlap_allowed": contract.main_special_overlap_allowed,
        "ticket_special_number_count": REPLAY_TICKET_SPECIAL_NUMBER_COUNT,
        "rule_contract_version": contract.contract_version,
        "rule_parameters_sha256": _PLACEHOLDER_SHA256,
    }
    draft = RuleParameters.model_validate(payload)
    payload["rule_parameters_sha256"] = canonical_json.self_key_removed_sha256(
        draft.model_dump(mode="json", exclude_none=True), "rule_parameters_sha256"
    )
    return RuleParameters.model_validate(payload)


def _draw_ref(draw: DrawEntry) -> DrawRef:
    return DrawRef(
        draw_id=draw.draw_id, draw_sequence=draw.draw_sequence, draw_date=draw.draw_date
    )


def _ticket_special_hit(
    lottery_type: LotteryType, predicted_main: tuple[int, ...], target: DrawEntry
) -> bool:
    """Decide ``special_hit`` for a ticket that selects no special number.

    Delegates to the committed domain scoring authority. No lottery gets a
    default here: an unsupported one fails closed rather than being scored a
    miss, which is what a fabricated ``False`` would silently claim.
    """

    if not target.special_numbers:
        # The game draws no special number, so there is nothing to hit.
        return False
    if lottery_type is LotteryType.BIG_LOTTO:
        _require(
            len(target.special_numbers) == 1,
            f"draw {target.draw_id} must carry exactly one special number to score special_hit",
        )
        return score_big_lotto_ticket(
            predicted_main_numbers=predicted_main,
            winning_main_numbers=target.main_numbers,
            winning_special_number=target.special_numbers[0],
        ).special_hit
    raise MethodEvaluationMaterializationError(
        f"no committed scoring authority can decide special_hit for a {lottery_type.value} "
        "ticket that selects no special number"
    )


def _exact_rational(value: Fraction) -> ExactRational:
    """One canonical, lossless representation of an exact evaluator value."""

    reduced = Fraction(value)  # normalizes sign and reduces to lowest terms
    return ExactRational(numerator=reduced.numerator, denominator=reduced.denominator)


def _metric_result(
    metric_id: str,
    cell: MetricCell,
    binding: MetricDefinitionBinding,
    *,
    draw_count: int,
    ticket_count: int,
) -> MetricResult:
    _require(
        cell.observed_value is not None,
        f"{metric_id} has no observed value for a non-empty window; refusing to "
        "materialize evidence for an unevaluable window",
    )
    assert cell.observed_value is not None  # narrowed by the check above
    sample_size = draw_count if binding.sample_unit is SampleUnit.DRAWS else ticket_count
    return MetricResult(
        metric_id=binding.metric_id,
        metric_version=binding.metric_version,
        metric_definition_path=binding.definition_path,
        metric_definition_sha256=binding.definition_sha256,
        sample_size=sample_size,
        sample_unit=binding.sample_unit,
        aggregation=binding.aggregation,
        value_status=MetricValueStatus.VALUE_PRESENT,
        value=_exact_rational(cell.observed_value),
        verification_state="DECLARED_NOT_RECOMPUTED",
    )


def _build_record(
    observation: MethodDrawObservation,
    snapshot: ReplayPredictionSnapshot,
    target: DrawEntry,
    cutoff: DrawEntry,
    *,
    lottery_type: LotteryType,
) -> EvaluationRecord:
    predicted = snapshot.predicted_main_numbers
    _require(
        predicted is not None,
        f"snapshot for draw {snapshot.target_draw_number} carries no predicted_main_numbers",
    )
    assert predicted is not None  # narrowed by the check above
    _require(
        list(predicted) == sorted(predicted),
        f"predicted_main_numbers for draw {snapshot.target_draw_number} are not in the "
        "canonical ascending order the rule contract requires; refusing to reorder a ticket",
    )

    main_hit_count = len(set(predicted) & set(target.main_numbers))
    _require(
        observation.main_hit_counts == (main_hit_count,),
        f"evaluated hit count for draw {target.draw_id} disagrees with the dataset outcome",
    )

    payload: dict[str, object] = {
        "target": _draw_ref(target).model_dump(mode="json"),
        "cutoff": _draw_ref(cutoff).model_dump(mode="json"),
        "tickets": [
            Ticket(
                ticket_id=f"{snapshot.strategy_id}:{target.draw_id}",
                main_numbers=predicted,
                special_numbers=(),
                main_hit_count=main_hit_count,
                special_hit=_ticket_special_hit(lottery_type, predicted, target),
            ).model_dump(mode="json", exclude_none=True)
        ],
        "actual_main_numbers": list(target.main_numbers),
        "actual_special_numbers": list(target.special_numbers),
        "outcome_source": OutcomeSource.DATASET_SNAPSHOT.value,
        "record_sha256": _PLACEHOLDER_SHA256,
    }
    draft = EvaluationRecord.model_validate(payload)
    payload["record_sha256"] = canonical_json.self_key_removed_sha256(
        draft.model_dump(mode="json", exclude_none=True), "record_sha256"
    )
    return EvaluationRecord.model_validate(payload)


def _build_windows(
    records: Sequence[EvaluationRecord],
    snapshots_by_draw_id: Mapping[str, ReplayPredictionSnapshot],
) -> EvaluationWindows:
    """Describe the causal shape this window's records actually have."""

    target_sequences = [record.target.draw_sequence for record in records]
    cutoff_sequences = [record.cutoff.draw_sequence for record in records]

    lags = {
        record.target.draw_sequence - record.cutoff.draw_sequence for record in records
    }
    _require(
        len(lags) == 1,
        "walk-forward cutoff lag is not uniform across this window's records; the existing "
        "EvaluationWindows contract cannot truthfully describe it "
        "(EVALUATION_WINDOW_MAPPING_UNRESOLVED)",
    )
    walk_forward_cutoff_lag = lags.pop()
    _require(walk_forward_cutoff_lag > 0, "cutoff must precede its target")

    causal_history_counts = [
        count
        for record in records
        if (count := snapshots_by_draw_id[record.target.draw_id].causal_history_count) is not None
    ]
    _require(
        len(causal_history_counts) == len(records),
        "every replay snapshot must declare its causal history count",
    )
    minimum_history = min(causal_history_counts)
    _require(
        minimum_history >= 1,
        "a replay step with no causal history cannot be described by the existing "
        "EvaluationWindows contract (EVALUATION_WINDOW_MAPPING_UNRESOLVED)",
    )

    maximum_cutoff_sequence = max(cutoff_sequences)
    maximum_cutoff_draw = next(
        record.cutoff
        for record in records
        if record.cutoff.draw_sequence == maximum_cutoff_sequence
    )
    return EvaluationWindows(
        evaluation_window=SequenceWindow(
            start_sequence=min(target_sequences), end_sequence=max(target_sequences)
        ),
        training_window=SequenceWindow(
            start_sequence=0, end_sequence=min(cutoff_sequences)
        ),
        # Each replay step recomputes from its own causal history; there is no
        # single frozen fitting window, and claiming one would be a fiction.
        parameter_selection_mode=ParameterSelectionMode.PER_STEP_REFIT,
        minimum_history=minimum_history,
        missing_draw_policy=MissingDrawPolicy.STRICT_NONE_TOLERATED,
        duplicate_draw_policy=DuplicateDrawPolicy.STRICT_NONE_TOLERATED,
        maximum_data_cutoff=maximum_cutoff_draw,
        walk_forward_cutoff_lag=walk_forward_cutoff_lag,
    )


def _outcomes_from_dataset(
    snapshots: Sequence[ReplayPredictionSnapshot], draws_by_id: Mapping[str, DrawEntry]
) -> tuple[ReplayTargetOutcome, ...]:
    """Read every realized outcome out of the authoritative dataset snapshot.

    Never accepts an outcome from the caller: this is the single point where
    "what actually happened" enters the artifact, and it is the same document
    the semantic validator later cross-checks the finished evidence against.
    """

    outcomes: list[ReplayTargetOutcome] = []
    for snapshot in snapshots:
        draw = draws_by_id.get(snapshot.target_draw_number)
        _require(
            draw is not None,
            f"target draw {snapshot.target_draw_number} is absent from the dataset snapshot",
        )
        assert draw is not None  # narrowed by the check above
        _require(
            draw.draw_date == snapshot.target_draw_date,
            f"dataset draw {draw.draw_id} is dated {draw.draw_date} but the snapshot "
            f"targets {snapshot.target_draw_date}",
        )
        outcomes.append(
            ReplayTargetOutcome(
                draw_number=draw.draw_id,
                draw_date=draw.draw_date,
                main_numbers=draw.main_numbers,
            )
        )
    return tuple(outcomes)


def materialize_method_evaluation_evidence(
    *,
    dataset: DatasetSnapshot,
    snapshots: Sequence[ReplayPredictionSnapshot],
    evaluation: MethodEvaluationRecord,
    metric_definitions: Mapping[str, MetricDefinitionBinding],
    producer: EvidenceProducerIdentity,
    contract: LotteryMatchContract = BIG_LOTTO_MATCH_CONTRACT,
) -> tuple[StrategyEvaluationEvidence, ...]:
    """Return exactly four evidence documents, in the evaluator's window order.

    Fails closed on any disagreement between the supplied evaluation record,
    the replay snapshots, and the dataset snapshot: the record is recomputed
    from inputs this function reconstructs itself and must match exactly.
    """

    _require(len(snapshots) > 0, "snapshots must not be empty")
    _require(
        set(metric_definitions) >= set(V1B_METRIC_IDS),
        f"metric definitions must cover {list(V1B_METRIC_IDS)}",
    )

    lottery_type = dataset.lottery_type
    _require(
        contract.lottery_type == lottery_type.value,
        f"match contract is for {contract.lottery_type}, dataset is {lottery_type.value}",
    )
    rule_contract = resolve_lottery_rule_contract(lottery_type, _RULE_CONTRACTS)
    _require(
        rule_contract is not None,
        f"no authoritative committed rule contract for {lottery_type.value}",
    )
    assert rule_contract is not None  # narrowed by the check above

    for snapshot in snapshots:
        _require(
            snapshot.dataset_id == dataset.dataset_id
            and snapshot.dataset_version == dataset.dataset_version,
            f"snapshot for draw {snapshot.target_draw_number} was replayed against dataset "
            f"{snapshot.dataset_id}/{snapshot.dataset_version}, not "
            f"{dataset.dataset_id}/{dataset.dataset_version}",
        )
        _require(
            snapshot.lottery_type == lottery_type,
            f"snapshot for draw {snapshot.target_draw_number} is not a "
            f"{lottery_type.value} snapshot",
        )

    draws_by_id = {draw.draw_id: draw for draw in dataset.draws}
    outcomes = _outcomes_from_dataset(snapshots, draws_by_id)

    # V1A owns binding, duplicate/missing/extra-target detection and ordering.
    observations = build_method_draw_observations(snapshots, outcomes, contract=contract)
    identity = build_single_ticket_identity(
        snapshots,
        observations,
        method_family=evaluation.identity.method_family,
        replay_status=evaluation.identity.replay_status,
    )
    recomputed = evaluate_method(contract, identity, observations)
    _require(
        recomputed == evaluation,
        "the supplied MethodEvaluationRecord does not match an evaluation recomputed from "
        "these snapshots and this dataset snapshot",
    )

    snapshots_by_draw_id = {
        snapshot.target_draw_number: snapshot for snapshot in snapshots
    }
    rule_parameters = _rule_parameters_for(rule_contract)
    parameters: dict[str, object] = {
        "base_method_evaluator_semantic_version": BASE_METHOD_EVALUATOR_SEMANTIC_VERSION
    }
    parameters_sha256 = canonical_json.sha256_hex(canonical_json.canonical_bytes(parameters))
    dataset_reference = DatasetReference(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        dataset_sha256=dataset.dataset_sha256,
        lottery_type=lottery_type,
        draw_count=len(dataset.draws),
        first_draw=_draw_ref(dataset.draws[0]),
        last_draw=_draw_ref(dataset.draws[-1]),
    )

    artifacts: list[StrategyEvaluationEvidence] = []
    for window_kind, requested_size in WINDOW_SIZES:
        artifacts.append(
            _build_artifact(
                window_kind=window_kind,
                selected=(
                    observations if requested_size is None else observations[-requested_size:]
                ),
                evaluation=evaluation,
                snapshots_by_draw_id=snapshots_by_draw_id,
                draws_by_id=draws_by_id,
                lottery_type=lottery_type,
                rule_parameters=rule_parameters,
                dataset_reference=dataset_reference,
                parameters=parameters,
                parameters_sha256=parameters_sha256,
                metric_definitions=metric_definitions,
                identity_method_id=identity.method_id,
                identity_method_version=identity.method_version,
                producer=producer,
            )
        )
    return tuple(artifacts)


def _build_artifact(
    *,
    window_kind: WindowKind,
    selected: Sequence[MethodDrawObservation],
    evaluation: MethodEvaluationRecord,
    snapshots_by_draw_id: Mapping[str, ReplayPredictionSnapshot],
    draws_by_id: Mapping[str, DrawEntry],
    lottery_type: LotteryType,
    rule_parameters: RuleParameters,
    dataset_reference: DatasetReference,
    parameters: Mapping[str, object],
    parameters_sha256: str,
    metric_definitions: Mapping[str, MetricDefinitionBinding],
    identity_method_id: str,
    identity_method_version: str,
    producer: EvidenceProducerIdentity,
) -> StrategyEvaluationEvidence:
    _require(
        len(selected) > 0,
        f"{window_kind.value} selected no draws; the evidence contract requires at least "
        "one record per artifact",
    )

    records: list[EvaluationRecord] = []
    for observation in selected:
        snapshot = snapshots_by_draw_id[observation.draw_id]
        _require(
            snapshot.cutoff_draw_number is not None,
            f"snapshot for draw {observation.draw_id} declares no causal cutoff",
        )
        assert snapshot.cutoff_draw_number is not None  # narrowed above
        cutoff = draws_by_id.get(snapshot.cutoff_draw_number)
        _require(
            cutoff is not None,
            f"cutoff draw {snapshot.cutoff_draw_number} is absent from the dataset snapshot",
        )
        assert cutoff is not None  # narrowed by the check above
        _require(
            cutoff.draw_date == snapshot.cutoff_draw_date,
            f"dataset cutoff draw {cutoff.draw_id} is dated {cutoff.draw_date} but the "
            f"snapshot declares {snapshot.cutoff_draw_date}",
        )
        records.append(
            _build_record(
                observation,
                snapshot,
                draws_by_id[observation.draw_id],
                cutoff,
                lottery_type=lottery_type,
            )
        )

    block = evaluation.windows[window_kind]
    _require(
        block.eligible_draw_count == len(records),
        f"{window_kind.value} evaluated {block.eligible_draw_count} draws but "
        f"{len(records)} records were materialized",
    )
    _require(
        set(block.metrics) == set(V1B_METRIC_IDS),
        f"{window_kind.value} exposes metrics {sorted(block.metrics)}, expected "
        f"{sorted(V1B_METRIC_IDS)}",
    )
    ticket_count = sum(len(record.tickets) for record in records)
    metric_results = tuple(
        _metric_result(
            metric_id,
            block.metrics[metric_id],
            metric_definitions[metric_id],
            draw_count=len(records),
            ticket_count=ticket_count,
        )
        for metric_id in V1B_METRIC_IDS
    )

    draft = StrategyEvaluationEvidence(
        schema_id="lottolab.evidence.strategy_evaluation_evidence",
        schema_version=EVIDENCE_SCHEMA_VERSION,
        artifact_id=f"{producer.artifact_id_prefix}_{window_kind.value}",
        evidence_status=producer.evidence_status,
        produced_at=producer.produced_at,
        producer_name=producer.producer_name,
        producer_git_oid=producer.producer_git_oid,
        artifact_content_sha256=_PLACEHOLDER_SHA256,
        strategy_id=identity_method_id,
        strategy_version=identity_method_version,
        method_id=identity_method_id,
        method_version=identity_method_version,
        method_source_git_oid=producer.method_source_git_oid,
        feature_version=producer.feature_version,
        feature_definition_path=producer.feature_definition_path,
        feature_definition_sha256=producer.feature_definition_sha256,
        parameters=dict(parameters),
        parameters_sha256=parameters_sha256,
        dataset_reference=dataset_reference,
        rule_parameters=rule_parameters,
        evaluation_mode=EvaluationMode.HISTORICAL_REPLAY,
        evaluation_protocol=EvaluationProtocol.WALK_FORWARD,
        evaluation_windows=_build_windows(records, snapshots_by_draw_id),
        records=tuple(records),
        metric_results=metric_results,
    )
    return draft.model_copy(
        update={
            "artifact_content_sha256": canonical_json.self_key_removed_sha256(
                draft.model_dump(mode="json", exclude_none=True), "artifact_content_sha256"
            )
        }
    )


__all__ = [
    "BASE_METHOD_EVALUATOR_SEMANTIC_VERSION",
    "EVIDENCE_SCHEMA_VERSION",
    "METRIC_DEFINITION_DIRECTORY",
    "REPLAY_TICKET_SPECIAL_NUMBER_COUNT",
    "V1B_METRIC_IDS",
    "EvidenceProducerIdentity",
    "MethodEvaluationMaterializationError",
    "MetricDefinitionBinding",
    "load_metric_definition_bindings",
    "materialize_method_evaluation_evidence",
]
